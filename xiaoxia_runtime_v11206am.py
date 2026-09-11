# -*- coding: utf-8 -*-
"""v1.12.06am — Seedream v4.5 Xiaoxia Pose Library producer."""
import traceback

import xiaoxia_runtime_v11206al as previous
from xiaoxia.pose.core import install_pose_commands

app = previous.app
MIGRATION_VERSION = "1.12.06am"


def _activate_v11206am():
    info = install_pose_commands(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💃 [V11206AM_POSE_LIBRARY_ACTIVE] info={info}")


_activate_v11206am()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06am previous=1.12.06al stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
