# -*- coding: utf-8 -*-
"""v1.12.06al — harden Love Intent display cleanup; keep Seedream repair backend."""
import traceback

import xiaoxia_runtime_v11206aj as previous

app = previous.app
MIGRATION_VERSION = "1.12.06al"
app.LOBSTER_VERSION = MIGRATION_VERSION

print("💗🧹 [V11206AL_LOVE_DISPLAY_BOUNDARY_ACTIVE] generation_prompt_unchanged=True repair=Seedream_v4.5")

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06al previous=1.12.06aj stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
