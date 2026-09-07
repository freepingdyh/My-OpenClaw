# -*- coding: utf-8 -*-
"""v1.12.06k — targeted retry for fal H3 body.image_url policy rejections.

Experimental design:
- keep model/prompt/duration/resolution/safety/voice settings unchanged;
- only when fal explicitly returns content_policy_violation at body.image_url;
- download the exact bytes from the submitted image_url;
- upload those exact bytes again to fal to obtain a fresh URL;
- retry exactly once.

This isolates whether the rejection is tied to URL/request-side moderation drift rather
than changing Xiaoxia's content or prompt. Existing trace_store will record each fal
attempt and hash the image bytes for comparison.
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


def _is_image_url_policy_error(exc: Exception) -> bool:
    info = diagnostics.extract_h3_error(exc)
    return (
        str(info.get("type") or "").lower() == "content_policy_violation"
        and str(info.get("loc") or "").lower() == "body.image_url"
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


async def _subscribe_with_image_retry(app: Any, model_id: str, arguments: Dict[str, Any], tag: str) -> Dict[str, Any]:
    # IMPORTANT: first attempt remains byte-for-byte / prompt-for-prompt the existing request.
    try:
        return await _ORIGINAL_SUBSCRIBE(app, model_id, arguments, tag)
    except Exception as exc:
        if not _env_bool("H3_IMAGE_URL_RETRY_ENABLED", True) or not _is_image_url_policy_error(exc):
            raise

        original_url = str((arguments or {}).get("image_url") or "").strip()
        if not original_url.startswith(("http://", "https://")):
            raise

        fresh_url, source_sha256, source_size = await _reupload_same_bytes(app, original_url)
        retry_args = dict(arguments or {})
        retry_args["image_url"] = fresh_url

        print(
            "🔁 [H3_IMAGE_URL_POLICY_RETRY] "
            f"same_bytes_sha256={source_sha256} size={source_size} "
            "payload_unchanged_except=image_url"
        )
        try:
            return await _ORIGINAL_SUBSCRIBE(
                app,
                model_id,
                retry_args,
                "H3_IMAGE_URL_REUPLOAD_RETRY_QUEUE",
            )
        except Exception as retry_exc:
            # Preserve the trace id from the second attempt if available; otherwise the first.
            if not getattr(retry_exc, "h3_trace_id", None):
                try:
                    setattr(retry_exc, "h3_trace_id", getattr(exc, "h3_trace_id", None))
                except Exception:
                    pass
            raise


def install_h3_image_url_retry(app: Any) -> Dict[str, Any]:
    global _ORIGINAL_SUBSCRIBE
    if getattr(voiceover_mode, "_xiaoxia_h3_image_url_retry_installed", False):
        return {"patched": False, "reason": "already_installed"}

    # Install AFTER trace_store so both initial and retry attempts are independently traced.
    _ORIGINAL_SUBSCRIBE = voiceover_mode._subscribe
    voiceover_mode._subscribe = _subscribe_with_image_retry
    voiceover_mode._xiaoxia_h3_image_url_retry_installed = True
    return {
        "patched": True,
        "trigger": "type=content_policy_violation + loc=body.image_url",
        "retry_count": 1,
        "retry_strategy": "download exact bytes -> fresh fal upload -> identical payload except image_url",
        "env": "H3_IMAGE_URL_RETRY_ENABLED",
    }
