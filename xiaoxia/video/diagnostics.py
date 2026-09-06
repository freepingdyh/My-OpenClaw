# -*- coding: utf-8 -*-
"""H3 diagnostics / safety-checker runtime policy for Xiaoxia.

Goals:
- do not guess why fal rejected a request; expose the structured error fields;
- keep the full exception in server logs, but show a compact diagnostic in Discord;
- default H3's optional enable_safety_checker flag to False unless ENV explicitly sets it;
- apply the same diagnostics to both the shared H3 button and legacy `/影片` reply command.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, Optional

import discord

from xiaoxia.video import h3
from xiaoxia.video import legacy_command


def _iter_error_dicts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_error_dicts(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_error_dicts(child)


def _loc_text(loc: Any) -> str:
    if isinstance(loc, (list, tuple)):
        parts = []
        for part in loc:
            text = str(part)
            if text.startswith("["):
                parts.append(text)
            elif parts:
                parts.append("." + text)
            else:
                parts.append(text)
        return "".join(parts)
    return str(loc or "").strip()


def extract_h3_error(exc: Exception) -> Dict[str, Any]:
    """Extract fal/FastAPI style structured errors without relying on prompt guessing."""
    result: Dict[str, Any] = {
        "exception": type(exc).__name__,
        "http_status": None,
        "type": None,
        "loc": None,
        "msg": None,
        "url": None,
    }

    for attr in ("status_code", "status", "http_status"):
        value = getattr(exc, attr, None)
        if value is not None:
            result["http_status"] = value
            break

    candidates = []
    for arg in getattr(exc, "args", ()) or ():
        candidates.extend(list(_iter_error_dicts(arg)))
    for attr in ("body", "detail", "response", "data"):
        value = getattr(exc, attr, None)
        if value is not None:
            candidates.extend(list(_iter_error_dicts(value)))

    for item in candidates:
        if result["type"] is None and item.get("type"):
            result["type"] = str(item.get("type"))
        if result["loc"] is None and item.get("loc") is not None:
            result["loc"] = _loc_text(item.get("loc"))
        if result["msg"] is None and item.get("msg"):
            result["msg"] = str(item.get("msg"))
        if result["url"] is None and item.get("url"):
            result["url"] = str(item.get("url"))
        if result["type"] and result["loc"] and result["msg"]:
            break

    # Conservative text fallback only for fields that were not structurally available.
    raw = str(exc or "")
    if result["type"] is None:
        match = re.search(r"['\"]type['\"]\s*:\s*['\"]([^'\"]+)", raw)
        if match:
            result["type"] = match.group(1)
    if result["loc"] is None:
        match = re.search(r"['\"]loc['\"]\s*:\s*\[([^\]]+)\]", raw)
        if match:
            bits = [x.strip().strip("'\"") for x in match.group(1).split(",")]
            result["loc"] = _loc_text(bits)
    if result["msg"] is None:
        match = re.search(r"['\"]msg['\"]\s*:\s*['\"]([^'\"]+)", raw)
        if match:
            result["msg"] = match.group(1)

    return result


def format_h3_error(exc: Exception, cfg: Optional[Dict[str, Any]] = None) -> str:
    cfg = cfg or h3._config()
    info = extract_h3_error(exc)
    lines = ["⚠️ **H3影片生成失敗**"]
    lines.append(f"`exception: {info.get('exception') or 'unknown'}`")
    if info.get("http_status") is not None:
        lines.append(f"`http: {info.get('http_status')}`")
    if info.get("type"):
        lines.append(f"`type: {info.get('type')}`")
    if info.get("loc"):
        lines.append(f"`loc: {info.get('loc')}`")
    if info.get("msg"):
        msg = " ".join(str(info.get("msg")).split())[:260]
        lines.append(f"`msg: {msg}`")
    lines.append(f"`safety_checker: {str(bool(cfg.get('safety'))).lower()}`")
    lines.append(f"`voice_mode: {cfg.get('voice_mode')}`")
    lines.append(f"`reference_model: {cfg.get('reference_model')}`")
    lines.append(f"`image_model: {cfg.get('image_model')}`")
    return "\n".join(lines)


async def _send_success_to_interaction(view, interaction: discord.Interaction, result: Dict[str, Any]) -> None:
    cfg = h3._config()
    lines = [
        "🎬 **H3影片生成完成**",
        f"規格：{result.get('duration')} 秒｜{result.get('resolution')}",
    ]
    if result.get("used_voice") and result.get("voice_script"):
        label = "Sulafat 聲音參考" if result.get("voice_mode") == "reference_audio" else "H3 原生語音"
        lines.append(f"🗣️ {label}：{result.get('voice_script')}")
    elif result.get("voice_mode") == "silent_turbo":
        lines.append("🔇 本次為無語音 H3 fallback")

    local_path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
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


async def _diagnostic_button_callback(button, interaction: discord.Interaction) -> None:
    app = button._app
    view = button._owner_view
    cfg = h3._config()
    if not cfg["enabled"]:
        await interaction.response.send_message("🎬 H3影片生成功能目前未啟用。", ephemeral=True)
        return

    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = message_id or id(view)
    if job_key in h3._ACTIVE_JOBS:
        await interaction.response.send_message("🎬 這張照片正在生成 H3 影片，先等這一支完成喔。", ephemeral=True)
        return

    h3._ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    try:
        context = dict(getattr(view, "context", {}) or {})
        result = await h3.generate_h3_video(app, context)
        await _send_success_to_interaction(view, interaction, result)
    except Exception as exc:
        # Full raw exception remains in logs for forensic inspection; Discord gets structured fields only.
        print(f"❌ [H3_VIDEO_ERROR_RAW] {type(exc).__name__}: {exc!r}")
        await interaction.followup.send(format_h3_error(exc, cfg), ephemeral=True)
    finally:
        h3._ACTIVE_JOBS.discard(job_key)


async def _diagnostic_legacy_command(ctx, app) -> None:
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

    cfg = h3._config()
    await ctx.reply(
        f"🎬 收到，直接用你回覆的這張原圖生成 {cfg.get('duration')} 秒 H3 影片。",
        mention_author=False,
    )
    try:
        async with ctx.typing():
            result = await h3.generate_h3_video(app, context)
        await legacy_command._send_video_result(ctx, result)
    except Exception as exc:
        print(f"❌ [H3_LEGACY_ERROR_RAW] {type(exc).__name__}: {exc!r}")
        await ctx.reply(format_h3_error(exc, cfg), mention_author=False)


def install_h3_diagnostics(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_h3_diagnostics_installed", False):
        return {"patched": False, "reason": "already_installed"}

    # The endpoint exposes this optional checker switch. Default it off for Xiaoxia,
    # while preserving an explicit Zeabur ENV override in either direction.
    original_config = h3._config

    def diagnostic_config():
        cfg = dict(original_config())
        if "H3_VIDEO_ENABLE_SAFETY_CHECKER" not in os.environ:
            cfg["safety"] = False
        return cfg

    h3._config = diagnostic_config
    legacy_command._config = diagnostic_config

    # New image result cards: replace callback behavior centrally at the Button class.
    async def patched_button_callback(self, interaction: discord.Interaction):
        await _diagnostic_button_callback(self, interaction)

    h3.H3VideoButton.callback = patched_button_callback

    # Old-image `/影片`: re-register command so its error reply is structured, not a giant raw exception.
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")
    bot.remove_command("影片")

    @bot.command(name="影片")
    async def diagnostic_legacy_h3_video_command(ctx):
        await _diagnostic_legacy_command(ctx, app)

    app.h3_format_error = format_h3_error
    app.h3_extract_error = extract_h3_error
    h3._xiaoxia_h3_diagnostics_installed = True
    cfg = h3._config()
    return {
        "patched": True,
        "safety_checker_default": cfg.get("safety"),
        "env_override_supported": True,
        "discord_error_format": "structured",
        "legacy_command_rewired": True,
    }
