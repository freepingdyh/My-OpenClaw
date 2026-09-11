# -*- coding: utf-8 -*-
"""v1.12.06bd — strengthen /photo + Pose geometry authority."""
import traceback

import xiaoxia_runtime_v11206bc as previous

app = previous.app
MIGRATION_VERSION = "1.12.06bd"


def _activate_v11206bd():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("💃 [V11206BD_POSE_GEOMETRY_AUTHORITY_ACTIVE] Figure 9 geometry authority strengthened")


_activate_v11206bd()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06bd previous=1.12.06bc stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
