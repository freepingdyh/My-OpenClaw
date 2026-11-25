# -*- coding: utf-8 -*-
"""Gemini model lifecycle refresh for Xiaoxia video capabilities.

Keeps model names out of downstream H3/director logic and provides ENV-based
escape hatches for future migrations without touching the large legacy core.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from xiaoxia.video import h3, voiceover_mode

_DEFAULT_REASONING_MODEL = "gemini-3.5-flash-lite"
_DEFAULT_VIDEO_VISION_MODEL = "gemini-3.5-flash-lite"
_DEFAULT_TTS_MODEL = "gemini-3.1-flash-tts-preview"

_ORIGINAL_H3_CONFIG = h3._config
_ORIGINAL_VOICE_CONFIG = voiceover_mode._config


def _pick(specific_env: str, shared_env: str, default: str) -> str:
    value = os.environ.get(specific_env)
    if value and value.strip():
        return value.strip()
    value = os.environ.get(shared_env)
    if value and value.strip():
        return value.strip()
    return default


def reasoning_model() -> str:
    return _pick("XIAOXIA_H3_SCRIPT_MODEL", "XIAOXIA_GEMINI_MODEL", _DEFAULT_REASONING_MODEL)


def video_vision_model() -> str:
    return _pick("XIAOXIA_VIDEO_VISION_MODEL", "XIAOXIA_GEMINI_MODEL", _DEFAULT_VIDEO_VISION_MODEL)


def tts_model() -> str:
    return _pick("XIAOXIA_H3_TTS_MODEL", "XIAOXIA_TTS_MODEL", _DEFAULT_TTS_MODEL)


def _refresh_config(base_fn):
    def wrapped() -> Dict[str, Any]:
        cfg = dict(base_fn())
        cfg["script_model"] = reasoning_model()
        cfg["tts_model"] = tts_model()
        return cfg
    return wrapped


def install_model_refresh(app: Any) -> Dict[str, Any]:
    if getattr(app, "_xiaoxia_gemini_refresh_installed", False):
        return {"patched": False, "reason": "already_installed"}

    # voiceover_mode captured the old h3._config at import time, so patch both
    # public config seams. H3 Director reads voiceover_mode._config dynamically.
    h3._config = _refresh_config(_ORIGINAL_H3_CONFIG)
    voiceover_mode._config = _refresh_config(_ORIGINAL_VOICE_CONFIG)

    app.xiaoxia_gemini_model = reasoning_model
    app.xiaoxia_video_vision_model = video_vision_model
    app.xiaoxia_tts_model = tts_model
    app._xiaoxia_gemini_refresh_installed = True
    return {
        "patched": True,
        "reasoning_model": reasoning_model(),
        "video_vision_model": video_vision_model(),
        "tts_model": tts_model(),
        "env": {
            "reasoning": "XIAOXIA_GEMINI_MODEL / XIAOXIA_H3_SCRIPT_MODEL",
            "video_vision": "XIAOXIA_VIDEO_VISION_MODEL",
            "tts": "XIAOXIA_TTS_MODEL / XIAOXIA_H3_TTS_MODEL",
        },
    }
