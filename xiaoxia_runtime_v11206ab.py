# -*- coding: utf-8 -*-
"""v1.12.06ab — user-directed subject action fidelity for /影片."""
import traceback

import xiaoxia_runtime_v11206aa as previous
from xiaoxia.video.user_action_fidelity import install_user_action_fidelity

app = previous.app
MIGRATION_VERSION = "1.12.06ab"


def _activate_v11206ab():
    info = install_user_action_fidelity(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🚶🎬 [V11206AB_USER_ACTION_FIDELITY_ACTIVE] info={info}")


_activate_v11206ab()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ab previous=1.12.06aa stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
