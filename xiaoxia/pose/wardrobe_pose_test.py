# -*- coding: utf-8 -*-
"""v1.13.09 — minimal Figure 9 pose-image authority.

Experiment contract:
  Figures 1-8 = Xiaoxia identity authority
  Figure 9     = direct pose-image authority
  Figure 10    = selected Wxxx wardrobe authority

Gemini Camera / Visible / Pose / Composition metadata remains useful for the Pose
Library, search, display and trace, but is deliberately NOT translated back into a
long Seedream pose instruction.  This A/B keeps the image itself as the highest
resolution description of the pose and avoids a second, text-derived pose source.
"""
from __future__ import annotations

import re

VERSION = "1.13.09-minimal-pose-image-authority"
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
            "人物姿勢直接以 Figure 9 圖像為準。"
        )
    else:
        clean = (
            f"大俠本次指定：{user_instruction}。"
            "只把這段文字當作場景／故事需求；人物姿勢直接以 Figure 9 圖像為準。"
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
                    "**8 張小俠 Identity + Figure 9 Pose Image + Wxxx 衣服 → Seedream V4.5**。"
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

            # Keep Pose Library metadata for trace/debug only.  None of these text
            # descriptions is injected into the Seedream generation contract below.
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
            composition_feature = str(analysis.get("composition_feature") or "").strip() if isinstance(analysis, dict) else ""

            ctx["pose_camera_intent"] = camera_intent
            ctx["pose_visible_scope"] = visible_scope
            ctx["pose_visible_description"] = pose_description
            if composition_feature:
                ctx["pose_composition_feature"] = composition_feature

            try:
                channel = getattr(msg, "channel", None) if msg is not None else None
                if channel is None:
                    channel = ctx.get("channel")
                if channel is not None and hasattr(channel, "send"):
                    await channel.send(
                        "🔎 **Pose metadata 已讀取（僅紀錄，不送 Seedream）：** "
                        f"`{camera_intent or '—'}`"
                    )
            except Exception as exc:
                print(f"⚠️ [POSE_METADATA_DEBUG_ECHO_FAILED] {type(exc).__name__}: {exc}")

            print(
                f"🧩 [POSE_METADATA_TRACE_ONLY] camera={camera_intent!r} scope={visible_scope!r} "
                f"pose={pose_description!r} composition={composition_feature!r}"
            )

            pose_rule = (
                "REFERENCE ROLE CONTRACT — Figures 1-8 are the identity authority for Xiaoxia. "
                "Figure 9 is the pose authority. Match Xiaoxia to the complete visible body pose and spatial geometry shown in Figure 9. "
                "Figure 9 controls pose only; do not copy its identity, facial appearance, clothing, background, lighting, or scene. "
                "Figure 10 is the wardrobe authority only. Do not blend identity, pose, and wardrobe reference roles."
            )

            ctx["authoritative_scene"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["prompt_base"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["pose_public_scene"] = clean_scene
            ctx["pose_suppressed_scene"] = suppressed_scene
            ctx["pose_generic_photo_request"] = generic_request
            ctx["wardrobe_pose_test"] = True
            ctx["wardrobe_pose_test_version"] = VERSION
            ctx["pose_generation_contract"] = "figure9_image_only"

            print(
                f"🎬 [POSE_AUTHORITY_MINIMAL] generic={generic_request} "
                f"suppressed={suppressed_scene[:220]!r} clean={clean_scene[:220]!r}"
            )
            print(
                f"💃 [WARDROBE_POSE_TEST] version={VERSION} wardrobe={wardrobe_id or expected_wid} "
                f"inputs={len(input_urls[:10])} roles=8_identity+pose_image+wardrobe "
                "metadata_to_seedream=false model=v4.5"
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
        "mode": "minimal_pose_image_authority_8_identity_plus_pose_plus_wardrobe_v45",
        "one_shot": True,
        "metadata_to_seedream": False,
        "debug_echo": True,
    }
