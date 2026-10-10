# -*- coding: utf-8 -*-
"""Seedream photo prompt boundary.

Keeps the legacy builder as the source for ordinary photo flows, but gives Pose
Library its own explicit figure-role contract before the request reaches FAL.
This removes the need to repair the legacy Figures 1-9 identity sentence at the
provider boundary.
"""
from __future__ import annotations

VERSION = "1.13.23-root-pose-role-builder-signature-sync"


def install_seedream_photo_prompt_boundary(app):
    legacy_builder = app._seedream_photo_prompt

    def _builder(
        custom_prompt,
        has_reference=False,
        current_outfit=None,
        visual_checklist=None,
        semantic_contract_locked=False,
        input_image_roles=None,
        **kwargs,
    ):
        prompt = legacy_builder(
            custom_prompt,
            has_reference=has_reference,
            current_outfit=current_outfit,
            visual_checklist=visual_checklist,
            semantic_contract_locked=semantic_contract_locked,
            input_image_roles=input_image_roles,
            **kwargs,
        )

        ctx = getattr(app, "_xiaoxia_seedream_prompt_context", None)
        if not isinstance(ctx, dict) or not ctx.get("wardrobe_pose_test"):
            return prompt

        pose_contract = str(ctx.get("pose_generation_contract") or "")
        if not pose_contract:
            return prompt

        old_locked = (
            "REFERENCES: Figures 1-9 preserve Xiaoxia identity/body only; "
            "do not copy their pose, outfit, background or composition."
        )
        old_general = (
            "Figures 1-9 are identity-only references for Xiaoxia. Apply their face/body identity only to Xiaoxia. "
            "Do not copy their pose, outfit, background, lighting, or composition."
        )
        pose_roles = (
            "REFERENCES — POSE LIBRARY ROLE MAP: Figures 1-8 preserve Xiaoxia identity/body only; "
            "do not copy their pose, outfit, background or composition. "
            "Figure 9 is pose/camera/composition visual evidence only; never use Figure 9 for identity, clothing, background or lighting."
        )
        figure10_explicit = any(
            isinstance(x, dict)
            and str(x.get("figure")) == "10"
            and str(x.get("role") or "") == "wardrobe_reference"
            for x in (input_image_roles or [])
        )
        if figure10_explicit:
            pose_roles += (
                " Figure 10 is clothing / visible fashion-accessory authority only; "
                "it must not change pose, camera, composition, identity or background."
            )

        rewritten = prompt.replace(old_locked, pose_roles).replace(old_general, pose_roles)
        if rewritten == prompt:
            print("❌ [POSE_ROOT_ROLE_BUILDER] legacy identity sentence not found; refusing silent fallback")
        elif "Figures 1-9 preserve Xiaoxia identity/body only" in rewritten or "Figures 1-9 are identity-only references" in rewritten:
            print("❌ [POSE_ROOT_ROLE_BUILDER] legacy Figure 1-9 role survived rewrite")
        else:
            print(
                f"✅ [POSE_ROOT_ROLE_BUILDER] version={VERSION} "
                f"figure10={str(bool(figure10_explicit)).lower()} contract={pose_contract}"
            )
        return rewritten

    app._seedream_photo_prompt = _builder
    return {"version": VERSION, "legacy_builder_preserved_for_non_pose": True}
