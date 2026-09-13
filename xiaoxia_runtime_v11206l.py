# -*- coding: utf-8 -*-
"""v1.12.06l — three-step H3 policy retry diagnostics + full attempt trace display."""
import traceback

import xiaoxia_runtime_v11206k as previous
from xiaoxia.video.image_retry import install_h3_image_url_retry
from xiaoxia.video.trace_command import install_h3_trace_command

app = previous.app
MIGRATION_VERSION = "1.12.06l"


def _activate_v11206l():
    retry_info = install_h3_image_url_retry(app)
    trace_info = install_h3_trace_command(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🔁 [V11206L_H3_RETRY_ACTIVE] "
        f"retry_patched={retry_info.get('patched')} "
        f"max_attempts={retry_info.get('max_attempts')} "
        f"trace_attempts_visible={trace_info.get('attempts_visible')}"
    )


_activate_v11206l()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06l previous=1.12.06k stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
