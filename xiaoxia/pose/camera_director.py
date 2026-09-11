# -*- coding: utf-8 -*-
"""v1.12.06aw — Gemini reads the attached Pose image and describes its camera framing.

Camera Director does NOT choose a new viewpoint. It observes the actual Pose Reference
and emits one concise English camera description for Seedream V4.5.
"""
from __future__ import annotations

from typing import Any, Dict

from google.genai import types


async def build_camera_intent(app: Any, context: Dict[str, Any]) -> str:
    pose_url = str(context.get("pose_reference_url") or "").strip()
    mime_type = str(context.get("pose_reference_mime_type") or "image/jpeg").strip() or "image/jpeg"
    if not pose_url:
        return ""

    instruction = """Inspect the attached pose reference image and describe the camera viewpoint that is ACTUALLY PRESENT in that image.
Do not invent, improve, or choose a different camera angle.

Output rules:
- English only, one line only, normally 10-25 words.
- Describe only observable camera direction, subject-facing direction, camera height, tilt/angle, distance, perspective, and framing/composition when useful.
- Be concrete enough that an image model can reproduce the same viewpoint.
- Do NOT describe identity, face, body shape, clothing, pose/action, background, lighting, mood, or image quality.
- Do NOT rewrite the full image prompt.
- If uncertain about one camera property, omit it rather than guessing.

Return only the concise camera description."""

    try:
        model = (
            getattr(app, "GEMINI_FLASH_MODEL", None)
            or getattr(app, "GEMINI_MODEL", None)
            or "gemini-2.5-flash"
        )
        image_part = types.Part.from_uri(file_uri=pose_url, mime_type=mime_type)
        resp = await app.gemini_client.aio.models.generate_content(
            model=model,
            contents=[image_part, instruction],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        text = str(getattr(resp, "text", "") or "").strip().replace("\n", " ")
        text = " ".join(text.split())
        words = text.split()
        if len(words) > 30:
            text = " ".join(words[:30])
        print(f"📷 [POSE_CAMERA_OBSERVED] {text!r}")
        return text.strip(" \"'")
    except Exception as exc:
        print(f"⚠️ [POSE_CAMERA_DIRECTOR_FAILED] {type(exc).__name__}: {exc}")
        return ""


def install_camera_director(app: Any) -> Dict[str, Any]:
    app.build_pose_camera_intent = lambda context: build_camera_intent(app, context)
    return {
        "version": "1.12.06aw",
        "camera_director": "Gemini visual camera observer",
        "target_words": "10-25",
        "hard_cap_words": 30,
        "scope": "describe camera viewpoint already present in Pose Reference",
    }
