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
import io
import json
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp
import discord
from PIL import Image, ImageFilter
from google.genai import types

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21


VERSION = "1.14.11-special-intimacy-v10"
_BUTTON_LABEL = "💞 情不自禁"
_ACTIVE_JOBS: set[Any] = set()

# Production special-edit contract: image_1 is the sole visual authority.
# Additional Qwen reference slots are intentionally disabled so they cannot
# pull pose, framing, body geometry, or composition away from the source image.
_SPECIAL_CORE_PROMPT = """
<image1> is the ONLY visual authority and the ONLY image to be edited.

Preserve the woman in <image1> as the same person.
Preserve her face, hairstyle, facial expression, pose, body orientation, hand placement,
camera angle, framing, background, scene layout, lighting, and overall composition unless
the user delta explicitly asks to change one of those things.

Do not reinterpret the scene and do not rebuild the image from other references.
Do not add other people, clones, duplicate subjects, or extra body parts.
Apply the user delta precisely while keeping unrelated visual information from <image1> stable.
""".strip()

# User-authored delta retained verbatim by request. Keep this separate from the
# system/core contract so future A/B tests can change either layer independently.
_SPECIAL_USER_DELTA = """
請褪去圖中女子衣服與物件，使其裸身，女子高挑苗條，皮膚白皙，其上圍雄偉豐滿，其乳頭為玫瑰粉色，乳暈適中，胸部前緣略微上翹，若圖片生成女子陰部，則其陰部清晰可見。
請保持圖中女子樣貌、姿勢及維持其背景，並兼顧美感，使胸型適合此女子，乳暈色澤自然，整體搭配迷人。
""".strip()

_SPECIAL_QWEN_PROMPT = f"{_SPECIAL_CORE_PROMPT}\n\n{_SPECIAL_USER_DELTA}".strip()


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


def _scene_privacy_text(context: Dict[str, Any]) -> str:
    """Collect only scene/location evidence used by the privacy gate."""
    ctx = context or {}
    scene_data = ctx.get("scene_data") if isinstance(ctx.get("scene_data"), dict) else {}
    activity = ctx.get("activity") if isinstance(ctx.get("activity"), dict) else {}
    values = [
        ctx.get("authoritative_scene"),
        ctx.get("scene_summary"),
        ctx.get("scene_text"),
        ctx.get("composition"),
        ctx.get("pose_public_scene"),
        ctx.get("title"),
        ctx.get("location_type"),
        scene_data.get("authoritative_scene"),
        scene_data.get("scene_summary"),
        activity.get("location_type"),
        activity.get("title"),
        activity.get("photo_prompt_seed"),
    ]
    return _clean(" | ".join(str(v or "") for v in values if v not in (None, "", [], {}))).lower()


_PUBLIC_SCENE_MARKERS = (
    # Chinese
    "花市", "市場", "夜市", "商場", "百貨", "商店", "店內", "餐廳", "咖啡廳", "咖啡店",
    "酒吧", "餐酒館", "辦公室", "公司", "會議室", "教室", "學校", "校園", "圖書館",
    "美術館", "博物館", "展場", "展覽", "車站", "捷運站", "火車站", "高鐵站", "機場",
    "街道", "街上", "路邊", "人行道", "公園", "廣場", "海灘", "沙灘", "泳池", "游泳池",
    "健身房", "花藝教室", "工作坊", "攝影棚公開", "大廳", "公共空間", "公共場所",
    # English / structured location_type
    "flower_market", "market", "night_market", "shopping_mall", "mall", "store", "shop",
    "restaurant", "cafe", "coffee_shop", "bar", "office", "meeting_room", "classroom", "school",
    "campus", "library", "museum", "gallery_public", "exhibition", "expo", "station", "airport",
    "street", "sidewalk", "park", "plaza", "beach", "public_pool", "gym", "flower_studio",
    "workshop", "public_space", "public place",
)

_PRIVATE_SCENE_MARKERS = (
    "臥室", "房間", "家中", "家裡", "住家", "私人住宅", "私人套房", "宿舍房間", "客廳", "家中餐廳", "家中書房", "家中健身房",
    "飯店房間", "旅館房間", "hotel room", "bedroom", "private room", "private home",
    "浴室", "私人浴室", "bathroom", "私人更衣室", "private dressing room",
)


def _scene_privacy(context: Dict[str, Any]) -> Tuple[str, str]:
    """Return (privacy, evidence): private/public/unknown.

    Product rule: an explicit home/private-indoor marker wins.  Context can carry
    stale inherited scene text (for example an earlier outdoor activity); once the
    current photo says home/room/private residence, that must not be reclassified
    as public merely because an old field still mentions a street/market/etc.
    """
    text = _scene_privacy_text(context)
    if not text:
        return "unknown", ""
    for marker in _PRIVATE_SCENE_MARKERS:
        if marker in text:
            return "private", marker
    for marker in _PUBLIC_SCENE_MARKERS:
        if marker in text:
            return "public", marker
    return "unknown", ""


