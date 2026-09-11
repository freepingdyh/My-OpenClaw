# -*- coding: utf-8 -*-
"""Native Discord slash-command bridge for legacy Xiaoxia text commands.

Discord mobile increasingly treats a leading slash as application-command UI.
This bridge registers the bot's existing prefix commands as native slash commands
without replacing their legacy handlers. /photo is special because it is handled
inside on_message rather than discord.py's prefix command registry.
"""
from __future__ import annotations

import inspect
from discord import app_commands

VERSION = "1.12.06aq"


class _InteractionCtx:
    """Small Context adapter sufficient for the existing command callbacks."""
    def __init__(self, app, interaction, content):
        self.bot = app.girlfriend_bot
        self.interaction = interaction
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.message = _InteractionMessage(interaction, content)

    async def send(self, content=None, **kwargs):
        if not self.interaction.response.is_done():
            return await self.interaction.response.send_message(content, **kwargs)
        return await self.interaction.followup.send(content, **kwargs)


class _InteractionMessage:
    def __init__(self, interaction, content):
        self.content = content
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.id = interaction.id
        self.attachments = []


async def _run_prefix_callback(app, interaction, command_name, args=""):
    cmd = app.girlfriend_bot.get_command(command_name)
    if cmd is None:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"⚠️ 找不到既有指令：/{command_name}", ephemeral=True)
        return
    content = f"/{command_name}" + (f" {args}" if args else "")
    ctx = _InteractionCtx(app, interaction, content)
    callback = cmd.callback
    sig = inspect.signature(callback)
    params = list(sig.parameters.values())[1:]  # skip ctx
    if not params:
        await callback(ctx)
        return
    # Existing Xiaoxia commands mostly use one optional positional or keyword-only text argument.
    p = params[0]
    if p.kind == inspect.Parameter.KEYWORD_ONLY:
        await callback(ctx, **{p.name: args})
    else:
        await callback(ctx, args or None)


def install_native_slash_commands(app):
    bot = app.girlfriend_bot
    tree = bot.tree
    registered = []

    # /photo is not a prefix Command; it is a special on_message route.
    async def photo_cb(interaction, prompt: str = ""):
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)
        content = "/photo" + (f" {prompt}" if prompt else "")
        msg = _InteractionMessage(interaction, content)
        await app.handle_unified_photo_command(msg, prompt)

    photo_cmd = app_commands.Command(
        name="photo",
        description="拍一張小俠照片",
        callback=photo_cb,
    )
    try:
        tree.add_command(photo_cmd, override=True)
        registered.append("photo")
    except Exception as exc:
        print(f"⚠️ [SLASH_REGISTER_SKIP] /photo {type(exc).__name__}: {exc}")

    # Mirror all ordinary prefix commands. One free-text option keeps legacy syntax flexible.
    for legacy in list(bot.commands):
        name = str(getattr(legacy, "name", "") or "").strip()
        if not name or name == "photo" or len(name) > 32:
            continue

        async def generic_cb(interaction, args: str = "", _name=name):
            await _run_prefix_callback(app, interaction, _name, args)

        try:
            cmd = app_commands.Command(
                name=name,
                description=(str(getattr(legacy, "help", "") or f"小俠指令：/{name}")[:100]),
                callback=generic_cb,
            )
            tree.add_command(cmd, override=True)
            registered.append(name)
        except Exception as exc:
            print(f"⚠️ [SLASH_REGISTER_SKIP] /{name} {type(exc).__name__}: {exc}")

    # Sync once after login. Preserve the existing on_ready behavior by wrapping it.
    original_ready = getattr(bot, "on_ready", None)
    synced = False

    async def on_ready_with_slash_sync():
        nonlocal synced
        if original_ready is not None:
            await original_ready()
        if synced:
            return
        try:
            synced_cmds = await tree.sync()
            synced = True
            print(f"✅ [NATIVE_SLASH_SYNC] version={VERSION} synced={len(synced_cmds)} registered={len(registered)}")
        except Exception as exc:
            print(f"❌ [NATIVE_SLASH_SYNC_FAILED] {type(exc).__name__}: {exc}")

    bot.on_ready = on_ready_with_slash_sync
    return {"version": VERSION, "registered": registered, "count": len(registered)}
