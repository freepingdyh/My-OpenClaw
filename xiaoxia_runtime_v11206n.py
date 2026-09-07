# -*- coding: utf-8 -*-
"""v1.12.06n — shared H3 Director + H3 native off-screen narration."""
import traceback

import xiaoxia_runtime_v11206m as previous
from xiaoxia.video.h3_director_mode import install_h3_director_mode

app = previous.app
MIGRATION_VERSION = "1.12.06n"


def _activate_v11206n():
    info = install_h3_director_mode(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎬 [V11206N_H3_DIRECTOR_ACTIVE] "
        f"patched={info.get('patched')} "
        f"theme_first={info.get('theme_first')} "
        f"module_specific_rules={info.get('module_specific_rules')} "
        f"scene_database={info.get('scene_database')} "
        f"primary_voice={info.get('primary_voice')}"
    )


_activate_v11206n()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06n previous=1.12.06m stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
