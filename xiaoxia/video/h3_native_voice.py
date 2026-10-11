# -*- coding: utf-8 -*-
"""v1.12.06ai — H3 Max Turbo native voice, no Gemini TTS post-mix.

fal's H3 Max Turbo API exposes no discrete voice/speaker parameter. Native voice is
therefore directed in the H3 prompt. Keep ag's image transport and prompt-422 recovery.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import h3, h3_director_mode, slim_h3_prompt, voiceover_mode


def build_h3_native_voice_prompt(plan: Dict[str, str]) -> str:
    action = str(plan.get("hero_action") or "").strip()
    reaction = str(plan.get("reaction") or "").strip()
    camera = str(plan.get("camera") or "").strip()
    ambience = str(plan.get("ambience") or "").strip()
    line = str(plan.get("voiceover") or "").strip()
    parts = ["Use Image 1 as the starting frame."]
    if action:
        parts.append(f"Action: {action}")
    if reaction:
        parts.append(f"Reaction: {reaction}")
    if camera:
        parts.append(f"Camera: {camera}.")
    if line:
        parts.append(
            "Native audio: an off-screen young Taiwanese woman in her early twenties speaks in a bright, sweet, "
            "natural conversational voice, youthful and clear, with a light smile and relaxed everyday delivery; "
            "avoid a mature, husky, announcer-like or theatrical tone. "
            f'She says in Traditional Chinese: "{line}". The woman on screen does not lip-sync.'
        )
    if ambience:
        parts.append(f"Natural ambience underneath: {ambience}.")
    parts.append("No music or subtitles.")
    return " ".join(parts)


async def _generate_h3_native_voice(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = voiceover_mode._config()
    plan = await h3_director_mode.build_h3_director_plan(app, context, cfg)
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    submitted_prompt = build_h3_native_voice_prompt(plan)
    args = {
        "prompt": submitted_prompt,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }
    result = await voiceover_mode._subscribe(app, model_id, args, "H3_NATIVE_YOUNG_VOICE_QUEUE")
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_NATIVE_YOUNG_VOICE_NO_URL: {result}")
    path, filename, public = await h3._download_video(app, url)
    if not path:
        raise RuntimeError("H3_NATIVE_YOUNG_VOICE_DOWNLOAD_FAILED")
    expanded = slim_h3_prompt._expanded_prompt(result)
    context["h3_submitted_prompt"] = submitted_prompt
    context["h3_expanded_prompt"] = expanded
    print(f"🎙️ [H3_NATIVE_VOICE] submitted={submitted_prompt!r} expanded={expanded!r}")
    return {
        "model_id": model_id,
        "video_url": url,
        "local_path": path,
        "local_filename": filename,
        "local_url": public,
        "voice_script": str(plan.get("voiceover") or "").strip(),
        "used_voice": bool(str(plan.get("voiceover") or "").strip()),
        "voice_mode": "h3_native_prompted_young_voice",
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "ambient_audio": True,
        "video_theme": plan["video_theme"],
        "motion_level": plan["motion_level"],
        "director_plan": plan,
        "submitted_prompt": submitted_prompt,
        "expanded_prompt": expanded,
        "h3_received_voiceover": True,
    }


def install_h3_native_voice(app: Any) -> Dict[str, Any]:
    h3_director_mode.build_compact_h3_prompt = build_h3_native_voice_prompt
    h3_director_mode._generate_h3_native_directed = _generate_h3_native_voice
    if hasattr(app, "h3_generate_native_directed"):
        app.h3_generate_native_directed = _generate_h3_native_voice
    return {
        "patched": True,
        "image_model": "minimax/h3-max-turbo/image-to-video",
        "audio": "H3 native",
        "voice_control": "prompt-directed; fal API has no voice/speaker field",
        "gemini_tts_postmix": False,
    }
