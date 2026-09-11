# -*- coding: utf-8 -*-
"""v1.12.06at — rollback native slash bridge; restore legacy image-capable commands."""
import traceback

# IMPORTANT: import ap directly, not aq/as, so the native slash bridge is not installed.
import xiaoxia_runtime_v11206ap as previous
from xiaoxia.video.h3_typeerror_fix import install_h3_typeerror_fix
from xiaoxia.discord_slash_rollback import install_native_slash_rollback

app = previous.app
MIGRATION_VERSION = "1.12.06at"


def _activate_v11206at():
    h3_info = install_h3_typeerror_fix(app)
    slash_info = install_native_slash_rollback(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"↩️ [V11206AT_ROLLBACK_ACTIVE] h3={h3_info} slash={slash_info}")


_activate_v11206at()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06at previous=1.12.06ap stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
