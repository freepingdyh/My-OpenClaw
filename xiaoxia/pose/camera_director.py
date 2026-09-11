# -*- coding: utf-8 -*-
"""v1.12.06av — concise Gemini Camera Director for Pose + Wardrobe photos.

Camera Director has one job only: choose a short camera intent for Seedream V4.5.
It must not rewrite identity, wardrobe, pose, scene, lighting, or the full prompt.
"""
from __future__ import annotations

from typing import Any, Dict

from google.genai import types


async def build_camera_intent(app: Any, context: Dict[str, Any]) -> str:
    user_text = str(
        context.get("user_prompt")
        or context.get("message")
        or context.get("request")
        or context.get("prompt_user")
        or ""
    ).strip()

    instruction = f"""You are a Camera Director for one Seedream V4.5 photo.
Choose ONE concise camera intent that best presents the existing pose and the user's intent.

Rules:
- Output English only, one line only, normally 10-25 words.
- Describe ONLY camera position/direction, height, angle, distance, and framing when useful.
- Do NOT describe the person's identity, face, body shape, clothing, pose/action, background, lighting, mood, or image quality.
- Do NOT rewrite the full image prompt.
- The pose reference controls body pose. Camera intent controls viewpoint only.
- If the user already specifies a camera/viewpoint, preserve that intent and merely translate/condense it.
- If the user gives no camera instruction, choose a viewpoint that clearly presents the referenced pose without changing it.

User request: {user_text}

Return only the camera intent."""

    try:
        model = (
            getattr(app, "GEMINI_FLASH_MODEL", None)
            or getattr(app, "GEMINI_MODEL", None)
            or "gemini-2.5-flash"
        )
        resp = await app.gemini_client.aio.models.generate_content(
            model=model,
            contents=instruction,
            config=types.GenerateContentConfig(temperature=0.35),
        )
        text = str(getattr(resp, "text", "") or "").strip().replace("\n", " ")
        text = " ".join(text.split())
        # Keep this a small steering signal even if Gemini ignores the requested length.
        words = text.split()
        if len(words) > 30:
            text = " ".join(words[:30])
        return text.strip(" \"'")
    except Exception as exc:
        print(f"⚠️ [POSE_CAMERA_DIRECTOR_FAILED] {type(exc).__name__}: {exc}")
        return ""


def install_camera_director(app: Any) -> Dict[str, Any]:
    # Export a narrow seam; wardrobe_pose_test calls it only when a pending Pose exists.
    app.build_pose_camera_intent = lambda context: build_camera_intent(app, context)
    return {
        "version": "1.12.06av",
        "camera_director": "Gemini concise intent",
        "target_words": "10-25",
        "hard_cap_words": 30,
        "scope": "camera viewpoint only",
    }
