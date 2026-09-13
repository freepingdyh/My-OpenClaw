# -*- coding: utf-8 -*-
"""v1.13.10 — Figure 9 image authority + lightweight metadata guidance.

Figures 1-8 = Xiaoxia identity authority
Figure 9     = primary pose-image authority
Figure 10    = wardrobe authority

Camera / Pose / Composition are intentionally concise guidance. Detailed legacy
Pose Library text is never converted into a joint-by-joint Seedream prompt.
"""
from __future__ import annotations

import re

VERSION = "1.13.10-lightweight-pose-guidance"
_STATE_KEY = "photo_pending_pose_reference"
_GENERIC_PHOTO_REQUESTS = {
    "", ".", "。", "拍一張", "拍張", "拍照", "拍照吧", "拍一張吧", "來一張", "來張", "一張", "照一張", "拍一下", "拍吧"
}
_LEGACY_ANATOMY_TERMS = (
    "pelvis", "hip higher", "hip lower", "torso is", "torso slightly", "elbow", "forearm",
    "weight bearing", "bearing weight", "weight appears", "joint", "lower leg is", "knee is bent"
)


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
        clean = "背景保持自然且不搶戲；人物姿勢以 Figure 9 圖像為準。"
    else:
        clean = f"大俠本次指定：{user_instruction}。只把這段文字當作場景／故事需求；人物姿勢以 Figure 9 圖像為準。"
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


def _split_camera_composition(camera: str, composition: str) -> tuple[str, str]:
    cam = str(camera or "").strip()
    comp = str(composition or "").strip()
    marker = "Composition emphasis:"
    if marker in cam:
        left, right = cam.split(marker, 1)
        cam = left.strip()
        if not comp:
            comp = right.strip()
    return cam, comp


def _short_words(text: str, cap: int) -> str:
    return " ".join(str(text or "").strip().split()[:cap])


def _safe_pose_hint(text: str) -> str:
    """Use new concise metadata; suppress old anatomy-heavy metadata entirely."""
    value = " ".join(str(text or "").strip().split())
    low = value.lower()
    hits = sum(1 for term in _LEGACY_ANATOMY_TERMS if term in low)
    if hits >= 2:
        return ""
    return _short_words(value, 34)


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
                await message.channel.send("💃 已把附圖記為 Pose Reference。下一張 `/photo` 使用 Figure 9 圖像 + 精簡 Camera/Pose/Composition。")
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

            camera_intent = str(analysis.get("camera_intent") or "").strip() if isinstance(analysis, dict) else ""
            visible_scope = str(analysis.get("visible_pose_scope") or "").strip() if isinstance(analysis, dict) else ""
            pose_description = str(analysis.get("pose_description") or "").strip() if isinstance(analysis, dict) else ""
            composition_feature = str(analysis.get("composition_feature") or "").strip() if isinstance(analysis, dict) else ""
            camera_intent, composition_feature = _split_camera_composition(camera_intent, composition_feature)

            camera_hint = _short_words(camera_intent, 28)
            pose_hint = _safe_pose_hint(pose_description)
            composition_hint = _short_words(composition_feature, 30)

            ctx["pose_camera_intent"] = camera_intent
            ctx["pose_visible_scope"] = visible_scope
            ctx["pose_visible_description"] = pose_description
            ctx["pose_composition_feature"] = composition_feature

            parts = [
                "REFERENCE ROLE CONTRACT — Figures 1-8 define Xiaoxia identity.",
                "Figure 9 is the primary pose authority; match its overall visible pose and silhouette.",
            ]
            if pose_hint:
                parts.append(f"Pose cue: {pose_hint}")
            if camera_hint:
                parts.append(f"Camera cue: {camera_hint}")
            if composition_hint:
                parts.append(f"Composition cue: {composition_hint}")
            parts.extend(["Do not copy Figure 9 identity, clothing, background, or lighting.", "Figure 10 defines wardrobe only."])
            pose_rule = " ".join(parts)

            try:
                channel = getattr(msg, "channel", None) if msg is not None else None
                if channel is None:
                    channel = ctx.get("channel")
                if channel is not None and hasattr(channel, "send"):
                    await channel.send(
                        "🔎 **Pose 精簡指引 → Seedream**\n"
                        f"Camera: `{camera_hint or '—'}`\n"
                        f"Pose: `{pose_hint or '—（舊版過細 metadata 已略過）'}`\n"
                        f"Composition: `{composition_hint or '—'}`"
                    )
            except Exception as exc:
                print(f"⚠️ [POSE_GUIDANCE_ECHO_FAILED] {type(exc).__name__}: {exc}")

            print(f"🧩 [POSE_LIGHT_GUIDANCE] camera={camera_hint!r} pose={pose_hint!r} composition={composition_hint!r}")
            ctx["authoritative_scene"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["prompt_base"] = (clean_scene + "\n\n" + pose_rule).strip()
            ctx["pose_public_scene"] = clean_scene
            ctx["pose_suppressed_scene"] = suppressed_scene
            ctx["pose_generic_photo_request"] = generic_request
            ctx["wardrobe_pose_test"] = True
            ctx["wardrobe_pose_test_version"] = VERSION
            ctx["pose_generation_contract"] = "figure9_plus_lightweight_metadata"
            print(f"🎬 [POSE_AUTHORITY_LIGHT] generic={generic_request} clean={clean_scene[:220]!r}")
            return await original_generate(ctx, msg=msg)
        finally:
            latest = app.load_state()
            latest[_STATE_KEY] = None
            app.save_state(latest)

    app._handle_wardrobe_message_direct = _direct_with_optional_pose
    app._generate_photo_from_context = _generate_with_pending_pose
    return {
        "version": VERSION,
        "mode": "figure9_image_authority_plus_lightweight_camera_pose_composition_v45",
        "one_shot": True,
        "metadata_to_seedream": "concise_only; legacy anatomy-heavy pose omitted",
        "debug_echo": True,
    }
