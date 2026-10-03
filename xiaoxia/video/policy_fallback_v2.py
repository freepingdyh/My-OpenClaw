# -*- coding: utf-8 -*-
"""Second-stage fal H3 policy fallback.

Strategy:
1) normal Sulafat reference-audio path;
2) if fal rejects reference_audio_urls, retry once with H3 native dialogue;
3) if native dialogue is also rejected by content checker, retry the same image one final time as silent image-to-video.

This keeps the user's image generation usable instead of failing the whole request because spoken content was moderated.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from xiaoxia.video import h3
from xiaoxia.video import policy_fallback


def _is_policy_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "content_policy_violation" in text or "content checker" in text


async def _generate_silent_turbo(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = h3._config()
    fal_client = app._get_fal_client()
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    arguments = {
        "prompt": h3._prompt(app, context, script="", native_dialogue=False),
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
                        print(f"🎬 [H3_SILENT_FALLBACK_QUEUE] {log.get('message', '')}")
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
        raise RuntimeError(f"H3_SILENT_FALLBACK_NO_URL: {result}")

    local_path, local_filename, local_url = await h3._download_video(app, video_url)
    return {
        "model_id": model_id,
        "video_url": video_url,
        "local_path": local_path,
        "local_filename": local_filename,
        "local_url": local_url,
        "voice_script": "",
        "used_voice": False,
        "voice_mode": "silent_turbo",
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "reference_audio_url": None,
        "policy_fallback_used": True,
        "policy_fallback_reason": "native_dialogue_content_checker",
    }


def install_h3_policy_fallback_v2(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_policy_fallback_v2_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original_generate_native = policy_fallback._generate_native_turbo

    async def generate_native_then_silent(app_obj, context):
        try:
            return await original_generate_native(app_obj, context)
        except Exception as exc:
            if not _is_policy_error(exc):
                raise
            print(
                "⚠️ [H3_NATIVE_DIALOGUE_POLICY_FALLBACK] "
                "native H3 dialogue rejected by fal; retrying once as silent image-to-video"
            )
            return await _generate_silent_turbo(app_obj, context)

    policy_fallback._generate_native_turbo = generate_native_then_silent
    h3._xiaoxia_policy_fallback_v2_installed = True
    return {
        "patched": True,
        "strategy": "reference_audio -> native_dialogue -> silent_turbo",
        "final_fallback": "silent_turbo",
    }
