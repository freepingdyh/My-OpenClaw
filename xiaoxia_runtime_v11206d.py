# -*- coding: utf-8 -*-
"""v1.12.06d migration entrypoint — H3 policy fallback from Sulafat reference audio to native turbo."""
import traceback

import xiaoxia_runtime_v11206c as previous
from xiaoxia.video.policy_fallback import install_h3_policy_fallback

app = previous.app
MIGRATION_VERSION = "1.12.06d"


def _activate_v11206d():
    info = install_h3_policy_fallback(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🛟 [V11206D_H3_POLICY_FALLBACK_ACTIVE] "
        f"patched={info.get('patched')} "
        f"strategy={info.get('strategy')} "
        f"reference_voice={info.get('reference_voice')} "
        f"fallback_voice={info.get('fallback_voice')}"
    )


_activate_v11206d()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06d previous=1.12.06c stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
