# -*- coding: utf-8 -*-
"""v1.12.06ap — wardrobe wear + optional pose reference experiment."""
import traceback

import xiaoxia_runtime_v11206ao as previous
from xiaoxia.pose.wardrobe_pose_test import install_wardrobe_pose_test

app = previous.app
MIGRATION_VERSION = "1.12.06ap"


def _activate_v11206ap():
    info = install_wardrobe_pose_test(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💃 [V11206AP_WARDROBE_POSE_TEST_ACTIVE] info={info}")


_activate_v11206ap()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ap previous=1.12.06ao stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
