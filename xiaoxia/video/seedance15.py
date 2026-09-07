# -*- coding: utf-8 -*-
"""Seedance 1.5 Pro image-to-video PK path for Xiaoxia photo result cards.

This intentionally does not reuse the H3 final prompt.  Both providers receive the
same source image and the same shared Director intent, but each gets a prompt shaped
for its own documented strengths.  Seedance 1.5 Pro's start frame already defines
identity/composition, so the prompt concentrates on motion, audio and camera rather
than redundantly redescribing Xiaoxia.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import aiofiles
import aiohttp
import discord

from xiaoxia.video import h3


_ACTIVE_JOBS = set()
_MODEL_ID_DEFAULT = "fal-ai/bytedance/seedance/v1.5/pro/image-to-video"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "關", "關閉"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except Exception:
        value = int(default)
    return max(minimum, min(maximum, value))


def _config(app: Any) -> Dict[str, Any]:
    # For a fair H3 PK, inherit H3 duration when possible. Seedance accepts 4-12 s.
    try:
        h3_duration = int(h3._config().get("duration") or 10)
    except Exception:
        h3_duration = 10
    duration = _env_int("SEEDANCE15_VIDEO_DURATION", min(h3_duration, 12), 4, 12)
    resolution = (os.environ.get("SEEDANCE15_VIDEO_RESOLUTION") or "720p").strip().lower()
    if resolution not in {"480p", "720p", "1080p"}:
        resolution = "720p"
    return {
        "enabled": _env_bool("SEEDANCE15_VIDEO_ENABLED", True),
        "model_id": (os.environ.get("SEEDANCE15_VIDEO_MODEL_ID") or _MODEL_ID_DEFAULT).strip(),
        "duration": duration,
        "resolution": resolution,
        "generate_audio": _env_bool("SEEDANCE15_VIDEO_GENERATE_AUDIO", True),
        "send_file_max_mb": _env_int("SEEDANCE15_VIDEO_SEND_FILE_MAX_MB", 24, 1, 200),
    }


def _clean(app: Any, value: Any) -> str:
    return h3._clean(app, value)


async def _director_plan(app: Any, context: Dict[str, Any]) -> Dict[str, str]:
    """Use the same upstream Director logic as H3, not H3's provider-specific prompt."""
    existing = context.get("video_compare_plan") or context.get("h3_director_plan")
    if isinstance(existing, dict) and existing.get("hero_action"):
        return dict(existing)

    builder = getattr(app, "h3_build_director_plan", None)
    if callable(builder):
        plan = await builder(context)
        if isinstance(plan, dict):
            context["video_compare_plan"] = dict(plan)
            return dict(plan)

    # Conservative fallback if the shared Director is unavailable.
    return {
        "video_theme": _clean(app, context.get("title") or context.get("scene_summary") or "小俠自然動起來")[:100],
        "motion_level": "natural",
        "hero_action": "She makes one natural movement that follows directly from her current pose.",
        "reaction": "She settles naturally and gives a brief genuine reaction toward the camera.",
        "camera": "mostly stable camera",
        "voiceover": "大俠，這一刻也想讓你看到會動的我。",
        "ambience": "natural ambience from the visible environment",
        "audio_mode": "voiceover",
    }


