# -*- coding: utf-8 -*-
"""v1.12.06ap — optional Pose Reference for `/衣櫃 穿 Wxxx`.

Experiment contract:
  Figures 1-8 = Xiaoxia identity authority
  Figure 9     = user pose authority
  Figure 10    = selected Wxxx outfit authority

Without an attachment the existing wardrobe/photo path is untouched.
"""
from __future__ import annotations

import re

VERSION = "1.12.06ap"
_STATE_KEY = "photo_pending_pose_reference"


def install_wardrobe_pose_test(app):
    original_direct = app._handle_wardrobe_message_direct
    original_generate = app._generate_photo_from_context

    async def _direct_with_optional_pose(message):
        text = str(getattr(message, "content", "") or "").strip()
        # Accept both `/衣櫃 穿 W001` and `/衣櫃穿 W001` forms already supported by the bot.
        m = re.match(r"^/衣櫃\s*穿\s+(W\d{3,4})\b", text, flags=re.IGNORECASE)
        attachments = list(getattr(message, "attachments", None) or [])
        pose_attachment = attachments[0] if (m and attachments) else None

        handled = await original_direct(message)

        if pose_attachment is not None:
            url = str(getattr(pose_attachment, "url", "") or "").strip()
            content_type = str(getattr(pose_attachment, "content_type", "") or "").lower()
            filename = str(getattr(pose_attachment, "filename", "") or "").lower()
            looks_image = content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp"))
            if url and looks_image:
                state = app.load_state()
                state[_STATE_KEY] = {
                    "url": url,
                    "wardrobe_id": m.group(1).upper(),
                    "message_id": getattr(message, "id", None),
                }
                app.save_state(state)
                await message.channel.send(
                    "💃 已把這張附圖記為 **Pose Reference**。下一張 `/photo` 會測試："
                    "**8 張小俠 Identity + Pose + Wxxx 衣服 → Seedream V4.5**。"
                )
        return handled

    async def _generate_with_pending_pose(context, msg=None):
        state = app.load_state()
        pose = state.get(_STATE_KEY)
        if not isinstance(pose, dict) or not str(pose.get("url") or "").startswith("http"):
            return await original_generate(context, msg=msg)

        ctx = dict(context or {})
        pose_url = str(pose.get("url") or "").strip()
        wardrobe_id = str(ctx.get("wardrobe_id") or "").strip().upper()
        expected_wid = str(pose.get("wardrobe_id") or "").strip().upper()

        # Never apply a stale pose to another outfit/request.
        if expected_wid and wardrobe_id and expected_wid != wardrobe_id:
            return await original_generate(context, msg=msg)

        reference_path = ctx.get("reference_item_path") or ctx.get("reference_item_url")
        if not reference_path:
            return await original_generate(context, msg=msg)

        try:
            identity_urls = await app._seedream_upload_reference_images(
                selected_figure_indexes=[1, 2, 3, 4, 5, 6, 7, 8]
            )
            input_urls = list(identity_urls[:8])
            roles = [
                {"figure": i + 1, "role": "xiaoxia_identity", "source_figure": i + 1, "url": url}
                for i, url in enumerate(input_urls)
            ]

            # Figure 9 = pose authority.
            input_urls.append(pose_url)
            roles.append({"figure": 9, "role": "pose_reference_only", "url": pose_url})

            # Figure 10 = wardrobe authority.
            if str(reference_path).startswith("http"):
                outfit_url = str(reference_path)
            else:
                outfit_url = await app._seedream_upload_single_file(reference_path)
            input_urls.append(outfit_url)
            roles.append({"figure": 10, "role": "wardrobe_reference", "url": outfit_url})

            ctx["seedream_input_images_override"] = input_urls[:10]
            ctx["seedream_input_image_roles_override"] = roles[:10]
            ctx["seedream_identity_selected_figures"] = [1, 2, 3, 4, 5, 6, 7, 8]
            ctx["figure10_present"] = True
            ctx["seedream_model_id"] = getattr(app, "SEEDREAM_V45_MODEL_ID", "fal-ai/bytedance/seedream/v4.5/edit")

            pose_rule = (
                "POSE AUTHORITY — Figure 9 is pose/camera reference ONLY. Reproduce Figure 9's distinctive pose as faithfully as possible: "
                "preserve body pose, joint positions, hand and foot placement, torso lean and twist, pelvis orientation, hip placement and silhouette, "
                "weight distribution, head direction, camera angle, camera height, crop/framing, and support-surface relationship. "
                "Do NOT copy Figure 9's person identity, face, hair, clothing, body identity, or background. "
                "Figures 1-8 are the ONLY authority for Xiaoxia's identity and established tall/slim body identity. "
                "Figure 10 is the ONLY authority for the requested wardrobe item. "
                "Do not average, redesign, beautify, or reinterpret the pose into a generic pose; preserve the visual feature that makes Figure 9 distinctive."
            )
            base_scene = str(ctx.get("authoritative_scene") or ctx.get("prompt_base") or "").strip()
            ctx["authoritative_scene"] = (base_scene + "\n\n" + pose_rule).strip()
            ctx["prompt_base"] = (str(ctx.get("prompt_base") or base_scene).strip() + "\n\n" + pose_rule).strip()
            ctx["wardrobe_pose_test"] = True
            ctx["wardrobe_pose_test_version"] = VERSION

            print(
                f"💃 [WARDROBE_POSE_TEST] version={VERSION} wardrobe={wardrobe_id or expected_wid} "
                f"inputs={len(input_urls[:10])} roles=8_identity+pose+wardrobe model=v4.5"
            )
            return await original_generate(ctx, msg=msg)
        finally:
            # One-shot: whether generation succeeds or fails, never leak the pose into a later photo.
            latest = app.load_state()
            latest[_STATE_KEY] = None
            app.save_state(latest)

    app._handle_wardrobe_message_direct = _direct_with_optional_pose
    app._generate_photo_from_context = _generate_with_pending_pose
    return {"version": VERSION, "mode": "8_identity_plus_pose_plus_wardrobe_v45", "one_shot": True}
