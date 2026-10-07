# -*- coding: utf-8 -*-
"""Qwen Image 2.1 reference-scene mode for /photo."""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import uuid
from typing import Any, Dict
from types import SimpleNamespace
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from PIL import Image

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21_reference_scene
from xiaoxia.photo.special_intimacy import _SPECIAL_USER_DELTA as _DEFAULT_SPECIAL_DELTA

VERSION = "1.8.1-qwen-photo-scene-v16-love-trace"

LOVE_TRACE_PATH = Path("/data/memory/qwen21/meta/latest_love_scene.json")


def _write_love_trace(payload: Dict[str, Any]) -> None:
    LOVE_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOVE_TRACE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, LOVE_TRACE_PATH)


_REF_FILES = {
    "face_front": "image_2_face_front.png",
    "face_45": "image_3_face_45.png",
    "body_full": "image_4_body_full.png",
    "body_half": "image_5_body_half.png",
    "body_clothed": "image_6_body_clothed.png",
}

_QWEN_SCENE_CORE = """QWEN IMAGE 2.1 — 多參考圖新場景生成（無既有畫布）

三張輸入圖都是同一位成年女性的人物一致性參考來源，沒有任何一張是要被直接編修的原始畫布。

參考圖角色：
- <image1>：全身人物一致性與整體身材比例參考。
- <image2>：正面臉部人物一致性參考。
- <image3>：45 度臉部人物一致性參考。

依照後面的重寫提示詞生成一個全新的場景與構圖。
保留三張參考圖所代表的同一人物身分與整體外觀一致性。
場景、穿著或人物狀態、動作與姿勢、表情、鏡頭方向、取景範圍、光線與整體氣氛，
都以後面的重寫提示詞為準；不要沿用任何參考圖原本的背景、姿勢、服裝或構圖。

最終畫面只出現一位人物，人體結構自然且完整，維持正常的兩隻手臂與兩條腿，
避免重複肢體、額外手腳、肢體融合或其他明顯人體結構錯誤。

參考圖負責人物一致性；重寫提示詞負責新的場景與構圖。
""".strip()


_QWEN_LOVE_SINGLE_REF_CORE = """QWEN IMAGE 2.1 — 小俠愛意單一人物參考新場景生成

這是全新的場景生成，不是既有圖片編修。

參考圖角色：
- <image1>：唯一的小俠人物參考圖。它提供同一位成年女性的臉部身分、全身比例與整體外觀一致性。
- 若存在 <image2>：它是純服飾參考圖，只提供服裝款式、材質、顏色與剪裁；它不是人物參考。

生成規則：
- 最終畫面只出現一位小俠。
- 不要生成第二位、第三位、背景副本、重疊人物、被遮住的另一位人物、局部人物或鏡中分身。
- 不要把參考圖拆解成多個版本的小俠，也不要同時生成不同穿著版本的小俠。
- <image1> 只負責人物身分與整體外觀一致性；後面的愛意提示詞負責場景、動作、表情、鏡頭與氣氛。
- 若存在 <image2>，請讓唯一的小俠穿著 <image2> 的服裝；不要沿用 <image1> 原本的衣服。
- 不要沿用參考圖原本的背景、姿勢或構圖。
- 人體結構自然且完整，維持正常兩隻手臂與兩條腿，避免重複肢體、額外手腳、肢體融合或其他明顯人體結構錯誤。
""".strip()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()



def _extract_json(text: str) -> dict:
    raw = str(text or "").strip()
    raw = re.sub(r"^~~~(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*~~~$", "", raw)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


