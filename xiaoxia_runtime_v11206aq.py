# -*- coding: utf-8 -*-
"""v1.12.06aq — native Discord slash-command bridge."""
import traceback

import xiaoxia_runtime_v11206ap as previous
from xiaoxia.discord_slash_bridge import install_native_slash_commands

app = previous.app
MIGRATION_VERSION = "1.12.06aq"


def _activate_v11206aq():
    info = install_native_slash_commands(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"⌨️ [V11206AQ_NATIVE_SLASH_ACTIVE] info={info}")


_activate_v11206aq()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06aq previous=1.12.06ap stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
