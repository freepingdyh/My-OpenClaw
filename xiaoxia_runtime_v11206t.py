# -*- coding: utf-8 -*-
"""v1.12.06t — add Seedance 1.5 Pro as a side-by-side H3 PK path."""
import traceback

import xiaoxia_runtime_v11206s as previous
from xiaoxia.video.seedance15 import install_seedance15_video_button

app = previous.app
MIGRATION_VERSION = "1.12.06t"


def _activate_v11206t():
    seedance_info = install_seedance15_video_button(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎞️ [V11206T_SEEDANCE15_PK_ACTIVE] "
        f"seedance={seedance_info}"
    )


_activate_v11206t()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06t previous=1.12.06s stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
