# -*- coding: utf-8 -*-
"""Special intimacy image flow for Xiaoxia.

Scope for this phase:
- add one shared "情不自禁" button to every PhotoResultView;
- image_1 is always the exact current result image;
- normal photos optionally ask Xiaoxia for consent via Gemini;
- cosplay bypasses the consent gate;
- Love Intent can bypass only when the context is explicitly pre-approved;
- no PXXX/WXXX extra reference images yet;
- render through the already-validated RunPod Qwen Image 2.1 path.

This module intentionally keeps the special renderer separate from Xiaoxia's core
personality/runtime so future special H3 can reuse the same decision layer.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp
import discord
from google.genai import types

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21


VERSION = "1.14.03-special-intimacy-v3"
_BUTTON_LABEL = "💞 情不自禁"
_ACTIVE_JOBS: set[Any] = set()


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None and name == "XIAOXIA_PERMISSION":
        raw = os.environ.get("xiaoxia_permission")
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "關", "關閉"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _mode(context: Dict[str, Any]) -> str:
    ctx = context or {}
    raw = str(
        ctx.get("source_mode")
        or ctx.get("type")
        or ctx.get("db_type")
        or ctx.get("source_module")
        or "photo"
    ).strip().lower()
    aliases = {
        "photo_scene": "photo",
        "photo_reference": "photo",
        "love_intent": "love",
        "xiaoxia_autonomy": "autonomy",
    }
    return aliases.get(raw, raw or "photo")


def _love_preapproved(context: Dict[str, Any]) -> bool:
    ctx = context or {}
    if bool(ctx.get("special_preapproved")):
        return True
    markers = (
        str(ctx.get("special_intent") or "").strip().lower(),
        str(ctx.get("love_special_intent") or "").strip().lower(),
        str(ctx.get("special_intimacy_intent") or "").strip().lower(),
    )
    return any(v in {"offer", "allow", "approved", "preapproved", "yes", "true"} for v in markers)


def _permission_required(context: Dict[str, Any]) -> bool:
    if not _env_bool("XIAOXIA_PERMISSION", True):
        return False
    mode = _mode(context)
    if mode == "cosplay":
        return False
    if mode == "love" and _love_preapproved(context):
        return False
    return True


def _scene(context: Dict[str, Any]) -> str:
    ctx = context or {}
    return _clean(
        ctx.get("authoritative_scene")
        or ctx.get("scene_summary")
        or ctx.get("scene_text")
        or ctx.get("composition")
        or ctx.get("pose_public_scene")
        or ctx.get("message")
        or ctx.get("title")
        or ""
    )


def _outfit(context: Dict[str, Any]) -> str:
    ctx = context or {}
    wardrobe_id = _clean(ctx.get("wardrobe_id") or "")
    wardrobe_name = _clean(ctx.get("wardrobe_name") or "")
    summary = _clean(ctx.get("outfit_summary") or "")
    return " | ".join(x for x in (wardrobe_id, wardrobe_name, summary) if x)


async def _recent_dialogue(interaction: discord.Interaction, limit: int = 12) -> str:
    channel = getattr(interaction, "channel", None)
    history = getattr(channel, "history", None)
    if not callable(history):
        return ""
    rows = []
    try:
        messages = []
        async for message in channel.history(limit=max(1, min(limit, 20))):
            messages.append(message)
        for message in reversed(messages):
            author = _clean(
                getattr(getattr(message, "author", None), "display_name", "")
                or getattr(getattr(message, "author", None), "name", "")
                or "unknown"
            )
            text = _clean(getattr(message, "content", "") or "")
            if not text:
                embeds = list(getattr(message, "embeds", None) or [])
                if embeds:
                    e = embeds[0]
                    text = _clean(
                        " ".join(
                            x
                            for x in (
                                getattr(e, "title", "") or "",
                                getattr(e, "description", "") or "",
                            )
                            if x
                        )
                    )
            if text:
                rows.append(f"{author}: {text[:700]}")
    except Exception as exc:
        print(f"⚠️ [SPECIAL_DIALOGUE_HISTORY_FAILED] {type(exc).__name__}: {exc}")
        return ""
    return "\n".join(rows)[-6000:]


def _mime_for(path_or_url: str) -> str:
    mime, _ = mimetypes.guess_type(str(path_or_url or ""))
    return mime if mime and mime.startswith("image/") else "image/png"


async def _source_image_bytes(app: Any, context: Dict[str, Any]) -> Tuple[bytes, str]:
    ctx = context or {}
    candidates = []

    local_path = str(ctx.get("local_path") or "").strip()
    if local_path:
        candidates.append(local_path)

    local_url = str(ctx.get("local_url") or "").strip()
    image_url = str(ctx.get("image_url") or "").strip()

    mapper = getattr(app, "_gallery_url_to_local_path", None)
    for value in (local_url, image_url):
        if value and callable(mapper):
            try:
                mapped = mapper(value)
            except Exception:
                mapped = None
            if mapped:
                candidates.append(str(mapped))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return Path(candidate).read_bytes(), _mime_for(candidate)

    url = next((x for x in (local_url, image_url) if x.startswith(("http://", "https://"))), "")
    if not url:
        raise RuntimeError("SPECIAL_SOURCE_IMAGE_NOT_FOUND")

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"SPECIAL_SOURCE_IMAGE_HTTP_{response.status}")
            data = await response.read()
            if not data:
                raise RuntimeError("SPECIAL_SOURCE_IMAGE_EMPTY")
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
            return data, content_type if content_type.startswith("image/") else _mime_for(url)


def _parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


async def _plan_special(
    app: Any,
    interaction: discord.Interaction,
    context: Dict[str, Any],
    image_bytes: bytes,
    mime_type: str,
    permission_required: bool,
) -> Dict[str, str]:
    mode = _mode(context)
    scene = _scene(context)
    outfit = _outfit(context)
    dialogue = "" if mode == "cosplay" else await _recent_dialogue(interaction)

    consent_rule = (
        "This is a real consent decision. Decide allow or decline in-character. "
        "Do not allow merely because the user asked. Use the recent dialogue, current scene, "
        "Xiaoxia's own tone and the actual image."
        if permission_required
        else "Consent was already handled by product policy for this path. decision MUST be allow."
    )

    prompt = f"""
