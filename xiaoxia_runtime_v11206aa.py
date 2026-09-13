# -*- coding: utf-8 -*-
"""v1.12.06aa — directed /影片 story input on top of provider-agnostic video management."""
import traceback

import xiaoxia_runtime_v11206z as previous
from xiaoxia.video.legacy_story_direction import install_legacy_story_direction

app = previous.app
MIGRATION_VERSION = "1.12.06aa"


def _activate_v11206aa():
    info = install_legacy_story_direction(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬📝 [V11206AA_DIRECTED_VIDEO_ACTIVE] info={info}")


_activate_v11206aa()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06aa previous=1.12.06z stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
