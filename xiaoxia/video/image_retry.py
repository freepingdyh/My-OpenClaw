# -*- coding: utf-8 -*-
"""v1.12.06l — targeted retry chain for fal H3 policy rejections.

Experimental design:
- keep the first request untouched;
- only when fal explicitly returns content_policy_violation at body.image_url:
  1) download the exact bytes from the submitted image_url;
  2) upload those exact bytes again to fal to obtain a fresh URL;
  3) retry with an otherwise identical payload;
- if that fresh-URL retry moves the rejection to body.prompt, retry one final time
  with the SAME fresh image URL and a minimal neutral motion prompt.

This gives us a clean three-step diagnostic chain without regenerating Xiaoxia:
A) original URL + original prompt
B) fresh URL, same bytes + original prompt
C) same fresh URL + minimal prompt (only if B is blocked at body.prompt)

Existing trace_store records every fal attempt and hashes the image bytes, so the
Discord /H3紀錄 command can compare the attempts rather than relying on guesses.
"""
from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
import tempfile
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from xiaoxia.video import diagnostics, voiceover_mode


_ORIGINAL_SUBSCRIBE = None


def _is_policy_error_at(exc: Exception, loc: str) -> bool:
    info = diagnostics.extract_h3_error(exc)
    return (
        str(info.get("type") or "").lower() == "content_policy_violation"
        and str(info.get("loc") or "").lower() == str(loc or "").lower()
    )


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "關", "關閉"}


async def _download_exact_bytes(url: str) -> Tuple[bytes, str, Optional[str]]:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"H3_IMAGE_RETRY_DOWNLOAD_HTTP_{resp.status}")
            data = await resp.read()
            if not data:
                raise RuntimeError("H3_IMAGE_RETRY_EMPTY_IMAGE")
            content_type = str(resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() or None
            return data, hashlib.sha256(data).hexdigest(), content_type


def _temp_suffix(url: str, content_type: Optional[str]) -> str:
    suffix = os.path.splitext(urlparse(url).path)[1].lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type) or ""
        if guessed == ".jpe":
            guessed = ".jpg"
        if guessed:
            return guessed
    return ".jpg"


async def _reupload_same_bytes(app: Any, image_url: str) -> Tuple[str, str, int]:
    data, sha256, content_type = await _download_exact_bytes(image_url)
    suffix = _temp_suffix(image_url, content_type)
    fd, path = tempfile.mkstemp(prefix="xiaoxia_h3_retry_", suffix=suffix)
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(data)
        fal_client = app._get_fal_client()
        fresh_url = await asyncio.to_thread(fal_client.upload_file, path)
        if not fresh_url:
            raise RuntimeError("H3_IMAGE_RETRY_UPLOAD_NO_URL")
        return str(fresh_url), sha256, len(data)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def _minimal_prompt() -> str:
    return (
        "Animate the same person from the source image with subtle natural motion. "
        "Keep the same face, hairstyle, clothing, body proportions, camera view and location. "
        "Her mouth stays relaxed and mostly closed; she is not speaking. "
        "Use only small realistic movements: blinking, breathing, slight eye movement, tiny head movement, "
        "and gentle hair or fabric motion. Avoid exaggerated facial expressions, wide mouth movement, "
        "strong jaw motion, neck strain, or dramatic acting. Generate natural scene ambience only, "
        "with no dialogue and no music."
    )


async def _subscribe_with_image_retry(app: Any, model_id: str, arguments: Dict[str, Any], tag: str) -> Dict[str, Any]:
    # Attempt 1: the existing request, unchanged.
    try:
        return await _ORIGINAL_SUBSCRIBE(app, model_id, arguments, tag)
    except Exception as first_exc:
        if not _env_bool("H3_IMAGE_URL_RETRY_ENABLED", True) or not _is_policy_error_at(first_exc, "body.image_url"):
            raise

        original_url = str((arguments or {}).get("image_url") or "").strip()
        if not original_url.startswith(("http://", "https://")):
            raise

        fresh_url, source_sha256, source_size = await _reupload_same_bytes(app, original_url)
        retry_args = dict(arguments or {})
        retry_args["image_url"] = fresh_url

        print(
            "🔁 [H3_IMAGE_URL_POLICY_RETRY_2] "
            f"same_bytes_sha256={source_sha256} size={source_size} "
            "payload_unchanged_except=image_url"
        )

        # Attempt 2: exact same bytes at a fresh URL; prompt and all other arguments unchanged.
        try:
            return await _ORIGINAL_SUBSCRIBE(
                app,
                model_id,
                retry_args,
                "H3_IMAGE_URL_REUPLOAD_RETRY_QUEUE",
            )
        except Exception as second_exc:
            # If the fresh URL passes image checking but fal now explicitly points to body.prompt,
            # run one final isolated prompt test on the SAME fresh image URL.
            if not _env_bool("H3_PROMPT_AFTER_IMAGE_RETRY_ENABLED", True) or not _is_policy_error_at(second_exc, "body.prompt"):
                if not getattr(second_exc, "h3_trace_id", None):
                    try:
                        setattr(second_exc, "h3_trace_id", getattr(first_exc, "h3_trace_id", None))
                    except Exception:
                        pass
                raise

            final_args = dict(retry_args)
            final_args["prompt"] = _minimal_prompt()
            print(
                "🔁 [H3_IMAGE_URL_POLICY_RETRY_3] "
                "second_attempt_loc=body.prompt -> same_fresh_image_url + minimal_prompt"
            )

            # Attempt 3: same fresh image URL, only prompt is reduced.
            try:
                return await _ORIGINAL_SUBSCRIBE(
                    app,
                    model_id,
                    final_args,
                    "H3_IMAGE_REUPLOAD_MINIMAL_PROMPT_QUEUE",
                )
            except Exception as third_exc:
                if not getattr(third_exc, "h3_trace_id", None):
                    try:
                        setattr(third_exc, "h3_trace_id", getattr(second_exc, "h3_trace_id", None) or getattr(first_exc, "h3_trace_id", None))
                    except Exception:
                        pass
                raise


def install_h3_image_url_retry(app: Any) -> Dict[str, Any]:
    global _ORIGINAL_SUBSCRIBE
    if getattr(voiceover_mode, "_xiaoxia_h3_image_url_retry_installed", False):
        return {"patched": False, "reason": "already_installed"}

    # Install AFTER trace_store so every attempt is independently traced.
    _ORIGINAL_SUBSCRIBE = voiceover_mode._subscribe
    voiceover_mode._subscribe = _subscribe_with_image_retry
    voiceover_mode._xiaoxia_h3_image_url_retry_installed = True
    return {
        "patched": True,
        "trigger_1": "type=content_policy_violation + loc=body.image_url",
        "retry_2": "exact same bytes -> fresh fal URL -> identical payload except image_url",
        "trigger_2": "retry_2 fails at body.prompt",
        "retry_3": "same fresh image URL -> minimal prompt",
        "max_attempts": 3,
        "env_image_retry": "H3_IMAGE_URL_RETRY_ENABLED",
        "env_prompt_after_image_retry": "H3_PROMPT_AFTER_IMAGE_RETRY_ENABLED",
    }
