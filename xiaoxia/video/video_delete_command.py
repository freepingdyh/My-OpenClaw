# -*- coding: utf-8 -*-
"""v1.12.06z — provider-agnostic Discord video deletion by date.

Usage:
  /video_delete              -> today's archived videos (Asia/Taipei)
  /video_delete 2026-09-08   -> archived videos saved on that local date
  /video_delete 9/8          -> same, current year

The command lists all archived videos for the selected date with number, local time,
provider/model, title/theme and basic specs. The user chooses one numbered option from
a dropdown and confirms deletion. It deletes the private file + metadata record only;
it never calls a video model.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import discord

from xiaoxia.video import archive, archive_privacy

_TZ = ZoneInfo("Asia/Taipei")


def _parse_date(raw: str) -> str:
    text = str(raw or "").strip()
    now = datetime.now(_TZ)
    if not text:
        return now.strftime("%Y-%m-%d")

    text = text.replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return datetime(now.year, month, day).strftime("%Y-%m-%d")

    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")

    raise ValueError("DATE_FORMAT")


def _saved_local_dt(rec: Dict[str, Any]) -> Optional[datetime]:
    raw = str(rec.get("saved_at") or "").strip()
    if not raw:
        # legacy fallback: source_date has no reliable time, so use noon local for date matching.
        d = str(rec.get("source_date") or "").strip()[:10]
        try:
            return datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=_TZ, hour=12)
        except Exception:
            return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ)
        return dt.astimezone(_TZ)
    except Exception:
        return None


def _provider_label(rec: Dict[str, Any]) -> str:
    explicit = str(rec.get("provider") or rec.get("video_provider") or "").strip()
    if explicit:
        return explicit
    model = str(rec.get("model_id") or rec.get("video_model_id") or "").lower()
    vid = str(rec.get("video_id") or "").lower()
    if "seedance" in model or vid.startswith("seedance"):
        return "Seedance"
    if "wan" in model or vid.startswith("wan"):
        return "Wan"
    if "grok" in model or vid.startswith("grok"):
        return "Grok"
    if "h3" in model or "minimax" in model or vid.startswith("h3_"):
        return "H3"
    return "Video"


def _model_short(rec: Dict[str, Any]) -> str:
    model = str(rec.get("model_id") or rec.get("video_model_id") or "").strip()
    if not model:
        return ""
    return model.split("/")[-1][:32]


def _title(rec: Dict[str, Any]) -> str:
    return str(rec.get("source_title") or rec.get("video_theme") or "未命名影片").strip()


def _theme(rec: Dict[str, Any]) -> str:
    return str(rec.get("video_theme") or "").strip()


def _rows_for_date(date_str: str) -> List[Dict[str, Any]]:
    rows = []
    for rec in archive._load_records_sync():
        dt = _saved_local_dt(rec)
        if dt and dt.strftime("%Y-%m-%d") == date_str:
            item = dict(rec)
            item["_local_dt"] = dt
            rows.append(item)
    rows.sort(key=lambda r: r["_local_dt"], reverse=True)
    return rows


async def _delete_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    video_id = str(rec.get("video_id") or "").strip()
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
    print(f"🗑️ [VIDEO_ARCHIVE_DELETE] video_id={video_id} provider={_provider_label(rec)} file_deleted={file_deleted}")
    return {"deleted": True, "video_id": video_id, "file_deleted": file_deleted}


class VideoDeleteConfirmView(discord.ui.View):
    def __init__(self, rec: Dict[str, Any], owner_id: int):
        super().__init__(timeout=60)
        self.rec = dict(rec)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(getattr(interaction.user, "id", 0) or 0) != self.owner_id:
            await interaction.response.send_message("只有下 `/video_delete` 的大俠可以操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="確定刪除", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await _delete_record(self.rec)
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(
                content=f"✅ 已刪除 **{_provider_label(self.rec)}** 影片｜{_title(self.rec)}\n`{result.get('video_id')}`",
                view=self,
            )
            await interaction.followup.send("✅ 影片檔與收藏紀錄都已刪除。", ephemeral=True)
        except Exception as exc:
            print(f"❌ [VIDEO_ARCHIVE_DELETE_FAILED] {type(exc).__name__}: {exc!r}")
            await interaction.followup.send("⚠️ 刪除失敗，請查看 Zeabur log。", ephemeral=True)

    @discord.ui.button(label="取消", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="已取消刪除。", view=self)


class VideoNumberSelect(discord.ui.Select):
    def __init__(self, rows: List[Dict[str, Any]], owner_id: int):
        self.rows = rows
        self.owner_id = int(owner_id)
        options = []
        for idx, rec in enumerate(rows[:25], start=1):
            dt = rec["_local_dt"].strftime("%H:%M")
            provider = _provider_label(rec)
            title = _title(rec)
            desc_bits = [dt, provider]
            model = _model_short(rec)
            if model:
                desc_bits.append(model)
            options.append(
                discord.SelectOption(
                    label=f"{idx}. {title[:78]}",
                    value=str(idx - 1),
                    description="｜".join(desc_bits)[:100],
                    emoji="🎬",
                )
            )
        super().__init__(placeholder="選擇要刪除的影片編號", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if int(getattr(interaction.user, "id", 0) or 0) != self.owner_id:
            await interaction.response.send_message("只有下 `/video_delete` 的大俠可以選擇。", ephemeral=True)
            return
        idx = int(self.values[0])
        rec = self.rows[idx]
        dt = rec["_local_dt"].strftime("%Y-%m-%d %H:%M")
        provider = _provider_label(rec)
        model = _model_short(rec)
        specs = " × ".join(str(x) for x in (rec.get("duration"), rec.get("resolution")) if x not in (None, ""))
        text = (
            f"🗑️ **確認刪除影片**\n"
            f"時間：{dt}\n"
            f"模型：{provider}{('｜' + model) if model else ''}\n"
            f"主題：{_title(rec)}\n"
            f"{('規格：' + specs + chr(10)) if specs else ''}"
            f"刪除後會同時移除私有影片檔與收藏紀錄，無法復原。"
        )
        await interaction.response.send_message(
            text,
            view=VideoDeleteConfirmView(rec, self.owner_id),
            ephemeral=True,
        )


class VideoDeleteListView(discord.ui.View):
    def __init__(self, rows: List[Dict[str, Any]], owner_id: int):
        super().__init__(timeout=120)
        self.add_item(VideoNumberSelect(rows, owner_id))


def _format_listing(date_str: str, rows: List[Dict[str, Any]]) -> str:
    lines = [f"🎞️ **{date_str} 收藏影片**｜共 {len(rows)} 支"]
    for idx, rec in enumerate(rows, start=1):
        dt = rec["_local_dt"].strftime("%H:%M")
        provider = _provider_label(rec)
        model = _model_short(rec)
        title = _title(rec)
        theme = _theme(rec)
        specs = []
        if rec.get("duration") not in (None, ""):
            specs.append(f"{rec.get('duration')}s")
        if rec.get("resolution"):
            specs.append(str(rec.get("resolution")))
        meta = "｜".join(x for x in [dt, provider, model, " ".join(specs)] if x)
        lines.append(f"**{idx}.** {meta}\n　{title[:70]}")
        if theme and theme != title:
            lines.append(f"　主題：{theme[:80]}")
    if len(rows) > 25:
        lines.append("\n⚠️ Discord 單次選單最多 25 支；目前先提供最新 25 支可選。")
    lines.append("\n請從下方選單選擇編號，再做一次刪除確認。")
    return "\n".join(lines)


def install_video_delete_command(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    # Retire H3-specific public command names. Keep the old module loaded only for
    # backward runtime compatibility; users get one provider-agnostic command.
    for name in ("H3刪除", "刪除H3", "video_delete"):
        try:
            bot.remove_command(name)
        except Exception:
            pass

    @bot.command(name="video_delete")
    async def video_delete(ctx, date_text: str = ""):
        try:
            date_str = _parse_date(date_text)
        except Exception:
            await ctx.reply(
                "日期格式可用 `2026-09-08`、`2026/9/8` 或 `9/8`；不填日期就是今天。",
                mention_author=False,
            )
            return
        rows = _rows_for_date(date_str)
        if not rows:
            await ctx.reply(f"🎞️ {date_str} 沒有收藏影片。", mention_author=False)
            return
        await ctx.reply(
            _format_listing(date_str, rows),
            view=VideoDeleteListView(rows[:25], int(ctx.author.id)),
            mention_author=False,
        )

    # Future-proof metadata for newly archived videos: keep model/provider on the
    # shared archive record so /video_delete can remain provider-agnostic.
    original_archive = archive.archive_h3_video

    async def archive_with_model_metadata(app_module: Any, *, context: Dict[str, Any], result: Dict[str, Any], source_jump_url: str = "", source_message_id: str = ""):
        rec = await original_archive(
            app_module,
            context=context,
            result=result,
            source_jump_url=source_jump_url,
            source_message_id=source_message_id,
        )
        model_id = str(result.get("model_id") or "").strip()
        provider = _provider_label({"model_id": model_id, "video_id": rec.get("video_id")})
        async with archive._STORE_LOCK:
            rows = await asyncio.to_thread(archive._load_records_sync)
            target = next((r for r in rows if str(r.get("video_id") or "") == str(rec.get("video_id") or "")), None)
            if target is not None:
                if model_id:
                    target["model_id"] = model_id
                target["provider"] = provider
                await asyncio.to_thread(archive._write_records_sync, rows)
                rec.update({"model_id": model_id, "provider": provider})
        return rec

    archive.archive_h3_video = archive_with_model_metadata

    return {
        "patched": True,
        "command": "/video_delete [date]",
        "default_date": "today Asia/Taipei",
        "provider_agnostic": True,
        "lists_time_provider_model_title_theme_specs": True,
        "numbered_select": True,
        "confirmation_required": True,
        "deletes_file_and_metadata": True,
        "retired_commands": ["/H3刪除", "/刪除H3"],
    }
