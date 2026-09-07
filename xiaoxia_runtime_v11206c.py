# -*- coding: utf-8 -*-
"""v1.12.06c migration entrypoint — sanitize H3 spoken line before Sulafat reference audio."""
import traceback

import xiaoxia_runtime_v11206b as previous
from xiaoxia.video.safety_retry import install_h3_dialogue_safety

app = previous.app
MIGRATION_VERSION = "1.12.06c"


def _activate_v11206c():
    info = install_h3_dialogue_safety(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧼 [V11206C_H3_DIALOGUE_SAFETY_ACTIVE] "
        f"patched={info.get('patched')} "
        f"strategy={info.get('strategy')} "
        f"voice_preserved={info.get('voice_preserved')}"
    )


_activate_v11206c()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06c previous=1.12.06b stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
