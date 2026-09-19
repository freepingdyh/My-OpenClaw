# -*- coding: utf-8 -*-
"""v1.12.06a migration entrypoint — fix H3 button attachment on routed PhotoResultView factory."""
import traceback
import discord

import xiaoxia_runtime_v11206 as previous
from xiaoxia.video.h3 import H3VideoButton, _config

app = previous.app
MIGRATION_VERSION = "1.12.06a"


def _activate_v11206a():
    current_factory = getattr(app, "PhotoResultView", None)
    if current_factory is None:
        raise RuntimeError("PhotoResultView not found")

    def routed_h3_photo_result_view(context):
        view = current_factory(context)
        if not any(
            isinstance(child, discord.ui.Button)
            and getattr(child, "label", "") == "🎬 H3影片生成"
            for child in getattr(view, "children", [])
        ):
            view.add_item(H3VideoButton(app, view))
        return view

    routed_h3_photo_result_view.__name__ = "PhotoResultView"
    routed_h3_photo_result_view.__qualname__ = "PhotoResultView"
    routed_h3_photo_result_view.__doc__ = (
        "v1.12.06a wrapper around the v1.12.02b routed PhotoResultView factory; "
        "adds the shared H3 video button to each newly created result view."
    )
    app.PhotoResultView = routed_h3_photo_result_view
    app.LOBSTER_VERSION = MIGRATION_VERSION

    cfg = _config()
    print(
        "🎬 [V11206A_H3_BUTTON_FACTORY_FIX_ACTIVE] "
        f"factory_wrapped=True duration={cfg.get('duration')} "
        f"resolution={cfg.get('resolution')} voice_mode={cfg.get('voice_mode')}"
    )


_activate_v11206a()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06a previous=1.12.06 stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
