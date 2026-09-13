# -*- coding: utf-8 -*-
"""v1.12.06u — fix Seedance 1.5 Pro button injection behind PhotoResultView router."""
import traceback

import xiaoxia_runtime_v11206t as previous
from xiaoxia.video.seedance15 import install_seedance15_video_button

app = previous.app
MIGRATION_VERSION = "1.12.06u"


def _activate_v11206u():
    # v1.12.06t marked the router function as installed. Clear only that stale marker;
    # the corrected installer targets the real stable View class behind the router.
    routed = getattr(app, "PhotoResultView", None)
    if routed is not None and not isinstance(routed, type):
        try:
            delattr(routed, "_xiaoxia_seedance15_installed")
        except Exception:
            pass
    seedance_info = install_seedance15_video_button(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"🎞️ [V11206U_SEEDANCE15_ROUTER_FIX_ACTIVE] seedance={seedance_info}")


_activate_v11206u()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06u previous=1.12.06t stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
