# -*- coding: utf-8 -*-
"""Photo lineage SSOT extracted from the v1.11.17.2 stable monolith.

This module is intentionally pure: it reads/writes only the supplied context dicts.
Runtime-only recovery (for very old autonomy records) is injected by the migration runtime
so the first modularization checkpoint does not create circular imports.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional

_GENERIC_PHOTO_PREFIX_RE = re.compile(
    r"^\s*大俠(?:按下|使用|用)?\s*/photo\s*(?:留住|拍下)?這一刻[。.!！]?\s*",
    flags=re.I,
)
_GENERIC_PHOTO_EVENT_RE = re.compile(r"大俠.*?/photo.*?(?:生成|拍下|留住)", flags=re.I)

LINEAGE_PRESENTATION_FIELDS = (
    "original_autonomy_share_text", "autonomy_share_text", "share_text",
    "diary_original_text", "post_text", "photo_name", "activity_title",
    "autonomy_activity", "episode_id", "episode_angle", "episode_plan",
    "album_id", "album_type", "album_title", "album_date", "album_status",
    "shot_number", "shot_role", "shot_title", "photobook_user_instruction",
    "photobook_content_scene", "photobook_camera_scene", "render_title_hint",
    "why_this_photo", "love_candidate",
    "cosplay_story", "cosplay_topic_candidate", "cosplay_family", "cosplay_family_label",
    "cosplay_work_title", "cosplay_character_name", "cosplay_title_hint",
)


def _clean_text_compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def photo_display_module(context: Dict[str, Any] | None, type_override: str = "") -> str:
    """Return the current human-facing photo module, separate from lineage root."""
    ctx = context if isinstance(context, dict) else {}
    record_type = str(type_override or ctx.get("type") or ctx.get("db_type") or "").strip().lower()
    source_mode = str(ctx.get("source_mode") or "").strip().lower()
    source_module = str(ctx.get("source_module") or "").strip().lower()
    album_type = str(ctx.get("album_type") or "").strip().lower()
    if record_type == "diary" or source_mode == "diary":
        return "diary"
    if record_type == "cosplay" or source_mode == "cosplay":
        return "cosplay"
    if record_type == "photobook" or source_mode == "photobook" or album_type == "photobook":
        return "photobook"
    if source_mode == "love_intent" or source_module == "love_intent":
        return "love_intent"
    if record_type == "autonomy_photo" or source_module == "autonomy" or str(ctx.get("image_role") or "").strip().lower() == "autonomy_today_image":
        return "autonomy"
    if source_mode == "travel_photo" or source_module == "travel":
        return "travel"
    return "photo"


def clean_photo_lineage_text(value: Any, module: str = "photo") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if module != "photo":
        cleaned = _GENERIC_PHOTO_PREFIX_RE.sub("", text).strip()
        if cleaned:
            return cleaned
        if "/photo" in text.lower():
            return ""
    return text


def canonical_photo_original_text(
    context: Dict[str, Any] | None,
    type_override: str = "",
    autonomy_recover: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> str:
    """Single human-facing narrative source for Discord descendants and Cloud Villa DB."""
    ctx = context if isinstance(context, dict) else {}
    module = photo_display_module(ctx, type_override=type_override)
    post_text = ctx.get("post_text") if isinstance(ctx.get("post_text"), dict) else {}
    candidates = [
        ctx.get("lineage_original_text"),
        ctx.get("original_display_text"),
        ctx.get("diary_original_text"),
        ctx.get("original_autonomy_share_text"),
        ctx.get("autonomy_share_text"),
        ctx.get("share_text"),
        post_text.get("message_to_daxia"),
        ctx.get("message"),
    ]
    for raw in candidates:
        cleaned = clean_photo_lineage_text(raw, module=module)
        if cleaned:
            return cleaned
    if module == "autonomy" and autonomy_recover is not None:
        try:
            recovered = str(autonomy_recover(ctx) or "").strip()
            if recovered:
                return recovered
        except Exception:
            pass
    if module == "photobook":
        request = _clean_text_compact(ctx.get("photobook_user_instruction") or "")
        if request:
            return request
    return ""


def default_photo_event_for_module(context: Dict[str, Any] | None, type_override: str = "") -> str:
    ctx = context if isinstance(context, dict) else {}
    module = photo_display_module(ctx, type_override=type_override)
    existing = str(ctx.get("lineage_event") or ctx.get("original_event") or ctx.get("event") or "").strip()
    if existing and not (module != "photo" and _GENERIC_PHOTO_EVENT_RE.search(existing)):
        return existing
    if module == "diary":
        topic = _clean_text_compact(ctx.get("topic") or "")
        return topic or "小俠交換日記照片"
    if module == "autonomy":
        activity = ctx.get("autonomy_activity") if isinstance(ctx.get("autonomy_activity"), dict) else {}
        title = _clean_text_compact(activity.get("title") or ctx.get("activity_title") or ctx.get("scene_text") or "小俠自主生活")
        return f"小俠自主｜{title}"
    if module == "cosplay":
        title = _clean_text_compact(ctx.get("render_title") or ctx.get("title") or ctx.get("topic") or "今日 Cosplay")
        return f"小俠 Cosplay｜{title}"
    if module == "photobook":
        album = _clean_text_compact(ctx.get("album_title") or "小俠寫真")
        shot = ctx.get("shot_number")
        return f"小俠寫真｜{album}" + (f"｜第 {shot} 張" if shot else "")
    if module == "love_intent":
        return "小俠主動留下的愛意照片"
    if module == "travel":
        return "小俠旅途生活照片"
    return existing or "大俠使用 /photo 主動生成的小俠照片"


def inherit_photo_lineage(
    source_context: Dict[str, Any] | None,
    target_context: Dict[str, Any] | None,
    action: str = "",
    autonomy_recover: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> Dict[str, Any]:
    """Universal descendant inheritance. Image may change; original narrative may not."""
    source = source_context if isinstance(source_context, dict) else {}
    target = target_context if isinstance(target_context, dict) else {}
    if not source:
        return target

    current_module = photo_display_module(source, type_override=source.get("type") or source.get("db_type") or "")
    root_module = str(source.get("lineage_root_source_module") or source.get("source_module") or current_module).strip().lower() or current_module
    original_text = str(source.get("lineage_original_text") or "").strip() or canonical_photo_original_text(
        source, autonomy_recover=autonomy_recover
    )
    lineage_event = str(source.get("lineage_event") or "").strip() or default_photo_event_for_module(source)

    target["lineage_root_source_module"] = root_module
    target["lineage_root_type"] = str(source.get("lineage_root_type") or source.get("type") or source.get("db_type") or current_module).strip()
    target["lineage_root_topic"] = str(source.get("lineage_root_topic") or source.get("topic") or source.get("photo_name") or source.get("title") or "").strip()
    target["lineage_parent_image_url"] = str(source.get("local_url") or source.get("image_url") or "").strip()
    if action:
        target["lineage_action"] = str(action)
    if original_text:
        target["lineage_original_text"] = original_text
        target["original_display_text"] = original_text
        target["message"] = original_text
    if lineage_event:
        target["lineage_event"] = lineage_event
    if source.get("source_module"):
        target["source_module"] = source.get("source_module")

    for key in LINEAGE_PRESENTATION_FIELDS:
        value = source.get(key)
        if value not in (None, "", [], {}):
            target[key] = value
    return target
