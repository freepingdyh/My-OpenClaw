# -*- coding: utf-8 -*-
"""Prompt-specific fallback for fal H3 content-policy rejections.

Only activates when fal explicitly reports:
  type=content_policy_violation
  loc=body.prompt

The normal Xiaoxia prompt remains untouched. On this exact error, retry with a
minimal neutral motion prompt. First preserve Sulafat/reference audio when that
mode is active; if that still fails by policy, fall back once to minimal silent
Turbo. This avoids guessing at image/audio causes when the structured error says
`body.prompt`.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict

from xiaoxia.video import h3
from xiaoxia.video import diagnostics


def _is_prompt_policy_error(exc: Exception) -> bool:
    info = diagnostics.extract_h3_error(exc)
    return (
        str(info.get("type") or "").lower() == "content_policy_violation"
        and str(info.get("loc") or "").lower() == "body.prompt"
    )


def _minimal_prompt(*, with_audio: bool = False) -> str:
    parts = [
        "Animate Image 1 naturally while keeping the same person, clothing, camera view, and setting.",
        "Use subtle realistic motion such as blinking, breathing, small head movement, and gentle hand movement appropriate to the existing pose.",
        "Do not add people, text, subtitles, logos, or change the location.",
    ]
    if with_audio:
        parts.append("Synchronize the visible speech naturally to Audio 1.")
    else:
        parts.append("Use only subtle natural ambient sound and no dialogue.")
    return " ".join(parts)


async def _subscribe(app: Any, model_id: str, arguments: Dict[str, Any], log_tag: str):
    fal_client = app._get_fal_client()

    def run():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🎬 [{log_tag}] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            model_id,
            arguments=arguments,
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    return await asyncio.to_thread(run)


async def _finish_result(app: Any, result: Dict[str, Any], *, model_id: str, cfg: Dict[str, Any], voice_mode: str, script: str = "", fallback_stage: str):
    video = result.get("video") if isinstance(result, dict) else None
    video_url = video.get("url") if isinstance(video, dict) else None
    if not video_url:
        raise RuntimeError(f"H3_PROMPT_FALLBACK_NO_URL: {result}")
    local_path, local_filename, local_url = await h3._download_video(app, video_url)
    return {
        "model_id": model_id,
        "video_url": video_url,
        "local_path": local_path,
        "local_filename": local_filename,
        "local_url": local_url,
        "voice_script": script,
        "used_voice": bool(script and voice_mode == "reference_audio"),
        "voice_mode": voice_mode,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "reference_audio_url": None,
        "policy_fallback_used": True,
        "policy_fallback_reason": "body.prompt",
        "policy_fallback_stage": fallback_stage,
    }


async def _minimal_reference_audio(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]):
    image_url = await h3._ensure_image_url(app, context)
    script = await h3._build_script(app, context, cfg)
    audio_path = None
    try:
        audio_path = await h3._tts_wav(app, script, cfg)
        fal_client = app._get_fal_client()
        audio_url = await asyncio.to_thread(fal_client.upload_file, audio_path)
        model_id = cfg["reference_model"]
        args = {
            "prompt": _minimal_prompt(with_audio=True),
            "duration": cfg["duration"],
            "resolution": cfg["resolution"],
            "enable_safety_checker": cfg["safety"],
            "prompt_expansion_mode": cfg["expansion"],
            "aspect_ratio": "adaptive",
            "reference_image_urls": [image_url],
            "reference_audio_urls": [audio_url],
        }
        result = await _subscribe(app, model_id, args, "H3_MIN_PROMPT_REFERENCE_QUEUE")
        out = await _finish_result(
            app, result, model_id=model_id, cfg=cfg,
            voice_mode="reference_audio", script=script,
            fallback_stage="minimal_reference_audio",
        )
        out["reference_audio_url"] = audio_url
        return out
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


async def _minimal_silent_turbo(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]):
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    args = {
        "prompt": _minimal_prompt(with_audio=False),
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }
    result = await _subscribe(app, model_id, args, "H3_MIN_PROMPT_SILENT_QUEUE")
    return await _finish_result(
        app, result, model_id=model_id, cfg=cfg,
        voice_mode="silent_turbo", script="",
        fallback_stage="minimal_silent_turbo",
    )


def install_h3_prompt_policy_fallback(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_prompt_policy_fallback_installed", False):
        return {"patched": False, "reason": "already_installed"}

    previous_generate = h3.generate_h3_video

    async def generate_with_prompt_retry(app_obj, context):
        try:
            return await previous_generate(app_obj, context)
        except Exception as exc:
            if not _is_prompt_policy_error(exc):
                raise

            cfg = h3._config()
            print(
                "⚠️ [H3_PROMPT_POLICY_RETRY] loc=body.prompt "
                f"safety_checker={cfg.get('safety')} voice_mode={cfg.get('voice_mode')}"
            )

            # The structured error says prompt, so keep the image untouched and
            # first retry only the prompt while preserving Sulafat when possible.
            if (
                cfg.get("voice_enabled")
                and cfg.get("voice_mode") == "reference_audio"
                and os.environ.get("GEMINI_API_KEY")
            ):
                try:
                    return await _minimal_reference_audio(app_obj, context, cfg)
                except Exception as ref_exc:
                    info = diagnostics.extract_h3_error(ref_exc)
                    if str(info.get("type") or "").lower() != "content_policy_violation":
                        raise
                    print(
                        "⚠️ [H3_MIN_PROMPT_REFERENCE_REJECTED] "
                        f"loc={info.get('loc')} -> minimal silent turbo"
                    )

            return await _minimal_silent_turbo(app_obj, context, cfg)

    h3.generate_h3_video = generate_with_prompt_retry
    app.generate_h3_video_from_context = lambda context: generate_with_prompt_retry(app, context)

    # diagnostics and legacy command call h3.generate_h3_video dynamically, so no
    # additional by-value patch is needed here.
    h3._xiaoxia_prompt_policy_fallback_installed = True
    return {
        "patched": True,
        "trigger": "type=content_policy_violation + loc=body.prompt",
        "normal_prompt_unchanged": True,
        "retry_1": "minimal prompt + Sulafat reference audio",
        "retry_2": "minimal prompt + silent turbo",
    }
