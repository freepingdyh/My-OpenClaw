# -*- coding: utf-8 -*-
"""Love Intent render-engine choice.

After Daxia approves "好，開始吧", keep Xiaoxia's already-authored Love Intent
candidate unchanged and let the user choose only the rendering engine:
- Seedream v4.5: existing Love Intent generation path.
- RunPod + Qwen-2.1: existing Qwen reference-scene path with Love prompt sanitizer.

The creative decision remains Xiaoxia's; this module changes only the renderer.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict

import discord

from xiaoxia.photo.qwen_scene import generate_qwen_scene_from_prompt
from xiaoxia.photo.love_qwen_fallback import (
    _prompt_from_context,
    _sanitize_seedream_prompt_for_qwen,
)

VERSION = "1.0.0-love-model-choice"
_ACTIVE_CANDIDATES: set[str] = set()


def _candidate_id(candidate: Dict[str, Any]) -> str:
    return str((candidate or {}).get("id") or "").strip()


def _owner_id(candidate: Dict[str, Any]) -> int | None:
    value = (candidate or {}).get("approved_by")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


async def _load_pending_candidate(app: Any, interaction: discord.Interaction) -> Dict[str, Any] | None:
    state = app.load_state()
    state, love = app._love_get_day_state(state)
    pending = love.get("pending_request") if isinstance(love.get("pending_request"), dict) else {}
    if not pending or pending.get("status", "waiting") not in {"waiting", "approved"}:
        await interaction.followup.send("這一張愛意邀請已經沒有等待中的內容了。", ephemeral=True)
        return None
    return dict(pending)


async def _run_seedream(
    app: Any,
    interaction: discord.Interaction,
    candidate: Dict[str, Any],
    *,
    auto_mode: bool = False,
) -> None:
    cid = _candidate_id(candidate)
    if cid and cid in _ACTIVE_CANDIDATES:
        await interaction.followup.send("💗 這份愛意已經在生成中了。", ephemeral=True)
        return

    try:
        if cid:
            _ACTIVE_CANDIDATES.add(cid)
        await interaction.message.edit(
            content=(
                "🌱 已選擇 **Seedream v4.5**。小俠正在把剛剛那份愛意畫出來…"
                if not auto_mode
                else "🔁 已選擇 **自動模式**。先用 Seedream v4.5；若最終失敗，再讓你決定是否改用 Qwen-2.1。"
            ),
            view=None,
        )
        await app._love_start_generation_task(
            interaction.channel,
            candidate,
            approved_by=getattr(interaction.user, "id", None),
            consume_daily_trigger=True,
        )
    finally:
        # _love_start_generation_task returns immediately after creating its own
        # tracked background task; do not keep this UI-level guard latched.
        if cid:
            _ACTIVE_CANDIDATES.discard(cid)


def _build_love_qwen_context(app: Any, candidate: Dict[str, Any]):
    wardrobe_item, wardrobe_reason, wardrobe_selection = app._love_pick_wardrobe(
        candidate.get("scene_text") or ""
    )
    context = app._love_build_photo_context(
        candidate,
        wardrobe_item=wardrobe_item,
        wardrobe_reason=wardrobe_reason,
        wardrobe_selection=wardrobe_selection,
    )
    context["generation_priority"] = "love"
    return context, wardrobe_item


async def _persist_qwen_love_result(
    app: Any,
    interaction: discord.Interaction,
    candidate: Dict[str, Any],
    context: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    db = app.load_memory()
    db.insert(0, app._photo_db_payload(result, type_override="photo"))
    app.save_memory(db)

    try:
        app._set_current_outfit_state(app._build_outfit_state_from_context(result))
        app._log_wardrobe_usage_from_context(result, purpose="love_intent_qwen")
    except Exception as exc:
        print(f"⚠️ [LOVE_MODEL_QWEN_OUTFIT_STATE_FAILED] {type(exc).__name__}: {exc}")

    view = app.PhotoResultView(result)
    sent = await app._send_photo_message(
        interaction.channel,
        result,
        view=view,
        title_prefix="💗 小俠愛意｜Qwen-2.1",
    )
    result["message_id"] = sent.id
    app.photo_generation_contexts[sent.id] = result
    view.context = result

    try:
        app._love_record_awareness(result, status="completed")
    except Exception as exc:
        print(f"⚠️ [LOVE_MODEL_QWEN_AWARENESS_FAILED] {type(exc).__name__}: {exc}")

    state = app.load_state()
    state, love = app._love_get_day_state(state)
    love["daily_generation_count"] = int(love.get("daily_generation_count") or 0) + 1
    app._love_mark_review_finished(
        love,
        result="completed_qwen",
        mark_asked=True,
        clear_pending=True,
    )
    app.save_state(state)


async def _run_qwen(
    app: Any,
    interaction: discord.Interaction,
    candidate: Dict[str, Any],
) -> None:
    cid = _candidate_id(candidate)
    if cid and cid in _ACTIVE_CANDIDATES:
        await interaction.followup.send("💗 這份愛意已經在生成中了。", ephemeral=True)
        return

    status = None
    if cid:
        _ACTIVE_CANDIDATES.add(cid)
    try:
        context, wardrobe_item = _build_love_qwen_context(app, candidate)
        raw_prompt = _prompt_from_context(context)
        if not raw_prompt:
            await interaction.followup.send("⚠️ 找不到小俠原本的愛意提示詞，這次先不生成。", ephemeral=True)
            return

        wid = str(context.get("wardrobe_id") or "").strip().upper()
        prompt = _sanitize_seedream_prompt_for_qwen(raw_prompt, wardrobe_id=wid)
        if not prompt:
            await interaction.followup.send("⚠️ 愛意提示詞整理後為空，這次先不生成。", ephemeral=True)
            return

        await interaction.message.edit(
            content="🧪 已選擇 **RunPod + Qwen-2.1**。保留小俠原本的愛意構想，整理 Seedream 專用語法後生成…",
            view=None,
        )
        status = await interaction.followup.send(
            "🧪 Qwen-2.1 正在生成這份愛意…",
            wait=True,
        )

        result = await generate_qwen_scene_from_prompt(
            app,
            prompt_text=prompt,
            source_context=context,
            wardrobe_item=wardrobe_item,
            wh_ratio=str(context.get("qwen_wh_ratio") or context.get("wh_ratio") or "3:4"),
        )
        result["love_qwen_prompt_sanitized"] = True
        result["love_qwen_prompt_sanitizer_version"] = VERSION
        result["love_qwen_original_prompt_chars"] = len(raw_prompt)
        result["love_qwen_sanitized_prompt"] = prompt
        result["love_render_engine_choice"] = "qwen_2.1"

        await _persist_qwen_love_result(app, interaction, candidate, context, result)

        if status is not None:
            try:
                await status.delete()
            except Exception:
                pass
        print(
            f"✅ [LOVE_MODEL_QWEN_COMPLETED] version={VERSION} "
            f"candidate={cid or '-'} wardrobe={wid or '-'} "
            f"outfit_ref={bool(result.get('love_qwen_outfit_ref_used'))}"
        )
    except Exception as exc:
        print(f"❌ [LOVE_MODEL_QWEN_FAILED] candidate={cid or '-'} {type(exc).__name__}: {exc}")
        if status is not None:
            try:
                await status.edit(
                    content=f"⚠️ RunPod + Qwen-2.1 生成失敗：{type(exc).__name__}: {str(exc)[:900]}"
                )
                return
            except Exception:
                pass
        await interaction.followup.send(
            f"⚠️ RunPod + Qwen-2.1 生成失敗：{type(exc).__name__}: {str(exc)[:900]}",
            ephemeral=True,
        )
    finally:
        if cid:
            _ACTIVE_CANDIDATES.discard(cid)


class LoveModelChoiceView(discord.ui.View):
    def __init__(self, app: Any, candidate: Dict[str, Any]):
        super().__init__(timeout=600)
        self.app = app
        self.candidate = dict(candidate or {})
        self.owner_id = _owner_id(self.candidate)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的小俠愛意模型選擇。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Seedream v4.5", style=discord.ButtonStyle.secondary, emoji="🌱")
    async def seedream(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        candidate = await _load_pending_candidate(self.app, interaction)
        if candidate is not None:
            await _run_seedream(self.app, interaction, candidate)

    @discord.ui.button(label="RunPod + Qwen-2.1", style=discord.ButtonStyle.primary, emoji="🧪")
    async def qwen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        candidate = await _load_pending_candidate(self.app, interaction)
        if candidate is not None:
            await _run_qwen(self.app, interaction, candidate)

    @discord.ui.button(label="自動模式", style=discord.ButtonStyle.success, emoji="🔁")
    async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        candidate = await _load_pending_candidate(self.app, interaction)
        if candidate is not None:
            await _run_seedream(self.app, interaction, candidate, auto_mode=True)


def install_love_model_choice(app: Any) -> Dict[str, Any]:
    view_cls = getattr(app, "LoveIntentInviteView", None)
    if view_cls is None:
        raise RuntimeError("LoveIntentInviteView not found")
    if getattr(view_cls, "_xiaoxia_love_model_choice_installed", False):
        return {"version": VERSION, "patched": False, "reason": "already_installed"}

    original_finish = view_cls._finish

    async def routed_finish(self, interaction, approved):
        if not approved:
            return await original_finish(self, interaction, approved)

        await interaction.response.defer(thinking=False)
        state = app.load_state()
        state, love = app._love_get_day_state(state)
        pending = love.get("pending_request") if isinstance(love.get("pending_request"), dict) else {}

        if not pending or pending.get("status", "waiting") not in {"waiting", "approved"}:
            await interaction.followup.send("這一張愛意邀請已經沒有等待中的內容了。", ephemeral=True)
            return

        pending_message_id = pending.get("message_id")
        clicked_message_id = getattr(getattr(interaction, "message", None), "id", None)
        if pending_message_id and clicked_message_id and int(pending_message_id) != int(clicked_message_id):
            await interaction.followup.send("這一張是舊的愛意邀請，小俠以最新的一張為準喔。", ephemeral=True)
            return

        candidate = dict(pending)
        candidate["status"] = "approved"
        candidate["approved_at"] = datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
        candidate["approved_by"] = getattr(getattr(interaction, "user", None), "id", None)
        love["pending_request"] = candidate
        app.save_state(state)

        print(
            f"💗 [LOVE_MODEL_CHOICE_OPENED] version={VERSION} "
            f"candidate={candidate.get('id')} message={clicked_message_id}"
        )
        await interaction.followup.send(
            "💗 小俠已經決定好今天想表達的內容了。這次要用哪個模型把它畫出來？",
            view=LoveModelChoiceView(app, candidate),
        )

    view_cls._finish = routed_finish
    view_cls._xiaoxia_love_model_choice_installed = True

    return {
        "version": VERSION,
        "patched": True,
        "choices": ["seedream_v4.5", "qwen_2.1", "auto"],
        "creative_source": "existing Love Intent candidate",
        "qwen_prompt": "sanitized existing Love Intent prompt",
        "special_delta": False,
    }
