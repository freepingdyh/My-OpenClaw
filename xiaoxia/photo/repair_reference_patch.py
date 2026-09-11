# -*- coding: utf-8 -*-
"""Minimal/local repair reference policy.

Repair is not a new synthesis pass. Keep the completed photo as the dominant
visual source and use only two Xiaoxia identity anchors. The prompt explicitly
allows local anatomy correction so a malformed limb is not preserved merely
because the source photo is otherwise authoritative.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

PATCH_VERSION = "1.12.06bf"
_REPAIR_SIGNATURE = "Image 10 is the current completed photo to repair"
_SCENE_MARKER = "TITLE + SCENE CONTRACT:"


def _rewrite_prompt(prompt: str) -> str:
    text = str(prompt or "")
    if _REPAIR_SIGNATURE not in text:
        return text

    # Keep the legacy tail because it contains the user's actual repair request,
    # but replace the heavy identity/body preamble with a repair-specific contract.
    tail = ""
    if _SCENE_MARKER in text:
        tail = text[text.index(_SCENE_MARKER):].strip()

    head = (
        "REPAIR CONTRACT — this is a local correction of an already completed photo, not a new photo.\n"
        "Figure 1 is the PRIMARY SOURCE PHOTO. Preserve its recognizable Xiaoxia, hairstyle, outfit, garment details, "
        "background, props, lighting, camera viewpoint, crop, composition, and overall pose.\n"
        "Figures 2-3 are IDENTITY ANCHORS ONLY. Use them only if needed to keep Xiaoxia recognizable; never copy their "
        "pose, clothing, background, camera, or composition.\n"
        "USER REPAIR REQUEST IS AUTHORITATIVE FOR THE DEFECT. Correct the requested defect even when doing so requires "
        "changing the malformed local pixels or local limb geometry already present in Figure 1. Do not preserve an "
        "anatomical error merely because Figure 1 is the source authority.\n"
        "For anatomy repairs, restore plausible human joint structure, limb length, left/right continuity, hand/foot "
        "attachment, bend direction, foreshortening, support/contact, and occlusion while keeping the same intended pose "
        "and camera viewpoint. Change only the defective body region and the smallest immediately connected area needed "
        "for anatomical continuity.\n"
        "Do not restage the subject, change the pose category, move her to another place, change the camera, redesign the "
        "outfit, beautify unrelated areas, or invent a new scene. Everything outside the requested repair region should "
        "remain visually as close to Figure 1 as possible."
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
            # Legacy order: identity 1..9 + completed photo 10.
            # Repair order: source photo + two identity anchors.
            out[key] = [refs[-1], refs[0], refs[1]]
            changed = True
            break

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
        if original is None:
            continue
        # bc may already have wrapped this callable earlier in the runtime chain.
        # Wrap it once more with bf so the final request receives the newer contract.
        if getattr(original, "_xiaoxia_repair_bf", False):
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
                print(f"🩹 [REPAIR_REF_BF] fal_method={__name} refs=3 mode=local_anatomy_aware")
            return __orig(*args, **local_kwargs)

        wrapper._xiaoxia_repair_bf = True
        wrapper.__name__ = getattr(original, "__name__", name)
        setattr(fal_client, name, wrapper)
        patched.append(name)

    return {"version": PATCH_VERSION, "installed": bool(patched), "patched": patched}
