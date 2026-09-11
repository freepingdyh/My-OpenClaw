# -*- coding: utf-8 -*-
"""v1.12.06ba — move ad-hoc Pose Reference input to /photo.

This is deliberately a thin input adapter.  The already-tested az generation path
continues to own Gemini pose/camera analysis and the 8 identity + pose + wardrobe
Seedream V4.5 contract.

Preferred UX:
    /衣櫃 穿 W505          -> wardrobe state only
    /photo <attach image> -> this one photo uses the attachment as Pose Reference

The attachment is one-shot and is consumed by the existing az pose generator.
"""
from __future__ import annotations

VERSION = "1.12.06ba-photo-pose-input"
_STATE_KEY = "photo_pending_pose_reference"


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
                # Deliberately NOT bound to a wardrobe id.  Wardrobe is persistent
                # state; pose is a one-photo instruction.
                "wardrobe_id": "",
                "source": "photo_attachment",
            }
    return None


def _is_photo_message(ctx, msg) -> bool:
    candidates = [
        str((ctx or {}).get("user_input") or "").strip(),
        str(getattr(msg, "content", "") or "").strip() if msg is not None else "",
    ]
    return any(text.lower().startswith("/photo") for text in candidates if text)


def install_photo_pose_input(app):
    previous_generate = app._generate_photo_from_context

    async def _generate_with_photo_attachment(context, msg=None):
        ctx = dict(context or {})
        pose = _first_image_attachment(msg) if _is_photo_message(ctx, msg) else None

        if pose is not None:
            state = app.load_state()
            state[_STATE_KEY] = pose
            app.save_state(state)
            ctx["pose_input_source"] = "photo_attachment"
            print(
                f"💃 [PHOTO_POSE_INPUT] version={VERSION} message_id={pose.get('message_id')} "
                "source=/photo_attachment one_shot=true"
            )

        return await previous_generate(ctx, msg=msg)

    app._generate_photo_from_context = _generate_with_photo_attachment
    return {
        "version": VERSION,
        "input": "/photo attachment",
        "one_shot": True,
        "wardrobe_independent": True,
        "generation_contract": "delegates_to_existing_az_visible_pose_authority",
    }
