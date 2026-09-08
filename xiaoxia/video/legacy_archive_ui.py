# -*- coding: utf-8 -*-
"""v1.12.06w — give legacy /影片 output the same archive affordance as button H3."""
from __future__ import annotations

import os
from typing import Any, Dict

import discord

from xiaoxia.video import archive, h3_director_mode, legacy_command, voiceover_mode


async def _send_legacy_with_archive(ctx, result: Dict[str, Any], context: Dict[str, Any], app: Any) -> None:
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

    source_jump = str(getattr(getattr(ctx, "message", None), "jump_url", "") or "")
    source_id = str(getattr(getattr(ctx, "message", None), "id", "") or "")
    view = archive.H3ArchiveView(app, context, result, source_jump, source_id)

    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await ctx.reply("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)), view=view, mention_author=False)
    else:
        link = result.get("local_url") or result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await ctx.reply("\n".join(lines), view=view, mention_author=False)


def install_legacy_archive_ui(app: Any) -> Dict[str, Any]:
    if getattr(legacy_command, "_xiaoxia_legacy_archive_ui_installed", False):
        return {"patched": False, "reason": "already_installed"}

    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    # Replace the legacy command at the final runtime layer so it uses the same
    # H3 generator/Director and archive.H3ArchiveView as the image-card button.
    try:
        bot.remove_command("影片")
    except Exception:
        pass

    @bot.command(name="影片")
    async def legacy_h3_with_archive(ctx):
        replied = await legacy_command._resolve_replied_message(ctx)
        if replied is None:
            await ctx.reply("請先回覆一則小俠的圖片訊息，再輸入 `/影片`。", mention_author=False)
            return
        context = legacy_command._context_from_runtime(app, replied) or legacy_command._context_from_message(replied)
        image_url = str(context.get("local_url") or context.get("image_url") or "").strip()
        local_path = str(context.get("local_path") or "").strip()
        if not image_url and not (local_path and os.path.exists(local_path)):
            await ctx.reply("這則訊息裡找不到可用的圖片，請回覆真正有小俠圖片的那一則。", mention_author=False)
            return
        cfg = voiceover_mode._config()
        await ctx.reply(f"🎬 收到，直接用你回覆的這張原圖生成 {cfg.get('duration')} 秒 H3 影片。", mention_author=False)
        try:
            async with ctx.typing():
                result = await h3_director_mode._generate_h3_native_directed(app, context)
            await _send_legacy_with_archive(ctx, result, context, app)
        except Exception as exc:
            print(f"❌ [H3_LEGACY_ARCHIVE_UI_ERROR] {type(exc).__name__}: {exc!r}")
            try:
                from xiaoxia.video import diagnostics
                await ctx.reply(diagnostics.format_h3_error(exc, cfg), mention_author=False)
            except Exception:
                await ctx.reply("⚠️ H3 影片生成失敗，請查看 Zeabur log。", mention_author=False)

    legacy_command._xiaoxia_legacy_archive_ui_installed = True
    return {
        "patched": True,
        "command": "/影片",
        "archive_button": True,
        "download_after_save": True,
        "same_archive_view": True,
        "regeneration_for_archive": False,
    }
