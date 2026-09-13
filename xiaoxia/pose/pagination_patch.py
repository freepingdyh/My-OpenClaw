# -*- coding: utf-8 -*-
"""v1.13.08 — paginated Pose Library browser.

Discord allows at most 10 attachments per message. `/姿勢` therefore renders ten
Pose cards per page and adds Previous/Next buttons so older Pxxx assets remain
reachable without changing the existing Pose command vocabulary.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Tuple

import discord

from xiaoxia.pose import core as pose_core

VERSION = "1.13.08"
PAGE_SIZE = 10


def _page_payload(rows: List[Dict[str, Any]], page: int) -> Tuple[str, List[discord.Embed], List[discord.File], int, int]:
    total = len(rows)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, pages))
    start = (page - 1) * PAGE_SIZE
    shown = rows[start:start + PAGE_SIZE]

    embeds: List[discord.Embed] = []
    files: List[discord.File] = []
    for i, row in enumerate(shown):
        path = str(row.get("file_path") or "")
        ext = os.path.splitext(path)[1] or ".jpg"
        filename = f"pose_p{page}_{i}{ext}"
        emb = discord.Embed(
            title=f"{row.get('id')}｜{row.get('name') or '姿勢'}",
            description=f"{row.get('category') or '其他'}｜{'、'.join(row.get('tags') or [])}",
        )
        if path and os.path.exists(path):
            files.append(discord.File(path, filename=filename))
            emb.set_thumbnail(url=f"attachment://{filename}")
        embeds.append(emb)

    content = f"💃 **小俠姿勢櫃**｜共 {total} 張｜第 {page}/{pages} 頁"
    return content, embeds, files, page, pages


class PosePager(discord.ui.View):
    def __init__(self, rows: List[Dict[str, Any]], page: int, owner_id: int | None = None):
        super().__init__(timeout=600)
        self.rows = rows
        self.page = page
        self.owner_id = owner_id
        self.pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.pages

    async def _render(self, interaction: discord.Interaction, page: int) -> None:
        if self.owner_id is not None and getattr(getattr(interaction, "user", None), "id", None) != self.owner_id:
            await interaction.response.send_message("這是大俠目前開啟的姿勢櫃頁面。", ephemeral=True)
            return
        content, embeds, files, page, pages = _page_payload(self.rows, page)
        self.page = page
        self.pages = pages
        self._sync_buttons()
        await interaction.response.edit_message(content=content, embeds=embeds, attachments=files, view=self)

    @discord.ui.button(label="上一頁", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, self.page - 1)

    @discord.ui.button(label="下一頁", emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, self.page + 1)


def install_pose_pagination_patch(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    old_command = bot.get_command("姿勢")
    if old_command is None:
        raise RuntimeError("/姿勢 command not installed")
    try:
        bot.remove_command("姿勢")
    except Exception:
        pass

    @bot.command(name="姿勢")
    async def pose_command_v11308(ctx, *, request: str = ""):
        text = str(request or "").strip()

        # Empty `/姿勢` opens page 1. `/姿勢 2` or `/姿勢 第2頁` is a text fallback
        # for clients where Discord component buttons are unavailable.
        page = None
        if not text:
            page = 1
        else:
            m = re.match(r"^(?:第\s*)?(\d+)\s*(?:頁)?$", text)
            if m:
                page = int(m.group(1))

        if page is not None:
            rows = pose_core._load_index()
            if not rows:
                await ctx.reply("💃 姿勢櫃目前是空的。附上一張姿勢圖後輸入 `/姿勢 新增` 即可收錄。", mention_author=False)
                return
            content, embeds, files, page, pages = _page_payload(rows, page)
            view = PosePager(rows, page, owner_id=getattr(getattr(ctx, "author", None), "id", None))
            await ctx.reply(content, embeds=embeds, files=files, view=view, mention_author=False)
            return

        await ctx.invoke(old_command, request=text)

    return {
        "version": VERSION,
        "page_size": PAGE_SIZE,
        "buttons": ["上一頁", "下一頁"],
        "text_fallback": "/姿勢 2 or /姿勢 第2頁",
    }
