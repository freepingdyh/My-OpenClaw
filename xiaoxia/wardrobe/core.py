# -*- coding: utf-8 -*-
"""Wardrobe / Outfit core extracted from the Xiaoxia monolith.

v1.12.03 owns the low-level wardrobe persistence, category normalization,
current/pending outfit state, wardrobe lookup/matching, generation references,
and item persistence helpers. Legacy copies remain in lobster_discord.py only as
an immediate rollback/reference path.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime

EXTRACTION_VERSION = "1.12.03"
_APP = None


def _app():
    if _APP is None:
        raise RuntimeError("wardrobe core is not installed")
    return _APP


def _clean(value):
    return _app()._clean_text_compact(value)


def load_wardrobe():
    app = _app()
    if not os.path.exists(app.WARDROBE_DATA_PATH):
        return []
    try:
        with open(app.WARDROBE_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_wardrobe(items):
    with open(_app().WARDROBE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_wardrobe_usage_log():
    app = _app()
    if not os.path.exists(app.WARDROBE_USAGE_LOG_PATH):
        return []
    try:
        with open(app.WARDROBE_USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_wardrobe_usage_log(entries):
    trimmed = entries[-500:] if isinstance(entries, list) else []
    with open(_app().WARDROBE_USAGE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def normalize_main_category(value, fallback=None):
    app = _app()
    raw = _clean(value).replace("/", "／")
    if not raw:
        return fallback if fallback in app.WARDROBE_MAIN_CATEGORIES else "上衣"
    if raw in app.WARDROBE_MAIN_CATEGORIES:
        return raw
    if raw in app.WARDROBE_CATEGORY_ALIASES:
        return app.WARDROBE_CATEGORY_ALIASES[raw]
    if raw == "睡衣／居家服":
        return "睡衣／居家服"
    return fallback if fallback in app.WARDROBE_MAIN_CATEGORIES else None


def normalize_sub_category(main_category, value):
    app = _app()
    main_category = normalize_main_category(main_category, fallback="上衣") or "上衣"
    options = app.WARDROBE_SUBCATEGORY_OPTIONS.get(main_category, [main_category])
    raw = _clean(value)
    if not raw:
        return options[0]
    aliases = {
        "連衣裙": "洋裝", "連身裙": "洋裝", "連身洋裝": "洋裝", "背心裙": "洋裝",
        "小洋裝": "短洋裝", "迷你洋裝": "短洋裝", "連身短洋裝": "短洋裝",
        "中長洋裝": "洋裝", "茶歇裙": "洋裝", "日常洋裝": "洋裝",
        "小禮服": "禮服", "晚宴禮服": "禮服", "舞台洋裝": "禮服",
        "連體褲": "連身褲", "連衣褲": "連身褲", "短連體褲": "短連身褲", "短連衣褲": "短連身褲",
        "長連體褲": "長連身褲", "長連衣褲": "長連身褲", "jumpsuit": "連身褲", "romper": "短連身褲",
        "半裙": "半身裙", "裙": "半身裙", "褲裙": "褲裙",
        "短裙套裝": "裙裝套裝", "百褶裙套裝": "裙裝套裝", "長裙套裝": "裙裝套裝",
        "連衣裙套裝": "裙裝套裝", "上衣長裙套裝": "裙裝套裝", "蓬裙套裝": "裙裝套裝",
        "短褲套裝": "褲裝套裝", "甜美褲裝套裝": "褲裝套裝",
        "運動服裝套裝": "運動套裝", "運動居家套裝": "運動套裝",
        "兩件式套裝": "上下身套裝", "三件式套裝": "上下身套裝",
        "休閒套裝": "上下身套裝", "甜美套裝": "上下身套裝", "休閒時尚套裝": "上下身套裝",
        "睡衣": "睡衣套裝", "性感睡衣": "睡衣套裝", "睡袍／罩衫": "睡袍",
        "居家長洋裝": "居家服", "衣服": options[0],
    }
    normalized = aliases.get(raw, raw)
    if normalized in options:
        return normalized
    if main_category == "洋裝":
        if any(k in raw for k in ("禮服", "晚宴", "舞台")): return "禮服"
        if any(k in raw for k in ("短", "迷你")): return "短洋裝"
        if any(k in raw for k in ("長", "及踝", "拖地")): return "長洋裝"
        return "洋裝"
    if main_category == "連身褲":
        if any(k in raw.lower() for k in ("短", "romper", "playsuit")): return "短連身褲"
        if any(k in raw.lower() for k in ("長", "及踝", "寬褲", "jumpsuit")): return "長連身褲"
        return "連身褲"
    if main_category == "套裝":
        if "運動" in raw: return "運動套裝"
        if "居家" in raw: return "居家套裝"
        if "圍裙" in raw: return "圍裙套裝"
        if "褲裙" in raw: return "褲裙套裝"
        if "裙" in raw: return "裙裝套裝"
        if "褲" in raw: return "褲裝套裝"
        return "上下身套裝"
    if main_category == "下身":
        if "褲裙" in raw: return "褲裙"
        if "短裙" in raw: return "短裙"
        if "長裙" in raw: return "長裙"
        if "裙" in raw: return "半身裙"
        if "短褲" in raw: return "短褲"
        if "褲" in raw: return "褲子"
    return options[0]


def wardrobe_tags_from_text(*parts, limit=8):
    blob = " ".join(str(p or "") for p in parts)
    tokens = [x for x in re.split(r"[\s,，、/／「」()（）]+", blob) if x]
    result = []
    for token in tokens:
        token = _clean(token)
        if token and token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result


def today_outfit_reset_if_needed(state_data):
    today = _app()._today_str_tpe()
    if state_data.get("current_outfit_date") != today:
        state_data["current_outfit_date"] = today
        state_data["current_outfit"] = None
    return state_data


def get_current_outfit_state():
    app = _app()
    state_data = today_outfit_reset_if_needed(app.load_state())
    app.save_state(state_data)
    return state_data.get("current_outfit")


def set_current_outfit_state(outfit_payload):
    app = _app()
    state_data = today_outfit_reset_if_needed(app.load_state())
    state_data["current_outfit"] = outfit_payload
    state_data["current_outfit_date"] = app._today_str_tpe()
    app.save_state(state_data)


def clear_current_outfit_state():
    app = _app()
    state_data = app.load_state()
    state_data["current_outfit"] = None
    state_data["current_outfit_date"] = app._today_str_tpe()
    app.save_state(state_data)


def get_pending_wardrobe_state():
    return _app().load_state().get("photo_pending_wardrobe")


def set_pending_wardrobe_state(item):
    app = _app()
    state_data = app.load_state()
    state_data["photo_pending_wardrobe"] = item
    app.save_state(state_data)


def clear_pending_wardrobe_state():
    app = _app()
    state_data = app.load_state()
    state_data["photo_pending_wardrobe"] = None
    app.save_state(state_data)


def find_wardrobe_item(item_id):
    wanted = str(item_id or "").strip().upper()
    for item in load_wardrobe():
        if str(item.get("id") or "").strip().upper() == wanted:
            return item
    return None


def refresh_pending_wardrobe_from_current_db(pending_item):
    if not isinstance(pending_item, dict):
        return pending_item
    wid = str(pending_item.get("id") or "").strip().upper()
    if not wid:
        return pending_item
    current = find_wardrobe_item(wid)
    return current if isinstance(current, dict) else pending_item


def sync_pending_wardrobe_if_same_item(updated_item):
    if not isinstance(updated_item, dict):
        return
    wid = str(updated_item.get("id") or "").strip().upper()
    if not wid:
        return
    app = _app()
    state_data = app.load_state()
    pending = state_data.get("photo_pending_wardrobe")
    if isinstance(pending, dict) and str(pending.get("id") or "").strip().upper() == wid:
        state_data["photo_pending_wardrobe"] = updated_item
        app.save_state(state_data)


def pending_wardrobe_has_usable_reference(item):
    if not isinstance(item, dict):
        return False
    ref_path = str(item.get("reference_image_path") or "").strip()
    ref_url = str(item.get("local_url") or item.get("reference_item_url") or "").strip()
    return bool((ref_path and os.path.exists(ref_path)) or ref_url.startswith("http"))


def wardrobe_reference_for_generation(item):
    if not isinstance(item, dict):
        return None, None
    ref_path = str(item.get("reference_image_path") or "").strip()
    ref_url = str(item.get("local_url") or item.get("reference_item_url") or "").strip()
    if ref_path and os.path.exists(ref_path):
        return ref_path, ref_url or None
    if ref_url.startswith("http"):
        return ref_url, ref_url
    return None, ref_url or None


def extract_current_outfit_reference(outfit_state):
    app = _app()
    if not isinstance(outfit_state, dict):
        return None
    wardrobe_id = str(outfit_state.get("wardrobe_id") or "").strip().upper() or None
    if wardrobe_id:
        latest = find_wardrobe_item(wardrobe_id)
        ref_path, ref_url = wardrobe_reference_for_generation(latest) if latest else (None, None)
        if ref_path or ref_url:
            return {"reference_item_path": ref_path, "reference_item_url": ref_url, "wardrobe_id": wardrobe_id}
    def normalize_candidate(value):
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("http"):
            if "/gallery/" in raw:
                local = app._gallery_url_to_local_path(raw)
                return local if local and os.path.exists(local) else ""
            return raw
        return raw if os.path.exists(raw) else ""
    ref_path = normalize_candidate(outfit_state.get("reference_item_path"))
    ref_url = str(outfit_state.get("reference_item_url") or "").strip()
    if not ref_path:
        fallback = normalize_candidate(ref_url)
        if fallback:
            ref_path = fallback
        elif ref_url.startswith("http") and "/gallery/" in ref_url:
            ref_url = ""
    if not ref_path and not ref_url and not wardrobe_id:
        return None
    return {"reference_item_path": ref_path or None, "reference_item_url": ref_url or None, "wardrobe_id": wardrobe_id}


def photo_requests_outfit_change(raw_scene_text):
    text = str(raw_scene_text or "")
    patterns = [r"換成", r"換上", r"改穿", r"穿上", r"改成.*(?:衣|裙|褲|外套|睡衣|泳裝|內衣)", r"今天穿", r"想讓她穿", r"套用衣櫃", r"穿這件", r"穿那件"]
    return any(re.search(pattern, text) for pattern in patterns)


def extract_wardrobe_ids_from_text(text_value):
    return [m.group(0).upper() for m in re.finditer(r"\bW\d{3,4}\b", str(text_value or ""), flags=re.IGNORECASE)]


def find_first_wardrobe_item_in_text(text_value):
    for wid in extract_wardrobe_ids_from_text(text_value):
        item = find_wardrobe_item(wid)
        if item:
            return item
    return None


def next_wardrobe_id(items):
    max_id = 0
    for item in items or []:
        m = re.match(r"^W(\d+)$", str(item.get("id") or "").strip().upper())
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"W{max_id + 1:03d}"


def wardrobe_matches(item, query):
    q = str(query or "").strip().lower()
    if not q:
        return True
    blob = " ".join([
        str(item.get("id") or ""), str(item.get("name") or ""),
        str(item.get("main_category") or ""), str(item.get("sub_category") or ""),
        " ".join(str(x) for x in (item.get("tags") or [])), str(item.get("style_summary") or ""),
    ]).lower()
    return all(part in blob for part in q.split())


def parse_wardrobe_command(command_text):
    raw_text = str(command_text or "").strip()
    raw = re.sub(r"^/衣櫃(?:\s+|$)", "", raw_text, flags=re.IGNORECASE).strip()
    if not raw:
        return "browse", ""
    first, _, rest = raw.partition(" ")
    action, rest = first.strip(), rest.strip()
    if action in {"新增", "去人", "看", "穿", "刪除", "問小俠", "修正", "換圖", "換圖去人", "換圖去人化", "健檢", "修復圖片", "圖片修復"}:
        return action, rest
    return "search", raw


def wardrobe_category_counts(items):
    counts = {k: 0 for k in _app().WARDROBE_MAIN_CATEGORIES}
    for item in items:
        cat = str(item.get("main_category", "") or "")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def build_wardrobe_item_payload(meta, reference_path, reference_url):
    app = _app()
    item_id = next_wardrobe_id(load_wardrobe())
    return {
        "id": item_id,
        "name": meta.get("name") or item_id,
        "main_category": meta.get("main_category") or "配件",
        "sub_category": meta.get("sub_category") or "未分類",
        "tags": meta.get("tags") or [],
        "style_summary": meta.get("style_summary") or meta.get("name") or item_id,
        "reference_image_path": reference_path,
        "local_url": reference_url,
        "image_storage": "zeabur_local" if str(reference_path or "").startswith(app.OUTPUT_DIR) else "remote_or_external",
        "created_at": datetime.now(app.TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_new_wardrobe_item(item):
    items = load_wardrobe()
    items.insert(0, item)
    save_wardrobe(items)
    return item


def wardrobe_filtered_items(query=""):
    return [item for item in load_wardrobe() if wardrobe_matches(item, query)]


def wardrobe_total_pages(total, page_size=None):
    size = page_size or _app().WARDROBE_PAGE_SIZE
    return max(1, math.ceil(max(0, int(total)) / size))


_PATCH_MAP = {
    "load_wardrobe": load_wardrobe,
    "save_wardrobe": save_wardrobe,
    "load_wardrobe_usage_log": load_wardrobe_usage_log,
    "save_wardrobe_usage_log": save_wardrobe_usage_log,
    "_normalize_wardrobe_main_category": normalize_main_category,
    "_normalize_wardrobe_sub_category": normalize_sub_category,
    "_wardrobe_tags_from_text": wardrobe_tags_from_text,
    "_today_outfit_reset_if_needed": today_outfit_reset_if_needed,
    "_get_current_outfit_state": get_current_outfit_state,
    "_set_current_outfit_state": set_current_outfit_state,
    "_clear_current_outfit_state": clear_current_outfit_state,
    "_get_pending_wardrobe_state": get_pending_wardrobe_state,
    "_set_pending_wardrobe_state": set_pending_wardrobe_state,
    "_clear_pending_wardrobe_state": clear_pending_wardrobe_state,
    "_find_wardrobe_item": find_wardrobe_item,
    "_refresh_pending_wardrobe_from_current_db": refresh_pending_wardrobe_from_current_db,
    "_sync_pending_wardrobe_if_same_item": sync_pending_wardrobe_if_same_item,
    "_pending_wardrobe_has_usable_reference": pending_wardrobe_has_usable_reference,
    "_wardrobe_reference_for_generation": wardrobe_reference_for_generation,
    "_extract_current_outfit_reference": extract_current_outfit_reference,
    "_photo_requests_outfit_change": photo_requests_outfit_change,
    "_extract_wardrobe_ids_from_text": extract_wardrobe_ids_from_text,
    "_find_first_wardrobe_item_in_text": find_first_wardrobe_item_in_text,
    "_next_wardrobe_id": next_wardrobe_id,
    "_wardrobe_matches": wardrobe_matches,
    "_parse_wardrobe_command": parse_wardrobe_command,
    "_wardrobe_category_counts": wardrobe_category_counts,
    "_build_wardrobe_item_payload": build_wardrobe_item_payload,
    "_save_new_wardrobe_item": save_new_wardrobe_item,
    "_wardrobe_filtered_items": wardrobe_filtered_items,
    "_wardrobe_total_pages": wardrobe_total_pages,
}


def install_wardrobe_core(app):
    global _APP
    required = [
        "WARDROBE_DATA_PATH", "WARDROBE_USAGE_LOG_PATH", "WARDROBE_MAIN_CATEGORIES",
        "WARDROBE_CATEGORY_ALIASES", "WARDROBE_SUBCATEGORY_OPTIONS", "WARDROBE_PAGE_SIZE",
        "OUTPUT_DIR", "TZ_TPE", "load_state", "save_state", "_today_str_tpe",
        "_clean_text_compact", "_gallery_url_to_local_path",
    ]
    missing = [name for name in required if not hasattr(app, name)]
    if missing:
        raise RuntimeError(f"wardrobe core missing dependencies: {missing}")
    _APP = app
    for name, fn in _PATCH_MAP.items():
        setattr(app, name, fn)
    return {
        "version": EXTRACTION_VERSION,
        "module": "xiaoxia.wardrobe.core",
        "functions_moved": len(_PATCH_MAP),
        "exports": sorted(_PATCH_MAP),
    }
