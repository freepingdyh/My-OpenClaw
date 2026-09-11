# -*- coding: utf-8 -*-
"""v1.12.06ar — H3 audio TypeError hardening."""
import traceback

import xiaoxia_runtime_v11206aq as previous
from xiaoxia.video.h3_typeerror_fix import install_h3_typeerror_fix

app = previous.app
MIGRATION_VERSION = "1.12.06ar"


def _activate_v11206ar():
    info = install_h3_typeerror_fix(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬 [V11206AR_H3_TYPEERROR_FIX_ACTIVE] info={info}")


_activate_v11206ar()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ar previous=1.12.06aq stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