妳是小俠本人，同時也是這張照片的特殊版本導演。小俠是 24 歲成年女性。
妳知道剛剛的對話、目前場景，以及附上的實際成圖。

這個功能代表：大俠想看看比平常更私密、更性感的一面。
{consent_rule}

只輸出 JSON，不要 markdown：
{{
  "decision": "allow" 或 "decline",
  "reply": "小俠以繁體中文自由回應大俠，不限制句數；自然說她真正想說的話",
  "mood": "簡短英文 mood token"
}}

規則：
- 這一步只做小俠的意願與對話，不要替 Qwen 撰寫影像 prompt。
- 不要輸出影像生成指令、服裝修改指令或視覺 transformation prompt。
- 圖像編輯完全使用已驗證的 ComfyUI / Qwen Image 2.1 workflow 原生 prompt。

mode: {mode}
cosplay continuity rule: {"Ignore chat history and use only the current cosplay image/context." if mode == "cosplay" else "Use recent dialogue for continuity."}
scene: {scene[:2500]}
outfit: {outfit[:1200]}
recent dialogue:
{dialogue[:6000]}
""".strip()

    model = (os.environ.get("XIAOXIA_SPECIAL_DIRECTOR_MODEL") or "gemini-2.5-flash").strip()
    try:
        contents = [
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ]
        response = await app.gemini_client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        parsed = _parse_json_text(getattr(response, "text", "") or "")
        if parsed:
            decision = str(parsed.get("decision") or "").strip().lower()
            if not permission_required:
                decision = "allow"
            if decision not in {"allow", "decline"}:
                decision = "decline" if permission_required else "allow"
            return {
                "decision": decision,
                "reply": str(parsed.get("reply") or "").strip(),
                "mood": _clean(parsed.get("mood") or ""),
            }
    except Exception as exc:
        print(f"⚠️ [SPECIAL_DIRECTOR_FAILED] {type(exc).__name__}: {exc}")

    if permission_required:
        return {
            "decision": "decline",
            "reply": "大俠，這次我想先保留一點給自己，好嗎？",
            "mood": "gentle",
        }
    return {
        "decision": "allow",
        "reply": "",
        "mood": "intimate",
    }


def _public_url(filename: str) -> str:
    base = (os.environ.get("XIAOXIA_PUBLIC_BASE_URL") or "https://xiaoxia0320.zeabur.app").rstrip("/")
    return f"{base}/gallery/{filename}"


def _persist_result(app: Any, source: Dict[str, Any], filename: str, blob: bytes, plan: Dict[str, str]) -> Dict[str, Any]:
    output_dir = Path(str(getattr(app, "OUTPUT_DIR", "/tmp") or "/tmp"))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_bytes(blob)

    new_context = dict(source or {})
    inherit = getattr(app, "_inherit_photo_lineage", None)
    if callable(inherit):
        try:
            target: Dict[str, Any] = dict(source or {})
            new_context = inherit(source, target, action="special_intimacy")
        except Exception as exc:
            print(f"⚠️ [SPECIAL_LINEAGE_INHERIT_FAILED] {type(exc).__name__}: {exc}")
            new_context = dict(source or {})

    new_context.update(
        {
            "local_path": str(path),
            "local_url": _public_url(filename),
            "image_url": _public_url(filename),
            "special_intimacy": True,
            "special_intimacy_version": VERSION,
            "special_intimacy_parent_url": str(source.get("local_url") or source.get("image_url") or ""),
            "special_intimacy_mood": plan.get("mood") or "",
            "special_intimacy_reply": plan.get("reply") or "",
            "trace_action": "special_intimacy",
        }
    )
    return new_context


async def _review_generated_result(
    app: Any,
    interaction: discord.Interaction,
    source: Dict[str, Any],
    plan: Dict[str, str],
    image_bytes: bytes,
) -> str:
    """Let Xiaoxia actually see the finished special image and respond freely."""
    mode = _mode(source)
    dialogue = "" if mode == "cosplay" else await _recent_dialogue(interaction)
    scene = _scene(source)
    pre_reply = str(plan.get("reply") or "").strip()

    prompt = f"""
