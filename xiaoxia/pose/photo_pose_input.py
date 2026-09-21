# -*- coding: utf-8 -*-
"""v1.12.06bb — /photo attachment defaults to Pose Reference.

The legacy photo pipeline may consume an attachment early as a real-background
reference before the pose adapter sees the original Discord message.  This adapter
therefore recovers that same attachment from context when necessary, reclassifies it
as Pose Reference, and clears the legacy background-reference fields before delegating
to the already-tested visible-pose generation path.

Preferred UX:
    /衣櫃 穿 W505                 -> wardrobe state only
    /photo 拍一張 + image         -> image is Pose Reference (default)
    /photo 在這裡拍 + image       -> explicit background/location reference

Pose is one-shot; wardrobe remains persistent.
"""
from __future__ import annotations

VERSION = "1.12.06bb-photo-attachment-router"
_STATE_KEY = "photo_pending_pose_reference"
_BACKGROUND_MARKERS = (
    "背景", "場景", "在這裡", "在這拍", "在這邊", "這個地方", "這個地點",
    "用這張當背景", "以這張為背景", "參考這個地方", "實景", "環境參考",
)


def _first_image_attachment(msg):
    attachments = list(getattr(msg, "attachments", None) or []) if msg is not None else []
    for attachment in attachments:
        url = str(getattr(attachment, "url", "") or "").strip()
        content_type = str(getattr(attachment, "content_type", "") or "").lower()
        filename = str(getattr(attachment, "filename", "") or "").lower()
        looks_image = content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp"))
        if url.startswith("http") and looks_image:
            return {
                "url": url,
                "content_type": content_type or "image/jpeg",
                "message_id": getattr(msg, "id", None),
                "wardrobe_id": "",
                "source": "photo_attachment",
            }
    return None


def _photo_text(ctx, msg) -> str:
    candidates = [
        str((ctx or {}).get("user_input") or "").strip(),
        str(getattr(msg, "content", "") or "").strip() if msg is not None else "",
    ]
    for text in candidates:
        if text.lower().startswith("/photo"):
            return text
    return ""


def _is_photo_message(ctx, msg) -> bool:
    return bool(_photo_text(ctx, msg))


def _explicit_background_request(ctx, msg) -> bool:
    text = _photo_text(ctx, msg)
    return any(marker in text for marker in _BACKGROUND_MARKERS)


def _pose_from_legacy_background_context(ctx):
    """Recover an attachment that upstream already classified as background."""
    url = str(ctx.get("background_reference_url") or "").strip()
    path = str(ctx.get("background_reference_path") or "").strip()
    if not url.startswith("http") and not path:
        return None
    return {
        "url": url,
        "content_type": "image/jpeg",
        "message_id": None,
        "wardrobe_id": "",
        "source": "photo_attachment_recovered_from_background",
    }


def _clear_legacy_background_reference(ctx):
    """Remove the old interpretation so it cannot compete with Pose Authority."""
    ctx["background_reference_present"] = False
    ctx["background_reference_url"] = None
    ctx["background_reference_path"] = None
    ctx["background_reference_provider"] = ""

    scene_data = ctx.get("scene_data")
    if isinstance(scene_data, dict):
        scene_data = dict(scene_data)
        scene_data["background_reference_present"] = False
        scene_data["background_reference_url"] = None
        scene_data["background_reference_path"] = None
        scene_data["background_reference_provider"] = ""
        ctx["scene_data"] = scene_data

    # Strip legacy background-reference prose if it was already appended upstream.
    marker = "REAL BACKGROUND PHOTO REFERENCE:"
    for key in ("prompt_base", "root_prompt_base", "authoritative_scene", "scene_text"):
        value = str(ctx.get(key) or "")
        if marker in value:
            ctx[key] = value.split(marker, 1)[0].rstrip()


def install_photo_pose_input(app):
    previous_generate = app._generate_photo_from_context

    async def _generate_with_photo_attachment(context, msg=None):
        ctx = dict(context or {})
        if not _is_photo_message(ctx, msg):
            return await previous_generate(ctx, msg=msg)

        # Explicit location/background wording preserves the legacy background feature.
        if _explicit_background_request(ctx, msg):
            print(f"🖼️ [PHOTO_ATTACHMENT_ROUTER] version={VERSION} route=background explicit=true")
            return await previous_generate(ctx, msg=msg)

        # Prefer the original Discord attachment. If downstream no longer carries it,
        # recover the URL that the legacy pipeline already stored as background_reference.
        pose = _first_image_attachment(msg)
        if pose is None:
            pose = _pose_from_legacy_background_context(ctx)

        if pose is not None and str(pose.get("url") or "").startswith("http"):
            _clear_legacy_background_reference(ctx)
            state = app.load_state()
            state[_STATE_KEY] = pose
            app.save_state(state)
            ctx["pose_input_source"] = str(pose.get("source") or "photo_attachment")
            ctx["photo_attachment_role"] = "pose_reference"
            print(
                f"💃 [PHOTO_ATTACHMENT_ROUTER] version={VERSION} route=pose "
                f"source={pose.get('source')} one_shot=true"
            )

        return await previous_generate(ctx, msg=msg)

    app._generate_photo_from_context = _generate_with_photo_attachment
    return {
        "version": VERSION,
        "default_attachment_role": "pose_reference",
        "explicit_background_markers": list(_BACKGROUND_MARKERS),
        "one_shot": True,
        "wardrobe_independent": True,
        "legacy_background_recovery": True,
        "generation_contract": "delegates_to_existing_az_visible_pose_authority",
    }
