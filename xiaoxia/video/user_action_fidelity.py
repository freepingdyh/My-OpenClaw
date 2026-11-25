# -*- coding: utf-8 -*-
"""v1.12.06ab — keep explicit user subject actions from being replaced by camera motion.

This is a Director-layer constraint only. It does not rewrite authoritative_scene and
it does not hard-code any particular body part or motion. When /影片 carries explicit
user-directed physical action, Gemini must preserve that action as subject motion;
camera motion may support it but may not simulate or replace it.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import h3_director_mode

_ORIGINAL_BUILD = h3_director_mode.build_h3_director_plan


def _with_action_fidelity(context: Dict[str, Any]) -> Dict[str, Any]:
    ctx = dict(context or {})
    direction = str(ctx.get("video_user_direction") or "").strip()
    if not direction:
        return ctx

    existing = str(ctx.get("message") or "").strip()
    rule = (
        "\n\n【USER ACTION FIDELITY — Director constraint】\n"
        "The user explicitly directed the subject's story/action. Preserve physical subject actions as subject motion. "
        "If the request says or clearly implies walking/approaching, stepping, turning, looking back, sitting, standing, "
        "retreating, reaching, picking up, putting down, or another observable body action, the Hero Action/Reaction must "
        "describe Xiaoxia physically performing it when feasible from the start frame. Do NOT substitute camera push-in, "
        "zoom, pan, orbit, crop, or reframing for the requested subject displacement/action. Camera motion may only support "
        "the action. Prefer a mostly locked or gently tracking camera when that makes the subject action unambiguous. "
        "Preserve requested action order and ending beat when feasible. Do not invent exposure, outfit changes, or unsafe/"
        "physically incoherent motion. If the exact action is impossible from the start frame, simplify to the nearest "
        "physically coherent subject action while preserving the user's core intent.\n"
        f"User-directed action: {direction}"
    )
    ctx["message"] = existing + rule
    ctx["video_action_fidelity"] = True
    return ctx


async def build_h3_director_plan(app: Any, context: Dict[str, Any], *args, **kwargs):
    return await _ORIGINAL_BUILD(app, _with_action_fidelity(context), *args, **kwargs)


def install_user_action_fidelity(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_user_action_fidelity_installed", False):
        return {"patched": False, "reason": "already_installed"}
    h3_director_mode.build_h3_director_plan = build_h3_director_plan
    if hasattr(app, "h3_build_director_plan"):
        app.h3_build_director_plan = build_h3_director_plan
    h3_director_mode._xiaoxia_user_action_fidelity_installed = True
    return {
        "patched": True,
        "user_subject_action_preserved": True,
        "camera_cannot_substitute_subject_action": True,
        "camera_may_support": True,
        "hardcoded_body_motion": False,
        "authoritative_scene_unchanged": True,
    }
