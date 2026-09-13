# -*- coding: utf-8 -*-
"""v1.12.05a migration entrypoint — Scene SSOT observability."""
import traceback

import xiaoxia_runtime_v11205 as previous
from xiaoxia.scene.observability import install_photo_scene_observability

app = previous.app
MIGRATION_VERSION = "1.12.05a"


def _activate_v11205a():
    info = install_photo_scene_observability(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🔎 [V11205A_SCENE_SSOT_OBSERVABILITY_ACTIVE] "
        f"module={info.get('module')} "
        f"patched={info.get('patched')} "
        f"display_source={info.get('display_source')}"
    )


_activate_v11205a()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.05a previous=1.12.05 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
