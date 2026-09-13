# -*- coding: utf-8 -*-
"""v1.12.05b migration entrypoint — public OAuth branding pages."""
import traceback

import xiaoxia_runtime_v11205a as previous
from xiaoxia.web.oauth_branding import install_oauth_branding_pages

app = previous.app
MIGRATION_VERSION = "1.12.05b"


def _activate_v11205b():
    info = install_oauth_branding_pages(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🌐 [V11205B_OAUTH_BRANDING_ACTIVE] "
        f"module={info.get('module')} "
        f"public_routes={','.join(info.get('public_routes') or [])} "
        f"vault_route={info.get('vault_route')} "
        f"removed_legacy_root_routes={info.get('removed_legacy_root_routes')}"
    )


_activate_v11205b()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.05b previous=1.12.05a stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
