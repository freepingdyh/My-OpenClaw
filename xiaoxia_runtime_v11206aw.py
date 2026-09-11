# -*- coding: utf-8 -*-
"""v1.12.06aw — Gemini observes camera framing from the attached Pose image."""
import traceback

import xiaoxia_runtime_v11206au as previous
from xiaoxia.pose.camera_director import install_camera_director

app = previous.app
MIGRATION_VERSION = "1.12.06aw"


def _activate_v11206aw():
    info = install_camera_director(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"📷 [V11206AW_CAMERA_OBSERVER_ACTIVE] info={info}")


_activate_v11206aw()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06aw previous=1.12.06au stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
