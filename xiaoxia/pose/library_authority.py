# -*- coding: utf-8 -*-
"""Pose Library metadata authority.

For `/姿勢 穿 Pxxx`, the Camera / Visible / Pose metadata saved in the Pose Library
is authoritative and must be reused during `/photo`.  Do not ask Gemini to observe
Figure 9 again and replace those saved values with a second, potentially different,
interpretation.

Temporary pose references (for example `/photo` with an attached pose image) have no
library metadata, so they continue to use the live Gemini observer.
"""
from __future__ import annotations

from typing import Any, Dict

VERSION = "1.13.03"
_STATE_KEY = "photo_pending_pose_reference"


def _pending_library_metadata(app: Any) -> Dict[str, str] | None:
    try:
        state = app.load_state()
    except Exception:
        return None

    pose = state.get(_STATE_KEY) if isinstance(state, dict) else None
    if not isinstance(pose, dict) or str(pose.get("source") or "").strip() != "pose_library":
        return None

    return {
        "camera_intent": str(pose.get("camera_intent") or "").strip(),
        "visible_pose_scope": str(pose.get("visible_pose_scope") or "").strip(),
        "pose_description": str(pose.get("pose_description") or "").strip(),
    }


def install_pose_library_authority(app: Any) -> Dict[str, Any]:
    original_analysis = getattr(app, "build_pose_reference_analysis", None)
    original_camera = getattr(app, "build_pose_camera_intent", None)

    async def authoritative_analysis(context):
        cached = _pending_library_metadata(app)
        if cached is not None:
            pose_id = ""
            try:
                pose_id = str(app.load_state().get(_STATE_KEY, {}).get("pose_id") or "").strip()
            except Exception:
                pass
            print(
                f"📚 [POSE_LIBRARY_METADATA_AUTHORITY] id={pose_id or '?'} "
                f"camera={cached['camera_intent']!r} scope={cached['visible_pose_scope']!r}"
            )
            return dict(cached)

        if callable(original_analysis):
            return await original_analysis(context)
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": ""}

    async def authoritative_camera(context):
        cached = _pending_library_metadata(app)
        if cached is not None:
            return str(cached.get("camera_intent") or "").strip()
        if callable(original_camera):
            return await original_camera(context)
        return ""

    app.build_pose_reference_analysis = authoritative_analysis
    app.build_pose_camera_intent = authoritative_camera

    return {
        "version": VERSION,
        "pose_library": "saved Camera / Visible / Pose metadata is authoritative",
        "temporary_pose": "live Gemini observer unchanged",
        "gemini_rerun_for_library_pose": False,
    }