async def _compile_scene_with_gemini(
    app: Any,
    *,
    scene_delta: str,
    subject_delta: str,
    camera_delta: str,
    mood_delta: str,
) -> dict:
    prompt = f"""
你是 Qwen-Image-2.1 的 prompt rewrite 階段。這是「多張 reference、沒有 canvas、重新生成新場景」任務。

三張 reference 都是同一位成年女性的 identity source：
<image1> 全身 identity／整體身材比例
<image2> 正面臉部 identity
<image3> 45 度臉部 identity

使用者原始要求：
【場景／環境】
{scene_delta}

【人物動作／表情／劇情／穿著狀態】
{subject_delta}

【鏡頭／構圖】
{camera_delta}

【整體氣氛】
{mood_delta}

請依 Qwen-Image-2.1 官方 scene-generation/no-canvas rewrite 原則，只回傳 JSON：
{{
  "rewritten_prompt": "一個完整、連續、沒有換行的繁體中文提示詞。逐一引用 <image1>、<image2>、<image3> 作為人物一致性參考來源；完整保留使用者指定的場景、人物狀態/穿著、動作姿勢、表情、鏡頭構圖與氣氛。不要把任何參考圖當成既有畫布，不要改寫成沿用參考圖原本的姿勢、背景或服裝。不要加入使用者未要求的狀態。",
  "wh_ratio": "輸出比例，例如 3:4、2:3、3:2、16:9；若使用者未明講比例，依官方 no-canvas scene semantics 決定。",
  "ratio_follow": "",
  "scene_summary": "繁體中文，40字內",
  "camera_summary": "繁體中文，30字內",
  "mood_summary": "繁體中文，30字內"
}}

規則：
1. 這是 no-canvas scene generation；ratio_follow 必須為空字串。
2. 若是 full-body scene，預設 wh_ratio=3:4；portrait/half-body 預設 2:3；landscape-oriented scene 預設 3:2。若使用者明確指定比例，使用指定比例。
3. rewritten_prompt 必須使用繁體中文，且為一個完整連續段落，不含比例資訊。
4. identity 直接以 <image1>、<image2>、<image3> 指向來源，不用額外發明人物外貌描述。
5. 使用者明確指定的 clothing/state、pose/action、location、camera/framing 不得被省略或改成別的內容。
6. 使用肯定、明確的敘述，不用堆疊反向 negative constraints。
""".strip()

    resp = await app.gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=app.types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    data = _extract_json(getattr(resp, "text", ""))
    rewritten = _clean(data.get("rewritten_prompt"))
    if not rewritten:
        rewritten = _clean(
            f"將 <image1>、<image2>、<image3> 僅作為同一位成年女性的人物一致性參考來源，"
            f"生成一個全新的場景。場景／環境：{scene_delta}。人物動作／表情／劇情／穿著狀態：{subject_delta}。"
            f"鏡頭／構圖：{camera_delta}。整體氣氛：{mood_delta}。"
        )

    wh_ratio = _clean(data.get("wh_ratio") or "3:4")
    ratio_follow = _clean(data.get("ratio_follow") or "")
    if ratio_follow:
        ratio_follow = ""

    return {
        "rewritten_prompt": rewritten,
        "wh_ratio": wh_ratio,
        "ratio_follow": "",
        "scene_summary": _clean(data.get("scene_summary") or scene_delta)[:80],
        "camera_summary": _clean(data.get("camera_summary") or camera_delta)[:60],
        "mood_summary": _clean(data.get("mood_summary") or mood_delta)[:60],
    }


def _build_qwen_prompt(rewritten_prompt: str, special_delta: str = "") -> str:
    parts = [
        _QWEN_SCENE_CORE,
        str(rewritten_prompt or "").strip(),
    ]
    special = str(special_delta or "").strip()
    if special:
        parts.append(special)
    return _clean("\n\n".join(parts))


def _build_direct_qwen_prompt(prompt_text: str, *, has_outfit_ref: bool = False) -> str:
    """Build the Love Intent Qwen prompt.

    Love Intent intentionally uses a single Xiaoxia identity reference:
    <image1> = full-body identity
    <image2> = optional pure-clothing authority
    """
    parts = [_QWEN_LOVE_SINGLE_REF_CORE, str(prompt_text or "").strip()]
    if has_outfit_ref:
        parts.append(
            "<image2> 是純服飾參考圖。請讓唯一的小俠穿著 <image2> 的服裝，"
            "只取其服裝款式、材質、顏色與剪裁；不可把 <image2> 解讀成第二位人物。"
        )
    return _clean("\n\n".join(x for x in parts if str(x or "").strip()))


