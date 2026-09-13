# -*- coding: utf-8 -*-
"""v1.12.06h — 10s H3 visual + Sulafat inner-monologue voiceover + scene ambience."""
import traceback

import xiaoxia_runtime_v11206g as previous
from xiaoxia.video.voiceover_mode import install_voiceover_mode

app = previous.app
MIGRATION_VERSION = "1.12.06h"


def _activate_v11206h():
    info = install_voiceover_mode(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎙️ [V11206H_H3_VOICEOVER_MODE_ACTIVE] "
        f"patched={info.get('patched')} "
        f"duration_default={info.get('duration_default')} "
        f"primary_voice={info.get('primary_voice')} "
        f"fallback_voice={info.get('fallback_voice')} "
        f"ambient_audio={info.get('ambient_audio')}"
    )


_activate_v11206h()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06h previous=1.12.06g stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
