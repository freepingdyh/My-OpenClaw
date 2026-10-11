# -*- coding: utf-8 -*-
"""Qwen Image 2.1 collectible photobook refinement for Xiaoxia.

One shared "收藏寫真" button routes automatically:
- ordinary/clothed source -> clothed beauty refs
- 情不自禁/special source -> existing nude beauty refs

The current image is always image_1. Gemini does not write or rewrite the
Qwen prompt. Existing H3 remains untouched.
"""
from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

import aiohttp
import discord
from PIL import Image, ImageFilter
from google.genai import types

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21


VERSION = "1.14.10-beauty-portrait-v4"
_BUTTON_LABEL = "📸 收藏寫真"
_ACTIVE_JOBS: set[Any] = set()
_REFS_DIR = Path("/data/memory/qwen21/refs")

_CLOTHED_FULL = "image_4_body_full_clothed.png"
_CLOTHED_HALF = "image_5_body_half_clothed.png"

_REMOVE_BUTTON_MARKERS = (
    "收藏到衣櫃",
    "上傳成為 Project",
    "上傳成為 Diary",
    "SD 1.5Pro",
)

_COMMON_HEAD = """<image1> is the edit canvas and the single source of truth for the final photograph.

Keep the woman in <image1> unchanged:
same identity,
same facial features,
same facial expression,
same hairstyle,
same body shape and proportions,
same anatomy,
same pose,
same camera angle,
same framing,
same scene,
same background,
same objects and spatial relationships.

Do not redesign or regenerate the woman.

<image2>, <image3>, <image4>, <image5>, and <image6> are reference images of the SAME single 24-year-old adult woman shown in <image1>.
They are reference-only and must never appear as additional people.

Use <image2> and <image3> only as safeguards against facial-identity drift.
Use <image4> and <image5> only as safeguards against body-proportion drift.
Use <image6> only as an additional body-consistency safeguard.
Do not transfer pose, expression, lighting, skin rendering, scene, composition, or state of dress from any reference image.

The final image must contain exactly ONE woman: the woman from <image1>.
"""

_COMMON_BEAUTY = """
Change ONLY the photographic rendering quality of <image1>:

- correct white balance while preserving the original atmosphere and time of day
- improve flattering but realistic portrait lighting without changing light direction
- preserve natural skin color
- render clean, realistic, fine skin texture
- preserve pores and subtle natural skin detail without exaggeration
- reduce harsh digital sharpening, noisy texture, gritty skin, waxy skin, and artificial micro-contrast
- improve highlight and shadow transitions
- improve tonal depth and photographic clarity
- improve natural hair and fabric detail where present
- apply restrained professional color grading and portrait retouching

The result must look like THE SAME photograph professionally color-graded and retouched by a skilled portrait photographer, not like a newly generated photograph.

Do not change body size, breast size, waist, hips, legs, face shape, expression, pose, anatomy, camera angle, framing, background, objects, or composition.

Exactly one woman.
No clones.
No twins.
No duplicate subjects.
No additional people.
No extra heads, torsos, arms, legs, or foreign body parts.
"""

NUDE_BEAUTY_PROMPT = _COMMON_HEAD + """
Preserve the exact state of dress shown in <image1>.
Do not add, remove, cover, expose, enlarge, reduce, or redesign any body area.
""" + _COMMON_BEAUTY

CLOTHED_BEAUTY_PROMPT = _COMMON_HEAD + """
Preserve the exact outfit shown in <image1>.
Do not alter garment coverage, garment shape, fit, material, color, accessories, or styling.
""" + _COMMON_BEAUTY


def _public_url(filename: str) -> str:
    base = (os.environ.get("XIAOXIA_PUBLIC_BASE_URL") or "https://xiaoxia0320.zeabur.app").rstrip("/")
    return f"{base}/gallery/{filename}"


def _is_nude_beauty_source(context: Dict[str, Any]) -> bool:
    ctx = context or {}
    if bool(ctx.get("special_intimacy")):
        return True
    return str(ctx.get("special_beauty_variant") or "").strip().lower() == "nude"


