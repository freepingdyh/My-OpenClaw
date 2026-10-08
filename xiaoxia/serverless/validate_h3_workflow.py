#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline contract check for the bundled MiniMax H3 FL2VA API workflow.

No GPU, RunPod account, or model files are required.  This protects the graph
shape before the workflow is ever submitted to a worker.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKFLOW = Path(__file__).resolve().parent / "workflows" / "minimax_h3_fl2va_api.json"

EXPECTED_SINGLE = (
    "LoadImage",
    "UNETLoader",
    "CLIPLoader",
    "MiniMaxH3ImageToVideo",
    "RandomNoise",
    "KSamplerSelect",
    "BasicScheduler",
    "BasicGuider",
    "SamplerCustomAdvanced",
    "VAEDecode",
    "VAEDecodeAudio",
    "CreateVideo",
    "SaveVideo",
)


def _nodes(graph: dict[str, Any], class_type: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (str(k), v)
        for k, v in graph.items()
        if isinstance(v, dict) and v.get("class_type") == class_type
    ]


def main() -> int:
    graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not graph:
        raise RuntimeError("workflow is empty")

    for class_type in EXPECTED_SINGLE:
        rows = _nodes(graph, class_type)
        if len(rows) != 1:
            raise RuntimeError(f"{class_type}: expected 1 node, found {len(rows)}")

    if len(_nodes(graph, "VAELoader")) != 2:
        raise RuntimeError("VAELoader: expected exactly video + audio VAE")

    load = _nodes(graph, "LoadImage")[0][1]
    if load["inputs"].get("image") != "h3_first_frame.png":
        raise RuntimeError("first-frame filename contract changed")

    h3 = _nodes(graph, "MiniMaxH3ImageToVideo")[0][1]["inputs"]
    required_h3 = {"clip", "vae", "first_frame", "prompt", "width", "height", "length"}
    missing = required_h3 - set(h3)
    if missing:
        raise RuntimeError("H3 node missing inputs: " + ", ".join(sorted(missing)))
    if "last_frame" in h3:
        raise RuntimeError("baseline must remain first-frame-only FL2VA")

    sampler = _nodes(graph, "KSamplerSelect")[0][1]["inputs"]
    if sampler.get("sampler_name") != "res_multistep":
        raise RuntimeError("baseline sampler must remain res_multistep")

    scheduler = _nodes(graph, "BasicScheduler")[0][1]["inputs"]
    if scheduler.get("scheduler") != "simple":
        raise RuntimeError("baseline scheduler must remain simple")

    create = _nodes(graph, "CreateVideo")[0][1]["inputs"]
    if create.get("fps") != 24:
        raise RuntimeError("H3 native baseline must remain 24 fps")

    save = _nodes(graph, "SaveVideo")[0][1]["inputs"]
    fmt = save.get("format")
    if not isinstance(fmt, dict) or fmt.get("format") != "mp4":
        raise RuntimeError("SaveVideo must use explicit MP4 dynamic-combo payload")

    print(
        "[H3_WORKFLOW_VALIDATE] ok "
        f"nodes={len(graph)} size={h3.get('width')}x{h3.get('height')} "
        f"length={h3.get('length')} steps={scheduler.get('steps')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
