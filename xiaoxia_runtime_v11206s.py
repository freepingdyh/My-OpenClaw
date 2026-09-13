# -*- coding: utf-8 -*-
"""v1.12.06s — normal-chat video vision + Love Intent display cleanup."""
import traceback

import xiaoxia_runtime_v11206r as previous
from xiaoxia.video.auto_video_context import install_auto_video_context
from xiaoxia.photo.love_display_cleanup import install_love_display_cleanup

app = previous.app
MIGRATION_VERSION = "1.12.06s"


def _activate_v11206s():
    video_info = install_auto_video_context(app)
    love_info = install_love_display_cleanup(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "👀💗 [V11206S_NATURAL_VIDEO_LOVE_CLEANUP_ACTIVE] "
        f"video={video_info} love={love_info}"
    )


_activate_v11206s()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06s previous=1.12.06r stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
