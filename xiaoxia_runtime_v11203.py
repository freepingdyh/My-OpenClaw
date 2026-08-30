# -*- coding: utf-8 -*-
"""v1.12.03 migration entrypoint — Wardrobe / Outfit core extraction."""
import traceback

import xiaoxia_runtime_v11202 as previous
from xiaoxia.wardrobe.core import install_wardrobe_core

app = previous.app
MIGRATION_VERSION = "1.12.03"


def _activate_v11203():
    info = install_wardrobe_core(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "👗 [V11203_WARDROBE_CORE_ACTIVE] "
        f"module={info.get('module')} "
        f"functions_moved={info.get('functions_moved')} "
        "legacy_monolith=rollback_only"
    )


_activate_v11203()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.03 previous=1.12.02b stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
