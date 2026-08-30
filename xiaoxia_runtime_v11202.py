# -*- coding: utf-8 -*-
"""v1.12.02b migration entrypoint.

Builds on the v1.12.01 Photo Lineage / Presentation checkpoint, then adds:
- external PhotoResultView construction routing seam
- extracted business handlers for the complete PhotoResultView button surface
- private OpenAI / Suno health-check commands

The stable monolith is intentionally retained unchanged as a rollback/reference copy;
runtime PhotoResultView button execution is owned by xiaoxia.photo.handlers.
"""
import traceback

import xiaoxia_runtime_v11201 as previous
from xiaoxia.health_checks import register_health_commands
from xiaoxia.photo.actions import install_photo_result_view_router

app = previous.app
MIGRATION_VERSION = "1.12.02b"


def _activate_v11202b():
    route_info = install_photo_result_view_router(app)
    register_health_commands(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    actions = ",".join(route_info.get("externalized", [])) or "none"
    print(
        "🧩 [V11202B_MODULE_PATCH_ACTIVE] "
        f"photo_view_router={route_info.get('router')} "
        f"stable_class={route_info.get('stable_class')} "
        f"handler_owner={route_info.get('handler_owner')} "
        f"externalized={actions}"
    )


_activate_v11202b()

if __name__ == "__main__":
    print(f"🚀 [LOBSTER_ENTRYPOINT] version={MIGRATION_VERSION} previous=1.12.01 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