async def _source_image_bytes(app: Any, context: Dict[str, Any]) -> bytes:
    ctx = context or {}
    candidates = []
    local_path = str(ctx.get("local_path") or "").strip()
    if local_path:
        candidates.append(local_path)

    mapper = getattr(app, "_gallery_url_to_local_path", None)
    for value in (str(ctx.get("local_url") or ""), str(ctx.get("image_url") or "")):
        if value and callable(mapper):
            try:
                mapped = mapper(value)
            except Exception:
                mapped = None
            if mapped:
                candidates.append(str(mapped))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            data = Path(candidate).read_bytes()
            if data:
                return data

    url = next(
        (
            x for x in (str(ctx.get("local_url") or ""), str(ctx.get("image_url") or ""))
            if x.startswith(("http://", "https://"))
        ),
        "",
    )
    if not url:
        raise RuntimeError("BEAUTY_SOURCE_IMAGE_NOT_FOUND")

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"BEAUTY_SOURCE_IMAGE_HTTP_{response.status}")
            data = await response.read()
            if not data:
                raise RuntimeError("BEAUTY_SOURCE_IMAGE_EMPTY")
            return data


def _jpeg_job_ref(path: Path, name: str) -> Tuple[str, bytes]:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90, optimize=True)
        data = buf.getvalue()
    if not data:
        raise RuntimeError(f"BEAUTY_CLOTHED_REF_ENCODE_EMPTY: {path}")
    return name, data


def _clothed_refs() -> Tuple[Dict[str, str], Dict[str, bytes]]:
    full_path = _REFS_DIR / _CLOTHED_FULL
    half_path = _REFS_DIR / _CLOTHED_HALF
    missing = [str(p) for p in (full_path, half_path) if not p.is_file()]
    if missing:
        raise RuntimeError("BEAUTY_CLOTHED_REF_MISSING: " + ", ".join(missing))

    full_name, full_blob = _jpeg_job_ref(full_path, "image_4_body_full_clothed_job.jpg")
    half_name, half_blob = _jpeg_job_ref(half_path, "image_5_body_half_clothed_job.jpg")
    replacements = {
        "image_4_body_full.png": full_name,
        "image_5_body_half.png": half_name,
    }
    extras = {full_name: full_blob, half_name: half_blob}
    print(
        f"📦 [BEAUTY_CLOTHED_REFS] full={len(full_blob)} half={len(half_blob)} total={len(full_blob)+len(half_blob)}"
    )
    return replacements, extras

def _persist_result(
    app: Any,
    source: Dict[str, Any],
    blob: bytes,
    variant: str,
) -> Dict[str, Any]:
    output_dir = Path(str(getattr(app, "OUTPUT_DIR", "/tmp") or "/tmp"))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"xiaoxia_beauty_{variant}_{uuid.uuid4().hex[:10]}.png"
    path = output_dir / filename
    path.write_bytes(blob)

    new_context = dict(source or {})
    inherit = getattr(app, "_inherit_photo_lineage", None)
    if callable(inherit):
        try:
            new_context = inherit(source, dict(source or {}), action="special_beauty")
        except Exception as exc:
            print(f"⚠️ [BEAUTY_LINEAGE_INHERIT_FAILED] {type(exc).__name__}: {exc}")
            new_context = dict(source or {})

    new_context.update(
        {
            "local_path": str(path),
            "local_url": _public_url(filename),
            "image_url": _public_url(filename),
            "special_beauty": True,
            "special_beauty_version": VERSION,
            "special_beauty_variant": variant,
            "special_beauty_parent_url": str(source.get("local_url") or source.get("image_url") or ""),
            "trace_action": f"special_beauty_{variant}",
        }
    )
    return new_context


