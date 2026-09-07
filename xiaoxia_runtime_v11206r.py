# -*- coding: utf-8 -*-
"""v1.12.06r — H3 Director chooses voice-over, selective direct dialogue, or ambience."""
import traceback

import xiaoxia_runtime_v11206q as previous
from xiaoxia.video.adaptive_audio import install_adaptive_audio

app = previous.app
MIGRATION_VERSION = "1.12.06r"


def _activate_v11206r():
    audio_info = install_adaptive_audio(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎙️ [V11206R_ADAPTIVE_AUDIO_ACTIVE] audio={audio_info}")


_activate_v11206r()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06r previous=1.12.06q stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
