# -*- coding: utf-8 -*-
"""Shared MiniMax H3 video button for Xiaoxia image result cards.

Design goals:
- attach one shared button to PhotoResultView so photo/cosplay/calendar/diary/autonomy/etc.
  inherit the same capability without duplicating handlers;
- default to 15-second output, fully ENV-adjustable;
- optionally create a short Xiaoxia line with Gemini and synthesize it with Sulafat;
- use H3 reference-to-video when a reference-audio voice is requested;
- fall back to H3 Max Turbo image-to-video when voice is disabled or unavailable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import wave
from typing import Any, Dict, Optional, Tuple

import aiofiles
import aiohttp
import discord
from google.genai import types


_ACTIVE_JOBS = set()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "關", "關閉"}


def _env_int(name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _clean(app, value: Any) -> str:
    fn = getattr(app, "_clean_text_compact", None)
    if callable(fn):
        try:
            return str(fn(value or "") or "").strip()
        except Exception:
            pass
    return " ".join(str(value or "").split()).strip()


def _config() -> Dict[str, Any]:
    resolution = (os.environ.get("H3_VIDEO_RESOLUTION") or "768P").strip().upper()
    if resolution not in {"480P", "768P"}:
        resolution = "768P"
    expansion = (os.environ.get("H3_VIDEO_PROMPT_EXPANSION_MODE") or "balanced").strip().lower()
    if expansion not in {"balanced", "quality"}:
        expansion = "balanced"
    voice_mode = (os.environ.get("XIAOXIA_H3_VOICE_MODE") or "reference_audio").strip().lower()
    if voice_mode not in {"reference_audio", "native_turbo", "off"}:
        voice_mode = "reference_audio"
    return {
        "enabled": _env_bool("H3_VIDEO_ENABLED", True),
        "duration": _env_int("H3_VIDEO_DURATION", 15, 5, 15),
        "resolution": resolution,
        "safety": _env_bool("H3_VIDEO_ENABLE_SAFETY_CHECKER", True),
        "expansion": expansion,
        "image_model": (os.environ.get("H3_VIDEO_IMAGE_MODEL_ID") or "minimax/h3-max-turbo/image-to-video").strip(),
        "reference_model": (os.environ.get("H3_VIDEO_REFERENCE_MODEL_ID") or "minimax/h3-max/reference-to-video").strip(),
        "send_file_max_mb": _env_int("H3_VIDEO_SEND_FILE_MAX_MB", 24, 1, 200),
        "voice_enabled": _env_bool("XIAOXIA_H3_VOICE_ENABLED", True),
        "voice_mode": voice_mode,
        "tts_model": (os.environ.get("XIAOXIA_H3_TTS_MODEL") or "gemini-2.5-flash-preview-tts").strip(),
        "tts_voice": (os.environ.get("XIAOXIA_H3_TTS_VOICE") or "Sulafat").strip() or "Sulafat",
        "tts_language": (os.environ.get("XIAOXIA_H3_TTS_LANGUAGE") or "zh-TW").strip() or "zh-TW",
        "script_model": (os.environ.get("XIAOXIA_H3_SCRIPT_MODEL") or "gemini-2.5-flash").strip() or "gemini-2.5-flash",
    }


def _image_candidates(context: Dict[str, Any]) -> list[str]:
    values = []
    for key in ("local_url", "image_url", "local_path"):
        value = str((context or {}).get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _scene_text(app, context: Dict[str, Any]) -> str:
    ctx = context or {}
    return _clean(
        app,
        ctx.get("authoritative_scene")
        or ctx.get("scene_summary")
        or ctx.get("scene_text")
        or ctx.get("composition")
        or ctx.get("message")
        or ctx.get("title")
        or "小俠自然地在原畫面中動起來",
    )


def _mode(context: Dict[str, Any]) -> str:
    raw = str((context or {}).get("source_mode") or (context or {}).get("type") or "photo").strip().lower()
    aliases = {
        "photo_scene": "photo",
        "photo_reference": "photo",
        "love_intent": "love",
        "xiaoxia_autonomy": "autonomy",
    }
    return aliases.get(raw, raw or "photo")


async def _ensure_image_url(app, context: Dict[str, Any]) -> str:
    for value in _image_candidates(context):
        if value.startswith("http://") or value.startswith("https://"):
            return value
    local = next((x for x in _image_candidates(context) if os.path.exists(x)), None)
    if not local:
        raise RuntimeError("H3_SOURCE_IMAGE_NOT_FOUND")
    fal_client = app._get_fal_client()
    return await asyncio.to_thread(fal_client.upload_file, local)


async def _build_script(app, context: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    scene = _scene_text(app, context)
    title = _clean(app, context.get("title") or context.get("activity_title") or "")
    composition = _clean(app, context.get("composition") or "")
    message = _clean(app, context.get("message") or "")
    prompt = f"""妳是小俠短影片的台詞編劇。請只輸出可直接朗讀的繁體中文台詞，不要標題、括號、動作說明或 emoji。
