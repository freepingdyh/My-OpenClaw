# -*- coding: utf-8 -*-
"""H3 archive retry/rescue for v1.12.06v.

Goals:
- acknowledge the Discord component immediately before any file/archive I/O;
- let the save button be retried without regenerating H3;
- keep the archive view alive for the life of the process;
- after a successful save, expose a direct download link;
- rescue an already-generated Discord H3 attachment by replying `/H3收藏`
  (alias `/H3補收藏`) without calling fal/H3 again.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import discord

from xiaoxia.video import archive

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v")


def _find_save_button(view: discord.ui.View) -> Optional[discord.ui.Button]:
    for child in list(getattr(view, "children", []) or []):
        if not isinstance(child, discord.ui.Button):
            continue
        label = str(getattr(child, "label", "") or "").strip()
        if label in {"收藏到雲端別墅", "已收藏"}:
            return child
    return None


def _has_download_button(view: discord.ui.View) -> bool:
    for child in list(getattr(view, "children", []) or []):
        if isinstance(child, discord.ui.Button) and str(getattr(child, "label", "") or "").strip() == "下載影片":
            return True
    return False


def _add_download_button(view: discord.ui.View, url: str) -> None:
    if not url or _has_download_button(view):
        return
    view.add_item(
        discord.ui.Button(
            label="下載影片",
            emoji="⬇️",
            style=discord.ButtonStyle.link,
            url=url,
        )
    )


async def _save_existing_view(view: Any, interaction: discord.Interaction, button: discord.ui.Button) -> None:
    """Archive the already-generated H3 result. Never invokes H3 generation."""
    if getattr(view, "saved", False):
        if not interaction.response.is_done():
            await interaction.response.send_message("這支影片已經收藏到小俠放映室了。", ephemeral=True)
        return

    # ACK first. File copy/download and JSON writes happen only after Discord has
    # received the component acknowledgement, so slow storage cannot cause the
    # red '未及時回應' banner.
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    lock = getattr(view, "_xiaoxia_archive_retry_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        view._xiaoxia_archive_retry_lock = lock

    async with lock:
        if getattr(view, "saved", False):
            await interaction.followup.send("這支影片已經收藏到小俠放映室了。", ephemeral=True)
            return
        try:
            print("💾 [H3_ARCHIVE_RETRY_BEGIN] reuse_existing_video=True regenerate=False")
            record = await archive.archive_h3_video(
                view.app,
                context=view.context,
                result=view.result,
                source_jump_url=view.source_jump_url,
                source_message_id=view.source_message_id,
            )
            view.saved = True
            button.disabled = True
            button.label = "已收藏"
            button.emoji = "✅"
            _add_download_button(view, str(record.get("video_url") or ""))
            try:
                await interaction.message.edit(view=view)
            except Exception as exc:
                print(f"⚠️ [H3_ARCHIVE_VIEW_EDIT_FAILED] {type(exc).__name__}: {exc}")

            # Delete /tmp only after the permanent copy is confirmed saved.
            preview = str((view.result or {}).get("local_path") or "")
            if preview.startswith("/tmp/") and os.path.exists(preview):
                try:
                    os.remove(preview)
                except Exception:
                    pass

            await interaction.followup.send(
                f"✅ 已收藏到 **小俠放映室**｜{record.get('source_title')}\n"
                f"分類：{record.get('source_mode')}\n"
                f"⬇️ {record.get('video_url')}",
                ephemeral=True,
            )
            print(f"✅ [H3_ARCHIVE_RETRY_SAVED] video_id={record.get('video_id')} regenerate=False")
        except Exception as exc:
            print(f"❌ [H3_ARCHIVE_RETRY_FAILED] {type(exc).__name__}: {exc!r}")
            await interaction.followup.send(
                "收藏失敗，但不會重跑 H3；原影片仍保留，可再按一次收藏。",
                ephemeral=True,
            )


async def _resolve_replied_message(ctx):
    ref = getattr(ctx.message, "reference", None)
    if ref is None or not getattr(ref, "message_id", None):
        return None
    resolved = getattr(ref, "resolved", None)
    if resolved is not None:
        return resolved
    try:
        return await ctx.channel.fetch_message(ref.message_id)
    except Exception:
        return None


def _video_attachment(message) -> Optional[Any]:
    for att in list(getattr(message, "attachments", []) or []):
        ctype = str(getattr(att, "content_type", "") or "").lower()
        name = str(getattr(att, "filename", "") or "").lower()
        if ctype.startswith("video/") or name.endswith(_VIDEO_EXTS):
            return att
    return None


async def _rescue_from_discord_message(ctx, app: Any) -> None:
    """Promote a Discord H3 attachment into the archive with zero H3/fal calls."""
    replied = await _resolve_replied_message(ctx)
    if replied is None:
        await ctx.reply("請回覆那則已生成完成的 H3 影片訊息，再輸入 `/H3收藏`。", mention_author=False)
        return
    attachment = _video_attachment(replied)
    if attachment is None:
        await ctx.reply("你回覆的訊息裡找不到影片附件；請回覆 H3 影片本身。", mention_author=False)
        return

    # Use the Discord CDN attachment as the source. archive_h3_video downloads it
    # directly into OUTPUT_DIR; no model endpoint is called.
    result: Dict[str, Any] = {
        "video_url": str(getattr(attachment, "url", "") or ""),
        "local_path": "",
        "video_theme": "H3 既有影片補收藏",
        "motion_level": "",
        "voice_script": "",
        "director_plan": {},
        "duration": None,
        "resolution": None,
    }
    context: Dict[str, Any] = {
        "source_mode": "h3_rescue",
        "title": "H3 既有影片補收藏",
        "message": str(getattr(replied, "content", "") or "")[:1000],
    }

    ack = await ctx.reply("💾 收到，直接收藏這支既有 H3 影片；**不會重新生成**。", mention_author=False)
    try:
        record = await archive.archive_h3_video(
            app,
            context=context,
            result=result,
            source_jump_url=str(getattr(replied, "jump_url", "") or ""),
            source_message_id=str(getattr(replied, "id", "") or ""),
        )
        download_view = discord.ui.View(timeout=None)
        _add_download_button(download_view, str(record.get("video_url") or ""))
        await ack.edit(
            content=f"✅ 已補收藏到 **小俠放映室**，沒有重跑 H3。\n⬇️ {record.get('video_url')}",
            view=download_view,
        )
        print(f"✅ [H3_ARCHIVE_RESCUE_SAVED] video_id={record.get('video_id')} source=discord_attachment regenerate=False")
    except Exception as exc:
        print(f"❌ [H3_ARCHIVE_RESCUE_FAILED] {type(exc).__name__}: {exc!r}")
        await ack.edit(content="⚠️ 補收藏失敗；沒有重跑 H3，也沒有產生模型費用。")


def install_h3_archive_retry(app: Any) -> Dict[str, Any]:
    if getattr(archive, "_xiaoxia_h3_archive_retry_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original_init = archive.H3ArchiveView.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Keep retry available while this process remains alive. A redeploy still
        # loses dynamic View state, which is why /H3收藏 exists as a rescue path.
        self.timeout = None
        self._xiaoxia_archive_retry_lock = asyncio.Lock()
        button = _find_save_button(self)
        if button is not None:
            async def retry_callback(interaction: discord.Interaction, _button=button, _view=self):
                await _save_existing_view(_view, interaction, _button)
            button.callback = retry_callback
            button._xiaoxia_archive_retry = True

    archive.H3ArchiveView.__init__ = patched_init

    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")
    for name in ("H3收藏", "H3補收藏"):
        try:
            bot.remove_command(name)
        except Exception:
            pass

    @bot.command(name="H3收藏", aliases=["H3補收藏"])
    async def h3_archive_rescue_command(ctx):
        await _rescue_from_discord_message(ctx, app)

    archive._xiaoxia_h3_archive_retry_installed = True
    return {
        "patched": True,
        "component_ack_first": True,
        "retry_without_regeneration": True,
        "view_timeout": None,
        "download_button_after_save": True,
        "rescue_command": "/H3收藏 (alias /H3補收藏)",
        "rescue_source": "existing Discord video attachment",
        "regenerates_h3": False,
    }
