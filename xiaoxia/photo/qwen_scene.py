# -*- coding: utf-8 -*-
"""Qwen Image 2.1 reference-scene mode for /photo."""
from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict
from types import SimpleNamespace

import discord
from discord import app_commands

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21_reference_scene
from xiaoxia.photo.special_intimacy import _SPECIAL_USER_DELTA

VERSION = "1.1.0-qwen-photo-scene-v4-five-ref-scene"

_REFS_DIR = Path("/data/memory/qwen21/refs")
_REF_FILES = {
    "face_front": "image_2_face_front.png",
    "face_45": "image_3_face_45.png",
    "body_full": "image_4_body_full_clothed.png",
    "body_half": "image_5_body_half_clothed.png",
    "body_clothed": "image_6_body_clothed.png",
}

_QWEN_SCENE_CORE = """QWEN PHOTO — NEW SCENE FROM FIVE REFERENCES

All five reference images show the SAME single adult woman.
They are identity/body-consistency references only, not an edit target and not a canvas.

Reference roles:
- <image1>: full-body reference for overall height, long-legged proportions, waist, and body scale.
- <image2>: front-face identity reference.
- <image3>: 45-degree face identity reference.
- <image4>: half-body reference for upper-body proportions.
- <image5>: clothed body reference for silhouette and overall body consistency.

Create a completely NEW photorealistic scene containing exactly ONE woman: the same woman shown in the
references. Preserve her recognizable identity and established body proportions, but DO NOT copy any
reference pose, background, clothing, framing, camera angle, or composition unless the user explicitly
requests it.

The COMPILED SCENE block defines environment, lighting, camera/framing, and mood.
The SUBJECT DELTA block is direct user authority for the woman's action, pose, expression, and story beat.
Follow SUBJECT DELTA literally and do not rewrite it.
Do not add clones, duplicate subjects, extra people, extra limbs, or unrelated props.
""".strip()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _refs() -> Dict[str, Path]:
    refs = {k: _REFS_DIR / v for k, v in _REF_FILES.items()}
    missing = [str(p) for p in refs.values() if not p.is_file()]
    if missing:
        raise RuntimeError("QWEN_SCENE_REFERENCE_MISSING: " + ", ".join(missing))
    return refs


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


async def _compile_scene_with_gemini(app: Any, *, scene_delta: str, camera_delta: str, mood_delta: str) -> dict:
    prompt = f"""
你是影像場景導演，只負責把使用者的自然語言整理成適合影像模型理解的「場景／鏡頭／氣氛」描述。

你不會看到、推測、補寫或改寫人物的肢體動作與劇情；那部分由另一個欄位直接交給影像模型。

【場景／環境】
{scene_delta or '未指定；請使用簡潔自然、不搶人物的環境'}

【想怎麼拍】
{camera_delta or '自然生活照視角，構圖以人物為主'}

【整體氣氛】
{mood_delta or '自然、寫實、生活感'}

請只回傳 JSON：
{{
  "compiled_scene_prompt": "一段可直接交給影像模型的英文場景描述，只寫 location/environment, lighting, camera/framing, atmosphere/mood；不要描述人物具體肢體動作，也不要改寫任何未提供的劇情。",
  "scene_summary": "繁體中文，40字內",
  "camera_summary": "繁體中文，30字內",
  "mood_summary": "繁體中文，30字內"
}}

規則：
1. 使用者可以完全不懂攝影術語；請把自然語言轉成合理的鏡頭與構圖語言。
2. 不要自行加入第二人物。
3. 不要自行加入人物姿勢、觸碰、肢體互動或劇情。
4. 場景、鏡頭、氣氛之間要彼此一致，不要堆砌攝影術語。
""".strip()

    resp = await app.gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=app.types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    data = _extract_json(getattr(resp, "text", ""))
    compiled = _clean(data.get("compiled_scene_prompt"))
    if not compiled:
        compiled = _clean(f"{scene_delta}. Camera/framing: {camera_delta}. Mood/lighting: {mood_delta}.")
    return {
        "compiled_scene_prompt": compiled,
        "scene_summary": _clean(data.get("scene_summary") or scene_delta)[:80],
        "camera_summary": _clean(data.get("camera_summary") or camera_delta)[:60],
        "mood_summary": _clean(data.get("mood_summary") or mood_delta)[:60],
    }


