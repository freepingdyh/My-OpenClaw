# -*- coding: utf-8 -*-
"""Keep Love Intent generation rules internal instead of leaking prompt text into Discord.

Display cleanup only.  Generation/root prompts are never mutated.
"""
from __future__ import annotations

import re
from typing import Any, Dict


_LOVE_MARKER = re.compile(r"LOVE\s+INTENT\s+(?:SOLO\s+RULES|POSE\s+RULES|OUTFIT\s+LOCK)\s*:", re.I)

# These are real user-facing section headers used by the Discord card.  The important
# detail is that they do not need to start on a fresh line: some legacy result builders
# concatenate the internal prompt block and the next display section into one string.
_DISPLAY_SECTION = re.compile(
    r"(?P<prefix>(?:\r?\n|\s))(?P<header>服裝\s*(?:/|／)\s*搭配)\b",
    re.I,
)


def _strip_internal_love_segment(value: str) -> str:
    """Remove the whole internal Love Intent segment while preserving later display text."""
    marker = _LOVE_MARKER.search(value)
    if not marker:
        return value

    start = marker.start()
    tail = value[marker.end():]
    next_section = _DISPLAY_SECTION.search(tail)

    if next_section:
        # Keep the actual user-facing section header and everything after it.
        suffix_start = marker.end() + next_section.start("header")
        text = value[:start].rstrip() + "\n\n" + value[suffix_start:].lstrip()
    else:
        # No trustworthy display boundary follows.  Internal prompt text must never be
        # shown, so keep only the human-facing text that preceded the first marker.
        text = value[:start].rstrip()

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str) or "LOVE INTENT" not in value.upper():
        return value

    text = value
    # A malformed legacy payload can contain more than one internal segment.  Remove
    # repeatedly until no Love Intent directive remains in the display copy.
    previous = None
    while previous != text and _LOVE_MARKER.search(text):
        previous = text
        text = _strip_internal_love_segment(text)

    return text.strip()


def _is_love(context: Dict[str, Any]) -> bool:
    joined = " ".join(
        str(context.get(k) or "").lower()
        for k in ("source_mode", "type", "db_type", "source_module", "album_type")
    )
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

    # Display-only sanitation.  Do not touch generation/root prompt fields.
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
        "strategy": "remove_internal_segment_before_display_render",
        "removed_markers": [
            "LOVE INTENT SOLO RULES",
            "LOVE INTENT POSE RULES",
            "LOVE INTENT OUTFIT LOCK",
        ],
    }