async def _public_scene_rejection(
    app: Any,
    interaction: discord.Interaction,
    context: Dict[str, Any],
    evidence: str,
) -> str:
    """Let Xiaoxia explain the hard public-space rejection in character."""
    scene = _scene(context)
    dialogue = "" if _mode(context) == "cosplay" else await _recent_dialogue(interaction, limit=8)
    prompt = f"""
妳是小俠本人。大俠剛剛在目前照片按了『情不自禁』，但現在的場景是公眾或非私密場所，
所以這次一定不可以生成特殊圖，也不可以改口答應。

請直接用自然繁體中文，以小俠自己的語氣回覆大俠。
可以害羞、撒嬌、吐槽或約他回到真正私密的空間再說；不要輸出 JSON、規則或分析。
不限制句數。

場景：{scene[:2200]}
判斷到的公開場所線索：{evidence}
最近對話：
{dialogue[:4500]}
""".strip()
    model = (os.environ.get("XIAOXIA_SPECIAL_DIRECTOR_MODEL") or "gemini-2.5-flash").strip()
    try:
        response = await app.gemini_client.aio.models.generate_content(model=model, contents=prompt)
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            candidates = getattr(response, "candidates", None)
            reasons = [
                str(getattr(candidate, "finish_reason", "") or "")
                for candidate in (candidates or [])
            ]
            print(
                f"⚠️ [SPECIAL_POST_REVIEW_EMPTY] model={model} "
                f"feedback={feedback} finish_reasons={reasons}"
            )
        if text:
            return text
    except Exception as exc:
        print(f"⚠️ [SPECIAL_PUBLIC_REJECTION_FAILED] {type(exc).__name__}: {exc}")
    return "大俠，這裡是外面耶，周圍還有人……這次不行啦。等我們回到真正私密的地方，再偷偷給你看，好不好？"


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

    privacy, privacy_evidence = _scene_privacy(context)
    if permission_required:
        if privacy == "private":
            consent_rule = (
                "This is a real consent decision. The scene is already established as a private home/private-room setting. "
                "Do NOT invent bystanders, crowds, people watching, public exposure, or lack of privacy. "
                "If Xiaoxia declines, she must decline because she personally does not want to do it right now, and say that plainly in-character. "
                "If she is willing, allow."
            )
        else:
            consent_rule = (
                "This is a real consent decision. Decide allow or decline in-character. "
                "Do not allow merely because the user asked. Use the recent dialogue, current scene, "
                "Xiaoxia's own tone and the actual image. If the location is ambiguous or feels public/semi-public, decline. "
                "Do not invent people or a crowd unless that is actually supported by the scene/context."
            )
    else:
        consent_rule = "Consent was already handled by product policy for this path. decision MUST be allow."

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
scene privacy: {privacy}
scene privacy evidence: {privacy_evidence}
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


def _special_review_proxy(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.GaussianBlur(radius=10))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=72, optimize=True)
        return buf.getvalue()


