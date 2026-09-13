# -*- coding: utf-8 -*-
"""v1.12.06x — private H3 archive playback + delete controls."""
import traceback

import xiaoxia_runtime_v11206w as previous
from xiaoxia.video.archive_privacy import install_archive_privacy
from xiaoxia.web.video_room_privacy import install_video_room_privacy

app = previous.app
MIGRATION_VERSION = "1.12.06x"


def _activate_v11206x():
    privacy_info = install_archive_privacy(app)
    room_info = install_video_room_privacy(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🔐🎞️ [V11206X_PRIVATE_VIDEO_ARCHIVE_ACTIVE] privacy={privacy_info} room={room_info}")


_activate_v11206x()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06x previous=1.12.06w stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
