# -*- coding: utf-8 -*-
"""v1.12.06 migration entrypoint — shared MiniMax H3 video button."""
import traceback

import xiaoxia_runtime_v11205b as previous
from xiaoxia.video.h3 import install_h3_video_button

app = previous.app
MIGRATION_VERSION = "1.12.06"


def _activate_v11206():
    info = install_h3_video_button(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎬 [V11206_H3_VIDEO_ACTIVE] "
        f"module={info.get('module')} "
        f"patched={info.get('patched')} "
        f"duration={info.get('duration')} "
        f"resolution={info.get('resolution')} "
        f"voice_enabled={info.get('voice_enabled')} "
        f"voice_mode={info.get('voice_mode')} "
        f"tts_voice={info.get('tts_voice')} "
        f"image_model={info.get('image_model')} "
        f"reference_model={info.get('reference_model')}"
    )


_activate_v11206()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06 previous=1.12.05b stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