async def _outfit_reference_png_bytes(app: Any, wardrobe_item: dict | None) -> bytes | None:
    if not isinstance(wardrobe_item, dict):
        return None

    candidates = []
    local_path = str(wardrobe_item.get("reference_image_path") or "").strip()
    if local_path:
        candidates.append(local_path)

    ref_url = str(
        wardrobe_item.get("local_url")
        or wardrobe_item.get("reference_item_url")
        or ""
    ).strip()

    mapper = getattr(app, "_gallery_url_to_local_path", None)
    if ref_url and callable(mapper):
        try:
            mapped = mapper(ref_url)
        except Exception:
            mapped = None
        if mapped:
            candidates.append(str(mapped))

    raw = None
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            with open(candidate, "rb") as fh:
                raw = fh.read()
            if raw:
                break

    if raw is None and ref_url.startswith(("http://", "https://")):
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(ref_url) as response:
                if response.status == 200:
                    raw = await response.read()

    if not raw:
        return None

    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGBA")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()


async def generate_qwen_scene_from_prompt(
    app: Any,
    *,
    prompt_text: str,
    source_context: dict | None = None,
    wardrobe_item: dict | None = None,
    wh_ratio: str = "3:4",
) -> dict:
    """Generate a Qwen reference scene from an already-authored prompt.

    This path deliberately skips Gemini rewrite and special_delta. It is used by
    flows that already own their prompt semantics, such as Love Intent fallback.
    Love Intent uses exactly one Xiaoxia identity ref (clothed master), plus an
    optional pure-clothing ref.
    """
    source = dict(source_context or {})
    outfit_bytes = await _outfit_reference_png_bytes(app, wardrobe_item)
    prompt = _build_direct_qwen_prompt(
        prompt_text,
        has_outfit_ref=bool(outfit_bytes),
    )

    wardrobe_id = str((wardrobe_item or {}).get("id") or source.get("wardrobe_id") or "").strip().upper()
    wardrobe_name = str((wardrobe_item or {}).get("name") or source.get("wardrobe_name") or "").strip()
    seed = secrets.randbelow(2**63 - 1)

    trace = {
        "mode": "love_intent_qwen_reference_scene",
        "status": "starting",
        "trace_version": VERSION,
        "created_at": app.datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": source.get("source_mode") or "love_intent",
        "title": source.get("title") or source.get("photo_name") or "",
        "scene_summary": source.get("scene_summary") or "",
        "action_summary": source.get("action_summary") or "",
        "mood_summary": source.get("mood_summary") or source.get("mood") or "",
        "wardrobe_id": wardrobe_id,
        "wardrobe_name": wardrobe_name,
        "outfit_ref_used": bool(outfit_bytes),
        "original_prompt": str(prompt_text or "").strip(),
        "final_qwen_prompt": prompt,
        "reference_slots_expected": {
            "image1": _REF_FILES["body_clothed"],
            "image2": "wardrobe_pure_clothing_ref" if outfit_bytes else None,
        },
        "reference_set_expected": [
            _REF_FILES["body_clothed"],
        ] + (["wardrobe_pure_clothing_ref"] if outfit_bytes else []),
        "reference_mode_expected": "single_identity_ref_plus_optional_outfit",
        "scene_workflow_mode_expected": "love_single_identity_ref_plus_optional_outfit_v1",
        "scene_workflow_file_expected": "xiaoxia/serverless/workflows/qwen21_reference_scene_api.json",
        "steps_expected": 25,
        "wh_ratio_expected": wh_ratio or "3:4",
        "seed": seed,
        "special_delta": "",
        "prompt_rewrite": False,
    }
    _write_love_trace(trace)

    try:
        results = await run_qwen21_reference_scene(
            prompt=prompt,
            seed=seed,
            steps=25,
            wh_ratio=wh_ratio or "3:4",
            outfit_image_bytes=outfit_bytes,
            reference_mode="single_identity_ref",
        )
    except Exception as exc:
        trace["status"] = "failed"
        trace["failed_at"] = app.datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
        trace["error"] = f"{type(exc).__name__}: {exc}"
        _write_love_trace(trace)
        raise

    if not results:
        trace["status"] = "failed"
        trace["failed_at"] = app.datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
        trace["error"] = "RunPodServerlessError: Qwen scene generation returned no image"
        _write_love_trace(trace)
        raise RunPodServerlessError("Qwen scene generation returned no image")

    _, blob = results[0]
    filename = f"qwen_love_scene_{uuid.uuid4().hex[:12]}.png"
    os.makedirs(app.OUTPUT_DIR, exist_ok=True)
    local_path = os.path.join(app.OUTPUT_DIR, filename)
    with open(local_path, "wb") as fh:
        fh.write(blob)
    local_url = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"

    result = dict(source)
    inherit = getattr(app, "_inherit_photo_lineage", None)
    if callable(inherit):
        try:
            result = inherit(source, result, action="love_qwen_fallback")
        except Exception:
            result = dict(source)

    result.update({
        "id": str(uuid.uuid4()),
        "image_url": local_url,
        "local_url": local_url,
        "local_filename": filename,
        "local_path": local_path,
        "type": source.get("type") or "photo",
        "db_type": source.get("db_type") or "photo",
        "source_mode": "love_intent",
        "source_module": "love_intent",
        "image_role": "qwen_love_fallback",
        "generation_level": "QWEN_LOVE_FALLBACK",
        "final_level": "QWEN_LOVE_FALLBACK",
        "qwen_model_label": "Qwen-Image-2.1",
        "qwen_seed": seed,
        "qwen_steps": 25,
        "qwen_reference_set": [
            _REF_FILES["body_clothed"],
        ] + (["wardrobe_pure_clothing_ref"] if outfit_bytes else []),
        "qwen_reference_mode": "single_identity_ref_plus_optional_outfit",
        "qwen_scene_workflow_mode": "love_single_identity_ref_plus_optional_outfit_v1",
        "qwen_scene_workflow_file": "xiaoxia/serverless/workflows/qwen21_reference_scene_api.json",
        "qwen_wh_ratio": wh_ratio or "3:4",
        "qwen_final_prompt": prompt,
        "qwen_compiled_scene_prompt": str(prompt_text or "").strip(),
        "qwen_special_delta": "",
        "wardrobe_id": wardrobe_id or source.get("wardrobe_id"),
        "wardrobe_name": wardrobe_name or source.get("wardrobe_name"),
        "love_qwen_outfit_ref_used": bool(outfit_bytes),
        "love_qwen_prompt_rewrite": False,
    })

    trace.update({
        "status": "completed",
        "completed_at": app.datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "result_url": local_url,
        "result_filename": filename,
        "reference_set": result.get("qwen_reference_set"),
        "reference_mode": result.get("qwen_reference_mode"),
        "scene_workflow_mode": result.get("qwen_scene_workflow_mode"),
        "scene_workflow_file": result.get("qwen_scene_workflow_file"),
        "wh_ratio": result.get("qwen_wh_ratio"),
        "steps": result.get("qwen_steps"),
        "love_qwen_outfit_ref_used": result.get("love_qwen_outfit_ref_used"),
        "compiled_scene_prompt": result.get("qwen_compiled_scene_prompt"),
        "final_qwen_prompt": result.get("qwen_final_prompt"),
    })
    _write_love_trace(trace)
    result["qwen_love_scene_trace_path"] = str(LOVE_TRACE_PATH)
    return result


