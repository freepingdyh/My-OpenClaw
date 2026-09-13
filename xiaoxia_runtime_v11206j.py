# -*- coding: utf-8 -*-
"""v1.12.06j — add Discord command for inspecting persistent H3 trace records."""
import traceback

import xiaoxia_runtime_v11206i as previous
from xiaoxia.video.trace_command import install_h3_trace_command

app = previous.app
MIGRATION_VERSION = "1.12.06j"


def _activate_v11206j():
    info = install_h3_trace_command(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧾 [V11206J_H3_TRACE_COMMAND_ACTIVE] "
        f"patched={info.get('patched')} "
        f"command={info.get('command')} "
        f"jsonl={info.get('jsonl')}"
    )


_activate_v11206j()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06j previous=1.12.06i stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
