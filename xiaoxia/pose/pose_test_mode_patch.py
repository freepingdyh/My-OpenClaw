# -*- coding: utf-8 -*-
"""v1.13.13 — robust Pose A/B test-mode handoff.

Why this exists:
The first v1.13.12 experiment stored A_TEXT_ONLY only inside
photo_pending_pose_reference. Later wrappers can reconstruct/replace that pending
payload, so the selector may disappear before wardrobe_pose_test reads it.

This patch stores the experiment selector at state top-level as the durable source
of truth, mirrors it back into the pending pose immediately before generation, and
clears it after the one-shot generation. It is installed late so the handoff occurs
outside the other photo wrappers.
"""
from __future__ import annotations

from typing import Any, Dict

VERSION = "1.13.13-test-mode-persistence"
_STATE_KEY = "photo_pending_pose_reference"
_TEST_KEY = "pose_ab_test_mode"
_A_MODE = "A_TEXT_ONLY"


def install_pose_test_mode_patch(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    # Re-register after all earlier pose command wrappers. The top-level selector is
    # authoritative; mirroring into pending keeps v1.13.12 wardrobe_pose_test fully
    # compatible without changing the normal pose path.
    try:
        bot.remove_command("姿勢測試")
    except Exception:
        pass

    @bot.command(name="姿勢測試")
    async def pose_test_command(ctx, *, request: str = ""):
        mode = str(request or "").strip().upper()
        state = app.load_state()
        if not isinstance(state, dict):
            state = {}
        pending = state.get(_STATE_KEY)

        if mode in ("關閉", "OFF", "RESET", "取消"):
            state.pop(_TEST_KEY, None)
            if isinstance(pending, dict):
                pending.pop(_TEST_KEY, None)
                state[_STATE_KEY] = pending
            app.save_state(state)
            await ctx.reply("🧪 姿勢測試模式已關閉。", mention_author=False)
            return

        if mode not in ("A", "A_TEXT", "TEXT", "TEXT_ONLY"):
            await ctx.reply(
                "用法：先 `/姿勢 穿 P013`，再 `/姿勢測試 A`，最後 `/photo 拍一張`。\n"
                "A = 固定 Pose Library 文字 ON；Figure 9 Pose visual reference OFF。",
                mention_author=False,
            )
            return

        if not isinstance(pending, dict) or not str(pending.get("pose_id") or "").strip():
            await ctx.reply("⚠️ 請先用 `/姿勢 穿 Pxxx` 選定姿勢，再開 Test A。", mention_author=False)
            return

        state[_TEST_KEY] = _A_MODE
        pending[_TEST_KEY] = _A_MODE
        state[_STATE_KEY] = pending
        app.save_state(state)
        await ctx.reply(
            f"🧪 **Pose Test A 已鎖定：{pending.get('pose_id')}**\n"
            "固定 Camera / Pose / Composition 文字：`ON`\n"
            "Figure 9 Pose visual reference：`OFF`\n"
            "Gemini 重新判讀：`OFF`\n"
            "Test selector：`TOP-LEVEL + PENDING LOCKED`\n"
            "下一步請輸入 `/photo 拍一張`。",
            mention_author=False,
        )

    previous_generate = app._generate_photo_from_context

    async def generate_with_test_mode_handoff(context, msg=None):
        state = app.load_state()
        if not isinstance(state, dict):
            state = {}
        top_mode = str(state.get(_TEST_KEY) or "").strip().upper()
        pending = state.get(_STATE_KEY)

        if top_mode == _A_MODE and isinstance(pending, dict):
            pending[_TEST_KEY] = _A_MODE
            state[_STATE_KEY] = pending
            app.save_state(state)
            print(
                f"🧪 [POSE_TEST_MODE_HANDOFF_V11313] mode={_A_MODE} "
                f"pose_id={pending.get('pose_id') or '?'} mirrored_to_pending=true"
            )

        try:
            return await previous_generate(context, msg=msg)
        finally:
            # The pose itself is already one-shot in the inner wrapper. The experiment
            # selector must also be one-shot so a later normal /photo cannot inherit A.
            latest = app.load_state()
            if isinstance(latest, dict) and str(latest.get(_TEST_KEY) or "").strip():
                latest.pop(_TEST_KEY, None)
                p = latest.get(_STATE_KEY)
                if isinstance(p, dict):
                    p.pop(_TEST_KEY, None)
                    latest[_STATE_KEY] = p
                app.save_state(latest)
                print("🧪 [POSE_TEST_MODE_CLEARED_V11313] one_shot=true")

    app._generate_photo_from_context = generate_with_test_mode_handoff
    return {
        "version": VERSION,
        "selector_storage": "top-level + pending mirror",
        "generation_handoff": True,
        "one_shot": True,
        "test_a": _A_MODE,
    }
