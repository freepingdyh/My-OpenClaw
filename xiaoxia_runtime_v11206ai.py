# -*- coding: utf-8 -*-
"""v1.12.06ai — H3 Turbo native voice; bypass ah Gemini voice profile."""
import traceback

# Stack directly on ag: ah's Gemini TTS voice-profile change is intentionally bypassed.
import xiaoxia_runtime_v11206ag as previous
from xiaoxia.video.h3_native_voice import install_h3_native_voice

app = previous.app
MIGRATION_VERSION = "1.12.06ai"


def _activate_v11206ai():
    info = install_h3_native_voice(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎙️🎬 [V11206AI_H3_NATIVE_VOICE_ACTIVE] info={info}")


_activate_v11206ai()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ai previous=1.12.06ag bypasses=1.12.06ah stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
