# -*- coding: utf-8 -*-
"""v1.12.06q — Gemini lifecycle refresh + Xiaoxia video understanding."""
import traceback

import xiaoxia_runtime_v11206p as previous
from xiaoxia.video.model_refresh import install_model_refresh
from xiaoxia.video.video_understanding import install_video_understanding

app = previous.app
MIGRATION_VERSION = "1.12.06q"


def _activate_v11206q():
    model_info = install_model_refresh(app)
    vision_info = install_video_understanding(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "👀 [V11206Q_GEMINI_REFRESH_ACTIVE] "
        f"models={model_info} video_vision={vision_info}"
    )


_activate_v11206q()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06q previous=1.12.06p stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
