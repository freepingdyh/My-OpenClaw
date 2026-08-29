# -*- coding: utf-8 -*-
"""v1.12.01 migration entrypoint.

The stable v1.11.17.2 monolith remains untouched as a rollback reference.
This entrypoint imports it, activates the first extracted Photo Lineage / Presentation
modules, then starts the same main() coroutine.
"""
import traceback

import lobster_discord as app
from xiaoxia.photo import lineage as photo_lineage
from xiaoxia.photo.presentation import build_photo_presentation

MIGRATION_VERSION = "1.12.01"


def _activate_photo_modules():
    """Route existing runtime callers to extracted modules without changing call signatures."""
    autonomy_recover = app._autonomy_display_share_text

    def photo_display_module(context, type_override=""):
        return photo_lineage.photo_display_module(context, type_override=type_override)

    def clean_photo_lineage_text(value, module="photo"):
        return photo_lineage.clean_photo_lineage_text(value, module=module)

    def canonical_photo_original_text(context, type_override=""):
        return photo_lineage.canonical_photo_original_text(
            context,
            type_override=type_override,
            autonomy_recover=autonomy_recover,
        )

    def default_photo_event_for_module(context, type_override=""):
        return photo_lineage.default_photo_event_for_module(context, type_override=type_override)

    def inherit_photo_lineage(source_context, target_context, action=""):
        return photo_lineage.inherit_photo_lineage(
            source_context,
            target_context,
            action=action,
            autonomy_recover=autonomy_recover,
        )

    def build_photo_embed(context, title_prefix="📸 小俠照片", attachment_filename=None):
        context = context or {}
        plan = build_photo_presentation(
            context,
            title_prefix=title_prefix,
            canonical_text=lambda ctx: canonical_photo_original_text(
                ctx, type_override=app._context_db_type(ctx)
            ),
            autonomy_text=autonomy_recover,
            is_autonomy=app._is_autonomy_context,
        )
        embed = app.discord.Embed(
            title=plan["title"],
            description=plan["description"],
            color=0xffb6c1,
        )
        if attachment_filename:
            embed.set_image(url=f"attachment://{attachment_filename}")
        else:
            embed.set_image(url=context.get("local_url") or context.get("image_url"))
        for field_name, field_value in plan.get("fields") or []:
            embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(
            text=(
                f"{plan['footer_source']} | {app._context_seedream_model_label(context)}"
                f"{app._generation_level_footer(context)}"
            )
        )
        return embed

    # Preserve all call signatures used by the stable monolith.
    app._photo_display_module = photo_display_module
    app._clean_photo_lineage_text = clean_photo_lineage_text
    app._canonical_photo_original_text = canonical_photo_original_text
    app._default_photo_event_for_module = default_photo_event_for_module
    app._inherit_photo_lineage = inherit_photo_lineage
    app._build_photo_embed = build_photo_embed
    app.LOBSTER_VERSION = MIGRATION_VERSION
    print("🧩 [V11201_MODULE_PATCH_ACTIVE] photo_lineage=external photo_presentation=external")


_activate_photo_modules()

if __name__ == "__main__":
    print(f"🚀 [LOBSTER_ENTRYPOINT] version={MIGRATION_VERSION} stable_base=1.11.17.2")
    try:
        app.asyncio.run(app.main())
    except Exception as exc:
        print(f"❌ [LOBSTER_FATAL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
