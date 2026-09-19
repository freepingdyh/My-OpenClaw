# -*- coding: utf-8 -*-
"""v1.12.06w — mood-aware H3 motion + archive UI for legacy /影片."""
import traceback

import xiaoxia_runtime_v11206v as previous
from xiaoxia.video.director_sensual_motion import install_sensual_motion_director
from xiaoxia.video.legacy_archive_ui import install_legacy_archive_ui

app = previous.app
MIGRATION_VERSION = "1.12.06w"


def _activate_v11206w():
    motion_info = install_sensual_motion_director(app)
    legacy_info = install_legacy_archive_ui(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💃🎬 [V11206W_H3_MOOD_MOTION_ACTIVE] motion={motion_info} legacy={legacy_info}")


_activate_v11206w()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06w previous=1.12.06v stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
