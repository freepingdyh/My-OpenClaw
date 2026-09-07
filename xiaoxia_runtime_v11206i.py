# -*- coding: utf-8 -*-
"""v1.12.06i — persist exact H3 inputs/results for moderation diagnostics."""
import traceback

import xiaoxia_runtime_v11206h as previous
from xiaoxia.video.trace_store import install_h3_trace

app = previous.app
MIGRATION_VERSION = "1.12.06i"


def _activate_v11206i():
    info = install_h3_trace(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧾 [V11206I_H3_TRACE_ACTIVE] "
        f"patched={info.get('patched')} "
        f"jsonl={info.get('jsonl')} "
        f"failed_dir={info.get('failed_dir')} "
        f"image_sha256={info.get('image_sha256')} "
        f"prompt_sha256={info.get('prompt_sha256')}"
    )


_activate_v11206i()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06i previous=1.12.06h stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
