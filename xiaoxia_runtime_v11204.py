# -*- coding: utf-8 -*-
"""v1.12.04 migration entrypoint — Gemini scene fidelity repair."""
import traceback

import xiaoxia_runtime_v11203 as previous
from xiaoxia.scene.fidelity import install_scene_fidelity

app = previous.app
MIGRATION_VERSION = "1.12.04"


def _activate_v11204():
    info = install_scene_fidelity(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎯 [V11204_SCENE_FIDELITY_ACTIVE] "
        f"module={info.get('module')} "
        f"patched={info.get('patched')} "
        f"scene_ssot={info.get('scene_ssot')} "
        "downstream_source=authoritative_scene_only"
    )


_activate_v11204()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.04 previous=1.12.03 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