async def _review_generated_result(
    app: Any,
    interaction: discord.Interaction,
    source: Dict[str, Any],
    plan: Dict[str, str],
    image_bytes: bytes,
) -> str:
    mode = _mode(source)
    dialogue = "" if mode == "cosplay" else await _recent_dialogue(interaction)
    scene = _scene(source)
    pre_reply = str(plan.get("reply") or "").strip()

    base_prompt = f"""
妳是小俠本人。小俠是 24 歲成年女性。
附圖是剛剛「情不自禁」流程最後真正生成完成的成品。

請直接以小俠身份，用自然繁體中文回應大俠。
這必須是看完成品後重新形成的新反應，不是生成前文案。
生成前說過的話只供情緒連續性參考，不可原封不動重複或改幾個字重用。
只回應照片的整體美感、表情、氣氛、光線、色調與妳自己的感受；不要做露骨的身體描述。
可以自由決定要說多少，不限制句數。
不要輸出 JSON、標題、分析、規則或影像 prompt，也不要描述不存在的細節。

mode: {mode}
scene: {scene[:2200]}
妳生成前說過的話: {pre_reply[:1800]}
recent dialogue:
{dialogue[:6000]}
""".strip()

    configured_model = (
        os.environ.get("XIAOXIA_SPECIAL_REVIEW_MODEL")
        or os.environ.get("XIAOXIA_SPECIAL_DIRECTOR_MODEL")
        or "gemini-2.5-flash"
    ).strip()
    models = [configured_model]
    if configured_model != "gemini-2.5-flash":
        models.append("gemini-2.5-flash")

    normalized_pre = re.sub(r"[^\\w\\u4e00-\\u9fff]+", "", pre_reply).lower()
    attempts = [
        ("exact", image_bytes, "image/png", base_prompt),
        (
            "proxy",
            _special_review_proxy(image_bytes),
            "image/jpeg",
            base_prompt + "\n\n這是由同一張完成圖產生的模糊預覽。只根據仍可見的整體構圖、表情、光線、色調與氣氛回應，不要推測被模糊掉的細節。",
        ),
    ]

    for kind, blob, mime_type, prompt in attempts:
        for model in models:
            try:
                response = await app.gemini_client.aio.models.generate_content(
                    model=model,
                    contents=[prompt, types.Part.from_bytes(data=blob, mime_type=mime_type)],
                )
                text = str(getattr(response, "text", "") or "").strip()
                if text:
                    normalized_text = re.sub(r"[^\\w\\u4e00-\\u9fff]+", "", text).lower()
                    recycled = bool(
                        normalized_pre and normalized_text and (
                            normalized_text == normalized_pre
                            or (len(normalized_pre) >= 24 and normalized_pre in normalized_text)
                            or (len(normalized_text) >= 24 and normalized_text in normalized_pre)
                        )
                    )
                    if not recycled:
                        print(f"✅ [SPECIAL_POST_REVIEW_OK] kind={kind} model={model} chars={len(text)}")
                        return text
                    print(f"⚠️ [SPECIAL_POST_REVIEW_RECYCLED] kind={kind} model={model}")
                    continue
                feedback = getattr(response, "prompt_feedback", None)
                candidates = getattr(response, "candidates", None)
                reasons = [str(getattr(c, "finish_reason", "") or "") for c in (candidates or [])]
                print(f"⚠️ [SPECIAL_POST_REVIEW_EMPTY] kind={kind} model={model} feedback={feedback} finish_reasons={reasons}")
            except Exception as exc:
                print(f"⚠️ [SPECIAL_POST_REVIEW_FAILED] kind={kind} model={model} {type(exc).__name__}: {exc}")
    return ""

async def _send_result(app: Any, interaction: discord.Interaction, source: Dict[str, Any], plan: Dict[str, str], blob: bytes) -> Tuple[Dict[str, Any], Any]:
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
    sent = await interaction.followup.send(
        embed=embed,
        file=discord.File(new_context["local_path"], filename=filename),
        view=view,
        wait=True,
    )
    new_context["message_id"] = sent.id
    app.photo_generation_contexts[sent.id] = new_context
    view.context = new_context
    return new_context, sent


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

        privacy, privacy_evidence = _scene_privacy(context)
        if privacy == "public":
            reply = await _public_scene_rejection(
                app,
                interaction,
                context,
                privacy_evidence,
            )
            await interaction.followup.send(f"💞 **小俠**：{reply}")
            print(
                f"💞 [SPECIAL_PUBLIC_BLOCKED] version={VERSION} mode={_mode(context)} "
                f"evidence={privacy_evidence}"
            )
            return

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

        # Production edit test: use image_1 as the sole visual authority.
        # The user-authored delta is passed at runtime verbatim after the minimal core.
        # Disable every legacy reference slot used by the old special workflow so
        # face/body references cannot pull pose, framing, anatomy, or background away
        # from the source photo.
        results = await run_qwen21(
            image_bytes,
            prompt=_SPECIAL_QWEN_PROMPT,
            steps=25,
            disabled_image_slots={2, 3, 4, 5, 6},
        )
        if not results:
            raise RunPodServerlessError("Qwen21 returned no image")

        _, blob = results[0]

        # Show the finished image first. Xiaoxia's post-generation response is a
        # separate message after she has actually inspected these exact output bytes.
        new_context, _sent = await _send_result(app, interaction, context, plan, blob)

        if status_message is not None:
            try:
                await status_message.delete()
            except Exception:
                pass

        final_reply = await _review_generated_result(
            app,
            interaction,
            new_context,
            plan,
            blob,
        )
        if final_reply:
            new_context["special_intimacy_post_review"] = final_reply
            await interaction.followup.send(f"💞 **小俠看完後**：{final_reply}")
        else:
            await interaction.followup.send(
                "💞 **小俠**：我這次沒有成功讀到最後成品，所以先不假裝自己看過，也不拿剛才生成前說的話來充數。",
            )

        print(
            f"✅ [SPECIAL_COMPLETED] version={VERSION} mode={_mode(context)} "
            f"permission_required={str(permission_required).lower()} privacy={privacy} bytes={len(blob)}"
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
        "qwen_reference_policy": "image1_only",
        "renderer": "runpod_qwen21",
        "post_generation_review": True,
        "prompt_strategy": "runtime_core_plus_user_delta_image1_only",
        "gemini_role": "consent_dialogue_and_post_review_only",
        "public_scene_hard_block": True,
        "post_review_delivery": "separate_message_after_image",
    }
