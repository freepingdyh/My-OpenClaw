# -*- coding: utf-8 -*-
"""Safety hardening for Xiaoxia H3 dialogue/reference-audio flow.

Keeps Sulafat as the preferred voice while preventing the generated spoken line
from drifting into wording that fal's audio content checker may reject.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from xiaoxia.video import h3


_BLOCKED_TONE_PATTERNS = (
    r"魅惑",
    r"誘惑",
    r"性感",
    r"挑逗",
    r"撩人",
    r"勾引",
    r"只為你",
    r"只屬於你",
    r"為你閃耀",
    r"慾望",
    r"情慾",
    r"色誘",
)


def _sanitize_dialogue(text: str) -> str:
    value = " ".join(str(text or "").split()).strip().strip('"').strip("「」").strip()
    replacements = {
        "這份魅惑，現在只為你閃耀。": "今天這個造型，想第一個讓你看看。",
        "魅惑": "魅力",
        "誘惑": "驚喜",
        "性感": "亮眼",
        "挑逗": "俏皮",
        "撩人": "迷人",
        "勾引": "吸引",
        "只為你": "想給你看",
        "只屬於你": "想和你分享",
        "為你閃耀": "好好亮相",
        "慾望": "心情",
        "情慾": "氛圍",
        "色誘": "吸睛",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    if any(re.search(pattern, value, flags=re.I) for pattern in _BLOCKED_TONE_PATTERNS):
        value = "大俠，準備好了嗎？今天這個造型很有意思，我想第一個讓你看看。"
    return value[:120]


def install_h3_dialogue_safety(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_dialogue_safety_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original_build_script = h3._build_script

    async def safe_build_script(app_obj, context, cfg):
        script = await original_build_script(app_obj, context, cfg)
        safe_script = _sanitize_dialogue(script)
        if safe_script != script:
            print(f"🧼 [H3_DIALOGUE_SANITIZED] before={script!r} after={safe_script!r}")
        return safe_script

    h3._build_script = safe_build_script
    h3._xiaoxia_dialogue_safety_installed = True
    return {
        "patched": True,
        "strategy": "sanitize_reference_audio_dialogue_before_tts",
        "voice_preserved": "Sulafat",
    }
