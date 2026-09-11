# -*- coding: utf-8 -*-
"""v1.12.06bb — /photo attachment router: pose by default, background only when explicit."""
import traceback

import xiaoxia_runtime_v11206ba as previous

app = previous.app
MIGRATION_VERSION = "1.12.06bb"


def _activate_v11206bb():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("🧭 [V11206BB_PHOTO_ATTACHMENT_ROUTER_ACTIVE] /photo image => pose by default")


_activate_v11206bb()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06bb previous=1.12.06ba stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
