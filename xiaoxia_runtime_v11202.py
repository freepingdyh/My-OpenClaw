# -*- coding: utf-8 -*-
"""v1.12.02a migration entrypoint.

Builds on the v1.12.01 Photo Lineage / Presentation checkpoint, then adds:
- external PhotoResultView construction routing seam
- private OpenAI / Suno health-check commands

The stable monolith remains untouched and is still the callback implementation in 02a.
"""
import traceback

import xiaoxia_runtime_v11201 as previous
from xiaoxia.health_checks import register_health_commands
from xiaoxia.photo.actions import install_photo_result_view_router

app = previous.app
MIGRATION_VERSION = "1.12.02a"


def _activate_v11202a():
    route_info = install_photo_result_view_router(app)
    register_health_commands(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧩 [V11202A_MODULE_PATCH_ACTIVE] "
        f"photo_view_router={route_info.get('router')} "
        f"stable_class={route_info.get('stable_class')} "
        "callbacks=stable"
    )


_activate_v11202a()

if __name__ == "__main__":
    print(f"🚀 [LOBSTER_ENTRYPOINT] version={MIGRATION_VERSION} previous=1.12.01 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
