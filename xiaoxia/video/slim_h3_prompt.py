# -*- coding: utf-8 -*-
"""v1.12.06ad — slim H3 prompt + exact prompt trace.

Gemini remains responsible for understanding Daxia's intent. This layer only turns the
Director plan into one short, coherent H3 instruction. It deliberately avoids an
application-side semantic/content re-review. Provider safety remains enabled; if the
provider rejects a prompt, the error is surfaced instead of silently replacing the
requested action with a sanitized fallback.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from xiaoxia.video import archive, h3, h3_director_mode, voiceover_mode

_ORIGINAL_ARCHIVE = archive.archive_h3_video


def build_slim_h3_prompt(plan: Dict[str, str]) -> str:
    action = str(plan.get("hero_action") or "").strip()
    reaction = str(plan.get("reaction") or "").strip()
    camera = str(plan.get("camera") or "").strip()
    voice = str(plan.get("voiceover") or "").strip()
    ambience = str(plan.get("ambience") or "").strip()

    parts = ["Use Image 1 as the starting frame."]
    if action:
        parts.append(f"Action: {action}")
    if reaction:
        parts.append(f"Reaction: {reaction}")
    if camera:
        parts.append(f"Camera: {camera}.")
    if voice:
        parts.append(
            "Xiaoxia performs silently while an off-screen young Taiwanese female voice says: "
            f'"{voice}".'
        )
    if ambience:
        parts.append(f"Natural ambience: {ambience}.")
    parts.append("No music or subtitles.")
    return " ".join(parts)


def _expanded_prompt(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    for key in ("expanded_prompt", "prompt", "final_prompt"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("expanded_prompt", "prompt", "final_prompt"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


async def _generate_h3_native_directed(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = voiceover_mode._config()
    plan = await h3_director_mode.build_h3_director_plan(app, context, cfg)
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    submitted_prompt = build_slim_h3_prompt(plan)

    args = {
        "prompt": submitted_prompt,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }

    # No application-side re-review/sanitizing retry here. Provider safety stays on.
    result = await voiceover_mode._subscribe(app, model_id, args, "H3_DIRECTOR_SLIM_QUEUE")

    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_DIRECTOR_NO_URL: {result}")
    path, filename, public = await h3._download_video(app, url)
    if not path:
        raise RuntimeError("H3_DIRECTOR_DOWNLOAD_FAILED")

    expanded = _expanded_prompt(result)
    context["h3_submitted_prompt"] = submitted_prompt
    context["h3_expanded_prompt"] = expanded
    print(
        "🎬 [H3_SLIM_PROMPT] "
        f"submitted={submitted_prompt!r} expanded={expanded!r}"
    )

    return {
        "model_id": model_id,
        "video_url": url,
        "local_path": path,
        "local_filename": filename,
        "local_url": public,
        "voice_script": plan["voiceover"],
        "used_voice": True,
        "voice_mode": "voiceover_h3_native",
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "ambient_audio": True,
        "video_theme": plan["video_theme"],
        "motion_level": plan["motion_level"],
        "director_plan": plan,
        "submitted_prompt": submitted_prompt,
        "expanded_prompt": expanded,
    }


async def _archive_h3_video_with_prompt_trace(app: Any, **kwargs) -> Dict[str, Any]:
    result = kwargs.get("result") if isinstance(kwargs.get("result"), dict) else {}
    record = await _ORIGINAL_ARCHIVE(app, **kwargs)
    video_id = str(record.get("video_id") or "")
    submitted = str(result.get("submitted_prompt") or "")
    expanded = str(result.get("expanded_prompt") or "")
    if not video_id or (not submitted and not expanded):
        return record

    async with archive._STORE_LOCK:
        records = await asyncio.to_thread(archive._load_records_sync)
        for item in records:
            if str(item.get("video_id") or "") == video_id:
                item["submitted_prompt"] = submitted
                item["expanded_prompt"] = expanded
                record = dict(item)
                break
        await asyncio.to_thread(archive._write_records_sync, records)
    return record


def install_slim_h3_prompt(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_slim_h3_prompt_installed", False):
        return {"patched": False, "reason": "already_installed"}

    h3_director_mode.build_compact_h3_prompt = build_slim_h3_prompt
    h3_director_mode._generate_h3_native_directed = _generate_h3_native_directed
    archive.archive_h3_video = _archive_h3_video_with_prompt_trace
    if hasattr(app, "h3_generate_native_directed"):
        app.h3_generate_native_directed = _generate_h3_native_directed
    h3_director_mode._xiaoxia_slim_h3_prompt_installed = True

    return {
        "patched": True,
        "slim_prompt": True,
        "theme_sent_to_h3": False,
        "motion_note_sent_to_h3": False,
        "negative_rule_stack_removed": True,
        "app_side_sanitizing_retry": False,
        "provider_safety_unchanged": True,
        "submitted_prompt_trace": True,
        "expanded_prompt_trace": True,
    }
