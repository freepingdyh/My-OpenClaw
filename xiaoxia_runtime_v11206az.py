# -*- coding: utf-8 -*-
"""v1.12.06az — Visible Pose Authority for close-up and partial-body references."""
import traceback

import xiaoxia_runtime_v11206ay as previous

app = previous.app
MIGRATION_VERSION = "1.12.06az"


def _activate_v11206az():
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("🧩 [V11206AZ_VISIBLE_POSE_AUTHORITY_ACTIVE] visible regions + camera framing override unseen-body inference")


_activate_v11206az()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06az previous=1.12.06ay stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
