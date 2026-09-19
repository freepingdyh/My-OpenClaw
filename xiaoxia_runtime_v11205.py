# -*- coding: utf-8 -*-
"""v1.12.05 migration entrypoint — photo semantic-contract direct pass."""
import traceback

import xiaoxia_runtime_v11204 as previous
from xiaoxia.scene.semantic_contract import install_photo_semantic_contract_repair

app = previous.app
MIGRATION_VERSION = "1.12.05"


def _activate_v11205():
    info = install_photo_semantic_contract_repair(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧩 [V11205_PHOTO_SEMANTIC_CONTRACT_ACTIVE] "
        f"module={info.get('module')} "
        f"patched={info.get('patched')} "
        f"scene_ssot={info.get('scene_ssot')} "
        "legacy_photo_pose_minimal_bypassed=True"
    )


_activate_v11205()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.05 previous=1.12.04 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
