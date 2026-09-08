# -*- coding: utf-8 -*-
"""v1.12.06ag — restore proven H3 body.prompt 422 recovery."""
import traceback

import xiaoxia_runtime_v11206af as previous
from xiaoxia.video.prompt_retry_recovery import install_prompt_retry_recovery

app = previous.app
MIGRATION_VERSION = "1.12.06ag"


def _activate_v11206ag():
    info = install_prompt_retry_recovery(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🛟🎬 [V11206AG_PROMPT_RECOVERY_ACTIVE] info={info}")


_activate_v11206ag()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ag previous=1.12.06af stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
