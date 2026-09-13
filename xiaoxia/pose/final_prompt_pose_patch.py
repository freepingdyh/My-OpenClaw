# -*- coding: utf-8 -*-
"""v1.13.11 — final FAL prompt role correction for Pose Library generation.

This is an end-of-pipeline guard. Older shared Seedream prompt code may still emit
"Figures 1-9 ... identity/body ... do not copy their pose". When the v1.13.11
Figure-9 direct pose marker is present, rewrite that legacy role statement before
the request reaches FAL.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

VERSION = "1.13.11-final-role-guard"
_MARKER = "Figure 9 is the sole pose, camera, and composition authority"
_LEGACY = "REFERENCES: Figures 1-9 preserve Xiaoxia identity/body only; do not copy their pose, outfit, background or composition."
_CORRECT = (
    "REFERENCES: Figures 1-8 preserve Xiaoxia identity/body only; do not copy their pose, outfit, background or composition. "
    "Figure 9 is the sole pose, camera, and composition authority; do not use Figure 9 for identity."
)


def _rewrite_prompt(prompt: str) -> Tuple[str, bool]:
    text = str(prompt or "")
    if _MARKER not in text:
        return text, False

    changed = False
    if _LEGACY in text:
        text = text.replace(_LEGACY, _CORRECT)
        changed = True
    elif not text.startswith(_CORRECT):
        # Defensive fallback if the older shared preamble changes wording later.
        text = _CORRECT + "\n\n" + text
        changed = True
    return text, changed


def _rewrite_arguments(arguments: Any) -> Tuple[Any, bool]:
    if not isinstance(arguments, dict):
        return arguments, False
    prompt = str(arguments.get("prompt") or "")
    rewritten, changed = _rewrite_prompt(prompt)
    if not changed:
        return arguments, False
    out: Dict[str, Any] = dict(arguments)
    out["prompt"] = rewritten
    return out, True


def install_final_pose_prompt_patch(app: Any) -> Dict[str, Any]:
    try:
        import fal_client
    except Exception as exc:
        return {"version": VERSION, "installed": False, "reason": f"fal_client import failed: {exc}"}

    patched = []
    for name in ("subscribe", "run", "submit"):
        original = getattr(fal_client, name, None)
        if original is None or getattr(original, "_xiaoxia_pose_v11311", False):
            continue

        def wrapper(*args, __orig=original, __name=name, **kwargs):
            local_kwargs = dict(kwargs)
            changed = False
            if "arguments" in local_kwargs:
                rewritten, changed = _rewrite_arguments(local_kwargs.get("arguments"))
                local_kwargs["arguments"] = rewritten
            elif len(args) >= 2 and isinstance(args[1], dict):
                rewritten, changed = _rewrite_arguments(args[1])
                if changed:
                    args = (args[0], rewritten, *args[2:])
            if changed:
                print(f"🎯 [POSE_FINAL_ROLE_GUARD] fal_method={__name} figures=1-8_identity figure9=pose_camera_composition")
            return __orig(*args, **local_kwargs)

        wrapper._xiaoxia_pose_v11311 = True
        wrapper.__name__ = getattr(original, "__name__", name)
        setattr(fal_client, name, wrapper)
        patched.append(name)

    return {"version": VERSION, "installed": bool(patched), "patched": patched}
