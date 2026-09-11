# -*- coding: utf-8 -*-
"""v1.12.06au — normalize the shared Director callable exposed on app.

Seedance calls app.h3_build_director_plan(context). Some later runtime patches can
replace the underlying h3_director_mode.build_h3_director_plan implementation while
leaving the exported app seam with an incompatible callable signature. Rebind the
seam after all previous installs so every consumer gets the same one-argument API.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import h3_director_mode, voiceover_mode


def install_director_signature_fix(app: Any) -> Dict[str, Any]:
    async def _build(context):
        cfg = voiceover_mode._config()
        return await h3_director_mode.build_h3_director_plan(app, context, cfg)

    app.h3_build_director_plan = _build
    return {
        "patched": True,
        "export": "app.h3_build_director_plan(context)",
        "target": "h3_director_mode.build_h3_director_plan(app, context, cfg)",
    }
