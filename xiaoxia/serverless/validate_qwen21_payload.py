#!/usr/bin/env python3
"""Offline validation for Xiaoxia's RunPod Serverless Qwen21 request payload."""
from __future__ import annotations

import argparse
import json
import sys

from xiaoxia.media.runpod_serverless import (
    RunPodServerlessError,
    build_qwen21_job_from_path,
    payload_size_bytes,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Local PNG used only as image_1 for payload validation")
    args = parser.parse_args()

    payload = build_qwen21_job_from_path(args.image)
    workflow = payload["input"]["workflow"]

    load_images = {}
    for node_id, node in workflow.items():
        if node.get("class_type") == "LoadImage":
            load_images[str(node_id)] = node["inputs"]["image"]

    sampler = next(
        node for node in workflow.values()
        if node.get("class_type") == "KSampler"
    )

    print("[QWEN21_PAYLOAD_DRYRUN] valid=true")
    print(f"[QWEN21_PAYLOAD_DRYRUN] payload_bytes={payload_size_bytes(payload)}")
    print(
        "[QWEN21_PAYLOAD_DRYRUN] images="
        + json.dumps(load_images, ensure_ascii=False, sort_keys=True)
    )
    print(
        "[QWEN21_PAYLOAD_DRYRUN] sampler="
        + json.dumps(
            {
                "seed": sampler["inputs"].get("seed"),
                "steps": sampler["inputs"].get("steps"),
                "cfg": sampler["inputs"].get("cfg"),
                "sampler_name": sampler["inputs"].get("sampler_name"),
                "scheduler": sampler["inputs"].get("scheduler"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunPodServerlessError as exc:
        print(f"[QWEN21_PAYLOAD_DRYRUN] error={exc}", file=sys.stderr)
        raise SystemExit(1)
