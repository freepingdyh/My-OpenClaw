# -*- coding: utf-8 -*-
"""v1.12.06as — native slash acknowledgement/context compatibility fix."""
import traceback

import xiaoxia_runtime_v11206ar as previous

app = previous.app
MIGRATION_VERSION = "1.12.06as"


def _activate_v11206as():
    # discord_slash_bridge is installed during aq import; this version documents
    # the corrected bridge implementation and exposes the active migration version.
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("⌨️ [V11206AS_SLASH_ACK_FIX_ACTIVE]")


_activate_v11206as()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06as previous=1.12.06ar stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