async def _generate_qwen_scene(app: Any, *, scene_delta: str, subject_delta: str, camera_delta: str, mood_delta: str, special_delta: str = "") -> dict:
    scene = await _compile_scene_with_gemini(
        app,
        scene_delta=scene_delta,
        subject_delta=subject_delta,
        camera_delta=camera_delta,
        mood_delta=mood_delta,
    )
    prompt = _build_qwen_prompt(scene["rewritten_prompt"], special_delta=special_delta)

    # Dedicated reference-scene workflow: all five refs are staged on the
    # RunPod worker and feed Qwen's multi-reference conditioning. No edit image
    # and no per-request reference upload are used in this path.
    seed = secrets.randbelow(2**63 - 1)
    results = await run_qwen21_reference_scene(
        prompt=prompt,
        seed=seed,
        steps=25,
        wh_ratio=scene["wh_ratio"],
    )
    if not results:
        raise RunPodServerlessError("Qwen scene generation returned no image")

    _, blob = results[0]
    filename = f"qwen_photo_scene_{uuid.uuid4().hex[:12]}.png"
    os.makedirs(app.OUTPUT_DIR, exist_ok=True)
    local_path = os.path.join(app.OUTPUT_DIR, filename)
    with open(local_path, "wb") as f:
        f.write(blob)
    local_url = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"

    now_text = app.datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "id": str(uuid.uuid4()),
        "publish_date": now_text,
        "created_at": now_text,
        "topic": "【Photo】Qwen 特殊場景",
        "event": "大俠使用 /photo 的 Qwen-2.1 模式生成一張特殊場景照片。",
        "composition": scene["scene_summary"] or scene_delta,
        "authoritative_scene": scene["rewritten_prompt"],
        "root_prompt_base": scene["rewritten_prompt"],
        "scene_text": scene["scene_summary"] or scene_delta,
        "scene_summary": scene["scene_summary"] or scene_delta,
        "action_summary": _clean(subject_delta)[:120],
        "camera_summary": scene["camera_summary"],
        "mood": scene["mood_summary"] or mood_delta,
        "mood_summary": scene["mood_summary"] or mood_delta,
        "outfit_summary": "Qwen 特殊場景",
        "message": "大俠用 Qwen-2.1 特殊場景模式留下這一刻。",
        "image_url": local_url,
        "local_url": local_url,
        "local_filename": filename,
        "local_path": local_path,
        "type": "photo",
        "db_type": "photo",
        "source_mode": "photo_qwen_special",
        "source_module": "photo_qwen_special",
        "gallery_category": "portrait",
        "image_role": "qwen_reference_scene_generation",
        "generation_level": "QWEN_SPECIAL",
        "final_level": "QWEN_SPECIAL",
        "seedream_model_label": "Qwen-Image-2.1",
        "qwen_model_label": "Qwen-Image-2.1",
        "qwen_seed": seed,
        "qwen_steps": 25,
        "qwen_reference_set": [
            _REF_FILES["body_full"],
            _REF_FILES["face_front"],
            _REF_FILES["face_45"],
        ],
        "qwen_reference_mode": "official_multiref_with_vae_reference_latents",
        "qwen_scene_workflow_mode": "dedicated_three_ref_no_canvas_ab_v1",
        "qwen_scene_workflow_file": "xiaoxia/serverless/workflows/qwen21_reference_scene_api.json",
        "qwen_wh_ratio": scene["wh_ratio"],
        "qwen_ratio_follow": scene["ratio_follow"],
        "qwen_final_prompt": prompt,
        "qwen_scene_delta": scene_delta,
        "qwen_subject_delta": subject_delta,
        "qwen_camera_delta": camera_delta,
        "qwen_mood_delta": mood_delta,
        "qwen_special_delta": str(special_delta or "").strip(),
        "qwen_compiled_scene_prompt": scene["rewritten_prompt"],
    }


