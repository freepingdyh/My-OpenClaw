# -*- coding: utf-8 -*-
"""v1.12.06ae — fal-native source-image transport for H3."""
import traceback

import xiaoxia_runtime_v11206ad as previous
from xiaoxia.video.fal_native_image_transport import install_fal_native_image_transport

app = previous.app
MIGRATION_VERSION = "1.12.06ae"


def _activate_v11206ae():
    info = install_fal_native_image_transport(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(f"📤🎬 [V11206AE_FAL_NATIVE_IMAGE_ACTIVE] info={info}")


_activate_v11206ae()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06ae previous=1.12.06ad stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
