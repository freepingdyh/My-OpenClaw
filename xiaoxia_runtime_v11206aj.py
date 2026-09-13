# -*- coding: utf-8 -*-
"""v1.12.06aj — keep Love Intent internal English directives out of Discord display."""
import traceback

import xiaoxia_runtime_v11206ai as previous
from xiaoxia.photo.love_display_cleanup import install_love_display_cleanup

app = previous.app
MIGRATION_VERSION = "1.12.06aj"


def _activate_v11206aj():
    # The cleanup is deliberately presentation-only. Seedream/root prompts are unchanged.
    # Clear an older installer marker if this module was activated by a previous runtime,
    # then wrap the current result builder with the strengthened sanitizer.
    if getattr(app, "_xiaoxia_love_display_cleanup_installed", False):
        try:
            delattr(app, "_xiaoxia_love_display_cleanup_installed")
        except Exception:
            pass
    info = install_love_display_cleanup(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"💗🧹 [V11206AJ_LOVE_DISPLAY_CLEANUP_ACTIVE] info={info}")


_activate_v11206aj()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06aj previous=1.12.06ai stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
