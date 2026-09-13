# -*- coding: utf-8 -*-
"""v1.12.06ad — slim H3 prompt, exact prompt trace, no app-side sanitizing retry."""
import traceback

import xiaoxia_runtime_v11206ac as previous
from xiaoxia.video.slim_h3_prompt import install_slim_h3_prompt

app = previous.app
MIGRATION_VERSION = "1.12.06ad"


def _activate_v11206ad():
    info = install_slim_h3_prompt(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬✂️ [V11206AD_SLIM_H3_PROMPT_ACTIVE] info={info}")


_activate_v11206ad()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ad previous=1.12.06ac stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
