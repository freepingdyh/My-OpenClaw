# -*- coding: utf-8 -*-
"""v1.14.00-flat candidate — behavior-equivalent flattening of the active runtime chain.

IMPORTANT:
- Candidate only. Production entrypoint remains xiaoxia_runtime_v11207.py.
- Installer order and special side effects mirror the active 44-wrapper chain.
- No prompt/model/generation parameter is intentionally changed here.
"""
import traceback
import discord

import lobster_discord as app
from xiaoxia.photo import lineage as photo_lineage
from xiaoxia.photo.presentation import build_photo_presentation
from xiaoxia.health_checks import register_health_commands
from xiaoxia.photo.actions import install_photo_result_view_router
from xiaoxia.wardrobe.core import install_wardrobe_core
from xiaoxia.scene.fidelity import install_scene_fidelity
from xiaoxia.scene.semantic_contract import install_photo_semantic_contract_repair
from xiaoxia.scene.observability import install_photo_scene_observability
from xiaoxia.web.oauth_branding import install_oauth_branding_pages
from xiaoxia.video.h3 import install_h3_video_button, H3VideoButton, _config
from xiaoxia.video.legacy_command import install_legacy_video_command
from xiaoxia.video.safety_retry import install_h3_dialogue_safety
from xiaoxia.video.policy_fallback import install_h3_policy_fallback
from xiaoxia.video.policy_fallback_v2 import install_h3_policy_fallback_v2
from xiaoxia.video.diagnostics import install_h3_diagnostics
from xiaoxia.video.prompt_policy_fallback import install_h3_prompt_policy_fallback
from xiaoxia.video.voiceover_mode import install_voiceover_mode
from xiaoxia.video.trace_store import install_h3_trace
from xiaoxia.video.trace_command import install_h3_trace_command
from xiaoxia.video.image_retry import install_h3_image_url_retry
from xiaoxia.video.h3_director_mode import install_h3_director_mode
from xiaoxia.video import archive as h3_archive
from xiaoxia.video import h3_director_mode
from xiaoxia.web.video_room import install_video_room_ui
from xiaoxia.video.model_refresh import install_model_refresh
from xiaoxia.video.video_understanding import install_video_understanding
from xiaoxia.video.adaptive_audio import install_adaptive_audio
from xiaoxia.video.auto_video_context import install_auto_video_context
from xiaoxia.photo.love_display_cleanup import install_love_display_cleanup
from xiaoxia.video.seedance15 import install_seedance15_video_button
from xiaoxia.video.archive_retry import install_h3_archive_retry
from xiaoxia.video.director_sensual_motion import install_sensual_motion_director
from xiaoxia.video.legacy_archive_ui import install_legacy_archive_ui
from xiaoxia.video.archive_privacy import install_archive_privacy
from xiaoxia.web.video_room_privacy import install_video_room_privacy
from xiaoxia.video.archive_delete_command import install_archive_delete_command
from xiaoxia.video.video_delete_command import install_video_delete_command
from xiaoxia.video.legacy_story_direction import install_legacy_story_direction
from xiaoxia.video.user_semantic_fidelity import install_user_semantic_fidelity
from xiaoxia.video.slim_h3_prompt import install_slim_h3_prompt
from xiaoxia.video.fal_native_image_transport import install_fal_native_image_transport
from xiaoxia.video.director_audio_separation import install_director_audio_separation
from xiaoxia.video.prompt_retry_recovery import install_prompt_retry_recovery
from xiaoxia.video.h3_native_voice import install_h3_native_voice
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
from xiaoxia.pose.final_prompt_pose_patch import install_final_pose_prompt_patch

MIGRATION_VERSION = "1.14.00"

