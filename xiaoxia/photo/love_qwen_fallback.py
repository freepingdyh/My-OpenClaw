# -*- coding: utf-8 -*-
"""User-confirmed Qwen fallback for failed Love Intent still-image generation.

Contract:
- Love Intent keeps Seedream v4.5 as the primary path.
- Only after the existing Seedream pipeline ultimately raises do we remember the
  already-authored Love Intent context.
- The existing long Discord failure message is replaced with a compact opt-in UI.
- Qwen runs only after the user presses the confirmation button.
- The existing Love Intent prompt is reused directly; Gemini is not called again.
- special_delta is never appended on this path.
- A matching wardrobe item may contribute one pure-clothing reference as image4.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict

import discord

from xiaoxia.photo.qwen_scene import generate_qwen_scene_from_prompt

VERSION = "1.0.3-love-qwen-fallback-button-owner-fix"

_PENDING_BY_TASK: dict[int, dict] = {}
_LATEST_PENDING: dict | None = None
_ORIGINAL_GENERATE = None
_ORIGINAL_MESSAGEABLE_SEND = None
_ORIGINAL_CHANNEL_SENDS: dict[type, Any] = {}
_ORIGINAL_WEBHOOK_SEND = None
_ORIGINAL_MESSAGE_EDIT = None


def _is_love_context(context: Any) -> bool:
    if not isinstance(context, dict):
        return False
    joined = " ".join(
        str(context.get(k) or "").strip().lower()
        for k in ("source_mode", "source_module", "type", "db_type")
    )
    if "love_intent" in joined or joined.strip() == "love":
        return True
    return any(
        isinstance(v, str) and "LOVE INTENT" in v.upper()
        for v in context.values()
    )


def _task_key() -> int:
    task = asyncio.current_task()
    return id(task) if task is not None else 0


def _remember_pending(context: dict, msg: Any, exc: Exception) -> None:
    global _LATEST_PENDING
    author = getattr(msg, "author", None)
    owner_id = None
    if author is not None and not bool(getattr(author, "bot", False)):
        owner_id = getattr(author, "id", None)
    payload = {
        "context": dict(context or {}),
        "msg": msg,
        "owner_id": owner_id,
        "error_type": type(exc).__name__,
        "error_text": str(exc),
        "created_mono": time.monotonic(),
    }
    _PENDING_BY_TASK[_task_key()] = payload
    _LATEST_PENDING = payload
    print(
        f"💞 [LOVE_QWEN_FALLBACK_READY] version={VERSION} "
        f"error={type(exc).__name__} wardrobe={payload['context'].get('wardrobe_id') or ''}"
    )


def _pending_for_current_task() -> dict | None:
    payload = _PENDING_BY_TASK.pop(_task_key(), None)
    if payload is not None:
        return payload
    latest = _LATEST_PENDING
    if isinstance(latest, dict) and time.monotonic() - float(latest.get("created_mono") or 0) <= 180:
        return latest
    return None


def _looks_like_love_failure_message(content: Any) -> bool:
    text = str(content or "")
    if not text:
        return False
    if "小俠剛剛想拍這份愛意" in text and "失敗" in text:
        return True
    return "最終保底生圖依然失敗" in text and "愛意" in text


def _prompt_from_context(context: Dict[str, Any]) -> str:
    # Prefer the already-authored Love Intent / Gemini scene contract. Avoid a
    # second rewrite so the fallback preserves what Xiaoxia originally chose.
    for key in (
        "love_intent_prompt",
        "love_prompt",
        "authoritative_scene",
        "root_prompt_base",
        "prompt_base",
        "scene_text",
        "composition",
    ):
        value = str(context.get(key) or "").strip()
        if value:
            return value
    return ""


def _wardrobe_id_from_context(context: Dict[str, Any]) -> str:
    direct = str(context.get("wardrobe_id") or "").strip().upper()
    if direct:
        return direct
    blob = " ".join(
        str(context.get(k) or "")
        for k in (
            "outfit_summary",
            "wardrobe_name",
            "root_prompt_base",
            "prompt_base",
            "authoritative_scene",
        )
    )
    match = re.search(r"\bW\d{3,4}\b", blob, flags=re.I)
    return match.group(0).upper() if match else ""


def _wardrobe_item(app: Any, context: Dict[str, Any]) -> dict | None:
    wid = _wardrobe_id_from_context(context)
    finder = getattr(app, "_find_wardrobe_item", None)
    if wid and callable(finder):
        try:
            item = finder(wid)
            if isinstance(item, dict):
                return item
        except Exception as exc:
            print(f"⚠️ [LOVE_QWEN_WARDROBE_LOOKUP_FAILED] {type(exc).__name__}: {exc}")
    return None


async def _send_qwen_result(app: Any, interaction: discord.Interaction, source: dict, result: dict) -> None:
    db = app.load_memory()
    db.insert(0, app._photo_db_payload(result, type_override=app._context_db_type(result)))
    app.save_memory(db)

    view = app.PhotoResultView(result)
    sent = await app._send_photo_message(
        interaction.channel,
        result,
        view=view,
        title_prefix="💞 小俠愛意｜Qwen-2.1",
    )
    result["message_id"] = sent.id
    app.photo_generation_contexts[sent.id] = result
    view.context = result


class LoveQwenFallbackView(discord.ui.View):
    def __init__(self, app: Any, pending: dict):
        super().__init__(timeout=600)
        self.app = app
        self.pending = pending
        self.owner_id = pending.get("owner_id")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Love Intent generation often runs in a background task whose msg.author
        # is the bot/status message rather than the human who approved the invite.
        # Do not reject the confirmation button based on that stale author.
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            print(
                f"⚠️ [LOVE_QWEN_OWNER_MISMATCH_IGNORED] version={VERSION} "
                f"stored_owner={self.owner_id} click_user={interaction.user.id}"
            )
        return True

    @discord.ui.button(label="改用 RunPod + Qwen-2.1", style=discord.ButtonStyle.primary, emoji="🧪")
    async def use_qwen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        source = dict(self.pending.get("context") or {})
        prompt = _prompt_from_context(source)
        if not prompt:
            await interaction.followup.send("⚠️ 找不到小俠原本的愛意提示詞，這次先不改走 Qwen。", ephemeral=True)
            return

        item = _wardrobe_item(self.app, source)
        wid = _wardrobe_id_from_context(source)
        status = await interaction.followup.send(
            "🧪 正在沿用小俠原本的愛意構想，改用 RunPod + Qwen-2.1 生成…",
            wait=True,
        )
        try:
            result = await generate_qwen_scene_from_prompt(
                self.app,
                prompt_text=prompt,
                source_context=source,
                wardrobe_item=item,
                wh_ratio=str(source.get("qwen_wh_ratio") or source.get("wh_ratio") or "3:4"),
            )
            await _send_qwen_result(self.app, interaction, source, result)
            try:
                await status.delete()
            except Exception:
                pass
            try:
                await interaction.message.edit(
                    content=(
                        "✅ Seedream v4.5 失敗後，已依你的確認改用 RunPod + Qwen-2.1。"
                        + (f"\n衣著：{wid}" if wid else "")
                    ),
                    view=None,
                )
            except Exception:
                pass
            print(
                f"✅ [LOVE_QWEN_FALLBACK_COMPLETED] version={VERSION} "
                f"wardrobe={wid or '-'} outfit_ref={bool(result.get('love_qwen_outfit_ref_used'))}"
            )
        except Exception as exc:
            try:
                await status.edit(content=f"⚠️ RunPod + Qwen-2.1 生成失敗：{type(exc).__name__}: {str(exc)[:900]}")
            except Exception:
                await interaction.followup.send(
                    f"⚠️ RunPod + Qwen-2.1 生成失敗：{type(exc).__name__}: {str(exc)[:900]}",
                    ephemeral=True,
                )

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="好，這次小俠愛意照片先不重試。", view=None)


def install_love_qwen_fallback(app: Any) -> Dict[str, Any]:
    global _ORIGINAL_GENERATE, _ORIGINAL_MESSAGEABLE_SEND

    if getattr(app, "_xiaoxia_love_qwen_fallback_installed", False):
        return {"version": VERSION, "patched": False, "reason": "already_installed"}

    current_generate = getattr(app, "_generate_photo_from_context", None)
    if not callable(current_generate):
        raise RuntimeError("_generate_photo_from_context not found")

    _ORIGINAL_GENERATE = current_generate

    async def wrapped_generate(context, msg=None, *args, **kwargs):
        try:
            return await current_generate(context, msg=msg, *args, **kwargs)
        except Exception as exc:
            if _is_love_context(context):
                _remember_pending(dict(context or {}), msg, exc)
            raise

    wrapped_generate._xiaoxia_love_qwen_fallback = True
    wrapped_generate._xiaoxia_love_qwen_fallback_original = current_generate
    app._generate_photo_from_context = wrapped_generate

    # Existing Love Intent code owns its retry count and final failure wording.
    # The runtime emits the final error through concrete Discord channel classes,
    # so patch both the base Messageable method and concrete channel send methods.
    def _wrap_send(current_send):
        async def wrapped_send(self, content=None, *args, **kwargs):
            if _looks_like_love_failure_message(content):
                pending = _pending_for_current_task()
                if pending is not None:
                    ctx = pending.get("context") or {}
                    wid = _wardrobe_id_from_context(ctx)
                    concise = (
                        "⚠️ 小俠這次用 Seedream v4.5 表達愛意失敗了。\n"
                        "要改用 RunPod + Qwen-2.1，沿用小俠原本的提示詞繼續生成嗎？"
                    )
                    if wid:
                        concise += f"\n衣著：{wid}"
                    kwargs["view"] = LoveQwenFallbackView(app, pending)
                    print(
                        f"💞 [LOVE_QWEN_FALLBACK_UI_INTERCEPTED] version={VERSION} "
                        f"channel_type={type(self).__name__} wardrobe={wid or '-'}"
                    )
                    return await current_send(self, concise, *args, **kwargs)
            return await current_send(self, content, *args, **kwargs)

        wrapped_send._xiaoxia_love_qwen_fallback = True
        wrapped_send._xiaoxia_love_qwen_fallback_original = current_send
        return wrapped_send

    messageable = discord.abc.Messageable
    current_send = messageable.send
    _ORIGINAL_MESSAGEABLE_SEND = current_send
    messageable.send = _wrap_send(current_send)

    for channel_cls in (
        getattr(discord, "TextChannel", None),
        getattr(discord, "Thread", None),
        getattr(discord, "DMChannel", None),
        getattr(discord, "GroupChannel", None),
    ):
        if channel_cls is None:
            continue
        concrete_send = getattr(channel_cls, "send", None)
        if not callable(concrete_send):
            continue
        if getattr(concrete_send, "_xiaoxia_love_qwen_fallback", False):
            continue
        _ORIGINAL_CHANNEL_SENDS[channel_cls] = concrete_send
        setattr(channel_cls, "send", _wrap_send(concrete_send))

    # Background Love Intent generation is launched from a button interaction.
    # Its terminal result may therefore be emitted via Interaction.followup
    # (discord.Webhook.send) or by editing an existing status message rather
    # than through channel.send. Cover those concrete exits too.
    webhook_cls = getattr(discord, "Webhook", None)
    if webhook_cls is not None:
        webhook_send = getattr(webhook_cls, "send", None)
        if callable(webhook_send) and not getattr(webhook_send, "_xiaoxia_love_qwen_fallback", False):
            _ORIGINAL_WEBHOOK_SEND = webhook_send
            setattr(webhook_cls, "send", _wrap_send(webhook_send))

    message_cls = getattr(discord, "Message", None)
    if message_cls is not None:
        message_edit = getattr(message_cls, "edit", None)
        if callable(message_edit) and not getattr(message_edit, "_xiaoxia_love_qwen_fallback", False):
            _ORIGINAL_MESSAGE_EDIT = message_edit

            async def wrapped_message_edit(self, *args, **kwargs):
                content = kwargs.get("content")
                if _looks_like_love_failure_message(content):
                    pending = _pending_for_current_task()
                    if pending is not None:
                        ctx = pending.get("context") or {}
                        wid = _wardrobe_id_from_context(ctx)
                        concise = (
                            "⚠️ 小俠這次用 Seedream v4.5 表達愛意失敗了。\n"
                            "要改用 RunPod + Qwen-2.1，沿用小俠原本的提示詞繼續生成嗎？"
                        )
                        if wid:
                            concise += f"\n衣著：{wid}"
                        kwargs["content"] = concise
                        kwargs["view"] = LoveQwenFallbackView(app, pending)
                        print(
                            f"💞 [LOVE_QWEN_FALLBACK_UI_INTERCEPTED_EDIT] version={VERSION} "
                            f"message_id={getattr(self, 'id', None)} wardrobe={wid or '-'}"
                        )
                return await message_edit(self, *args, **kwargs)

            wrapped_message_edit._xiaoxia_love_qwen_fallback = True
            wrapped_message_edit._xiaoxia_love_qwen_fallback_original = message_edit
            setattr(message_cls, "edit", wrapped_message_edit)

    app._xiaoxia_love_qwen_fallback_installed = True
    print(f"✅ [LOVE_QWEN_FALLBACK_INSTALLED] version={VERSION}")
    return {
        "version": VERSION,
        "patched": True,
        "primary": "Seedream v4.5 existing retry path",
        "fallback": "RunPod Qwen-Image-2.1 after explicit user confirmation",
        "prompt_rewrite": False,
        "special_delta": False,
        "outfit_reference": "optional pure wardrobe image as image4",
    }