def _build_qwen_prompt(compiled_scene: str, subject_delta: str) -> str:
    return (
        _QWEN_SCENE_CORE
        + "\n\nCOMPILED SCENE — environment/camera/mood only:\n"
        + _clean(compiled_scene)
        + "\n\nSUBJECT DELTA — direct user wording; follow precisely:\n"
        + str(subject_delta or "").strip()
        + "\n\nSPECIAL PRESENTATION BLOCK — fixed production wording:\n"
        + _SPECIAL_USER_DELTA
    ).strip()


async def _generate_qwen_scene(app: Any, *, scene_delta: str, subject_delta: str, camera_delta: str, mood_delta: str) -> dict:
    refs = _refs()
    scene = await _compile_scene_with_gemini(
        app, scene_delta=scene_delta, camera_delta=camera_delta, mood_delta=mood_delta
    )
    prompt = _build_qwen_prompt(scene["compiled_scene_prompt"], subject_delta)

    # True reference-scene path: all five refs are worker-staged and remain
    # vision references only. No reference image is uploaded as an edit canvas,
    # and the scene job removes VAE reference-latent injection.
    seed = secrets.randbelow(2**63 - 1)
    results = await run_qwen21_reference_scene(
        prompt=prompt,
        seed=seed,
        steps=40,
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
        "authoritative_scene": scene["compiled_scene_prompt"],
        "root_prompt_base": scene["compiled_scene_prompt"],
        "scene_text": scene["scene_summary"] or scene_delta,
        "scene_summary": scene["scene_summary"] or scene_delta,
        "action_summary": _clean(subject_delta)[:120],
        "camera_summary": scene["camera_summary"],
        "mood": scene["mood_summary"] or mood_delta,
        "mood_summary": scene["mood_summary"] or mood_delta,
        "outfit_summary": "Qwen special scene",
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
        "qwen_steps": 40,
        "qwen_reference_set": [
            _REF_FILES["body_full"],
            _REF_FILES["face_front"],
            _REF_FILES["face_45"],
            _REF_FILES["body_half"],
            _REF_FILES["body_clothed"],
        ],
        "qwen_reference_mode": "vision_only_no_vae_reference_latents",
        "qwen_scene_workflow_mode": "five_ref_fresh_latent",
        "qwen_scene_delta": scene_delta,
        "qwen_subject_delta": subject_delta,
        "qwen_camera_delta": camera_delta,
        "qwen_mood_delta": mood_delta,
        "qwen_compiled_scene_prompt": scene["compiled_scene_prompt"],
    }


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
            await self.original_handler(self.source_message, "/photo " + str(self.scene.value or "").strip())
            await interaction.followup.send("✅ 已交給 Seedream v4.5。", ephemeral=True)
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
        self.add_item(self.scene_delta)
        self.add_item(self.subject_delta)
        self.add_item(self.camera_delta)
        self.add_item(self.mood_delta)

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
                "四個欄位都是自然語言，可直接改範例；Gemini 只整理場景／鏡頭／氣氛，人物動作欄原文直接交給 Qwen。",
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
            "🧪 Qwen-2.1：特殊圖（reference scene generation）",
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
            "🧪 Qwen-2.1：特殊圖（reference scene generation）",
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
        "qwen_input_fields": ["scene_delta", "subject_delta", "camera_delta", "mood_delta"],
        "gemini_reads": ["scene_delta", "camera_delta", "mood_delta"],
        "subject_delta_rewritten": False,
        "qwen_refs": list(_REF_FILES.values()),
        "native_slash": "/photo",
        "legacy_text_photo_preserved": True,
    }
