# -*- coding: utf-8 -*-
"""Persistent observability for Qwen /photo reference-scene generation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

VERSION = "1.5.0-qwen-scene-trace-v8-special-delta"
TRACE_PATH = Path("/data/memory/qwen21/meta/latest_scene.json")


def _write(payload: Dict[str, Any]) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRACE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, TRACE_PATH)


def _fingerprint(value: Any) -> str:
    text = str(value or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_qwen_scene_trace(app: Any) -> Dict[str, Any]:
    from xiaoxia.photo import qwen_scene as scene_mod

    original = getattr(scene_mod, "_generate_qwen_scene", None)
    if original is None:
        raise RuntimeError("qwen_scene._generate_qwen_scene not found")
    if getattr(original, "_xiaoxia_qwen_scene_trace_installed", False):
        return {"version": VERSION, "installed": False, "trace_path": str(TRACE_PATH)}

    async def traced_generate(app_obj: Any, *, scene_delta: str, subject_delta: str, camera_delta: str, mood_delta: str, special_delta: str = "") -> dict:
        trace = {
            "mode": "reference_scene_generation",
            "status": "starting",
            "trace_version": VERSION,
            "created_at": app_obj.datetime.now(app_obj.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "scene_delta": scene_delta,
            "camera_delta": camera_delta,
            "mood_delta": mood_delta,
            "subject_delta_present": bool(str(subject_delta or "").strip()),
            "subject_delta_length": len(str(subject_delta or "")),
            "subject_delta_sha256": _fingerprint(subject_delta),
            "special_delta_present": bool(str(special_delta or "").strip()),
            "special_delta_length": len(str(special_delta or "")),
            "special_delta_sha256": _fingerprint(special_delta),
            "reference_slots_expected": {
                "image1": "image_4_body_full.png",
                "image2": "image_2_face_front.png",
                "image3": "image_3_face_45.png",
                "image4": "image_5_body_half.png",
                "image5": "image_6_body_clothed.png",
            },
            "reference_mode_expected": "official_multiref_with_vae_reference_latents",
            "scene_workflow_mode_expected": "dedicated_five_ref_no_canvas_api_v1",
            "scene_workflow_file_expected": "xiaoxia/serverless/workflows/qwen21_reference_scene_api.json",
            "edit_target_expected": False,
            "ratio_follow_expected": "",
            "steps_expected": 25,
        }
        _write(trace)

        try:
            result = await original(
                app_obj,
                scene_delta=scene_delta,
                subject_delta=subject_delta,
                camera_delta=camera_delta,
                mood_delta=mood_delta,
                special_delta=special_delta,
            )
        except Exception as exc:
            trace["status"] = "failed"
            trace["error"] = f"{type(exc).__name__}: {exc}"
            trace["failed_at"] = app_obj.datetime.now(app_obj.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            _write(trace)
            raise

        result = dict(result or {})
        trace.update({
            "status": "completed",
            "completed_at": app_obj.datetime.now(app_obj.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "rewritten_prompt": result.get("qwen_compiled_scene_prompt"),
            "final_qwen_prompt": result.get("qwen_final_prompt"),
            "wh_ratio": result.get("qwen_wh_ratio"),
            "ratio_follow": result.get("qwen_ratio_follow"),
            "reference_set": result.get("qwen_reference_set"),
            "reference_mode": result.get("qwen_reference_mode"),
            "scene_workflow_mode": result.get("qwen_scene_workflow_mode"),
            "scene_workflow_file": result.get("qwen_scene_workflow_file"),
            "seed": result.get("qwen_seed"),
            "steps": result.get("qwen_steps"),
            "result_url": result.get("local_url") or result.get("image_url"),
            "source_mode": result.get("source_mode"),
            "scene_summary": result.get("scene_summary"),
            "camera_summary": result.get("camera_summary"),
            "mood_summary": result.get("mood_summary"),
            "special_delta": result.get("qwen_special_delta"),
        })
        _write(trace)
        result["qwen_scene_trace_path"] = str(TRACE_PATH)
        return result

    traced_generate._xiaoxia_qwen_scene_trace_installed = True
    traced_generate._xiaoxia_qwen_scene_trace_original = original
    scene_mod._generate_qwen_scene = traced_generate

    print(f"✅ [QWEN_SCENE_TRACE_INSTALLED] version={VERSION} path={TRACE_PATH}")
    return {"version": VERSION, "installed": True, "trace_path": str(TRACE_PATH)}
