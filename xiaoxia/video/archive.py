# -*- coding: utf-8 -*-
"""Selective H3 archive for Xiaoxia Cloud Villa.

Generated H3 clips are preview-only by default. A Discord save button promotes the
chosen clip into the permanent gallery and records source lineage for fast return to
the original photo/diary/calendar message.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiofiles
import aiohttp
import discord
from fastapi import FastAPI

from xiaoxia.photo import lineage
from xiaoxia.video import diagnostics, h3, voiceover_mode

_ARCHIVE_DIR = "/data/memory/h3_archive"
_ARCHIVE_FILE = os.path.join(_ARCHIVE_DIR, "videos.json")
_STORE_LOCK = asyncio.Lock()
_ORIGINAL_DOWNLOAD = None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first(ctx: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = ctx.get(key)
        if value not in (None, "", [], {}):
            return _clean(value)
    return ""


def _source_mode(context: Dict[str, Any]) -> str:
    ctx = context or {}
    raw_values = [
        str(ctx.get("source_mode") or "").lower(),
        str(ctx.get("type") or "").lower(),
        str(ctx.get("db_type") or "").lower(),
        str(ctx.get("source_module") or "").lower(),
        str(ctx.get("album_type") or "").lower(),
    ]
    joined = " ".join(raw_values)
    if "calendar" in joined or "月曆" in joined:
        return "calendar"
    if "cosplay" in joined:
        return "cosplay"
    if "diary" in joined:
        return "diary"
    if "autonomy" in joined:
        return "autonomy"
    if "travel" in joined:
        return "travel"
    if "photobook" in joined:
        return "photobook"
    if "love_intent" in joined or "love" in joined:
        return "love_intent"
    try:
        module = lineage.photo_display_module(ctx)
        if module:
            return module
    except Exception:
        pass
    return "photo"


def _source_original_text(context: Dict[str, Any]) -> str:
    try:
        text = lineage.canonical_photo_original_text(context)
        if text:
            return str(text).strip()
    except Exception:
        pass
    return _first(
        context,
        "lineage_original_text",
        "original_display_text",
        "diary_original_text",
        "original_autonomy_share_text",
        "autonomy_share_text",
        "share_text",
        "message",
    )


def _source_title(context: Dict[str, Any]) -> str:
    return _first(
        context,
        "title",
        "activity_title",
        "photo_name",
        "topic",
        "render_title",
        "cosplay_title_hint",
        "album_title",
    ) or "小俠的生活片刻"


def _source_reason(context: Dict[str, Any], original: str) -> str:
    why = _first(context, "why_this_photo", "event", "lineage_event", "action_summary")
    if why:
        return why
    return original[:240]


def _source_id(context: Dict[str, Any]) -> str:
    return _first(
        context,
        "id",
        "photo_id",
        "db_id",
        "diary_id",
        "calendar_event_id",
        "episode_id",
        "album_id",
    )


def _source_date(context: Dict[str, Any]) -> str:
    raw = _first(context, "publish_date", "date", "activity_date", "album_date", "scheduled_date")
    return raw[:10] if raw else ""


def _source_image_url(context: Dict[str, Any]) -> str:
    return _first(context, "local_url", "image_url")


def _find_fastapi_app(app_module: Any) -> Optional[FastAPI]:
    for name in ("web_app", "fastapi_app", "api", "server", "app"):
        value = getattr(app_module, name, None)
        if isinstance(value, FastAPI):
            return value
    try:
        for value in vars(app_module).values():
            if isinstance(value, FastAPI):
                return value
    except Exception:
        pass
    return None


def _load_records_sync() -> list[Dict[str, Any]]:
    try:
        with open(_ARCHIVE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_records_sync(records: list[Dict[str, Any]]) -> None:
    os.makedirs(_ARCHIVE_DIR, exist_ok=True)
    tmp = _ARCHIVE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, _ARCHIVE_FILE)


async def _download_preview_video(app: Any, url: str):
    if not url:
        return None, None, None
    try:
        filename = f"xiaoxia_h3_preview_{uuid.uuid4().hex[:10]}.mp4"
        path = os.path.join("/tmp", filename)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=180) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"H3_PREVIEW_DOWNLOAD_HTTP_{resp.status}")
                async with aiofiles.open(path, "wb") as fh:
                    await fh.write(await resp.read())
        return path, filename, None
    except Exception as exc:
        print(f"⚠️ [H3_PREVIEW_DOWNLOAD_FAILED] {type(exc).__name__}: {exc}")
        return None, None, None


async def _persist_video_file(app: Any, result: Dict[str, Any]) -> tuple[str, str]:
    os.makedirs(app.OUTPUT_DIR, exist_ok=True)
    filename = f"xiaoxia_h3_saved_{uuid.uuid4().hex[:10]}.mp4"
    target = os.path.join(app.OUTPUT_DIR, filename)
    preview_path = str(result.get("local_path") or "")
    if preview_path and os.path.exists(preview_path):
        await asyncio.to_thread(shutil.copy2, preview_path, target)
    else:
        url = str(result.get("video_url") or "")
        if not url:
            raise RuntimeError("H3_ARCHIVE_SOURCE_MISSING")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=180) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"H3_ARCHIVE_DOWNLOAD_HTTP_{resp.status}")
                async with aiofiles.open(target, "wb") as fh:
                    await fh.write(await resp.read())
    public = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
    return target, public


async def archive_h3_video(
    app: Any,
    *,
    context: Dict[str, Any],
    result: Dict[str, Any],
    source_jump_url: str = "",
    source_message_id: str = "",
) -> Dict[str, Any]:
    _, public_url = await _persist_video_file(app, result)
    original = _source_original_text(context)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "video_id": f"h3_{uuid.uuid4().hex[:12]}",
        "video_url": public_url,
        "source_mode": _source_mode(context),
        "source_id": _source_id(context),
        "source_title": _source_title(context),
        "source_date": _source_date(context),
        "source_image_url": _source_image_url(context),
        "source_reason": _source_reason(context, original),
        "source_original_text": original,
        "source_scene": _first(context, "authoritative_scene", "scene_summary", "scene_text", "composition"),
        "source_jump_url": str(source_jump_url or ""),
        "source_message_id": str(source_message_id or ""),
        "video_theme": str(result.get("video_theme") or context.get("h3_video_theme") or ""),
        "motion_level": str(result.get("motion_level") or context.get("h3_motion_level") or ""),
        "voiceover": str(result.get("voice_script") or ""),
        "director_plan": result.get("director_plan") if isinstance(result.get("director_plan"), dict) else {},
        "duration": result.get("duration"),
        "resolution": result.get("resolution"),
        "saved_at": now,
    }
    async with _STORE_LOCK:
        records = await asyncio.to_thread(_load_records_sync)
        records.insert(0, record)
        await asyncio.to_thread(_write_records_sync, records)
    return record


class H3ArchiveView(discord.ui.View):
    def __init__(self, app: Any, context: Dict[str, Any], result: Dict[str, Any], source_jump_url: str, source_message_id: str):
        super().__init__(timeout=3600)
        self.app = app
        self.context = dict(context or {})
        self.result = dict(result or {})
        self.source_jump_url = source_jump_url
        self.source_message_id = source_message_id
        self.saved = False

    @discord.ui.button(label="收藏到雲端別墅", emoji="💾", style=discord.ButtonStyle.secondary)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.saved:
            await interaction.response.send_message("這支影片已經收藏到小俠放映室了。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            record = await archive_h3_video(
                self.app,
                context=self.context,
                result=self.result,
                source_jump_url=self.source_jump_url,
                source_message_id=self.source_message_id,
            )
            self.saved = True
            button.disabled = True
            button.label = "已收藏"
            button.emoji = "✅"
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            preview = str(self.result.get("local_path") or "")
            if preview.startswith("/tmp/") and os.path.exists(preview):
                try:
                    os.remove(preview)
                except Exception:
                    pass
            await interaction.followup.send(
                f"✅ 已收藏到 **小俠放映室**｜{record.get('source_title')}\n分類：{record.get('source_mode')}",
                ephemeral=True,
            )
        except Exception as exc:
            print(f"❌ [H3_ARCHIVE_SAVE_FAILED] {type(exc).__name__}: {exc}")
            await interaction.followup.send("收藏失敗，影片仍保留在目前 Discord 訊息中。", ephemeral=True)

    async def on_timeout(self):
        if self.saved:
            return
        preview = str(self.result.get("local_path") or "")
        if preview.startswith("/tmp/") and os.path.exists(preview):
            try:
                os.remove(preview)
            except Exception:
                pass


async def _send_success_with_archive(view: Any, interaction: discord.Interaction, result: Dict[str, Any]) -> None:
    cfg = voiceover_mode._config()
    lines = ["🎬 **H3影片生成完成**", f"規格：{result.get('duration')} 秒｜{result.get('resolution')}"]
    if result.get("video_theme"):
        lines.append(f"🎞️ 主題：{result.get('video_theme')}")
    if result.get("motion_level"):
        lines.append(f"🎭 動作：{result.get('motion_level')}")
    if result.get("voice_script"):
        lines.append(f"🎙️ H3 原生旁白：{result.get('voice_script')}")
    if result.get("ambient_audio"):
        lines.append("🌿 H3 原生場景音")

    source_jump_url = ""
    source_message_id = ""
    try:
        if interaction.message:
            source_jump_url = interaction.message.jump_url
            source_message_id = str(interaction.message.id)
    except Exception:
        pass

    archive_view = H3ArchiveView(app=view.app if hasattr(view, "app") else None, context=view.context, result=result, source_jump_url=source_jump_url, source_message_id=source_message_id)
    if archive_view.app is None:
        archive_view.app = getattr(view, "_app", None)
    if archive_view.app is None:
        # PhotoResultView historically does not guarantee an app field; attach through module install closure.
        archive_view.app = getattr(_send_success_with_archive, "_app", None)

    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await interaction.followup.send("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)), view=archive_view)
    else:
        link = result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await interaction.followup.send("\n".join(lines), view=archive_view)
    view.context["last_h3_video_url"] = result.get("video_url")
    view.context["last_h3_video_model_id"] = result.get("model_id")
    view.context["last_h3_voice_script"] = result.get("voice_script") or ""


def _register_video_api(app_module: Any) -> Dict[str, Any]:
    web = _find_fastapi_app(app_module)
    if web is None:
        return {"registered": False, "reason": "fastapi_not_found"}
    if any(getattr(route, "path", None) == "/api/videos" for route in getattr(web, "routes", [])):
        return {"registered": False, "reason": "already_registered"}

    async def list_archived_videos():
        return await asyncio.to_thread(_load_records_sync)

    web.add_api_route("/api/videos", list_archived_videos, methods=["GET"], name="xiaoxia_h3_video_archive")
    return {"registered": True, "path": "/api/videos"}


def install_h3_archive(app: Any) -> Dict[str, Any]:
    global _ORIGINAL_DOWNLOAD
    if getattr(h3, "_xiaoxia_h3_archive_installed", False):
        return {"patched": False, "reason": "already_installed"}

    os.makedirs(_ARCHIVE_DIR, exist_ok=True)
    if _ORIGINAL_DOWNLOAD is None:
        _ORIGINAL_DOWNLOAD = h3._download_video
    h3._download_video = _download_preview_video
    _send_success_with_archive._app = app
    diagnostics._send_success_to_interaction = _send_success_with_archive
    api_info = _register_video_api(app)
    h3._xiaoxia_h3_archive_installed = True
    return {
        "patched": True,
        "preview_only_until_saved": True,
        "discord_save_button": True,
        "source_lineage": True,
        "api": api_info,
        "archive_file": _ARCHIVE_FILE,
    }
