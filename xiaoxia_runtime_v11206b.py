# -*- coding: utf-8 -*-
"""v1.12.06b migration entrypoint — add /影片 for existing image messages."""
import traceback

import xiaoxia_runtime_v11206a as previous
from xiaoxia.video.legacy_command import install_legacy_video_command

app = previous.app
MIGRATION_VERSION = "1.12.06b"


def _activate_v11206b():
    info = install_legacy_video_command(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🎬 [V11206B_H3_LEGACY_COMMAND_ACTIVE] "
        f"module={info.get('module')} "
        f"installed={info.get('installed')} "
        f"command={info.get('command')} "
        f"reason={info.get('reason')}"
    )


_activate_v11206b()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06b previous=1.12.06a stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
