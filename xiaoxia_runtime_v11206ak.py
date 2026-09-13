# -*- coding: utf-8 -*-
"""v1.12.06ak — route existing `修正這張` photo edits to GPT-Image 2.5 Sunburst."""
import traceback

import xiaoxia_runtime_v11206aj as previous
from xiaoxia.photo.sunburst_repair import install_sunburst_repair

app = previous.app
MIGRATION_VERSION = "1.12.06ak"


def _activate_v11206ak():
    info = install_sunburst_repair(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"☀️🩹 [V11206AK_SUNBURST_REPAIR_ACTIVE] info={info}")


_activate_v11206ak()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ak previous=1.12.06aj stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
