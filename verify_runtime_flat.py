#!/usr/bin/env python3
"""Static equivalence gate for xiaoxia_runtime_flat.py.

Does not import application code. Fails closed if installer order, required special
side effects, or final Pose guard ordering differs from the frozen active chain.
"""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TARGET=ROOT/"xiaoxia_runtime_flat.py"

EXPECTED=[
"_activate_photo_modules",
"install_photo_result_view_router","register_health_commands",
"install_wardrobe_core","install_scene_fidelity","install_photo_semantic_contract_repair",
"install_photo_scene_observability","install_oauth_branding_pages","install_h3_video_button",
"install_legacy_video_command","install_h3_dialogue_safety","install_h3_policy_fallback",
"install_h3_policy_fallback_v2","install_h3_diagnostics","install_h3_prompt_policy_fallback",
"install_voiceover_mode","install_h3_trace","install_h3_trace_command","install_h3_image_url_retry",
"install_h3_image_url_retry","install_h3_trace_command","install_h3_director_mode",
"install_h3_director_mode","install_h3_archive","install_video_room_ui","install_model_refresh",
"install_video_understanding","install_adaptive_audio","install_auto_video_context",
"install_love_display_cleanup","install_seedance15_video_button","install_seedance15_video_button",
"install_h3_archive_retry","install_sensual_motion_director","install_legacy_archive_ui",
"install_archive_privacy","install_video_room_privacy","install_archive_delete_command",
"install_video_delete_command","install_legacy_story_direction","install_user_semantic_fidelity",
"install_slim_h3_prompt","install_fal_native_image_transport","install_director_audio_separation",
"install_prompt_retry_recovery","install_h3_native_voice","install_love_display_cleanup",
"install_camera_director","install_pose_commands","install_wardrobe_pose_test","install_h3_typeerror_fix",
"install_native_slash_rollback","install_director_signature_fix","install_photo_pose_input",
"install_repair_reference_patch","install_seedream_photo_prompt_boundary","install_pose_output_guard",
"install_final_pose_prompt_patch",
]

def call_name(call):
    f=call.func
    if isinstance(f,ast.Name): return f.id
    if isinstance(f,ast.Attribute): return f.attr
    return None

tree=ast.parse(TARGET.read_text(encoding="utf-8"),filename=str(TARGET))
fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_activate_flat"),None)
if not fn: raise SystemExit("FAIL: _activate_flat missing")
actual=[]
for n in ast.walk(fn):
    if isinstance(n,ast.Call):
        name=call_name(n)
        if name in set(EXPECTED):
            actual.append((getattr(n,"lineno",0),name))
actual=[name for _,name in sorted(actual)]
if actual!=EXPECTED:
    print("FAIL: installer sequence mismatch")
    for i in range(max(len(actual),len(EXPECTED))):
        a=actual[i] if i<len(actual) else "<missing>"
        e=EXPECTED[i] if i<len(EXPECTED) else "<extra>"
        if a!=e: print(f"  {i+1:02d}: expected={e} actual={a}")
    raise SystemExit(1)

src=TARGET.read_text(encoding="utf-8")
required=[
'h3_director_mode._send_success_interaction = h3_archive._send_success_with_archive',
'delattr(routed, "_xiaoxia_seedance15_installed")',
'delattr(app, "_xiaoxia_love_display_cleanup_installed")',
'app.PhotoResultView = routed_h3_photo_result_view',
'activated["pose_final_prompt_guard"] = install_final_pose_prompt_patch(app)',
]
missing=[x for x in required if x not in src]
if missing:
    print("FAIL: special side effects missing:",missing); raise SystemExit(1)
if src.index('install_pose_output_guard(app)') > src.index('install_final_pose_prompt_patch(app)'):
    print("FAIL: final Pose guard ordering"); raise SystemExit(1)
print(f"PASS: {len(EXPECTED)} ordered calls + {len(required)} special side-effect guards")
