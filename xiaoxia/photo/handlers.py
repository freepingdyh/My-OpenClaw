# -*- coding: utf-8 -*-
"""External PhotoResultView action handlers for Xiaoxia v1.12.02b.

The legacy methods remain in lobster_discord.py only as a rollback/reference copy.
At runtime PhotoResultView buttons are rewired to these handlers, so business-logic
ownership for the photo action surface lives outside the monolith.
"""
from __future__ import annotations

import os
import traceback
from typing import Any

EXTRACTION_VERSION = "1.12.02b"


async def more(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.defer(thinking=True)
    context = dict(view.context)
    if str(context.get("type") or context.get("db_type") or context.get("source_mode") or "").lower() == "photobook":
        try:
            await app._prepare_photobook_more_choices(interaction, context)
        except Exception as exc:
            print(f"⚠️ [PHOTOBOOK_MORE_PREPARE_FAILED] {type(exc).__name__}: {exc}")
            traceback.print_exc()
            await interaction.followup.send(f"⚠️ More 鏡頭分析失敗：`{str(exc)[:1200]}`", ephemeral=True)
        return

    context.pop("__trace_context", None)
    context["trace_action"] = "photo_more"
    context["user_input"] = "More button from previous photo"
    if str(context.get("source_mode") or context.get("type") or "").lower() == "love_intent":
        context, root_prompt = app._love_refresh_prompt_context(context)
    else:
        root_prompt = app._photo_context_root_scene_prompt(context)
    context["root_prompt_base"] = root_prompt
    context["prompt_base"] = (
        root_prompt
        + "\nCONTINUATION: Keep the same story, scene, activity, people boundary, and outfit. Create one fresh natural variation in pose, expression, camera angle, and composition only."
    )
    try:
        if context.get("v5_refine_mode") and (
            context.get("v5_background_generated_url")
            or context.get("v5_background_local_url")
            or context.get("v5_background_local_path")
        ):
            new_context = await app._more_with_existing_v5_background(context)
        else:
            new_context = await app._generate_photo_from_context(context)
        db = app.load_memory()
        db.insert(0, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
        app.save_memory(db)
        app._set_current_outfit_state(app._build_outfit_state_from_context(new_context))
        app._log_wardrobe_usage_from_context(new_context, purpose="photo_more")
        new_view = app.PhotoResultView(new_context)
        file, filename = app._photo_discord_file(new_context)
        embed = app._build_result_embed(new_context, title_prefix="📸 More", attachment_filename=filename if file else None)
        if file:
            print(f"📤 [PHOTO_MORE_SEND_WITH_FILE] filename={filename}")
            sent = await interaction.followup.send(embed=embed, file=file, view=new_view)
        else:
            print("📤 [PHOTO_MORE_SEND_URL_FALLBACK]")
            sent = await interaction.followup.send(embed=embed, view=new_view)
        new_context["message_id"] = sent.id
        app.photo_generation_contexts[sent.id] = new_context
        new_view.context = new_context
    except Exception as exc:
        await interaction.followup.send(f"⚠️ More 生成失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def dice_reroll(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.defer()
    context = dict(view.context)
    context.pop("__trace_context", None)
    context["trace_action"] = "photo_reroll_replace"
    context["user_input"] = "骰子取代 from previous photo"
    if str(context.get("source_mode") or context.get("type") or "").lower() == "love_intent":
        context, root_prompt = app._love_refresh_prompt_context(context)
    else:
        root_prompt = app._photo_context_root_scene_prompt(context)
    context["root_prompt_base"] = root_prompt
    context["prompt_base"] = (
        root_prompt
        + "\nREROLL: Keep the same core story, activity, people boundary, outfit, time of day, and mood. Recompose freely, but do not change the subject or invent a new scene."
    )
    try:
        old_url = context.get("local_url") or context.get("image_url")
        if context.get("v5_refine_mode") and (
            context.get("v5_background_generated_url")
            or context.get("v5_background_local_url")
            or context.get("v5_background_local_path")
        ):
            new_context = await app._reroll_with_existing_v5_background(context)
        else:
            new_context = await app._generate_photo_from_context(context)
        app._replace_photo_db_record(old_url, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
        app._sync_autonomy_today_after_photo_replace(context, new_context)
        app._safe_delete_vault_image(old_url)
        app._set_current_outfit_state(app._build_outfit_state_from_context(new_context))
        app._log_wardrobe_usage_from_context(new_context, purpose="photo_reroll")
        view.context = new_context
        if interaction.message:
            new_context["message_id"] = interaction.message.id
            app.photo_generation_contexts[interaction.message.id] = new_context
            await app._edit_photo_message_with_file(interaction.message, new_context, view=view, title_prefix="📸 骰子取代")
    except Exception as exc:
        await interaction.followup.send(f"⚠️ 骰子取代失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def full_reroll(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.defer(thinking=True)
    context = dict(view.context)
    mode_key = str(context.get("type") or context.get("source_mode") or "").lower()
    is_autonomy = app._is_autonomy_context(context)
    if mode_key != "cosplay" and not is_autonomy:
        await interaction.followup.send("🔄 完整重擲目前支援 cosplay 與 /小俠自主；這張先用『骰子取代』重畫。", ephemeral=True)
        return
    status = None
    try:
        if mode_key == "cosplay":
            status = await interaction.followup.send("🔄 小俠正在重新抽題、重寫內文、重新生圖…", wait=True)
            old_url = context.get("local_url") or context.get("image_url")
            new_context = await app._create_cosplay_context_for_reroll(context.get("user_mode_request") or "auto", msg=status, force_new_topic=True)
            app._replace_photo_db_record(old_url, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
            app._safe_delete_vault_image(old_url)
        else:
            status = await interaction.followup.send("🔄 小俠正在重新安排今天的自主活動、重寫分享、重新拍照…", wait=True)
            old_url = context.get("local_url") or context.get("image_url")
            new_context = await app._create_autonomy_context_for_full_reroll(context, msg=status)
            app._replace_photo_db_record(old_url, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
            app._safe_delete_vault_image(old_url)
        view.context = new_context
        if interaction.message:
            new_context["message_id"] = interaction.message.id
            app.photo_generation_contexts[interaction.message.id] = new_context
            await app._edit_photo_message_with_file(interaction.message, new_context, view=view, title_prefix="🔄 重擲")
        if status:
            try:
                await status.delete()
            except Exception:
                pass
    except Exception as exc:
        if status:
            try:
                await status.edit(content=f"⚠️ 重擲失敗：`{str(exc)[:1500]}`")
                return
            except Exception:
                pass
        await interaction.followup.send(f"⚠️ 重擲失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def allure_fantasy(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.defer(thinking=True)
    context = dict(view.context)
    if str(context.get("type") or context.get("source_mode") or "").lower() != "cosplay":
        await interaction.followup.send("💋『只給大俠』目前只支援 cosplay 圖。", ephemeral=True)
        return
    status = None
    try:
        status = await interaction.followup.send("💋 小俠正在把這個角色帶進『只給大俠』版本…", wait=True)
        new_context = await app._create_cosplay_allure_fantasy_context(context, msg=status)
        db = app.load_memory()
        db.insert(0, app._photo_db_payload(new_context, type_override=app._context_db_type(new_context)))
        app.save_memory(db)
        new_view = app.PhotoResultView(new_context)
        file, filename = app._photo_discord_file(new_context)
        embed = app._build_result_embed(new_context, title_prefix="💋 只給大俠", attachment_filename=filename if file else None)
        if file:
            sent = await interaction.followup.send(embed=embed, file=file, view=new_view)
        else:
            sent = await interaction.followup.send(embed=embed, view=new_view)
        new_context["message_id"] = sent.id
        app.photo_generation_contexts[sent.id] = new_context
        new_view.context = new_context
        if status:
            try:
                await status.delete()
            except Exception:
                pass
    except Exception as exc:
        if status:
            try:
                await status.edit(content=f"⚠️ 只給大俠失敗：`{str(exc)[:1500]}`")
                return
            except Exception:
                pass
        await interaction.followup.send(f"⚠️ 只給大俠失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def v5_refine(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.defer(thinking=True)
    context = dict(view.context)
    if context.get("v5_refine_mode"):
        await interaction.followup.send("✨ 這張已經是 v5.0 場景升級結果；請從原本的 v4.5 成圖再按『v5.0 場景升級』，避免連續重算讓小俠漂掉。", ephemeral=True)
        return
    target_url = context.get("local_url") or context.get("image_url")
    if not target_url and not context.get("local_path"):
        await interaction.followup.send("⚠️ 找不到這張 v4.5 成圖，無法交給 v5.0 場景升級。", ephemeral=True)
        return
    try:
        new_context = await app._generate_seedream_v5_refine_from_v45(context)
        new_context["v5_replace_target_url"] = target_url
        new_context["v5_replace_target_message_id"] = getattr(interaction.message, "id", None)
        db = app.load_memory()
        db_type = app._context_db_type(new_context)
        db.insert(0, app._photo_db_payload(new_context, type_override=db_type))
        app.save_memory(db)
        new_view = app.PhotoResultView(new_context)
        file, filename = app._photo_discord_file(new_context)
        embed = app._build_result_embed(new_context, title_prefix="✨ v5.0 場景升級", attachment_filename=filename if file else None)
        if file:
            sent = await interaction.followup.send(embed=embed, file=file, view=new_view)
        else:
            sent = await interaction.followup.send(embed=embed, view=new_view)
        new_context["message_id"] = sent.id
        app.photo_generation_contexts[sent.id] = new_context
        new_view.context = new_context
    except Exception as exc:
        await interaction.followup.send(f"⚠️ v5.0 場景升級失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def inspect_reference(view: Any, interaction: Any, app: Any) -> None:
    context = dict(view.context)
    mode_key = str(context.get("source_mode") or context.get("type") or "").lower()
    is_cosplay = mode_key == "cosplay"
    clothing_local_path = context.get("cosplay_clothing_ref_local_path") or context.get("nano_clothing_ref_local_path")
    clothing_local_url = context.get("cosplay_clothing_ref_local_url") or context.get("nano_clothing_ref_local_url")
    clothing_summary = app._clean_text_compact(context.get("cosplay_clothing_ref_summary") or context.get("nano_clothing_ref_summary") or "")
    clothing_provider = app._clean_text_compact(context.get("cosplay_clothing_ref_provider") or context.get("nano_clothing_ref_provider") or app.COSPLAY_NANO_CLOTHING_REF_LABEL)
    bg_local_path = context.get("v5_background_local_path")
    bg_local_url = context.get("v5_background_local_url") or context.get("v5_background_generated_url")
    danbooru_trace = context.get("cosplay_danbooru_trace") or {}

    if clothing_local_path or clothing_local_url or (is_cosplay and danbooru_trace):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            source_path = context.get("cosplay_clothing_ref_source_path") if is_cosplay else None
            source_original_url = context.get("cosplay_clothing_ref_source_original_url") if is_cosplay else None
            source_local_url = context.get("cosplay_clothing_ref_source_local_url") if is_cosplay else None
            source_page_url = context.get("cosplay_clothing_ref_source_page_url") if is_cosplay else None
            source_kind = app._clean_text_compact(context.get("cosplay_clothing_ref_source_kind") or "") if is_cosplay else ""

            def _join_items(items, limit=6, cap=900):
                vals = [str(x).strip() for x in (items or []) if str(x).strip()][:limit]
                text = "\n".join([f"• {x}" for x in vals])
                return text[:cap] if text else "（無）"

            def _join_pairs(rows, limit=6, cap=900):
                vals = []
                for row in (rows or [])[:limit]:
                    if not isinstance(row, dict):
                        continue
                    label = str(row.get("alias") or row.get("tags") or row.get("character_tag") or "").strip()
                    count = row.get("result_count")
                    mode = str(row.get("mode") or row.get("query_mode") or "").strip()
                    piece = label
                    if mode:
                        piece = f"[{mode}] {piece}"
                    if count is not None:
                        piece = f"{piece} ({count})"
                    vals.append(piece)
                text = "\n".join([f"• {x}" for x in vals])
                return text[:cap] if text else "（無）"

            embeds = []
            files = []
            if is_cosplay and (source_path or source_original_url or source_local_url):
                source_label = "Danbooru 自動角色參考原圖" if source_kind == "danbooru" else "大俠提供的原始角色參考圖"
                source_embed = app.discord.Embed(title="🖼️ 原始角色參考圖（debug）", description=source_label, color=app.discord.Color.dark_teal())
                if source_page_url:
                    source_embed.add_field(name="來源頁", value=str(source_page_url)[:1024], inline=False)
                if source_kind == "danbooru":
                    selected_post = danbooru_trace.get("selected_post") or {}
                    if selected_post:
                        vision_text = f"✅ 通過｜confidence={selected_post.get('vision_confidence', '—')}\n{str(selected_post.get('vision_reason') or '')[:700]}"
                        source_embed.add_field(name="Gemini Vision Gate", value=vision_text[:1024], inline=False)
                if source_path and os.path.exists(str(source_path)):
                    src_filename = f"source_{os.path.basename(str(source_path))}"
                    src_file = app.discord.File(str(source_path), filename=src_filename)
                    files.append(src_file)
                    source_embed.set_image(url=f"attachment://{src_filename}")
                elif source_local_url or source_original_url:
                    source_embed.set_image(url=str(source_local_url or source_original_url))
                embeds.append(source_embed)

            if clothing_local_path or clothing_local_url:
                nano_embed = app.discord.Embed(
                    title="👗 Nano 服裝參考（debug）",
                    description=("這是從大俠附圖整理出的服裝參考，交給 Seedream 當 Figure 10 使用。" if not is_cosplay else f"這是 {clothing_provider} 提供、交給 Seedream 當 Figure 10 使用的服裝參考。"),
                    color=app.discord.Color.blurple(),
                )
                if clothing_summary:
                    nano_embed.add_field(name="服裝摘要", value=clothing_summary[:1024], inline=False)
                if clothing_local_path and os.path.exists(str(clothing_local_path)):
                    filename = f"nano_{os.path.basename(str(clothing_local_path))}"
                    file = app.discord.File(str(clothing_local_path), filename=filename)
                    files.append(file)
                    nano_embed.set_image(url=f"attachment://{filename}")
                    if clothing_local_url:
                        nano_embed.add_field(name="Nano Image URL", value=str(clothing_local_url)[:1024], inline=False)
                elif clothing_local_url:
                    nano_embed.set_image(url=str(clothing_local_url))
                    nano_embed.add_field(name="Nano Image URL", value=str(clothing_local_url)[:1024], inline=False)
                embeds.append(nano_embed)
            elif is_cosplay and danbooru_trace:
                matched = bool(danbooru_trace.get("matched"))
                diag = app.discord.Embed(
                    title="👗 Cosplay 參考診斷（debug）",
                    description=("這次有跑 Danbooru 自動搜尋，但最後沒有做出可用的 Nano 服裝參考。" if not matched else "這次有跑 Danbooru 自動搜尋。"),
                    color=app.discord.Color.orange(),
                )
                char_name = app._clean_text_compact(danbooru_trace.get("character_name") or context.get("cosplay_character_name") or "")
                work_title = app._clean_text_compact(danbooru_trace.get("work_title") or context.get("cosplay_work_title") or "")
                failure_reason = app._clean_text_compact(danbooru_trace.get("failure_reason") or "")
                if char_name or work_title:
                    diag.add_field(name="角色 / 作品", value=f"{char_name or '（未解析）'}\n{work_title or '（未解析）'}"[:1024], inline=False)
                if failure_reason:
                    diag.add_field(name="未採用原因", value=failure_reason[:1024], inline=False)
                alias_hints = danbooru_trace.get("alias_hints") or {}
                diag.add_field(name="查詢別名", value=_join_items((alias_hints.get("combined_aliases") or []) + (alias_hints.get("character_aliases") or []), limit=8), inline=False)
                diag.add_field(name="候選角色 tag", value=_join_items(danbooru_trace.get("selected_character_tags") or [], limit=8), inline=False)
                diag.add_field(name="tag 查詢紀錄", value=_join_pairs(danbooru_trace.get("tag_queries") or [], limit=6), inline=False)
                diag.add_field(name="post 查詢紀錄", value=_join_pairs(danbooru_trace.get("post_queries") or [], limit=6), inline=False)
                vision_checks = danbooru_trace.get("vision_checks") or []
                if vision_checks:
                    vision_preview = []
                    for row in vision_checks[:5]:
                        if not isinstance(row, dict):
                            continue
                        mark = "✅" if row.get("accepted") else "❌"
                        vision_preview.append(f"{mark} post {row.get('post_id')} | conf {row.get('confidence')} | {str(row.get('reason') or row.get('obvious_conflict') or '')[:160]}")
                    diag.add_field(name="Gemini Vision 驗證", value=_join_items(vision_preview, limit=5), inline=False)
                selected_post = danbooru_trace.get("selected_post") or {}
                if selected_post:
                    diag.add_field(name="最終採用 post", value=str(selected_post)[:1024], inline=False)
                elif danbooru_trace.get("candidate_posts"):
                    preview = []
                    for row in (danbooru_trace.get("candidate_posts") or [])[:5]:
                        if not isinstance(row, dict):
                            continue
                        preview.append(f"post {row.get('post_id')} | {row.get('character_tag')} | {row.get('query_mode')} | {row.get('score')}")
                    diag.add_field(name="候選 post 前幾名", value=_join_items(preview, limit=5), inline=False)
                if danbooru_trace.get("download_attempts"):
                    preview = []
                    for row in (danbooru_trace.get("download_attempts") or [])[:4]:
                        if not isinstance(row, dict):
                            continue
                        preview.append(f"post {row.get('post_id')}: {str(row.get('error') or '')[:120]}")
                    diag.add_field(name="下載失敗紀錄", value=_join_items(preview, limit=4), inline=False)
                embeds.append(diag)
            await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 顯示服裝參考圖失敗：`{str(exc)[:1500]}`", ephemeral=True)
        return

    if not bg_local_path and not bg_local_url:
        await interaction.response.send_message("這張沒有可查看的 v5.0 背景圖。", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        embed = app.discord.Embed(title="🪟 v5.0 背景圖（debug）", description="這是 v5.0 先產生、再交給 v4.5 當 Figure 9 使用的背景板。", color=app.discord.Color.blurple())
        if bg_local_path and os.path.exists(str(bg_local_path)):
            filename = os.path.basename(str(bg_local_path))
            file = app.discord.File(str(bg_local_path), filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            if bg_local_url:
                embed.add_field(name="Vault URL", value=bg_local_url[:1024], inline=False)
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            if bg_local_url:
                embed.set_image(url=str(bg_local_url))
                embed.add_field(name="Image URL", value=str(bg_local_url)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(f"⚠️ 顯示 v5.0 背景圖失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def adopt_v5(view: Any, interaction: Any, app: Any) -> None:
    context = dict(view.context)
    target_url = context.get("v5_replace_target_url")
    target_mid = context.get("v5_replace_target_message_id")
    if not target_url:
        await interaction.response.send_message("這張不是 v5.0 場景升級結果，沒有可取代的 v4.5 原圖。", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        db_type = app._context_db_type(context)
        app._replace_photo_db_record(target_url, app._photo_db_payload(context, type_override=db_type))
        app._sync_autonomy_today_after_photo_replace(context, context)
        app._safe_delete_vault_image(target_url)
        if target_mid and interaction.channel:
            try:
                target_message = await interaction.channel.fetch_message(int(target_mid))
                adopted_context = dict(context)
                adopted_context["message_id"] = target_message.id
                app.photo_generation_contexts[target_message.id] = adopted_context
                await app._edit_photo_message_with_file(target_message, adopted_context, view=app.PhotoResultView(adopted_context), title_prefix="✅ 採用 v5.0 場景升級")
                if str(adopted_context.get("source_mode") or "").strip().lower() == "love_intent":
                    app._love_record_awareness(adopted_context, status="adopted")
            except Exception as edit_exc:
                print(f"⚠️ [V5_ADOPT_EDIT_SOURCE_FAILED] {type(edit_exc).__name__}: {edit_exc}")
        await interaction.followup.send("✅ 已採用這張 v5.0 場景升級版並取代 v4.5 來源紀錄。", ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(f"⚠️ 採用 v5.0 場景升級版取代來源失敗：`{str(exc)[:1500]}`", ephemeral=True)


async def repair(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.send_modal(app.PhotoRepairModal(view.context))


async def save_wardrobe(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.send_modal(app.WardrobeSaveModal(view.context))


async def upload_project(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.send_modal(app.PhotoNameModal(view.context, "project"))


async def upload_diary(view: Any, interaction: Any, app: Any) -> None:
    await interaction.response.send_modal(app.PhotoNameModal(view.context, "diary"))


HANDLERS = {
    "more": more,
    "dice_reroll": dice_reroll,
    "full_reroll": full_reroll,
    "allure_fantasy": allure_fantasy,
    "v5_refine": v5_refine,
    "inspect_v5_background": inspect_reference,
    "inspect_clothing_reference": inspect_reference,
    "adopt_v5": adopt_v5,
    "repair": repair,
    "save_wardrobe": save_wardrobe,
    "upload_project": upload_project,
    "upload_diary": upload_diary,
}
