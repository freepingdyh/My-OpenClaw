# -*- coding: utf-8 -*-
"""Pose-photo public/internal metadata boundary and v5 background guard.

Generation contracts may contain Figure/Camera/POSE engineering instructions. Those
instructions must stay available to the generation pipeline, but must never leak into
Discord presentation or normal photo/gallery metadata.
"""
from __future__ import annotations

import re
from typing import Any, Dict

PATCH_VERSION = "1.12.07a"
_INTERNAL_MARKERS = (
    "REFERENCE ROLE CONTRACT",
    "FIGURE ROLES:",
    "POSE GEOMETRY AUTHORITY",
    "VISIBLE-POSE AUTHORITY",
)
_ENGINEERING_HINTS = (
    "Figure 9",
    "Figure 10",
    "Figures 1-8",
    "Camera 指令",
    "Camera authority",
    "Pose authority",
    "POSE GEOMETRY",
    "REFERENCE ROLE",
)


def _is_pose_context(ctx: Dict[str, Any] | None) -> bool:
    c = ctx if isinstance(ctx, dict) else {}
    joined = " ".join(str(c.get(k) or "") for k in (
        "authoritative_scene", "scene_text", "composition", "prompt_base", "root_prompt_base"
    ))
    return bool(
        c.get("wardrobe_pose_test")
        or c.get("pose_reference_url")
        or c.get("pose_camera_intent")
        or "POSE GEOMETRY AUTHORITY" in joined
        or "VISIBLE-POSE AUTHORITY" in joined
        or "Figure 9" in joined
    )


def _strip_internal(text: Any) -> str:
    value = str(text or "").strip()
    cut = len(value)
    for marker in _INTERNAL_MARKERS:
        pos = value.find(marker)
        if pos >= 0:
            cut = min(cut, pos)
    value = value[:cut].strip(" \n。.-")

    # A legacy pose scene can already contain human-facing Chinese mixed with internal
    # tokens such as "Figure 9" / "Camera 指令" before the English contract starts.
    # Do not try to surgically translate engineering prose; replace it at the public
    # boundary with a neutral human-facing scene description instead.
    if any(hint in value for hint in _ENGINEERING_HINTS):
        return ""
    return value


def _public_scene(ctx: Dict[str, Any]) -> str:
    explicit = _strip_internal(ctx.get("pose_public_scene"))
    if explicit:
        return explicit

    # Prefer genuinely human-facing scene text. Reject legacy pose-routing prose even
    # when it is Chinese, because "Figure 9 / Camera" are implementation details.
    for key in ("scene_summary", "title", "render_title", "scene_text", "authoritative_scene", "composition"):
        cleaned = _strip_internal(ctx.get(key))
        if cleaned:
            return cleaned

    return "背景自然且不搶戲，小俠依姿勢參考留下這一刻。"


def _sanitized_context(context: Any) -> Any:
    if not isinstance(context, dict) or not _is_pose_context(context):
        return context

    ctx = dict(context)
    public = _public_scene(ctx)

    # Public/persistence metadata is deliberately separated from generation contracts.
    # Do NOT mutate prompt_base/root_prompt_base/semantic_contract: those remain internal
    # generation evidence and may be needed by More/replay/debug paths.
    for key in (
        "title", "render_title", "scene_summary", "scene_text",
        "composition", "authoritative_scene", "activity_title",
    ):
        ctx[key] = public

    ctx["pose_public_scene"] = public
    ctx.pop("pose_camera_intent", None)  # raw Gemini English is internal-only
    return ctx


def install_pose_output_guard(app: Any) -> Dict[str, Any]:
    patched = []

    original_embed = getattr(app, "_build_result_embed", None)
    if callable(original_embed) and not getattr(original_embed, "_xiaoxia_pose_public_guard_v11207a", False):
        def guarded_embed(context, *args, **kwargs):
            return original_embed(_sanitized_context(context), *args, **kwargs)
        guarded_embed._xiaoxia_pose_public_guard_v11207a = True
        app._build_result_embed = guarded_embed
        patched.append("result_embed")

    original_payload = getattr(app, "_photo_db_payload", None)
    if callable(original_payload) and not getattr(original_payload, "_xiaoxia_pose_public_guard_v11207a", False):
        def guarded_payload(context, *args, **kwargs):
            return original_payload(_sanitized_context(context), *args, **kwargs)
        guarded_payload._xiaoxia_pose_public_guard_v11207a = True
        app._photo_db_payload = guarded_payload
        patched.append("photo_db_payload")

    # The current v5 refinement path consumes Figure 9 as a v5 background plate.
    # On a pose-driven photo, Figure 9 is the Pose Authority, so keep that path blocked.
    try:
        from xiaoxia.photo import handlers
        original_v5 = handlers.HANDLERS.get("v5_refine")
        if callable(original_v5) and not getattr(original_v5, "_xiaoxia_pose_v5_guard", False):
            async def pose_safe_v5(view, interaction, app_obj):
                ctx = dict(getattr(view, "context", {}) or {})
                if _is_pose_context(ctx):
                    await interaction.response.send_message(
                        "⚠️ 這張是姿勢參考照片；目前的 v5.0 場景升級會占用姿勢參考位置，"
                        "因此可能破壞原姿勢與場景。這類照片暫不執行 v5.0 場景升級。",
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
