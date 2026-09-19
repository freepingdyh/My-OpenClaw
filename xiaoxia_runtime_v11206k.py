# -*- coding: utf-8 -*-
"""v1.12.06k — exact-byte fresh-URL retry for H3 body.image_url policy rejection."""
import traceback

import xiaoxia_runtime_v11206j as previous
from xiaoxia.video.image_retry import install_h3_image_url_retry

app = previous.app
MIGRATION_VERSION = "1.12.06k"


def _activate_v11206k():
    info = install_h3_image_url_retry(app)
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print(
        "🔁 [V11206K_H3_IMAGE_RETRY_ACTIVE] "
        f"patched={info.get('patched')} "
        f"trigger={info.get('trigger')} "
        f"retry_count={info.get('retry_count')} "
        f"strategy={info.get('retry_strategy')}"
    )


_activate_v11206k()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.12.06k previous=1.12.06j stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
