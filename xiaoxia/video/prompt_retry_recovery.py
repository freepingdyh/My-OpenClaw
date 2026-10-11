# -*- coding: utf-8 -*-
"""v1.12.06ag — recover H3 body.prompt 422 without changing the normal path.

Normal request remains v1.12.06af visual-only.  Only when fal reports
content_policy_violation at body.prompt do we retry, first with the same Hero Action
alone, then with the previously proven generic minimal-motion prompt.  Image/model/
duration/resolution/safety/expansion stay unchanged.  Voiceover is still post-mix only.
"""
from __future__ import annotations

from typing import Any, Dict

from xiaoxia.video import diagnostics, director_audio_separation, h3_director_mode, voiceover_mode

_ORIGINAL_GENERATE = director_audio_separation._generate_h3_visual_then_sulafat
_ORIGINAL_SUBSCRIBE = voiceover_mode._subscribe


def _is_prompt_422(exc: Exception) -> bool:
    info = diagnostics.extract_h3_error(exc)
    return (
        str(info.get("type") or "").lower() == "content_policy_violation"
        and str(info.get("loc") or "").lower() == "body.prompt"
    )


def _action_only_prompt(plan: Dict[str, str]) -> str:
    action = str(plan.get("hero_action") or "").strip()
    return f"Use Image 1 as the starting frame. {action}" if action else "Use Image 1 as the starting frame. Add subtle natural motion."


def _minimal_motion_prompt() -> str:
    return "Use Image 1 as the starting frame. Add subtle natural motion with gentle blinking, breathing, and small natural head movement."


async def _subscribe_with_prompt_recovery(app: Any, model_id: str, arguments: Dict[str, Any], tag: str) -> Dict[str, Any]:
    try:
        return await _ORIGINAL_SUBSCRIBE(app, model_id, arguments, tag)
    except Exception as first_exc:
        if not _is_prompt_422(first_exc):
            raise

        # The current Director plan is attached temporarily by the wrapper below.
        plan = getattr(app, "_xiaoxia_h3_retry_plan", {}) or {}
        retry_args = dict(arguments)
        retry_args["prompt"] = _action_only_prompt(plan)
        print(f"⚠️ [H3_PROMPT_422_RETRY_ACTION_ONLY] prompt={retry_args['prompt']!r}")
        try:
            result = await _ORIGINAL_SUBSCRIBE(app, model_id, retry_args, "H3_PROMPT_RETRY_ACTION_ONLY")
            if isinstance(result, dict):
                result["_xiaoxia_prompt_retry"] = "action_only"
                result["_xiaoxia_actual_submitted_prompt"] = retry_args["prompt"]
            return result
        except Exception as second_exc:
            if not _is_prompt_422(second_exc):
                raise

            retry_args["prompt"] = _minimal_motion_prompt()
            print(f"⚠️ [H3_PROMPT_422_RETRY_MINIMAL] prompt={retry_args['prompt']!r}")
            result = await _ORIGINAL_SUBSCRIBE(app, model_id, retry_args, "H3_PROMPT_RETRY_MINIMAL")
            if isinstance(result, dict):
                result["_xiaoxia_prompt_retry"] = "minimal_motion"
                result["_xiaoxia_actual_submitted_prompt"] = retry_args["prompt"]
            return result


async def _generate_with_recovery(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    # Capture exactly the Director plan used by af without asking Gemini a second time.
    original_builder = h3_director_mode.build_h3_director_plan

    async def capture_builder(app_: Any, context_: Dict[str, Any], cfg_: Dict[str, Any]):
        plan = await original_builder(app_, context_, cfg_)
        app._xiaoxia_h3_retry_plan = dict(plan or {})
        return plan

    h3_director_mode.build_h3_director_plan = capture_builder
    old_subscribe = voiceover_mode._subscribe
    voiceover_mode._subscribe = _subscribe_with_prompt_recovery
    try:
        result = await _ORIGINAL_GENERATE(app, context)
        retry = ""
        # af does not expose provider metadata; log recovery at subscribe time.
        if isinstance(result, dict):
            result["prompt_recovery_enabled"] = True
        return result
    finally:
        h3_director_mode.build_h3_director_plan = original_builder
        voiceover_mode._subscribe = old_subscribe
        try:
            delattr(app, "_xiaoxia_h3_retry_plan")
        except Exception:
            pass


def install_prompt_retry_recovery(app: Any) -> Dict[str, Any]:
    if getattr(h3_director_mode, "_xiaoxia_prompt_retry_recovery_installed", False):
        return {"patched": False, "reason": "already_installed"}

    h3_director_mode._generate_h3_native_directed = _generate_with_recovery
    if hasattr(app, "h3_generate_native_directed"):
        app.h3_generate_native_directed = _generate_with_recovery
    h3_director_mode._xiaoxia_prompt_retry_recovery_installed = True
    return {
        "patched": True,
        "normal_path": "v1.12.06af unchanged",
        "retry_1": "same hero action only",
        "retry_2": "generic minimal motion",
        "retry_trigger": "content_policy_violation/body.prompt only",
        "image_transport": "v1.12.06ae preserved",
        "voiceover": "Sulafat postmix only",
    }
