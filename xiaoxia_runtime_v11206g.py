# -*- coding: utf-8 -*-
"""v1.12.06g migration entrypoint — prompt-specific H3 policy fallback."""
import traceback

import xiaoxia_runtime_v11206f as previous
from xiaoxia.video.prompt_policy_fallback import install_h3_prompt_policy_fallback

app = previous.app
MIGRATION_VERSION = "1.12.06g"


def _activate_v11206g():
    info = install_h3_prompt_policy_fallback(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🧩 [V11206G_H3_PROMPT_POLICY_FALLBACK_ACTIVE] "
        f"patched={info.get('patched')} "
        f"trigger={info.get('trigger')} "
        f"retry_1={info.get('retry_1')} "
        f"retry_2={info.get('retry_2')}"
    )


_activate_v11206g()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06g previous=1.12.06f stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
