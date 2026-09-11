# -*- coding: utf-8 -*-
"""v1.12.06az — Gemini observes camera framing plus visible pose scope.

The observer does not choose a new shot. It reports what is actually visible in the
Pose Reference so Seedream can reproduce only supported pose geometry and avoid
inventing unseen lower-body poses from a close-up reference.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from google.genai import types


def _clean_json_text(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.strip("`").strip()
        if value.lower().startswith("json"):
            value = value[4:].strip()
    return value


async def analyze_pose_reference(app: Any, context: Dict[str, Any]) -> Dict[str, str]:
    pose_url = str(context.get("pose_reference_url") or "").strip()
    mime_type = str(context.get("pose_reference_mime_type") or "image/jpeg").strip() or "image/jpeg"
    if not pose_url:
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": ""}

    instruction = """Inspect the attached Pose Reference and report ONLY information that is visibly supported by the image.
Do not invent, improve, or choose a different camera angle or unseen body geometry.

Return one JSON object with exactly these keys:
{
  "camera_intent": "...",
  "visible_pose_scope": "...",
  "pose_description": "..."
}

Rules:
- camera_intent: English, one concise line, normally 10-25 words. Describe the camera direction, subject-facing direction, camera height/angle, distance, perspective, and shot framing actually present.
- visible_pose_scope: English, short phrase listing only body regions whose pose is clearly visible, e.g. "head, shoulders, arms, upper torso" or "full body".
- pose_description: English, one concise line describing only the visible pose/action and support/contact relationships, e.g. "cheek resting on one hand, upper body leaning slightly forward".
- Do NOT describe identity, face appearance, body shape, clothing, background, lighting, mood, or image quality.
- Do NOT infer legs, hips, feet, or other body regions hidden outside the frame.
- If uncertain about a property, omit it rather than guessing.
- Return JSON only."""

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
        raw = _clean_json_text(str(getattr(resp, "text", "") or ""))
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Gemini pose analysis did not return an object")

        camera = " ".join(str(data.get("camera_intent") or "").split()).strip(" \"'")
        scope = " ".join(str(data.get("visible_pose_scope") or "").split()).strip(" \"'")
        pose_desc = " ".join(str(data.get("pose_description") or "").split()).strip(" \"'")

        # Keep the camera clause compact so it remains a strong, simple instruction.
        words = camera.split()
        if len(words) > 30:
            camera = " ".join(words[:30])

        result = {
            "camera_intent": camera,
            "visible_pose_scope": scope,
            "pose_description": pose_desc,
        }
        print(f"📷 [POSE_REFERENCE_ANALYSIS] {result!r}")
        return result
    except Exception as exc:
        print(f"⚠️ [POSE_REFERENCE_ANALYSIS_FAILED] {type(exc).__name__}: {exc}")
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": ""}


async def build_camera_intent(app: Any, context: Dict[str, Any]) -> str:
    """Backward-compatible camera-only seam."""
    result = await analyze_pose_reference(app, context)
    return str(result.get("camera_intent") or "").strip()


def install_camera_director(app: Any) -> Dict[str, Any]:
    app.build_pose_reference_analysis = lambda context: analyze_pose_reference(app, context)
    app.build_pose_camera_intent = lambda context: build_camera_intent(app, context)
    return {
        "version": "1.12.06az",
        "camera_director": "Gemini visual camera + visible pose scope observer",
        "target_words": "10-25 camera words",
        "hard_cap_words": 30,
        "scope": "camera viewpoint + visible body regions + visible pose only",
    }