def build_seedance_prompt(app: Any, context: Dict[str, Any], plan: Dict[str, str]) -> str:
    """Translate shared intent into Seedance 1.5 Pro's preferred prompt grammar.

    Fal's Seedance guide recommends: primary action -> dialogue/key sound -> ambient
    audio -> visual style.  For I2V it specifically says the start frame already
    defines the scene, so prompts should focus on motion and sound.
    """
    action = _clean(app, plan.get("hero_action") or "She makes one natural movement.")
    reaction = _clean(app, plan.get("reaction") or "She settles naturally.")
    camera = _clean(app, plan.get("camera") or "mostly stable camera")
    ambience = _clean(app, plan.get("ambience") or "natural room ambience")
    line = _clean(app, plan.get("voiceover") or "")
    audio_mode = str(plan.get("audio_mode") or "voiceover").strip().lower()

    # Do not re-invent facial/body descriptors: the start frame is the authority.
    layers = [
        f"{action}, then {reaction}",
        "preserve the exact person, face, hairstyle, outfit, body proportions, lighting and environment from the start frame",
        "natural physically coherent motion, stable facial identity, no morphing, no new people, no outfit change",
        f"camera: {camera}",
    ]

    if audio_mode == "dialogue" and line:
        layers.append(f'Xiaoxia says in natural Traditional Chinese, warmly and softly: "{line}"')
    elif audio_mode == "ambience":
        layers.append("no dialogue, no narration, no lip-sync")
    elif line:
        layers.append(
            f'off-screen non-diegetic inner narration in natural Traditional Chinese by a young Taiwanese woman: "{line}"; '
            "the visible woman remains silent and does not lip-sync"
        )
    else:
        layers.append("no dialogue; the visible woman remains silent")

    layers.extend([
        f"environmental audio: {ambience}",
        "photorealistic lifestyle footage, subtle believable facial expression, coherent temporal motion, no subtitles, no captions, no logos, no watermarks",
    ])
    return ", ".join(x for x in layers if x)


def _camera_fixed(plan: Dict[str, str]) -> bool:
    camera = str(plan.get("camera") or "").lower()
    return any(token in camera for token in ("fixed", "locked", "tripod", "static"))


async def _download_video(app: Any, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not url:
        return None, None, None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=180) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"SEEDANCE15_VIDEO_DOWNLOAD_HTTP_{resp.status}")
                filename = f"xiaoxia_seedance15_{uuid.uuid4().hex[:8]}.mp4"
                path = os.path.join(app.OUTPUT_DIR, filename)
                async with aiofiles.open(path, "wb") as f:
                    await f.write(await resp.read())
        public = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        return path, filename, public
    except Exception as exc:
        print(f"⚠️ [SEEDANCE15_PERSIST_FAILED] {type(exc).__name__}: {exc}")
        return None, None, None


