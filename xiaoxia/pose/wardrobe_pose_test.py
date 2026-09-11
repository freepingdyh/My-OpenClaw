# -*- coding: utf-8 -*-
"""v1.12.06bd — Pose Geometry Authority + Camera framing authority.

Experiment contract:
  Figures 1-8 = Xiaoxia identity authority
  Figure 9     = pose geometry authority for all geometry visible in the image
  Figure 10    = selected Wxxx outfit authority within the requested framing
  Camera       = concise Gemini description OBSERVED from Figure 9

When a pending Pose Reference exists, the old /photo scene director is not allowed
to silently dictate action, gaze, shot size, camera framing, or an invented location.
Generic `/photo`, `/photo 拍照`, `/photo 拍一張` style requests are recognized from
the original context input, not only from the transient Discord message object.
"""
from __future__ import annotations

import re

VERSION = "1.12.06bd-pose-geometry-authority"
_STATE_KEY = "photo_pending_pose_reference"
_GENERIC_PHOTO_REQUESTS = {
    "", ".", "。", "拍一張", "拍張", "拍照", "拍照吧", "拍一張吧", "來一張", "來張", "一張", "照一張", "拍一下", "拍吧"
}


def _strip_photo_prefix(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^/photo(?:\s+|$)", "", value, flags=re.IGNORECASE).strip()
    return value


def _photo_instruction_from_context(ctx, msg) -> str:
    candidates = [
        ctx.get("user_input"),
        ctx.get("raw_scene_text"),
        getattr(msg, "content", "") if msg is not None else "",
    ]
    for candidate in candidates:
        value = _strip_photo_prefix(str(candidate or ""))
        if value:
            return value
    return ""


def _is_generic_photo_instruction(text: str) -> bool:
    value = re.sub(r"[\s!！?？。,.，]+", "", str(text or "").strip()).lower()
    normalized = {
        re.sub(r"[\s!！?？。,.，]+", "", item).lower()
        for item in _GENERIC_PHOTO_REQUESTS
    }
    return value in normalized


def _clean_pose_scene(ctx, msg) -> tuple[str, str, bool]:
    """Return (clean_scene, original_generated_scene, generic_request)."""
    original = str(
        ctx.get("authoritative_scene")
        or ctx.get("scene_text")
        or ctx.get("scene_summary")
        or ctx.get("prompt_base")
        or ""
    ).strip()
    user_instruction = _photo_instruction_from_context(ctx, msg)
    generic = _is_generic_photo_instruction(user_instruction)

    if generic:
        clean = (
            "背景保持自然且不搶戲；不要自行指定特定地點、活動、人物動作、視線、景別或鏡位。"
            "人物姿勢以 Figure 9 的整體可見姿勢幾何為準，取景與景別以 Camera 指令為準。"
        )
    else:
        clean = (
            f"大俠本次指定：{user_instruction}。"
            "只把這段文字當作場景／故事需求；人物姿勢以 Figure 9 的整體可見姿勢幾何為準，"
            "取景與景別以 Camera 指令為準。"
        )
    return clean, original, generic


def _apply_pose_scene_authority(ctx, clean_scene: str) -> None:
    """Remove upstream action/framing authority before the Seedream prompt is built."""
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
                state[_STATE_KEY] = {
                    "url": url,
                    "content_type": content_type or "image/jpeg",
                    "wardrobe_id": m.group(1).upper(),
                    "message_id": getattr(message, "id", None),
                }
                app.save_state(state)
                await message.channel.send(
                    "💃 已把這張附圖記為 **Pose Reference**。下一張 `/photo` 會測試："
                    "**8 張小俠 Identity + Pose Geometry + Wxxx 衣服 + Gemini 看圖取景 → Seedream V4.5**。"
                )
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

            identity_urls = await app._seedream_upload_reference_images(
                selected_figure_indexes=[1, 2, 3, 4, 5, 6, 7, 8]
            )
            input_urls = list(identity_urls[:8])
            roles = [
                {"figure": i + 1, "role": "xiaoxia_identity", "source_figure": i + 1, "url": url}
                for i, url in enumerate(input_urls)
            ]

            input_urls.append(pose_url)
            roles.append({"figure": 9, "role": "pose_geometry_reference", "url": pose_url})

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

            analysis = {}
            analysis_builder = getattr(app, "build_pose_reference_analysis", None)
            if callable(analysis_builder):
                try:
                    analysis = await analysis_builder(ctx) or {}
                except Exception as exc:
                    print(f"⚠️ [POSE_REFERENCE_ANALYSIS_CALL_FAILED] {type(exc).__name__}: {exc}")
                    analysis = {}

            camera_intent = str(analysis.get("camera_intent") or "").strip() if isinstance(analysis, dict) else ""
            visible_scope = str(analysis.get("visible_pose_scope") or "").strip() if isinstance(analysis, dict) else ""
            pose_description = str(analysis.get("pose_description") or "").strip() if isinstance(analysis, dict) else ""

            if not camera_intent:
                camera_builder = getattr(app, "build_pose_camera_intent", None)
                if callable(camera_builder):
                    camera_intent = str(await camera_builder(ctx) or "").strip()

            ctx["pose_camera_intent"] = camera_intent
            ctx["pose_visible_scope"] = visible_scope
            ctx["pose_visible_description"] = pose_description

            debug_line = camera_intent or "(Gemini 未產生取景描述)"
            try:
                channel = getattr(msg, "channel", None) if msg is not None else None
                if channel is None:
                    channel = ctx.get("channel")
                if channel is not None and hasattr(channel, "send"):
                    await channel.send(f"🔎 **Gemini 取景判讀：** `{debug_line}`")
            except Exception as exc:
                print(f"⚠️ [POSE_CAMERA_DEBUG_ECHO_FAILED] {type(exc).__name__}: {exc}")
            print(f"🔎 [POSE_CAMERA_TO_SEEDREAM] {debug_line}")
            print(f"🧩 [POSE_ANALYSIS] scope={visible_scope!r} pose={pose_description!r}")

            # Gemini's scope/description are observational metadata only.  They must
            # never reduce Figure 9's authority or exclude hips/pelvis/legs that are
            # actually visible in the reference image.
            pose_clause = pose_description or "the pose, body orientation, joint relationships, weight distribution, and support/contact geometry visible in Figure 9"
            pose_rule = (
                "REFERENCE ROLE CONTRACT — Figures 1-8 are the identity authority for Xiaoxia. "
                "Figure 9 is POSE GEOMETRY AUTHORITY. Preserve the complete pose geometry that is visually observable in Figure 9 as one connected body configuration. "
                f"Observed pose note: {pose_clause}. "
                "Match the relative geometry of head, shoulders, spine/torso, pelvis/hips, arms, hands, thighs, knees, and any other visible body parts; preserve joint relationships, body orientation, weight distribution, limb placement, and support/contact points. "
                "Do not reinterpret the pose into a more common, more comfortable, or merely similar pose. Do not use Gemini's visible-scope text as permission to discard visible pelvis, hip, thigh, leg, or support geometry from Figure 9. "
                "The pose reference controls geometry only; do not copy Figure 9 person's identity, facial appearance, body identity, clothing, background, lighting, or scene. "
                "Figure 10 is wardrobe authority only for garment portions naturally visible inside the Camera framing. "
                "Camera authority and Pose authority are independent: Camera controls crop/viewpoint while Figure 9 controls the body configuration inside that crop. "
                "Do not widen the shot merely to display more clothing, and do not alter Figure 9 pose geometry merely to fit the wardrobe. "
                "Do not blend identity, pose, and wardrobe reference roles."
            )
            if camera_intent:
                pose_rule += f" Camera framing authority: {camera_intent}."

            ctx["authoritative_scene"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["prompt_base"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["pose_public_scene"] = clean_scene
            ctx["pose_suppressed_scene"] = suppressed_scene
            ctx["pose_generic_photo_request"] = generic_request
            ctx["wardrobe_pose_test"] = True
            ctx["wardrobe_pose_test_version"] = VERSION

            print(
                f"🎬 [POSE_AUTHORITY] generic={generic_request} "
                f"suppressed={suppressed_scene[:220]!r} clean={clean_scene[:220]!r}"
            )
            print(
                f"💃 [WARDROBE_POSE_TEST] version={VERSION} wardrobe={wardrobe_id or expected_wid} "
                f"inputs={len(input_urls[:10])} roles=8_identity+pose_geometry+wardrobe observed_camera={camera_intent!r} model=v4.5"
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
        "mode": "pose_geometry_authority_8_identity_plus_pose_plus_wardrobe_plus_observed_camera_v45",
        "one_shot": True,
        "debug_echo": True,
    }
