# -*- coding: utf-8 -*-
"""v1.12.06m — dedicated H3 motion/audio prompt layer; authoritative_scene no longer copied into fal prompt."""
import traceback

import xiaoxia_runtime_v11206l as previous

app = previous.app
MIGRATION_VERSION = "1.12.06m"


def _activate_v11206m():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎬 [V11206M_H3_VIDEO_PROMPT_ACTIVE] "
        "strategy=motion_only_prompt scene_text_not_forwarded_to_fal "
        "timeline=0-3/3-7/7-10s ambience=short_scene_category"
    )


_activate_v11206m()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06m previous=1.12.06l stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
