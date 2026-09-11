# -*- coding: utf-8 -*-
"""v1.12.06ba — Pose Reference attachment belongs to /photo, not wardrobe state."""
import traceback

import xiaoxia_runtime_v11206az as previous
from xiaoxia.pose.photo_pose_input import install_photo_pose_input

app = previous.app
MIGRATION_VERSION = "1.12.06ba"


def _activate_v11206ba():
    info = install_photo_pose_input(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💃 [V11206BA_PHOTO_POSE_INPUT_ACTIVE] info={info}")


_activate_v11206ba()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ba previous=1.12.06az stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
