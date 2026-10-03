# -*- coding: utf-8 -*-
"""v1.12.06x — private H3 archive storage, protected playback and delete API."""
from __future__ import annotations

import asyncio
import hmac
import os
import shutil
import uuid
from typing import Any, Dict
from urllib.parse import urlparse

import aiofiles
import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from xiaoxia.video import archive, archive_retry

_PRIVATE_DIR = "/data/memory/h3_archive/files"
_HEADER = "x-xiaoxia-vault-key"


def _vault_key() -> str:
    return str(os.environ.get("XIAOXIA_VAULT_PASSWORD") or "xiaoxia520")


def _authorized(request: Request) -> bool:
    supplied = str(request.headers.get(_HEADER) or "")
    return bool(supplied) and hmac.compare_digest(supplied, _vault_key())


def _record_filename(record: Dict[str, Any]) -> str:
    name = str(record.get("storage_filename") or "").strip()
    if name:
        return os.path.basename(name)
    raw = str(record.get("video_url") or "").strip()
    if raw.startswith("vault://"):
        return os.path.basename(raw[len("vault://"):])
    if raw:
        try:
            return os.path.basename(urlparse(raw).path)
        except Exception:
            return os.path.basename(raw)
    return ""


def _private_path(record: Dict[str, Any]) -> str:
    name = _record_filename(record)
    return os.path.join(_PRIVATE_DIR, name) if name else ""


def _migrate_existing(app: Any) -> Dict[str, int]:
    os.makedirs(_PRIVATE_DIR, exist_ok=True)
    records = archive._load_records_sync()
    moved = rewritten = 0
    changed = False
    for rec in records:
        filename = _record_filename(rec)
        if not filename:
            continue
        dst = os.path.join(_PRIVATE_DIR, filename)
        if not os.path.exists(dst):
            src = os.path.join(getattr(app, "OUTPUT_DIR", ""), filename)
            if src and os.path.exists(src):
                try:
                    shutil.move(src, dst)
                    moved += 1
                except Exception:
                    try:
                        shutil.copy2(src, dst)
                        os.remove(src)
                        moved += 1
                    except Exception:
                        pass
        if rec.get("storage_filename") != filename or rec.get("video_url"):
            rec["storage_filename"] = filename
            rec["video_url"] = ""
            rewritten += 1
            changed = True
    if changed:
        archive._write_records_sync(records)
    return {"moved": moved, "rewritten": rewritten}


async def _persist_private(app: Any, result: Dict[str, Any]) -> tuple[str, str]:
    os.makedirs(_PRIVATE_DIR, exist_ok=True)
    filename = f"xiaoxia_h3_saved_{uuid.uuid4().hex[:10]}.mp4"
    target = os.path.join(_PRIVATE_DIR, filename)
    preview = str(result.get("local_path") or "")
    if preview and os.path.exists(preview):
        await asyncio.to_thread(shutil.copy2, preview, target)
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
    return target, f"vault://{filename}"


async def _archive_private(app: Any, *, context: Dict[str, Any], result: Dict[str, Any], source_jump_url: str = "", source_message_id: str = "") -> Dict[str, Any]:
    # Reuse the existing metadata writer, but make its persistence seam private.
    rec = await _ORIGINAL_ARCHIVE(
        app,
        context=context,
        result=result,
        source_jump_url=source_jump_url,
        source_message_id=source_message_id,
    )
    filename = _record_filename(rec)
    rec["storage_filename"] = filename
    rec["video_url"] = ""
    async with archive._STORE_LOCK:
        rows = await asyncio.to_thread(archive._load_records_sync)
        for row in rows:
            if str(row.get("video_id")) == str(rec.get("video_id")):
                row["storage_filename"] = filename
                row["video_url"] = ""
                break
        await asyncio.to_thread(archive._write_records_sync, rows)
    return rec


async def _save_no_download(view: Any, interaction, button) -> None:
    if getattr(view, "saved", False):
        if not interaction.response.is_done():
            await interaction.response.send_message("這支影片已經收藏到小俠放映室了。", ephemeral=True)
        return
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    lock = getattr(view, "_xiaoxia_archive_retry_lock", None) or asyncio.Lock()
    view._xiaoxia_archive_retry_lock = lock
    async with lock:
        if getattr(view, "saved", False):
            return
        try:
            rec = await archive.archive_h3_video(
                view.app, context=view.context, result=view.result,
                source_jump_url=view.source_jump_url, source_message_id=view.source_message_id,
            )
            view.saved = True
            button.disabled = True
            button.label = "已收藏"
            button.emoji = "✅"
            try:
                await interaction.message.edit(view=view)
            except Exception:
                pass
            preview = str((view.result or {}).get("local_path") or "")
            if preview.startswith("/tmp/") and os.path.exists(preview):
                try: os.remove(preview)
                except Exception: pass
            await interaction.followup.send(
                f"✅ 已收藏到 **小俠放映室**｜{rec.get('source_title')}\n分類：{rec.get('source_mode')}",
                ephemeral=True,
            )
        except Exception as exc:
            print(f"❌ [H3_ARCHIVE_PRIVATE_SAVE_FAILED] {type(exc).__name__}: {exc!r}")
            await interaction.followup.send("收藏失敗，但不會重跑 H3。", ephemeral=True)


