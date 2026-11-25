# -*- coding: utf-8 -*-
"""v1.12.06ar — harden H3/Sulafat audio payload handling.

Fixes local TypeError risk when Google GenAI audio data is returned as a
bytes-like or base64 string rather than plain bytes. Also exposes the local
TypeError message in Discord diagnostics so future failures are actionable.
Does not alter provider content-policy behavior.
"""
from __future__ import annotations

import base64
import os
import uuid
import wave
from typing import Any, Dict

from google.genai import types

from xiaoxia.video import h3, voiceover_mode, diagnostics

VERSION = "1.12.06ar"


def _audio_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise TypeError("H3_TTS_AUDIO_EMPTY_STRING")
        try:
            return base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise TypeError("H3_TTS_AUDIO_STRING_NOT_BASE64") from exc
    try:
        return bytes(value)
    except Exception as exc:
        raise TypeError(f"H3_TTS_UNSUPPORTED_AUDIO_TYPE:{type(value).__name__}") from exc


async def _patched_sulafat_tts(app: Any, script: str, cfg: Dict[str, Any]) -> str:
    tts_prompt = (
        "請用自然的台灣國語朗讀以下旁白。聲音設定：24 歲台灣女生，年輕、活潑、明亮，"
        "帶一點磁性與溫柔感；有輕微笑意，但不要撒嬌、不要播音腔、不要舞台式表演。"
        "語速自然偏輕快，清楚但像真實生活中的內心旁白。不要自行增刪內容。\n"
        "【旁白】\n" + script
    )
    tts_cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg["tts_voice"])
            )
        ),
    )
    resp = await app.gemini_client.aio.models.generate_content(
        model=cfg["tts_model"], contents=[tts_prompt], config=tts_cfg
    )
    raw = resp.candidates[0].content.parts[0].inline_data.data
    pcm = _audio_bytes(raw)
    if not pcm:
        raise TypeError("H3_TTS_AUDIO_EMPTY_BYTES")
    wav_path = os.path.join("/tmp", f"xiaoxia_vo_{uuid.uuid4().hex[:8]}.wav")
    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    return wav_path


async def _patched_h3_tts(app: Any, script: str, cfg: Dict[str, Any]) -> str:
    prompt = (
        f"請以 {cfg['tts_language']} 的年輕台灣女生聲線朗讀下方【台詞】。"
        "聲線自然、親切、活潑但不浮誇，帶著輕微笑意，咬字清楚、語速自然；"
        "不要自行增加、刪減或重複內容。\n【台詞】\n" + script
    )
    tts_config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg["tts_voice"])
            )
        ),
    )
    response = await app.gemini_client.aio.models.generate_content(
        model=cfg["tts_model"], contents=[prompt], config=tts_config
    )
    raw = response.candidates[0].content.parts[0].inline_data.data
    pcm = _audio_bytes(raw)
    if not pcm:
        raise TypeError("H3_TTS_AUDIO_EMPTY_BYTES")
    path = os.path.join("/tmp", f"xiaoxia_h3_voice_{uuid.uuid4().hex[:8]}.wav")
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    return path


def install_h3_typeerror_fix(app: Any):
    voiceover_mode._tts_sulafat_voiceover = _patched_sulafat_tts
    h3._tts_wav = _patched_h3_tts

    original_format = diagnostics.format_h3_error

    def format_with_local_message(exc: Exception, cfg=None):
        text = original_format(exc, cfg)
        if isinstance(exc, TypeError):
            detail = " ".join(str(exc or "").split())[:220]
            if detail:
                lines = text.splitlines()
                lines.insert(2, f"`msg: {detail}`")
                return "\n".join(lines)
        return text

    diagnostics.format_h3_error = format_with_local_message
    app.h3_format_error = format_with_local_message
    return {
        "version": VERSION,
        "audio_bytes_normalized": True,
        "typeerror_message_exposed": True,
        "provider_policy_unchanged": True,
    }