def _activate_photo_modules():
    autonomy_recover = app._autonomy_display_share_text
    def photo_display_module(context, type_override=""):
        return photo_lineage.photo_display_module(context, type_override=type_override)
    def clean_photo_lineage_text(value, module="photo"):
        return photo_lineage.clean_photo_lineage_text(value, module=module)
    def canonical_photo_original_text(context, type_override=""):
        return photo_lineage.canonical_photo_original_text(context, type_override=type_override, autonomy_recover=autonomy_recover)
    def default_photo_event_for_module(context, type_override=""):
        return photo_lineage.default_photo_event_for_module(context, type_override=type_override)
    def inherit_photo_lineage(source_context, target_context, action=""):
        return photo_lineage.inherit_photo_lineage(source_context, target_context, action=action, autonomy_recover=autonomy_recover)
    def build_photo_embed(context, title_prefix="📸 小俠照片", attachment_filename=None):
        context = context or {}
        plan = build_photo_presentation(
            context, title_prefix=title_prefix,
            canonical_text=lambda ctx: canonical_photo_original_text(ctx, type_override=app._context_db_type(ctx)),
            autonomy_text=autonomy_recover, is_autonomy=app._is_autonomy_context,
        )
        embed = app.discord.Embed(title=plan["title"], description=plan["description"], color=0xffb6c1)
        if attachment_filename:
            embed.set_image(url=f"attachment://{attachment_filename}")
        else:
            embed.set_image(url=context.get("local_url") or context.get("image_url"))
        for field_name, field_value in plan.get("fields") or []:
            embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(text=f"{plan['footer_source']} | {app._context_seedream_model_label(context)}{app._generation_level_footer(context)}")
        return embed
    app._photo_display_module = photo_display_module
    app._clean_photo_lineage_text = clean_photo_lineage_text
    app._canonical_photo_original_text = canonical_photo_original_text
    app._default_photo_event_for_module = default_photo_event_for_module
    app._inherit_photo_lineage = inherit_photo_lineage
    app._build_photo_embed = build_photo_embed
    app.LOBSTER_VERSION = "1.12.01"

