# -*- coding: utf-8 -*-
"""v1.13.14 — process-memory Pose Test A selector handoff.

The v1.13.13 selector used app.load_state()/save_state() as the source of truth.
Runtime evidence showed that the command could succeed while the selector was absent
when /photo reached generation.  For an experiment switch, persistent bot state is the
wrong transport.

v1.13.14 therefore keeps the selector in process memory.  `/姿勢測試 A` writes a
one-shot selector keyed by (channel_id, user_id), plus a guarded global fallback for
this single-bot runtime.  The outer generation wrapper reads that memory immediately
before the inner photo wrappers execute and mirrors A_TEXT_ONLY into the currently
pending pose payload solely for compatibility with wardrobe_pose_test v1.13.12.
The selector is cleared after generation.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

VERSION = "1.13.14-process-memory-selector"
_STATE_KEY = "photo_pending_pose_reference"
_TEST_KEY = "pose_ab_test_mode"
_A_MODE = "A_TEXT_ONLY"


def _snowflake(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "id", value)
    return str(raw or "").strip()


def _key_from_command_ctx(ctx: Any) -> Tuple[str, str]:
    return (_snowflake(getattr(ctx, "channel", None)), _snowflake(getattr(ctx, "author", None)))


def _key_from_generation(context: Any, msg: Any) -> Tuple[str, str]:
    channel_id = ""
    user_id = ""
    if msg is not None:
        channel_id = _snowflake(getattr(msg, "channel", None))
        user_id = _snowflake(getattr(msg, "author", None))
    if isinstance(context, dict):
        if not channel_id:
            channel_id = _snowflake(context.get("channel_id") or context.get("discord_channel_id") or context.get("channel"))
        if not user_id:
            user_id = _snowflake(context.get("user_id") or context.get("discord_user_id") or context.get("author_id") or context.get("author"))
    return (channel_id, user_id)


def install_pose_test_mode_patch(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    # Process-local source of truth.  Never depend on serialized bot state for this
    # short-lived experimental switch.
    modes = getattr(app, "_pose_test_modes_v11314", None)
    if not isinstance(modes, dict):
        modes = {}
        setattr(app, "_pose_test_modes_v11314", modes)
    setattr(app, "_pose_test_global_v11314", "")

    try:
        bot.remove_command("姿勢測試")
    except Exception:
        pass

    @bot.command(name="姿勢測試")
    async def pose_test_command(ctx, *, request: str = ""):
        mode = str(request or "").strip().upper()
        key = _key_from_command_ctx(ctx)

        if mode in ("關閉", "OFF", "RESET", "取消"):
            modes.pop(key, None)
            setattr(app, "_pose_test_global_v11314", "")
            await ctx.reply("🧪 姿勢測試模式已關閉。", mention_author=False)
            print(f"🧪 [POSE_TEST_SELECTOR_V11314] action=clear key={key}")
            return

        if mode not in ("A", "A_TEXT", "TEXT", "TEXT_ONLY"):
            await ctx.reply(
                "用法：先 `/姿勢 穿 P013`，再 `/姿勢測試 A`，最後 `/photo 拍一張`。\n"
                "A = 固定 Pose Library 文字 ON；Figure 9 Pose visual reference OFF。",
                mention_author=False,
            )
            return

        state = app.load_state()
        pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
        if not isinstance(pending, dict) or not str(pending.get("pose_id") or "").strip():
            await ctx.reply("⚠️ 請先用 `/姿勢 穿 Pxxx` 選定姿勢，再開 Test A。", mention_author=False)
            return

        modes[key] = _A_MODE
        # Global fallback is intentional: some legacy generation calls do not retain
        # Discord author/channel on msg/context.  It is still one-shot and cleared in
        # finally, so it cannot leak to a later normal /photo.
        setattr(app, "_pose_test_global_v11314", _A_MODE)
        print(
            f"🧪 [POSE_TEST_SELECTOR_V11314] action=set mode={_A_MODE} "
            f"key={key} pose_id={pending.get('pose_id') or '?'} storage=process_memory"
        )
        await ctx.reply(
            f"🧪 **Pose Test A 已鎖定：{pending.get('pose_id')}**\n"
            "固定 Camera / Pose / Composition 文字：`ON`\n"
            "Figure 9 Pose visual reference：`OFF`\n"
            "Gemini 重新判讀：`OFF`\n"
            "Test selector：`PROCESS MEMORY LOCKED`\n"
            "下一步請輸入 `/photo 拍一張`。",
            mention_author=False,
        )

    previous_generate = app._generate_photo_from_context

    async def generate_with_test_mode_handoff(context, msg=None):
        key = _key_from_generation(context, msg)
        exact_mode = str(modes.get(key) or "").strip().upper()
        fallback_mode = str(getattr(app, "_pose_test_global_v11314", "") or "").strip().upper()
        mode = exact_mode or fallback_mode

        print(
            f"🧪 [POSE_TEST_LOOKUP_V11314] key={key} exact={exact_mode or '-'} "
            f"fallback={fallback_mode or '-'} selected={mode or '-'}"
        )

        if mode == _A_MODE:
            # Compatibility bridge only.  Process memory is authoritative; this write
            # simply lets the already-installed v1.13.12 generation wrapper read A.
            state = app.load_state()
            if not isinstance(state, dict):
                state = {}
            pending = state.get(_STATE_KEY)
            if isinstance(pending, dict) and str(pending.get("url") or "").startswith("http"):
                pending[_TEST_KEY] = _A_MODE
                state[_STATE_KEY] = pending
                app.save_state(state)
                print(
                    f"🧪 [POSE_TEST_MODE_HANDOFF_V11314] mode={_A_MODE} "
                    f"pose_id={pending.get('pose_id') or '?'} mirrored_to_pending=true source=process_memory"
                )
            else:
                print("⚠️ [POSE_TEST_MODE_HANDOFF_V11314] pending_pose_missing=true")

        try:
            return await previous_generate(context, msg=msg)
        finally:
            # One-shot selector.  Clear exact and fallback unconditionally after a
            # generation attempt so A cannot bleed into a later normal photo.
            modes.pop(key, None)
            setattr(app, "_pose_test_global_v11314", "")
            latest = app.load_state()
            if isinstance(latest, dict):
                p = latest.get(_STATE_KEY)
                if isinstance(p, dict) and _TEST_KEY in p:
                    p.pop(_TEST_KEY, None)
                    latest[_STATE_KEY] = p
                    app.save_state(latest)
            print(f"🧪 [POSE_TEST_MODE_CLEARED_V11314] key={key} one_shot=true")

    app._generate_photo_from_context = generate_with_test_mode_handoff
    return {
        "version": VERSION,
        "selector_storage": "process memory keyed by channel+user with one-shot fallback",
        "generation_handoff": True,
        "persistent_state_is_source_of_truth": False,
        "one_shot": True,
        "test_a": _A_MODE,
    }