台詞要適合 15 秒內自然說完，約 18～45 個中文字，1～3 句。
語氣像 24 歲台灣女生：年輕、自然、活潑、微甜，但不要裝可愛、不要播音腔。
可以自然稱呼大俠。內容必須和目前畫面一致，不可跳到別的場景。

模式：{_mode(context)}
標題：{title}
場景：{scene}
畫面補充：{composition}
補充訊息：{message}
"""
    try:
        resp = await app.gemini_client.aio.models.generate_content(model=cfg["script_model"], contents=prompt)
        script = _clean(app, getattr(resp, "text", "") or "")
        script = script.strip('"').strip("「」").strip()
        if script:
            return script[:120]
    except Exception as exc:
        print(f"⚠️ [H3_SCRIPT_FAILED] {type(exc).__name__}: {exc}")
    fallback = title or scene or "大俠，我在這裡，今天這一刻也想讓你看看我。"
    fallback = _clean(app, fallback)
    if len(fallback) < 12:
        fallback = "大俠，我在這裡，今天這一刻也想讓你看看我。"
    return fallback[:120]


async def _tts_wav(app, script: str, cfg: Dict[str, Any]) -> str:
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
    pcm = response.candidates[0].content.parts[0].inline_data.data
    path = os.path.join("/tmp", f"xiaoxia_h3_voice_{uuid.uuid4().hex[:8]}.wav")
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    return path


def _prompt(app, context: Dict[str, Any], script: str = "", reference_audio: bool = False, native_dialogue: bool = False) -> str:
    scene = _scene_text(app, context)
    mode = _mode(context)
    parts = [
        "Image 1 is Xiaoxia and the visual source for this clip.",
        "Preserve Xiaoxia's recognizable face, body proportions, hairstyle, outfit, pose logic, and the original environment.",
        "Keep the shot photorealistic and coherent with the still image.",
        "Use subtle natural motion: breathing, blinking, small eye shifts, slight head motion, gentle hair and fabric movement, and a light posture adjustment that fits the original pose.",
        "Do not add extra people. Do not change the outfit. Do not relocate the scene. Do not add subtitles, captions, UI text, logos, or watermarks.",
    ]
    if mode == "cosplay":
        parts.append("Preserve the cosplay role readability while clearly keeping Xiaoxia as the same woman.")
    elif mode == "diary":
        parts.append("Preserve the intimate diary-like lifestyle mood and the same place/room feeling.")
    elif mode in {"calendar", "autonomy"}:
        parts.append("Preserve the lived daily-activity feeling so the scheduled activity remains visually recognizable.")

    if reference_audio and script:
        parts.extend([
            "Audio 1 is Xiaoxia's exact spoken performance and voice reference.",
            "Make Xiaoxia speak Audio 1 with natural lip sync and keep that young Taiwanese female voice identity.",
            f"Spoken line: {script}",
            "Use only very light scene-appropriate ambience underneath the dialogue. No music unless the scene clearly needs it.",
        ])
    elif native_dialogue and script:
        parts.extend([
            f'Xiaoxia speaks in Traditional Chinese with natural lip sync: "{script}"',
            "Use a young Taiwanese female voice: natural, lively, warm, clear, not a broadcast voice.",
            "Keep light scene-appropriate ambience. No subtitles.",
        ])
    else:
        parts.append("No dialogue. Use only subtle scene-appropriate ambience.")
    parts.append(f"Scene anchor: {scene}")
    return " ".join(parts)


async def _download_video(app, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not url:
        return None, None, None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=180) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"H3_VIDEO_DOWNLOAD_HTTP_{resp.status}")
                filename = f"xiaoxia_h3_{uuid.uuid4().hex[:8]}.mp4"
                path = os.path.join(app.OUTPUT_DIR, filename)
                async with aiofiles.open(path, "wb") as f:
                    await f.write(await resp.read())
        public = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        return path, filename, public
    except Exception as exc:
        print(f"⚠️ [H3_VIDEO_PERSIST_FAILED] {type(exc).__name__}: {exc}")
        return None, None, None


async def generate_h3_video(app, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _config()
    if not cfg["enabled"]:
        raise RuntimeError("H3_VIDEO_DISABLED")
    if not (os.environ.get("FAL_KEY") or getattr(app, "FAL_KEY", None)):
        raise RuntimeError("H3_FAL_KEY_MISSING")

    fal_client = app._get_fal_client()
    image_url = await _ensure_image_url(app, context)
    script = ""
    audio_path = None
    audio_url = None
    used_voice = False
    voice_mode = cfg["voice_mode"] if cfg["voice_enabled"] else "off"

    try:
        if voice_mode != "off" and os.environ.get("GEMINI_API_KEY"):
            script = await _build_script(app, context, cfg)

        if voice_mode == "reference_audio" and script:
            audio_path = await _tts_wav(app, script, cfg)
            audio_url = await asyncio.to_thread(fal_client.upload_file, audio_path)
            model_id = cfg["reference_model"]
            arguments = {
                "prompt": _prompt(app, context, script=script, reference_audio=True),
                "duration": cfg["duration"],
                "resolution": cfg["resolution"],
                "enable_safety_checker": cfg["safety"],
                "prompt_expansion_mode": cfg["expansion"],
                "aspect_ratio": "adaptive",
                "reference_image_urls": [image_url],
                "reference_audio_urls": [audio_url],
            }
            used_voice = True
        else:
            # Turbo image-to-video is the cheap/default visual path. If native_turbo is selected,
            # the exact same script is requested from H3's native audio system.
            model_id = cfg["image_model"]
            native_dialogue = voice_mode == "native_turbo" and bool(script)
            arguments = {
                "prompt": _prompt(app, context, script=script, native_dialogue=native_dialogue),
                "duration": cfg["duration"],
                "resolution": cfg["resolution"],
                "enable_safety_checker": cfg["safety"],
                "prompt_expansion_mode": cfg["expansion"],
                "image_url": image_url,
            }
            used_voice = native_dialogue

        def _subscribe():
            def on_queue_update(update):
                try:
                    if isinstance(update, fal_client.InProgress):
                        for log in update.logs:
                            print(f"🎬 [H3_QUEUE] {log.get('message', '')}")
                except Exception:
                    pass
            return fal_client.subscribe(
                model_id,
                arguments=arguments,
                with_logs=True,
                on_queue_update=on_queue_update,
            )

        result = await asyncio.to_thread(_subscribe)
        video = result.get("video") if isinstance(result, dict) else None
        video_url = video.get("url") if isinstance(video, dict) else None
        if not video_url:
            raise RuntimeError(f"H3_VIDEO_NO_URL: {result}")
        local_path, local_filename, local_url = await _download_video(app, video_url)
        return {
            "model_id": model_id,
            "video_url": video_url,
            "local_path": local_path,
            "local_filename": local_filename,
            "local_url": local_url,
            "voice_script": script,
            "used_voice": used_voice,
            "voice_mode": voice_mode,
            "duration": cfg["duration"],
            "resolution": cfg["resolution"],
            "reference_audio_url": audio_url,
        }
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


async def _handle_button(app, view, interaction: discord.Interaction) -> None:
    cfg = _config()
    if not cfg["enabled"]:
        await interaction.response.send_message("🎬 H3影片生成功能目前未啟用。", ephemeral=True)
        return

    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = message_id or id(view)
    if job_key in _ACTIVE_JOBS:
        await interaction.response.send_message("🎬 這張照片正在生成 H3 影片，先等這一支完成喔。", ephemeral=True)
        return

    _ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    try:
        context = dict(getattr(view, "context", {}) or {})
        result = await generate_h3_video(app, context)
        lines = [
            "🎬 **H3影片生成完成**",
            f"規格：{result['duration']} 秒｜{result['resolution']}",
        ]
        if result.get("used_voice") and result.get("voice_script"):
            label = "Sulafat 聲音參考" if result.get("voice_mode") == "reference_audio" else "H3 原生語音"
            lines.append(f"🗣️ {label}：{result['voice_script']}")

        local_path = str(result.get("local_path") or "")
        max_bytes = cfg["send_file_max_mb"] * 1024 * 1024
        if local_path and os.path.exists(local_path) and os.path.getsize(local_path) <= max_bytes:
            await interaction.followup.send(
                "\n".join(lines),
                file=discord.File(local_path, filename=os.path.basename(local_path)),
            )
        else:
            link = result.get("local_url") or result.get("video_url")
            if link:
                lines.append(f"📎 {link}")
            await interaction.followup.send("\n".join(lines))

        view.context["last_h3_video_url"] = result.get("local_url") or result.get("video_url")
        view.context["last_h3_video_model_id"] = result.get("model_id")
        view.context["last_h3_voice_script"] = result.get("voice_script") or ""
    except Exception as exc:
        print(f"❌ [H3_VIDEO_ERROR] {type(exc).__name__}: {exc}")
        await interaction.followup.send(
            f"⚠️ H3影片生成失敗：`{type(exc).__name__}: {str(exc)[:1200]}`",
            ephemeral=True,
        )
    finally:
        _ACTIVE_JOBS.discard(job_key)


class H3VideoButton(discord.ui.Button):
    def __init__(self, app, view):
        cfg = _config()
        super().__init__(
            label="🎬 H3影片生成",
            style=discord.ButtonStyle.success,
            row=3,
            disabled=not bool(cfg["enabled"] and (os.environ.get("FAL_KEY") or getattr(app, "FAL_KEY", None))),
        )
        self._app = app
        self._owner_view = view

    async def callback(self, interaction: discord.Interaction):
        await _handle_button(self._app, self._owner_view, interaction)


def install_h3_video_button(app) -> Dict[str, Any]:
    """Patch the existing shared PhotoResultView in-place.

    Because calendar, diary, cosplay, photo, autonomy and other image flows already instantiate
    PhotoResultView, this keeps the H3 feature centralized instead of duplicating per-module code.
    """
    view_cls = getattr(app, "PhotoResultView", None)
    if view_cls is None:
        raise RuntimeError("PhotoResultView not found")
    if getattr(view_cls, "_xiaoxia_h3_installed", False):
        return {"module": "xiaoxia.video.h3", "patched": False, "reason": "already_installed"}

    original_init = view_cls.__init__

    def patched_init(self, context, *args, **kwargs):
        original_init(self, context, *args, **kwargs)
        if not any(isinstance(child, discord.ui.Button) and getattr(child, "label", "") == "🎬 H3影片生成" for child in self.children):
            self.add_item(H3VideoButton(app, self))

    view_cls.__init__ = patched_init
    view_cls._xiaoxia_h3_installed = True
    app.generate_h3_video_from_context = lambda context: generate_h3_video(app, context)

    cfg = _config()
    return {
        "module": "xiaoxia.video.h3",
        "patched": True,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "voice_enabled": cfg["voice_enabled"],
        "voice_mode": cfg["voice_mode"],
        "tts_voice": cfg["tts_voice"],
        "image_model": cfg["image_model"],
        "reference_model": cfg["reference_model"],
    }
