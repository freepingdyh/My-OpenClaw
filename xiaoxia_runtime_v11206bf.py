# -*- coding: utf-8 -*-
"""v1.12.06bf — anatomy-aware minimal/local photo repair."""
import traceback

import xiaoxia_runtime_v11206be as previous
from xiaoxia.photo.repair_reference_patch import install_repair_reference_patch

app = previous.app
MIGRATION_VERSION = "1.12.06bf"


def _activate_v11206bf():
    info = install_repair_reference_patch(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🩹 [V11206BF_LOCAL_REPAIR_ACTIVE] {info}")


_activate_v11206bf()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06bf previous=1.12.06be stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
