# -*- coding: utf-8 -*-
"""v1.12.06e migration entrypoint — add silent fallback after native H3 policy rejection."""
import traceback

import xiaoxia_runtime_v11206d as previous
from xiaoxia.video.policy_fallback_v2 import install_h3_policy_fallback_v2

app = previous.app
MIGRATION_VERSION = "1.12.06e"


def _activate_v11206e():
    info = install_h3_policy_fallback_v2(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🛟 [V11206E_H3_POLICY_FALLBACK_V2_ACTIVE] "
        f"patched={info.get('patched')} "
        f"strategy={info.get('strategy')} "
        f"final_fallback={info.get('final_fallback')}"
    )


_activate_v11206e()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06e previous=1.12.06d stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
