# -*- coding: utf-8 -*-
"""v1.12.06v — H3 archive retry/rescue without regeneration."""
import traceback

import xiaoxia_runtime_v11206u as previous
from xiaoxia.video.archive_retry import install_h3_archive_retry

app = previous.app
MIGRATION_VERSION = "1.12.06v"


def _activate_v11206v():
    retry_info = install_h3_archive_retry(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💾 [V11206V_H3_ARCHIVE_RETRY_ACTIVE] retry={retry_info}")


_activate_v11206v()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06v previous=1.12.06u stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
