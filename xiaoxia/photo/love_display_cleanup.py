# -*- coding: utf-8 -*-
"""Keep Love Intent generation rules internal instead of leaking prompt text into Discord."""
from __future__ import annotations

import re
from typing import Any, Dict


# Internal Love Intent directives are useful for image generation, but must never be
# rendered in the Discord result card.  Stop at the next user-facing Chinese section.
_INTERNAL_LOVE_BLOCK = re.compile(
    r"\s*LOVE\s+INTENT\s+(?:SOLO\s+RULES|POSE\s+RULES|OUTFIT\s+LOCK)\s*:.*?"
    r"(?=(?:\n|\r\n?)(?:服裝\s*/?\s*搭配|服裝|搭配|場景|構圖)\b|$)",
    flags=re.I | re.S,
)
# Defensive fallback for concatenated directives such as the current SOLO RULES ->
# POSE RULES -> OUTFIT LOCK block.  Remove the whole internal segment in one pass.
_INTERNAL_LOVE_SEGMENT = re.compile(
    r"\s*LOVE\s+INTENT\s+SOLO\s+RULES\s*:.*?"
    r"(?=(?:\n|\r\n?)(?:服裝\s*/?\s*搭配|服裝|搭配|場景|構圖)\b|$)",
    flags=re.I | re.S,
)


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str) or "LOVE INTENT" not in value.upper():
        return value
    text = _INTERNAL_LOVE_SEGMENT.sub("\n", value)
    # Also clean isolated directives if their layout changes later.
    previous = None
    while previous != text:
        previous = text
        text = _INTERNAL_LOVE_BLOCK.sub("\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_love(context: Dict[str, Any]) -> bool:
    joined = " ".join(
        str(context.get(k) or "").lower()
        for k in ("source_mode", "type", "db_type", "source_module", "album_type")
    )
    # Some legacy Love Intent result contexts do not carry a reliable type marker,
    # so the presence of the internal marker itself is also sufficient for display cleanup.
    if "love_intent" in joined or joined.strip() == "love":
        return True
    return any(
        isinstance(v, str) and "LOVE INTENT" in v.upper()
        for v in context.values()
    )


def _display_copy(context: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(context or {})
    if not _is_love(out):
        return out
    # Display-only sanitation: generation/root prompts remain untouched.
    for key in (
        "scene_summary", "scene_text", "authoritative_scene", "composition",
        "message", "share_text", "original_display_text", "description",
        "outfit_summary", "render_description", "scene", "prompt_summary",
    ):
        if key in out:
            out[key] = _clean_text(out.get(key))
    return out


def install_love_display_cleanup(app: Any) -> Dict[str, Any]:
    if getattr(app, "_xiaoxia_love_display_cleanup_installed", False):
        return {"patched": False, "reason": "already_installed"}
    original = getattr(app, "_build_result_embed", None)
    if not callable(original):
        return {"patched": False, "reason": "_build_result_embed_not_found"}

    def wrapped(context, *args, **kwargs):
        return original(_display_copy(context), *args, **kwargs)

    app._build_result_embed = wrapped
    app._xiaoxia_love_display_cleanup_installed = True
    return {
        "patched": True,
        "scope": "love_intent_display_only",
        "generation_prompt_unchanged": True,
        "removed_markers": [
            "LOVE INTENT SOLO RULES",
            "LOVE INTENT POSE RULES",
            "LOVE INTENT OUTFIT LOCK",
        ],
    }
