# -*- coding: utf-8 -*-
"""v1.12.06f migration entrypoint — structured H3 error diagnostics + checker default off."""
import traceback

import xiaoxia_runtime_v11206e as previous
from xiaoxia.video.diagnostics import install_h3_diagnostics

app = previous.app
MIGRATION_VERSION = "1.12.06f"


def _activate_v11206f():
    info = install_h3_diagnostics(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧪 [V11206F_H3_DIAGNOSTICS_ACTIVE] "
        f"patched={info.get('patched')} "
        f"safety_checker_default={info.get('safety_checker_default')} "
        f"env_override_supported={info.get('env_override_supported')} "
        f"discord_error_format={info.get('discord_error_format')} "
        f"legacy_command_rewired={info.get('legacy_command_rewired')}"
    )


_activate_v11206f()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06f previous=1.12.06e stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
