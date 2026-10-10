# -*- coding: utf-8 -*-
"""Fallback for fal H3 reference-audio content-checker rejections.

If Sulafat/reference-to-video is rejected specifically at reference_audio_urls,
retry the same image once with H3 Max Turbo native dialogue instead of failing
back to Discord. This preserves normal dialogue text as much as possible and
avoids repeatedly sanitizing Xiaoxia into bland lines.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from xiaoxia.video import h3


def _is_reference_audio_policy_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return (
        "content_policy_violation" in text
        and "reference_audio_urls" in text
    )


async def _generate_native_turbo(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = h3._config()
    fal_client = app._get_fal_client()
    image_url = await h3._ensure_image_url(app, context)
    script = ""
    if cfg.get("voice_enabled"):
        try:
            script = await h3._build_script(app, context, cfg)
        except Exception as exc:
            print(f"⚠️ [H3_NATIVE_FALLBACK_SCRIPT_FAILED] {type(exc).__name__}: {exc}")

    model_id = cfg["image_model"]
    arguments = {
        "prompt": h3._prompt(app, context, script=script, native_dialogue=bool(script)),
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🎬 [H3_NATIVE_FALLBACK_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            model_id,
            arguments=arguments,
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    result = await asyncio.to_thread(_subscribe)
    video = result.get("video") if isinstance(result, dict) else None
    video_url = video.get("url") if isinstance(video, dict) else None
    if not video_url:
        raise RuntimeError(f"H3_NATIVE_FALLBACK_NO_URL: {result}")

    local_path, local_filename, local_url = await h3._download_video(app, video_url)
    return {
        "model_id": model_id,
        "video_url": video_url,
        "local_path": local_path,
        "local_filename": local_filename,
        "local_url": local_url,
        "voice_script": script,
        "used_voice": bool(script),
        "voice_mode": "native_turbo",
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "reference_audio_url": None,
        "policy_fallback_used": True,
        "policy_fallback_reason": "reference_audio_content_checker",
    }


def install_h3_policy_fallback(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_policy_fallback_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original_generate = h3.generate_h3_video

    async def generate_with_policy_fallback(app_obj, context):
        try:
            return await original_generate(app_obj, context)
        except Exception as exc:
            if not _is_reference_audio_policy_error(exc):
                raise
            print(
                "⚠️ [H3_REFERENCE_AUDIO_POLICY_FALLBACK] "
                "reference audio rejected by fal; retrying once with native turbo dialogue"
            )
            return await _generate_native_turbo(app_obj, context)

    h3.generate_h3_video = generate_with_policy_fallback
    app.generate_h3_video_from_context = lambda context: generate_with_policy_fallback(app, context)

    # legacy_command imported generate_h3_video by value, so patch that binding too.
    try:
        from xiaoxia.video import legacy_command
        legacy_command.generate_h3_video = generate_with_policy_fallback
    except Exception as exc:
        print(f"⚠️ [H3_POLICY_FALLBACK_LEGACY_PATCH_WARN] {type(exc).__name__}: {exc}")

    h3._xiaoxia_policy_fallback_installed = True
    return {
        "patched": True,
        "strategy": "reference_audio_policy_error_then_native_turbo_once",
        "reference_voice": "Sulafat",
        "fallback_voice": "H3 native",
    }
