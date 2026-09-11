# -*- coding: utf-8 -*-
"""v1.12.06ay — Pose authority over legacy /photo scene direction."""
import traceback

import xiaoxia_runtime_v11206ax as previous

app = previous.app
MIGRATION_VERSION = "1.12.06ay"


def _activate_v11206ay():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("🎬 [V11206AY_POSE_AUTHORITY_ACTIVE] Pose/Camera override legacy scene action/framing")


_activate_v11206ay()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ay previous=1.12.06ax stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
