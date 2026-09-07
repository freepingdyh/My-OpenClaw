# -*- coding: utf-8 -*-
"""v1.12.06p — selective H3 archive + Cloud Villa screening room."""
import traceback

import xiaoxia_runtime_v11206o as previous
from xiaoxia.video import archive as h3_archive
from xiaoxia.video import h3_director_mode
from xiaoxia.web.video_room import install_video_room_ui

app = previous.app
MIGRATION_VERSION = "1.12.06p"


def _activate_v11206p():
    archive_info = h3_archive.install_h3_archive(app)
    # v1.12.06o's active Director owns its interaction-success sender locally.
    # Patch that exact seam so the selective-save View is present on the real H3 path.
    h3_director_mode._send_success_interaction = h3_archive._send_success_with_archive
    room_info = install_video_room_ui(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎞️ [V11206P_H3_ARCHIVE_ACTIVE] "
        f"archive={archive_info} director_success_patched=True room={room_info}"
    )


_activate_v11206p()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06p previous=1.12.06o stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
