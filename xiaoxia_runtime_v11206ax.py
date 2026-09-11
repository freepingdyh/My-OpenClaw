# -*- coding: utf-8 -*-
"""v1.12.06ax — visible Gemini camera observation for Pose + Wardrobe debugging."""
import traceback

import xiaoxia_runtime_v11206aw as previous

app = previous.app
MIGRATION_VERSION = "1.12.06ax"


def _activate_v11206ax():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("🔎 [V11206AX_CAMERA_DEBUG_ECHO_ACTIVE] Discord + stdout")


_activate_v11206ax()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ax previous=1.12.06aw stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
