# -*- coding: utf-8 -*-
"""Native Discord slash-command bridge for legacy Xiaoxia text commands."""
from __future__ import annotations

import contextlib
import inspect
from discord import app_commands

VERSION = "1.12.06as"


class _TypingProxy:
    """Async context manager compatible with `async with ctx.typing()`.

    Native slash interactions have no classic channel typing lifecycle that matters here,
    so this becomes a harmless no-op while preserving legacy command code.
    """
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _InteractionCtx:
    def __init__(self, app, interaction, content):
        self.bot = app.girlfriend_bot
        self.interaction = interaction
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.message = _InteractionMessage(interaction, content)

    async def send(self, content=None, **kwargs):
        # Legacy prefix commands often call ctx.send(). A slash command may already have
        # been deferred, in which case every visible reply must go through followup.
        kwargs.pop("mention_author", None)
        if not self.interaction.response.is_done():
            return await self.interaction.response.send_message(content, **kwargs)
        return await self.interaction.followup.send(content, **kwargs)

    async def reply(self, content=None, **kwargs):
        # Prefix handlers such as /影片 use ctx.reply(..., mention_author=False).
        # Interactions do not have a message to reply to in the same way, so map it to send.
        kwargs.pop("mention_author", None)
        return await self.send(content, **kwargs)

    def typing(self):
        # Preserve `async with ctx.typing()` used by long-running legacy handlers.
        return _TypingProxy()


class _InteractionMessage:
    def __init__(self, interaction, content):
        self.content = content
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.id = interaction.id
        self.attachments = []

    async def delete(self):
        # Some legacy commands delete the invoking prefix message. There is no ordinary
        # user-authored message to delete for an application command, so this is a no-op.
        return None


async def _run_prefix_callback(app, interaction, command_name, args=""):
    cmd = app.girlfriend_bot.get_command(command_name)
    if cmd is None:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"⚠️ 找不到既有指令：/{command_name}", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ 找不到既有指令：/{command_name}", ephemeral=True)
        return
    content = f"/{command_name}" + (f" {args}" if args else "")
    ctx = _InteractionCtx(app, interaction, content)
    callback = cmd.callback
    params = list(inspect.signature(callback).parameters.values())[1:]
    if not params:
        await callback(ctx)
        return
    p = params[0]
    if p.kind == inspect.Parameter.KEYWORD_ONLY:
        await callback(ctx, **{p.name: args})
    else:
        await callback(ctx, args or None)


def _make_generic_callback(app, command_name):
    async def callback(interaction, args: str = ""):
        # Discord requires an initial application-command acknowledgement quickly.
        # Legacy commands may do API/video work before their first ctx.send(), so defer
        # immediately and let the adapter route all later output through followups.
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)
        try:
            await _run_prefix_callback(app, interaction, command_name, args)
        except Exception as exc:
            print(f"❌ [NATIVE_SLASH_HANDLER_FAILED] /{command_name} {type(exc).__name__}: {exc}")
            with contextlib.suppress(Exception):
                await interaction.followup.send(
                    f"⚠️ `/{command_name}` 執行失敗：`{type(exc).__name__}` — `{str(exc)[:300]}`",
                    ephemeral=True,
                )
            raise
    return callback


def install_native_slash_commands(app):
    bot = app.girlfriend_bot
    tree = bot.tree
    registered = []

    async def photo_cb(interaction, prompt: str = ""):
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)
        content = "/photo" + (f" {prompt}" if prompt else "")
        msg = _InteractionMessage(interaction, content)
        await app.handle_unified_photo_command(msg, prompt)

    try:
        tree.add_command(app_commands.Command(name="photo", description="拍一張小俠照片", callback=photo_cb), override=True)
        registered.append("photo")
    except Exception as exc:
        print(f"⚠️ [SLASH_REGISTER_SKIP] /photo {type(exc).__name__}: {exc}")

    for legacy in list(bot.commands):
        name = str(getattr(legacy, "name", "") or "").strip()
        if not name or name == "photo" or len(name) > 32:
            continue
        try:
            tree.add_command(
                app_commands.Command(
                    name=name,
                    description=(str(getattr(legacy, "help", "") or f"小俠指令：/{name}")[:100]),
                    callback=_make_generic_callback(app, name),
                ),
                override=True,
            )
            registered.append(name)
        except Exception as exc:
            print(f"⚠️ [SLASH_REGISTER_SKIP] /{name} {type(exc).__name__}: {exc}")

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
