# -*- coding: utf-8 -*-
"""v1.13.00 — consolidated runtime + original-reference Pose Library.

v1.12.06al remains the stable base. Post-al features are installed directly from
xiaoxia/ modules; no migration-runtime chain is reintroduced.
"""
import traceback

import xiaoxia_runtime_v11206al as stable_base

from xiaoxia.pose.core import install_pose_commands
from xiaoxia.pose.wardrobe_pose_test import install_wardrobe_pose_test
from xiaoxia.video.h3_typeerror_fix import install_h3_typeerror_fix
from xiaoxia.discord_slash_rollback import install_native_slash_rollback
from xiaoxia.video.director_signature_fix import install_director_signature_fix
from xiaoxia.pose.camera_director import install_camera_director
from xiaoxia.pose.photo_pose_input import install_photo_pose_input
from xiaoxia.photo.repair_reference_patch import install_repair_reference_patch
from xiaoxia.pose.pose_output_guard import install_pose_output_guard

app = stable_base.app
MIGRATION_VERSION = "1.13.00"


def _activate_v11300():
    activated = {}
    # Camera observer is installed before Pose commands so /姿勢 新增 can use it.
    activated["camera_observer"] = install_camera_director(app)
    activated["pose_commands"] = install_pose_commands(app)
    activated["wardrobe_pose"] = install_wardrobe_pose_test(app)
    activated["h3_typeerror"] = install_h3_typeerror_fix(app)
    activated["slash_rollback"] = install_native_slash_rollback(app)
    activated["director_signature"] = install_director_signature_fix(app)
    activated["photo_pose_input"] = install_photo_pose_input(app)
    activated["repair"] = install_repair_reference_patch(app)
    activated["pose_output_guard"] = install_pose_output_guard(app)

    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("💃 [V11300_POSE_LIBRARY_RUNTIME_ACTIVE]")
    for name, info in activated.items():
        print(f"   • {name}: {info}")
    return activated


_ACTIVATED = _activate_v11300()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.13.00 consolidated_after=1.12.06al stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
