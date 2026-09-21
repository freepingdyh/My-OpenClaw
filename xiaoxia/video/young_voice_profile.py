# -*- coding: utf-8 -*-
"""v1.12.06ah — younger Xiaoxia post-mix voice profile.

H3 remains the primary/cheap visual generator (Max Turbo).  This layer changes only
the separate Gemini TTS voice used after H3 has already rendered successfully.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import voiceover_mode

_ORIGINAL_CONFIG = voiceover_mode._config


def _config_with_young_voice() -> Dict[str, Any]:
    cfg = dict(_ORIGINAL_CONFIG())
    # Official Gemini TTS voice list describes Leda as "Youthful".
    cfg["tts_voice"] = "Leda"
    # Use the current Gemini TTS generation model; this does not affect H3 selection/cost.
    cfg["tts_model"] = "gemini-3.1-flash-tts-preview"
    return cfg


def install_young_voice_profile(app: Any) -> Dict[str, Any]:
    if getattr(voiceover_mode, "_xiaoxia_young_voice_profile_installed", False):
        return {"patched": False, "reason": "already_installed"}

    voiceover_mode._config = _config_with_young_voice
    voiceover_mode._xiaoxia_young_voice_profile_installed = True
    return {
        "patched": True,
        "h3_model_unchanged": True,
        "h3_primary": "minimax/h3-max-turbo/image-to-video",
        "tts_voice": "Leda",
        "tts_voice_character": "Youthful",
        "tts_model": "gemini-3.1-flash-tts-preview",
        "voice_stage": "postmix only",
    }
