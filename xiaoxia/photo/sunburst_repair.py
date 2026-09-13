# -*- coding: utf-8 -*-
"""GPT-Image 2.5 Sunburst backend for Xiaoxia's existing `修正這張` flow.

Design goals:
- Keep Seedream v4.5 as the normal new-image engine.
- Replace only the repair/edit backend used by PhotoRepairModal.
- Send the current image directly to OpenAI image edit; no Gemini rewrite layer.
- Preserve the current image as the source of truth for multi-turn repair.
- Keep provider moderation enabled/configurable; never silently rewrite a rejected request.
"""
from __future__ import annotations

import base64
import os
import uuid
from typing import Any, Dict, Optional

SUNBURST_DEFAULT_MODEL = "gpt-image-2.5-sunburst-2026-09-08"
SUNBURST_DEFAULT_QUALITY = "high"
SUNBURST_DEFAULT_MODERATION = "auto"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _model() -> str:
    return _clean(os.environ.get("XIAOXIA_REPAIR_MODEL")) or SUNBURST_DEFAULT_MODEL


def _quality() -> str:
    value = (_clean(os.environ.get("XIAOXIA_REPAIR_QUALITY")) or SUNBURST_DEFAULT_QUALITY).lower()
    allowed = {"low", "medium", "high", "xhigh", "max", "auto"}
    return value if value in allowed else SUNBURST_DEFAULT_QUALITY


def _moderation() -> str:
    value = (_clean(os.environ.get("XIAOXIA_REPAIR_MODERATION")) or SUNBURST_DEFAULT_MODERATION).lower()
    return value if value in {"auto", "low"} else SUNBURST_DEFAULT_MODERATION


def _edit_prompt(request_text: str) -> str:
    request_text = _clean(request_text)
    return (
        "Edit the supplied image, using it as the authoritative source image. "
        "Preserve the same adult woman's identity and facial features, hairstyle unless explicitly requested, "
        "outfit except where explicitly requested, background, camera viewpoint, lighting, and overall composition. "
        "Change only what the user asks for. Keep the result photorealistic, natural, anatomically plausible, "
        "and visually consistent with the original. Do not redesign unrelated parts of the image.\n\n"
        f"Requested edit: {request_text}"
    )


def _response_image_bytes(response: Any) -> Optional[bytes]:
    data = getattr(response, "data", None) or []
    if not data:
        return None
    item = data[0]
    b64 = getattr(item, "b64_json", None)
    if not b64 and isinstance(item, dict):
        b64 = item.get("b64_json")
    if not b64:
        return None
    return base64.b64decode(b64)


def _response_url(response: Any) -> str:
    data = getattr(response, "data", None) or []
    if not data:
        return ""
    item = data[0]
    url = getattr(item, "url", None)
    if not url and isinstance(item, dict):
        url = item.get("url")
    return _clean(url)


def _write_gallery_image(app: Any, image_bytes: bytes) -> str:
    output_dir = _clean(getattr(app, "OUTPUT_DIR", ""))
    if not output_dir:
        raise RuntimeError("Sunburst repair succeeded, but OUTPUT_DIR is unavailable.")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"sunburst_repair_{uuid.uuid4().hex}.png"
    path = os.path.join(output_dir, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    base = _clean(os.environ.get("XIAOXIA_PUBLIC_BASE_URL")) or "https://xiaoxia0320.zeabur.app"
    return f"{base.rstrip('/')}/gallery/{filename}"


async def generate_sunburst_repair(
    app: Any,
    source_path: str,
    repair_request: str,
    enable_safety_checker: bool = True,
    trace_context: Optional[Dict[str, Any]] = None,
    source_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Signature-compatible replacement for legacy generate_seedream_v45_repair."""
    if not source_path or not os.path.exists(source_path):
        raise RuntimeError("Sunburst repair source image is missing.")
    if not _clean(repair_request):
        raise RuntimeError("Sunburst repair request is empty.")
    if not _clean(os.environ.get("OPENAI_API_KEY")):
        raise RuntimeError("OPENAI_API_KEY 未設定，無法使用 GPT-Image 2.5 Sunburst 修圖。")

    model = _model()
    quality = _quality()
    moderation = _moderation()
    prompt = _edit_prompt(repair_request)

    if isinstance(trace_context, dict):
        trace_context["repair_engine"] = "openai_sunburst"
        trace_context["repair_model"] = model
        trace_context["repair_quality"] = quality
        trace_context["repair_moderation"] = moderation
        trace_context["repair_user_request"] = _clean(repair_request)

    print(
        f"☀️🩹 [SUNBURST_REPAIR_START] model={model} quality={quality} "
        f"moderation={moderation} source={os.path.basename(source_path)}"
    )

    try:
        with open(source_path, "rb") as image_file:
            response = await app.openai_client.images.edit(
                model=model,
                image=image_file,
                prompt=prompt,
                quality=quality,
                size="auto",
                moderation=moderation,
            )
    except TypeError as exc:
        # Backward-compatible SDK fallback: keep provider moderation defaults if a locally
        # installed older SDK does not yet expose the new moderation parameter.
        if "moderation" not in str(exc):
            raise
        print("⚠️ [SUNBURST_SDK_MODERATION_PARAM_UNAVAILABLE] retrying with provider default moderation")
        with open(source_path, "rb") as image_file:
            response = await app.openai_client.images.edit(
                model=model,
                image=image_file,
                prompt=prompt,
                quality=quality,
                size="auto",
            )

    url = _response_url(response)
    if url:
        print("✅ [SUNBURST_REPAIR_OK] transport=url")
        return url

    image_bytes = _response_image_bytes(response)
    if not image_bytes:
        raise RuntimeError("Sunburst returned no image payload.")
    gallery_url = _write_gallery_image(app, image_bytes)
    print(f"✅ [SUNBURST_REPAIR_OK] transport=b64 gallery={gallery_url}")
    return gallery_url


def install_sunburst_repair(app: Any) -> Dict[str, Any]:
    """Patch only the monolith repair generator symbol; existing Discord UX stays intact."""
    previous = getattr(app, "generate_seedream_v45_repair", None)
    if previous is None:
        raise RuntimeError("generate_seedream_v45_repair not found; repair hook cannot be installed.")

    async def _replacement(
        source_path: str,
        repair_request: str,
        enable_safety_checker: bool = True,
        trace_context: Optional[Dict[str, Any]] = None,
        source_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await generate_sunburst_repair(
            app,
            source_path,
            repair_request,
            enable_safety_checker=enable_safety_checker,
            trace_context=trace_context,
            source_context=source_context,
        )

    app.generate_seedream_v45_repair = _replacement
    app._xiaoxia_previous_repair_generator = previous
    app._xiaoxia_sunburst_repair_installed = True
    return {
        "installed": True,
        "model": _model(),
        "quality": _quality(),
        "moderation": _moderation(),
        "scope": "PhotoRepairModal only",
    }
