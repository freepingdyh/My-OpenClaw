# -*- coding: utf-8 -*-
"""v1.12.06ah — keep H3 Turbo pipeline; restore a younger Xiaoxia postmix voice."""
import traceback

import xiaoxia_runtime_v11206ag as previous
from xiaoxia.video.young_voice_profile import install_young_voice_profile

app = previous.app
MIGRATION_VERSION = "1.12.06ah"


def _activate_v11206ah():
    info = install_young_voice_profile(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎙️✨ [V11206AH_YOUNG_VOICE_ACTIVE] info={info}")


_activate_v11206ah()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ah previous=1.12.06ag stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
