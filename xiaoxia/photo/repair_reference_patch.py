# -*- coding: utf-8 -*-
"""Repair reference slimming for v1.12.06bc.

The legacy PhotoRepairModal builds a 10-reference repair request: nine Xiaoxia
identity images plus the completed photo.  Repair is an edit operation, not a new
character synthesis pass, so this patch intercepts only that recognisable repair
request at the fal_client boundary and reduces it to:

  Figure 1 = completed photo (primary repair/source authority)
  Figure 2-3 = two Xiaoxia identity anchors (identity only)

All other fal requests are left untouched.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

PATCH_VERSION = "1.12.06bc"
_REPAIR_SIGNATURE = "Image 10 is the current completed photo to repair"
_SCENE_MARKER = "TITLE + SCENE CONTRACT:"


def _rewrite_prompt(prompt: str) -> str:
    text = str(prompt or "")
    if _REPAIR_SIGNATURE not in text:
        return text
    tail = ""
    if _SCENE_MARKER in text:
        tail = text[text.index(_SCENE_MARKER):].strip()
    head = (
        "FIGURE ROLES: Figure 1 is the current completed Xiaoxia photo and is the PRIMARY REPAIR AUTHORITY. "
        "Preserve Figure 1's face appearance, hairstyle, body appearance, outfit, pose, camera framing, scene, "
        "lighting, props, and composition except for the specific defect the user asks to repair. "
        "Figures 2-3 are Xiaoxia IDENTITY ANCHORS ONLY; use them only to prevent identity drift. "
        "Do not copy their clothing, pose, camera, background, body proportions, or composition. "
        "Make the smallest local correction necessary; do not redesign or restage the photo."
    )
    return head + (("\n\n" + tail) if tail else "")


def _rewrite_arguments(arguments: Any) -> Tuple[Any, bool]:
    if not isinstance(arguments, dict):
        return arguments, False
    prompt = str(arguments.get("prompt") or "")
    if _REPAIR_SIGNATURE not in prompt:
        return arguments, False

    out: Dict[str, Any] = dict(arguments)
    changed = False
    for key in ("image_urls", "images"):
        value = out.get(key)
        if isinstance(value, (list, tuple)) and len(value) >= 10:
            refs = list(value)
            # Legacy order is identity 1..9 + completed photo 10.
            out[key] = [refs[-1], refs[0], refs[1]]
            changed = True
            break

    # Defensive support for wrappers that name a list `image`.
    if not changed:
        value = out.get("image")
        if isinstance(value, (list, tuple)) and len(value) >= 10:
            refs = list(value)
            out["image"] = [refs[-1], refs[0], refs[1]]
            changed = True

    out["prompt"] = _rewrite_prompt(prompt)
    return out, changed


def install_repair_reference_patch(app: Any) -> Dict[str, Any]:
    try:
        import fal_client
    except Exception as exc:
        return {"version": PATCH_VERSION, "installed": False, "reason": f"fal_client import failed: {exc}"}

    patched = []
    for name in ("subscribe", "run", "submit"):
        original = getattr(fal_client, name, None)
        if original is None or getattr(original, "_xiaoxia_repair_bc", False):
            continue

        def wrapper(*args, __orig=original, __name=name, **kwargs):
            # fal_client commonly receives arguments={...}; support positional
            # arguments dict as well without changing unrelated calls.
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
                print(f"🩹 [REPAIR_REF_BC] fal_method={__name} refs=3 source=completed_photo identity_anchors=2")
            return __orig(*args, **local_kwargs)

        wrapper._xiaoxia_repair_bc = True
        wrapper.__name__ = getattr(original, "__name__", name)
        setattr(fal_client, name, wrapper)
        patched.append(name)

    return {"version": PATCH_VERSION, "installed": bool(patched), "patched": patched}
