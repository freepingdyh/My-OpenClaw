# -*- coding: utf-8 -*-
"""Pure photo presentation planning helpers.

Discord objects stay in the stable monolith for v1.12.01. This module only decides the
human-facing title/description/fields so presentation rules can evolve without owning UI I/O.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Callable

_INTERNAL_CONTRACT_MARKER = "REFERENCE ROLE CONTRACT"


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _public_text(value: Any) -> str:
    """Hide generation-only engineering contracts from Discord presentation."""
    text = str(value or "")
    if _INTERNAL_CONTRACT_MARKER in text:
        text = text.split(_INTERNAL_CONTRACT_MARKER, 1)[0]
    return text.strip()


def compact_scene_title(context: Dict[str, Any] | None, fallback: str = "快門瞬間") -> str:
    ctx = context if isinstance(context, dict) else {}
    base = _compact(
        ctx.get("pose_public_scene")
        or _public_text(ctx.get("title"))
        or _public_text(ctx.get("scene_summary"))
        or _public_text(ctx.get("scene_text"))
        or _public_text(ctx.get("composition"))
        or fallback
    )
    return base[:48] if base else fallback


def build_photo_presentation(
    context: Dict[str, Any] | None,
    *,
    title_prefix: str,
    canonical_text: Callable[[Dict[str, Any]], str],
    autonomy_text: Callable[[Dict[str, Any]], str],
    is_autonomy: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    """Return title, description, fields and footer source without creating Discord objects."""
    ctx = context if isinstance(context, dict) else {}
    photo_type = str(ctx.get("db_type") or ctx.get("type") or ctx.get("source_mode") or "").lower()
    is_photobook = photo_type == "photobook" or str(ctx.get("album_type") or "").lower() == "photobook"

    if is_photobook:
        album_title = _compact(ctx.get("album_title") or "小俠寫真")
        shot_number = int(ctx.get("shot_number") or 1)
        shot_title = _compact(ctx.get("shot_title") or ctx.get("title") or f"第 {shot_number} 張")
        raw_title = f"📸 小俠寫真｜{shot_title}"
        content_scene = _compact(ctx.get("photobook_content_scene") or "")
        camera_scene = _compact(ctx.get("photobook_camera_scene") or "")
        if content_scene or camera_scene:
            blocks = []
            if content_scene:
                blocks.append(f"**畫面內容**\n{content_scene}")
            if camera_scene:
                blocks.append(f"**鏡頭設計**\n{camera_scene}")
            description = "\n\n".join(blocks)
        else:
            user_instruction = _compact(ctx.get("photobook_user_instruction") or "")
            description = user_instruction or f"「{album_title}」第 {shot_number} 張。"
    else:
        raw_title = f"{title_prefix}｜{compact_scene_title(ctx)}"
        description = _public_text(canonical_text(ctx) or "")
        if not description:
            if is_autonomy(ctx):
                description = _public_text(autonomy_text(ctx) or ctx.get("action_summary") or "小俠今天的自主生活片刻。")
            else:
                description = _public_text(ctx.get("message") or ctx.get("action_summary") or "小俠留下的這一刻。")

    fields = []
    is_diary = str(ctx.get("source_mode") or ctx.get("type") or "").lower() == "diary"
    public_scene = _public_text(
        ctx.get("pose_public_scene")
        or ctx.get("authoritative_scene")
        or ctx.get("composition")
        or ctx.get("scene_summary")
        or ""
    )
    if (not is_photobook) and is_diary and public_scene:
        fields.append(("📸 寫真構想", public_scene[:1024]))
    elif (not is_photobook) and is_autonomy(ctx) and public_scene:
        fields.append(("場景", public_scene[:1024]))
    elif (not is_photobook) and public_scene:
        fields.append(("場景", public_scene[:900]))

    if ctx.get("outfit_summary"):
        wardrobe_id = str(ctx.get("wardrobe_id") or "").strip().upper()
        wardrobe_name = str(ctx.get("wardrobe_name") or "").strip()
        wardrobe_prefix = ""
        if wardrobe_id:
            wardrobe_prefix = f"【{wardrobe_id}{('｜' + wardrobe_name) if wardrobe_name else ''}】\n"
        fields.append(("服裝／搭配", (wardrobe_prefix + str(ctx.get("outfit_summary")))[:900]))

    # Exact short camera description Gemini handed to Seedream.
    camera_intent = _compact(ctx.get("pose_camera_intent") or "")
    if camera_intent:
        fields.append(("📷 Gemini 鏡位判讀", camera_intent[:900]))

    return {
        "title": str(raw_title)[:256],
        "description": str(description)[:4096],
        "fields": fields,
        "footer_source": "photobook" if is_photobook else ctx.get("source_mode", "photo_scene"),
        "is_photobook": is_photobook,
    }
