# -*- coding: utf-8 -*-
"""v1.12.06o — stricter H3 off-screen narration / no-lip-sync prompt tuning."""
import traceback

import xiaoxia_runtime_v11206n as previous
from xiaoxia.video.h3_director_mode import install_h3_director_mode

app = previous.app
MIGRATION_VERSION = "1.12.06o"


def _activate_v11206o():
    info = install_h3_director_mode(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎬 [V11206O_H3_DIRECTOR_PROMPT_TUNE_ACTIVE] "
        f"patched={info.get('patched')} "
        f"theme_first={info.get('theme_first')} "
        f"primary_voice={info.get('primary_voice')} "
        f"motion_levels={info.get('motion_levels')}"
    )


_activate_v11206o()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06o previous=1.12.06n stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
