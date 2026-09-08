# -*- coding: utf-8 -*-
"""v1.12.06af — H3 visual-only request; Sulafat added only after render."""
import traceback

import xiaoxia_runtime_v11206ae as previous
from xiaoxia.video.director_audio_separation import install_director_audio_separation

app = previous.app
MIGRATION_VERSION = "1.12.06af"


def _activate_v11206af():
    info = install_director_audio_separation(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬🔇🎙️ [V11206AF_AUDIO_SEPARATION_ACTIVE] info={info}")


_activate_v11206af()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06af previous=1.12.06ae stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
