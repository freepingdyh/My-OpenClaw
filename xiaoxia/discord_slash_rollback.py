# -*- coding: utf-8 -*-
"""Rollback the temporary native slash-command bridge.

Reason: many Xiaoxia legacy commands intentionally accept a normal Discord
message with both free-form text and image attachments. Mirroring them into
application commands with a single string `args` option breaks that workflow
on mobile because attachments are no longer part of the message.

This module removes Xiaoxia's temporary global application commands from the
bot command tree and syncs the removal once after login. Legacy prefix/message
handlers remain untouched.
"""
from __future__ import annotations

VERSION = "1.12.06at"


def install_native_slash_rollback(app):
    bot = app.girlfriend_bot
    tree = bot.tree

    # Remove every global app command registered on this bot process. The
    # temporary aq/as bridge added these dynamically; legacy prefix/message
    # commands live in discord.ext.commands and are unaffected.
    try:
        tree.clear_commands(guild=None)
    except Exception as exc:
        print(f"⚠️ [SLASH_ROLLBACK_CLEAR_FAILED] {type(exc).__name__}: {exc}")

    original_ready = getattr(bot, "on_ready", None)
    synced = False

    async def on_ready_with_slash_rollback():
        nonlocal synced
        if original_ready is not None:
            await original_ready()
        if synced:
            return
        try:
            synced_cmds = await tree.sync()
            synced = True
            print(f"✅ [NATIVE_SLASH_ROLLBACK_SYNC] version={VERSION} remaining={len(synced_cmds)}")
        except Exception as exc:
            print(f"❌ [NATIVE_SLASH_ROLLBACK_SYNC_FAILED] {type(exc).__name__}: {exc}")

    bot.on_ready = on_ready_with_slash_rollback
    return {"version": VERSION, "global_tree_cleared": True, "legacy_commands_preserved": True}
