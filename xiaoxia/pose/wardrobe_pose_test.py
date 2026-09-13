# -*- coding: utf-8 -*-
"""v1.13.11 — direct Figure 9 pose/camera/composition authority.

Figures 1-8 = Xiaoxia identity authority
Figure 9     = sole pose + camera + composition authority
Figure 10    = wardrobe authority

Pose Library metadata remains available for display/search/trace, but Camera/Pose/
Composition text is NOT translated back into the Seedream generation prompt.
"""
from __future__ import annotations

import re

VERSION = "1.13.11-direct-figure9-authority"
_STATE_KEY = "photo_pending_pose_reference"
_GENERIC_PHOTO_REQUESTS = {
    "", ".", "。", "拍一張", "拍張", "拍照", "拍照吧", "拍一張吧", "來一張", "來張", "一張", "照一張", "拍一下", "拍吧"
}


def _strip_photo_prefix(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^/photo(?:\s+|$)", "", value, flags=re.IGNORECASE).strip()
    return value


def _photo_instruction_from_context(ctx, msg) -> str:
    candidates = [ctx.get("user_input"), ctx.get("raw_scene_text"), getattr(msg, "content", "") if msg is not None else ""]
    for candidate in candidates:
        value = _strip_photo_prefix(str(candidate or ""))
        if value:
            return value
    return ""


def _is_generic_photo_instruction(text: str) -> bool:
    value = re.sub(r"[\s!！?？。,.，]+", "", str(text or "").strip()).lower()
    normalized = {re.sub(r"[\s!！?？。,.，]+", "", item).lower() for item in _GENERIC_PHOTO_REQUESTS}
    return value in normalized


def _clean_pose_scene(ctx, msg) -> tuple[str, str, bool]:
    original = str(ctx.get("authoritative_scene") or ctx.get("scene_text") or ctx.get("scene_summary") or ctx.get("prompt_base") or "").strip()
    user_instruction = _photo_instruction_from_context(ctx, msg)
    generic = _is_generic_photo_instruction(user_instruction)
    if generic:
        clean = "背景保持自然且不搶戲；Figure 9 直接決定人物姿勢、鏡頭與構圖。"
    else:
        clean = f"大俠本次指定：{user_instruction}。場景／故事需求保留；人物姿勢、鏡頭與構圖直接以 Figure 9 圖像為準。"
    return clean, original, generic


def _apply_pose_scene_authority(ctx, clean_scene: str) -> None:
    ctx["scene_text"] = clean_scene
    ctx["scene_summary"] = clean_scene
    ctx["action_summary"] = ""
    ctx["mood_summary"] = ""
    ctx["camera_framing"] = ""
    ctx["title"] = clean_scene
    ctx["render_title"] = clean_scene
    scene_data = ctx.get("scene_data")
    if isinstance(scene_data, dict):
        scene_data = dict(scene_data)
        scene_data["authoritative_scene"] = clean_scene
        scene_data["scene_summary"] = clean_scene
        scene_data["action_summary"] = ""
        scene_data["mood_summary"] = ""
        scene_data["camera_framing"] = ""
        scene_data["photo_prompt"] = clean_scene
        ctx["scene_data"] = scene_data


def install_wardrobe_pose_test(app):
    original_direct = app._handle_wardrobe_message_direct
    original_generate = app._generate_photo_from_context

    async def _direct_with_optional_pose(message):
        text = str(getattr(message, "content", "") or "").strip()
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
                state[_STATE_KEY] = {"url": url, "content_type": content_type or "image/jpeg", "wardrobe_id": m.group(1).upper(), "message_id": getattr(message, "id", None)}
                app.save_state(state)
                await message.channel.send("💃 已把附圖記為 Pose Reference。下一張 `/photo`：Figures 1-8 身分、Figure 9 姿勢/鏡頭/構圖、Figure 10 服裝。")
        return handled

    async def _generate_with_pending_pose(context, msg=None):
        state = app.load_state()
        pose = state.get(_STATE_KEY)
        if not isinstance(pose, dict) or not str(pose.get("url") or "").startswith("http"):
            return await original_generate(context, msg=msg)

        ctx = dict(context or {})
        pose_url = str(pose.get("url") or "").strip()
        pose_mime = str(pose.get("content_type") or "image/jpeg").strip() or "image/jpeg"
        wardrobe_id = str(ctx.get("wardrobe_id") or "").strip().upper()
        expected_wid = str(pose.get("wardrobe_id") or "").strip().upper()
        if expected_wid and wardrobe_id and expected_wid != wardrobe_id:
            return await original_generate(context, msg=msg)

        reference_path = ctx.get("reference_item_path") or ctx.get("reference_item_url")
        if not reference_path:
            return await original_generate(context, msg=msg)

        try:
            clean_scene, suppressed_scene, generic_request = _clean_pose_scene(ctx, msg)
            _apply_pose_scene_authority(ctx, clean_scene)

            identity_urls = await app._seedream_upload_reference_images(selected_figure_indexes=[1, 2, 3, 4, 5, 6, 7, 8])
            input_urls = list(identity_urls[:8])
            roles = [{"figure": i + 1, "role": "xiaoxia_identity", "source_figure": i + 1, "url": url} for i, url in enumerate(input_urls)]

            input_urls.append(pose_url)
            roles.append({"figure": 9, "role": "pose_camera_composition_reference", "url": pose_url})

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
            ctx["pose_reference_url"] = pose_url
            ctx["pose_reference_mime_type"] = pose_mime

            # Metadata is still read so the library/trace remains useful, but none of
            # Camera / Visible / Pose / Composition text is sent to Seedream.
            analysis = {}
            analysis_builder = getattr(app, "build_pose_reference_analysis", None)
            if callable(analysis_builder):
                try:
                    analysis = await analysis_builder(ctx) or {}
                except Exception as exc:
                    print(f"⚠️ [POSE_REFERENCE_ANALYSIS_CALL_FAILED] {type(exc).__name__}: {exc}")

            camera_intent = str(analysis.get("camera_intent") or "").strip() if isinstance(analysis, dict) else ""
            visible_scope = str(analysis.get("visible_pose_scope") or "").strip() if isinstance(analysis, dict) else ""
            pose_description = str(analysis.get("pose_description") or "").strip() if isinstance(analysis, dict) else ""
            composition_feature = str(analysis.get("composition_feature") or "").strip() if isinstance(analysis, dict) else ""
            ctx["pose_camera_intent"] = camera_intent
            ctx["pose_visible_scope"] = visible_scope
            ctx["pose_visible_description"] = pose_description
            ctx["pose_composition_feature"] = composition_feature

            pose_rule = (
                "REFERENCE ROLE CONTRACT — Figures 1-8 define Xiaoxia identity only. "
                "Figure 9 is the sole pose, camera, and composition authority; reproduce its visible body arrangement, viewpoint, framing, crop, and subject-to-camera spatial relationship directly from the image. "
                "Do not use Figure 9 for identity and do not copy its clothing, background, or lighting. "
                "Figure 10 defines wardrobe only; do not let Figure 10 change pose, camera, composition, or identity."
            )

            try:
                channel = getattr(msg, "channel", None) if msg is not None else None
                if channel is None:
                    channel = ctx.get("channel")
                if channel is not None and hasattr(channel, "send"):
                    await channel.send(
                        "🎯 **Figure 9 直接控制 → Seedream**\n"
                        "Camera / Pose / Composition metadata：`僅紀錄，不送 Seedream`"
                    )
            except Exception as exc:
                print(f"⚠️ [POSE_DIRECT_ECHO_FAILED] {type(exc).__name__}: {exc}")

            print(
                f"🧩 [POSE_METADATA_TRACE_ONLY_V11311] camera={camera_intent!r} scope={visible_scope!r} "
                f"pose={pose_description!r} composition={composition_feature!r}"
            )
            ctx["authoritative_scene"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["prompt_base"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["pose_public_scene"] = clean_scene
            ctx["pose_suppressed_scene"] = suppressed_scene
            ctx["pose_generic_photo_request"] = generic_request
            ctx["wardrobe_pose_test"] = True
            ctx["wardrobe_pose_test_version"] = VERSION
            ctx["pose_generation_contract"] = "figure9_direct_pose_camera_composition_authority"

            print(
                f"🎬 [POSE_AUTHORITY_DIRECT_V11311] generic={generic_request} "
                f"inputs={len(input_urls[:10])} metadata_to_seedream=false"
            )
            return await original_generate(ctx, msg=msg)
        finally:
            latest = app.load_state()
            latest[_STATE_KEY] = None
            app.save_state(latest)

    app._handle_wardrobe_message_direct = _direct_with_optional_pose
    app._generate_photo_from_context = _generate_with_pending_pose
    return {
        "version": VERSION,
        "mode": "figure9_direct_pose_camera_composition_authority_v45",
        "one_shot": True,
        "metadata_to_seedream": False,
        "debug_echo": True,
    }
