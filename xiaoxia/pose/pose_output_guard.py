# -*- coding: utf-8 -*-
"""Pose-photo presentation cleanup and v5 background guard.

Goals:
- keep internal pose/reference contracts out of Discord/gallery/public records
- avoid exposing English Gemini camera debug in normal user-facing presentation
- prevent legacy v5-background upgrade from replacing Figure 9 Pose with a background plate
  on pose-driven /photo results
"""
from __future__ import annotations

from typing import Any, Dict

PATCH_VERSION = "1.12.06be"
_INTERNAL_MARKERS = (
    "REFERENCE ROLE CONTRACT",
    "FIGURE ROLES:",
    "POSE GEOMETRY AUTHORITY",
)


def _is_pose_context(ctx: Dict[str, Any] | None) -> bool:
    c = ctx if isinstance(ctx, dict) else {}
    joined = " ".join(str(c.get(k) or "") for k in (
        "authoritative_scene", "scene_text", "composition", "prompt_base"
    ))
    return bool(
        c.get("wardrobe_pose_test")
        or c.get("pose_reference_url")
        or c.get("pose_camera_intent")
        or "POSE GEOMETRY AUTHORITY" in joined
        or "VISIBLE-POSE AUTHORITY" in joined
    )


def _strip_internal(text: Any) -> str:
    value = str(text or "").strip()
    cut = len(value)
    for marker in _INTERNAL_MARKERS:
        pos = value.find(marker)
        if pos >= 0:
            cut = min(cut, pos)
    return value[:cut].strip(" \n。.-")


def _public_scene(ctx: Dict[str, Any]) -> str:
    explicit = str(ctx.get("pose_public_scene") or "").strip()
    if explicit:
        return _strip_internal(explicit)
    for key in ("scene_summary", "title", "render_title", "scene_text", "authoritative_scene", "composition"):
        cleaned = _strip_internal(ctx.get(key))
        if cleaned:
            return cleaned
    return "小俠依大俠提供的姿勢參考留下這一刻。"


def _sanitized_context(context: Any) -> Any:
    if not isinstance(context, dict) or not _is_pose_context(context):
        return context
    ctx = dict(context)
    public = _public_scene(ctx)
    # Internal contracts remain available in the live generation context, but all normal
    # presentation/persistence fields are replaced with concise public Chinese text.
    for key in ("title", "render_title", "scene_summary", "scene_text", "composition", "authoritative_scene"):
        ctx[key] = public
    ctx.pop("pose_camera_intent", None)  # do not expose raw English Gemini debug in public UI
    return ctx


def install_pose_output_guard(app: Any) -> Dict[str, Any]:
    patched = []

    original_embed = getattr(app, "_build_result_embed", None)
    if callable(original_embed) and not getattr(original_embed, "_xiaoxia_pose_public_guard", False):
        def guarded_embed(context, *args, **kwargs):
            return original_embed(_sanitized_context(context), *args, **kwargs)
        guarded_embed._xiaoxia_pose_public_guard = True
        app._build_result_embed = guarded_embed
        patched.append("result_embed")

    original_payload = getattr(app, "_photo_db_payload", None)
    if callable(original_payload) and not getattr(original_payload, "_xiaoxia_pose_public_guard", False):
        def guarded_payload(context, *args, **kwargs):
            return original_payload(_sanitized_context(context), *args, **kwargs)
        guarded_payload._xiaoxia_pose_public_guard = True
        app._photo_db_payload = guarded_payload
        patched.append("photo_db_payload")

    # The current v5 refinement path consumes Figure 9 as a v5 background plate.
    # On a pose-driven photo, Figure 9 is the Pose Authority, so using that path destroys
    # the very reference we need. Block this incompatible path instead of silently changing
    # pose/scene. A future dedicated pose-aware v5 path can use a separate reference budget.
    try:
        from xiaoxia.photo import handlers
        original_v5 = handlers.HANDLERS.get("v5_refine")
        if callable(original_v5) and not getattr(original_v5, "_xiaoxia_pose_v5_guard", False):
            async def pose_safe_v5(view, interaction, app_obj):
                ctx = dict(getattr(view, "context", {}) or {})
                if _is_pose_context(ctx):
                    await interaction.response.send_message(
                        "⚠️ 這張是 Pose Reference 照片；目前的 v5.0 場景升級會把 Pose 參考位改成背景圖，"
                        "因此會破壞原姿勢與場景。這類照片暫不執行 v5.0 場景升級。",
                        ephemeral=True,
                    )
                    return
                return await original_v5(view, interaction, app_obj)
            pose_safe_v5._xiaoxia_pose_v5_guard = True
            handlers.HANDLERS["v5_refine"] = pose_safe_v5
            patched.append("v5_pose_guard")
    except Exception as exc:
        print(f"⚠️ [POSE_OUTPUT_GUARD_V5_PATCH_FAILED] {type(exc).__name__}: {exc}")

    return {"version": PATCH_VERSION, "patched": patched}