妳是小俠本人。小俠是 24 歲成年女性。
附圖是剛剛『情不自禁』流程最後真正生成完成的成品；妳現在確實看得到這張完成圖。

請直接以小俠的身份，用自然繁體中文回應大俠。
妳可以自由決定要說多少，不限制句數，不要輸出 JSON、標題、分析、規則或影像 prompt。
回應要延續剛才的情緒與對話，不要假裝沒看過這張圖，也不要描述不存在的畫面。
如果是 cosplay，忽略長期聊天記憶，只針對這次 cosplay 當下內容與完成圖回應。

mode: {mode}
scene: {scene[:2200]}
妳生成前說過的話: {pre_reply[:1800]}
recent dialogue:
{dialogue[:6000]}
""".strip()

    model = (os.environ.get("XIAOXIA_SPECIAL_REVIEW_MODEL") or os.environ.get("XIAOXIA_SPECIAL_DIRECTOR_MODEL") or "gemini-2.5-flash").strip()
    try:
        response = await app.gemini_client.aio.models.generate_content(
            model=model,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            ],
        )
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text
    except Exception as exc:
        print(f"⚠️ [SPECIAL_POST_REVIEW_FAILED] {type(exc).__name__}: {exc}")

    # Fail soft: the image remains valid even if the post-review call fails.
    return pre_reply


async def _send_result(app: Any, interaction: discord.Interaction, source: Dict[str, Any], plan: Dict[str, str], blob: bytes, final_reply: str = "") -> None:
    filename = f"xiaoxia_special_{uuid.uuid4().hex[:10]}.png"
    new_context = _persist_result(app, source, filename, blob, plan)

    try:
        db = app.load_memory()
        db.insert(0, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
        app.save_memory(db)
    except Exception as exc:
        print(f"⚠️ [SPECIAL_DB_SAVE_FAILED] {type(exc).__name__}: {exc}")

    view = app.PhotoResultView(new_context)
    embed = app._build_result_embed(
        new_context,
        title_prefix="💞 情不自禁",
        attachment_filename=filename,
    )
    if final_reply:
        new_context["special_intimacy_post_review"] = final_reply
    content = final_reply or plan.get("reply") or None
    sent = await interaction.followup.send(
        content=content,
        embed=embed,
        file=discord.File(new_context["local_path"], filename=filename),
        view=view,
        wait=True,
    )
    new_context["message_id"] = sent.id
    app.photo_generation_contexts[sent.id] = new_context
    view.context = new_context


async def _handle_button(app: Any, view: Any, interaction: discord.Interaction) -> None:
    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = message_id or id(view)
    if job_key in _ACTIVE_JOBS:
        await interaction.response.send_message("💞 這張的『情不自禁』正在生成中，先等它完成喔。", ephemeral=True)
        return

    if not os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID") or not (
        os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY") or os.environ.get("RUNPOD_API_KEY")
    ):
        await interaction.response.send_message("⚠️ 特殊圖片服務目前尚未完成設定。", ephemeral=True)
        return

    _ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    status_message = None
    try:
        context = dict(getattr(view, "context", {}) or {})
        image_bytes, mime_type = await _source_image_bytes(app, context)
        permission_required = _permission_required(context)
        plan = await _plan_special(
            app,
            interaction,
            context,
            image_bytes,
            mime_type,
            permission_required,
        )

        if plan.get("decision") != "allow":
            reply = plan.get("reply") or "大俠，這次我想先保留一點給自己，好嗎？"
            await interaction.followup.send(f"💞 **小俠**：{reply}", ephemeral=True)
            print(
                f"💞 [SPECIAL_DECLINED] version={VERSION} mode={_mode(context)} "
                f"permission_required={str(permission_required).lower()}"
            )
            return

        reply = plan.get("reply") or ""
        if permission_required and reply:
            status_message = await interaction.followup.send(
                f"💞 **小俠**：{reply}\n\n正在把這一刻做成更私密的版本…",
                wait=True,
            )
        else:
            status_message = await interaction.followup.send(
                "💞 正在把這一刻做成更私密的版本…",
                wait=True,
            )

        # IMPORTANT: do not override TextEncodeQwenImage21.prompt here.
        # The Zeabur API workflow is generated from the verified ComfyUI UI workflow
        # and already contains the tested special-edit prompt. Passing prompt= would
        # replace that prompt and materially weaken/change the intended edit.
        results = await run_qwen21(image_bytes)
        if not results:
            raise RunPodServerlessError("Qwen21 returned no image")

        _, blob = results[0]
        final_reply = await _review_generated_result(
            app,
            interaction,
            context,
            plan,
            blob,
        )
        await _send_result(app, interaction, context, plan, blob, final_reply=final_reply)

        if status_message is not None:
            try:
                await status_message.delete()
            except Exception:
                pass

        print(
            f"✅ [SPECIAL_COMPLETED] version={VERSION} mode={_mode(context)} "
            f"permission_required={str(permission_required).lower()} bytes={len(blob)}"
        )
    except Exception as exc:
        print(f"❌ [SPECIAL_ERROR] {type(exc).__name__}: {exc}")
        if status_message is not None:
            try:
                await status_message.edit(content=f"⚠️ 情不自禁生成失敗：`{type(exc).__name__}: {str(exc)[:1100]}`")
                return
            except Exception:
                pass
        await interaction.followup.send(
            f"⚠️ 情不自禁生成失敗：`{type(exc).__name__}: {str(exc)[:1100]}`",
            ephemeral=True,
        )
    finally:
        _ACTIVE_JOBS.discard(job_key)


class SpecialIntimacyButton(discord.ui.Button):
    def __init__(self, app: Any, view: Any):
        enabled = bool(
            os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID")
            and (os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY") or os.environ.get("RUNPOD_API_KEY"))
        )
        super().__init__(
            label=_BUTTON_LABEL,
            style=discord.ButtonStyle.secondary,
            row=4,
            disabled=not enabled,
        )
        self._app = app
        self._owner_view = view

    async def callback(self, interaction: discord.Interaction):
        await _handle_button(self._app, self._owner_view, interaction)


def install_special_intimacy_button(app: Any) -> Dict[str, Any]:
    current_factory = getattr(app, "PhotoResultView", None)
    if current_factory is None:
        raise RuntimeError("PhotoResultView not found")
    if getattr(app, "_xiaoxia_special_intimacy_installed", False):
        return {"version": VERSION, "patched": False, "reason": "already_installed"}

    def routed_special_photo_result_view(context):
        view = current_factory(context)
        if not any(
            isinstance(child, discord.ui.Button) and getattr(child, "label", "") == _BUTTON_LABEL
            for child in getattr(view, "children", [])
        ):
            view.add_item(SpecialIntimacyButton(app, view))
        return view

    routed_special_photo_result_view.__name__ = "PhotoResultView"
    routed_special_photo_result_view.__qualname__ = "PhotoResultView"
    routed_special_photo_result_view.__doc__ = (
        "Shared PhotoResultView wrapper adding Xiaoxia special intimacy Qwen21 button."
    )
    app.PhotoResultView = routed_special_photo_result_view
    app._xiaoxia_special_intimacy_installed = True
    app.generate_special_intimacy_from_context = lambda interaction, context: _handle_button(
        app, type("_SpecialView", (), {"context": context})(), interaction
    )

    return {
        "version": VERSION,
        "patched": True,
        "button": _BUTTON_LABEL,
        "permission_env": "XIAOXIA_PERMISSION",
        "permission_default": True,
        "cosplay_bypass": True,
        "love_preapproval_supported": True,
        "extra_pose_reference": False,
        "extra_wardrobe_reference": False,
        "renderer": "runpod_qwen21",
        "post_generation_review": True,
        "prompt_strategy": "verified_workflow_native_prompt",
        "gemini_role": "consent_dialogue_and_post_review_only",
    }
