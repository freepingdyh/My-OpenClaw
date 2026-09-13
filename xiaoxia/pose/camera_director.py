# -*- coding: utf-8 -*-
"""v1.13.10 — concise Pose Library observer metadata.

Gemini remains an Observer, not a Director.  Figure 9 is the high-resolution pose
source; metadata is intentionally lightweight so it helps search and generation
without becoming a second skeleton specification.
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

    instruction = """Inspect the attached Pose Reference as an OBSERVER and report ONLY what is visibly supported by the current image.
The image itself is the primary pose authority. Metadata must be short, discriminative, and easy for another image model to understand.
Do not turn the pose into an anatomical or joint-by-joint specification.

Return one JSON object with exactly these keys:
{
  "camera_intent": "...",
  "visible_pose_scope": "...",
  "pose_description": "...",
  "composition_feature": "..."
}

Rules:
- camera_intent: English, ONE concise sentence, target 8-22 words. Include only viewpoint/framing that materially affects the pose: high/low/eye-level, front/rear/side/three-quarter, full-body/3-4 body/medium/close framing, and strong perspective if obvious.
- visible_pose_scope: English, short comma-separated list of only clearly visible broad body regions. Prefer broad groups such as head, shoulders, arms/hands, torso/back, hips, legs, feet. Do not over-segment into pelvis/thigh/knee/lower-leg unless one of those is uniquely important to what is visible.
- pose_description: English, ONE short sentence, target 10-30 words. Describe the pose the way a photographer or person would naturally distinguish it: base posture + the 1-3 defining actions/relationships. Examples: "Standing on stairs, one hand on the rail, turning the upper body back toward the camera." / "Seated on the floor with knees together, legs extending toward the camera, both hands supporting the face." Do NOT enumerate torso angle, pelvis rotation, hip height, elbow angles, individual joint mechanics, weight-bearing details, or anatomical relationships unless absolutely necessary to distinguish the pose.
- composition_feature: English, ONE concise sentence, target 8-25 words. Describe only the subject's major visual flow/depth: diagonal/vertical/horizontal line, near-vs-far body regions, foreshortening, or primary focal relationship. Do not describe props or decor.
- Preserve discriminative differences such as standing vs kneeling, seated vs crouching, front vs rear three-quarter, legs together vs apart, arms supporting vs merely raised, or feet projecting toward camera.
- Facial expression, clothing, hair, identity, body shape, background, lighting, mood, text, logo, watermark, and decor are not pose metadata.
- Do not invent hidden geometry. If uncertain, omit it.
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

        camera = " ".join(camera.split()[:28])
        pose_desc = " ".join(pose_desc.split()[:40])
        composition = " ".join(composition.split()[:32])

        result = {
            "camera_intent": camera,
            "visible_pose_scope": scope,
            "pose_description": pose_desc,
            "composition_feature": composition,
        }
        print(f"📷 [POSE_REFERENCE_ANALYSIS_CONCISE] {result!r}")
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
        "version": "1.13.10",
        "camera_director": "Gemini concise pose observer",
        "pose_style": "photographer-level discriminative summary, not anatomy",
        "scope": "lightweight Camera + Visible + Pose + Composition",
    }