async def generate_seedance15_video(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _config(app)
    if not cfg["enabled"]:
        raise RuntimeError("SEEDANCE15_VIDEO_DISABLED")
    if not (os.environ.get("FAL_KEY") or getattr(app, "FAL_KEY", None)):
        raise RuntimeError("SEEDANCE15_FAL_KEY_MISSING")

    image_url = await h3._ensure_image_url(app, context)
    plan = await _director_plan(app, context)
    prompt = build_seedance_prompt(app, context, plan)
    fal_client = app._get_fal_client()
    arguments = {
        "prompt": prompt,
        "image_url": image_url,
        "aspect_ratio": "auto",
        "resolution": cfg["resolution"],
        "duration": cfg["duration"],
        "generate_audio": cfg["generate_audio"],
        "camera_fixed": _camera_fixed(plan),
        "seed": -1,
    }

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🎞️ [SEEDANCE15_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            cfg["model_id"],
            arguments=arguments,
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    result = await asyncio.to_thread(_subscribe)
    video = result.get("video") if isinstance(result, dict) else None
    video_url = video.get("url") if isinstance(video, dict) else None
    if not video_url:
        raise RuntimeError(f"SEEDANCE15_VIDEO_NO_URL: {result}")

    local_path, local_filename, local_url = await _download_video(app, video_url)
    return {
        "model_id": cfg["model_id"],
        "video_url": video_url,
        "local_path": local_path,
        "local_filename": local_filename,
        "local_url": local_url,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "generate_audio": cfg["generate_audio"],
        "seed": result.get("seed") if isinstance(result, dict) else None,
        "director_plan": plan,
        "video_theme": plan.get("video_theme"),
        "motion_level": plan.get("motion_level"),
        "audio_mode": plan.get("audio_mode") or "voiceover",
        "voice_script": plan.get("voiceover") or "",
        "prompt": prompt,
    }


async def _handle_button(app: Any, view: Any, interaction: discord.Interaction) -> None:
    cfg = _config(app)
    if not cfg["enabled"]:
        await interaction.response.send_message("🎞️ SD 1.5Pro 目前未啟用。", ephemeral=True)
        return

    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = message_id or id(view)
    if job_key in _ACTIVE_JOBS:
        await interaction.response.send_message("🎞️ 這張照片正在生成 SD 1.5Pro，先等這支完成喔。", ephemeral=True)
        return

    _ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    try:
        context = dict(getattr(view, "context", {}) or {})
        result = await generate_seedance15_video(app, context)
        # Preserve the plan on the live view so repeated PK runs can reuse the same intent.
        if isinstance(result.get("director_plan"), dict):
            view.context["video_compare_plan"] = dict(result["director_plan"])

        lines = [
            "🎞️ **Seedance 1.5 Pro 影片生成完成**",
            f"規格：{result['duration']} 秒｜{result['resolution']}",
        ]
        if result.get("video_theme"):
            lines.append(f"🎬 主題：{result['video_theme']}")
        if result.get("motion_level"):
            lines.append(f"🎭 動作：{result['motion_level']}")
        if result.get("voice_script") and result.get("audio_mode") != "ambience":
            lines.append(f"🎙️ 聲音：{result['voice_script']}")

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

        view.context["last_seedance15_video_url"] = result.get("local_url") or result.get("video_url")
        view.context["last_seedance15_model_id"] = result.get("model_id")
        view.context["last_seedance15_seed"] = result.get("seed")
    except Exception as exc:
        print(f"❌ [SEEDANCE15_VIDEO_ERROR] {type(exc).__name__}: {exc!r}")
        await interaction.followup.send(
            f"⚠️ SD 1.5Pro 生成失敗：`{type(exc).__name__}: {str(exc)[:1200]}`",
            ephemeral=True,
        )
    finally:
        _ACTIVE_JOBS.discard(job_key)


class Seedance15VideoButton(discord.ui.Button):
    def __init__(self, app: Any, view: Any):
        cfg = _config(app)
        super().__init__(
            label="🎞️ SD 1.5Pro",
            style=discord.ButtonStyle.primary,
            row=3,
            disabled=not bool(cfg["enabled"] and (os.environ.get("FAL_KEY") or getattr(app, "FAL_KEY", None))),
        )
        self._app = app
        self._owner_view = view

    async def callback(self, interaction: discord.Interaction):
        await _handle_button(self._app, self._owner_view, interaction)


def install_seedance15_video_button(app: Any) -> Dict[str, Any]:
    """Append Seedance beside the existing H3 button on every shared photo result view."""
    view_cls = getattr(app, "PhotoResultView", None)
    if view_cls is None:
        raise RuntimeError("PhotoResultView not found")
    if getattr(view_cls, "_xiaoxia_seedance15_installed", False):
        return {"module": "xiaoxia.video.seedance15", "patched": False, "reason": "already_installed"}

    original_init = view_cls.__init__

    def patched_init(self, context, *args, **kwargs):
        original_init(self, context, *args, **kwargs)
        if not any(
            isinstance(child, discord.ui.Button) and getattr(child, "label", "") == "🎞️ SD 1.5Pro"
            for child in self.children
        ):
            self.add_item(Seedance15VideoButton(app, self))

    view_cls.__init__ = patched_init
    view_cls._xiaoxia_seedance15_installed = True
    app.generate_seedance15_video_from_context = lambda context: generate_seedance15_video(app, context)

    cfg = _config(app)
    return {
        "module": "xiaoxia.video.seedance15",
        "patched": True,
        "model_id": cfg["model_id"],
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "generate_audio": cfg["generate_audio"],
        "prompt_strategy": "Seedance-native: action -> audio -> ambience -> visual style",
        "start_frame_is_visual_ssot": True,
    }
