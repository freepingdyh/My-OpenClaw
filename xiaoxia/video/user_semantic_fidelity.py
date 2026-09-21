# -*- coding: utf-8 -*-
"""v1.12.06ac — concise semantic fidelity for user-directed /影片.

Gemini is a director-translator: understand Daxia's intended scene as-is, then express
that same intent as one concise, visually executable 10-second direction for H3.
The downstream H3 prompt stays compact; this module only shapes the Director's job.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import h3_director_mode

_ORIGINAL_BUILD = h3_director_mode.build_h3_director_plan


def _with_semantic_fidelity(context: Dict[str, Any]) -> Dict[str, Any]:
    ctx = dict(context or {})
    direction = str(ctx.get("video_user_direction") or "").strip()
    if not direction:
        return ctx

    existing = str(ctx.get("message") or "").strip()
    brief = (
        "\n\n【DIRECTOR ROLE】\n"
        "You are the director-translator between Daxia and H3. Understand Daxia's intended scene as-is, "
        "then express that same intent as one concise, visually executable 10-second video direction for H3. "
        "Preserve the meaning, mood, and physical action of his idea while naturally adapting only what is needed "
        "to make it work from the starting image. Keep the final Hero Action / Reaction / Camera plan simple and clean.\n"
        f"Daxia's intended scene: {direction}"
    )
    ctx["message"] = existing + brief
    ctx["video_semantic_fidelity"] = True
    return ctx


async def build_h3_director_plan(app: Any, context: Dict[str, Any], *args, **kwargs):
    return await _ORIGINAL_BUILD(app, _with_semantic_fidelity(context), *args, **kwargs)


def install_user_semantic_fidelity(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_user_semantic_fidelity_installed", False):
        return {"patched": False, "reason": "already_installed"}

    h3_director_mode.build_h3_director_plan = build_h3_director_plan
    if hasattr(app, "h3_build_director_plan"):
        app.h3_build_director_plan = build_h3_director_plan
    h3_director_mode._xiaoxia_user_semantic_fidelity_installed = True

    return {
        "patched": True,
        "director_role": "faithful translator",
        "user_intent_authoritative": True,
        "compact_h3_plan": True,
        "authoritative_scene_unchanged": True,
    }
