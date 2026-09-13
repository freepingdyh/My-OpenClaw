# -*- coding: utf-8 -*-
"""v1.12.06y — Discord command for deleting archived H3 videos."""
import traceback

import xiaoxia_runtime_v11206x as previous
from xiaoxia.video.archive_delete_command import install_archive_delete_command

app = previous.app
MIGRATION_VERSION = "1.12.06y"


def _activate_v11206y():
    delete_info = install_archive_delete_command(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🗑️ [V11206Y_H3_DELETE_COMMAND_ACTIVE] delete={delete_info}")


_activate_v11206y()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06y previous=1.12.06x stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
