# -*- coding: utf-8 -*-
"""v1.12.06au — normalize Director callable signature for Seedance."""
import traceback

import xiaoxia_runtime_v11206at as previous
from xiaoxia.video.director_signature_fix import install_director_signature_fix

app = previous.app
MIGRATION_VERSION = "1.12.06au"


def _activate_v11206au():
    info = install_director_signature_fix(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬 [V11206AU_DIRECTOR_SIGNATURE_FIX_ACTIVE] info={info}")


_activate_v11206au()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06au previous=1.12.06at stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