class _PhotoBrainMessage:
    """Minimal Discord-message proxy that re-enters Xiaoxia's normal chat brain.

    Native /photo interactions do not create a normal user Message event.  Calling
    the Seedream generator directly therefore skips the legacy on_message
    continuation that lets Xiaoxia actually see the finished photo and react to it.
    This proxy carries the small Message surface that the girlfriend on_message path
    expects, so the generated image and the follow-up response stay on the same path
    as the original text /photo command.
    """

    def __init__(self, source_message: Any, content: str):
        self.content = str(content or "")
        self.author = getattr(source_message, "author", None)
        self.channel = getattr(source_message, "channel", None)
        self.guild = getattr(source_message, "guild", None) or getattr(self.channel, "guild", None)
        self.id = getattr(source_message, "id", None) or uuid.uuid4().int >> 64
        self.attachments = list(getattr(source_message, "attachments", []) or [])
        self.mentions = []
        self.role_mentions = []
        self.channel_mentions = []
        self.stickers = []

    async def reply(self, content=None, **kwargs):
        kwargs.pop("mention_author", None)
        return await self.channel.send(content, **kwargs)


async def _dispatch_seedream_through_xiaoxia_brain(app: Any, source_message: Any, scene_text: str) -> None:
    """Run Seedream /photo through the normal girlfriend on_message continuation."""
    content = "/photo " + str(scene_text or "").strip()
    proxy = _PhotoBrainMessage(source_message, content)
    handler = getattr(app.girlfriend_bot, "on_message", None)
    if not callable(handler):
        raise RuntimeError("girlfriend on_message handler not available")
    await handler(proxy)


