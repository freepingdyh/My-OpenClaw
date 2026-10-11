#!/usr/bin/env python3
"""Convert Xiaoxia's verified Qwen Image 2.1 UI workflow into ComfyUI API format.

The source workflow stays in Zeabur persistent storage. This script reads it,
extracts the currently active Qwen 2.1 path, writes an API prompt JSON beside
the source, and refreshes the SHA256 manifest.

Important:
- The prompt text itself is never stored in GitHub; it is copied at runtime
  from the Zeabur-owned source JSON.
- The prompt-enhancer branch is supported only when disabled, which matches
  the currently verified workflow. If it is enabled later, conversion fails
  closed instead of silently changing behavior.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path("/data/memory/qwen21")
SOURCE = ROOT / "workflows" / "xiaoxia_qwen21_special_v1.json"
OUTPUT = ROOT / "workflows" / "xiaoxia_qwen21_special_v1_api.json"
MANIFEST = ROOT / "meta" / "sha256.txt"
DYNAMIC_IMAGE_1_NAME = "image_1.png"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _single(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if len(items) != 1:
        raise RuntimeError(f"expected exactly one {label}, found {len(items)}")
    return items[0]


def _node_by_type(nodes: list[dict[str, Any]], node_type: str) -> dict[str, Any]:
    return _single([n for n in nodes if n.get("type") == node_type], node_type)


def _linked_qwen_encoder(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [n for n in nodes if n.get("type") == "TextEncodeQwenImage21"]
    linked = []
    for node in candidates:
        outputs = node.get("outputs") or []
        if any(output.get("links") for output in outputs):
            linked.append(node)
    return _single(linked, "linked TextEncodeQwenImage21")


def _build_api(ui: dict[str, Any]) -> dict[str, Any]:
    top_nodes = {int(n["id"]): n for n in ui.get("nodes", [])}
    subgraphs = {
        str(s["id"]): s
        for s in ui.get("definitions", {}).get("subgraphs", [])
    }

    main = _single(
        [n for n in ui.get("nodes", []) if str(n.get("type")) in subgraphs],
        "Qwen subgraph instance",
    )
    subgraph = subgraphs[str(main["type"])]
    sg_nodes = subgraph.get("nodes", [])
    values = main.get("widgets_values_named") or {}

    if values.get("switch_1") is not False:
        raise RuntimeError(
            "refine_prompt is enabled; this converter intentionally refuses "
            "to drop the prompt-enhancer branch"
        )

    # Resolve top-level image slots from the actual graph links.
    top_links = {int(link[0]): link for link in ui.get("links", [])}
    image_sources: dict[str, tuple[int, str]] = {}
    for inp in main.get("inputs", []):
        label = str(inp.get("label") or inp.get("name") or "")
        link_id = inp.get("link")
        if not label.startswith("image_") or link_id is None:
            continue
        link = top_links[int(link_id)]
        origin_id = int(link[1])
        origin = top_nodes[origin_id]
        if origin.get("type") != "LoadImage":
            raise RuntimeError(f"{label} is not supplied by LoadImage")
        filename = (origin.get("widgets_values_named") or {}).get("image")
        if not filename:
            raise RuntimeError(f"{label} LoadImage has no filename")
        image_sources[label] = (origin_id, str(filename))

    for required in ("image_1", "image_2", "image_3", "image_4", "image_5", "image_6"):
        if required not in image_sources:
            raise RuntimeError(f"required slot is not connected: {required}")

    unet = _node_by_type(sg_nodes, "UNETLoader")
    vae = _node_by_type(sg_nodes, "VAELoader")
    sampler = _node_by_type(sg_nodes, "KSampler")
    cache = _node_by_type(sg_nodes, "QwenImage21Cache")
    latent = _node_by_type(sg_nodes, "EmptyLatentImage")
    encoder = _linked_qwen_encoder(sg_nodes)

    clip_candidates = [
        n
        for n in sg_nodes
        if n.get("type") == "CLIPLoader"
        and (n.get("widgets_values_named") or {}).get("clip_name") == values.get("clip_name")
    ]
    clip = _single(clip_candidates, "primary CLIPLoader")

    save = _node_by_type(list(top_nodes.values()), "SaveImageAdvanced")

    unet_w = unet.get("widgets_values_named") or {}
    clip_w = clip.get("widgets_values_named") or {}
    sampler_w = sampler.get("widgets_values_named") or {}
    latent_w = latent.get("widgets_values_named") or {}
    save_w = save.get("widgets_values_named") or {}

    api: dict[str, Any] = {}

    # Keep the original node ids where practical; image_1 is renamed to a
    # stable per-request filename uploaded through RunPod input.images.
    image_node_ids: dict[str, str] = {}
    for label, (origin_id, filename) in image_sources.items():
        image_node_ids[label] = str(origin_id)
        api[str(origin_id)] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": DYNAMIC_IMAGE_1_NAME if label == "image_1" else filename
            },
            "_meta": {"title": f"Load {label}"},
        }

    api[str(unet["id"])] = {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": values["unet_name"],
            "weight_dtype": unet_w.get("weight_dtype", "default"),
        },
        "_meta": {"title": "Load Diffusion Model"},
    }

    api[str(clip["id"])] = {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": values["clip_name"],
            "type": clip_w.get("type", "qwen_image"),
            "device": clip_w.get("device", "default"),
        },
        "_meta": {"title": "Load CLIP"},
    }

    api[str(vae["id"])] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": values["vae_name"]},
        "_meta": {"title": "Load VAE"},
    }

    api[str(cache["id"])] = {
        "class_type": "QwenImage21Cache",
        "inputs": {
            "model": [str(unet["id"]), 0],
            "device": values["device"],
            "dtype": values["dtype"],
        },
        "_meta": {"title": "Qwen Image 2.1 Cache"},
    }

    encode_inputs: dict[str, Any] = {
        "clip": [str(clip["id"]), 0],
        "prompt": values["prompt"],
        "negative_prompt": values["negative_prompt"],
        "vae": [str(vae["id"]), 0],
        "resolution": values["resolution"],
    }
    for i in range(1, 11):
        label = f"image_{i}"
        if label in image_node_ids:
            encode_inputs[f"images.image_{i}"] = [image_node_ids[label], 0]

    api[str(encoder["id"])] = {
        "class_type": "TextEncodeQwenImage21",
        "inputs": encode_inputs,
        "_meta": {"title": "Text Encode Qwen Image 2.1"},
    }

    # Preserve the source's custom-size switch.
    if values.get("switch") is True:
        api[str(latent["id"])] = {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": values["width"],
                "height": values["height"],
                "batch_size": latent_w.get("batch_size", 1),
            },
            "_meta": {"title": "Empty Latent Image"},
        }
        latent_input = [str(latent["id"]), 0]
    elif values.get("switch") is False:
        latent_input = [str(encoder["id"]), 2]
    else:
        raise RuntimeError("custom_size switch is missing or invalid")

    api[str(sampler["id"])] = {
        "class_type": "KSampler",
        "inputs": {
            "model": [str(cache["id"]), 0],
            "positive": [str(encoder["id"]), 0],
            "negative": [str(encoder["id"]), 1],
            "latent_image": latent_input,
            "seed": values["seed"],
            "steps": values["steps"],
            "cfg": values["cfg"],
            "sampler_name": values["scheduler"],
            "scheduler": values["scheduler_1"],
            "denoise": sampler_w.get("denoise", 1),
        },
        "_meta": {"title": "KSampler"},
    }

    decode_id = "457"
    if int(decode_id) not in {int(n["id"]) for n in sg_nodes if n.get("type") == "VAEDecode"}:
        decode = _node_by_type(sg_nodes, "VAEDecode")
        decode_id = str(decode["id"])

    api[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [str(sampler["id"]), 0],
            "vae": [str(vae["id"]), 0],
        },
        "_meta": {"title": "VAE Decode"},
    }

    api[str(save["id"])] = {
        "class_type": "SaveImageAdvanced",
        "inputs": {
            "images": [decode_id, 0],
            "filename_prefix": save_w["filename_prefix"],
            "format": save_w["format"],
            "format.bit_depth": save_w["format.bit_depth"],
            "format.input_color_space": save_w["format.input_color_space"],
        },
        "_meta": {"title": "Save Image (Advanced)"},
    }

    return api


def _refresh_manifest() -> None:
    paths = []
    for directory in (ROOT / "refs", ROOT / "workflows"):
        if directory.is_dir():
            paths.extend(
                p for p in directory.iterdir()
                if p.is_file() and not p.name.endswith(".tmp")
            )

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{_sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix())
    ]
    tmp = MANIFEST.with_suffix(".txt.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, MANIFEST)


def main() -> int:
    if not SOURCE.is_file():
        raise RuntimeError(f"source workflow not found: {SOURCE}")

    source_sha = _sha256(SOURCE)
    ui = json.loads(SOURCE.read_text(encoding="utf-8"))
    api = _build_api(ui)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(api, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Parse our own output before replacing the live file.
    json.loads(tmp.read_text(encoding="utf-8"))
    os.replace(tmp, OUTPUT)

    _refresh_manifest()

    print(f"[QWEN21_WORKFLOW_CONVERT] source={SOURCE} sha256={source_sha}")
    print(
        f"[QWEN21_WORKFLOW_CONVERT] api={OUTPUT} "
        f"nodes={len(api)} sha256={_sha256(OUTPUT)}"
    )
    print(
        "[QWEN21_WORKFLOW_CONVERT] preserved "
        f"cfg={api[str(458)]['inputs']['cfg']} "
        f"steps={api[str(458)]['inputs']['steps']} "
        f"seed={api[str(458)]['inputs']['seed']} "
        f"size={api.get('456', {}).get('inputs', {}).get('width')}x"
        f"{api.get('456', {}).get('inputs', {}).get('height')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
