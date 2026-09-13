# -*- coding: utf-8 -*-
"""v1.12.06ac — concise semantic fidelity for user-directed /影片."""
import traceback

# Intentionally stack on aa, not ab: ac replaces the verbose action-fidelity layer
# with a simpler Director-role definition.
import xiaoxia_runtime_v11206aa as previous
from xiaoxia.video.user_semantic_fidelity import install_user_semantic_fidelity

app = previous.app
MIGRATION_VERSION = "1.12.06ac"


def _activate_v11206ac():
    info = install_user_semantic_fidelity(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎬🧭 [V11206AC_SEMANTIC_FIDELITY_ACTIVE] info={info}")


_activate_v11206ac()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ac previous=1.12.06aa replaces=1.12.06ab stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
