# -*- coding: utf-8 -*-
"""v1.12.06y — delete archived H3 videos from Discord.

Usage:
- reply to an archived H3 video message and type /H3刪除
- or type /H3刪除 <video_id>
- /H3刪除 without a resolvable target shows recent archive IDs

Deletion removes both the private MP4 and its videos.json record. It never calls H3.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import discord

from xiaoxia.video import archive, archive_privacy, archive_retry


def _find_record_by_id(video_id: str) -> Optional[Dict[str, Any]]:
    target = str(video_id or "").strip()
    if not target:
        return None
    for rec in archive._load_records_sync():
        if str(rec.get("video_id") or "") == target:
            return rec
    return None


def _find_record_by_message_id(message_id: str) -> Optional[Dict[str, Any]]:
    target = str(message_id or "").strip()
    if not target:
        return None
    rows = archive._load_records_sync()
    # archive_message_id is the H3 result message itself for new saves.
    for rec in rows:
        if str(rec.get("archive_message_id") or "") == target:
            return rec
    # Rescue saves historically stored the replied H3 message as source_message_id.
    for rec in rows:
        if str(rec.get("source_message_id") or "") == target and str(rec.get("source_mode") or "") == "h3_rescue":
            return rec
    return None


async def _delete_record(record: Dict[str, Any]) -> Dict[str, Any]:
    video_id = str(record.get("video_id") or "").strip()
    if not video_id:
        raise RuntimeError("VIDEO_ID_MISSING")
    async with archive._STORE_LOCK:
        rows = await asyncio.to_thread(archive._load_records_sync)
        current = next((r for r in rows if str(r.get("video_id") or "") == video_id), None)
        if current is None:
            return {"deleted": False, "reason": "not_found", "video_id": video_id}
        path = archive_privacy._private_path(current)
        new_rows = [r for r in rows if str(r.get("video_id") or "") != video_id]
        await asyncio.to_thread(archive._write_records_sync, new_rows)
    file_deleted = False
    if path and os.path.exists(path):
        await asyncio.to_thread(os.remove, path)
        file_deleted = True
    print(f"🗑️ [H3_ARCHIVE_DISCORD_DELETE] video_id={video_id} file_deleted={file_deleted}")
    return {"deleted": True, "video_id": video_id, "file_deleted": file_deleted}


class DeleteConfirmView(discord.ui.View):
    def __init__(self, record: Dict[str, Any], owner_id: int):
        super().__init__(timeout=60)
        self.record = dict(record)
        self.owner_id = int(owner_id)
        self.completed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(getattr(interaction.user, "id", 0) or 0) != self.owner_id:
            await interaction.response.send_message("只有下這個刪除指令的大俠可以確認。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="確定刪除", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await _delete_record(self.record)
            self.completed = True
            for child in self.children:
                child.disabled = True
            try:
                await interaction.message.edit(content=f"✅ 已刪除 `{result.get('video_id')}`，影片檔與收藏紀錄都已移除。", view=self)
            except Exception:
                pass
            await interaction.followup.send("✅ 刪除完成。", ephemeral=True)
        except Exception as exc:
            print(f"❌ [H3_ARCHIVE_DISCORD_DELETE_FAILED] {type(exc).__name__}: {exc!r}")
            await interaction.followup.send("⚠️ 刪除失敗，請查看 Zeabur log。", ephemeral=True)

    @discord.ui.button(label="取消", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.completed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="已取消刪除。", view=self)


def _recent_lines(limit: int = 5) -> str:
    rows = archive._load_records_sync()[:limit]
    if not rows:
        return "小俠放映室目前沒有收藏影片。"
    lines = ["最近收藏："]
    for rec in rows:
        vid = str(rec.get("video_id") or "")
        title = str(rec.get("source_title") or rec.get("video_theme") or "H3 影片")
        lines.append(f"`{vid}`｜{title[:36]}")
    lines.append("\n回覆已收藏的 H3 影片輸入 `/H3刪除`，或輸入 `/H3刪除 <video_id>`。")
    return "\n".join(lines)


async def _resolved_reply(ctx):
    try:
        return await archive_retry._resolve_replied_message(ctx)
    except Exception:
        return None


def install_archive_delete_command(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")
    for name in ("H3刪除", "刪除H3"):
        try:
            bot.remove_command(name)
        except Exception:
            pass

    @bot.command(name="H3刪除", aliases=["刪除H3"])
    async def h3_delete_command(ctx, video_id: str = ""):
        record = _find_record_by_id(video_id) if video_id else None
        if record is None and not video_id:
            replied = await _resolved_reply(ctx)
            if replied is not None:
                record = _find_record_by_message_id(str(getattr(replied, "id", "") or ""))
        if record is None:
            await ctx.reply(_recent_lines(), mention_author=False)
            return

        vid = str(record.get("video_id") or "")
        title = str(record.get("source_title") or record.get("video_theme") or "H3 影片")
        view = DeleteConfirmView(record, int(ctx.author.id))
        await ctx.reply(
            f"🗑️ 要刪除這支收藏影片嗎？\n**{title}**\n`{vid}`\n刪除後會同時移除 MP4 與小俠放映室紀錄，無法復原。",
            view=view,
            mention_author=False,
        )

    # Persist the actual H3 result Discord message id whenever a save button is used.
    original_save = archive_privacy._save_no_download

    async def save_with_archive_message_id(view, interaction, button):
        before_ids = {str(r.get("video_id") or "") for r in archive._load_records_sync()}
        await original_save(view, interaction, button)
        if not getattr(view, "saved", False):
            return
        message_id = str(getattr(getattr(interaction, "message", None), "id", "") or "")
        if not message_id:
            return
        async with archive._STORE_LOCK:
            rows = await asyncio.to_thread(archive._load_records_sync)
            # The newest row created by this save is the first row not present before.
            target = next((r for r in rows if str(r.get("video_id") or "") not in before_ids), None)
            if target is not None:
                target["archive_message_id"] = message_id
                await asyncio.to_thread(archive._write_records_sync, rows)
                print(f"🔗 [H3_ARCHIVE_MESSAGE_LINKED] video_id={target.get('video_id')} message_id={message_id}")

    archive_privacy._save_no_download = save_with_archive_message_id
    archive_retry._save_existing_view = save_with_archive_message_id

    return {
        "patched": True,
        "command": "/H3刪除 (alias /刪除H3)",
        "reply_to_video_supported": True,
        "video_id_supported": True,
        "confirmation_required": True,
        "deletes_file_and_metadata": True,
        "regenerates_h3": False,
    }