def _activate_flat():
    # Exact active-chain order begins here.
    _activate_photo_modules()

    install_photo_result_view_router(app); register_health_commands(app); app.LOBSTER_VERSION="1.12.02b"
    install_wardrobe_core(app); app.LOBSTER_VERSION="1.12.03"
    install_scene_fidelity(app); app.LOBSTER_VERSION="1.12.04"
    install_photo_semantic_contract_repair(app); app.LOBSTER_VERSION="1.12.05"
    install_photo_scene_observability(app); app.LOBSTER_VERSION="1.12.05a"
    install_oauth_branding_pages(app); app.LOBSTER_VERSION="1.12.05b"
    install_h3_video_button(app); app.LOBSTER_VERSION="1.12.06"

    current_factory = getattr(app, "PhotoResultView", None)
    if current_factory is None:
        raise RuntimeError("PhotoResultView not found")
    def routed_h3_photo_result_view(context):
        view = current_factory(context)
        if not any(isinstance(child, discord.ui.Button) and getattr(child, "label", "") == "🎬 H3影片生成" for child in getattr(view, "children", [])):
            view.add_item(H3VideoButton(app, view))
        return view
    routed_h3_photo_result_view.__name__ = "PhotoResultView"
    routed_h3_photo_result_view.__qualname__ = "PhotoResultView"
    routed_h3_photo_result_view.__doc__ = (
        "v1.12.06a wrapper around the v1.12.02b routed PhotoResultView factory; "
        "adds the shared H3 video button to each newly created result view."
    )
    app.PhotoResultView = routed_h3_photo_result_view
    app.LOBSTER_VERSION="1.12.06a"
    _config()  # preserve config read side effect

    install_legacy_video_command(app); app.LOBSTER_VERSION="1.12.06b"
    install_h3_dialogue_safety(app); app.LOBSTER_VERSION="1.12.06c"
    install_h3_policy_fallback(app); app.LOBSTER_VERSION="1.12.06d"
    install_h3_policy_fallback_v2(app); app.LOBSTER_VERSION="1.12.06e"
    install_h3_diagnostics(app); app.LOBSTER_VERSION="1.12.06f"
    install_h3_prompt_policy_fallback(app); app.LOBSTER_VERSION="1.12.06g"
    install_voiceover_mode(app); app.LOBSTER_VERSION="1.12.06h"
    install_h3_trace(app); app.LOBSTER_VERSION="1.12.06i"
    install_h3_trace_command(app); app.LOBSTER_VERSION="1.12.06j"
    install_h3_image_url_retry(app); app.LOBSTER_VERSION="1.12.06k"
    install_h3_image_url_retry(app); install_h3_trace_command(app); app.LOBSTER_VERSION="1.12.06l"
    app.LOBSTER_VERSION="1.12.06m"
    install_h3_director_mode(app); app.LOBSTER_VERSION="1.12.06n"
    install_h3_director_mode(app); app.LOBSTER_VERSION="1.12.06o"

    h3_archive.install_h3_archive(app)
    h3_director_mode._send_success_interaction = h3_archive._send_success_with_archive
    install_video_room_ui(app); app.LOBSTER_VERSION="1.12.06p"

    install_model_refresh(app); install_video_understanding(app); app.LOBSTER_VERSION="1.12.06q"
    install_adaptive_audio(app); app.LOBSTER_VERSION="1.12.06r"
    install_auto_video_context(app); install_love_display_cleanup(app); app.LOBSTER_VERSION="1.12.06s"
    install_seedance15_video_button(app); app.LOBSTER_VERSION="1.12.06t"

    routed = getattr(app, "PhotoResultView", None)
    if routed is not None and not isinstance(routed, type):
        try:
            delattr(routed, "_xiaoxia_seedance15_installed")
        except Exception:
            pass
    install_seedance15_video_button(app); app.LOBSTER_VERSION="1.12.06u"

    install_h3_archive_retry(app); app.LOBSTER_VERSION="1.12.06v"
    install_sensual_motion_director(app); install_legacy_archive_ui(app); app.LOBSTER_VERSION="1.12.06w"
    install_archive_privacy(app); install_video_room_privacy(app); app.LOBSTER_VERSION="1.12.06x"
    install_archive_delete_command(app); app.LOBSTER_VERSION="1.12.06y"
    install_video_delete_command(app); app.LOBSTER_VERSION="1.12.06z"
    install_legacy_story_direction(app); app.LOBSTER_VERSION="1.12.06aa"
    # ab intentionally inactive
    install_user_semantic_fidelity(app); app.LOBSTER_VERSION="1.12.06ac"
    install_slim_h3_prompt(app); app.LOBSTER_VERSION="1.12.06ad"
    install_fal_native_image_transport(app); app.LOBSTER_VERSION="1.12.06ae"
    install_director_audio_separation(app); app.LOBSTER_VERSION="1.12.06af"
    install_prompt_retry_recovery(app); app.LOBSTER_VERSION="1.12.06ag"
    # ah intentionally bypassed
    install_h3_native_voice(app); app.LOBSTER_VERSION="1.12.06ai"

    if getattr(app, "_xiaoxia_love_display_cleanup_installed", False):
        try:
            delattr(app, "_xiaoxia_love_display_cleanup_installed")
        except Exception:
            pass
    install_love_display_cleanup(app); app.LOBSTER_VERSION="1.12.06aj"
    # ak intentionally inactive
    app.LOBSTER_VERSION="1.12.06al"

    activated = {}
    activated["camera_observer"] = install_camera_director(app)
    activated["pose_commands"] = install_pose_commands(app)
    activated["wardrobe_pose"] = install_wardrobe_pose_test(app)
    activated["h3_typeerror"] = install_h3_typeerror_fix(app)
    activated["slash_rollback"] = install_native_slash_rollback(app)
    activated["director_signature"] = install_director_signature_fix(app)
    activated["photo_pose_input"] = install_photo_pose_input(app)
    activated["repair"] = install_repair_reference_patch(app)
    activated["seedream_prompt_boundary"] = install_seedream_photo_prompt_boundary(app)
    activated["pose_output_guard"] = install_pose_output_guard(app)
    # Must remain last: protects final FAL role wording for Test C.
    activated["pose_final_prompt_guard"] = install_final_pose_prompt_patch(app)
    app.LOBSTER_VERSION=MIGRATION_VERSION
    print("🧱 [RUNTIME_FLAT_CANDIDATE_ACTIVE] version=1.14.00 wrappers=44 behavior_change_intended=False")
    return activated

_ACTIVATED = _activate_flat()

if __name__ == "__main__":
    print("🚀 [LOBSTER_ENTRYPOINT] version=1.14.00-flat stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