async def _rescue_no_download(ctx, app: Any) -> None:
    replied = await archive_retry._resolve_replied_message(ctx)
    if replied is None:
        await ctx.reply("請回覆那則已生成完成的 H3 影片訊息，再輸入 `/H3收藏`。", mention_author=False)
        return
    attachment = archive_retry._video_attachment(replied)
    if attachment is None:
        await ctx.reply("你回覆的訊息裡找不到影片附件。", mention_author=False)
        return
    result = {"video_url": str(getattr(attachment, "url", "") or ""), "local_path": "", "video_theme": "H3 既有影片補收藏", "motion_level": "", "voice_script": "", "director_plan": {}, "duration": None, "resolution": None}
    context = {"source_mode": "h3_rescue", "title": "H3 既有影片補收藏", "message": str(getattr(replied, "content", "") or "")[:1000]}
    ack = await ctx.reply("💾 收到，直接收藏這支既有 H3 影片；**不會重新生成**。", mention_author=False)
    try:
        await archive.archive_h3_video(app, context=context, result=result, source_jump_url=str(getattr(replied, "jump_url", "") or ""), source_message_id=str(getattr(replied, "id", "") or ""))
        await ack.edit(content="✅ 已補收藏到 **小俠放映室**，沒有重跑 H3。")
    except Exception as exc:
        print(f"❌ [H3_ARCHIVE_PRIVATE_RESCUE_FAILED] {type(exc).__name__}: {exc!r}")
        await ack.edit(content="⚠️ 補收藏失敗；沒有重跑 H3。")


_ORIGINAL_ARCHIVE = archive.archive_h3_video


def install_archive_privacy(app: Any) -> Dict[str, Any]:
    if getattr(archive, "_xiaoxia_archive_privacy_installed", False):
        return {"patched": False, "reason": "already_installed"}

    web = archive._find_fastapi_app(app)
    if web is None:
        raise RuntimeError("FastAPI app not found")

    migration = _migrate_existing(app)
    archive._persist_video_file = _persist_private
    archive.archive_h3_video = _archive_private
    archive_retry._add_download_button = lambda *args, **kwargs: None
    archive_retry._save_existing_view = _save_no_download
    archive_retry._rescue_from_discord_message = _rescue_no_download

    @web.middleware("http")
    async def protect_video_archive(request: Request, call_next):
        if request.url.path == "/api/videos" or request.url.path.startswith("/api/videos/"):
            if not _authorized(request):
                return JSONResponse({"detail": "vault authentication required"}, status_code=401)
        return await call_next(request)

    async def stream_video(video_id: str):
        rows = await asyncio.to_thread(archive._load_records_sync)
        rec = next((r for r in rows if str(r.get("video_id")) == str(video_id)), None)
        if not rec:
            raise HTTPException(status_code=404, detail="video not found")
        path = _private_path(rec)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="video file missing")
        return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))

    async def delete_video(video_id: str):
        async with archive._STORE_LOCK:
            rows = await asyncio.to_thread(archive._load_records_sync)
            rec = next((r for r in rows if str(r.get("video_id")) == str(video_id)), None)
            if not rec:
                raise HTTPException(status_code=404, detail="video not found")
            path = _private_path(rec)
            new_rows = [r for r in rows if str(r.get("video_id")) != str(video_id)]
            await asyncio.to_thread(archive._write_records_sync, new_rows)
        if path and os.path.exists(path):
            try:
                await asyncio.to_thread(os.remove, path)
            except Exception as exc:
                print(f"⚠️ [H3_ARCHIVE_DELETE_FILE_WARN] {type(exc).__name__}: {exc}")
        return {"deleted": True, "video_id": video_id}

    if not any(getattr(r, "path", None) == "/api/videos/{video_id}/stream" for r in web.routes):
        web.add_api_route("/api/videos/{video_id}/stream", stream_video, methods=["GET"], name="xiaoxia_private_video_stream")
    if not any(getattr(r, "path", None) == "/api/videos/{video_id}" for r in web.routes):
        web.add_api_route("/api/videos/{video_id}", delete_video, methods=["DELETE"], name="xiaoxia_delete_video")

    archive._xiaoxia_archive_privacy_installed = True
    return {"patched": True, "private_dir": _PRIVATE_DIR, "protected_api": True, "delete_api": True, "discord_download_link_removed": True, "migration": migration}
