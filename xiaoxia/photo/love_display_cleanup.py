# -*- coding: utf-8 -*-
"""Keep Love Intent generation rules internal instead of leaking English prompt text into Discord."""
from __future__ import annotations

import re
from typing import Any, Dict


_RULE_BLOCK = re.compile(
    r"\s*LOVE INTENT SOLO RULES:.*?(?:Outfit summary:\s*|(?=\n(?:服裝|搭配|場景|構圖)\b)|$)",
    flags=re.I | re.S,
)
_LOCK_ONLY = re.compile(r"\s*LOVE INTENT OUTFIT LOCK:.*?(?=\n(?:服裝|搭配|場景|構圖)\b|$)", flags=re.I | re.S)


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str) or "LOVE INTENT" not in value.upper():
        return value
    text = _RULE_BLOCK.sub("\n", value)
    text = _LOCK_ONLY.sub("\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_love(context: Dict[str, Any]) -> bool:
    joined = " ".join(
        str(context.get(k) or "").lower()
        for k in ("source_mode", "type", "db_type", "source_module", "album_type")
    )
    return "love_intent" in joined or joined.strip() == "love"


def _display_copy(context: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(context or {})
    if not _is_love(out):
        return out
    # Only sanitize user-visible descriptive fields. Keep generation/root prompts untouched.
    for key in (
        "scene_summary", "scene_text", "authoritative_scene", "composition",
        "message", "share_text", "original_display_text", "description",
        "outfit_summary", "render_description",
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
        "removed_markers": ["LOVE INTENT SOLO RULES", "LOVE INTENT OUTFIT LOCK"],
    }
