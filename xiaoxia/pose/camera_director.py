# -*- coding: utf-8 -*-
"""v1.13.07 — Gemini Pose Observer geometry/composition precision update.

Gemini remains an Observer, not a Director. The observer now prioritizes articulated
body geometry and support/contact relationships, and Composition is explicitly
subject-centric so background objects do not leak into Pose Library metadata.
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
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": "", "composition_feature": ""}

    instruction = """Inspect the attached Pose Reference as an OBSERVER and report ONLY information visibly supported by the current image.
The purpose is high-fidelity human pose transfer. Describe the subject's geometry precisely; do not direct or redesign the image.
Do not invent, improve, exaggerate, sexualize, or choose a different camera angle or unseen body geometry.

Return one JSON object with exactly these keys:
{
  "camera_intent": "...",
  "visible_pose_scope": "...",
  "pose_description": "...",
  "composition_feature": "..."
}

Rules:
- camera_intent: English, one concise line, normally 10-30 words. Describe ONLY the observed camera viewpoint: camera height/angle, front/rear/side or three-quarter view, distance/framing, and meaningful perspective. Do not describe furniture or scene objects.
- visible_pose_scope: English, short phrase listing only clearly visible body regions. When visible, distinguish head, neck, shoulders, back, arms, hands, torso, hips/pelvis, thighs, knees, lower legs, and feet rather than collapsing them into generic "legs".
- pose_description: English, concise but geometrically specific. First identify the base posture (standing, seated, kneeling, crouching/squatting, prone, supine, side-lying/reclining, or leaning). Then describe, when visibly supported: torso orientation/lean/twist; pelvis/hip position; each arm/hand placement; thigh, knee, lower-leg and foot arrangement; left/right or asymmetric relationships; weight distribution; and support/contact relationships. Distinguish a hand merely resting from a hand planted to support body weight. For kneeling, distinguish knees, lower legs, pelvis height and whether the pelvis rests on the heels. For seated poses, state what body region bears weight and how the legs fold/extend/cross. For standing poses, state the primary weight-bearing leg when visually clear. Use support-surface-neutral wording such as "supporting surface" unless the physical object is essential to the body geometry. Never include material or decor such as rug, wooden floor, bed, magazine, stuffed animal, furniture style, or room details.
- composition_feature: English, one concise SUBJECT-CENTRIC line describing only spatial relationships among visible parts of the subject: which body regions are nearer/farther from camera, the primary/secondary focal region, diagonal/vertical/horizontal body flow, foreshortening, or foreground-to-background depth. Do NOT describe background, props, furniture, floor, bedding, text, or any non-subject object. Never invent an object. If no distinctive subject-centric composition feature is visible, return an empty string.
- Facial expression (smile, wink, etc.) is NOT pose geometry; omit it unless it changes head orientation or visible geometry.
- Clothing and hair are NOT pose geometry; ignore them except where they genuinely occlude a body region.
- Do NOT describe identity, face appearance, body shape, clothing, background, lighting, mood, text, logo, watermark, or image quality.
- Do NOT infer legs, hips, feet, hands, support, or other geometry hidden outside the frame.
- If uncertain about a property, omit it rather than guessing.
- Before returning, verify that every statement refers to something visible in the CURRENT image and that composition_feature contains no scene object.
- Return JSON only."""

    try:
        model = getattr(app, "GEMINI_FLASH_MODEL", None) or getattr(app, "GEMINI_MODEL", None) or "gemini-2.5-flash"
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
        composition = " ".join(str(data.get("composition_feature") or "").split()).strip(" \"'")
        words = camera.split()
        if len(words) > 35:
            camera = " ".join(words[:35])
        comp_words = composition.split()
        if len(comp_words) > 55:
            composition = " ".join(comp_words[:55])

        result = {
            "camera_intent": camera,
            "visible_pose_scope": scope,
            "pose_description": pose_desc,
            "composition_feature": composition,
        }
        print(f"📷 [POSE_REFERENCE_ANALYSIS] {result!r}")
        return result
    except Exception as exc:
        print(f"⚠️ [POSE_REFERENCE_ANALYSIS_FAILED] {type(exc).__name__}: {exc}")
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": "", "composition_feature": ""}


async def build_camera_intent(app: Any, context: Dict[str, Any]) -> str:
    result = await analyze_pose_reference(app, context)
    return str(result.get("camera_intent") or "").strip()


def install_camera_director(app: Any) -> Dict[str, Any]:
    app.build_pose_reference_analysis = lambda context: analyze_pose_reference(app, context)
    app.build_pose_camera_intent = lambda context: build_camera_intent(app, context)
    return {
        "version": "1.13.07",
        "camera_director": "Gemini subject-centric pose geometry + camera + composition observer",
        "target_words": "10-30 camera words",
        "hard_cap_words": 35,
        "scope": "camera viewpoint + articulated visible body regions + support/contact geometry + subject-centric composition",
    }
