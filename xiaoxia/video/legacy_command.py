# -*- coding: utf-8 -*-
"""Legacy-message H3 entrypoint.

Usage in Discord:
1. Reply to an existing Xiaoxia image message.
2. Send `/影片`.

The command first reuses the in-memory photo_generation_contexts entry when available.
If the old message predates the current process/restart, it falls back to extracting the
actual image URL and visible embed text from the replied Discord message, so an old
cosplay/photo can still be animated without regenerating the image.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import discord

from .h3 import generate_h3_video, _config


def _embed_image_url(message: discord.Message) -> str:
    # Prefer the actual attachment if the image was sent as a Discord file.
    for attachment in list(getattr(message, "attachments", []) or []):
        content_type = str(getattr(attachment, "content_type", "") or "").lower()
        filename = str(getattr(attachment, "filename", "") or "").lower()
        if content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")):
            return str(getattr(attachment, "url", "") or "").strip()

    # Then try embed image / thumbnail URLs.
    for embed in list(getattr(message, "embeds", []) or []):
        image = getattr(embed, "image", None)
        url = str(getattr(image, "url", "") or "").strip()
        if url:
            return url
        thumb = getattr(embed, "thumbnail", None)
        url = str(getattr(thumb, "url", "") or "").strip()
        if url:
            return url
    return ""


def _context_from_message(message: discord.Message) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "image_url": _embed_image_url(message),
        "source_mode": "photo",
        "type": "photo",
        "title": "舊照片影片",
    }

    embeds = list(getattr(message, "embeds", []) or [])
    if embeds:
        embed = embeds[0]
        title = str(getattr(embed, "title", "") or "").strip()
        description = str(getattr(embed, "description", "") or "").strip()
        fields = list(getattr(embed, "fields", []) or [])
        field_map = {
            str(getattr(field, "name", "") or "").strip(): str(getattr(field, "value", "") or "").strip()
            for field in fields
        }

        visible_blob = "\n".join(x for x in [title, description, *field_map.values()] if x).lower()
        if "cosplay" in visible_blob or "今日角色" in field_map or "小俠版詮釋" in field_map:
            context["source_mode"] = "cosplay"
            context["type"] = "cosplay"

        context["title"] = title or context["title"]
        context["message"] = field_map.get("💌 小俠給大俠") or description
        context["composition"] = field_map.get("📸 今日畫面") or description
        context["scene_summary"] = field_map.get("📸 今日畫面") or description or title
        context["scene_text"] = context["scene_summary"]
        context["authoritative_scene"] = context["scene_summary"]

    return context


async def _resolve_replied_message(ctx) -> Optional[discord.Message]:
    ref = getattr(getattr(ctx, "message", None), "reference", None)
    if ref is None:
        return None

    resolved = getattr(ref, "resolved", None)
    if isinstance(resolved, discord.Message):
        return resolved

    message_id = getattr(ref, "message_id", None)
    if message_id and getattr(ctx, "channel", None):
        try:
            return await ctx.channel.fetch_message(int(message_id))
        except Exception as exc:
            print(f"⚠️ [H3_REPLY_FETCH_FAILED] {type(exc).__name__}: {exc}")
    return None


def _context_from_runtime(app, message: discord.Message) -> Optional[Dict[str, Any]]:
    store = getattr(app, "photo_generation_contexts", None)
    if isinstance(store, dict):
        found = store.get(getattr(message, "id", None))
        if isinstance(found, dict):
            return dict(found)
    return None


async def _send_video_result(ctx, result: Dict[str, Any]) -> None:
    cfg = _config()
    lines = [
        "🎬 **H3影片生成完成**",
        f"規格：{result.get('duration')} 秒｜{result.get('resolution')}",
    ]
    if result.get("used_voice") and result.get("voice_script"):
        label = "Sulafat 聲音參考" if result.get("voice_mode") == "reference_audio" else "H3 原生語音"
        lines.append(f"🗣️ {label}：{result.get('voice_script')}")

    local_path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if local_path and os.path.exists(local_path) and os.path.getsize(local_path) <= max_bytes:
        await ctx.reply(
            "\n".join(lines),
            file=discord.File(local_path, filename=os.path.basename(local_path)),
            mention_author=False,
        )
        return

    link = result.get("local_url") or result.get("video_url")
    if link:
        lines.append(f"📎 {link}")
    await ctx.reply("\n".join(lines), mention_author=False)


def install_legacy_video_command(app) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    existing = bot.get_command("影片")
    if existing is not None:
        return {"module": "xiaoxia.video.legacy_command", "installed": False, "reason": "already_exists"}

    @bot.command(name="影片")
    async def legacy_h3_video_command(ctx):
        replied = await _resolve_replied_message(ctx)
        if replied is None:
            await ctx.reply("請先回覆一則小俠的圖片訊息，再輸入 `/影片`。", mention_author=False)
            return

        context = _context_from_runtime(app, replied) or _context_from_message(replied)
        image_url = str(context.get("local_url") or context.get("image_url") or "").strip()
        local_path = str(context.get("local_path") or "").strip()
        if not image_url and not (local_path and os.path.exists(local_path)):
            await ctx.reply("這則訊息裡找不到可用的圖片，請回覆真正有小俠圖片的那一則。", mention_author=False)
            return

        await ctx.reply("🎬 收到，直接用你回覆的這張原圖生成 15 秒 H3 影片。", mention_author=False)
        try:
            async with ctx.typing():
                result = await generate_h3_video(app, context)
            await _send_video_result(ctx, result)
        except Exception as exc:
            print(f"❌ [H3_LEGACY_COMMAND_ERROR] {type(exc).__name__}: {exc}")
            await ctx.reply(
                f"⚠️ H3影片生成失敗：`{type(exc).__name__}: {str(exc)[:1200]}`",
                mention_author=False,
            )

    return {"module": "xiaoxia.video.legacy_command", "installed": True, "command": "/影片"}
