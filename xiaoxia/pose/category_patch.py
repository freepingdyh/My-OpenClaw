# -*- coding: utf-8 -*-
"""v1.13.07 — deterministic Pose Library category mapping fix.

Category remains derived locally from Gemini's observed pose text. This patch makes
base posture authoritative and prevents incidental torso 'leaning' from turning a
standing/seated/kneeling pose into 倚靠. It also recognizes prone/supine/side-lying.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.pose import core as pose_core

VERSION = "1.13.07"


def _category_from_analysis(scope: str, desc: str) -> str:
    text = f"{scope} {desc}".lower()

    # Specific base postures first. Incidental words such as "leaning forward"
    # must not override the subject's actual weight-bearing posture.
    if any(x in text for x in ("prone", "supine", "side-lying", "side lying", "lying", "reclining", "lies", "laying")):
        return "趴／躺姿"
    if any(x in text for x in ("kneeling", "kneels", "on both knees", "crouching", "crouched", "squatting", "squat")):
        return "蹲／跪姿"
    if any(x in text for x in ("sitting", "seated", "sits")):
        return "坐姿"
    if any(x in text for x in ("standing", "stands", "stood")):
        return "站姿"

    # 倚靠 is a fallback only when no stronger base posture was observed.
    if any(x in text for x in ("leaning against", "leans against", "supported against", "lean against")):
        return "倚靠"
    return "其他"


def install_pose_category_patch(app: Any) -> Dict[str, Any]:
    pose_core._category_from_analysis = _category_from_analysis
    return {
        "version": VERSION,
        "category_mapping": "base-posture-first; prone/supine recognized; incidental leaning cannot override standing/seated/kneeling",
    }
