# -*- coding: utf-8 -*-
"""v1.12.06be — pose public-output cleanup + incompatible v5 guard."""
import traceback

import xiaoxia_runtime_v11206bd as previous
from xiaoxia.pose.pose_output_guard import install_pose_output_guard

app = previous.app
MIGRATION_VERSION = "1.12.06be"


def _activate_v11206be():
    info = install_pose_output_guard(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🧼 [V11206BE_POSE_OUTPUT_GUARD_ACTIVE] {info}")


_activate_v11206be()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06be previous=1.12.06bd stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