class _SeedreamPhotoModal(discord.ui.Modal):
    def __init__(self, app: Any, original_handler: Any, source_message: Any):
        super().__init__(title="Photo｜Seedream v4.5")
        self.app = app
        self.original_handler = original_handler
        self.source_message = source_message
        self.scene = discord.ui.TextInput(
            label="想拍什麼？",
            style=discord.TextStyle.paragraph,
            default="在家中廚房做早餐，穿著今天的居家服，回頭看鏡頭。",
            max_length=1200,
            required=True,
        )
        self.add_item(self.scene)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            # Important: do not call the generator directly here.  Re-enter the
            # normal Xiaoxia on_message path so the finished photo is attached to
            # her vision turn and she can naturally react / continue the interaction.
            await _dispatch_seedream_through_xiaoxia_brain(
                self.app,
                self.source_message,
                str(self.scene.value or "").strip(),
            )
            await interaction.followup.send("✅ Seedream v4.5 已完成，小俠也看過照片了。", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(
                f"⚠️ Seedream /photo 失敗：{type(exc).__name__}: {str(exc)[:1200]}", ephemeral=True
            )


class _QwenPhotoModal(discord.ui.Modal):
    def __init__(self, app: Any, source_message: Any, initial_scene: str = ""):
        super().__init__(title="Photo｜Qwen-2.1 特殊圖", timeout=900)
        self.app = app
        self.source_message = source_message

        self.scene_delta = discord.ui.TextInput(
            label="場景／環境",
            style=discord.TextStyle.paragraph,
            default=initial_scene or "在家中臥室，夜晚，背景簡潔自然，保留真實生活感。",
            max_length=1000,
            required=True,
        )
        self.subject_delta = discord.ui.TextInput(
            label="人物動作／表情／劇情",
            style=discord.TextStyle.paragraph,
            default="小俠自然地面向鏡頭，依照我描述的劇情演出，表情真實、不僵硬。",
            max_length=1500,
            required=True,
        )
        self.camera_delta = discord.ui.TextInput(
            label="想怎麼拍",
            style=discord.TextStyle.paragraph,
            default="希望人物是畫面主體，能看清楚主要動作；鏡頭自然，不要誇張透視。",
            max_length=800,
            required=True,
        )
        self.mood_delta = discord.ui.TextInput(
            label="整體氣氛",
            style=discord.TextStyle.paragraph,
            default="自然、寫實、私密生活感，光線柔和，不要像棚拍。",
            max_length=800,
            required=True,
        )
        self.special_delta = discord.ui.TextInput(
            label="特別要求（可清空）",
            style=discord.TextStyle.paragraph,
            default=(
                "女子高挑苗條，皮膚白皙，其上圍雄偉豐滿，其乳頭為玫瑰粉色，乳暈適中，"
                "胸部前緣略微上翹，並兼顧美感，使胸型適合此女子，乳暈色澤自然，整體搭配迷人。"
                "若圖片生成女子陰部，則其陰部為玫瑰粉色且清晰可見。"
            ),
            max_length=1800,
            required=False,
        )
        self.add_item(self.scene_delta)
        self.add_item(self.subject_delta)
        self.add_item(self.camera_delta)
        self.add_item(self.mood_delta)
        self.add_item(self.special_delta)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        status = await interaction.followup.send(
            "🧪 Qwen-2.1 正在整理場景並用小俠參考圖生成新畫面…", wait=True
        )
        try:
            context = await _generate_qwen_scene(
                self.app,
                scene_delta=str(self.scene_delta.value or "").strip(),
                subject_delta=str(self.subject_delta.value or "").strip(),
                camera_delta=str(self.camera_delta.value or "").strip(),
                mood_delta=str(self.mood_delta.value or "").strip(),
                special_delta=str(self.special_delta.value or "").strip(),
            )

            db = self.app.load_memory()
            db.insert(0, self.app._photo_db_payload(context, type_override="photo"))
            self.app.save_memory(db)

            view = self.app.PhotoResultView(context)
            sent = await self.app._send_photo_message(
                interaction.channel, context, view=view, title_prefix="🧪 Qwen-2.1 特殊圖"
            )
            context["message_id"] = sent.id
            self.app.photo_generation_contexts[sent.id] = context
            view.context = context
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as exc:
            try:
                await status.edit(content=f"⚠️ Qwen-2.1 特殊圖生成失敗：{type(exc).__name__}: {str(exc)[:1400]}")
            except Exception:
                await interaction.followup.send(
                    f"⚠️ Qwen-2.1 特殊圖生成失敗：{type(exc).__name__}: {str(exc)[:1400]}", ephemeral=True
                )


class _PhotoEngineView(discord.ui.View):
    def __init__(self, app: Any, original_handler: Any, source_message: Any):
        super().__init__(timeout=600)
        self.app = app
        self.original_handler = original_handler
        self.source_message = source_message
        self.owner_id = getattr(getattr(source_message, "author", None), "id", None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 /photo 操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Seedream v4.5｜一般圖", style=discord.ButtonStyle.secondary, emoji="🌱")
    async def seedream(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(_SeedreamPhotoModal(self.app, self.original_handler, self.source_message))

    @discord.ui.button(label="Qwen-2.1｜特殊圖", style=discord.ButtonStyle.primary, emoji="🧪")
    async def qwen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(_QwenPhotoModal(self.app, self.source_message))


class _OpenQwenPhotoView(discord.ui.View):
    def __init__(self, app: Any, source_message: Any, initial_scene: str = ""):
        super().__init__(timeout=600)
        self.app = app
        self.source_message = source_message
        self.initial_scene = initial_scene
        self.owner_id = getattr(getattr(source_message, "author", None), "id", None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 /photo Qwen 操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="開啟 Qwen-2.1 特殊圖設定", style=discord.ButtonStyle.primary, emoji="🧪")
    async def open_builder(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(_QwenPhotoModal(self.app, self.source_message, initial_scene=self.initial_scene))


def install_qwen_photo_scene(app: Any) -> Dict[str, Any]:
    original = getattr(app, "handle_unified_photo_command", None)
    if original is None:
        raise RuntimeError("handle_unified_photo_command not found")

    async def routed(message, user_input, *, forced_wardrobe_item=None, photobook_mode=False, return_context=False):
        if forced_wardrobe_item is not None or photobook_mode or return_context:
            return await original(
                message, user_input,
                forced_wardrobe_item=forced_wardrobe_item,
                photobook_mode=photobook_mode,
                return_context=return_context,
            )

        raw = str(user_input or "").strip()
        body = re.sub(r"^/photo\b", "", raw, flags=re.I).strip()
        lower = body.lower()

        if body and not lower.startswith(("qwen", "特殊", "special", "seedream", "一般")):
            return await original(message, user_input)

        if lower.startswith(("qwen", "特殊", "special")):
            initial = re.sub(r"^(?:qwen(?:-?2\.1)?|特殊(?:圖)?|special)\s*", "", body, flags=re.I).strip()
            await message.channel.send(
                "🧪 **/photo｜Qwen-2.1 特殊圖**\n"
                "五個欄位都可直接修改；前四欄交給 Gemini 整理，「特別要求」原文直接附加給 Qwen，若這次不需要可整欄清空。",
                view=_OpenQwenPhotoView(app, message, initial_scene=initial),
            )
            return None

        if lower.startswith(("seedream", "一般")):
            cleaned = re.sub(r"^(?:seedream(?:\s*v?4\.5)?|一般(?:圖)?)\s*", "", body, flags=re.I).strip()
            if cleaned:
                return await original(message, "/photo " + cleaned)

        await message.channel.send(
            "📸 **/photo｜請選擇生圖引擎**\n"
            "🌱 Seedream v4.5：一般圖（原流程）\n"
            "🧪 Qwen-2.1：特殊圖（參考圖新場景生成）",
            view=_PhotoEngineView(app, original, message),
        )
        return None

    app.handle_unified_photo_command = routed

    # Native /photo entrypoint.
    # Legacy text "/photo <scene>" remains untouched for attachment-heavy workflows,
    # while bare /photo can now be selected from Discord's slash-command UI.
    bot = app.girlfriend_bot
    tree = bot.tree

    async def photo_slash(interaction: discord.Interaction):
        proxy_message = SimpleNamespace(
            channel=interaction.channel,
            author=interaction.user,
            attachments=[],
            content="/photo",
        )
        await interaction.response.send_message(
            "📸 **/photo｜請選擇生圖引擎**\n"
            "🌱 Seedream v4.5：一般圖（原流程）\n"
            "🧪 Qwen-2.1：特殊圖（參考圖新場景生成）",
            view=_PhotoEngineView(app, original, proxy_message),
            ephemeral=True,
        )

    command = app_commands.Command(
        name="photo",
        description="小俠照片工作台：選擇 Seedream v4.5 或 Qwen-2.1",
        callback=photo_slash,
    )
    tree.add_command(command, override=True)

    original_ready = getattr(bot, "on_ready", None)
    slash_synced = False

    async def on_ready_with_photo_sync():
        nonlocal slash_synced
        if original_ready is not None:
            await original_ready()
        if slash_synced:
            return
        try:
            synced_cmds = await tree.sync()
            slash_synced = True
            print(f"✅ [QWEN_PHOTO_SLASH_SYNC] version={VERSION} synced={len(synced_cmds)}")
        except Exception as exc:
            print(f"❌ [QWEN_PHOTO_SLASH_SYNC_FAILED] {type(exc).__name__}: {exc}")

    bot.on_ready = on_ready_with_photo_sync

    print(f"✅ [QWEN_PHOTO_SCENE_INSTALLED] version={VERSION} refs={list(_REF_FILES.values())}")
    return {
        "version": VERSION,
        "photo_modes": ["seedream_v4.5", "qwen_2.1_special"],
        "qwen_input_fields": ["scene_delta", "subject_delta", "camera_delta", "mood_delta", "special_delta"],
        "gemini_reads": ["scene_delta", "subject_delta", "camera_delta", "mood_delta"],
        "subject_delta_rewritten": True,
        "special_delta_rewritten": False,
        "special_delta_default_source": "special_intimacy._SPECIAL_USER_DELTA",
        "qwen_refs": list(_REF_FILES.values()),
        "native_slash": "/photo",
        "legacy_text_photo_preserved": True,
    }
