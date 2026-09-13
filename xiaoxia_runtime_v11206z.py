# -*- coding: utf-8 -*-
"""v1.12.06z — provider-agnostic /video_delete by date."""
import traceback

import xiaoxia_runtime_v11206y as previous
from xiaoxia.video.video_delete_command import install_video_delete_command

app = previous.app
MIGRATION_VERSION = "1.12.06z"


def _activate_v11206z():
    info = install_video_delete_command(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🗑️🎞️ [V11206Z_VIDEO_DELETE_ACTIVE] info={info}")


_activate_v11206z()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06z previous=1.12.06y stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
