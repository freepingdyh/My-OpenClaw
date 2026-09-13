# -*- coding: utf-8 -*-
"""v1.12.06w — preserve scene mood/body-language intent for H3 Director.

This does not hard-code leg/hip actions. It gives Gemini permission to read an
adult scene's existing elegant/sensual/alluring intent and choose one coherent
whole-body Hero Action when the starting frame supports it.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import h3_director_mode


_EXTRA_DIRECTOR_RULES = """
9. Preserve the emotional and body-language intent already present in the authoritative scene. If the scene is elegant, alluring, sensual, flirtatious, glamorous, seductive, coolly enchanting, or otherwise deliberately魅惑／性感／嫵媚, do not neutralize that mood into generic standing and upper-body swaying. Direct the performance to express that same non-explicit adult mood naturally.
10. Think in whole-body performance when the framing supports it: posture, weight shift, a step or turn, shoulders, waist, hips, legs, hands, gaze, garment/cape/skirt movement, and interaction with visible props are all available choices. Select only what serves the scene and Hero Action; do NOT force any particular body part to move.
11. For a slit dress, flowing skirt, cape, fitted costume, heels, or other visible styling, you may use physically natural movement that lets the existing design read on camera, but never change the outfit or manufacture exposure that is not already present in Image 1.
12. "dynamic" means a clearly readable action with meaningful body displacement or pose evolution when appropriate; it should not collapse into only blinking, breathing, hair flutter, or a tiny torso sway. Identity stability and physical coherence still outrank motion size.
""".strip()


def install_sensual_motion_director(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_sensual_motion_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original = h3_director_mode.build_h3_director_plan

    async def mood_aware_plan(app_module: Any, context: Dict[str, Any], cfg: Dict[str, Any]):
        # Do not rewrite authoritative_scene. Add a Director-only hint so the same
        # Gemini still makes the creative decision from the original scene.
        ctx = dict(context or {})
        existing = str(ctx.get("message") or "").strip()
        hint = (
            "H3 Director creative guidance (not a literal action command): "
            "Preserve the scene's existing mood and sensual/elegant/alluring body-language intent when present. "
            "If framing supports it, prefer one coherent whole-body action over generic upper-body swaying. "
            "Choose naturally from posture, weight shift, step/turn, waist/hips/legs, hands, gaze and garment motion; "
            "do not force any body part and do not invent exposure or change clothing. "
            "For dynamic motion, make the action visibly evolve while protecting identity."
        )
        ctx["message"] = f"{existing}\n{hint}".strip()
        plan = await original(app_module, ctx, cfg)
        # Persist only the actual Director result, not our temporary hint/context copy.
        context["h3_director_plan"] = dict(plan)
        context["h3_video_theme"] = plan.get("video_theme", "")
        context["h3_motion_level"] = plan.get("motion_level", "")
        return plan

    h3_director_mode.build_h3_director_plan = mood_aware_plan
    # Runtime callers use this exported seam after Director install.
    if hasattr(app, "h3_build_director_plan"):
        app.h3_build_director_plan = lambda context: mood_aware_plan(app, context, h3_director_mode.voiceover_mode._config())

    h3_director_mode._xiaoxia_sensual_motion_installed = True
    return {
        "patched": True,
        "scene_mood_preserved": True,
        "sensual_alluring_allowed": True,
        "whole_body_reasoning": True,
        "hardcoded_leg_motion": False,
        "dynamic_requires_readable_motion": True,
        "authoritative_scene_unchanged": True,
    }
