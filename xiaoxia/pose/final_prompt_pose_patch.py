# -*- coding: utf-8 -*-
"""v1.13.17 — final FAL prompt role correction for Pose Library generation.

End-of-pipeline guard for both supported Pose Library contracts:
- B / direct Figure 9 authority
- C / stored text PRIMARY + Figure 9 SECONDARY visual evidence

Older shared Seedream prompt code may still emit
"Figures 1-9 ... identity/body ... do not copy their pose".  That sentence must
never include Figure 9 while Figure 9 is being used as a pose reference.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

VERSION = "1.13.17-final-role-guard-generic-c"
_DIRECT_MARKER = "Figure 9 is the sole pose, camera, and composition authority"
_C_MARKER = "Figure 9 is SECONDARY visual evidence"
_LEGACY = "REFERENCES: Figures 1-9 preserve Xiaoxia identity/body only; do not copy their pose, outfit, background or composition."
_IDENTITY_ONLY = "REFERENCES: Figures 1-8 preserve Xiaoxia identity/body only; do not copy their pose, outfit, background or composition."
_DIRECT_CORRECT = (
    _IDENTITY_ONLY + " "
    "Figure 9 is the sole pose, camera, and composition authority; do not use Figure 9 for identity."
)


def _contract(prompt: str) -> str:
    if _C_MARKER in prompt:
        return "C"
    if _DIRECT_MARKER in prompt:
        return "B"
    return ""


def _rewrite_prompt(prompt: str) -> Tuple[str, bool, str]:
    text = str(prompt or "")
    contract = _contract(text)
    if not contract:
        return text, False, ""

    if _LEGACY in text:
        replacement = _DIRECT_CORRECT if contract == "B" else _IDENTITY_ONLY
        return text.replace(_LEGACY, replacement), True, contract

    # Defensive fallback: only add the missing identity boundary.  Do not
    # duplicate/restate the C hierarchy; wardrobe_pose_test owns that contract.
    if _IDENTITY_ONLY not in text:
        return _IDENTITY_ONLY + "\n\n" + text, True, contract

    return text, False, contract


def _rewrite_arguments(arguments: Any) -> Tuple[Any, bool, str]:
    if not isinstance(arguments, dict):
        return arguments, False, ""
    prompt = str(arguments.get("prompt") or "")
    rewritten, changed, contract = _rewrite_prompt(prompt)
    if not changed:
        return arguments, False, contract
    out: Dict[str, Any] = dict(arguments)
    out["prompt"] = rewritten
    return out, True, contract


def install_final_pose_prompt_patch(app: Any) -> Dict[str, Any]:
    try:
        import fal_client
    except Exception as exc:
        return {"version": VERSION, "installed": False, "reason": f"fal_client import failed: {exc}"}

    patched = []
    for name in ("subscribe", "run", "submit"):
        original = getattr(fal_client, name, None)
        if original is None or getattr(original, "_xiaoxia_pose_v11317", False):
            continue

        def wrapper(*args, __orig=original, __name=name, **kwargs):
            local_kwargs = dict(kwargs)
            changed = False
            contract = ""
            if "arguments" in local_kwargs:
                rewritten, changed, contract = _rewrite_arguments(local_kwargs.get("arguments"))
                local_kwargs["arguments"] = rewritten
            elif len(args) >= 2 and isinstance(args[1], dict):
                rewritten, changed, contract = _rewrite_arguments(args[1])
                if changed:
                    args = (args[0], rewritten, *args[2:])
            if changed:
                role = "figure9=secondary_visual" if contract == "C" else "figure9=pose_camera_composition"
                print(f"🎯 [POSE_FINAL_ROLE_GUARD_V11317] fal_method={__name} contract={contract} figures=1-8_identity {role}")
            return __orig(*args, **local_kwargs)

        wrapper._xiaoxia_pose_v11317 = True
        wrapper.__name__ = getattr(original, "__name__", name)
        setattr(fal_client, name, wrapper)
        patched.append(name)

    return {"version": VERSION, "installed": bool(patched), "patched": patched, "contracts": ["B", "C"]}
