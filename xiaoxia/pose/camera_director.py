# -*- coding: utf-8 -*-
"""v1.14.00 — Pose Reference observer built from P012/P013 field tests.

Gemini is an Observer, never a pose Director. Figure 9 carries fine geometry.
Metadata exists to remove ambiguity, especially camera position and depth, without
turning the prompt into an anatomical reconstruction.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from google.genai import types

VERSION = "1.14.00"


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
    empty = {"camera_intent": "", "visible_pose_scope": "", "pose_description": "", "composition_feature": ""}
    if not pose_url:
        return empty

    instruction = """Inspect the attached Pose Reference as an OBSERVER. Report only visibly supported facts.
Figure 9 itself carries fine pose geometry. Your text must REMOVE AMBIGUITY, not recreate the body joint by joint.

Return JSON only, exactly:
{
  "camera_intent": "...",
  "visible_pose_scope": "...",
  "pose_description": "...",
  "composition_feature": "..."
}

FIELD JOBS — keep them separate:
1. camera_intent = PHOTOGRAPHER / CAMERA POSITION.
   In one concise English sentence state:
   - camera height when meaningful (low / eye-level / slightly elevated / high);
   - subject-relative side or end (front / rear / side / three-quarter);
   - framing (full-body / 3-4 / medium / close);
   - FROM WHERE -> TOWARD WHERE whenever the subject has depth through the frame.
   Example: "Slightly elevated rear three-quarter full-body view from the legs-and-hips side, looking diagonally toward the face."
   Do not merely say "looking along the body" if the photographer's end/side can be identified.

2. visible_pose_scope = VISIBILITY ONLY.
   Short English list of broad visible regions, e.g. "Full body, including face, torso, arms, hips, legs and feet."
   Do not put pose mechanics here.

3. pose_description = DISTINCTIVE ACTIONS ONLY.
   One short natural English sentence: base posture plus only the 1-3 actions that distinguish this reference.
   Keep important gestures such as one hand supporting the cheek, holding a rail, supporting on one arm, looking back, or crossed legs.
   Do NOT enumerate anatomy, joint angles, pelvis rotation, elbow angles, knee mechanics, weight-bearing analysis, or hidden geometry.
   Never add a corrective instruction that is not visibly true. Do not say "face-down" merely because the pose is prone if the face is turned toward camera.

4. composition_feature = VISUAL FLOW + CAMERA-RELATIVE DEPTH.
   One concise English sentence. State the dominant diagonal/vertical/horizontal flow and, when visible, explicitly say which major body region is CLOSER TO THE CAMERA and which is FARTHER FROM THE CAMERA.
   Example: "The body forms a strong diagonal, with the legs and hips closer to the camera and the face farther from the camera."
   Avoid vague "nearer one end / opposite end" when actual camera-relative depth is visible.

CONSISTENCY CHECK before answering:
- Camera and Composition must agree about near/far direction.
- Camera must answer where the photographer is when the image makes that inferable.
- Pose must not duplicate Camera or Composition.
- Prefer fewer high-value words. If Figure 9 already shows a detail and omitting it does not create a plausible wrong interpretation, omit it.
- Preserve meaningful distinctions: standing/kneeling/seated/prone; front/rear three-quarter; support/contact gesture; looking back; near/far perspective.
- Ignore identity, clothing, body shape, hair, expression, background, lighting, mood, text, logo, watermark and decor.
- If uncertain, omit rather than invent.
"""

    try:
        model = getattr(app, "GEMINI_FLASH_MODEL", None) or getattr(app, "GEMINI_MODEL", None) or "gemini-2.5-flash"
        image_part = types.Part.from_uri(file_uri=pose_url, mime_type=mime_type)
        resp = await app.gemini_client.aio.models.generate_content(
            model=model,
            contents=[image_part, instruction],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        data = json.loads(_clean_json_text(str(getattr(resp, "text", "") or "")))
        if not isinstance(data, dict):
            raise ValueError("Gemini pose analysis did not return an object")

        def clean(key: str, cap: int) -> str:
            value = " ".join(str(data.get(key) or "").split()).strip(" \"'")
            return " ".join(value.split()[:cap])

        result = {
            "camera_intent": clean("camera_intent", 34),
            "visible_pose_scope": clean("visible_pose_scope", 24),
            "pose_description": clean("pose_description", 34),
            "composition_feature": clean("composition_feature", 30),
        }
        print(f"📷 [POSE_OBSERVER_V11400] {result!r}")
        return result
    except Exception as exc:
        print(f"⚠️ [POSE_REFERENCE_ANALYSIS_FAILED] {type(exc).__name__}: {exc}")
        return empty


async def build_camera_intent(app: Any, context: Dict[str, Any]) -> str:
    result = await analyze_pose_reference(app, context)
    return str(result.get("camera_intent") or "").strip()


def install_camera_director(app: Any) -> Dict[str, Any]:
    app.build_pose_reference_analysis = lambda context: analyze_pose_reference(app, context)
    app.build_pose_camera_intent = lambda context: build_camera_intent(app, context)
    return {
        "version": VERSION,
        "observer": "Figure 9 geometry + ambiguity-removal metadata",
        "camera": "photographer position + from/to direction",
        "composition": "visual flow + camera-relative depth",
        "pose": "distinctive actions only; no anatomy reconstruction",
    }