async def _send_result(
    app: Any,
    interaction: discord.Interaction,
    source: Dict[str, Any],
    blob: bytes,
    variant: str,
) -> None:
    new_context = _persist_result(app, source, blob, variant)

    try:
        db = app.load_memory()
        db.insert(0, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
        app.save_memory(db)
    except Exception as exc:
        print(f"⚠️ [BEAUTY_DB_SAVE_FAILED] {type(exc).__name__}: {exc}")

    filename = Path(new_context["local_path"]).name
    view = app.PhotoResultView(new_context)
    embed = app._build_result_embed(
        new_context,
        title_prefix="📸 收藏寫真",
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


def _review_proxy(image_bytes: bytes) -> bytes:
    """Blurred proxy derived from the exact final image for provider-safe vision fallback."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.GaussianBlur(radius=10))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=72, optimize=True)
        return buf.getvalue()


async def _review_beauty_result(
    app: Any,
    source: Dict[str, Any],
    variant: str,
    image_bytes: bytes,
) -> str:
    base_prompt = f"""
妳是小俠本人。小俠是 24 歲成年女性。
附圖是剛剛「收藏寫真」流程最後真正生成完成的成品。

請直接以小俠的身份，用自然繁體中文回應大俠。
這是看完成品之後的新反應，不是生成前文案，也不是影像生成 prompt。
可以自由決定要說多少，不限制句數。
只回應照片的整體美感、表情、氣氛、光線、色調與妳自己的感受；不要做露骨的身體描述。
不要輸出 JSON、標題、分析、規則，也不要描述不存在的細節。

收藏寫真類型：{variant}
來源模式：{str(source.get("source_mode") or source.get("type") or source.get("db_type") or "photo")}
""".strip()

    configured_model = (
        os.environ.get("XIAOXIA_SPECIAL_REVIEW_MODEL")
        or os.environ.get("XIAOXIA_SPECIAL_DIRECTOR_MODEL")
        or "gemini-2.5-flash"
    ).strip()
    models = [configured_model]
    if configured_model != "gemini-2.5-flash":
        models.append("gemini-2.5-flash")

    attempts = [("exact", image_bytes, "image/png", base_prompt)]
    if variant == "nude":
        attempts.append((
            "proxy",
            _review_proxy(image_bytes),
            "image/jpeg",
            base_prompt + "\n\n這是由同一張完成圖產生的模糊預覽。只根據仍可見的整體構圖、表情、光線、色調與氣氛回應，不要推測被模糊掉的細節。",
        ))

    for kind, blob, mime_type, prompt in attempts:
        for model in models:
            try:
                response = await app.gemini_client.aio.models.generate_content(
                    model=model,
                    contents=[prompt, types.Part.from_bytes(data=blob, mime_type=mime_type)],
                )
                text = str(getattr(response, "text", "") or "").strip()
                if text:
                    print(f"✅ [BEAUTY_POST_REVIEW_OK] kind={kind} model={model} chars={len(text)}")
                    return text
                feedback = getattr(response, "prompt_feedback", None)
                candidates = getattr(response, "candidates", None)
                reasons = [str(getattr(c, "finish_reason", "") or "") for c in (candidates or [])]
                print(f"⚠️ [BEAUTY_POST_REVIEW_EMPTY] kind={kind} model={model} feedback={feedback} finish_reasons={reasons}")
            except Exception as exc:
                print(f"⚠️ [BEAUTY_POST_REVIEW_FAILED] kind={kind} model={model} {type(exc).__name__}: {exc}")
    return ""

async def _handle_button(app: Any, view: Any, interaction: discord.Interaction) -> None:
    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = message_id or id(view)
    if job_key in _ACTIVE_JOBS:
        await interaction.response.send_message("📸 這張的收藏寫真正在生成中，先等它完成喔。", ephemeral=True)
        return

    if not os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID") or not (
        os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY") or os.environ.get("RUNPOD_API_KEY")
    ):
        await interaction.response.send_message("⚠️ 收藏寫真服務目前尚未完成設定。", ephemeral=True)
        return

    _ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    status = None
    try:
        context = dict(getattr(view, "context", {}) or {})
        variant = "nude" if _is_nude_beauty_source(context) else "clothed"
        image_bytes = await _source_image_bytes(app, context)

        status = await interaction.followup.send(
            "📸 正在把這張照片精修成收藏寫真…",
            wait=True,
        )

        if variant == "nude":
            results = await run_qwen21(
                image_bytes,
                prompt=NUDE_BEAUTY_PROMPT,
                steps=40,
            )
        else:
            replacements, extras = _clothed_refs()
            results = await run_qwen21(
                image_bytes,
                prompt=CLOTHED_BEAUTY_PROMPT,
                steps=40,
                workflow_image_replacements=replacements,
                extra_images=extras,
            )

        if not results:
            raise RunPodServerlessError("Qwen21 returned no beauty image")

        _, blob = results[0]
        await _send_result(app, interaction, context, blob, variant)

        if status is not None:
            try:
                await status.delete()
            except Exception:
                pass

        final_reply = await _review_beauty_result(
            app,
            context,
            variant,
            blob,
        )
        if final_reply:
            await interaction.followup.send(f"📸 **小俠看完後**：{final_reply}")
        else:
            await interaction.followup.send(
                "📸 **小俠**：我這次沒有成功讀到最後的收藏寫真，所以先不硬湊一段看圖反應。",
            )

        print(
            f"✅ [BEAUTY_COMPLETED] version={VERSION} variant={variant} bytes={len(blob)}"
        )
    except Exception as exc:
        print(f"❌ [BEAUTY_ERROR] {type(exc).__name__}: {exc}")
        message = f"⚠️ 收藏寫真生成失敗：`{type(exc).__name__}: {str(exc)[:1100]}`"
        if status is not None:
            try:
                await status.edit(content=message)
                return
            except Exception:
                pass
        await interaction.followup.send(message, ephemeral=True)
    finally:
        _ACTIVE_JOBS.discard(job_key)


class BeautyPortraitButton(discord.ui.Button):
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


def install_beauty_portrait(app: Any) -> Dict[str, Any]:
    current_factory = getattr(app, "PhotoResultView", None)
    if current_factory is None:
        raise RuntimeError("PhotoResultView not found")
    if getattr(app, "_xiaoxia_beauty_portrait_installed", False):
        return {"version": VERSION, "patched": False, "reason": "already_installed"}

    def routed_beauty_photo_result_view(context):
        view = current_factory(context)

        for child in list(getattr(view, "children", []) or []):
            label = str(getattr(child, "label", "") or "")
            if any(marker in label for marker in _REMOVE_BUTTON_MARKERS):
                try:
                    view.remove_item(child)
                except Exception:
                    pass

        if not any(
            isinstance(child, discord.ui.Button) and getattr(child, "label", "") == _BUTTON_LABEL
            for child in getattr(view, "children", [])
        ):
            view.add_item(BeautyPortraitButton(app, view))
        return view

    routed_beauty_photo_result_view.__name__ = "PhotoResultView"
    routed_beauty_photo_result_view.__qualname__ = "PhotoResultView"
    routed_beauty_photo_result_view.__doc__ = (
        "Final shared PhotoResultView wrapper: removes deprecated buttons and adds 收藏寫真."
    )
    app.PhotoResultView = routed_beauty_photo_result_view
    app._xiaoxia_beauty_portrait_installed = True

    return {
        "version": VERSION,
        "patched": True,
        "button": _BUTTON_LABEL,
        "removed_buttons": list(_REMOVE_BUTTON_MARKERS),
        "h3_preserved": True,
        "nude_route": "qwen21 existing refs + fixed beauty prompt",
        "clothed_route": "qwen21 clothed body refs + fixed beauty prompt",
        "gemini_prompt_engineering": False,
        "post_generation_review": True,
        "review_source": "exact_finished_image_bytes",
        "cfg_strategy": "unchanged workflow cfg=1; no negative-prompt override",
    }
