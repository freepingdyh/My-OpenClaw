# -*- coding: utf-8 -*-
"""v1.13.23 — extracted Seedream prompt boundary + native Pose figure roles.

v1.12.06al remains the stable base. Post-al features are installed directly from
xiaoxia/ modules; no migration-runtime chain is reintroduced.

Any stored Pose Library entry with complete Camera/Pose/Composition metadata uses
generic Test C inside wardrobe_pose_test: stored text is primary, Figure 9 is
secondary visual evidence, Figure 10 remains wardrobe authority.  The final FAL
guard now removes Figure 9 from the legacy identity-only prohibition for Test C
without changing the C primary/secondary hierarchy.
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
from xiaoxia.photo.seedream_prompt_boundary import install_seedream_photo_prompt_boundary
from xiaoxia.pose.pose_output_guard import install_pose_output_guard
from xiaoxia.pose.library_metadata_patch import install_pose_library_metadata_patch
from xiaoxia.pose.library_authority import install_pose_library_authority
from xiaoxia.pose.library_composition_replace import install_pose_library_composition_replace
from xiaoxia.pose.category_patch import install_pose_category_patch
from xiaoxia.pose.pagination_patch import install_pose_pagination_patch
from xiaoxia.pose.final_prompt_pose_patch import install_final_pose_prompt_patch

app = stable_base.app
MIGRATION_VERSION = "1.13.23"


def _activate_v11317():
    activated = {}
    activated["camera_observer"] = install_camera_director(app)
    activated["pose_category"] = install_pose_category_patch(app)
    activated["pose_commands"] = install_pose_commands(app)
    activated["pose_library_metadata"] = install_pose_library_metadata_patch(app)
    activated["wardrobe_pose"] = install_wardrobe_pose_test(app)
    activated["pose_library_authority"] = install_pose_library_authority(app)
    activated["pose_library_composition_replace"] = install_pose_library_composition_replace(app)
    activated["pose_pagination"] = install_pose_pagination_patch(app)
    activated["h3_typeerror"] = install_h3_typeerror_fix(app)
    activated["slash_rollback"] = install_native_slash_rollback(app)
    activated["director_signature"] = install_director_signature_fix(app)
    activated["photo_pose_input"] = install_photo_pose_input(app)
    activated["repair"] = install_repair_reference_patch(app)
    activated["seedream_prompt_boundary"] = install_seedream_photo_prompt_boundary(app)
    activated["pose_output_guard"] = install_pose_output_guard(app)
    # Must be last: nothing downstream may replace/wrap fal_client after this boundary guard.
    activated["pose_final_prompt_guard"] = install_final_pose_prompt_patch(app)

    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("💃 [V11323_ROOT_POSE_PROMPT_ROLE_FIX_ACTIVE]")
    for name, info in activated.items():
        print(f"   • {name}: {info}")
    return activated


_ACTIVATED = _activate_v11317()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.13.23 consolidated_after=1.12.06al stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
