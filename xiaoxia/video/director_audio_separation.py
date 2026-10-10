# -*- coding: utf-8 -*-
"""v1.12.06af — keep Gemini/Sulafat voiceover out of the H3 provider prompt.

The H3 request is visual-only plus natural ambience:
- Gemini Director still decides Hero Action / Reaction / Camera and a voiceover line.
- The voiceover text is NOT sent to H3.
- H3 renders motion + ambience first.
- Sulafat TTS is generated separately and mixed over the finished H3 clip with ffmpeg.
- If TTS/mix fails, keep the successful H3 ambient clip; never fall back by injecting narration into H3.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from xiaoxia.video import h3, h3_director_mode, slim_h3_prompt, voiceover_mode


def build_visual_only_h3_prompt(plan: Dict[str, str]) -> str:
    action = str(plan.get("hero_action") or "").strip()
    reaction = str(plan.get("reaction") or "").strip()
    camera = str(plan.get("camera") or "").strip()
    ambience = str(plan.get("ambience") or "").strip()

    parts = ["Use Image 1 as the starting frame."]
    if action:
        parts.append(f"Action: {action}")
    if reaction:
        parts.append(f"Reaction: {reaction}")
    if camera:
        parts.append(f"Camera: {camera}.")
    if ambience:
        parts.append(f"Natural ambience: {ambience}.")
    parts.append("No dialogue, music or subtitles.")
    return " ".join(parts)


async def _generate_h3_visual_then_sulafat(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = voiceover_mode._config()
    plan = await h3_director_mode.build_h3_director_plan(app, context, cfg)
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    submitted_prompt = build_visual_only_h3_prompt(plan)

    args = {
        "prompt": submitted_prompt,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }

    # H3 sees no narration text and no speech instruction.
    result = await voiceover_mode._subscribe(app, model_id, args, "H3_DIRECTOR_VISUAL_ONLY_QUEUE")
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_DIRECTOR_NO_URL: {result}")

    path, filename, public = await h3._download_video(app, url)
    if not path:
        raise RuntimeError("H3_DIRECTOR_DOWNLOAD_FAILED")

    expanded = slim_h3_prompt._expanded_prompt(result)
    context["h3_submitted_prompt"] = submitted_prompt
    context["h3_expanded_prompt"] = expanded
    print(
        "🎬🔇 [H3_VISUAL_ONLY_PROMPT] "
        f"submitted={submitted_prompt!r} expanded={expanded!r}"
    )

    final_path = path
    final_filename = filename
    final_public = public
    voice_script = str(plan.get("voiceover") or "").strip()
    used_voice = False
    voice_mode = "ambient_only"

    # Sulafat is strictly post-production. Failure here never changes the H3 request.
    voice_path = None
    if voice_script:
        try:
            voice_path = await voiceover_mode._tts_sulafat_voiceover(app, voice_script, cfg)
            mixed = await voiceover_mode._mix_voiceover(path, voice_path, cfg["duration"])
            final_path = mixed
            final_filename = os.path.basename(mixed)
            final_public = f"https://xiaoxia0320.zeabur.app/gallery/{final_filename}"
            used_voice = True
            voice_mode = "voiceover_sulafat_postmix"
            print("🎙️ [H3_SULAFAT_POSTMIX_OK] narration_was_not_sent_to_h3=true")
        except Exception as exc:
            print(f"⚠️ [H3_SULAFAT_POSTMIX_FAILED] {type(exc).__name__}: {exc}")
        finally:
            if voice_path:
                try:
                    os.remove(voice_path)
                except Exception:
                    pass

    return {
        "model_id": model_id,
        "video_url": url,
        "local_path": final_path,
        "local_filename": final_filename,
        "local_url": final_public,
        "voice_script": voice_script if used_voice else "",
        "used_voice": used_voice,
        "voice_mode": voice_mode,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "ambient_audio": True,
        "video_theme": plan["video_theme"],
        "motion_level": plan["motion_level"],
        "director_plan": plan,
        "submitted_prompt": submitted_prompt,
        "expanded_prompt": expanded,
        "h3_received_voiceover": False,
    }


def install_director_audio_separation(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_director_audio_separation_installed", False):
        return {"patched": False, "reason": "already_installed"}

    h3_director_mode.build_compact_h3_prompt = build_visual_only_h3_prompt
    h3_director_mode._generate_h3_native_directed = _generate_h3_visual_then_sulafat
    if hasattr(app, "h3_generate_native_directed"):
        app.h3_generate_native_directed = _generate_h3_visual_then_sulafat
    h3_director_mode._xiaoxia_director_audio_separation_installed = True

    return {
        "patched": True,
        "h3_prompt_voiceover": False,
        "h3_audio": "natural ambience only",
        "sulafat": "postmix only",
        "native_voice_fallback": False,
        "prompt_sanitizing_retry": False,
        "fal_native_image_transport_preserved": True,
    }
