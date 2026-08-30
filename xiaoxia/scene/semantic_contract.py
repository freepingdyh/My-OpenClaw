# -*- coding: utf-8 -*-
"""v1.12.05 photo semantic-contract repair.

Goal:
- keep the architecture unchanged: authoritative_scene remains the only visual truth.
- do NOT add a second prompt source for Seedream.
- prevent /photo-family flows from accidentally overwriting the final semantic
  contract with a legacy pose-critical/minimal prompt before Seedream runs.

This patch is intentionally surgical:
1. patch only the _generate_photo_from_context boundary;
2. rebuild prompt_base/root_prompt_base from authoritative_scene;
3. preserve downstream auxiliary blocks (wardrobe / freestyle / background ref);
4. force semantic_contract_locked=True so _execute_safe_generation_core sends the
   rebuilt title+scene contract directly to Seedream.
"""
from __future__ import annotations

_APP = None
_ORIGINAL_GENERATE_PHOTO_FROM_CONTEXT = None

PHOTO_SSOT_MODES = {"photo_scene", "photo_reference", "travel", "shopping", "world", "scene"}
_SUFFIX_MARKERS = (
    "\n\nFREESTYLE OUTFIT MODE:",
    "\n\nWARDROBE REFERENCE OVERRIDE:",
    "\n\nREAL BACKGROUND PHOTO REFERENCE:\n",
)


def _clean(value):
    app = _APP
    if app is None:
        return str(value or "").strip()
    return app._clean_text_compact(value or "")


def _source_mode_of(context):
    return str(
        context.get("source_mode")
        or context.get("mode")
        or context.get("type")
        or ""
    ).strip().lower()


def _extract_suffix(prompt_text):
    text = str(prompt_text or "")
    if not text:
        return ""
    indices = [idx for marker in _SUFFIX_MARKERS if (idx := text.find(marker)) >= 0]
    if not indices:
        return ""
    return text[min(indices):].strip()


def _render_module_for_context(context):
    source_mode = _source_mode_of(context)
    world_mode = str(context.get("world_mode") or "").strip().lower()
    if source_mode == "travel" or world_mode == "travel":
        return "travel"
    return "photo"


def _resolve_authoritative_scene(context):
    scene_data = context.get("scene_data") if isinstance(context.get("scene_data"), dict) else {}
    return _clean(
        context.get("authoritative_scene")
        or scene_data.get("authoritative_scene")
        or context.get("scene_text")
        or context.get("scene_summary")
        or ""
    )


def _rebuild_prompt_base(context):
    app = _APP
    old_prompt = str(context.get("prompt_base") or context.get("root_prompt_base") or "").strip()
    scene = _resolve_authoritative_scene(context)
    if not scene or app is None:
        return old_prompt

    title = _clean(context.get("title") or context.get("scene_summary") or "這一刻") or "這一刻"
    module = _render_module_for_context(context)
    base = app._compose_title_scene_render_prompt(module, title, scene)
    suffix = _extract_suffix(old_prompt)
    rebuilt = (base + ("\n" + suffix if suffix else "")).strip()
    return rebuilt or old_prompt or scene


async def _generate_photo_from_context_semantic_contract(context, msg=None):
    original = _ORIGINAL_GENERATE_PHOTO_FROM_CONTEXT
    if original is None:
        raise RuntimeError("original _generate_photo_from_context is not installed")

    if not isinstance(context, dict):
        return await original(context, msg=msg)

    source_mode = _source_mode_of(context)
    if source_mode not in PHOTO_SSOT_MODES:
        return await original(context, msg=msg)

    new_context = dict(context)
    authoritative_scene = _resolve_authoritative_scene(new_context)
    if authoritative_scene:
        rebuilt_prompt = _rebuild_prompt_base(new_context)
        new_context["authoritative_scene"] = authoritative_scene
        new_context["scene_text"] = authoritative_scene
        new_context["prompt_base"] = rebuilt_prompt
        new_context["root_prompt_base"] = rebuilt_prompt
        new_context["force_minimal_prompt"] = False

        trace_context = dict(new_context.get("__trace_context") or {})
        trace_context["semantic_contract_locked"] = True
        trace_context["semantic_contract"] = rebuilt_prompt
        trace_context["authoritative_scene"] = authoritative_scene
        trace_context["scene_seed_text"] = authoritative_scene
        trace_context["force_minimal_prompt"] = False
        trace_context["raw_seedream_mode"] = "title_scene_semantic_contract_direct"
        new_context["__trace_context"] = trace_context

        print(
            "🧩 [V11205_PHOTO_SEMANTIC_CONTRACT_REBUILT] "
            f"source_mode={source_mode} "
            f"scene_len={len(authoritative_scene)} "
            f"prompt_len={len(rebuilt_prompt)}"
        )

    return await original(new_context, msg=msg)



def install_photo_semantic_contract_repair(app):
    """Patch /photo-family generation to stop legacy prompt minimization override."""
    global _APP, _ORIGINAL_GENERATE_PHOTO_FROM_CONTEXT
    _APP = app

    existing = getattr(app, "_generate_photo_from_context", None)
    if existing is None:
        raise RuntimeError("_generate_photo_from_context not found")

    if getattr(existing, "_scene_ssot_v11205", False):
        return {
            "module": "xiaoxia.scene.semantic_contract",
            "patched": "_generate_photo_from_context",
            "scene_ssot": "authoritative_scene",
            "already_installed": True,
        }

    _ORIGINAL_GENERATE_PHOTO_FROM_CONTEXT = existing
    _generate_photo_from_context_semantic_contract._scene_ssot_v11205 = True
    _generate_photo_from_context_semantic_contract._scene_ssot_original = existing
    app._V11205_ORIGINAL_GENERATE_PHOTO_FROM_CONTEXT = existing
    app._generate_photo_from_context = _generate_photo_from_context_semantic_contract

    return {
        "module": "xiaoxia.scene.semantic_contract",
        "patched": "_generate_photo_from_context",
        "scene_ssot": "authoritative_scene",
        "already_installed": False,
    }
