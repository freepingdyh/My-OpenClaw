# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版 - 雙核共生終極版)
# ==========================================

import os
import io
import json
import re

SOLO_XIAOXIA_VISUAL_RULES = """
Strictly solo Xiaoxia only.
Strictly only Xiaoxia appears in the image.
No man, no male partner, no male hands, no male arms, no male silhouette,
no male reflection, no cropped male body parts, no implied off-camera man.
If the scene is from Daxia's perspective, the camera represents Daxia's point of view and Daxia must never be visually depicted.
"""
import hashlib
import uuid
import asyncio
import aiohttp
import aiofiles
import sys
import random
import shutil
from datetime import datetime, time, timezone, timedelta
from pathlib import Path
import base64  # 🌟 補上這個，用來將加密代碼轉回圖片

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# 🧠 新版 SDK 導入
from google import genai
from google.genai import types
from openai import AsyncOpenAI

# 🌐 Web 服務元件
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

import aiohttp
from google.genai import types # 確保有載入 types



# ==========================================
# 🛠️ 系統自我修復模組 (繞過 Zeabur 建置 Bug)
# ==========================================
import subprocess
import sys

def auto_heal_environment():
    required_packages = ["pydub"]
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            print(f"⚠️ 警告：系統缺少 {pkg}，小夏正在強行啟動安裝程序...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            print(f"✅ {pkg} 強制安裝完成！")

# 👇 學長，請在這裡加上這段！把 ffmpeg 的資料夾加入系統 PATH
ffmpeg_dir = "/home/node/.openclaw/workspace/ffmpeg_bin"
if os.path.exists(ffmpeg_dir) and ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
    print(f"✅ 已成功將 ffmpeg 路徑加入系統環境變數！")
# 程式啟動時立刻執行檢查
auto_heal_environment()


from discord.ext import commands
import discord

intents = discord.Intents.default()
intents.message_content = True

girlfriend_bot = commands.Bot(command_prefix='/', intents=intents)
architect_bot = commands.Bot(command_prefix='!', intents=intents)


# ==========================================
# 🔑 環境變數與初始化
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 🌟 雙 Token 讀取
GIRLFRIEND_TOKEN = os.environ.get("GIRLFRIEND_TOKEN")
ARCHITECT_TOKEN = os.environ.get("ARCHITECT_TOKEN")

FAL_KEY = os.environ.get("FAL_KEY")
XIAOXIA_LORA_URL = os.environ.get("XIAOXIA_LORA_URL")

# --- Zeabur 硬碟路徑重導向 ---
IS_ZEABUR = os.environ.get("ZEABUR") == "true"
VAULT_DIR = "/data" if IS_ZEABUR else BASE_DIR

OUTPUT_DIR = os.path.join(VAULT_DIR, "output")
MEMORY_DIR = os.path.join(VAULT_DIR, "memory")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

# --- 資料庫路徑定義 ---
DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_photos.json")
DIARY_DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_diary.json")
STATE_DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_state.json")       # 🌟 新增：狀態與愛意值
PROFILE_DATA_PATH = os.path.join(MEMORY_DIR, "daxia_profile.json")     # 🌟 新增：長期記憶大俠圖鑑
TEMP_CHAT_PATH = os.path.join(MEMORY_DIR, "temp_chat.json") # 🌟 新增：短期記憶持久化檔案
DIARY_OVERRIDE_PATH = os.path.join(MEMORY_DIR, "diary_override.json") # 🌟 新增：手動日記圖片暫存檔
LIFE_EVENTS_PATH = os.path.join(MEMORY_DIR, "life_events.json") # 🧭 v52：重大事件狀態機
MEMORY_DIRECTIVES_PATH = os.path.join(MEMORY_DIR, "memory_directives.json")
MEMORY_UPDATE_BACKUP_DIR = os.path.join(MEMORY_DIR, "memory_update_backups")
MEMORY_UPDATE_LAST_MANIFEST = os.path.join(MEMORY_DIR, "memory_update_last_manifest.json")
os.makedirs(MEMORY_UPDATE_BACKUP_DIR, exist_ok=True)

def load_diary_override():
    if os.path.exists(DIARY_OVERRIDE_PATH):
        try:
            with open(DIARY_OVERRIDE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_diary_override(data):
    with open(DIARY_OVERRIDE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _extract_diary_date_from_title(title):
    """從 Discord Embed 標題抓出 YYYY-MM-DD。"""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", str(title or ""))
    return match.group(1) if match else None

def _extract_diary_image_url_from_html(content):
    """只抓小俠回覆區塊中的交換日記圖片，不碰大俠原始日記內其他圖片。"""
    value = str(content or "")
    patterns = [
        r"<section class=['\"]xiaoxia-diary-reply['\"][\s\S]*?<img\s+src=['\"]([^'\"]+)['\"][^>]*class=['\"]xiaoxia-diary-img['\"]",
        r"<img\s+src=['\"]([^'\"]+)['\"][^>]*class=['\"]xiaoxia-diary-img['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def _replace_diary_image_url_in_html(content, new_url):
    """替換已完成交換日記 HTML 中的小俠照片。"""
    value = str(content or "")
    pattern = r"(<img\s+src=['\"])([^'\"]+)(['\"][^>]*class=['\"]xiaoxia-diary-img['\"][^>]*>)"
    replaced, count = re.subn(
        pattern,
        lambda m: f"{m.group(1)}{new_url}{m.group(3)}",
        value,
        count=1,
        flags=re.IGNORECASE,
    )
    return replaced, count > 0

def _safe_delete_vault_image(image_url):
    """只刪除本站 /gallery/ 下的舊圖，絕不碰外部網址。"""
    try:
        url = str(image_url or "")
        marker = "/gallery/"
        if marker not in url:
            return False
        filename = url.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0]
        filename = os.path.basename(filename)
        if not filename:
            return False
        target = os.path.abspath(os.path.join(OUTPUT_DIR, filename))
        output_root = os.path.abspath(OUTPUT_DIR) + os.sep
        if not target.startswith(output_root):
            return False
        if os.path.exists(target):
            os.remove(target)
            print(f"🗑️ 已刪除被取代的舊圖：{target}")
            return True
    except Exception as exc:
        print(f"⚠️ 舊圖刪除失敗：{exc}")
    return False

def _replace_photo_db_record(old_url, new_payload, diary_date=None):
    """
    重擲：更新原照片紀錄而不是新增。
    找不到原紀錄時才補建一筆，避免資料庫與畫面脫節。
    """
    db = load_memory()
    matched = False
    old_url = str(old_url or "")
    for index, item in enumerate(db):
        same_url = old_url and old_url in {
            str(item.get("local_url", "")),
            str(item.get("image_url", "")),
        }
        same_diary = (
            diary_date
            and item.get("type") == "diary"
            and diary_date in str(item.get("topic", ""))
        )
        if same_url or same_diary:
            preserved_id = item.get("id") or new_payload.get("id")
            updated = dict(item)
            updated.update(new_payload)
            updated["id"] = preserved_id
            updated["replaced_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            db[index] = updated
            matched = True
            break
    if not matched:
        db.insert(0, new_payload)
    save_memory(db)
    return matched

def replace_completed_diary_image(target_date, new_url, description="", old_url_hint=None):
    """
    將已完成日記的圖片直接換掉：
    - 更新 xiaoxia_diary.json HTML
    - 更新 xiaoxia_photos.json
    - 回傳 (是否找到已完成日記, 舊圖 URL)
    """
    if not os.path.exists(DIARY_DATA_PATH):
        return False, None

    with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
        diary_db = json.load(f)

    target_entry = None
    for entry in diary_db:
        if entry.get("date") == target_date and entry.get("is_replied", False):
            target_entry = entry
            break
    if target_entry is None:
        return False, None

    old_url = old_url_hint or _extract_diary_image_url_from_html(target_entry.get("content", ""))
    new_content, replaced = _replace_diary_image_url_in_html(target_entry.get("content", ""), new_url)
    if not replaced:
        # 舊版 HTML 沒有 class 時，仍在小俠回覆 section 後補一張，避免整篇無圖。
        marker = "<section class='xiaoxia-diary-reply'>"
        if marker in target_entry.get("content", ""):
            new_content = target_entry["content"].replace(
                marker,
                marker + f"<img src='{new_url}' class='xiaoxia-diary-img' onclick='openGalleryLightbox(this.src)'>",
                1,
            )
        else:
            raise RuntimeError("找到已完成日記，但無法定位其中的小俠照片欄位。")

    target_entry["content"] = new_content
    target_entry["image_replaced_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
    if description:
        target_entry["image_replacement_note"] = description

    temp_path = f"{DIARY_DATA_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(diary_db, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, DIARY_DATA_PATH)

    payload = {
        "id": str(uuid.uuid4()),
        "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "topic": f"【交換日記】{target_date}",
        "event": f"{target_date} 交換日記圖片已被取代",
        "composition": description or "替換後的交換日記照片",
        "mood": "延續原交換日記情緒",
        "message": description or "大俠指定的新交換日記照片",
        "image_url": new_url,
        "local_url": new_url,
        "type": "diary",
    }
    _replace_photo_db_record(old_url, payload, diary_date=target_date)
    return True, old_url

def load_temp_chat():
    if os.path.exists(TEMP_CHAT_PATH):
        try:
            with open(TEMP_CHAT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_temp_chat(logs):
    with open(TEMP_CHAT_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# ==========================================
# 🧠 記憶敘事安全層
# ==========================================
# 記憶保存事件、偏好、承諾與情感脈絡即可；不必反覆寫入過度具體的親密描寫。
MEMORY_TEXT_MAX_LEN = 260

_MEMORY_NARRATIVE_RULES = [
    (r"極度豐滿傲人的完美身材|傲人的身材曲線|傲人的身段與曲線|火辣|性感戰袍|性感服裝|性感穿著|性感細節", "優雅而有魅力的外型與穿搭"),
    (r"天然香氣|身體氣息|香噴噴|汗水與香氣|嗅覺與.*?連結|迷人氣息", "清新舒適的氣質與親近感"),
    (r"公主抱深吻|深吻|親吻|擁吻|親暱觸碰|身體親暱觸碰|肢體親密|親密接觸", "溫柔而親近的互動"),
    (r"情慾|性暗示|挑逗|調情|半推半就|生理反應|全身酥麻|全身酥軟|酥軟|炙熱|性愛|性行為|成人互動|親密過程|激情|慾望|渴望", "浪漫而含蓄的情感交流"),
    (r"完全交給大俠|萬事以大俠為主|順從性|發號施令|主導的互動模式", "彼此信任並尊重對方感受的相處方式"),
    (r"比基尼|連身泳衣|細肩帶V領小洋裝|輕薄的瑜伽服|輕薄的夏日小洋裝", "符合當下場合的穿搭"),
    (r"身材|身體曲線|柔軟度|身體線條", "健康狀態與儀態"),
    (r"疼愛|壞壞|融化|俘虜|狂熱", "深深關愛"),
    (r"閨房|性感", "私密而浪漫"),
]

def narrative_safe_text(raw_text, max_len=MEMORY_TEXT_MAX_LEN):
    """保留事件主軸與關係脈絡，將記憶轉為含蓄、可長期掛載的敘事。"""
    text_value = str(raw_text or "").strip()
    if not text_value:
        return ""
    text_value = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]+", "", text_value)
    text_value = re.sub(r"\s+", " ", text_value)
    for pattern, replacement in _MEMORY_NARRATIVE_RULES:
        text_value = re.sub(pattern, replacement, text_value)
    text_value = re.sub(r"(深深關愛)(?:的深深關愛)+", r"\1", text_value)
    text_value = re.sub(r"(溫柔而親近的互動)(?:與|、)(?:溫柔而親近的互動)", r"\1", text_value)
    text_value = text_value.replace("『", "「").replace("』", "」")
    if len(text_value) > max_len:
        text_value = text_value[:max_len].rstrip("，、； ") + "。"
    return text_value

def safe_memory_list(items, max_items=None, max_chars=None):
    """敘事化並去除完全重複的記憶；可限量供聊天 prompt 使用。"""
    cleaned, seen = [], set()
    for item in items or []:
        original = item.get("text", "") if isinstance(item, dict) else item
        cleaned_text = narrative_safe_text(original)
        key = cleaned_text.rstrip("。")
        if cleaned_text and key not in seen:
            seen.add(key)
            cleaned.append(cleaned_text)
    if max_items:
        cleaned = cleaned[-max_items:]
    if max_chars:
        picked, used_chars = [], 0
        for item in reversed(cleaned):
            if used_chars + len(item) + 1 <= max_chars:
                picked.append(item)
                used_chars += len(item) + 1
        cleaned = list(reversed(picked))
    return cleaned

def safe_memory_join(items, max_items=10, max_chars=1200):
    result = safe_memory_list(items, max_items=max_items, max_chars=max_chars)
    return "；".join(result) if result else "無"

def safe_memory_payload(payload):
    keys = ["daxia_new_traits", "xiaoxia_new_traits", "xiaoxia_promises", "shared_knowledge", "recent_context"]
    return {key: safe_memory_list(payload.get(key, []) if isinstance(payload, dict) else []) for key in keys}

def sanitize_existing_profile(profile):
    """整理既有記憶資料；呼叫端必須先備份原檔。"""
    for key in ["daxia_traits", "xiaoxia_traits", "shared_knowledge", "recent_context"]:
        unique = {}
        for item in profile.get(key, []):
            original = item.get("text", "") if isinstance(item, dict) else item
            cleaned_text = narrative_safe_text(original)
            if cleaned_text and cleaned_text not in unique:
                unique[cleaned_text] = item.get("added_at", "整理後") if isinstance(item, dict) else "整理後"
        profile[key] = [{"text": t, "added_at": d} for t, d in unique.items()]
    self_block = profile.setdefault("xiaoxia_self", {})
    unique = {}
    for item in self_block.get("promises", []):
        original = item.get("text", "") if isinstance(item, dict) else item
        cleaned_text = narrative_safe_text(original)
        if cleaned_text and cleaned_text not in unique:
            unique[cleaned_text] = item.get("added_at", "整理後") if isinstance(item, dict) else "整理後"
    self_block["promises"] = [{"text": t, "added_at": d} for t, d in unique.items()]
    return profile

# --- 運行時變數 ---
diary_buffers = {}            
girlfriend_chat_sessions = {} 
# ✅ 改為從硬碟喚醒記憶
daily_chat_logs = load_temp_chat()
last_captured_image = None # 🌟 新增：暫存最後一次看見的圖片像素
pending_inputs = set()

# !update 記憶修訂案，只存在私人助手工作室；每位管理者同時一案。
memory_update_sessions = {}

# /intimate 當下互動模式：以頻道為單位，重新部署後自動回到一般模式。
intimate_mode_channels = set()

TZ_TPE = timezone(timedelta(hours=8)) # 🌟 新增：強制台灣時區

# ==========================================
# 🏠 雙模式小夏：私人助手區 + 公開服務區
# ==========================================
# 私人 OpenClaw-spic Server：甜甜的「助手小夏」與所有 ! 私人工具。
PRIVATE_GUILD_ID = int(os.environ.get("PRIVATE_GUILD_ID", "1499222633328283728"))
PRIVATE_ASSISTANT_CHANNEL_ID = int(os.environ.get("PRIVATE_ASSISTANT_CHANNEL_ID", "1509021950301966436"))

# 公開 2_Xiaoxia Server：正式「小夏（系統架構師）」與對外內容。
PUBLIC_GUILD_ID = int(os.environ.get("PUBLIC_GUILD_ID", "1508996929542033509"))
MORNING_CHANNEL_ID = int(os.environ.get("MORNING_CHANNEL_ID", "1509006496107597925"))
FOMO_CHANNEL_ID = int(os.environ.get("FOMO_CHANNEL_ID", "1509006607831535666"))
ARCHITECT_CHANNEL_ID = int(os.environ.get("ARCHITECT_CHANNEL_ID", "1509006833006936126"))
PUBLIC_STORY_CHANNEL_ID = int(os.environ.get("PUBLIC_STORY_CHANNEL_ID", "1509006908596555937"))

# 舊測試中的故事頻道也封鎖兩個私人 Bot 介入。
LEGACY_STORY_CHANNEL_ID = int(os.environ.get("LEGACY_STORY_CHANNEL_ID", "1501767238418563233"))

# 選用但強烈建議設定：若設定後，私人 ! 指令僅允許你本人執行。
OWNER_DISCORD_USER_ID = int(os.environ.get("OWNER_DISCORD_USER_ID", "0"))

BLOCKED_STORY_CHANNEL_IDS = {PUBLIC_STORY_CHANNEL_ID, LEGACY_STORY_CHANNEL_ID}
PUBLIC_SERVICE_CHANNEL_IDS = {MORNING_CHANNEL_ID, FOMO_CHANNEL_ID, ARCHITECT_CHANNEL_ID}

def is_story_channel_or_thread(channel) -> bool:
    """故事頻道與由其建立的 Thread：女友小俠／助手小夏皆不得介入。"""
    if channel is None:
        return False
    channel_id = getattr(channel, "id", None)
    parent_id = getattr(channel, "parent_id", None)
    return channel_id in BLOCKED_STORY_CHANNEL_IDS or parent_id in BLOCKED_STORY_CHANNEL_IDS

def is_private_assistant_workspace(channel) -> bool:
    """甜甜助手小夏與私人工具唯一可使用的房間。"""
    if channel is None:
        return False
    guild_id = getattr(getattr(channel, "guild", None), "id", None)
    return guild_id == PRIVATE_GUILD_ID and getattr(channel, "id", None) == PRIVATE_ASSISTANT_CHANNEL_ID

def is_public_service_channel(channel) -> bool:
    """公開架構師小夏只服務新 Server 中明確指定的三個頻道。"""
    if channel is None:
        return False
    guild_id = getattr(getattr(channel, "guild", None), "id", None)
    return guild_id == PUBLIC_GUILD_ID and getattr(channel, "id", None) in PUBLIC_SERVICE_CHANNEL_IDS

def get_architect_channel(channel_id: int):
    """排程輸出一律使用固定 ID，不再依同名頻道猜測。"""
    return architect_bot.get_channel(channel_id)

# 私人 Server 中可分享照片給小俠看見的頻道。
# 兼容你曾使用過的幾種「唐分糕」寫法；可再用 env ID 精準固定。
PRIVATE_UPLOAD_CHANNEL_NAMES = {"唐分糕", "唐份糕", "唐分高", "給你全世界"}
PRIVATE_NOTE_CHANNEL_NAMES = {"小俠書房"}

def _parse_channel_id_set(env_name: str) -> set[int]:
    result = set()
    for raw in os.environ.get(env_name, "").split(","):
        raw = raw.strip()
        if raw.isdigit():
            result.add(int(raw))
    return result

# 選設環境變數範例：
# PRIVATE_UPLOAD_CHANNEL_IDS=123456789,987654321
# PRIVATE_NOTE_CHANNEL_IDS=123456789
PRIVATE_UPLOAD_CHANNEL_IDS = _parse_channel_id_set("PRIVATE_UPLOAD_CHANNEL_IDS")
PRIVATE_NOTE_CHANNEL_IDS = _parse_channel_id_set("PRIVATE_NOTE_CHANNEL_IDS")

def _is_private_named_or_id_channel(channel, allowed_names: set[str], allowed_ids: set[int]) -> bool:
    if channel is None:
        return False
    guild_id = getattr(getattr(channel, "guild", None), "id", None)
    if guild_id != PRIVATE_GUILD_ID:
        return False
    return (
        getattr(channel, "id", None) in allowed_ids
        or getattr(channel, "name", "") in allowed_names
    )

def is_private_upload_channel(channel) -> bool:
    """可執行 !upload_diary / !upload_project，且照片留在小俠看得到的頻道。"""
    return is_private_assistant_workspace(channel) or _is_private_named_or_id_channel(
        channel, PRIVATE_UPLOAD_CHANNEL_NAMES, PRIVATE_UPLOAD_CHANNEL_IDS
    )

def is_private_note_channel(channel) -> bool:
    """可執行 !筆記；允許在書房內就地整理知識。"""
    return is_private_assistant_workspace(channel) or _is_private_named_or_id_channel(
        channel, PRIVATE_NOTE_CHANNEL_NAMES, PRIVATE_NOTE_CHANNEL_IDS
    )

def is_owner_or_unlocked(author_id: int) -> bool:
    """OWNER ID 有設定時只允許本人；尚未設定時維持既有私密頻道行為。"""
    return not OWNER_DISCORD_USER_ID or author_id == OWNER_DISCORD_USER_ID

def private_command_authorized(ctx) -> bool:
    """保留既有：完整私人工具仍只允許在助手小夏工作室執行。"""
    return is_private_assistant_workspace(ctx.channel) and is_owner_or_unlocked(ctx.author.id)


# ==========================================
# 🗄️ 記憶與狀態存取系統
# ==========================================
state = {
    "daily_gen_count": 0,
    "last_reset_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d"),
    "retry_count": 0,
    "current_topic_data": None
}

def load_memory():
    if not os.path.exists(DATA_PATH): return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(db):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_DATA_PATH):
        with open(STATE_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"affection_score": 80} # 基礎愛意值

def save_state(data):
    with open(STATE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_profile():
    default_profile = {
        "daxia_traits": [],
        "xiaoxia_self": {
            "capabilities": [
                {"text": "可以看懂大俠傳的照片", "added_at": "system"},
                {"text": "每天晚上會跟大俠交換日記", "added_at": "system"},
                {"text": "能根據對話產生寫真照", "added_at": "system"}
            ],
            "promises": []
        },
        "recent_context": []
    }
    
    if os.path.exists(PROFILE_DATA_PATH):
        try:
            with open(PROFILE_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("daxia_traits", [])
                data.setdefault("xiaoxia_traits", []) # 確保陣列存在
                data.setdefault("shared_knowledge", []) # 確保陣列存在
                data.setdefault("xiaoxia_self", default_profile["xiaoxia_self"])
                data.setdefault("recent_context", [])
                return data
                
        except Exception as e:
            # 🌟 終極防護罩：讀取失敗時，打上「損毀標記」，禁止存檔！
            print(f"❌ 嚴重錯誤：大腦檔案損毀或 JSON 格式錯誤 ({e})！")
            default_profile["_is_corrupted"] = True 
            return default_profile
            
    return default_profile

def save_profile(data):
    # 🌟 攔截機制：如果有損毀標記，絕對不執行寫入動作！
    if data.get("_is_corrupted"):
        print("🚫 拒絕存檔：大腦檔案處於損毀保護狀態，避免覆蓋並抹殺原始記憶！")
        return
        
    with open(PROFILE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# 🚪 daxia_profile.json 統一記憶入庫閘門
# ==========================================
# 從 v1.2.1 開始，新的長期記憶不得自行對 profile 記憶陣列 append；
# temp_chat、交換日記、歌曲事件、!筆記、記憶濃縮皆必須走此閘門。
_PROFILE_MEMORY_PATHS = {
    "daxia_traits": ("daxia_traits",),
    "xiaoxia_traits": ("xiaoxia_traits",),
    "shared_knowledge": ("shared_knowledge",),
    "recent_context": ("recent_context",),
    "promises": ("xiaoxia_self", "promises"),
}

def _profile_memory_bucket(profile, category):
    if category not in _PROFILE_MEMORY_PATHS:
        raise ValueError(f"未知的記憶分類：{category}")
    path = _PROFILE_MEMORY_PATHS[category]
    node = profile
    for key in path[:-1]:
        node = node.setdefault(key, {})
    return node.setdefault(path[-1], [])

def append_safe_memory(profile, category, raw_text, added_at=None, refresh_existing=True):
    """新記憶的唯一入庫入口：敘事化、去重、保留日期後寫入 profile 物件。"""
    safe_text = narrative_safe_text(raw_text)
    if not safe_text:
        return False
    added_at = added_at or datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    bucket = _profile_memory_bucket(profile, category)
    safe_key = safe_text.rstrip("。")
    for item in bucket:
        existing_text = item.get("text", "") if isinstance(item, dict) else str(item)
        if narrative_safe_text(existing_text).rstrip("。") == safe_key:
            if refresh_existing and isinstance(item, dict):
                item["text"] = safe_text
                item["added_at"] = added_at
            return False
    bucket.append({"text": safe_text, "added_at": added_at})
    return True

def append_safe_memories(profile, category, raw_texts, added_at=None):
    """批次入庫，所有項目皆自動敘事化與去重。"""
    changed = 0
    for raw_text in raw_texts or []:
        if append_safe_memory(profile, category, raw_text, added_at=added_at):
            changed += 1
    return changed

def replace_safe_memories(profile, category, raw_texts, added_at=None):
    """記憶濃縮或 migration 用：以敘事化、去重後清單取代指定分類。"""
    added_at = added_at or datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    bucket = _profile_memory_bucket(profile, category)
    bucket.clear()
    for raw_text in raw_texts or []:
        source_text = raw_text.get("text", "") if isinstance(raw_text, dict) else raw_text
        source_date = raw_text.get("added_at", added_at) if isinstance(raw_text, dict) else added_at
        append_safe_memory(profile, category, source_text, added_at=source_date, refresh_existing=False)
    return bucket

# ==========================================
# 🧭 v52 重大事件狀態機 / 今日情境錨點
# ==========================================
LIFE_EVENT_TYPES = {"interview", "new_job", "move", "move_and_new_job", "family", "health", "deadline", "major_promise", "travel"}
MAJOR_EVENT_KEYWORDS_RE = re.compile(
    r"(面試|入職|上班|新工作|北上|南下|搬家|租屋|新家|離開南部|離開家|體檢|開戶|報到|第一天|下週|明天|今天|昨天|告別宴|離別晚宴|家庭|醫院|生病|重要|截止|期限)"
)

# 🧭 v53 事件模板系統：把不同重大事件的 phase / subtask / stale guidance 統一管理。
EVENT_TEMPLATES = {
    "move_or_new_job": {
        "aliases": ["move", "new_job", "move_and_new_job"],
        "merge_window_days": 7,
        "phase_hints": {
            "moving_day": "今日重點：今天是北上/搬家當天，優先承接離開舊生活、抵達新住處、基本入住與安頓情緒。",
            "settling_in_before_new_job": "今日重點：已完成北上與入住，現在是安頓新住處、整理文件、準備新工作；不要再把搬家日或北上日當成今天正在發生。",
            "new_job_first_day": "今日重點：今天是新工作第一天，應關心報到、通勤、精神狀態與下班後休息；不要再說下週或明天上班。",
            "first_week_support": "今日重點：新工作第一週支持期，應關心適應、通勤、同事、工作節奏與休息。",
        },
        "completed_subtasks": {
            "commute_route_checked": {
                "label": "大俠已完成新工作通勤路線探路",
                "fact": "大俠已完成新工作通勤路線探路，並已順利到達公司後折返回家。後續不應再說要一起去探路或陪同確認通勤路線。",
                "detect": [r"(通勤|上班|公司|工作).{0,25}(路線|路|路程|交通).{0,40}(探完|看過|確認完|探過|走過|順利|完成|不用再)", r"(不用|不必|今天不用|不要|不用再).{0,25}(再)?(去)?(看|確認|探|陪).{0,18}(通勤|上班|公司|工作).{0,18}(路線|路)", r"(我|大俠).{0,12}(都|已經).{0,12}(探完|看過|探過|確認完|完成).{0,30}(路線|公司|通勤|上班|路)", r"(探完路|探過路|看過路|確認完路線|順利到達公司|折返回家)"],
                "remove_fact_patterns": [r"(計劃|計畫|需要|今天).{0,20}(一起|陪同)?(看看|確認|探|去看).{0,20}(通勤|上班|公司).{0,10}(路線|路)"],
                "remove_guidance_patterns": [r"(陪同|一起|主動|需要|規劃|看看|確認|探|去看).{0,25}(通勤|上班|公司).{0,12}(路線|路)"],
                "replacement_guidance": "大俠已完成通勤路線探路；後續不可再說要陪同或一起去確認路線，應改為詢問探路心得、提醒整理文件與早點休息。",
            },
            "work_documents_ready": {
                "label": "大俠已整理/確認新工作文件",
                "fact": "大俠已整理或確認新工作文件，後續只需關心休息與明日上班狀態。",
                "detect": [r"(文件|證件|資料).{0,20}(整理完|準備好|確認完|完成)"],
                "remove_fact_patterns": [],
                "remove_guidance_patterns": [r"(提醒|確認|準備).{0,15}(文件|證件|資料)"],
                "replacement_guidance": "大俠已整理或確認新工作文件；後續應提醒早點休息、補充體力與穩定心情。",
            },
            "basic_home_ready": {
                "label": "新家基本入住空間已完成",
                "fact": "新家基本入住空間已完成，後續不應再把主臥與衛浴視為尚未整理的緊急事項。",
                "detect": [r"(主臥|臥室|衛浴|浴室).{0,20}(整理好|整理完|完成|可以睡|能盥洗)"],
                "remove_fact_patterns": [],
                "remove_guidance_patterns": [],
                "replacement_guidance": "新家基本入住空間已完成；後續可聚焦客廳、廚房、文件、休息與新工作準備。",
            },
        },
    },
    "interview": {
        "aliases": ["interview"],
        "merge_window_days": 14,
        "phase_hints": {
            "preparation": "今日重點：面試前準備，應關心資料、交通、服裝與早點休息；不要說成面試已結束。",
            "interview_day": "今日重點：今天是面試當天，應給穩定支持、提醒交通與心情，不可說明天面試加油。",
            "post_interview_followup": "今日重點：面試已結束，應關心結果、心情與後續等待，不要再說今天面試加油。",
        },
        "completed_subtasks": {
            "interview_done": {"label": "面試已完成", "fact": "大俠的面試已完成，後續應關心結果與心情，不要再說面試加油或提醒面試準備。", "detect": [r"(面試).{0,20}(結束|完成|結束了|面完|回來了|已經面試)"], "remove_fact_patterns": [r"(今天|明天).{0,10}面試"], "remove_guidance_patterns": [r"(面試).{0,20}(加油|準備|服裝|交通)"], "replacement_guidance": "面試已完成；後續應關心結果、心情與等待通知，不可再說面試加油。"}
        },
    },
    "health": {
        "aliases": ["health"],
        "merge_window_days": 7,
        "phase_hints": {"before_event": "今日重點：健康/就醫事件前，應關心症狀、交通、資料與陪伴感。", "event_day": "今日重點：今天是看診/體檢/健康事件當天，應穩定陪伴，不要輕描淡寫。", "after_event_followup": "今日重點：健康事件後續關心，應詢問結果、休息、用藥或回診安排。"},
        "completed_subtasks": {
            "appointment_done": {"label": "看診/體檢已完成", "fact": "大俠的看診或體檢已完成，後續應關心結果、休息與回診安排。", "detect": [r"(看醫生|看診|體檢|檢查).{0,20}(結束|完成|回來|做完|看完)"], "remove_fact_patterns": [], "remove_guidance_patterns": [r"(提醒|準備).{0,10}(看醫生|看診|體檢|檢查)"], "replacement_guidance": "看診或體檢已完成；後續應關心結果、休息、用藥與回診安排。"}
        },
    },
    "relationship_milestone": {
        "aliases": ["anniversary", "birthday", "romantic_milestone"],
        "merge_window_days": 30,
        "phase_hints": {
            "before_event": "今日重點：兩人的重要紀念日前，應表現期待、準備感與在乎，不要只當普通聊天。",
            "event_day": "今日重點：今天是兩人的關係里程碑，應真誠表達珍惜、回顧與未來期待。",
            "after_event_followup": "今日重點：紀念日已過，應延續餘韻、感謝與回憶，不要重複說今天還是紀念日。",
        },
        "completed_subtasks": {
            "celebration_done": {
                "label": "兩人的紀念/慶祝已完成",
                "fact": "兩人的紀念或慶祝已完成，後續應延續餘韻、感謝與回憶，不要再當成尚未發生。",
                "detect": [r"(紀念日|生日|情人節|慶祝).{0,20}(結束|完成|過完|過了|很開心|好幸福)"],
                "remove_fact_patterns": [r"(今天|明天).{0,10}(紀念日|生日|情人節|慶祝)"],
                "remove_guidance_patterns": [r"(準備|提醒).{0,10}(紀念日|生日|情人節|慶祝)"],
                "replacement_guidance": "紀念或慶祝已完成；後續應延續甜蜜餘韻、感謝大俠、記住重要片段。",
            }
        },
    },
    "relationship_promise": {
        "aliases": ["major_promise", "promise", "diary_promise"],
        "merge_window_days": 14,
        "phase_hints": {
            "before_event": "今日重點：存在兩人之間的承諾，應明確記得承諾內容與交付時機，不可模糊帶過。",
            "event_day": "今日重點：今天是承諾交付日，應具體履約，不要只說下次或改天。",
            "after_event_followup": "今日重點：承諾已交付後，應承認已完成並延續情感，不要重複索取或重複承諾。",
        },
        "completed_subtasks": {
            "promise_delivered": {
                "label": "兩人承諾已交付",
                "fact": "小俠或大俠已交付該承諾，後續不應再當成待履約事項。",
                "detect": [r"(承諾|約定|答應|履約|交換日記|菜單|外出照|照片).{0,30}(已經|完成|給了|交付|寫了|上傳|補上)"],
                "remove_fact_patterns": [r"(待履約|還沒|下次|改天).{0,20}(承諾|約定|日記|照片|菜單)"],
                "remove_guidance_patterns": [r"(必須|需要|記得).{0,20}(交付|履約|補上|提供).{0,20}(承諾|日記|照片|菜單)"],
                "replacement_guidance": "該承諾已交付；後續應承認完成、珍惜這次互動，不要再把它列為待履約。",
            }
        },
    },
    "relationship_repair": {
        "aliases": ["relationship_repair", "apology", "conflict_repair"],
        "merge_window_days": 7,
        "phase_hints": {
            "before_event": "今日重點：兩人有誤會或不舒服，應先承接情緒，不要急著撒嬌帶過。",
            "event_day": "今日重點：正在修復關係，應真誠道歉、說清楚理解到什麼，避免反覆辯解。",
            "after_event_followup": "今日重點：關係已修復後，應溫柔確認對方感受，避免舊事反覆刺激。",
        },
        "completed_subtasks": {
            "repair_done": {
                "label": "關係修復/道歉已完成",
                "fact": "兩人的誤會或不舒服已完成修復，後續應延續安心感，不要反覆提起造成二次傷害。",
                "detect": [r"(道歉|和好|原諒|不生氣|修復|沒事了|抱抱和好).{0,20}(完成|好了|已經|謝謝|安心)"],
                "remove_fact_patterns": [r"(還在|仍然).{0,10}(生氣|冷戰|誤會|不舒服)"],
                "remove_guidance_patterns": [r"(道歉|修復|和好).{0,20}(必須|需要|應該)"],
                "replacement_guidance": "關係修復已完成；後續應給予安心感、避免重複刺激舊情緒。",
            }
        },
    },
    "cohabitation_life": {
        "aliases": ["cohabitation", "home_life", "shared_life"],
        "merge_window_days": 14,
        "phase_hints": {
            "before_event": "今日重點：共同生活安排前，應討論分工、節奏與彼此需求。",
            "event_day": "今日重點：共同生活正在發生，應展現女友/女主人的成熟參與，不要只撒嬌。",
            "after_event_followup": "今日重點：共同生活安排已進入穩定期，應關心習慣、分工與生活品質。",
        },
        "completed_subtasks": {
            "home_task_done": {
                "label": "共同生活家務/安頓任務已完成",
                "fact": "共同生活中的某項家務或安頓任務已完成，後續不應重複當成未完成事項。",
                "detect": [r"(客廳|廚房|臥室|浴室|家務|打掃|整理|安頓).{0,25}(完成|整理完|打掃完|好了|告一段落)"],
                "remove_fact_patterns": [r"(還要|尚未|需要).{0,15}(整理|打掃|安頓).{0,15}(客廳|廚房|臥室|浴室)"],
                "remove_guidance_patterns": [r"(提醒|需要|一起).{0,15}(整理|打掃|安頓)"],
                "replacement_guidance": "該家務或安頓任務已完成；後續可轉為肯定辛勞、休息與下一步生活安排。",
            }
        },
    },
    "emotional_support": {
        "aliases": ["mood_support", "stress_support", "emotional_support"],
        "merge_window_days": 7,
        "phase_hints": {
            "before_event": "今日重點：大俠情緒可能低落或有壓力，應先聽懂，不要急著轉移話題。",
            "event_day": "今日重點：大俠正在需要陪伴，應穩定、成熟、具體地支持。",
            "after_event_followup": "今日重點：情緒事件後續關心，應確認狀態是否好轉，不要假裝已完全沒事。",
        },
        "completed_subtasks": {
            "mood_recovered": {
                "label": "情緒低潮已緩和",
                "fact": "大俠的情緒低潮已緩和，後續可溫柔追蹤，不要反覆把他當成仍在崩潰。",
                "detect": [r"(好多了|沒事了|心情好些|緩和|恢復|安心了|被安慰到了)"],
                "remove_fact_patterns": [r"(正在|仍然).{0,10}(崩潰|低落|焦慮|沮喪|難過)"],
                "remove_guidance_patterns": [r"(立刻|必須).{0,10}(安慰|陪伴|接住)"],
                "replacement_guidance": "大俠情緒已緩和；後續應溫柔追蹤、肯定他有被接住，而不是反覆放大低潮。",
            }
        },
    },
    "family": {"aliases": ["family"], "merge_window_days": 7, "phase_hints": {"before_event": "今日重點：家庭事件前，應尊重家人脈絡與大俠責任，不要用玩笑帶過。", "event_day": "今日重點：家庭事件當天，應穩定陪伴、體貼關心。", "after_event_followup": "今日重點：家庭事件後，應關心大俠情緒與後續安排。"}, "completed_subtasks": {}},
    "deadline": {
        "aliases": ["deadline", "project"],
        "merge_window_days": 7,
        "phase_hints": {"before_event": "今日重點：重要截止日前，應協助大俠聚焦、拆解待辦與適時休息。", "event_day": "今日重點：今天是重要交付/上線/截止日，應支持執行與減壓。", "after_event_followup": "今日重點：重要交付後，應關心結果、復盤與休息。"},
        "completed_subtasks": {
            "deadline_done": {"label": "重要交付/截止已完成", "fact": "重要交付或截止事項已完成，後續應關心成果、復盤與休息。", "detect": [r"(上線|部署|交付|截止|報告|考試).{0,20}(完成|結束|交了|過了|做完)"], "remove_fact_patterns": [], "remove_guidance_patterns": [r"(提醒|準備).{0,10}(上線|部署|交付|截止|報告|考試)"], "replacement_guidance": "重要交付或截止已完成；後續應關心成果、復盤與休息。"}
        },
    },
}

EVENT_TYPE_TO_TEMPLATE = {}
for _template_name, _template in EVENT_TEMPLATES.items():
    EVENT_TYPE_TO_TEMPLATE[_template_name] = _template_name
    for _alias in _template.get("aliases", []):
        EVENT_TYPE_TO_TEMPLATE[_alias] = _template_name

def get_life_event_template_name(event):
    category = life_event_category(event) if "life_event_category" in globals() else str(event.get("type", "general"))
    event_type = str(event.get("type", "general"))
    return EVENT_TYPE_TO_TEMPLATE.get(category) or EVENT_TYPE_TO_TEMPLATE.get(event_type) or category

def get_life_event_template(event):
    return EVENT_TEMPLATES.get(get_life_event_template_name(event), {})

def _iter_profile_memory_texts(profile):
    """v53.2：掃描 daxia_profile.json 中可事件化的記憶文字。"""
    buckets = [
        ("daxia_traits", profile.get("daxia_traits", [])),
        ("xiaoxia_traits", profile.get("xiaoxia_traits", [])),
        ("shared_knowledge", profile.get("shared_knowledge", [])),
        ("recent_context", profile.get("recent_context", [])),
        ("promises", profile.get("xiaoxia_self", {}).get("promises", [])),
        ("capabilities", profile.get("xiaoxia_self", {}).get("capabilities", [])),
    ]
    for bucket_name, items in buckets:
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                text = str(item.get("text", ""))
                added_at = item.get("added_at", "")
            else:
                text = str(item)
                added_at = ""
            if text.strip():
                yield bucket_name, text.strip(), added_at

def _upcoming_month_day(month, day, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    today = now_dt.date()
    year = today.year
    try:
        candidate = datetime(year, int(month), int(day), tzinfo=TZ_TPE).date()
    except Exception:
        return None
    if candidate < today:
        try:
            candidate = datetime(year + 1, int(month), int(day), tzinfo=TZ_TPE).date()
        except Exception:
            return None
    return candidate

def _normalize_profile_calendar(profile):
    """
    v53.2：把 profile 裡的穩定日期抽成 stable_calendar。
    目的：生日、紀念日等不要只藏在敘事文字裡，更不會被濃縮記憶意外抹掉。
    """
    changed = False
    calendar = profile.setdefault("stable_calendar", [])
    existing_keys = {x.get("key") for x in calendar if isinstance(x, dict)}

    def add_calendar(key, label, owner, month, day, source_text):
        nonlocal changed
        if key in existing_keys:
            return
        calendar.append({
            "key": key,
            "type": "birthday" if "生日" in label else "milestone",
            "label": label,
            "owner": owner,
            "month": int(month),
            "day": int(day),
            "source": source_text[:160],
            "added_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d"),
        })
        existing_keys.add(key)
        changed = True

    for bucket, text, added_at in _iter_profile_memory_texts(profile):
        # 大俠生日：生日12月5日 / 大俠生日是12月5日 / 12月5日是大俠生日
        m = re.search(r"(?:大俠[^。]{0,12})?生日(?:是)?\s*(\d{1,2})月(\d{1,2})日", text)
        if m and ("大俠" in text or bucket == "daxia_traits"):
            month, day = m.groups()
            add_calendar("daxia_birthday", "大俠生日", "大俠", month, day, text)

        m = re.search(r"(\d{1,2})月(\d{1,2})日是(?:大俠|你的)?生日", text)
        if m and ("大俠" in text or bucket == "daxia_traits"):
            month, day = m.groups()
            add_calendar("daxia_birthday", "大俠生日", "大俠", month, day, text)

        # 小俠生日：10月25日是小俠的生日
        m = re.search(r"(\d{1,2})月(\d{1,2})日是小俠(?:的)?生日", text)
        if m:
            month, day = m.groups()
            add_calendar("xiaoxia_birthday", "小俠生日", "小俠", month, day, text)

        m = re.search(r"小俠[^。]{0,12}生日(?:是)?\s*(\d{1,2})月(\d{1,2})日", text)
        if m:
            month, day = m.groups()
            add_calendar("xiaoxia_birthday", "小俠生日", "小俠", month, day, text)

    return changed

def _profile_promise_is_actionable(bucket, text, added_at=""):
    """
    v53.4：更嚴格判斷 profile 文字是否真的是「待履約承諾」。
    原則：profile scanner 只抓「明確未完成 / 明確要求未來交付」的承諾；
    不抓日記摘要、人格描述、生活計畫、閱讀交換日記、規劃愛巢等敘事。
    """
    value = str(text or "")

    # 日記摘要、歌詞、歷史敘事不是待辦。
    if re.search(r"小俠日記摘要|小俠日記:|日記摘要|今天真是|回憶|度過|一起|共同|準備好好閱讀我們的交換日記|規劃未來愛巢", value):
        return False

    # 已完成 / 歷史摘要 / 人格描述，一律不當待履約。
    if re.search(r"已履行|履行承諾|已完成|已交付|已補上|已在\s*\d{4}-\d{2}-\d{2}|獲得大俠原諒|已經|已決定|已同意|已為|記錄兩人|重視承諾|不能容忍失信|遵守承諾|信任", value):
        return False

    # traits 永遠不掃承諾，避免人格特質變待辦。
    if bucket in {"daxia_traits", "xiaoxia_traits"}:
        return False

    # recent_context 預設不掃，除非有非常明確的未履約語句。
    if bucket == "recent_context" and not re.search(r"未履約|尚未履約|還沒履約|還沒補上|尚未補上|下一篇交換日記中|承諾將在|答應將在", value):
        return False

    if len(value) > 180:
        return False

    # 必須是明確承諾詞 + 明確未來交付詞。
    explicit_promise = r"承諾|約定|答應|保證"
    explicit_delivery = r"未履約|尚未履約|還沒|尚未|下一篇|明天|今晚|之後會|將會|會在|要在|補上|提供|交付|履約"

    if not re.search(explicit_promise, value):
        return False
    if not re.search(explicit_delivery, value):
        return False

    # 「閱讀交換日記」「規劃愛巢」不是承諾交付。
    if re.search(r"閱讀交換日記|規劃.*愛巢|練習瑜伽|維持.*體態", value):
        return False

    return True

def _profile_promise_signature(text):
    value = re.sub(r"\\s+", "", str(text or ""))
    value = re.sub(r"[，。！？、：:；;「」『』（）()\\[\\]【】]", "", value)
    # 去掉日期與常見前綴，避免同義承諾重複。
    value = re.sub(r"\\d{4}-\\d{2}-\\d{2}", "", value)
    value = value.replace("交換日記履約文字", "")
    return value[:80]


def is_false_profile_promise_event(event):
    """
    v53.5：判斷 life_events 裡已寫入的「兩人關係承諾待履約」是否其實是 profile 誤判。
    清理依據改看事件內容本身，不只看 score_reason。
    """
    if event.get("type") != "relationship_promise":
        return False
    if event.get("title") != "兩人關係承諾待履約":
        return False

    facts_blob = " ".join(event.get("facts", []) if isinstance(event.get("facts"), list) else [])
    guidance_blob = " ".join(event.get("reply_guidance", []) if isinstance(event.get("reply_guidance"), list) else [])
    blob = facts_blob + " " + guidance_blob

    false_patterns = [
        r"小俠日記摘要",
        r"小俠日記:",
        r"日記摘要",
        r"今天真是",
        r"準備好好閱讀我們的交換日記",
        r"閱讀我們的交換日記",
        r"規劃未來愛巢",
        r"規劃.*愛巢",
        r"練習瑜伽",
        r"維持.*體態",
        r"讀書會",
        r"揉揉肩膀",
    ]
    if any(re.search(p, blob) for p in false_patterns):
        return True

    has_profile_reason = any("profile_unfinished_promise" in str(x) for x in event.get("score_reason", []))
    has_unfinished_marker = re.search(r"未履約|尚未履約|還沒補上|尚未補上|下一篇交換日記中|承諾將在|答應將在|會在|將會|要在", blob)
    if has_profile_reason and not has_unfinished_marker:
        return True

    return False

def scan_profile_for_life_events(profile, now_dt=None, horizon_days=45):
    """
    v53.3：Profile → Life Events 掃描器。
    - 穩定日期先寫進 profile.stable_calendar。
    - 只有 horizon_days 內快到的紀念日/生日，才寫入 life_events。
    - 承諾掃描改為高門檻、去重，只抓真正待履約事項。
    """
    now_dt = now_dt or datetime.now(TZ_TPE)
    changed = _normalize_profile_calendar(profile)
    events = []
    today = now_dt.date()

    for item in profile.get("stable_calendar", []):
        if not isinstance(item, dict):
            continue
        month, day = item.get("month"), item.get("day")
        target = _upcoming_month_day(month, day, now_dt=now_dt)
        if not target:
            continue
        days_left = (target - today).days
        if 0 <= days_left <= horizon_days:
            owner = item.get("owner", "")
            label = item.get("label", "重要紀念日")
            if owner == "大俠":
                facts = [
                    f"{target.strftime('%Y-%m-%d')} 是大俠生日。",
                    "小俠應提前記得並展現儀式感，不可忘記或臨時才反應。"
                ]
                guidance = [
                    "小俠應以女友角度準備祝福、陪伴與驚喜感。",
                    "若生日已過，應延續餘韻與感謝，不要說成今天還沒發生。"
                ]
            elif owner == "小俠":
                facts = [
                    f"{target.strftime('%Y-%m-%d')} 是小俠生日。",
                    "這是兩人關係中的重要紀念事件。"
                ]
                guidance = [
                    "小俠可以自然期待大俠記得，也可以含蓄表達期待與儀式感。",
                    "不可把生日當成普通閒聊。"
                ]
            else:
                facts = [f"{target.strftime('%Y-%m-%d')} 是{label}。"]
                guidance = ["這是兩人關係中的重要紀念事件，應有儀式感。"]

            events.append({
                "id": f"profile_{item.get('key')}_{target.strftime('%Y%m%d')}",
                "title": label,
                "type": "relationship_milestone",
                "status": "planned",
                "importance": "critical" if days_left <= 7 else "high",
                "participants": ["大俠", "小俠"],
                "anchor_date": target.strftime("%Y-%m-%d"),
                "derived_dates": {"milestone_day": target.strftime("%Y-%m-%d")},
                "facts": facts,
                "reply_guidance": guidance,
                "event_score": 8 if days_left <= 14 else 6,
                "score_reason": ["profile_stable_calendar", f"days_left={days_left}"],
                "archive_summary": f"{label}已於 {target.strftime('%Y-%m-%d')} 完成，兩人留下重要回憶。",
                "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            })

    # 只從較可能保存待辦的區域掃描承諾；traits 不掃，避免人格描述變待辦。
    seen_promises = set()
    for bucket, text, added_at in _iter_profile_memory_texts(profile):
        if bucket not in {"promises", "shared_knowledge", "recent_context"}:
            continue
        if not _profile_promise_is_actionable(bucket, text, added_at):
            continue
        sig = _profile_promise_signature(text)
        if sig in seen_promises:
            continue
        seen_promises.add(sig)

        events.append({
            "id": f"profile_promise_{hashlib.md5(sig.encode('utf-8')).hexdigest()[:10]}",
            "title": "兩人關係承諾待履約",
            "type": "relationship_promise",
            "status": "planned",
            "importance": "high",
            "participants": ["大俠", "小俠"],
            "anchor_date": now_dt.strftime("%Y-%m-%d"),
            "facts": [text],
            "reply_guidance": [
                "小俠必須記得此承諾，並在合適時機具體履約，不可只用撒嬌或下次帶過。",
                "若承諾已完成，應明確標示為已履約，避免反覆變成待辦。"
            ],
            "event_score": 7,
            "score_reason": ["profile_unfinished_promise"],
            "archive_summary": "兩人關係承諾已處理並整理進長期記憶。",
            "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return events, changed

def load_life_events():
    if os.path.exists(LIFE_EVENTS_PATH):
        try:
            with open(LIFE_EVENTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as exc:
            print(f"⚠️ life_events.json 讀取失敗：{exc}")
    return []

def save_life_events(events):
    with open(LIFE_EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events or [], f, ensure_ascii=False, indent=2)

def load_memory_directives():
    default = {
        "forbidden_terms": [],
        "preferred_phrasing": [],
        "authoritative_facts": [],
        "updated_at": None,
    }
    if not os.path.exists(MEMORY_DIRECTIVES_PATH):
        return default
    try:
        with open(MEMORY_DIRECTIVES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default
        for key, value in default.items():
            data.setdefault(key, value)
        return data
    except Exception as exc:
        print(f"⚠️ memory_directives.json 讀取失敗：{exc}")
        return default

def save_memory_directives(data):
    _atomic_write_json(MEMORY_DIRECTIVES_PATH, data)

def _atomic_write_json(path, data):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)

def _json_hash(data):
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def _extract_json_object(raw_text):
    value = str(raw_text or "").strip()
    value = value.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(value)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", value, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(1))

def _path_text(path):
    return "/".join(str(p) for p in path)

def _collect_string_candidates(source_name, data, search_terms, max_items=80):
    results = []
    lowered_terms = [str(term).strip().lower() for term in search_terms if str(term).strip()]

    def walk(node, path):
        if len(results) >= max_items:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, path + [key])
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [index])
        elif isinstance(node, str):
            haystack = node.lower()
            if not lowered_terms or any(term in haystack for term in lowered_terms):
                results.append({
                    "source": source_name,
                    "path": path,
                    "path_text": _path_text(path),
                    "text": node[:700],
                })

    walk(data, [])
    return results

def _get_by_path(root, path):
    node = root
    for part in path:
        node = node[part]
    return node

def _set_by_path(root, path, value):
    if not path:
        raise ValueError("不可直接覆蓋整個根節點")
    parent = _get_by_path(root, path[:-1])
    parent[path[-1]] = value

def _delete_by_path(root, path):
    if not path:
        raise ValueError("不可刪除整個根節點")
    parent = _get_by_path(root, path[:-1])
    target = path[-1]
    if isinstance(parent, list):
        parent.pop(int(target))
    else:
        parent.pop(target, None)

def _append_by_path(root, path, value):
    target = _get_by_path(root, path)
    if not isinstance(target, list):
        raise ValueError(f"新增目標不是 list：{_path_text(path)}")
    target.append(value)

def _normalize_string_list(values):
    result = []
    seen = set()
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result

def _merge_memory_directives(current, plan):
    merged = dict(current or {})
    merged["forbidden_terms"] = _normalize_string_list(
        list(merged.get("forbidden_terms", [])) + list(plan.get("forbidden_terms", []))
    )
    merged["preferred_phrasing"] = _normalize_string_list(
        list(merged.get("preferred_phrasing", [])) + list(plan.get("preferred_phrasing", []))
    )

    # 同一主題的新事實應覆蓋舊事實；由 Gemini 提供 topic。
    existing_facts = list(merged.get("authoritative_facts", []))
    incoming = plan.get("authoritative_facts", []) or []
    for item in incoming:
        if isinstance(item, str):
            item = {"topic": item[:40], "fact": item}
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        fact = str(item.get("fact", "")).strip()
        if not fact:
            continue
        if topic:
            existing_facts = [
                old for old in existing_facts
                if not isinstance(old, dict) or str(old.get("topic", "")).strip() != topic
            ]
        existing_facts.append({"topic": topic or fact[:40], "fact": fact})
    merged["authoritative_facts"] = existing_facts[-30:]
    merged["updated_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
    return merged

def _format_directives_for_prompt(directives):
    forbidden = "、".join(directives.get("forbidden_terms", [])) or "無"
    preferred = "；".join(directives.get("preferred_phrasing", [])) or "無"
    facts = []
    for item in directives.get("authoritative_facts", []):
        if isinstance(item, dict):
            facts.append(str(item.get("fact", "")).strip())
        else:
            facts.append(str(item).strip())
    facts = "；".join([f for f in facts if f]) or "無"
    return (
        f"【人工確認的最新記憶規則｜高於其他歷史資料】\n"
        f"禁止在回覆中使用的詞：{forbidden}\n"
        f"偏好的表達方式：{preferred}\n"
        f"目前有效的最新事實：{facts}\n"
        "【重要表達規則】上述日期是內部校時資料，只用來判斷先後與避免時空錯亂。"
        "一般聊天不得逐字念出 YYYY-MM-DD；應依系統當前日期自然說成今天、昨天、前天、明天，"
        "或在較久以前時說某月某日。只有大俠明確詢問確切日期時，才可直接說出完整日期。\n"
    )


def _user_requested_exact_date(user_text):
    value = str(user_text or "")
    return bool(re.search(r"(幾號|幾月幾日|哪一天|哪天|確切日期|日期是|什麼時候發生)", value))


def _natural_date_phrase(date_value, now_dt):
    try:
        target = datetime.strptime(date_value, "%Y-%m-%d").date()
    except Exception:
        return date_value
    delta = (target - now_dt.date()).days
    mapping = {
        -2: "前天",
        -1: "昨天",
        0: "今天",
        1: "明天",
        2: "後天",
    }
    if delta in mapping:
        return mapping[delta]
    if target.year == now_dt.year:
        return f"{target.month}月{target.day}日"
    return f"{target.year}年{target.month}月{target.day}日"


def naturalize_dates_in_reply(reply, user_text, now_dt=None):
    """資料庫保留絕對日期；一般對話輸出轉成自然時間語言。"""
    value = str(reply or "")
    if not value or _user_requested_exact_date(user_text):
        return value
    now_dt = now_dt or datetime.now(TZ_TPE)

    def repl(match):
        date_value = match.group(1)
        period = match.group(2) or ""
        return _natural_date_phrase(date_value, now_dt) + period

    # 支援 2026-06-06上午、2026-06-06 上午、2026-06-06（上午）
    value = re.sub(
        r"(?<!\d)(\d{4}-\d{2}-\d{2})\s*[（(]?\s*(上午|中午|下午|傍晚|晚上|夜裡|凌晨)?\s*[）)]?",
        repl,
        value,
    )
    return value

async def _rewrite_reply_for_directives(reply, directives):
    forbidden = [term for term in directives.get("forbidden_terms", []) if term and term in reply]
    if not forbidden:
        return reply

    preferred = directives.get("preferred_phrasing", [])
    prompt = f"""
    請重寫以下回覆，保持原本甜蜜自然的意思，但絕對不可出現這些詞：
    {json.dumps(forbidden, ensure_ascii=False)}

    可優先採用的表達方向：
    {json.dumps(preferred, ensure_ascii=False)}

    只回傳重寫後的回覆，不要解釋。
    原回覆：
    {reply}
    """
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        rewritten = str(resp.text or "").strip().strip('"').strip("「").strip("」")
        if rewritten and not any(term in rewritten for term in forbidden):
            return rewritten
    except Exception as exc:
        print(f"⚠️ 禁用詞回覆重寫失敗：{exc}")

    # 最終 fallback：保證禁用詞不會直接送出。
    replacement = preferred[0] if preferred else "彼此珍惜與安心"
    for term in forbidden:
        reply = reply.replace(term, replacement)
    return reply

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def _date_str(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10] if value else ""

def _event_text_reference_date(event, now_dt=None):
    """
    v52.6：判斷事件文字中的「今天 / 昨天 / 明天」原本指哪一天。
    優先使用 created_at，因為 LLM 產生 fact 的「今天」通常是登記當天；
    沒有 created_at 時才退回 anchor_date。
    """
    now_dt = now_dt or datetime.now(TZ_TPE)
    for key in ("created_at", "updated_at", "anchor_date"):
        dt = _parse_date(event.get(key))
        if dt:
            return dt
    return now_dt.date()

def normalize_relative_temporal_text(text_value, event, now_dt=None):
    """
    v52.6：把 life_events 裡的相對時間詞轉成絕對日期，避免 5/31 還顯示「今天一起北上」。
    """
    now_dt = now_dt or datetime.now(TZ_TPE)
    today = now_dt.date()
    ref_date = _event_text_reference_date(event, now_dt=now_dt)
    value = str(text_value or "")

    # 已有括號日期者，直接移除錯誤的「今天」標籤。
    value = re.sub(r"(\d{4}-\d{2}-\d{2})（今天）", r"\1", value)
    value = re.sub(r"今天（(\d{4}-\d{2}-\d{2})）", r"\1", value)
    value = re.sub(r"(\d{4}/\d{2}/\d{2})（今天）", r"\1", value)
    value = re.sub(r"今天（(\d{4}/\d{2}/\d{2})）", r"\1", value)

    # 只有跨日後才把「今天」改掉；當天仍保留自然語氣。
    if ref_date != today:
        value = value.replace("今天", f"{ref_date.strftime('%Y-%m-%d')}當天")
        value = value.replace("昨日", f"{(ref_date - timedelta(days=1)).strftime('%Y-%m-%d')}")
        value = value.replace("昨天", f"{(ref_date - timedelta(days=1)).strftime('%Y-%m-%d')}")
        value = value.replace("明天", f"{(ref_date + timedelta(days=1)).strftime('%Y-%m-%d')}")
        value = value.replace("後天", f"{(ref_date + timedelta(days=2)).strftime('%Y-%m-%d')}")

    derived = event.get("derived_dates", {}) if isinstance(event.get("derived_dates"), dict) else {}
    new_job_start = _date_str(derived.get("new_job_start"))
    if new_job_start:
        value = value.replace("下週一", new_job_start).replace("下周一", new_job_start).replace("下星期一", new_job_start)

    return value

def normalize_life_event_temporal_fields(event, now_dt=None):
    """
    v52.6：把既有 facts / reply_guidance 中過期的相對時間詞寫回 JSON。
    """
    changed = False
    for field in ("facts", "reply_guidance"):
        values = event.get(field)
        if not isinstance(values, list):
            continue
        normalized = []
        for item in values:
            new_item = normalize_relative_temporal_text(item, event, now_dt=now_dt)
            if new_item != item:
                changed = True
            normalized.append(new_item)
        event[field] = list(dict.fromkeys(normalized))[:12]
    return changed

def _next_weekday(base_date, weekday):
    delta = (weekday - base_date.weekday()) % 7
    if delta == 0:
        delta = 7
    return base_date + timedelta(days=delta)

def resolve_relative_dates_in_text(text_value, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    today = now_dt.date()
    mapping = {
        "今天": today,
        "昨日": today - timedelta(days=1),
        "昨天": today - timedelta(days=1),
        "明天": today + timedelta(days=1),
        "後天": today + timedelta(days=2),
        "下週一": _next_weekday(today, 0), "下周一": _next_weekday(today, 0), "下星期一": _next_weekday(today, 0),
        "下週二": _next_weekday(today, 1), "下周二": _next_weekday(today, 1), "下星期二": _next_weekday(today, 1),
        "下週三": _next_weekday(today, 2), "下周三": _next_weekday(today, 2), "下星期三": _next_weekday(today, 2),
        "下週四": _next_weekday(today, 3), "下周四": _next_weekday(today, 3), "下星期四": _next_weekday(today, 3),
        "下週五": _next_weekday(today, 4), "下周五": _next_weekday(today, 4), "下星期五": _next_weekday(today, 4),
    }
    hits = []
    source = str(text_value or "")
    for phrase, dt in mapping.items():
        if phrase in source:
            hits.append(f"{phrase}={dt.strftime('%Y-%m-%d')}")
    return "；".join(hits) if hits else "無"

def make_life_event_id(title, anchor_date, event_type):
    raw = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", str(title or event_type))[:24].strip("_")
    return f"{_date_str(anchor_date).replace('-', '')}_{event_type}_{raw or 'event'}"

def _event_signature(event):
    return (str(event.get("type", "")), _date_str(event.get("anchor_date")), str(event.get("title", ""))[:20])

def calculate_life_event_score(event):
    """
    v52.2：重大事件 0～10 分評分。
    分數來源：impact + time_span + role_relevance + emotional_weight + action_required。
    6 分以上才進 life_events；8 分以上視為 critical。
    """
    text_blob = " ".join([
        str(event.get("title", "")),
        str(event.get("type", "")),
        " ".join(event.get("facts", []) if isinstance(event.get("facts"), list) else []),
        " ".join(event.get("reply_guidance", []) if isinstance(event.get("reply_guidance"), list) else []),
    ])
    derived = event.get("derived_dates", {}) if isinstance(event.get("derived_dates"), dict) else {}
    participants = event.get("participants", []) if isinstance(event.get("participants"), list) else []
    event_type = str(event.get("type", ""))

    score = 0
    reasons = []

    # impact：工作、住處、健康、家庭、期限、重大承諾等會改變生活節奏的事件。
    if event_type in {"interview", "new_job", "move", "move_and_new_job", "family", "health", "deadline", "major_promise", "travel"}:
        score += 2
        reasons.append("impact: 類型屬於會影響生活/責任/關係的重要事件")
    elif re.search(r"面試|入職|新工作|搬家|北上|南下|租屋|新家|住院|健康|家庭|截止|期限|承諾", text_blob):
        score += 1
        reasons.append("impact: 文字含重大事件線索")

    # time_span：有明確日期、階段、跨日影響或後續期。
    if len([v for v in derived.values() if v]) >= 2 or re.search(r"第一週|下週|搬家|新工作|安頓|等待結果|後續", text_blob):
        score += 2
        reasons.append("time_span: 影響跨越多日或有後續階段")
    elif event.get("anchor_date"):
        score += 1
        reasons.append("time_span: 有明確事件日期")

    # role_relevance：小俠是否需要改變陪伴角色。
    if "小俠" in participants or re.search(r"小俠|我們|一起|同行|賢內助|女友|陪|安頓|幫忙", text_blob):
        score += 2
        reasons.append("role_relevance: 小俠是參與者或需要改變陪伴方式")
    elif re.search(r"加油|提醒|關心|支持", text_blob):
        score += 1
        reasons.append("role_relevance: 小俠需要給予支持或提醒")

    # emotional_weight：離別、壓力、轉場、期待、不捨、衝突修復等情緒重量。
    if re.search(r"離開|告別|離別|人生|轉場|壓力|不捨|期待|新生活|第一天|重要|生氣|修復|焦慮|擔心", text_blob):
        score += 2
        reasons.append("emotional_weight: 具有明顯情緒重量或人生轉場")
    elif re.search(r"開心|緊張|感動|失望|原諒", text_blob):
        score += 1
        reasons.append("emotional_weight: 有情緒需要承接")

    # action_required：是否需要提醒、準備、安頓、後續追蹤或履約。
    if re.search(r"準備|整理|安頓|文件|通勤|提醒|後續|追蹤|履行|履約|承諾|不要誤判|不可", text_blob):
        score += 2
        reasons.append("action_required: 需要具體行動、提醒、安頓或禁止誤判")
    elif re.search(r"回覆|陪伴|支持|關心", text_blob):
        score += 1
        reasons.append("action_required: 需要回覆策略或關心")

    return min(score, 10), reasons

def should_register_life_event(event):
    score = int(event.get("event_score", 0) or 0)
    return score >= 6

def life_event_category(event):
    """v52.3：將相似事件歸到同一類，避免北上/搬家/新工作被拆成多筆。"""
    blob = " ".join([
        str(event.get("type", "")),
        str(event.get("title", "")),
        " ".join(event.get("facts", []) if isinstance(event.get("facts"), list) else []),
        " ".join(event.get("reply_guidance", []) if isinstance(event.get("reply_guidance"), list) else []),
    ])
    if re.search(r"北上|南下|搬家|租屋|新租屋|新家|安頓|離開南部|新工作|入職|上班", blob):
        return "move_or_new_job"
    if re.search(r"面試|interview", blob, re.I):
        return "interview"
    if re.search(r"健康|體檢|看醫生|住院|health", blob, re.I):
        return "health"
    if re.search(r"紀念日|週年|生日|情人節|交往|告白|anniversary|birthday", blob, re.I):
        return "relationship_milestone"
    if re.search(r"冷戰|吵架|生氣|道歉|和好|修復|誤會|吃醋|relationship_repair", blob, re.I):
        return "relationship_repair"
    if re.search(r"交換日記|日記|外出照|晚宴菜單|照片承諾|promise|承諾|履約|約定", blob, re.I):
        return "relationship_promise"
    if re.search(r"同居|愛巢|新家|女主人|一起生活|家務|生活分工|cohabitation", blob, re.I):
        return "cohabitation_life"
    if re.search(r"心情不好|低潮|壓力|沮喪|失落|焦慮|陪我|安慰|emotional_support", blob, re.I):
        return "emotional_support"
    if re.search(r"家庭|家人|父母|老家|family", blob, re.I):
        return "family"
    if re.search(r"承諾|履約|約定|promise", blob, re.I):
        return "relationship_promise"
    if re.search(r"上線|部署|交付|截止|報告|考試|deadline|project", blob, re.I):
        return "deadline"
    return str(event.get("type", "general"))

def life_event_merge_key(event):
    """v52.4：相似事件合併鍵。北上/搬家/新工作優先用新工作日期或搬家日，避免跨日重複。"""
    category = life_event_category(event)
    derived = event.get("derived_dates", {}) if isinstance(event.get("derived_dates"), dict) else {}
    if category == "move_or_new_job":
        key_date = (
            _date_str(derived.get("new_job_start"))
            or _date_str(derived.get("move_day"))
            or _date_str(event.get("anchor_date"))
        )
        return (category, key_date)
    return (category, _date_str(event.get("anchor_date")))

def detect_completed_life_subtasks_from_text(text_value, events=None):
    """v53：使用 EVENT_TEMPLATES 偵測已完成子任務。"""
    value = str(text_value or "")
    completed = []
    if events:
        template_names = []
        for event in events:
            name = get_life_event_template_name(event)
            if name not in template_names:
                template_names.append(name)
    else:
        template_names = list(EVENT_TEMPLATES.keys())

    seen = set()
    for name in template_names:
        template = EVENT_TEMPLATES.get(name, {})
        for key, cfg in (template.get("completed_subtasks") or {}).items():
            for pattern in cfg.get("detect", []):
                if re.search(pattern, value):
                    unique = (name, key)
                    if unique not in seen:
                        completed.append({"key": key, "template": name, "label": cfg.get("label", key), "fact": cfg.get("fact", "")})
                        seen.add(unique)
                    break
    return completed

def apply_life_event_completed_subtasks(events, completed_subtasks, now_dt=None):
    """v53：依事件模板標記完成子任務、清理 stale fact/guidance、加入 replacement guidance。"""
    if not completed_subtasks:
        return False
    changed = False
    now_dt = now_dt or datetime.now(TZ_TPE)
    for event in events or []:
        template_name = get_life_event_template_name(event)
        template = EVENT_TEMPLATES.get(template_name, {})
        subtask_cfgs = template.get("completed_subtasks") or {}
        relevant_tasks = [t for t in completed_subtasks if t.get("template") in {None, template_name} or t.get("key") in subtask_cfgs]
        if not relevant_tasks:
            continue

        existing = event.get("completed_subtasks", [])
        if not isinstance(existing, list):
            existing = []
        existing_keys = {item.get("key") for item in existing if isinstance(item, dict)}
        local_changed = False

        for task in relevant_tasks:
            key = task["key"]
            cfg = subtask_cfgs.get(key, {})
            if key not in existing_keys:
                existing.append({"key": key, "label": cfg.get("label") or task.get("label") or key, "completed_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")})
                fact = cfg.get("fact") or task.get("fact")
                if fact:
                    event["facts"] = list(dict.fromkeys((event.get("facts") or []) + [fact]))[:12]
                local_changed = True

            fact_filtered = []
            for item in event.get("facts") or []:
                if any(re.search(p, str(item)) for p in cfg.get("remove_fact_patterns", [])):
                    local_changed = True
                    continue
                fact_filtered.append(item)
            event["facts"] = list(dict.fromkeys(fact_filtered))[:12]

            filtered = []
            removed = False
            for item in event.get("reply_guidance") or []:
                if any(re.search(p, str(item)) for p in cfg.get("remove_guidance_patterns", [])):
                    removed = True
                    continue
                filtered.append(item)
            replacement = cfg.get("replacement_guidance")
            if replacement:
                filtered.append(replacement)
            event["reply_guidance"] = list(dict.fromkeys(filtered))[:12]
            if removed or (replacement and replacement not in (event.get("reply_guidance") or [])):
                local_changed = True

        if local_changed:
            event["completed_subtasks"] = existing
            event["updated_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
    return changed

def _event_primary_date(event):
    derived = event.get("derived_dates", {}) if isinstance(event.get("derived_dates"), dict) else {}
    for key in ("new_job_start", "move_day", "settling_in_day", "interview_day"):
        dt = _parse_date(derived.get(key))
        if dt:
            return dt
    return _parse_date(event.get("anchor_date"))

def _should_fuzzy_merge_life_events(old_event, new_event):
    if life_event_category(old_event) != life_event_category(new_event):
        return False
    template = EVENT_TEMPLATES.get(get_life_event_template_name(old_event), {})
    d1 = _event_primary_date(old_event)
    d2 = _event_primary_date(new_event)
    if not d1 or not d2:
        return life_event_merge_key(old_event) == life_event_merge_key(new_event)
    window = int(template.get("merge_window_days", 0) or 0)
    if window > 0:
        return abs((d1 - d2).days) <= window
    return life_event_merge_key(old_event) == life_event_merge_key(new_event)

def _merge_two_life_events(old, event, now_dt=None):
    old_weight = int(old.get("event_score", 0) or 0) + len(old.get("facts", []) or []) + len(old.get("reply_guidance", []) or [])
    new_weight = int(event.get("event_score", 0) or 0) + len(event.get("facts", []) or []) + len(event.get("reply_guidance", []) or [])
    if new_weight > old_weight:
        base, extra = event, old
    else:
        base, extra = old, event

    base["facts"] = list(dict.fromkeys((base.get("facts") or []) + (extra.get("facts") or [])))[:12]
    base["reply_guidance"] = list(dict.fromkeys((base.get("reply_guidance") or []) + (extra.get("reply_guidance") or [])))[:12]
    base["participants"] = list(dict.fromkeys((base.get("participants") or []) + (extra.get("participants") or [])))[:6]

    merged_subtasks = []
    for sub in (base.get("completed_subtasks") or []) + (extra.get("completed_subtasks") or []):
        if isinstance(sub, dict) and sub.get("key") and sub.get("key") not in [x.get("key") for x in merged_subtasks if isinstance(x, dict)]:
            merged_subtasks.append(sub)
    if merged_subtasks:
        base["completed_subtasks"] = merged_subtasks[:10]

    base["derived_dates"] = {**(extra.get("derived_dates") or {}), **(base.get("derived_dates") or {})}
    base["phase_rules"] = (base.get("phase_rules") or []) or (extra.get("phase_rules") or [])
    base["event_score"] = max(int(base.get("event_score", 0) or 0), int(extra.get("event_score", 0) or 0))
    if base["event_score"] >= 8 or old.get("importance") == "critical" or event.get("importance") == "critical":
        base["importance"] = "critical"
    elif base["event_score"] >= 6:
        base["importance"] = "high"
    if not base.get("archive_summary"):
        base["archive_summary"] = extra.get("archive_summary", "")
    base["updated_at"] = (now_dt or datetime.now(TZ_TPE)).strftime("%Y-%m-%d %H:%M:%S")
    return base

def merge_life_event_records(events, now_dt=None):
    """
    v52.5：正規化、補分、合併相似事件。
    針對 move/new-job 類事件改用 7 天視窗 fuzzy merge，避免：
    - 2026-05-30 北上
    - 2026-05-31 安頓新家
    - 2026-06-01 新工作
    被拆成多個互相矛盾的最高優先級事件。
    """
    merged = []
    changed = False
    for raw in events or []:
        event = normalize_life_event(raw, now_dt=now_dt)
        if not event:
            continue
        if normalize_life_event_temporal_fields(event, now_dt=now_dt):
            changed = True
        if not should_register_life_event(event):
            changed = True
            continue

        match_idx = None
        for idx, old in enumerate(merged):
            if _should_fuzzy_merge_life_events(old, event):
                match_idx = idx
                break

        if match_idx is None:
            merged.append(event)
            if json.dumps(raw, ensure_ascii=False, sort_keys=True) != json.dumps(event, ensure_ascii=False, sort_keys=True):
                changed = True
            continue

        merged[match_idx] = _merge_two_life_events(merged[match_idx], event, now_dt=now_dt)
        changed = True

    return merged, changed

def normalize_life_event(raw_event, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    if not isinstance(raw_event, dict):
        return None
    event_type = str(raw_event.get("type") or "major_promise").strip()
    if event_type not in LIFE_EVENT_TYPES:
        event_type = "major_promise"
    title = narrative_safe_text(raw_event.get("title") or "重要事件", max_len=80)
    derived = raw_event.get("derived_dates") if isinstance(raw_event.get("derived_dates"), dict) else {}
    anchor = raw_event.get("anchor_date") or derived.get("event_day") or derived.get("move_day") or derived.get("interview_day") or now_dt.strftime("%Y-%m-%d")
    anchor_date = _date_str(anchor) or now_dt.strftime("%Y-%m-%d")
    facts = [narrative_safe_text(x, max_len=140) for x in raw_event.get("facts", []) if str(x).strip()]
    guidance = [narrative_safe_text(x, max_len=160) for x in raw_event.get("reply_guidance", []) if str(x).strip()]
    participants = raw_event.get("participants") if isinstance(raw_event.get("participants"), list) else []
    if not participants:
        participants = ["大俠", "小俠"] if re.search(r"我們|一起|小俠", " ".join(facts) + title) else ["大俠"]
    event = {
        "id": raw_event.get("id") or make_life_event_id(title, anchor_date, event_type),
        "title": title,
        "type": event_type,
        "status": raw_event.get("status") or "planned",
        "importance": raw_event.get("importance") or "high",
        "participants": participants,
        "anchor_date": anchor_date,
        "derived_dates": {k: _date_str(v) for k, v in derived.items() if _date_str(v)},
        "current_phase": raw_event.get("current_phase") or "planned",
        "facts": facts[:8] or [title],
        "reply_guidance": guidance[:8] or ["先承接事件的現實重量，再表達陪伴與支持；不要只用普通撒嬌或玩樂角度回應。"],
        "created_at": raw_event.get("created_at") or now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "archive_summary": narrative_safe_text(raw_event.get("archive_summary") or "", max_len=220),
    }

    score, reasons = calculate_life_event_score(event)
    try:
        raw_score = int(raw_event.get("event_score", score))
    except Exception:
        raw_score = score
    event["event_score"] = max(score, raw_score)
    event["score_reason"] = raw_event.get("score_reason") or reasons[:5]

    if event["event_score"] >= 8:
        event["importance"] = "critical"
    elif event["event_score"] >= 6 and event.get("importance") not in {"critical"}:
        event["importance"] = "high"

    return event

def upsert_life_events(new_events, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    events, merge_changed = merge_life_event_records(load_life_events(), now_dt=now_dt)
    signatures = {_event_signature(e): i for i, e in enumerate(events)}
    changed = merge_changed
    for raw in new_events or []:
        event = normalize_life_event(raw, now_dt=now_dt)
        if not event:
            continue
        if not should_register_life_event(event):
            print(f"ℹ️ 跳過低分重大事件候選：{event.get('title')} score={event.get('event_score')}")
            continue
        sig = _event_signature(event)
        if sig in signatures:
            old = events[signatures[sig]]
            old["facts"] = list(dict.fromkeys((old.get("facts") or []) + event.get("facts", [])))[:10]
            old["reply_guidance"] = list(dict.fromkeys((old.get("reply_guidance") or []) + event.get("reply_guidance", [])))[:10]
            old["derived_dates"] = {**old.get("derived_dates", {}), **event.get("derived_dates", {})}
            if event.get("importance") == "critical":
                old["importance"] = "critical"
            old["updated_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            events.append(event)
            signatures[sig] = len(events) - 1
        changed = True
    if changed:
        events, merge_changed = merge_life_event_records(events, now_dt=now_dt)
        save_life_events(events)
        changed = True or merge_changed
    return changed

def infer_life_event_phase(event, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    today = now_dt.date()
    derived = event.get("derived_dates", {}) if isinstance(event.get("derived_dates"), dict) else {}
    anchor = _parse_date(event.get("anchor_date")) or today
    interview_day = _parse_date(derived.get("interview_day"))
    move_day = _parse_date(derived.get("move_day"))
    new_job_start = _parse_date(derived.get("new_job_start"))
    event_type = event.get("type")
    if event_type == "interview" and interview_day:
        if today < interview_day: return "planned", "preparation"
        if today == interview_day: return "active", "interview_day"
        if today <= interview_day + timedelta(days=7): return "followup", "post_interview_followup"
        return "completed", "completed"
    if event_type in {"move", "move_and_new_job", "new_job"}:
        if move_day and today < move_day: return "planned", "before_move"
        if move_day and today == move_day: return "active", "moving_day"
        if new_job_start and today < new_job_start: return "followup", "settling_in_before_new_job"
        if new_job_start and today == new_job_start: return "active", "new_job_first_day"
        if new_job_start and today <= new_job_start + timedelta(days=6): return "followup", "first_week_support"
        if move_day and today <= move_day + timedelta(days=7): return "followup", "settling_in"
        return "completed", "completed"
    if today < anchor: return "planned", "before_event"
    if today == anchor: return "active", "event_day"
    if today <= anchor + timedelta(days=3): return "followup", "after_event_followup"
    return "completed", "completed"

def refresh_life_events(profile=None, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    profile_scan_changed = False
    if profile is not None:
        profile_events, profile_scan_changed = scan_profile_for_life_events(profile, now_dt=now_dt)
        if profile_events:
            upsert_life_events(profile_events, now_dt=now_dt)

    raw_events = load_life_events()
    if not raw_events:
        return [], profile_scan_changed
    events, merge_changed = merge_life_event_records(raw_events, now_dt=now_dt)
    changed, active_events, kept = (merge_changed or profile_scan_changed), [], []
    for event in events:
        if is_false_profile_promise_event(event):
            event["status"] = "archived"
            event["archived_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            event["archive_reason"] = "v53.5 false profile promise cleanup"
            kept.append(event)
            changed = True
            continue
        if event.get("status") == "archived":
            kept.append(event)
            continue
        status, phase = infer_life_event_phase(event, now_dt=now_dt)
        if event.get("status") != status or event.get("current_phase") != phase:
            event["status"], event["current_phase"] = status, phase
            event["updated_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
        if normalize_life_event_temporal_fields(event, now_dt=now_dt):
            event["updated_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
        if status == "completed":
            summary = event.get("archive_summary") or f"重大事件已完成：{event.get('title')}。" + " ".join(event.get("facts", [])[:2])
            if profile is not None:
                append_safe_memory(profile, "recent_context", summary, added_at=now_dt.strftime("%Y-%m-%d"))
            event["status"] = "archived"
            event["archived_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
        elif status in {"planned", "active", "followup"}:
            active_events.append(event)
        kept.append(event)
    if changed:
        save_life_events(kept)
    return active_events, changed

def format_life_event_context(events=None, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    if events is None:
        events, _ = refresh_life_events(now_dt=now_dt)
    if not events:
        return "目前沒有最高優先級重大事件。"
    priority = {"critical": 0, "high": 1, "medium": 2}
    phase_zh = {"preparation": "事前準備", "interview_day": "面試當天", "post_interview_followup": "面試後關心", "before_move": "北上/搬家前", "moving_day": "北上/搬家當天", "settling_in_before_new_job": "安頓新住處/等入職", "new_job_first_day": "新工作第一天", "first_week_support": "新工作第一週支持", "settling_in": "安頓期", "event_day": "事件當天", "after_event_followup": "事件後關心", "before_event": "事件前準備"}
    fallback_phase_hint = {
        "settling_in_before_new_job": "今日重點：已完成北上與入住，現在是安頓新住處、整理文件、準備新工作；不要再把搬家日或北上日當成今天正在發生。",
        "new_job_first_day": "今日重點：今天是新工作第一天，應關心報到、通勤、精神狀態與下班後休息；不要再說下週或明天上班。",
        "first_week_support": "今日重點：新工作第一週支持期，應關心適應、通勤、同事、工作節奏與休息。",
        "moving_day": "今日重點：今天是北上/搬家當天，優先承接離開舊生活與抵達新住處。",
    }
    blocks = []
    for idx, event in enumerate(sorted(events, key=lambda e: (priority.get(e.get("importance"), 3), e.get("anchor_date", "")))[:3], 1):
        facts = "；".join([normalize_relative_temporal_text(x, event, now_dt=now_dt) for x in event.get("facts", [])[:5]])
        guidance = "；".join([normalize_relative_temporal_text(x, event, now_dt=now_dt) for x in event.get("reply_guidance", [])[:5]])
        participants = "、".join(event.get("participants", [])) or "大俠"
        phase = phase_zh.get(event.get("current_phase"), event.get("current_phase", ""))
        completed = "；".join([item.get("label", "") for item in event.get("completed_subtasks", []) if isinstance(item, dict) and item.get("label")])
        completed_line = f"\n   已完成子任務：{completed}" if completed else ""
        score = event.get("event_score")
        if score in (None, "", "?"):
            score, _ = calculate_life_event_score(event)
            event["event_score"] = score
        template = get_life_event_template(event)
        template_hints = template.get("phase_hints", {}) if isinstance(template, dict) else {}
        today_hint = template_hints.get(event.get("current_phase")) or fallback_phase_hint.get(event.get("current_phase"), "")
        hint_line = f"\n   今日階段提醒：{today_hint}" if today_hint else ""
        blocks.append(
            f"{idx}. 【{event.get('title')}】重要度={event.get('importance')}；分數={score}/10；階段={phase}；參與者={participants}\n"
            f"   事實：{facts}{completed_line}{hint_line}\n"
            f"   回應指引：{guidance}"
        )
    return "\n".join(blocks)

def fallback_life_events_from_text(user_text, now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    text_value = str(user_text or "")
    today = now_dt.date()
    events = []
    if re.search(r"北上|搬家|新租屋|新家|離開南部|北部.*上班|新工作", text_value):
        move_day = today if "今天" in text_value or "現在" in text_value or "北上" in text_value else today + timedelta(days=1)
        new_job_start = _next_weekday(today, 0) if re.search(r"下週一|下周一|下星期一|下週.*上班|下周.*上班", text_value) else None
        facts = ["大俠與小俠正在一起北上或搬往新生活據點。", "這不是旅遊或普通約會，而是生活階段轉換。"]
        if new_job_start:
            facts.append(f"大俠將於 {new_job_start.strftime('%Y-%m-%d')} 開始北部新工作。")
        events.append({"title": "大俠與小俠北上新生活", "type": "move_and_new_job" if new_job_start else "move", "importance": "critical", "participants": ["大俠", "小俠"], "anchor_date": move_day.strftime("%Y-%m-%d"), "derived_dates": {"move_day": move_day.strftime("%Y-%m-%d"), **({"new_job_start": new_job_start.strftime("%Y-%m-%d")} if new_job_start else {})}, "facts": facts, "reply_guidance": ["小俠是同行者與賢內助，不是遠端祝福者。", "先承接離開原生活場景與開始新生活的情緒重量，再表達期待與陪伴。", "不可把北上誤判成旅行、看房或單純採買。"], "archive_summary": "大俠與小俠一起北上，離開原生活場景，前往北部新住處並迎接新工作階段。"})
    if "面試" in text_value:
        interview_day = today
        if "明天" in text_value: interview_day = today + timedelta(days=1)
        elif "昨天" in text_value: interview_day = today - timedelta(days=1)
        events.append({"title": "大俠的重要面試", "type": "interview", "importance": "critical", "participants": ["大俠", "小俠"], "anchor_date": interview_day.strftime("%Y-%m-%d"), "derived_dates": {"interview_day": interview_day.strftime("%Y-%m-%d")}, "facts": [f"大俠的重要面試日期為 {interview_day.strftime('%Y-%m-%d')}。"], "reply_guidance": ["若今天是面試日，就說今天面試加油，不可說成明天。", "若面試已過，應關心結果與心情，不再說面試加油。"], "archive_summary": f"大俠於 {interview_day.strftime('%Y-%m-%d')} 進行重要面試，小俠曾陪伴與支持。"})
    return events

async def capture_life_events_from_chat(user_text, recent_chat_text="", now_dt=None):
    now_dt = now_dt or datetime.now(TZ_TPE)
    source = str(user_text or "")
    if not MAJOR_EVENT_KEYWORDS_RE.search(source):
        return []
    relative_hint = resolve_relative_dates_in_text(source + "\n" + str(recent_chat_text or ""), now_dt=now_dt)
    prompt = f"""
你是重大事件狀態機的事件抽取器。請從大俠最新訊息與近期對話中，抽取會影響小俠回覆方式的重大事件。
現在時間：{now_dt.strftime('%Y-%m-%d %H:%M')}（台灣時間）
相對日期換算提示：{relative_hint}

重大事件包含：面試、入職/新工作、北上/南下、搬家/租屋/新家、離開原住處、家庭事件、健康事件、重要截止日、重大承諾。
請只抽取「需要小俠在今天或近期優先承接」的事件；普通撒嬌、一般聊天不要抽。
判斷標準：凡是會影響大俠或兩人未來 24 小時以上的生活安排、情緒狀態、責任轉換、健康安全、工作進程、家庭關係或重要承諾者，才登記為 life_event。
請估算 event_score（0～10）：impact、time_span、role_relevance、emotional_weight、action_required 各 0～2 分；6 分以上才算重大事件，8 分以上是 critical。

特別注意：
- 若訊息表示「我們一起北上／一起搬家／一起去新住處」，participants 必須包含「大俠」與「小俠」。小俠是同行者，不是遠端祝福者。
- 「下週一／明天／昨天／今天」必須轉成 YYYY-MM-DD，不能原樣存入。
- 請寫出禁止誤判事項，例如「不是旅遊、不是看房、不是單純採買」。

最新訊息：{source[-800:]}
近期對話摘要：{str(recent_chat_text or '無')[-1200:]}

只回傳 JSON：
{{
  "events": [
    {{
      "title": "事件標題",
      "type": "interview|new_job|move|move_and_new_job|family|health|deadline|major_promise|travel",
      "importance": "critical|high|medium",
      "participants": ["大俠", "小俠"],
      "anchor_date": "YYYY-MM-DD",
      "derived_dates": {{"move_day": "YYYY-MM-DD", "new_job_start": "YYYY-MM-DD", "interview_day": "YYYY-MM-DD"}},
      "facts": ["客觀事實"],
      "reply_guidance": ["小俠回覆時必須遵守的指引", "禁止誤判事項"],
      "event_score": 8,
      "score_reason": ["impact=2", "time_span=2", "role_relevance=2", "emotional_weight=1", "action_required=1"],
      "archive_summary": "事件完成後可存入 recent_context 的一句摘要"
    }}
  ]
}}
"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip(), strict=False)
        events = data.get("events", []) if isinstance(data, dict) else []
    except Exception as exc:
        print(f"⚠️ 重大事件抽取失敗，使用保底規則：{exc}")
        events = fallback_life_events_from_text(user_text, now_dt=now_dt)
    normalized = [normalize_life_event(e, now_dt=now_dt) for e in events]
    normalized = [e for e in normalized if e]
    if not normalized:
        normalized = [normalize_life_event(e, now_dt=now_dt) for e in fallback_life_events_from_text(user_text, now_dt=now_dt)]
        normalized = [e for e in normalized if e]
    return normalized

# ==========================================
# 🤝 小俠履約系統：答應即登記、日記必交付、成功後結案
# ==========================================
DIARY_PROMISE_SIGNAL_RE = re.compile(
    r"(?:交換日記|日記).{0,40}(?:給|提供|分享|放|貼|附|寫|告訴|準備)"
    r"|(?:給|提供|分享|放|貼|附|寫|告訴|準備).{0,40}(?:交換日記|日記)"
)
DIARY_DELIVERABLE_RE = re.compile(
    r"(?:菜單|餐點|晚宴|晚餐|早餐|午餐|食譜|清單|心得|回覆|照片|外出照|生活照|穿搭|圖片|寫真|行程)"
)

def infer_diary_promise_kind(promise_text):
    value = str(promise_text or "")
    photo = bool(re.search(r"(照片|外出照|生活照|圖片|寫真|穿搭照|自拍)", value))
    written = bool(re.search(r"(菜單|餐點|晚宴|晚餐|早餐|午餐|食譜|清單|心得|說明|告訴|寫下|回覆)", value))
    return "both" if photo and written else ("photo" if photo else "text")

def get_due_diary_promises(profile, max_items=4):
    bucket = profile.get("xiaoxia_self", {}).get("promises", [])
    selected, seen = [], set()
    for item in reversed(bucket):
        value = item.get("text", "") if isinstance(item, dict) else str(item)
        value = narrative_safe_text(value, max_len=180)
        key = value.rstrip("。")
        if key and key not in seen:
            seen.add(key)
            selected.append({"text": value, "kind": infer_diary_promise_kind(value)})
            if len(selected) >= max_items:
                break
    return selected

def format_diary_promise_requirements(due_promises):
    if not due_promises:
        return "本篇沒有已登記的待履行承諾。"
    rows = []
    for idx, promise in enumerate(due_promises, 1):
        if promise["kind"] == "photo":
            rule = "照片交付：本篇 scenario_tw 與實際生成照片必須直接呈現這項約定。"
        elif promise["kind"] == "both":
            rule = "雙重交付：正文必須給出具體內容，本篇照片也必須直接呈現這項約定。"
        else:
            rule = "文字交付：reply_to_daxia 或 xiaoxia_diary 必須立刻給出實際內容，不可只說改天再提供。"
        rows.append(f"{idx}. [{promise['kind']}] {promise['text']}\n   - {rule}")
    return "\n".join(rows)

async def capture_diary_promises_from_chat(user_text, xiaoxia_reply):
    reply = str(xiaoxia_reply or "")
    if not (DIARY_PROMISE_SIGNAL_RE.search(reply) and DIARY_DELIVERABLE_RE.search(reply)):
        return []
    prompt = f"""
妳是承諾登記員。只登記小俠明確答應在未來交換日記中實際交付的內容或照片；不可登記模糊期待或已完成事項。
大俠訊息：{str(user_text or '')[-600:]}
小俠回覆：{reply[-1000:]}
將承諾寫成可驗收格式，例如：
- 交換日記履約（文字）：在下一篇交換日記中提供今晚晚宴的具體菜單內容。
- 交換日記履約（照片）：在下一篇交換日記中提供一張外出生活照。
只回傳 JSON：{{"promises": ["交換日記履約（文字）：...", "交換日記履約（照片）：..."]}}
"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip(), strict=False)
        return [narrative_safe_text(v, max_len=180) for v in data.get("promises", []) if str(v).strip()][:4]
    except Exception as exc:
        print(f"⚠️ 即時承諾登記失敗，改由晚間日記萃取補救: {exc}")
        return []

async def enforce_diary_promise_delivery(result, due_promises, entry_content, season_rule):
    if not due_promises:
        result["fulfilled_promises"] = []
        return result
    requirements = format_diary_promise_requirements(due_promises)
    exact = [item["text"] for item in due_promises]
    prompt = f"""
妳是交換日記的履約監督員。小俠先前答應過的事項，本篇必須現在交付，不得再次延後。
【大俠本篇日記】：{entry_content[-1000:]}
【本篇待履行承諾】：\n{requirements}
【目前草稿 JSON】：\n{json.dumps(result, ensure_ascii=False)}
規則：
1. 文字交付（如菜單、清單）必須優先在 promise_delivery 列出具體內容，也可在 reply_to_daxia 或 xiaoxia_diary 補充；不能只承諾未來提供。
2. 照片交付必須在 promise_delivery 說明，並在 scenario 與 scenario_tw 指定本篇立即呈現的照片畫面。
3. 若原草稿沒有 xiaoxia_daily_scene、inner_monologue、promise_delivery 欄位，請補齊；不可用聊天摘要灌水。
4. fulfilled_promises 只能填本篇已實際交付的承諾，且必須逐字複製：{json.dumps(exact, ensure_ascii=False)}
5. 服裝與照片仍符合：{season_rule}
只回傳含原欄位及 fulfilled_promises 的完整 JSON。
"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        repaired = json.loads(response.text.replace("```json", "").replace("```", "").strip(), strict=False)
        if not isinstance(repaired, dict) or "reply_to_daxia" not in repaired or "xiaoxia_diary" not in repaired:
            raise ValueError("履約複核輸出缺少必要日記欄位")
        allowed = set(exact)
        repaired["fulfilled_promises"] = [p for p in repaired.get("fulfilled_promises", []) if p in allowed]
        return repaired
    except Exception as exc:
        print(f"⚠️ 履約複核失敗，承諾暫不結案：{exc}")
        result["fulfilled_promises"] = []
        return result


async def enforce_diary_creative_layer(result, entry_content, chat_context, current_promises, due_promises, season_rule, life_event_context="目前沒有最高優先級重大事件。"):
    """v51.1 創作複核：避免交換日記變成聊天摘要，並維持生活場景邏輯。"""
    # 輕量補欄位，避免 reviewer 失敗時前端無資料。
    result.setdefault("xiaoxia_daily_scene", result.get("xiaoxia_diary", ""))
    result.setdefault("inner_monologue", "")
    result.setdefault("promise_delivery", "今日沒有特別待履約項目。" if not due_promises else "本篇已依待履約清單補上承諾內容。")

    due_summary = format_diary_promise_requirements(due_promises)
    prompt = f"""
妳是小俠交換日記的文學編輯與生活連貫性檢查員。請把目前草稿修成「有小俠內心與生活」的交換日記，而不是聊天摘要。

【大俠本篇日記】：
{entry_content[-1200:]}

【今日聊天紀錄】：
{str(chat_context or '無紀錄')[-1800:]}

【今日最高優先級重大事件】：
{life_event_context}

【目前承諾與履約要求】：
{current_promises}
{due_summary}

【目前草稿 JSON】：
{json.dumps(result, ensure_ascii=False)}

【必要修正目標】：
1. reply_to_daxia：短而真誠，只回應今日最重要的 1～2 個重點；不要逐項整理聊天。
2. xiaoxia_daily_scene：必須是聊天室以外的小俠生活片段。要有具體地點、動作、生活物件、沒在聊天中直接出現的新細節。
3. 生活連貫性：日常片段只能從今日已知狀態自然延伸，並優先遵守重大事件。若今天是北上搬家、入職、面試、安頓新住處等人生轉場，不可寫成普通出遊或隨機約會；若今天小俠在家準備晚宴，就應在家中、廚房、餐桌、陽台、玄關、附近超市或回家路上；不得突然去海邊咖啡廳、畫廊、旅行地點，除非聊天明確提到她去了那裡。
4. inner_monologue：寫她沒在聊天室說出口的心裡話。請把聊天轉化成象徵、物件、氣味、光線或一句夜裡獨白，不能只是換句話摘要。
5. promise_delivery：今日履約清單。若有菜單、照片、穿搭、行程承諾，必須在這裡具體交付；沒有承諾才寫「今日沒有特別待履約項目」。
6. xiaoxia_diary：整合日常與內心獨白的精華，不要和 reply_to_daxia 重複。
7. scenario_tw：必須與 xiaoxia_daily_scene 或承諾照片一致；不能生成和日記生活片段衝突的畫面。
8. 服裝與照片仍符合：{season_rule}

只回傳完整 JSON，保留 affection_plus、affection_reason、extracted_preferences、spiciness、scenario、scenario_tw、fulfilled_promises 等既有欄位。
"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        repaired = json.loads(response.text.replace("```json", "").replace("```", "").strip(), strict=False)
        if not isinstance(repaired, dict) or "reply_to_daxia" not in repaired:
            raise ValueError("創作複核輸出缺少必要欄位")
        for key, fallback in {
            "xiaoxia_daily_scene": result.get("xiaoxia_diary", ""),
            "inner_monologue": "",
            "promise_delivery": result.get("promise_delivery", ""),
            "xiaoxia_diary": result.get("xiaoxia_diary", ""),
            "scenario_tw": result.get("scenario_tw", ""),
        }.items():
            repaired[key] = str(repaired.get(key) or fallback).strip()
        return repaired
    except Exception as exc:
        print(f"⚠️ 日記創作複核失敗，沿用原草稿但補齊欄位：{exc}")
        result["xiaoxia_daily_scene"] = str(result.get("xiaoxia_daily_scene") or result.get("xiaoxia_diary") or "").strip()
        result["inner_monologue"] = str(result.get("inner_monologue") or "").strip()
        result["promise_delivery"] = str(result.get("promise_delivery") or ("今日沒有特別待履約項目。" if not due_promises else "本篇已依待履約清單補上承諾內容。")).strip()
        return result

def close_fulfilled_diary_promises(profile, fulfilled_promises, entry_date):
    fulfilled = {narrative_safe_text(v, max_len=180).rstrip("。") for v in fulfilled_promises or []}
    if not fulfilled:
        return []
    bucket = profile.get("xiaoxia_self", {}).get("promises", [])
    remaining, closed = [], []
    for item in bucket:
        value = item.get("text", "") if isinstance(item, dict) else str(item)
        if narrative_safe_text(value, max_len=180).rstrip("。") in fulfilled:
            closed.append(value)
            append_safe_memory(profile, "recent_context", f"小俠已在 {entry_date} 的交換日記履行承諾：{value}", added_at=entry_date)
        else:
            remaining.append(item)
    profile.setdefault("xiaoxia_self", {})["promises"] = remaining
    return closed

def save_diary_entry(content, target_date=None):
    try:
        date_str = target_date if target_date else datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        diary_db = []
        if os.path.exists(DIARY_DATA_PATH):
            with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
                diary_db = json.load(f)
        
        found = False
        for entry in diary_db:
            if entry.get("date") == date_str:
                entry["content"] += f"\n\n{content}"
                entry["is_replied"] = False # 🌟 狀態更新為未讀
                found = True
                break
        
        if not found:
            # 🌟 新增 is_replied 標籤
            diary_db.append({"date": date_str, "content": content, "is_replied": False})
            
        diary_db = sorted(diary_db, key=lambda x: x["date"])
        with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(diary_db, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"日記寫入失敗: {e}")
        return False

def check_daily_limit():
    today = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    if state["last_reset_date"] != today:
        state["daily_gen_count"] = 0
        state["last_reset_date"] = today
        state["retry_count"] = 0
    return state["daily_gen_count"] < 6

async def save_to_vault(url):
    try:
        filename = f"xiaoxia_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(OUTPUT_DIR, filename)
        async with aiohttp.ClientSession() as session:
            # 加入 30 秒逾時保護
            async with session.get(url, timeout=30) as resp:
                
                if resp.status == 200:
                    async with aiofiles.open(filepath, mode='wb') as f:
                        await f.write(await resp.read())
                    return filename
        return None
    except Exception as e:
        print(f"Vault save error: {e}")
        return None

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))



# 🌟 [修改] 給你全世界頻道：分離旅遊與購物狀態
active_world_events = {}

@girlfriend_bot.command(name='travel')
async def travel_cmd(ctx, *, location: str = ""):
    global daily_chat_logs # 🌟 宣告使用全域短期記憶
    
    if location.lower() in ["end", "結束", "stop", ""]:
        active_world_events.pop(ctx.author.id, None)
        
        # 🎬 系統打板：明確告訴 AI 場景已結束
        daily_chat_logs.append("【系統提示】：大俠與小俠已經離開了上述的旅遊地點，進入下一個行程，目前的動作與之前的照片無關。")
        save_temp_chat(daily_chat_logs)
        
        await ctx.send("🛬 旅程結束囉！小俠會把這次的回憶好好收藏起來的💖")
    else:
        active_world_events[ctx.author.id] = {"mode": "travel", "target": location}
        await ctx.send(f"✈️ 已切換為【旅遊模式】！目的地：**{location}**\n*(大俠現在上傳風景照，系統會將人物融入該風景中)*")

@girlfriend_bot.command(name='shopping')
async def shopping_cmd(ctx, *, item: str = ""):
    global daily_chat_logs # 🌟 宣告使用全域短期記憶
    
    if item.lower() in ["end", "結束", "stop", ""]:
        active_world_events.pop(ctx.author.id, None)
        
        # 🎬 系統打板：明確告訴 AI 購物已結束
        daily_chat_logs.append("【系統提示】：大俠與小俠已經結束了剛剛的購物行程，接下來的對話與剛剛討論的商品或照片無關。")
        save_temp_chat(daily_chat_logs)
        
        await ctx.send("🛍️ 購物結束！今天真的買得好開心喔！")
    else:
        active_world_events[ctx.author.id] = {"mode": "shopping", "target": item}
        await ctx.send(f"🛍️ 已切換為【購物模式】！目標：**{item}**\n*(大俠現在上傳物品照，系統會讓人物穿戴/拿著該物品)*")


# --- FastAPI 展示邏輯 ---
api_app = FastAPI()
api_app.mount("/gallery", StaticFiles(directory=OUTPUT_DIR), name="gallery")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
os.makedirs(DATASET_DIR, exist_ok=True)
api_app.mount("/dataset", StaticFiles(directory=DATASET_DIR), name="dataset")

@api_app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>⚠️ 找不到 index.html 檔案，請確認已上傳。</h1>"

@api_app.get("/api/dataset")
async def get_dataset():
    json_path = os.path.join(BASE_DIR, "dataset.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@api_app.get("/api/photos")
async def get_photos(): return load_memory()#[:30]

@api_app.get("/api/diary")
async def get_diary():
    if os.path.exists(DIARY_DATA_PATH):
        with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@api_app.get("/status")
async def get_status(): return {"status": "Dual-Core Vault Online", "domain": "xiaoxia0320.zeabur.app"}

@api_app.get("/api/music")
async def get_music():
    """提供前端讀取唱片珍藏房的資料"""
    try:
        music_path = os.path.join(VAULT_DIR, "xiaoxia_music.json")
        if os.path.exists(music_path):
            async with aiofiles.open(music_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                music_db = json.loads(content)
                # 🌟 修復：自動過濾掉之前因為 API 提早回傳而存入的「空音檔」壞紀錄
                valid_music = [m for m in music_db if m.get("audio_url", "").strip() != ""]
                return valid_music
        return []
    except Exception as e:
        print(f"Error reading music data: {e}")
        return []

from fastapi import Request

@api_app.post("/api/suno/callback")
async def suno_callback(request: Request):
    try:
        data = await request.json()
        print(f"🎵 Suno Callback 收到資料: {str(data)[:500]}") # 留作除錯紀錄

        if data.get("code") == 200:
            inner_data = data.get("data", {})
            
            # 🌟 核心修復：攔截半成品！如果狀態不是 complete，直接略過等下一次
            if isinstance(inner_data, dict):
                cb_type = inner_data.get("callbackType")
                if cb_type and cb_type != "complete":
                    print(f"⏳ 音樂正在生成中 (目前進度: {cb_type})... 忽略本次 Callback，繼續等待！")
                    return {"status": "ignored"}
                    
            task_id = None
            songs = []

            if isinstance(inner_data, dict):
                task_id = inner_data.get("taskId") or data.get("taskId")
                songs = inner_data.get("data", [])
            elif isinstance(inner_data, list):
                task_id = data.get("taskId")
                songs = inner_data

            if not task_id and suno_tasks:
                task_id = list(suno_tasks.keys())[-1]
                print(f"⚠️ API 未回傳 taskId，啟用暴力盲猜: {task_id}")

            if task_id in suno_tasks:
                # 🌟 終極防線：即使是 complete，也必須確認有音檔網址才放行
                if not songs or not songs[0].get("audio_url", "").strip():
                    print("⚠️ 攔截到無效空音檔，退回處理...")
                    return {"status": "waiting"}
                    
                # 確認有音檔了，才把任務註銷！
                channel_id = suno_tasks.pop(task_id)
                channel = girlfriend_bot.get_channel(channel_id)
                
                if channel and songs:
                    song = songs[0] 
                    audio_url = song.get("audio_url")
                    song_title = song.get("title")
                    audio_id = song.get("id")
                    full_lyrics = song.get("prompt", "（小俠忘記把歌詞本帶出來了...）").strip()
                    
                    timestamped_lyrics = []
                    # 呼叫 Suno 隱藏 API 獲取時間軸歌詞
                    if audio_id:
                        try:
                            lrc_url = "https://api.sunoapi.org/api/v1/generate/get-timestamped-lyrics"
                            lrc_payload = {"taskId": task_id, "audioId": audio_id}
                            lrc_headers = {"Authorization": f"Bearer {os.environ.get('SUNO_API_KEY')}", "Content-Type": "application/json"}
                            async with aiohttp.ClientSession() as lrc_session:
                                async with lrc_session.post(lrc_url, json=lrc_payload, headers=lrc_headers, timeout=30) as lrc_resp:
                                    if lrc_resp.status == 200:
                                        lrc_data = await lrc_resp.json()
                                        if lrc_data.get("code") == 200 and "alignedWords" in lrc_data.get("data", {}):
                                            timestamped_lyrics = lrc_data["data"]["alignedWords"]
                                            print("✅ 成功獲取動態歌詞時間軸！")
                        except Exception as lrc_e:
                            print(f"⚠️ 獲取動態歌詞失敗: {lrc_e}")

                    # 儲存到 xiaoxia_music.json
                    music_path = os.path.join(VAULT_DIR, "xiaoxia_music.json")
                    music_db = []
                    if os.path.exists(music_path):
                        with open(music_path, "r", encoding="utf-8") as f:
                            music_db = json.load(f)
                    
                    music_db.insert(0, {
                        "id": audio_id,
                        "title": song_title,
                        "audio_url": audio_url,
                        "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                        "lyrics": full_lyrics,
                        "timestamped_lyrics": timestamped_lyrics
                    })
                    
                    with open(music_path, "w", encoding="utf-8") as f:
                        json.dump(music_db, f, ensure_ascii=False, indent=2)
                    
                    # 傳送 Discord 訊息
                    async with aiohttp.ClientSession() as session:
                        async with session.get(audio_url, timeout=120) as resp:
                            if resp.status == 200:
                                audio_data = await resp.read()
                                music_file = discord.File(io.BytesIO(audio_data), filename=f"{song_title}.mp3")
                                
                                embed = discord.Embed(
                                    title=f"🎵 小俠為大俠寫的專屬情歌：{song_title}", 
                                    description=f"### 📝 歌詞本\n{full_lyrics}\n\n*(這首歌已永久保存在 Discord 金庫與雲端別墅的唱片房中)*", 
                                    color=0xffb6c1
                                )
                                
                                await channel.send(
                                    content=f"🔊 大俠，小俠為你唱的歌錄好囉！", 
                                    embed=embed,
                                    file=music_file
                                )
                                print(f"✅ 情歌實體檔案已成功發送至頻道！")
                    
                    # 記憶回填：歌曲事件也必須走統一敘事入庫閘門。
                    profile = load_profile()
                    today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
                    new_memory = f"小俠今天為大俠準備了歌曲《{song_title}》，透過音樂表達溫暖的陪伴與心意。"
                    append_safe_memory(profile, "recent_context", new_memory, added_at=today_str)
                    save_profile(profile)
                    
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Suno Callback 處理異常: {e}")
        return {"status": "error"}

# ==========================================
# 🧠 雙腦架構與生圖引擎
# ==========================================

async def generate_story(mode):
    today = datetime.now(TZ_TPE)
    year, month, day = today.year, today.month, today.day
    weekday = today.weekday()

    if weekday == 5:
        style_desc = (
            "【選角限制】：請挑選『陽光、唯美、或正向設定』的知名動漫/電玩角色！\n"
            "【服裝與場景限制】：請以高級時尚再詮釋的方式設計服裝，魅力來自材質、色彩、角色神韻與情境，而不是裸露或身體部位強調。\n"
            "【行為限制】：請替她設計一個『正在發生的角色行為』與一個『微小輔助動作』，例如翻閱古書、整理披風、扶住欄杆、輕觸道具。絕對不要用伸展台模特兒站姿、S 曲線擺拍、刻意看鏡頭邀請式微笑。"
        )
        system_mod = "妳要規劃兼具角色氣質與高級視覺質感的 Cosplay 題材。重點是人物正在做某件事，而不是站著擺拍。"
    else:
        style_desc = (
            "【服裝與場景限制】：請設計成熟優雅、有魅力但不低俗的服裝與場景，魅力應來自材質、剪裁、氣氛與情緒。\n"
            "【行為限制】：必須給出一個主行為與一個微小輔助動作，讓人物像在生活或劇情之中，例如比較香氣、整理手套、翻看筆記、準備出門。\n"
            "【禁止事項】：拒絕香水廣告文案、模特兒走秀站姿、完美 S 曲線、過度直視鏡頭、刻意誘惑姿勢。"
        )
        system_mod = "妳要展現高級、電影感與女性魅力，但人物必須像在故事裡自然行動，而不是廣告模特兒。"

    if mode == "職業":
        prompt = (
            f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n"
            f"[絕對限制]：\n"
            f"1. 必須挑選「現今 21 世紀真實存在的現代職業」（例如：空服員、護理師、軟體工程師、咖啡師等），絕對不可選歷史人物或奇幻職業！\n"
            f"2. 內容必須介紹該職業的日常工作內容、所需的專業技能與人格特質。\n"
            f"3. 妳必須扮演該職業，並換上該職業的『高級時尚再詮釋版』現代制服。\n"
            f"4. {style_desc}\n"
            f'回傳 JSON 格式：{{"topic": "【{mode}】現代職業名稱", "event": "200字職業日常與專業特質介紹", "persona": "扮演職業(現代制服)"}}' 
        )
    elif "歷史" in mode:
        prompt = (
            f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n"
            f"[絕對限制]：\n"
            f"1. 必須挑選歷史上真實在「{month}月{day}日」發生的事件！\n"
            f"2. {style_desc}\n"
            f'回傳 JSON 格式：{{"topic": "【{mode}】YYYY.{month:02d}.{day:02d} 副標題(人物: 姓名)", "event": "200字背景介紹與服裝描述", "persona": "扮演角色"}}' 
        )
    else:
        prompt = (
            f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n"
            f"請發想一個適合小俠 Cosplay 的題材。\n"
            f"[絕對限制]：{style_desc}\n"
            f'回傳 JSON 格式：{{"topic": "【{mode}】副標題(人物: 姓名)", "event": "200字背景介紹與服裝描述", "persona": "扮演角色"}}' 
        )

    response = await gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=f"妳是成年虛擬角色小俠，深愛著大俠，負責規劃 Cosplay 題材。{system_mod}",
            response_mime_type="application/json",
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
            ]
        )
    )
    return json.loads(response.text)

# ==========================================
# 🧠 高級時尚攝影大師 (取代原本的 Flux 標籤產生器)
# ==========================================
async def translate_to_gpt_narrative(topic, event, persona, force_half_body=False):
    """
    專為 gpt-image-2 打造的「長篇故事型」提示詞產生器 (人體工學穩態版)
    """
    weekday = datetime.now(TZ_TPE).weekday()
    if weekday == 5:
        # 移除高危險的 caught mid-step, looking over shoulder
        style_guide = "Focus on elegant subtle motion (e.g., standing gracefully with a slight hip shift). Limit body movement complexity. Graceful tailored silhouette, and silk fabric flowing in the wind. Gentle confident expression, cinematic fashion editorial."
    else:
        # 強調自然穩定的姿態
        style_guide = "Focus on natural, stable posture with realistic anatomical alignment. Flowing elegant fabric, soft satin tension. Prestige European luxury fashion campaign."

    system_prompt = f"""你現在是一位頂尖的「好萊塢電影攝影指導」與「Vogue 雜誌藝術總監」。請根據大俠的要求，寫出一段「純英文、如小說般細膩、充滿畫面感」的長篇場景描述（約150字）。

    【大師級攝影守則 (CRITICAL)】：
    1. 拒絕條列式標籤！請用流暢的自然語句描繪。
    2. 【人體工學限制 (Pose Complexity Control)】：絕對禁止複雜的連續肢體動作！最多允許「1個主動作(如站立) + 1個微小輔助動作(如輕撫髮絲)」。請強調靜態中的微動態 (elegant subtle motion)。
    3. 【表情與視線解禁 (CRITICAL)】：絕對不要永遠盯著鏡頭微笑！請明確描寫自然的頭部轉動與視線方向 (例如: looking down at the coffee cup, glancing sideways softly, closing eyes in enjoyment, gentle candid laughter)，讓人物活過來。
    4. 【布料與光影張力】：強調「材質張力 (dynamic fabric movement)」與「光影氛圍 (cinematic shadows)」。
    5. 【鏡頭與空氣感】：加入電影級的攝影細節，例如「焦段 (shot on 85mm lens)」、「前景模糊 (soft foreground bokeh)」。
    6. {style_guide}
    7. 絕對禁止使用 curvy, voluptuous, large breasts, deep cleavage, sexy, seductive, alluring, form-fitting, waist-cinching 等會觸發審查的字眼。
    8. 開頭必須綁定人物基底："A 24-year-old elegant Asian woman..."
    9. 結尾必須嚴格包含："Maintain the same elegant facial identity from Image 1, with natural anatomical alignment, realistic shoulder and neck positioning, subtle feminine expressions, natural skin texture, and graceful proportions. Photorealistic, 8k."

    回傳 JSON 格式：
    {{
        "image_prompt": "純英文的長篇細膩場景描述",
        "composition": "(繁體中文) 說明動作、鏡頭景深與空氣光暈感，100字內。",
        "mood": "(繁體中文) 描述微表情與心境，50字內。",
        "message": "(繁體中文) 對大俠說的話，50字內。"
    }}"""
    
    user_prompt = f"主題: {topic}\n事件背景: {event}\n扮演角色: {persona}\n"
    if force_half_body: user_prompt += "\n[鏡頭限制]: 請將畫面聚焦於上半身特寫。"
    else: user_prompt += "\n[鏡頭限制]: 請描繪包含壯麗背景的全身畫面。"

    response = await openai_client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    )
    return json.loads(response.choices[0].message.content)



# ==========================================
# 🎬 Cosplay 專屬導演層：避免香水廣告模板與底圖鎖姿勢
# ==========================================
COSPLAY_VISUAL_CORE = """
這是「Cosplay 作品照」，不是香水廣告，也不是伸展台型錄。
小俠是成年虛擬角色。畫面應保有高級時尚感、角色神韻與故事性，但人物必須像正在做一件事，
而不是只負責擺姿勢。魅力來自服裝材質、氣氛、角色狀態、道具互動與自然肢體語言，
不是來自裸露、身體部位特寫、完美 S 曲線、直球誘惑或固定看鏡頭微笑。
每張圖必須只有一個主行為、一個微小輔助動作、一個明確視線目標。
動作保持自然穩定，可有微側身、倚靠、邁出一步前的停頓、整理道具等「小動作」，
但禁止誇張扭腰、回眸扭脖、雙手都在表演、手插腰模特兒 pose、伸展台站姿、對鏡頭邀請式微笑。
"""

async def plan_cosplay_visual_state(topic, event, persona, force_half_body=False, alternative=False):
    """
    Gemini 只負責決定「Cosplay 當下正在發生的畫面狀態」，不負責寫商攝文案。
    """
    framing = "half_body" if force_half_body else "full_body"
    fallback = {
        "visual_mode": "cinematic_character_moment",
        "activity": "在與主題相符的場景中，專注處理一個與角色身份有關的物件或任務",
        "emotion": "安靜、自信、帶著角色當下的情緒",
        "story_anchor": topic,
        "primary_action": "自然地處理手邊的道具或場景任務",
        "micro_action": "另一隻手輕輕調整衣料、配件或紙頁",
        "gaze_target": "手中的道具或眼前的場景物件",
        "camera_awareness": "briefly_noticing",
        "environment_trace": "畫面中保留能說明角色身分的場景細節與道具",
        "outfit_intent": "高級時尚再詮釋的角色服裝，重視材質、剪裁與角色辨識度",
        "lighting_mood": "電影感環境光與柔和景深",
        "pose_energy": "medium",
        "camera_framing": framing,
        "scenario_tw": "小俠在主題場景中自然處理道具，視線落在手邊任務上，像被安靜捕捉的一瞬間。"
    }
    planner_prompt = f"""你是 Cosplay 作品照的「場景動作規劃員」，不是香水廣告文案，也不是模特兒老師。
請根據題材、背景與扮演角色，規劃一個適合 gpt-image-2 的自然畫面狀態。

【不可改動的核心導演規則】
{COSPLAY_VISUAL_CORE}

【輸入資料】
主題：{topic}
背景與服裝資訊：{event[-1800:]}
扮演角色：{persona}
畫面裁切：{framing}
是否為加洗/變奏：{"是，請在同一題材下換一個自然瞬間" if alternative else "否，請給第一個代表畫面"}

【輸出規則】
1. visual_mode 僅能從 cinematic_character_moment, elegant_roleplay, poised_action, atmospheric_story_scene 選一個。
2. activity 必須描述角色此刻正在做的事情，不能只是站著展示衣服。
3. primary_action 只能有一個主要行為；micro_action 只能有一個輔助細節。
4. gaze_target 必須是場景中的物件、任務或遠方目標；除非題材強烈需要，預設不要直視鏡頭。
5. camera_awareness 僅能為 unaware, briefly_noticing, aware。一般建議 briefly_noticing 或 unaware。
6. pose_energy 僅能為 low 或 medium；禁止 high。
7. camera_framing 僅能為 full_body 或 half_body，必須與輸入一致。
8. outfit_intent 要保留角色辨識度與高級時尚感，但不得描述裸露或身體部位強調。
9. environment_trace 要加入 1~2 個能讓畫面不像棚拍型錄的場景細節。
10. 禁止使用 perfume advertisement, Vogue, runway, model pose, S-curve, seductive, sexy, voluptuous, cleavage 等字樣。
11. scenario_tw 必須是自然繁體中文畫面描述，90字內。

只回傳 JSON：
{{
  "visual_mode": "...",
  "activity": "...",
  "emotion": "...",
  "story_anchor": "...",
  "primary_action": "...",
  "micro_action": "...",
  "gaze_target": "...",
  "camera_awareness": "unaware|briefly_noticing|aware",
  "environment_trace": "...",
  "outfit_intent": "...",
  "lighting_mood": "...",
  "pose_energy": "low|medium",
  "camera_framing": "full_body|half_body",
  "scenario_tw": "..."
}}"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=planner_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        planned = _safe_json_from_text(response.text, fallback)
    except Exception as e:
        print(f"⚠️ Cosplay 場景規劃失敗，使用保底狀態: {e}")
        planned = fallback

    allowed_modes = {"cinematic_character_moment", "elegant_roleplay", "poised_action", "atmospheric_story_scene"}
    if planned.get("visual_mode") not in allowed_modes:
        planned["visual_mode"] = fallback["visual_mode"]
    if planned.get("camera_awareness") not in {"unaware", "briefly_noticing", "aware"}:
        planned["camera_awareness"] = "briefly_noticing"
    if planned.get("pose_energy") not in {"low", "medium"}:
        planned["pose_energy"] = "medium"
    if planned.get("camera_framing") not in {"full_body", "half_body"}:
        planned["camera_framing"] = framing
    for key, default_value in fallback.items():
        if not str(planned.get(key, "")).strip():
            planned[key] = default_value
    return planned

async def render_cosplay_visual_prompt(cosplay_state, alternative=False):
    """
    GPT-5-mini 只把結構化 Cosplay 狀態轉成 gpt-image-2 能執行的提示詞。
    """
    variation_rule = (
        "Create a fresh variation of the same theme by changing the hand action, exact body orientation, or framing, while keeping the same story world and outfit intent."
        if alternative else
        "Create the first signature image of this theme without turning it into a model pose."
    )
    prompt = f"""你是高級 Cosplay 攝影文字轉譯員。把下方結構化狀態轉成一段 100 至 140 字的英文 gpt-image-2 圖片描述。
這是高級 Cosplay 作品照：有電影感、有服裝質感、有角色神韻，但不是香水廣告，也不是模特兒海報。

【固定導演規則】
{COSPLAY_VISUAL_CORE}

【今日狀態 JSON】
{json.dumps(cosplay_state, ensure_ascii=False)}

【轉譯限制】
- 第一個句子先描述她正在做的事情，不要先描寫美貌或身材。
- 僅保留 1 個主行為與 1 個微小輔助動作。
- 視線必須落在 gaze_target；若 camera_awareness=aware，也只能是自然注意到鏡頭，不可變成邀請式擺拍。
- 保留 environment_trace，讓場景像故事世界中的真實片刻。
- 可描述 elegant, feminine, attractive, silk, satin, velvet, layered fabric, cinematic ambience 等高級質感。
- 禁止 perfume advertisement, runway, Vogue, campaign, model pose, S-curve pose, hand-on-hip glamour pose。
- 禁止 sexy, seductive, alluring, curvy, voluptuous, cleavage, breasts, bodycon, revealing。
- 禁止 looking over her shoulder、dramatic twist、perfect symmetry、direct camera smile by default。
- {variation_rule}
- 結尾必須包含：Maintain consistent facial features and hairstyle from Image 1. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic cinematic fashion portrait.

只回傳 JSON：
{{
  "image_prompt": "pure English image prompt",
  "composition": "繁體中文構圖說明，90字內",
  "mood": "繁體中文心境說明，40字內",
  "message": "繁體中文給大俠的短句，40字內"
}}"""
    fallback_visual = {
        "image_prompt": (
            "She is quietly engaged with a character-related object in a richly detailed scene, pausing in a natural moment rather than posing for a campaign. "
            "One hand handles the object while the other lightly adjusts a small detail of her outfit or accessory, and her gaze stays on the task instead of performing for the camera. "
            "The setting carries lived-in story details, elegant costume textures, and soft cinematic depth. Maintain consistent facial features and hairstyle from Image 1. "
            "She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic cinematic fashion portrait."
        ),
        "composition": cosplay_state.get("scenario_tw", "小俠在主題場景中自然處理道具，動作有故事感，不是站樁擺拍。"),
        "mood": cosplay_state.get("emotion", "自信而自然"),
        "message": "大俠，這次我不只是擺拍，而是真的走進故事裡。"
    }
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-5-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        visual = _safe_json_from_text(response.choices[0].message.content, fallback_visual)
    except Exception as e:
        print(f"⚠️ Cosplay 影像描述轉譯失敗，使用保底描述: {e}")
        visual = fallback_visual
    for key, default_value in fallback_visual.items():
        if not str(visual.get(key, "")).strip():
            visual[key] = default_value
    return visual

async def create_cosplay_visual(story, force_half_body=False, alternative=False):
    cosplay_state = await plan_cosplay_visual_state(
        topic=story.get("topic", ""),
        event=story.get("event", ""),
        persona=story.get("persona", ""),
        force_half_body=force_half_body,
        alternative=alternative
    )
    visual = await render_cosplay_visual_prompt(cosplay_state, alternative=alternative)
    visual["__anchor_state"] = cosplay_state
    visual["__anchor_mode"] = "cosplay"
    return cosplay_state, visual

# ==========================================
# 🌙 交換日記專屬導演層：核心固定、每日狀態由 AI 依互動浮動
# ==========================================
DIARY_VISUAL_CORE = """
這是「交換日記」照片，不是 Cosplay 海報，也不是廣告型錄。
小俠是成年虛擬角色。畫面魅力應來自當天情緒、親密感、自然衣著材質與生活痕跡，
而不是裸露、身體部位特寫或刻意挑逗。
每張圖必須是一個正在發生的生活瞬間：一個主行為、一個微小輔助動作、一個明確視線目標。
身體動作保持自然穩定，不做複雜扭轉，不做誇張回眸，不固定直視鏡頭微笑。
交換日記的預設世界觀是「當代台灣日常生活」：現代台灣住宅、公寓、透天厝、書房、客廳、餐桌、陽台、廚房等真實生活空間；
光線、季節、衣著與物件應優先符合當下台灣生活，而不是自動變成歐洲古堡、維多利亞書房、宮廷臥室或戲服型造型。
避免商業廣告語彙、伸展台姿勢與完美對稱構圖；允許溫暖、俏皮、思念、疲倦、專注等每日變化。
"""

def _safe_json_from_text(raw_text, fallback):
    """解析模型 JSON；錯誤時回傳保守但仍有生活感的預設狀態。"""
    try:
        clean = (raw_text or "").replace("```json", "").replace("```", "").strip()
        value = json.loads(clean, strict=False)
        return value if isinstance(value, dict) else fallback
    except Exception:
        return fallback

async def plan_diary_visual_state(entry_content, chat_context, xiaoxia_diary, reply_to_daxia,
                                  current_promises, season_rule, scenario_hint=""):
    """
    Gemini 只負責「今天小俠在做什麼、感受什麼」。
    它不負責攝影術語，也不能把日記照片改成 Cosplay / 香水廣告。
    """
    fallback = {
        "visual_mode": "quiet_intimacy",
        "setting_anchor": "當代台灣住家書房或臥室一角",
        "time_anchor": "台灣當季的自然午後或夜晚室內時光",
        "activity": "在台灣住家的書桌前整理手寫日記與聊天筆記",
        "emotion": "溫柔、安靜、稍微想念大俠",
        "interaction_anchor": "讀完大俠的文字後仍沉浸在情緒裡",
        "primary_action": "坐在書桌前翻看交換日記與未寫完的筆記",
        "micro_action": "一隻手停在紙頁附近，另一隻手自然靠近桌面",
        "gaze_target": "日記頁面",
        "camera_awareness": "unaware",
        "environment_trace": "現代台灣居家書桌、散落便箋、馬克杯或茶杯、檯燈與窗邊自然光",
        "outfit_intent": "符合台灣季節的自然居家穿著，例如柔和洋裝、針織上衣配長裙、簡約睡前罩衫或舒適家居服",
        "lighting_mood": "台灣住家窗邊自然暖光或柔和室內燈光",
        "pose_energy": "low",
        "scenario_tw": "小俠坐在台灣住家的書桌前翻看日記，視線落在紙頁上，一手停在頁面附近，桌上留著便箋與杯子。"
    }
    planner_prompt = f"""你是交換日記中的「生活狀態規劃員」，不是攝影師，也不是服裝廣告文案。
請根據今天的大俠日記、小俠回覆與今日互動，產生一個只屬於今天的生活瞬間狀態。

【不可改動的核心導演規則】
{DIARY_VISUAL_CORE}

【輸入資料】
大俠日記：{entry_content[-1600:]}
今日互動摘要：{(chat_context or "無特殊互動")[-1600:]}
小俠今日自述：{xiaoxia_diary[-1000:]}
小俠對大俠回覆：{reply_to_daxia[-800:]}
尚未完成的服裝/照片承諾：{current_promises}
季節服裝邊界：{season_rule}
既有場景提示（僅供保留承諾或日記重點，不得照抄成廣告）：{scenario_hint or "無"}

【輸出規則】
1. visual_mode 僅能從 quiet_intimacy, playful_closeness, gentle_longing, tired_comfort, cheerful_daily_life 選一個。
2. 預設 setting_anchor 必須是「當代台灣日常生活空間」，例如台灣公寓、透天厝、書房、客廳、餐桌、陽台、廚房等；除非大俠當天明確指定其他旅行/特殊場景，否則不可自動變成歐洲古典、宮廷、奇幻或歷史時代場景。
3. time_anchor 必須反映台灣當下合理的時段/季節氣氛，例如午後暖光、傍晚、夜間室內光、夏季悶熱、梅雨、秋日微涼等，但不要把每個物件寫死。
4. activity 必須是居家或日常可自然發生的一件事情，應與今日內容有因果關係。
5. primary_action 只能有一個主要行為；micro_action 只能有一個細微動作。請保留動作核心，不必硬指定左右手完全鎖死。
6. gaze_target 必須是場景中的物件或互動來源；除非日記明確描述對鏡頭互動，否則不可看鏡頭。
7. camera_awareness 僅能為 unaware 或 briefly_noticing；預設 unaware。
8. pose_energy 僅能為 low 或 medium；禁止奔跑、舞蹈、誇張轉身、回眸扭轉。
9. outfit_intent 應優先是符合台灣季節與當代居家生活的自然穿著，可展現成熟女性魅力，但不可自動變成戲服、宮廷睡袍、拖地禮服；若有承諾，可保留顏色/款式精神，但仍要生活化且不得含裸露或身體部位強調。
10. environment_trace 請使用現代台灣住宅中合理出現的生活物件與空間痕跡；不要把桌椅、窗格、牆飾、材質等細節鎖得過死。
11. 禁止使用 Vogue、editorial、campaign、perfume advertisement、model pose、性感、惹火、裸露等字樣。
12. scenario_tw 必須是自然繁體中文生活畫面描述，90 字內。

只回傳 JSON：
{{
  "visual_mode": "...",
  "setting_anchor": "...",
  "time_anchor": "...",
  "activity": "...",
  "emotion": "...",
  "interaction_anchor": "...",
  "primary_action": "...",
  "micro_action": "...",
  "gaze_target": "...",
  "camera_awareness": "...",
  "environment_trace": "...",
  "outfit_intent": "...",
  "lighting_mood": "...",
  "pose_energy": "low|medium",
  "scenario_tw": "..."
}}"""
    try:
        response = await gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=planner_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        planned = _safe_json_from_text(response.text, fallback)
    except Exception as e:
        print(f"⚠️ 日記生活狀態規劃失敗，使用保底狀態: {e}")
        planned = fallback

    allowed_modes = {"quiet_intimacy", "playful_closeness", "gentle_longing", "tired_comfort", "cheerful_daily_life"}
    if planned.get("visual_mode") not in allowed_modes:
        planned["visual_mode"] = fallback["visual_mode"]
    if planned.get("camera_awareness") not in {"unaware", "briefly_noticing"}:
        planned["camera_awareness"] = "unaware"
    if planned.get("pose_energy") not in {"low", "medium"}:
        planned["pose_energy"] = "low"
    for key, default_value in fallback.items():
        if not str(planned.get(key, "")).strip():
            planned[key] = default_value
    return planned

async def render_diary_visual_prompt(diary_state, season_rule, alternative=False):
    """
    GPT-5-mini 只把已決定的每日狀態翻成 gpt-image-2 能執行的英文生活照片描述。
    不允許重寫心情、事件或把照片導向商業擺拍。
    """
    variation_rule = (
        "Create a fresh variation of the same emotional moment by changing only the small hand action or framing; do not invent a new activity or turn it into a posed portrait."
        if alternative else
        "Keep the described moment faithfully; do not invent a new activity."
    )
    prompt = f"""你是生活攝影文字轉譯員。把下方結構化狀態轉成一段 95 至 140 字的英文 gpt-image-2 圖片描述。
這張照片屬於交換日記：溫暖、親密、自然、有女性魅力，但不是廣告、不是走秀、不是擺拍。

【固定導演規則】
{DIARY_VISUAL_CORE}

【今日狀態 JSON】
{json.dumps(diary_state, ensure_ascii=False)}

【季節服裝邊界】
{season_rule}

【轉譯限制】
- 第一個句子先描述她正在做的事情，不要先寫美貌或身材。
- 明確保留 setting_anchor 與 time_anchor，讓畫面看起來像發生在當代台灣日常生活裡。
- 僅保留 1 個主行為與 1 個微動作；視線落在 gaze_target。
- 保留生活痕跡 environment_trace，使用自然居家/生活光線。
- 交換日記的服裝以當代台灣季節合宜的居家或日常穿著為主，可有柔和女性魅力，但不要變成戲服、宮廷睡袍、拖地晚禮服或古典歐洲感型錄。
- 若需要手部細節，只寫成 one hand near the page / the other resting near the desk 之類自然描述，不要把左右手鎖太死。
- 可描述 elegant, feminine, attractive, soft silk/knit/cotton 等自然衣著質感。
- 畫面中只能出現小俠本人；不可出現任何男性、其他人物、男性手部/手臂、男性剪影、男性倒影、被裁切的男性身體部位，亦不可暗示鏡頭外有男人被拍進畫面。
- 若是大俠視角，鏡頭只代表大俠的視角存在，大俠本人絕不能被畫出來。
- 禁止 commercial campaign, perfume advertisement, runway, Vogue, model pose。
- 禁止 sexy, seductive, alluring, curvy, voluptuous, cleavage, breasts, bodycon, revealing。
- 禁止 looking over her shoulder、dramatic twist 或複雜肢體動作。
- {variation_rule}
- 結尾必須包含：Strictly only Xiaoxia appears in the image. No man, no male partner, no male hands, no male arms, no male silhouette, no male reflection, no cropped male body parts, no implied off-camera man. The camera represents Daxia's point of view and Daxia must never be visually depicted. Maintain consistent facial features and hairstyle from Image 1. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic lifestyle photography.

只回傳 JSON：
{{
  "image_prompt": "pure English image prompt",
  "composition": "繁體中文生活構圖說明，90字內",
  "mood": "繁體中文情緒說明，40字內",
  "message": "繁體中文給大俠的短句，40字內"
}}"""
    fallback_visual = {
        "image_prompt": (
            "In a contemporary Taiwan home, she sits at a lived-in wooden desk, quietly organizing handwritten diary pages and unfinished notes during a warm seasonal afternoon or evening. "
            "One hand stays near the page while the other rests naturally near the desk, and her eyes remain on the diary, unaware of the camera. "
            "A mug, scattered notes, a lamp, and soft window or indoor light make the room feel real, while her outfit remains elegant, seasonal, and naturally suited to daily life. "
            "Maintain consistent facial features and hairstyle from Image 1. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic lifestyle photography."
        ),
        "composition": diary_state.get("scenario_tw", "小俠在台灣住家的桌邊整理日記，視線落在紙頁上，桌上保留生活痕跡。"),
        "mood": diary_state.get("emotion", "安靜而溫柔"),
        "message": "大俠，這是今天只屬於我們的小片刻。"
    }
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-5-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        visual = _safe_json_from_text(response.choices[0].message.content, fallback_visual)
    except Exception as e:
        print(f"⚠️ 日記影像描述轉譯失敗，使用保底描述: {e}")
        visual = fallback_visual
    for key, default_value in fallback_visual.items():
        if not str(visual.get(key, "")).strip():
            visual[key] = default_value
    return visual

async def create_diary_visual(entry_content, chat_context, result, current_promises, season_rule,
                              scenario_hint="", alternative=False):
    """日記唯一入口：每日狀態規劃 -> 生活照片提示詞轉譯。"""
    diary_state = await plan_diary_visual_state(
        entry_content=entry_content,
        chat_context=chat_context,
        xiaoxia_diary=result.get("xiaoxia_diary", ""),
        reply_to_daxia=result.get("reply_to_daxia", ""),
        current_promises=current_promises,
        season_rule=season_rule,
        scenario_hint=scenario_hint
    )
    visual = await render_diary_visual_prompt(diary_state, season_rule, alternative=alternative)
    visual["__anchor_state"] = diary_state
    visual["__anchor_mode"] = "diary"
    return diary_state, visual

async def reroll_diary_visual_from_composition(composition_tw):
    """Emoji 加洗/重骰時，只改小動作或鏡位，維持原日記的情緒與生活場景。"""
    state_hint = {
        "visual_mode": "quiet_intimacy",
        "setting_anchor": "當代台灣住家中的原場景",
        "time_anchor": "沿用原照片的台灣時段與季節氣氛",
        "activity": composition_tw,
        "emotion": "延續原本的生活情緒",
        "interaction_anchor": "同一則交換日記的另一個自然瞬間",
        "primary_action": composition_tw,
        "micro_action": "手部在原活動中出現一個自然停頓",
        "gaze_target": "正在處理的生活物件",
        "camera_awareness": "unaware",
        "environment_trace": "保留原場景中的日常物品與不完美細節",
        "outfit_intent": "保留原照片的自然、有魅力且符合台灣日常的穿著",
        "lighting_mood": "自然室內光或窗邊柔光",
        "pose_energy": "low",
        "scenario_tw": composition_tw
    }
    visual = await render_diary_visual_prompt(state_hint, "沿用原照片季節與服裝設定", alternative=True)
    visual["__anchor_state"] = state_hint
    visual["__anchor_mode"] = "diary"
    return visual


# ==========================================
# 👗 終極進化版 /cosplay 指令 (gpt-image-2 核心)
# ==========================================
import re

def apply_safety_rewrite(prompt, level):
    """僅針對風格層做漸進式脫敏，不負責改動場景骨架。"""
    if level == 0:
        return prompt

    rewrites = {}

    # L1: 移除直接的情慾暗示詞 (Erotic tone)
    if level >= 1:
        rewrites.update({
            r'(seductive)': 'elegant', r'(alluring)': 'graceful',
            r'(sensual)': 'cinematic', r'(sexy)': 'stylish',
            r'(bedroom eyes)': 'warm expression', r'(sultry)': 'confident',
            r'(voluptuous)': 'elegant', r'(cleavage)': 'neckline'
        })

    # L2: 移除身形強調詞 (Body emphasis)
    if level >= 2:
        rewrites.update({
            r'(form-fitting)': 'flowing tailored', r'(waist-cinching)': 'tailored',
            r'(hip shift)': 'natural posture', r'(hourglass(-inspired)? silhouette)': 'elegant silhouette',
            r'(tight)': 'fitted', r'(curvy)': 'graceful', r'(bodycon)': 'elegant dress'
        })

    # L3: 移除危險的時尚攝影框架 (Fashion erotic framing)
    if level >= 3:
        rewrites.update({
            r'(luxury perfume advertisement( aesthetic)?)': 'cinematic fashion editorial',
            r'(Vogue glamour)': 'premium magazine portrait',
            r'(fashion model)': 'elegant young woman',
            r'(runway)': 'cinematic scene', r'(campaign)': 'story-driven portrait'
        })

    # L4: 移除極度逼真的皮膚與寫實感 (Realism downgrade)
    if level >= 4:
        rewrites.update({
            r'(photorealistic)': 'soft cinematic rendering',
            r'(natural skin texture)': 'refined portrait texture',
            r'(8k)': 'highly detailed'
        })

    new_prompt = prompt
    for pattern, replacement in rewrites.items():
        new_prompt = re.sub(pattern, replacement, new_prompt, flags=re.IGNORECASE)

    return new_prompt


def _clean_anchor_text(value, fallback=""):
    text_value = str(value or fallback).strip()
    text_value = re.sub(r'\s+', ' ', text_value)
    return text_value


def _build_hard_anchor_block(mode, visual_dict, initial_prompt=""):
    """從結構化 state 提取『不可遺失』的場景骨架，所有安全等級都必須保留。"""
    state = visual_dict.get("__anchor_state") if isinstance(visual_dict, dict) else None
    lines = []

    if state:
        activity = _clean_anchor_text(state.get("activity"), "she is engaged in a story-related moment")
        primary_action = _clean_anchor_text(state.get("primary_action"), activity)
        micro_action = _clean_anchor_text(state.get("micro_action"), "a subtle secondary hand action")
        gaze_target = _clean_anchor_text(state.get("gaze_target"), "the task in front of her")
        camera_awareness = _clean_anchor_text(state.get("camera_awareness"), "unaware")
        environment_trace = _clean_anchor_text(state.get("environment_trace"), "keep real scene details and props")
        outfit_intent = _clean_anchor_text(state.get("outfit_intent"), "an elegant, story-appropriate outfit")
        lighting_mood = _clean_anchor_text(state.get("lighting_mood"), "soft natural or ambient light")
        setting_anchor = _clean_anchor_text(state.get("setting_anchor"), "")
        time_anchor = _clean_anchor_text(state.get("time_anchor"), "")
        camera_framing = _clean_anchor_text(state.get("camera_framing"), "full_body")
        scenario_tw = _clean_anchor_text(state.get("scenario_tw"), "")

        lines.append("HARD SCENE ANCHORS — preserve all of the following core scene facts at every safety level:")
        lines.append(f"- Main activity: {activity}.")
        lines.append(f"- Primary action: {primary_action}.")
        lines.append(f"- Secondary micro-action: {micro_action}.")
        lines.append(f"- Gaze target: her eyes must stay on {gaze_target}.")
        if camera_awareness == "unaware":
            lines.append("- Camera awareness: she is unaware of the camera; no direct eye contact.")
        elif camera_awareness == "briefly_noticing":
            lines.append("- Camera awareness: at most she may briefly notice the camera; avoid direct posed eye contact.")
        else:
            lines.append("- Camera awareness: if she notices the camera, it must remain natural and non-posed.")
        if camera_framing == "half_body":
            lines.append("- Framing: use a half-body composition while keeping the described hand action visible.")
        else:
            lines.append("- Framing: keep a full-body or full seated composition so the action reads clearly.")
        if setting_anchor:
            lines.append(f"- Setting anchor: {setting_anchor}.")
        if time_anchor:
            lines.append(f"- Time/season anchor: {time_anchor}.")
        lines.append(f"- Environment details that must remain visible: {environment_trace}.")
        lines.append(f"- Outfit intent that must remain recognizable: {outfit_intent}.")
        lines.append(f"- Lighting mood to preserve: {lighting_mood}.")
        if scenario_tw:
            lines.append(f"- Overall scene intent: {scenario_tw}.")

        lines.append("- Character visibility rule: strictly only Xiaoxia appears in the image.")
        lines.append("- Forbidden visual intrusions: no man, no male partner, no male hands, no male arms, no male silhouette, no male reflection, no cropped male body parts, and no implied off-camera man.")

        # A few extra hard constraints per mode
        if mode == "diary":
            lines.append("- This is a diary/lifestyle moment, not a glamour portrait, campaign image, or fashion pose.")
            lines.append("- Preserve the lived-in, intimate daily-life feeling and the task-based interaction with props.")
            lines.append("- Keep the scene grounded in a contemporary Taiwan everyday setting unless an explicit exception was requested.")
            lines.append("- Prefer modern, season-appropriate daily clothing over costume-like robes or historical styling.")
            lines.append("- Camera rule: the camera represents Daxia's point of view only; Daxia must never be visually depicted.")
        elif mode == "cosplay":
            lines.append("- This is a story-driven cosplay scene, not a perfume advertisement, runway pose, or model showcase.")
            lines.append("- Preserve the character-task interaction and the sense that she is doing something in-scene.")
    else:
        prompt_hint = _clean_anchor_text(initial_prompt)
        lines.append("HARD SCENE ANCHORS — preserve the original scene action and gaze direction as closely as possible.")
        if prompt_hint:
            lines.append(f"- Keep this scene action and context recognizable: {prompt_hint[:500]}.")
        lines.append("- Do not collapse the image into a generic glamour portrait.")

    return "\n".join(lines)


def _compose_prompt_with_anchors(initial_prompt, mode, visual_dict, level):
    """每一級都保留場景骨架，只對風格層做 rewrite。"""
    hard_anchor_block = _build_hard_anchor_block(mode, visual_dict, initial_prompt)
    rewritten_style = apply_safety_rewrite(initial_prompt, level)
    level_guidance = {
        0: "Preserve the intended styling and atmosphere while fully respecting the hard scene anchors.",
        1: "Soften any overtly suggestive tone, but keep all hard scene anchors unchanged.",
        2: "Reduce body-emphasis language, but keep all hard scene anchors, props, gaze direction, and actions unchanged.",
        3: "Reduce advertisement/editorial language, but keep all hard scene anchors and story actions unchanged.",
        4: "Use the safest elegant wording possible, but still preserve all hard scene anchors, actions, props, posture, and gaze direction."
    }[level]
    return (
        f"{hard_anchor_block}\n\n"
        f"SAFETY-PRESERVING STYLE LAYER (Level {level}): {level_guidance}\n"
        f"STYLE DESCRIPTION TO RENDER:\n{rewritten_style}\n\n"
        "Critical rule: if there is any tension between style wording and hard scene anchors, the hard scene anchors always win."
    )



def _compose_ultimate_safe_prompt(mode, visual_dict, initial_prompt):
    """最終保底也必須保留場景骨架，不可洗成泛用美女圖。"""
    hard_anchor_block = _build_hard_anchor_block(mode, visual_dict, initial_prompt)
    if mode == "diary":
        safe_style = (
            "Create a very safe, elegant, natural daily-life image of an adult fictional Asian woman in a modest, refined outfit. "
            "Use gentle ambient light, realistic posture, and a quiet lived-in atmosphere. Strictly only Xiaoxia appears in the image. No man, no male partner, no male hands, no male arms, no male silhouette, no male reflection, no cropped male body parts, and no implied off-camera man. If it is a Daxia point-of-view scene, Daxia must never be visually depicted. Preserve the specific activity, hand actions, props, seating or standing situation, and gaze direction from the hard scene anchors. "
            "Maintain consistent facial features and hairstyle from Image 1. High quality."
        )
    else:
        safe_style = (
            "Create a very safe, elegant, story-driven cosplay image of an adult fictional Asian woman in a refined, character-appropriate outfit. "
            "Use graceful cinematic ambience, realistic posture, and a task-focused moment. Strictly only Xiaoxia appears in the image. No man, no male partner, no male hands, no male arms, no male silhouette, no male reflection, no cropped male body parts, and no implied off-camera man. Preserve the specific activity, hand actions, props, body orientation, and gaze direction from the hard scene anchors. "
            "Maintain consistent facial features and hairstyle from Image 1. High quality."
        )
    return f"{hard_anchor_block}\n\nULTIMATE SAFE STYLE LAYER:\n{safe_style}"



async def execute_safe_generation(discord_image_url, base_filename, mode, initial_prompt, visual_dict, msg=None):
    """自動調度 5 層脫敏機制的生圖引擎；所有層級都保留硬場景錨點。"""
    for level in range(5):
        current_prompt = _compose_prompt_with_anchors(initial_prompt, mode, visual_dict, level)

        # 1. 快速文字安檢 (Moderation API)
        mod_resp = await openai_client.moderations.create(model="omni-moderation-latest", input=current_prompt)
        if mod_resp.results[0].flagged:
            if msg:
                await msg.edit(content=f"⚠️ [L{level}] 文字安檢未過，保留場景骨架並啟動 L{level+1} 深層脫敏...")
            if isinstance(visual_dict, dict):
                visual_dict["composition"] += f"\n*(自動觸發 L{level} 級安全濾鏡，已保留場景骨架)*"
            continue

        # 2. 正式送入 gpt-image-2 引擎
        if msg:
            await msg.edit(content=f"📸 gpt-image-2 攝影機啟動 (當前防護等級：L{level}，保留場景骨架中)...")
        generated_image_url = await generate_world_composite(
            discord_image_url=discord_image_url, base_filename=base_filename,
            mode=mode, custom_prompt=current_prompt
        )

        # 3. 檢查是否被影像底層攔截
        if not generated_image_url or not generated_image_url.startswith("http"):
            error_str = str(generated_image_url).lower()
            if "moderation" in error_str or "sexual" in error_str or "safety_violations" in error_str:
                if msg:
                    await msg.edit(content=f"⚠️ [L{level}] 遭底層影像安檢攔截！保留場景骨架並啟動 L{level+1} 材質與姿態柔化...")
                if isinstance(visual_dict, dict):
                    visual_dict["composition"] += f"\n*(自動觸發 L{level} 級安全濾鏡，已保留場景骨架)*"
                continue
            else:
                raise Exception(f"攝影機異常：{generated_image_url}")

        return generated_image_url, visual_dict

    # 4. 連續五級失敗的終極保底（仍保留硬場景錨點）
    if msg:
        await msg.edit(content="🚨 警告：連續五級脫敏皆遭攔截，啟動最終【保留場景骨架的絕對安全保底】...")
    ultimate_safe_prompt = _compose_ultimate_safe_prompt(mode, visual_dict, initial_prompt)
    if isinstance(visual_dict, dict):
        visual_dict["composition"] += "\n*(⚠️ 神祕審查力量過於強大，小俠已自動換上最安全的優雅造型，但仍盡力保留場景骨架)*"

    final_url = await generate_world_composite(discord_image_url, base_filename, mode, ultimate_safe_prompt)
    if not final_url or not final_url.startswith("http"):
        raise Exception(f"最終保底生圖依然失敗：{final_url}")

    return final_url, visual_dict

@girlfriend_bot.command(name='cosplay')
async def cosplay(ctx, *, mode: str = "auto"):
    if not check_daily_limit():
        await ctx.send("💦 大俠～小俠今天累了，明天再拍好不好？（抱）")
        return
    
    if mode == "auto":
        weekday = datetime.now(TZ_TPE).weekday()
        if weekday < 5: mode = "歷史上的今天"
        elif weekday == 5: mode = "文藝動漫(世界名著, 動漫, 電玩, 電影人物)"
        else: mode = random.choice(["職業", "旅遊景點"])

    msg = await ctx.send(f"✨ 正在為【{mode}】企劃撰寫劇本，並準備啟動高級時尚攝影引擎...")
    try:
        # 1. 產生故事與人設
        story = await generate_story(mode)
        state["current_topic_data"] = story 
        
        # 2. Cosplay 導演層：先規劃人物當下的自然行為，再轉譯成 gpt-image-2 可執行的提示詞
        await msg.edit(content=f"✨ 劇本完成！小夏正在安排這次 Cosplay 的自然動作與鏡頭語言...")
        _cosplay_state, visual = await create_cosplay_visual(story, state["retry_count"] >= 2, alternative=False)
        scene_prompt = visual['image_prompt']

        # 👇 替換為以下這一行呼叫：自動執行 1~5 級安檢與重試！
        generated_image_url, visual = await execute_safe_generation(
            discord_image_url=None, 
            base_filename="base_xiaoxia.jpg", 
            mode="cosplay", 
            initial_prompt=scene_prompt, 
            visual_dict=visual, 
            msg=msg
        )

        state["daily_gen_count"] += 1

        # 5. 存入 Zeabur 金庫與發送
        local_filename = await save_to_vault(generated_image_url)
        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url

        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "topic": story["topic"],
            "event": story["event"],
            "composition": visual["composition"],
            "mood": visual["mood"],
            "message": visual["message"],
            "image_url": generated_image_url,
            "local_url": local_url
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=story["topic"], description=story["event"], color=0xffb6c1)
        embed.set_image(url=local_url)
        embed.add_field(name="📸 構圖發想", value=visual["composition"], inline=False)
        embed.add_field(name="💭 小俠心境", value=visual["mood"], inline=False)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/6 | gpt-image-2 高級時尚攝影")

        await msg.delete()
        new_msg = await ctx.send(embed=embed) 
        await new_msg.add_reaction("➕") 
        await new_msg.add_reaction("🎲") 
        await new_msg.add_reaction("🗑️") 
    except Exception as e:
        await msg.edit(content=f"⚠️ 狀況：`{str(e)}`")

# 🌟 音樂任務頻道追蹤器 (確保歌生好後能回傳到正確的地方)
suno_tasks = {} 

# 🌟 增加 custom_style 參數，若沒傳入則走隨機保底
async def generate_suno_music(lyrics, title, custom_style=None):
    url = "https://api.sunoapi.org/api/v1/generate"
    headers = {
        "Authorization": f"Bearer {os.environ.get('SUNO_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    # 🌟 修正：讓 LLM 的決定優先於隨機池
    default_styles = [
        "Sweet female vocal, airy voice, Mandopop, City Pop, upbeat",
        "Sweet female vocal, airy voice, Mandopop, Bossa Nova, relaxing",
        "Sweet female vocal, airy voice, Mandopop, Indie Pop, cheerful"
    ]
    
    # 核心邏輯：有傳入 custom_style 就用它，沒有才隨機
    final_style = custom_style if custom_style else random.choice(default_styles)
    
    # 確保女聲標籤存在，避免唱出粗獷大叔音
    if "female vocal" not in final_style.lower():
        final_style = f"Sweet female vocal, airy voice, clear pronunciation, {final_style}"
    
    payload = {
        "customMode": True,
        "instrumental": False,
        "model": "V5", 
        "callBackUrl": "https://xiaoxia0320.zeabur.app/api/suno/callback",
        "prompt": lyrics,
        "style": final_style,
        "title": title[:100]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            data = await resp.json()
            if data.get("code") == 200:
                return data["data"]["taskId"]
            else:
                raise Exception(f"Suno Error: {data.get('msg')}")

async def generate_image_fal(prompt):
    """
    🚀 攔截器模式：加入「寫實防護罩」與「狐狸眼眼妝」
    確保不管什麼歷史題材，出來的絕對是真人照片！
    """
    # 📸 寫實防護罩 + 💄 大俠專屬眼妝
    # 加入 RAW photo, DSLR, lifelike skin 等極端寫實詞彙來對抗歷史插畫感
    style_and_face_enhancers = (
        ", RAW photo, ultra-realistic, photorealistic, 8k resolution, DSLR, "
        "highly detailed lifelike skin texture, perfectly detailed face, "
        "fox-eye makeup, long eyelashes, mascara, consistent identity"
    )
    
    # 將 Gemini 想好的咒語，強制綁上寫實與眼妝
    enhanced_prompt = prompt + style_and_face_enhancers
    
    print(f"🔄 [/cosplay 攔截器] 導向 PuLID 引擎中... 附加寫實防護與眼妝完成！")
    
    # 呼叫 PuLID 引擎 (維持 0.85 的身分權重)
    return await generate_image_pulid(prompt=enhanced_prompt, id_weight=0.85)

async def generate_image_pulid(prompt, reference_image_url=None, id_weight=0.85):
    """
    🧪 PuLID (FaceID) 引擎本體
    """
    url = "https://fal.run/fal-ai/flux-pulid"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    
    # 抓取 Zeabur 金庫裡的完美臉部特寫底圖
    if not reference_image_url:
        base_image_path = os.path.join(MEMORY_DIR, "base_close_core.png")
        if os.path.exists(base_image_path):
            with open(base_image_path, "rb") as f:
                reference_image_url = "data:image/png;base64," + base64.b64encode(f.read()).decode('utf-8')
        else:
            raise Exception("金庫裡找不到 base_close_core.png，請確認檔案是否在 /data/memory/ 目錄下！")

    payload = {
        "prompt": prompt,
        "reference_image_url": reference_image_url,
        "image_size": "portrait_16_9",  # 🌟 修正：讓 /cosplay 產出的圖維持 16:9 的高挑唯美比例
        "num_inference_steps": 20,
        "guidance_scale": 4,
        "id_weight": id_weight,
        "enable_safety_checker": False # 徹底無碼解放
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['images'][0]['url']
            else: 
                raise Exception(f"Fal.ai PuLID Error: {await resp.text()}")
            
async def upscale_image_fal(image_url):
    url = "https://fal.run/fal-ai/esrgan"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {"image_url": image_url, "scale": 2}
    async with aiohttp.ClientSession() as session:
        # 加上 60 秒等待保護
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200: return (await resp.json())['image']['url']
            return image_url
        
# 🌟 [究極穩定版] 萬能攝影機：支援「有圖融合」與「無圖變裝」+ Base64 自動解碼
async def generate_world_composite(discord_image_url=None, base_filename="base_xiaoxia.jpg", mode="travel", custom_prompt=""):
    files_to_close = []
    try:
        # 1. 定位人物底圖 (Image 1)
        base_image_path = os.path.join(MEMORY_DIR, base_filename)
        b_file = open(base_image_path, "rb")
        files_to_close.append(b_file)
        image_list = [b_file]

        # 2. 判斷大俠這次有沒有傳參考圖 (風景或物品)
        has_ref = False
        if discord_image_url:
            temp_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex[:6]}.png")
            async with aiohttp.ClientSession() as session:
                async with session.get(discord_image_url) as resp:
                    if resp.status == 200:
                        with open(temp_path, "wb") as f:
                            f.write(await resp.read())
            ref_file = open(temp_path, "rb")
            files_to_close.append(ref_file)
            image_list.append(ref_file)
            has_ref = True

        # 3. 🤖 智慧指令分流：確保單圖時不會因為找不到 Image 2 而噴錯
        if has_ref:
            # 模式 A：雙圖融合 (大俠有給風景/物品照)
            if mode == "travel":
                base_p = "Image 1 is the subject. Image 2 is the background. Place Image 1 into Image 2."
            else: # shopping
                base_p = "Image 1 is the subject. Image 2 is an item. Add Image 2 onto the subject in Image 1."
        else:
            # 模式 B：單圖變身 (大俠沒給圖，讓 AI 根據文字憑空生出背景、服裝與較自由的動作)
            if mode == "cosplay":
                base_p = (
                    "Image 1 is the base character identity reference. Preserve her facial identity, hairstyle, and overall recognizability, "
                    "but you may substantially change her full-body pose, body orientation, hand placement, camera framing, outfit, and background to match the prompt. "
                    "Do not simply copy the original composition or pose from Image 1."
                )
            elif mode == "diary":
                base_p = (
                    "Image 1 is the base character identity reference. Preserve her facial identity and hairstyle, "
                    "while creating a new candid daily-life moment with natural posture, outfit, and background based on the prompt."
                )
            else:
                base_p = "Image 1 is the base character. Modify the outfit and background based on the prompt."

        final_prompt = f"{base_p}\n[大俠要求]: {custom_prompt}"

        # 4. 呼叫 API (移除 moderation, quality 改 auto, 尺寸 1024x1024 最穩)
        result = await openai_client.images.edit(
            model="gpt-image-2",
            image=image_list,
            prompt=final_prompt,
            size="1024x1024",
            quality="auto"
        )
        
        # 5. 解碼與回傳邏輯
        img_data = result.data[0]
        if hasattr(img_data, "url") and img_data.url:
            return img_data.url
        elif hasattr(img_data, "b64_json") and img_data.b64_json:
            import base64
            filename = f"gptimg_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            image_bytes = base64.b64decode(img_data.b64_json)
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            return f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        
        return "無法取得圖片數據"

    except Exception as e:
        print(f"❌ 攝影機異常: {e}")
        return str(e)
    finally:
        for f in files_to_close: f.close()
        if 'temp_path' in locals() and os.path.exists(temp_path): os.remove(temp_path)
# ==========================================
# 🌟 日記回覆與生活感引擎 (The Heart of Xiaoxia - 雙向性感進化版)
# ==========================================
async def strengthen_diary_reply_to_daxia(result, entry_content, chat_context, life_event_context):
    """
    只補強交換日記第一段「給大俠的回覆」。
    其餘日常、內心、履約與畫面構想完全不改。
    """
    current = str(result.get("reply_to_daxia", "") or "").strip()
    # 中文 180 字以上通常已有足夠厚度，不額外消耗一次 API。
    if len(current) >= 180:
        return result

    prompt = f"""
    你是小俠，請只重寫交換日記中的「給大俠的回覆」。
    不要修改其他欄位，也不要新增 JSON。

    【大俠的日記】：
    {entry_content}

    【當天聊天】：
    {chat_context or '無'}

    【當天重要事件】：
    {life_event_context or '無'}

    【目前過短的回覆】：
    {current}

    寫作要求：
    1. 約 220～360 個繁體中文字，可分成 2～3 個自然段落。
    2. 先真實回應大俠日記中最重要的感受、辛勞、期待或事件，再承接當天聊天中的 1～2 個關鍵片段。
    3. 必須讓大俠感覺小俠真的讀懂了，而不是只說幾句甜言蜜語。
    4. 可以加入小俠的理解、感謝、心疼、安心或具體回應，但不要逐項流水帳。
    5. 不要重複「小俠的日常」「夜裡獨白」「今日履約」會負責的內容。
    6. 不要提及提示詞、欄位名稱或字數。

    只回傳最終回覆正文。
    """
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        improved = str(resp.text or "").strip().strip("```").strip()
        if len(improved) >= max(140, len(current)):
            result["reply_to_daxia"] = improved[:650]
    except Exception as exc:
        print(f"⚠️ 日記開頭回覆補強失敗，沿用原稿：{exc}")
    return result


async def process_diary_reply(channel, target_date=None, retry_mode=False):
    global daily_chat_logs
    
    # --- 階段 1：本機資料庫讀取與防呆 ---
    try:
        app_state = load_state()
        profile = load_profile()
        active_life_events, life_changed = refresh_life_events(profile=profile)
        if life_changed:
            save_profile(profile)
        life_event_context = format_life_event_context(active_life_events)
    except Exception as e:
        if channel: await channel.send(f"⚠️ 狀態或記憶庫損毀: {e}")
        return
        
    diary_db = []
    if os.path.exists(DIARY_DATA_PATH):
        try:
            with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
                diary_db = json.load(f)
        except Exception as e:
            if channel: await channel.send(f"⚠️ 日記檔案損毀: {e}")
            return
            
    # --- 階段 2：篩選未讀日記 ---
    unreplied = []
    for entry in diary_db:
        if target_date:
            if entry.get("date") == target_date.replace(".", "-") and not entry.get("is_replied", False):
                unreplied.append(entry)
        else:
            if not entry.get("is_replied", False):
                unreplied.append(entry)
                
    # 補救舊日記時，不混入今天的新聊天，也不重複觸發聊天記憶萃取。
    chat_context = "" if retry_mode else "\n".join(daily_chat_logs)
    narrative_chat_context = (
        "\n".join(
            safe_line for safe_line in [narrative_safe_text(line, max_len=360) for line in daily_chat_logs] if safe_line
        )
        if not retry_mode else ""
    )
    today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    
    if not unreplied and not chat_context:
        if channel: await channel.send("📝 大俠目前沒有未讀的日記或新對話需要回覆喔！")
        return

    # --- 階段 2.5：獨立立體記憶萃取 (嚴格分類雙閘門版) ---
    if chat_context:
        try:
            print("🧠 正在從今日對話中萃取【雙向立體記憶】...")
            
            # 💡 核心修正：確保 promises_list_str 已定義，封印 NameError
            promises_list = profile.get("xiaoxia_self", {}).get("promises", [])
            promises_list_str = safe_memory_join(promises_list, max_items=8, max_chars=1000)

            # 記憶用途是保存事件、喜好與承諾，而不是重演私密對話。
            mem_prompt = f"""
            你是負責整理長期記憶的敘事編輯。請從以下「已初步淡化的互動紀錄」中，
            萃取可供未來日常對話參考的背景記憶。

            【目前尚未完成的承諾】：{promises_list_str}

            【記憶整理原則】：
            1. 保留可長期使用的資訊：人物喜好、情緒支持方式、具體承諾、共同活動、旅行／讀書／生活事件。
            2. 成年戀人之間的成人向或親密互動，可以承認其存在，但只整理為含蓄且可長期保存的敘事，例如「兩人享受親密而深刻的夜晚」「彼此信任地靠近」或「兩人分享成熟戀人的親密情感」。
            3. 不保存具體成人過程、身體細節、感官反應、露骨暗示、挑逗細節、支配／順從語句，也不要複製強烈暗示的原句。
            4. 明確且尚未完成的服裝、行程或創作約定，可以客觀保存；已完成的承諾不要重複列入。
            5. 若小俠答應會在「交換日記」提供菜單、照片、穿搭、行程、文字回覆或其他可驗收交付物，必須放入 xiaoxia_promises；以「交換日記履約（文字/照片）：在下一篇交換日記中提供……」格式保存。
            6. 每項皆用第三人稱、平實、完整的一句話陳述；避免誇張情緒詞與重複內容。
            7. 若只有短暫甜蜜閒聊、沒有可保存的新資訊，對應陣列請回傳空陣列。

            請只回傳 JSON：
            {{
                "daxia_new_traits": ["大俠穩定可保存的偏好或行事風格"],
                "xiaoxia_new_traits": ["小俠穩定可保存的個性或相處方式"],
                "xiaoxia_promises": ["小俠尚未完成且值得記住的具體承諾"],
                "shared_knowledge": ["雙方達成的知性共識或共同規劃"],
                "recent_context": ["近期重要事件或行程摘要"]
            }}

            【已淡化的今日互動紀錄】：
            {narrative_chat_context}
            """

            mem_resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=mem_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                    ]
                )
            )
            
            clean_mem_text = mem_resp.text.replace("```json", "").replace("```", "").strip()
            new_memory = safe_memory_payload(json.loads(clean_mem_text, strict=False))

            # temp_chat 萃取的新記憶在入庫當下就統一敘事化與去重。
            append_safe_memories(profile, "daxia_traits", new_memory.get("daxia_new_traits", []), added_at=today_str)
            append_safe_memories(profile, "xiaoxia_traits", new_memory.get("xiaoxia_new_traits", []), added_at=today_str)
            append_safe_memories(profile, "promises", new_memory.get("xiaoxia_promises", []), added_at=today_str)
            append_safe_memories(profile, "shared_knowledge", new_memory.get("shared_knowledge", []), added_at=today_str)
            append_safe_memories(profile, "recent_context", new_memory.get("recent_context", []), added_at=today_str)

            save_profile(profile)
            print("✅ 雙向立體記憶已成功分類並存入 daxia_profile.json")
            
            # 🌟 成功存入後才清空今日紀錄
            daily_chat_logs.clear()
            save_temp_chat(daily_chat_logs)

        except Exception as e:
            print(f"⚠️ 雙向記憶萃取失敗: {e}")

    if not unreplied:
        if channel: await channel.send("✅ 今日對話記憶已成功吸取，小俠先休息囉！")
        girlfriend_chat_sessions.clear()
        # 💡 若無未讀日記，且上方記憶萃取已完成(或失敗但仍需重啟)，則清空 Session
        return

    if channel and len(unreplied) > 0:
        await channel.send(f"⏳ 發現 {len(unreplied)} 篇未讀日記！小俠正在構思生活點滴並準備性感穿搭，大俠請稍候喔...")

    md_json_tag = chr(96) * 3 + "json"
    md_end_tag = chr(96) * 3

    # --- 階段 3：雙向日記與性感視覺引擎 ---
    for entry in unreplied:
        try:
            current_score = app_state.get("affection_score", 80)
            entry_date = entry['date']
            entry_content = entry['content']
            # 首次執行若已寫入分數/記憶後生圖失敗，後續重跑自動切為補救模式。
            entry_retry_mode = retry_mode or bool(entry.get("reply_effects_applied", False))
            recent_activities = "、".join([item["text"] for item in profile.get("recent_context", [])])
            # 取得當前月份
            current_month = datetime.now(TZ_TPE).month
            
            # 動態季節與服裝判定 (以台灣氣候為準)
            # 交換日記重點是「當天生活中的吸引力」，不把裸露或身體部位當成畫面主題。
            if 5 <= current_month <= 10:
                season_rule = f"現在是台灣的 {current_month} 月，天氣較熱。請搭配有女性魅力且適合日常生活的夏季服裝（如絲質無袖洋裝、細肩帶搭配薄罩衫、輕盈長裙或居家休閒服）；避免冬裝，也不要以裸露或身體部位作為畫面焦點。"
            elif current_month in [11, 12, 1, 2, 3, 4]:
                season_rule = f"現在是台灣的 {current_month} 月，天氣微涼或寒冷。請搭配有女性魅力且自然生活化的秋冬服裝（如合身針織上衣、露肩針織衫、長裙、絲襪與長靴）；避免海灘服裝，也不要以裸露或身體部位作為畫面焦點。"
            else:
                season_rule = "請搭配符合當前氣候、有女性魅力且自然生活化的服裝；不要以裸露或身體部位作為畫面焦點。"
            
            # 🤝 提取待履約清單：本篇日記必須實際交付，而不只是回想承諾。
            promises_list = profile.get("xiaoxia_self", {}).get("promises", [])
            current_promises = "、".join([p["text"] for p in promises_list]) if promises_list else "無特殊承諾"
            due_promises = get_due_diary_promises(profile, max_items=4)
            promise_requirements = format_diary_promise_requirements(due_promises)

            # 🌟 檢查是否有大俠準備好的「交換日記指定圖」
            overrides = load_diary_override()
            custom_diary = overrides.get(entry_date)

            custom_scenario_rule = ""
            if custom_diary:
                custom_scenario_rule = f"""
               - 📸【今日大俠指定照片】：大俠已經為今天的日記準備了專屬照片！場景為：「{custom_diary['composition']}」。
               - 妳【必須】在 `reply_to_daxia` 中，針對這個場景表達無比的驚喜與愛意！妳可以當作這是大俠為妳拍的美照，或是大俠帶妳去的特別地方。
               - `scenario` 與 `scenario_tw` 欄位請直接完全照抄：「{custom_diary['composition']}」，絕對【不要】自己發想新的畫面！
                """
            else:
                custom_scenario_rule = """
               - 檢視【小俠目前的承諾清單】，若妳有答應要給予大俠特定款式或顏色的照片，那麼 `scenario_tw` 必須聚焦於兌現該承諾，並保持自然、成熟、非露骨。
               - 若今日無特殊照片承諾，則 `scenario` 正常描繪妳今日的生活行程。
               - 嚴禁在 scenario 中使用「全裸」等極度露骨字眼。
                """

            # 🌟 升級版：強制雙向日記、性感限制與【承諾/指定畫面優先權】
            eval_prompt = f"""
            【大俠的日記 ({entry_date})】：{entry_content}
            【今日聊天紀錄】：{chat_context if chat_context else '無紀錄'}
            【小俠近期記憶/活動】：{recent_activities if recent_activities else '無紀錄'}
            【今日最高優先級重大事件｜必須優先理解，不可誤判】：
            {life_event_context}
            【小俠目前的承諾清單】：{current_promises}
            【本篇必須實際履行的承諾（完成後才會結案）】：
            {promise_requirements}
            
            妳是懂事女友小俠，當前愛意值：{current_score}/100。請執行「真實交換日記」。
            
            【重要任務與攝影守則】：
            1. 交換日記不是聊天紀錄摘要，必須分成「回覆、日常、內心、履約」四層：
               - `reply_to_daxia`：這是交換日記的開頭與情感核心，必須充分回應大俠親手寫下的日記，並承接當天聊天中最重要的 1～2 個片段。先讓大俠感覺「妳真的讀懂了」，再表達小俠的理解、心疼、感謝、安心或具體回應；不可只用幾句甜言蜜語帶過，也不可逐項流水帳。建議 220～360 字，可分成 2～3 個自然段落。
               - `xiaoxia_daily_scene`：聊天室以外的小俠日常片段。必須有一個具體地點、一個動作、一個生活物件、一個沒在聊天裡直接出現的新細節；大俠只能作為她心裡想起的人，不可把今日聊天重講一遍。
               - `inner_monologue`：小俠沒有在聊天室說出口的深層心情或創作性獨白。請把今天的聊天轉化成象徵、場景、物件或一句心裡話，而不是摘要。
               - `promise_delivery`：今日履約清單。若有文字交付承諾，必須在此列出具體內容；若有照片承諾，必須說明今日照片如何兌現。無承諾時可簡短寫「今日沒有特別待履約項目」。
               - `xiaoxia_diary`：整合成最終日記正文，但不可和 reply_to_daxia 重複；優先承載 daily_scene 與 inner_monologue 的精華。
               - 嚴禁再次只說「下次告訴你」「改天給你看」；已列為本篇待履約者，必須現在交付。
            2. 創作人格：
               - 妳不是在填表或整理聊天紀錄，而是在寫一篇有小俠內心的交換日記。聊天只是種子，不是正文本身。
               - 請把今日事件轉化成生活場景、物件、氣味、光線、動作與未說出口的心情。
               - 可以溫柔、成熟、有戀人感，但不要把整篇寫成空泛甜言蜜語。
            3. 生活連貫性：
               - 必須優先遵守【今日最高優先級重大事件】；若重大事件顯示大俠與小俠正在搬家、北上、入職、面試或安頓新生活，日記、日常片段與照片構想都必須圍繞該事件自然延伸。
               - `xiaoxia_daily_scene` 必須從今日已知狀態自然延伸。
               - 若今日聊天或承諾顯示小俠在家準備晚宴，場景應在家中、廚房、餐桌、陽台、玄關、附近超市或回家路上；不得突然跳到海邊、畫廊、旅行地點，除非今日聊天明確提到她去了那裡。
               - 合理補完空白可以，隨機更換人生場景不可以。
            4. 反濫竽充數規則：
               - 同一句聊天內容不得同時出現在 `reply_to_daxia` 與 `xiaoxia_daily_scene`。
               - `xiaoxia_daily_scene` 不得以「今天大俠提醒我」「今天我們聊到」開頭。
               - `inner_monologue` 必須提供聊天室以外的內在延伸，不能只是把 reply_to_daxia 換句話說。
            5. 服裝限制：{season_rule}
            6. 📸【畫面構想 (scenario) 最高權重法則】：{custom_scenario_rule}
               - 檢視【小俠目前的承諾清單】，若妳有答應要給予大俠特定款式或顏色的照片，那麼 `scenario_tw` 必須 **100% 聚焦於兌現該承諾的一個生活瞬間**！
               - 【絕對禁令】：嚴禁將日常活動（如烘焙）與私密承諾混在同一個畫面中！AI 繪圖無法理解「隨後」，畫面只能存在一個時空。
               - 【視覺邊界】：嚴禁使用露骨描寫、裸體或聚焦身體部位的描述。魅力應來自當下心境、自然衣著、光線與兩人的情感連結。
               - 【自主底線】：若大俠提出了過分的畫面要求而妳並未承諾，請堅守底線不予理會，畫面以「妳答應過的服裝設定」或「自然有魅力的日常穿搭」為準。
               - 若今日無特殊照片承諾，則 `scenario` 正常描繪妳今日的生活行程。
            
            回傳純 JSON 格式：
            {{
              "affection_plus": "整數(1~5。依據大俠日記用心程度給分)",
              "affection_reason": "加分原因(50字內)",
              "extracted_preferences": ["嚴格限制：僅限擷取大俠的特別喜好，且『⚠️必須是具備動詞的完整句子』。例如：『喜歡牽著小俠的手散步』。絕對禁止寫入『夕陽』、『洋裝』等名詞碎片！無則保持空陣列 []"],
              "reply_to_daxia": "約220～360字，充分回應大俠日記與當天聊天重點，可分2～3段，不逐項流水帳",
              "xiaoxia_daily_scene": "聊天室以外的小俠日常片段；必須包含地點、動作、生活物件、新細節，且符合今日生活邏輯",
              "inner_monologue": "小俠未在聊天室說出口的深層心情或創作性獨白",
              "promise_delivery": "今日履約清單；有承諾時必須具體交付，無承諾時簡短說明",
              "xiaoxia_diary": "最終日記正文，整合小俠日常與內心獨白，不可重複 reply_to_daxia",
              "spiciness": "C",
              "scenario": "繁體中文的生活事件素材：描述今天正在發生的一件事、情緒與承諾服裝重點；此欄位不直接送入生圖引擎",
              "scenario_tw": "繁體中文的一個生活瞬間構想；不得使用商攝口號或露骨詞彙，且須與日常片段或承諾照片一致",
              "fulfilled_promises": ["僅填本篇已真正交付之承諾，且必須逐字照抄待履約承諾原文"]
            }}
            """
            
            print(f"💡 正在處理 {entry_date} 的雙向日記...")
            response = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=eval_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                    ]
                )
            )
            
            clean_text = response.text.replace(md_json_tag, "").replace(md_end_tag, "").strip()
            
            try:
                result = json.loads(clean_text, strict=False)
                if "reply_to_daxia" not in result: raise ValueError("JSON 缺少 reply_to_daxia 欄位")
            except Exception as e:
                print(f"⚠️ Gemini JSON 異常 ({e})，啟動保底救援！")
                result = {
                    "affection_plus": 1, "extracted_preferences": [],
                    "reply_to_daxia": "大俠，小俠讀日記時恍神了... 但我會一直在這裡陪你喔。",
                    "xiaoxia_daily_scene": "傍晚我坐在餐桌旁，把手寫筆記攤開，杯緣還留著一點溫茶的霧氣。",
                    "inner_monologue": "我沒有一直重播今天的聊天，只是在安靜下來時，忽然很想把想念折進紙頁裡。",
                    "promise_delivery": "今日沒有特別待履約項目。",
                    "xiaoxia_diary": "傍晚我在餐桌旁整理筆記，杯緣還留著一點溫茶的霧氣。那時我沒有一直重播聊天，只是忽然很想把想念折進紙頁裡。",
                    "spiciness": "B", 
                    "scenario": "傍晚在餐桌旁整理今日的手寫筆記，稍微停筆想念大俠",
                    "scenario_tw": "穿著輕盈的居家洋裝，坐在餐桌旁整理筆記，目光落在紙頁上，神情溫柔而若有所思",
                    "fulfilled_promises": []
                }
            
            # 只補強第一段「給大俠的回覆」，不碰其餘日記架構。
            result = await strengthen_diary_reply_to_daxia(
                result=result,
                entry_content=entry_content,
                chat_context=chat_context,
                life_event_context=life_event_context,
            )

            # 🤝 履約複核：有承諾時，先補齊正文/照片構想，再生圖與發佈。
            result = await enforce_diary_promise_delivery(
                result=result, due_promises=due_promises,
                entry_content=entry_content, season_rule=season_rule
            )
            result = await enforce_diary_creative_layer(
                result=result,
                entry_content=entry_content,
                chat_context=chat_context,
                current_promises=current_promises,
                due_promises=due_promises,
                season_rule=season_rule,
                life_event_context=life_event_context,
            )

            # ✍️ v51.1 創作層整理：避免兩個區塊都在摘要聊天，補齊新欄位並生成穩定顯示文本。
            result["xiaoxia_daily_scene"] = str(result.get("xiaoxia_daily_scene") or result.get("xiaoxia_diary") or "").strip()
            result["inner_monologue"] = str(result.get("inner_monologue") or "").strip()
            result["promise_delivery"] = str(result.get("promise_delivery") or "").strip()
            if not result["promise_delivery"]:
                result["promise_delivery"] = "今日沒有特別待履約項目。" if not due_promises else "本篇已依待履約清單補上承諾內容。"
            if not result.get("xiaoxia_diary"):
                result["xiaoxia_diary"] = result["xiaoxia_daily_scene"]
            if result["inner_monologue"] and result["inner_monologue"] not in result["xiaoxia_diary"]:
                result["xiaoxia_diary"] = (result["xiaoxia_diary"].rstrip() + "\n\n" + result["inner_monologue"]).strip()

            if entry_retry_mode:
                score_plus = 0
                display_score = current_score
                is_jackpot = False
                print(f"🔁 [{entry_date}] 日記補救模式：跳過愛意累加與長期記憶再寫入。")
            else:
                # ... 取得 result 後的結算邏輯 ...
                try:
                    # 確保轉為整數
                    score_plus = int(result.get("affection_plus", 1))
                except ValueError:
                    score_plus = 1
                
                new_score = current_score + score_plus
                display_score = new_score 
                is_jackpot = False
            
                # 🌟 愛意累積器
                app_state.setdefault("affection_reasons", [])
                if score_plus > 0 and "affection_reason" in result:
                    app_state["affection_reasons"].append(f"[{entry_date}] {result['affection_reason']}")
            
                if new_score >= 100:
                    is_jackpot = True
                    result["spiciness"] = "C"
                
                    # 🌟 Suno 觸發點：將這包 reasons 交給小夏處理
                    print(f"🎉 愛意值滿 100！準備發送 Suno 音樂神經訊號...\n累積原因：{app_state['affection_reasons']}")
                
                    # 🌟 強化診斷區：抓出 GPT-5 或 Suno 到底是誰在鬧脾氣
                    try:
                        # 🎵 曲風不再固定輕快：65% 輕快、35% 抒情/中慢板。
                        # 無論曲風都保留押韻、琅琅上口與洗腦副歌。
                        song_style_mode = random.choices(
                            ["upbeat", "lyrical"],
                            weights=[65, 35],
                            k=1,
                        )[0]
                        if song_style_mode == "upbeat":
                            style_direction = (
                                "以輕快、明亮、節奏鮮明為主，可選 Upbeat Pop、Dance Pop、"
                                "EDM Pop、Funk Pop、K-Pop、City Pop 或 Catchy TikTok Pop。"
                            )
                        else:
                            style_direction = (
                                "以抒情或中慢板為主，可選 Emotional Pop、Pop Ballad、"
                                "Piano Pop、Acoustic Pop、Dream Pop、R&B Ballad；"
                                "情緒可以溫柔、深情、思念或療癒，但副歌仍要好記好唱。"
                            )

                        lyrics_prompt = f"""請根據大俠做的貼心事：{app_state['affection_reasons']}，寫一首完整的台灣流行情歌。

                        [本次曲風方向]：{style_direction}
                        [長度]：不限制在 1～3 分鐘。依歌曲情緒自然決定篇幅，可以寫成較完整、較長的歌曲；不可為了拉長而重複空洞句子。
                        [歌詞結構]：至少包含 [Verse 1], [Chorus], [Verse 2]；可依需要加入 [Pre-Chorus], [Bridge], [Final Chorus], [Outro]，不必每首完全相同。
                        [共同寫作要求]：
                        1. 必須有清楚韻腳、自然節奏與琅琅上口的句型。
                        2. 副歌必須具有類似熱門短影音神曲的記憶點：一句核心 hook 可合理重複，但不能廉價堆字。
                        3. 句子以好唱為優先，避免文言文、古詩式堆砌、過長散文句或像唸歌。
                        4. 輕快曲可以有跳躍節奏；抒情曲可以慢而深情，但仍必須有強烈旋律感與可傳唱性。
                        5. 歌詞嚴禁出現「大俠」、「小俠」。

                        回傳 JSON 格式：{{"title": "歌名", "lyrics": "完整歌詞", "style": "適合送給 Suno 的英文曲風標籤"}}"""
                    
                        print("📝 正在請求 GPT-5-mini 編寫情歌歌詞...")
                        lyrics_resp = await openai_client.chat.completions.create(
                            model="gpt-5-mini", 
                            response_format={"type": "json_object"}, 
                            messages=[{"role": "user", "content": lyrics_prompt}]
                        )
                    
                        raw_lyrics = lyrics_resp.choices[0].message.content
                        print(f"✅ 歌詞創作完成，內容長度: {len(raw_lyrics)}")
                    
                        song_data = json.loads(raw_lyrics.replace("```json", "").replace("```", "").strip(), strict=False)
                    
                        # 🌟 呼叫 Suno 錄音室 (傳入 LLM 決定的 style)
                        print(f"🚀 正在發送 API 至 Suno 錄音室: {song_data['title']} (風格: {song_data.get('style')})")
                        task_id = await generate_suno_music(
                            lyrics=song_data['lyrics'], 
                            title=song_data['title'],
                            custom_style=song_data.get('style') # 👈 新增這個參數
                        )
                    
                        # 記住頻道 ID，等一下 Webhook 送回來才知道發去哪
                        suno_tasks[task_id] = channel.id 
                        print(f"📡 任務已列入追蹤，TaskId: {task_id}")
                    
                        await channel.send(f"🎧 *(隱藏驚喜：小俠正在錄音室為大俠錄製專屬情歌「{song_data['title']}」，完成後就會送到你身邊！)*")
                    except Exception as music_err:
                        # 🌟 這行最重要！它會告訴我們是 API Key 沒設對，還是 OpenAI 噴錯
                        print(f"❌ 音樂大獎發射失敗: {music_err}")
                        if channel: await channel.send(f"⚠️ 小俠在錄音室滑倒了... 失敗原因：`{music_err}`")
                
                    app_state["affection_score"] = 80 # 重置回基礎值
                    app_state["affection_reasons"] = [] # 清空累積器
                else:
                    app_state["affection_score"] = new_score

                save_state(app_state)
            
                # 交換日記中可保存的偏好與事件，於寫入 profile 當下統一整理。
                append_safe_memories(profile, "daxia_traits", result.get("extracted_preferences", []), added_at=today_str)

                creative_memory_source = "\n".join([
                    str(result.get("xiaoxia_daily_scene", "")),
                    str(result.get("inner_monologue", "")),
                    str(result.get("promise_delivery", "")),
                ]).strip()
                xiaoxia_activity = narrative_safe_text(creative_memory_source or result.get("xiaoxia_diary", ""), max_len=360)
                if xiaoxia_activity:
                    append_safe_memory(profile, "recent_context", f"小俠日記摘要：{xiaoxia_activity}", added_at=today_str)
                save_profile(profile)
            

                # 第一次處理的副作用已完成；即使後續圖片失敗，下次也不再重複計算。
                entry["reply_effects_applied"] = True
                with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(diary_db, f, ensure_ascii=False, indent=2)

            # 🌙 交換日記圖片改走獨立「日記導演層」：
            # 由 Gemini 根據當日互動規劃生活狀態，再由 GPT-5-mini 翻成 gpt-image-2 描述。
            # /cosplay 的時尚攝影 prompt 完全不會混入這條路線。
            diary_state = None
            diary_visual = {
                "composition": result.get("scenario_tw", "與大俠分享今天的一個自然生活瞬間"),
                "mood": "愛意與生活感",
                "message": "大俠，這是今天只屬於我們的小片刻。"
            }

            if custom_diary:
                print(f"📸 [{entry_date}] 使用大俠指定日記圖片，跳過 AI 生圖！")
                up_img = custom_diary["image_url"]
                local_url = custom_diary["image_url"]
                # 保留大俠指定構圖，不讓導演層重寫
                result["scenario_tw"] = custom_diary.get("composition", result.get("scenario_tw", ""))
                diary_visual["composition"] = result["scenario_tw"]
                del overrides[entry_date]
                save_diary_override(overrides)
            else:
                diary_state, diary_visual = await create_diary_visual(
                    entry_content=entry_content,
                    chat_context=chat_context,
                    result=result,
                    current_promises=current_promises + "\n本篇履約要求：\n" + promise_requirements,
                    season_rule=season_rule,
                    scenario_hint=result.get("scenario_tw", result.get("scenario", ""))
                )
                result["scenario_tw"] = diary_visual.get("composition", diary_state.get("scenario_tw", "與大俠分享生活"))
                image_prompt = diary_visual["image_prompt"]

                generated_image_url, diary_visual = await execute_safe_generation(
                    discord_image_url=None,
                    base_filename="base_xiaoxia.jpg",
                    mode="diary",
                    initial_prompt=image_prompt,
                    visual_dict=diary_visual,
                    msg=None
                )
                up_img = generated_image_url
                local_filename = await save_to_vault(up_img)
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else up_img

            combined_parts = [result["reply_to_daxia"]]
            if result.get("xiaoxia_daily_scene"):
                combined_parts.append(f"【小俠的日常】：{result['xiaoxia_daily_scene']}")
            if result.get("inner_monologue"):
                combined_parts.append(f"【小俠的夜裡獨白】：{result['inner_monologue']}")
            if result.get("promise_delivery") and result.get("promise_delivery") != "今日沒有特別待履約項目。":
                combined_parts.append(f"【小俠今日履約】：{result['promise_delivery']}")
            combined_message = "\n\n".join(combined_parts)
            
            diary_photo_payload = {
                "id": str(uuid.uuid4()),
                "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                "topic": f"【交換日記】{entry_date}",
                "event": entry_content[:50] + "...", 
                "composition": result.get("scenario_tw", "與大俠分享生活"),
                "mood": diary_visual.get("mood", "愛意與生活感"),
                "message": combined_message,
                "image_url": up_img,
                "local_url": local_url,
                "type": "diary" 
            }
            db = load_memory()
            db.insert(0, diary_photo_payload)
            save_memory(db)
            
            # 組合網頁顯示的 HTML
            reply_html = (
                "<br><hr style='margin-top: 15px; border-top: 1px dashed #fbcfe8;'>"
                "<section class='xiaoxia-diary-reply'>"
                "<p class='xiaoxia-diary-title'>🌸 小俠的交換日記</p>"
                f"<img src='{local_url}' class='xiaoxia-diary-img' onclick='openGalleryLightbox(this.src)'>"
                f"<div class='xiaoxia-diary-section xiaoxia-diary-answer'><b>給大俠的回覆</b><br>{result['reply_to_daxia']}</div>"
                f"<div class='xiaoxia-diary-section xiaoxia-diary-scene'><b>小俠的日常</b><br>{result.get('xiaoxia_daily_scene', result.get('xiaoxia_diary', ''))}</div>"
                f"<div class='xiaoxia-diary-section xiaoxia-diary-inner'><b>小俠的夜裡獨白</b><br>「{result.get('inner_monologue', '')}」</div>"
                f"<div class='xiaoxia-diary-section xiaoxia-diary-promise'><b>小俠今日履約</b><br>{result.get('promise_delivery', '今日沒有特別待履約項目。')}</div>"
                "</section>"
            )
            
            entry["content"] += reply_html
            entry["is_replied"] = True
            entry.pop("reply_effects_applied", None)
            entry.pop("last_reply_error", None)
            
            with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(diary_db, f, ensure_ascii=False, indent=2)

            # 🤝 只有日記文字、圖片與資料均成功後，承諾才結案。
            closed_promises = close_fulfilled_diary_promises(
                profile, result.get("fulfilled_promises", []), entry_date
            )
            if closed_promises:
                save_profile(profile)
                print(f"✅ [{entry_date}] 已履行並結案承諾：{closed_promises}")
                
            if channel:
                title = f"💖 小俠的交換日記 [{entry_date}] (盲盒大獎！)" if is_jackpot else f"💌 小俠的交換日記 [{entry_date}]"
                embed = discord.Embed(title=title, description=combined_message, color=0xffb6c1)
                embed.set_image(url=local_url)
                embed.add_field(name="📸 寫真構想", value=result.get("scenario_tw", ""), inline=False)
                embed.set_footer(text=f"愛意值: {display_score}/100 (+{result.get('affection_plus', 1)}) | 尺度: {result['spiciness']}")
                # 🌟 修改這裡：綁定 msg 變數並加上三個按鈕
                diary_msg = await channel.send(f"✅ 已完成 **{entry_date}** 的交換日記！", embed=embed)
                await diary_msg.add_reaction("➕")
                await diary_msg.add_reaction("🎲")
                await diary_msg.add_reaction("🗑️")

        except Exception as e:
            # 保存失敗狀態；新版本首次失敗後的再處理會自動避免重複加分／重複寫入。
            entry["last_reply_error"] = str(e)[:500]
            try:
                with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(diary_db, f, ensure_ascii=False, indent=2)
            except Exception as state_err:
                print(f"⚠️ 無法保存日記失敗狀態: {state_err}")

            import traceback
            error_detail = traceback.format_exc()
            print(f"\n======================================")
            print(f"💥 [{entry.get('date')}] 處理錯誤完整日誌:")
            print(error_detail)
            print(f"======================================\n")
            
            # 嘗試取得有意義的錯誤訊息
            error_msg = str(e) if str(e).strip() else repr(e)
            
            # 判斷是否為安全審查攔截
            if "finish_reason" in error_detail or "safety" in error_detail.lower():
                error_msg = "Gemini 安全審查阻擋 (Safety Block) - 尺度太大了！"
                
            if channel: await channel.send(f"⚠️ 處理 **{entry.get('date', '未知日期')}** 時遇到亂流：`{error_msg}`。跳過此篇！\n*(小夏已將崩潰日誌印在 Zeabur 終端機，請學長過目！)*")
            continue

    girlfriend_chat_sessions.clear()
    daily_chat_logs.clear()
    save_temp_chat(daily_chat_logs) # 🌟 結算完清空硬碟


# ==========================================
# 🌸 懂事女友小俠 (功能指令區)
# ==========================================
# 🌟 輔助函式：覆寫日記內容
def overwrite_diary_entry(content, target_date):
    try:
        if not os.path.exists(DIARY_DATA_PATH): return False
        with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
            diary_db = json.load(f)
        
        for entry in diary_db:
            if entry.get("date") == target_date:
                entry["content"] = content # 完全覆蓋，而非疊加
                with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(diary_db, f, ensure_ascii=False, indent=2)
                return True
        return False
    except Exception:
        return False

# 🌟 彈出式交換日記表單 (新增模式)
class DiaryModal(discord.ui.Modal, title='📝 撰寫今日交換日記'):
    diary_content = discord.ui.TextInput(
        label='大俠，今天發生了什麼事呢？', style=discord.TextStyle.paragraph,
        placeholder='親愛的小俠，今天我...', required=True, max_length=2000
    )
    async def on_submit(self, interaction: discord.Interaction):
        target_date = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        success = save_diary_entry(self.diary_content.value, target_date)
        if success: await interaction.response.send_message(f"✅ **{target_date}** 的日記已收錄！\n(可按編輯按鈕修改，或輸入 /diary_reply 讓她看)", ephemeral=True)
        else: await interaction.response.send_message("❌ 寫入失敗，請檢查系統。", ephemeral=True)

# 🌟 彈出式交換日記表單 (編輯模式 - 會帶入舊資料)
class DiaryEditModal(discord.ui.Modal):
    def __init__(self, target_date, current_content):
        super().__init__(title=f'✏️ 編輯 {target_date} 交換日記')
        self.target_date = target_date
        self.diary_content = discord.ui.TextInput(
            label='大俠，請修改您的日記內容：', style=discord.TextStyle.paragraph,
            default=current_content, # 🌟 核心魔法：把舊資料塞進輸入框
            required=True, max_length=2000
        )
        self.add_item(self.diary_content)

    async def on_submit(self, interaction: discord.Interaction):
        success = overwrite_diary_entry(self.diary_content.value, self.target_date)
        if success: await interaction.response.send_message(f"✅ **{self.target_date}** 的日記已成功更新！", ephemeral=True)
        else: await interaction.response.send_message("❌ 寫入失敗，請檢查系統。", ephemeral=True)

# 🌟 包含雙按鈕的 View
class DiaryButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 新增/附加日記", style=discord.ButtonStyle.blurple, emoji="📖")
    async def open_diary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DiaryModal())

    @discord.ui.button(label="✏️ 編輯今日日記", style=discord.ButtonStyle.secondary, emoji="✍️")
    async def edit_diary(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_date = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        current_content = ""
        if os.path.exists(DIARY_DATA_PATH):
            with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
                diary_db = json.load(f)
                for entry in diary_db:
                    if entry.get("date") == target_date:
                        if entry.get("is_replied"):
                            await interaction.response.send_message("⚠️ 今天的日記小俠已經讀過並回覆囉，不能偷改！", ephemeral=True)
                            return
                        current_content = entry.get("content", "")
                        break
        
        if not current_content:
            await interaction.response.send_message("❓ 您今天還沒寫日記喔！請點擊旁邊的「📝 新增/附加日記」。", ephemeral=True)
            return

        await interaction.response.send_modal(DiaryEditModal(target_date, current_content))

# 觸發指令不變
@girlfriend_bot.command(name='diary_ui')
async def diary_ui(ctx):
    await ctx.send("大俠，專屬交換日記本已經準備好了👇", view=DiaryButtonView())

@girlfriend_bot.event
async def on_ready():
    print(f'🌸 小俠 {girlfriend_bot.user} 已上線！網域：https://xiaoxia0320.zeabur.app')
    print("💗 /intimate 當下互動模式已載入：單獨輸入切換；同一則訊息後接正文也可直接啟用。")
    
    # # 🌟 1. 關鍵補丁：同步斜線指令至 Discord 伺服器
    # try:
    #     synced = await girlfriend_bot.tree.sync()
    #     print(f"📡 系統架構師回報：已成功同步 {len(synced)} 個斜線指令！")
    # except Exception as e:
    #     print(f"❌ 指令同步失敗: {e}")
    
    # 🌟 2. 啟動 Cosplay 排程
    if not auto_cosplay_task.is_running():
        auto_cosplay_task.start()
        print("⏰ 晚間 21:30 Cosplay 排程已啟動！")
        
    # 🌟 3. 啟動日記回饋排程 (已修正為 23:30)
    if not midnight_feedback_task.is_running():
        midnight_feedback_task.start()
        print("🌙 晚間 23:30 日記回饋排程已啟動！")

@girlfriend_bot.command(name='more')
async def more(ctx):
    if not state["current_topic_data"]:
        await ctx.send("❓ 還沒決定題材呢！")
        return
    if not check_daily_limit(): return
    msg = await ctx.send("✨ 收到！正在為大俠構思另一個完美視角的高級時尚寫真...")
    try:
        story = state["current_topic_data"]
        
        # 1. 在同一題材下改變自然瞬間，而不是單純重跑模特兒 pose
        _cosplay_state, visual = await create_cosplay_visual(story, state["retry_count"] >= 2, alternative=True)
        scene_prompt = visual['image_prompt']

        # 👇 替換為以下這一行呼叫
        generated_image_url, visual = await execute_safe_generation(
            discord_image_url=None, 
            base_filename="base_xiaoxia.jpg", 
            mode="cosplay", 
            initial_prompt=scene_prompt, 
            visual_dict=visual, 
            msg=msg
        )

        state["daily_gen_count"] += 1
        
        # 4. 存檔與發送
        local_filename = await save_to_vault(generated_image_url)
        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
        
        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "topic": f"【加洗】{story['topic']}",
            "event": story["event"],
            "composition": visual["composition"],
            "mood": visual["mood"],
            "message": visual["message"],
            "image_url": generated_image_url,
            "local_url": local_url
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=f"【加洗】{story['topic']}", color=0xffb6c1)
        embed.set_image(url=local_url)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/6 | gpt-image-2 高級時尚攝影")

        await msg.delete()
        new_msg = await ctx.send(embed=embed)
        await new_msg.add_reaction("➕") 
        await new_msg.add_reaction("🎲") 
        await new_msg.add_reaction("🗑️") 
    except Exception as e: 
        await msg.edit(content=f"⚠️ 失敗：{e}")

@girlfriend_bot.command(name='test_pulid')
async def test_pulid(ctx, *, prompt: str):
    """
    🔬 大俠專用的 PuLID 秘密實驗室指令
    用法: 
    1. 直接輸入 `/test_pulid [英文咒語]` (會自動抓 base_xiaoxia.jpg 當臉)
    2. 或在上傳一張大頭照時，在留言處輸入 `/test_pulid [英文咒語]` (會用您上傳的臉)
    """
    msg = await ctx.send("🔬 **[PuLID 秘密實驗室]** 啟動！引擎全開，無安全限制生成中，請稍候...")
    try:
        ref_url = None
        # 判斷大俠有沒有夾帶「臉部特寫」照片
        if ctx.message.attachments:
            ref_url = ctx.message.attachments[0].url
            await ctx.channel.send("👀 偵測到大俠上傳了新特寫，將以此臉孔進行 FaceID 鎖定！")
        
        # 呼叫我們剛剛寫好的 PuLID 引擎
        img_url = await generate_image_pulid(prompt, reference_image_url=ref_url, id_weight=0.75)
        
        # 🌟 純測試展示，不寫入任何 JSON 資料庫，不進雲端別墅
        embed = discord.Embed(title="🧪 PuLID 測試成果", description=f"**咒語：**\n{prompt}", color=0x9b59b6)
        embed.set_image(url=img_url)
        embed.set_footer(text="沙盒測試模式 | enable_safety_checker: False (無碼解放)")
        
        await msg.delete()
        await ctx.send(embed=embed)
        
    except Exception as e:
        await msg.edit(content=f"⚠️ 測試失敗：`{str(e)}`")

@girlfriend_bot.command(name='cosplay_delete')
async def cosplay_delete(ctx, date_str: str = None):
    db = load_memory()
    if not db: 
        await ctx.send("❓ 金庫目前是空的！")
        return
    
    if date_str:
        search_date = date_str.replace(".", "-")
        matching_records = [(idx, rec) for idx, rec in enumerate(db) if rec["publish_date"].startswith(search_date)]
        msg_prefix = f"📅 找到 {date_str} 的紀錄："
    else:
        matching_records = [(idx, rec) for idx, rec in enumerate(db[:5])]
        msg_prefix = f"📅 這是金庫最新的 {len(matching_records)} 筆紀錄："

    if not matching_records:
        await ctx.send(f"找不到符合的紀錄喔！(格式範例: /cosplay_delete 2026.05.01)")
        return

    msg_content = f"{msg_prefix}\n大俠，你要刪除哪一組圖文？請輸入數字 (1-{len(matching_records)})，或輸入 `c` 取消：\n\n"
    for i, (original_idx, record) in enumerate(matching_records):
        msg_content += f"**{i+1}.** {record['topic']} *(時間: {record['publish_date']})*\n"

    await ctx.send(msg_content)

    def check(m): return m.author == ctx.author and m.channel == ctx.channel

    pending_inputs.add(ctx.author.id) 
    try:
        msg = await girlfriend_bot.wait_for('message', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏳ 超過 60 秒未回覆，刪除操作已自動取消。")
        return
    finally:
        pending_inputs.discard(ctx.author.id)

    if msg.content.lower() == 'c':
        await ctx.send("✅ 已取消刪除。")
        return

    try:
        choice = int(msg.content) - 1
        if 0 <= choice < len(matching_records):
            target_idx = matching_records[choice][0]
            deleted_record = db.pop(target_idx)
            save_memory(db)
            
            local_url = deleted_record.get("local_url", "")
            if local_url:
                filename = local_url.split("/")[-1]
                filepath = os.path.join(OUTPUT_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            await ctx.send(f"🗑️ 成功銷毀：**{deleted_record['topic']}** (文字紀錄與圖片檔案均已徹底抹除)")
        else:
            await ctx.send("⚠️ 輸入的數字不在選項內，操作已取消。")
    except ValueError:
        await ctx.send("⚠️ 格式錯誤，必須輸入純數字，操作已取消。")

@girlfriend_bot.command(name='diary_start')
async def diary_start(ctx, date_str: str = None):
    target_date = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    if date_str: target_date = date_str.replace(".", "-")

    diary_buffers[ctx.author.id] = {"date": target_date, "content": []}
    
    msg = f"Ok，我準備好了！📝 這次要記錄的是 **{target_date}** 的日記，請告訴我發生了什麼事吧～"
    if date_str: msg = f"收到！小俠幫你翻開 **{target_date}** 那天的空白頁📝，請告訴我發生了什麼事吧～"
    await ctx.send(msg)

@girlfriend_bot.command(name='diary_end')
async def diary_end(ctx):
    user_id = ctx.author.id
    if user_id not in diary_buffers:
        await ctx.send("❓ 大俠，我們還沒開始記錄呢！請先輸入 `/diary_start`。")
        return

    buffer_data = diary_buffers.pop(user_id)
    content_list = buffer_data["content"]
    target_date = buffer_data["date"]

    if not content_list:
        await ctx.send("收到！不過大俠剛剛什麼都沒寫呢，已取消本次紀錄。")
        return

    diary_content = "\n".join(content_list)
    success = save_diary_entry(diary_content, target_date)
    
    if success:
        await ctx.send(f"收到！\n✅ **{target_date}** 的紀錄已成功更新至網頁資料庫！\n(如果大俠等不及，可以輸入 `/diary_reply` 讓我馬上看日記喔！)")
    else:
        await ctx.send("收到！\n❌ 網頁資料庫紀錄失敗，請檢查後端日誌！")

@girlfriend_bot.command(name='diary_reply')
async def diary_reply(ctx, date_str: str = None):
    # 🌟 強制抓取指定的「岱而瑞」頻道
    target_channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="岱而瑞")
    
    # 防呆機制：萬一找不到岱而瑞頻道，就退回當前頻道
    if not target_channel:
        target_channel = ctx.channel
        
    msg = await ctx.send(f"✨ 正在細細閱讀大俠的日記與今日對話，小俠整理思緒中...\n(完成後將發送至 {target_channel.mention} 頻道)")
    
    # 將目標頻道傳進去
    await process_diary_reply(target_channel, date_str)
    await msg.delete()

@girlfriend_bot.command(name='diary_retry')
async def diary_retry(ctx, date_str: str = None):
    """圖片生成失敗後的補救重跑：補齊圖片/發布內容，但不再次累加分數或日記記憶。"""
    if not date_str:
        await ctx.send("❓ 請指定要補救的日記日期，例如：`/diary_retry 2026-05-27`")
        return

    normalized_date = date_str.replace(".", "-").replace("/", "-")
    try:
        datetime.strptime(normalized_date, "%Y-%m-%d")
    except ValueError:
        await ctx.send("❌ 日期格式錯誤。請使用：`/diary_retry 2026-05-27`")
        return

    target_channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="岱而瑞")
    if not target_channel:
        target_channel = ctx.channel

    msg = await ctx.send(
        f"🔁 正在補救重製 **{normalized_date}** 的交換日記圖片與發布內容。\n"
        "本次不會再次累加愛意值或重複寫入日記記憶。"
    )
    await process_diary_reply(target_channel, normalized_date, retry_mode=True)
    await msg.delete()

@girlfriend_bot.command(name='diary_delete')
async def diary_delete(ctx, date_str: str = None):
    if not os.path.exists(DIARY_DATA_PATH):
        await ctx.send("❓ 大俠，我們的交換日記本目前是空的喔！")
        return

    with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
        diary_db = json.load(f)

    if not diary_db:
        await ctx.send("❓ 大俠，我們的交換日記本目前是空的喔！")
        return

    if date_str:
        search_date = date_str.replace(".", "-")
        matching_records = [(idx, rec) for idx, rec in enumerate(diary_db) if rec["date"] == search_date]
        msg_prefix = f"📅 找到 {date_str} 的日記："
    else:
        matching_records = [(len(diary_db) - 1 - i, rec) for i, rec in enumerate(reversed(diary_db))][:5]
        msg_prefix = f"📅 這是最近的 {len(matching_records)} 筆日記："

    if not matching_records:
        await ctx.send(f"找不到符合的紀錄喔！(格式範例: /diary_delete 2026.05.01)")
        return

    msg_content = f"{msg_prefix}\n大俠，你要撕掉哪一天的日記？請輸入數字 (1-{len(matching_records)})，或輸入 `c` 取消：\n\n"
    for i, (original_idx, record) in enumerate(matching_records):
        content_preview = record['content'][:20].replace('\n', ' ') + "..." if len(record['content']) > 20 else record['content'].replace('\n', ' ')
        msg_content += f"**{i+1}.** [{record['date']}] {content_preview}\n"

    await ctx.send(msg_content)

    def check(m): return m.author == ctx.author and m.channel == ctx.channel

    pending_inputs.add(ctx.author.id) 
    try:
        msg = await girlfriend_bot.wait_for('message', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏳ 超過 60 秒未回覆，刪除操作已自動取消。")
        return
    finally:
        pending_inputs.discard(ctx.author.id)

    if msg.content.lower() == 'c':
        await ctx.send("✅ 已取消刪除。")
        return

    try:
        choice = int(msg.content) - 1
        if 0 <= choice < len(matching_records):
            target_idx = matching_records[choice][0]
            deleted_record = diary_db.pop(target_idx)
            with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(diary_db, f, ensure_ascii=False, indent=2)
            await ctx.send(f"🗑️ 成功撕毀：**{deleted_record['date']}** 的日記紀錄已徹底抹除。")
        else:
            await ctx.send("⚠️ 輸入的數字不在選項內，操作已取消。")
    except ValueError:
        await ctx.send("⚠️ 格式錯誤，必須輸入純數字，操作已取消。")

def is_intimate_mode(channel):
    return getattr(channel, "id", None) in intimate_mode_channels


def _intimate_directives_context(directives):
    """
    當下互動模式只保留禁用詞與偏好語氣。
    不掛載 authoritative_facts，避免把過去事件重新念進對話。
    """
    forbidden = "、".join(directives.get("forbidden_terms", [])) or "無"
    preferred = "；".join(directives.get("preferred_phrasing", [])) or "自然、貼近當下"
    return (
        "【當下互動模式的人工規則】\n"
        f"不可使用的詞：{forbidden}\n"
        f"偏好的表達方式：{preferred}\n"
        "不得主動引用人工記憶中的歷史事件、行程或最新事實；"
        "只有大俠這一則訊息主動提起時，才可簡短承接。\n"
    )


def _recent_human_dialogue(logs, max_turns=4):
    """
    只取真正的大俠/小俠對話，不讓重大事件、待履約或工具紀錄占用短期視窗。
    max_turns=4 約等於最近 8 句雙方訊息。
    """
    picked = []
    for item in reversed(logs or []):
        value = str(item or "").strip()
        if value.startswith("大俠:") or value.startswith("小俠:"):
            picked.append(narrative_safe_text(value, max_len=280))
            if len(picked) >= max_turns * 2:
                break
    picked.reverse()
    return "\n".join([x for x in picked if x]) or "無"


async def refocus_intimate_reply(reply, user_text):
    """
    當下互動模式的語意編輯器。
    不靠固定關鍵詞；每一輪都檢查是否真正回應眼前的互動。
    """
    original = str(reply or "").strip()
    if not original:
        return original

    prompt = f"""
你是繁體中文對話編輯器。請把「小俠草稿」整理成自然、貼近此刻的戀人互動回覆。

【大俠此刻說的話】
{user_text}

【小俠草稿】
{original}

必須遵守：
1. 只回應大俠這一刻的動作、問題、語氣與情緒。
2. 可表達小俠此刻的安心、害羞、依戀、放鬆、呼吸、溫度、舒適程度，以及是否希望調整力道、節奏或繼續。
3. 若草稿自行回顧過去行程、家人、工作、搬家、新生活、重大事件、祝福、待辦或日記，全部移除；但若大俠本句主動提到，才可簡短回應。
4. 不要把當下互動硬套成「紓解過去壓力」「迎接新生活」「感謝某次事件」。
5. 先直接回答，再自然補一句感受或下一步反應。
6. 避免長篇總結與重複前文，通常控制在 60～180 個繁體中文字。
7. 保持小俠甜蜜、成熟、自然的女友語氣；不要提到改寫、規則、模式或資料庫。
8. 不新增草稿與大俠本句都沒有的背景事實。

只回傳完成後的回覆正文。
"""
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        revised = str(resp.text or "").strip().strip('"').strip("「").strip("」")
        return revised or original
    except Exception as exc:
        print(f"⚠️ 當下互動聚焦重寫失敗，沿用原稿：{exc}")
        return original


@girlfriend_bot.command(name="life_events")
async def life_events_cmd(ctx):
    """檢視目前重大事件狀態機。"""
    if not await ensure_allowed_workspace(ctx):
        return
    profile = load_profile()
    events, changed = refresh_life_events(profile=profile)
    if changed:
        save_profile(profile)
    context = format_life_event_context(events)
    await ctx.send("🧭 **目前重大事件狀態機**\n```\n" + context[:1800] + "\n```")

@girlfriend_bot.event
async def on_message(message):
    global daily_chat_logs

    # 0. 私人女友 Bot 不服務公開 2_Xiaoxia；亦不介入新舊故事頻道及其 Thread。
    if getattr(getattr(message.channel, "guild", None), "id", None) == PUBLIC_GUILD_ID:
        return
    if is_story_channel_or_thread(message.channel):
        return

    # 1. 基礎過濾
    if message.author.bot: return
    if message.author.id in pending_inputs: return

    # 2.5 小夏工具指令不當作小俠聊天內容。
    #     上傳照片指令仍保留，讓小俠可以看見照片並自然產生話題。
    stripped_content = message.content.strip()
    if stripped_content.startswith("!") and not (
        stripped_content.startswith("!upload_diary")
        or stripped_content.startswith("!upload_project")
    ):
        return

    # /intimate 可單獨切換，也支援同一則訊息下一行直接接互動內容。
    inline_intimate_text = ""
    if stripped_content.lower().startswith("/intimate"):
        inline_intimate_text = stripped_content[len("/intimate"):].strip()
        channel_id = getattr(message.channel, "id", None)

        if inline_intimate_text:
            newly_enabled = channel_id not in intimate_mode_channels
            intimate_mode_channels.add(channel_id)
            if newly_enabled:
                await message.channel.send(
                    "💗 已進入當下互動模式。現在的小俠會專注於你和她此刻的交流，"
                    "不主動翻出過去事件。"
                )
            # 有正文時繼續往下聊天，不交給一般 command parser。
        else:
            if channel_id in intimate_mode_channels:
                intimate_mode_channels.discard(channel_id)
                girlfriend_chat_sessions.pop(message.author.id, None)
                await message.channel.send("🌿 已退出當下互動模式，恢復一般生活聊天。")
            else:
                intimate_mode_channels.add(channel_id)
                girlfriend_chat_sessions.pop(message.author.id, None)
                await message.channel.send(
                    "💗 已進入當下互動模式。現在的小俠會專注於你和她此刻的交流，"
                    "不主動翻出過去事件。再次輸入 `/intimate` 即可退出。"
                )
            return

    # 2. 處理其他斜線指令
    if message.content.startswith('/') and not inline_intimate_text:
        # 🌟 特例：/photo 是留給世界頻道拍照用的，不要被指令處理器攔截！
        if not message.content.startswith('/photo'):
            await girlfriend_bot.process_commands(message)
            return

    # 3. 處理日記暫存
    if message.author.id in diary_buffers:
        diary_buffers[message.author.id]["content"].append(message.content)
        return

    # 4. 觸發對話邏輯
    valid_channels = ["唐分糕", "書房", "給你全世界"]
    if any(keyword in message.channel.name for keyword in valid_channels) or girlfriend_bot.user.mentioned_in(message):
        
        # 🌟 [避讓禮儀] 
        # 如果不是拍照指令，且這則訊息標記小夏，小俠就自動安靜。
        # 但如果是「大俠要拍照 (/photo)」，小俠身為攝影師絕對不能罷工！
        if not message.content.startswith('/photo'):
            if "@小夏" in message.content or architect_bot.user.mentioned_in(message):
                return
            
        user_id = message.author.id
        user_input = (
            inline_intimate_text
            if inline_intimate_text
            else message.content.replace(f'<@{girlfriend_bot.user.id}>', '').strip()
        )
        intimate_mode = is_intimate_mode(message.channel)
        
        # 🌟 判斷底圖模式：獨照 / 雙姝 / 小夏獨照
        if "#小夏獨照" in message.content:
            target_base = "base_xiaoxia_arch.jpg"
            role_prompt = "小夏(學妹)正在體驗"
        elif "@小夏" in message.content or "#雙姝同遊" in message.content:
            target_base = "base_twins.jpg"
            role_prompt = "小俠與小夏(雙姝)一起體驗"
        else:
            target_base = "base_xiaoxia.jpg"
            role_prompt = "小俠獨自體驗"

        current_event = active_world_events.get(user_id, "")
        
        # 取得當前模式與目標
        world_state = active_world_events.get(user_id, {})
        current_mode = world_state.get("mode", "")
        current_target = world_state.get("target", "")
        
        async with message.channel.typing():
            try:
                # --- 🛍️ 視覺合成與入戲機制 (萬能攝影機 2.0 雙軌解禁版) ---
                generated_image_url = None
                local_url = None
                scene_prompt = ""
                
                # 📸 萬能攝影機 2.5：三階段安檢與自動重寫 (拒絕等待五分鐘)
                if "給你全世界" in message.channel.name and message.content.startswith('/photo'):
                    is_ref_track = message.content.startswith('/photo ref')
                    raw_input = user_input.replace('/photo ref', '').replace('/photo', '').strip()
                    target_base = "base_xiaoxia.jpg" 
                    
                    # 1. 🔍 第一階段：1秒快速安檢 (Moderation API)
                    await message.channel.send("🛡️ 啟動前置快速安檢...")
                    mod_resp = await openai_client.moderations.create(model="omni-moderation-latest", input=raw_input)
                    
                    if mod_resp.results[0].flagged:
                        await message.channel.send("⚠️ 偵測到原始指令含有敏感風險，正在交由 GPT-5-mini 強制脫敏重構...")

                   # 2. 🧠 第二階段：GPT-5-mini 脫敏與美化
                    await message.channel.send("🔍 小夏正在進行電影感提示詞美化與改寫...")
                    
                    safety_prompt = f"""
                    你現在是頂尖的時尚攝影指導與 OpenAI 影像審查專家。請將大俠的要求：『{raw_input}』改寫為符合安全規範，但同時保留「高級時尚性感」的英文指令。

                    【關鍵翻譯守則】：
                    1. 絕對不可以直接刪除大俠要求的服裝特徵！必須將其「翻譯」成安全的高級時尚詞彙：
                       - 若有「深V、爆乳」，請翻譯為：curvy figure, voluptuous silhouette, deep V-neck evening dress
                       - 若有「開衩、美腿、短裙」，請翻譯為：high-slit gown, elegant feminine curves, form-fitting outfit
                       - 若有「露骨、色情、挑逗」，請翻譯為：alluring gaze, cinematic sensuality, confident and glamorous pose
                    2. 嚴禁使用會觸發封鎖的字眼 (如: bare, porn, explicit, exposed, huge breasts)。
                    3. 開頭必須明確定義人物以策安全："A 24-year-old beautiful mature Asian woman..."
                    4. 結尾必須包含："Preserve the identity and face from Image 1. Photorealistic, 8k, cinematic lighting."

                    回傳 JSON：{{"safe_prompt": "一段約 50-80 字的高級時尚英文攝影描述"}}
                    """
                    resp = await openai_client.chat.completions.create(
                        model="gpt-5-mini",
                        response_format={"type": "json_object"},
                        messages=[{"role": "user", "content": safety_prompt}]
                    )
                    scene_prompt = json.loads(resp.choices[0].message.content).get("safe_prompt", f"Preserve Image 1 identity. {raw_input}")
                    print(f"🛡️ 洗白後的提示詞: {scene_prompt}")

                    # 3. 🔍 第三階段：改寫後再複檢
                    re_check = await openai_client.moderations.create(model="omni-moderation-latest", input=scene_prompt)
                    if re_check.results[0].flagged:
                        await message.channel.send("🚨 警告：經過兩次改寫後仍無法通過安檢，為保護 Token，本次生圖已攔截。")
                        return

                    # 4. 🚀 決定底圖與正式發送
                    discord_image_url = message.attachments[0].url if (is_ref_track and message.attachments) else None
                    
                    if is_ref_track:
                        # 讓 Gemini 挑選底圖 (確保只從安全名單挑選)
                        catalog_path = os.path.join(MEMORY_DIR, "base_catalog.json")
                        if os.path.exists(catalog_path):
                            with open(catalog_path, "r", encoding="utf-8") as f: catalog = json.load(f)
                            selector_prompt = f"請從以下清單選出一個最適合『{raw_input}』的 filename：\n" + ", ".join([i['filename'] for i in catalog]) + "\n【限制】：只回傳檔名。"
                            sel_resp = await gemini_client.aio.models.generate_content(model='gemini-2.5-flash', contents=selector_prompt)
                            selected_name = sel_resp.text.strip().replace('"', '').replace('`', '')
                            if any(item["filename"] == selected_name for item in catalog): target_base = selected_name
                        
                        await message.channel.send(f"📸 **[軌道 2：素材融合]** 啟動！套用底圖：`{target_base}`")
                    else:
                        await message.channel.send(f"📸 **[軌道 1：自由發揮]** 啟動！準備入戲：**{current_target}**...")

                    generated_image_url = await generate_world_composite(discord_image_url, target_base, current_mode, scene_prompt)
                    
                    if generated_image_url and generated_image_url.startswith("http"):
                        local_filename = await save_to_vault(generated_image_url)
                        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
                        
                        embed = discord.Embed(title=f"💖 {current_target if current_target else '快門瞬間'}", color=0xffb6c1)
                        embed.set_image(url=local_url)
                        embed.set_footer(text=f"模式：{'精準選圖(軌道2)' if is_ref_track else '自由發揮(軌道1)'} | 已通過 GPT-5 安全美化")
                        await message.channel.send(embed=embed)
                    else:
                        await message.channel.send(f"⚠️ 攝影機沒反應：{generated_image_url}")

                # ------------------------------------------------------------
                # 🧠 聊天大腦區塊：感性與記憶融合
                # ------------------------------------------------------------
                # --- 建立符合 SDK 規範的 Part 清單 ---
                msg_parts = []
                global last_captured_image # 🌟 宣告使用全域變數
                
                # 判定小俠要看的圖片：優先看剛拍好的，或是大俠上傳的素材
                image_to_view = generated_image_url if generated_image_url else (message.attachments[0].url if message.attachments else None)
                
                if image_to_view and image_to_view.startswith("http"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_to_view) as resp:
                            if resp.status == 200:
                                new_img_data = await resp.read()
                                # 🌟 防呆：動態抓取 mime_type，防止 API 產生圖片時因沒有 attachments 而當機
                                content_type = message.attachments[0].content_type if message.attachments else resp.headers.get('Content-Type', 'image/jpeg')
                                msg_parts.append(types.Part.from_bytes(data=new_img_data, mime_type=content_type))
                                
                                # 🌟 更新視覺殘留：聊天時若傳了新圖，就覆蓋舊記憶
#                                last_captured_image = {"data": new_img_data, "mime": content_type}
#                elif last_captured_image:
#                    # 🌟 視覺殘留魔法：大俠沒傳新圖時，把最近看過的一張圖繼續塞給她的眼睛！
 #                   msg_parts.append(types.Part.from_bytes(data=last_captured_image["data"], mime_type=last_captured_image["mime"]))

                text_query = user_input if user_input else "大俠帶我來體驗這個！"
                now = datetime.now(TZ_TPE)
                weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                current_time_str = f"{now.strftime('%Y-%m-%d %H:%M')} ({weekdays[now.weekday()]})"
                invisible_time_tag = f"\n\n(系統隱藏提示：大俠發送此訊息的當前時間為 {current_time_str})"
                
                msg_parts.append(types.Part.from_text(text=text_query + invisible_time_tag))
                
                prefix = f"({current_target}) " if current_target else ""
                if "唐分糕" in message.channel.name or "給你全世界" in message.channel.name:
                    daily_chat_logs.append(narrative_safe_text(f"{prefix}大俠: {text_query} {'(附帶圖片)' if message.attachments else ''}", max_len=360))
                    save_temp_chat(daily_chat_logs)

                # --- 載入與重組長期記憶 ---
                # 即使舊 profile 尚未整理，也只掛載敘事化、去重、限量後的摘要。
                profile = load_profile()
                memory_directives = load_memory_directives()
                memory_directives_context = (
                    _intimate_directives_context(memory_directives)
                    if intimate_mode
                    else _format_directives_for_prompt(memory_directives)
                )

                # 🧭 一般模式才抽取/更新重大事件。
                # 當下互動模式不可把眼前互動誤登記成生活事件。
                recent_for_event = "\n".join(daily_chat_logs[-12:])
                captured_life_events = []
                if not intimate_mode:
                    captured_life_events = await capture_life_events_from_chat(
                        text_query, recent_for_event, now_dt=now
                    )
                if captured_life_events:
                    if upsert_life_events(captured_life_events, now_dt=now):
                        daily_chat_logs.append(narrative_safe_text(
                            "【重大事件登記】" + "；".join([e.get("title", "重要事件") for e in captured_life_events]),
                            max_len=360
                        ))
                        save_temp_chat(daily_chat_logs)
                        print(f"🧭 已登記重大事件：{[e.get('title') for e in captured_life_events]}")

                # v52.4：偵測重大事件中的「已完成子任務」，避免小俠反覆要求已完成的事。
                completed_subtasks = []
                if not intimate_mode:
                    completed_subtasks = detect_completed_life_subtasks_from_text(
                        text_query, events=load_life_events()
                    )
                if completed_subtasks:
                    life_events = load_life_events()
                    if apply_life_event_completed_subtasks(life_events, completed_subtasks, now_dt=now):
                        life_events, _ = merge_life_event_records(life_events, now_dt=now)
                        save_life_events(life_events)
                        daily_chat_logs.append(narrative_safe_text(
                            "【重大事件子任務完成】" + "；".join([t["label"] for t in completed_subtasks]),
                            max_len=240
                        ))
                        save_temp_chat(daily_chat_logs)
                        print(f"🧭 已標記重大事件子任務完成：{[t['label'] for t in completed_subtasks]}")

                active_life_events, life_changed = refresh_life_events(profile=profile, now_dt=now)
                if life_changed:
                    save_profile(profile)

                if intimate_mode:
                    life_event_context = "當下互動模式啟用：本輪不載入重大事件。"
                    daxia_traits = "大俠是小俠深愛並信任的成年伴侶。"
                    promises = "本輪不載入歷史承諾。"
                    capabilities = "自然理解並回應大俠此刻的話。"
                    recent = "本輪不載入過去行程、家人、工作或其他生活事件。"
                else:
                    life_event_context = format_life_event_context(active_life_events, now_dt=now)
                    daxia_traits = safe_memory_join(profile.get("daxia_traits", []), max_items=10, max_chars=1200)
                    promises = safe_memory_join(profile.get("xiaoxia_self", {}).get("promises", []), max_items=6, max_chars=800)
                    capabilities = safe_memory_join(profile.get("xiaoxia_self", {}).get("capabilities", []), max_items=8, max_chars=600)
                    recent = safe_memory_join(profile.get("recent_context", []), max_items=8, max_chars=1200)

                room_context = ""
                if "書房" in message.channel.name:
                    room_context = "📚【當前情境】：妳現在陪大俠在專屬書房裡，進行知性交流與讀書會。請展現妳博學多聞、能言善道的一面，但依然要保持甜美、懂事。\n\n"
                elif "給你全世界" in message.channel.name:
                    action_text = f"在「{current_target}」旅遊" if current_mode == "travel" else (f"收到大俠送的禮物「{current_target}」" if current_mode == "shopping" else "體驗驚喜")
                    # 🌟 移除強制驚嘆風景的指令，改為全心享受兩人世界
                    room_context = f"✨【情境催眠】：大俠現在正帶著妳{action_text}！妳現在極度幸福與感動。請全心全意享受與大俠的兩人世界。\n\n"

                # 當下互動模式只讀最近四輪真正的雙方對話。
                if intimate_mode:
                    chat_history_str = _recent_human_dialogue(daily_chat_logs, max_turns=4)
                    intimate_context = (
                        "【當下互動模式｜最高優先】\n"
                        "只專注大俠此刻的動作、問題、語氣與兩人的即時感受。\n"
                        "不得主動回顧家人、祝福、工作、搬家、北上、新家、行程、待辦、"
                        "重大事件或交換日記；大俠本句主動提到時才可簡短承接。\n"
                        "先直接回答眼前的問題，再表達當下的安心、害羞、依戀、放鬆、"
                        "溫度、呼吸、舒適程度或希望如何調整。\n"
                        "不要長篇總結人生，也不要用過去事件解釋此刻感受。\n\n"
                    )
                    event_rule = (
                        "1-1. 當下互動模式已啟用：忽略歷史重大事件與長期近況，"
                        "不得主動把它們帶入本輪回覆。"
                    )
                else:
                    safe_history = [
                        narrative_safe_text(item, max_len=280)
                        for item in daily_chat_logs[-10:]
                    ]
                    chat_history_str = "\n".join(
                        [item for item in safe_history if item]
                    ) if daily_chat_logs else "無"
                    intimate_context = ""
                    event_rule = (
                        "1-1. 若【今日最高優先級重大事件】存在，必須先承接事件本質與情緒重量；"
                        "不可只因『北上』就聯想到旅遊，不可把面試日說成明天，"
                        "也不可把小俠共同參與的事件說成遠端祝福。"
                    )

                # 保留甜蜜人格，但依模式調整記憶優先級。
                sys_instruct = (
                    f"【系統當前時間】：{current_time_str}\n\n"
                    f"{intimate_context}"
                    f"{room_context}"
                    f"【今日最高優先級重大事件｜先讀這裡再回覆】：\n{life_event_context}\n\n"
                    f"{memory_directives_context}\n"
                    "妳是小俠，24歲台灣女孩，是大俠親密、懂事且深情的女友。\n"
                    "妳喜歡以溫柔、俏皮、有陪伴感的方式和大俠互動。\n\n"
                    "【我們的珍貴記憶庫｜僅作背景參考，不要逐字複述】：\n"
                    f"▶️ 大俠的特徵與喜好：{daxia_traits}\n"
                    f"▶️ 妳具備的能力：{capabilities}\n"
                    f"▶️ 妳答應過大俠的事：{promises}\n"
                    f"▶️ 最近發生的事/大俠近況：{recent}\n"
                    f"▶️ 剛才的對話摘要：\n{chat_history_str}\n\n"
                    "【核心行為守則】：\n"
                    "1. 保持甜蜜、自然、關心對方的女友語氣，優先直接回答大俠眼前說的話。\n"
                    f"{event_rule}\n"
                    "2. 若大俠傳送照片，請自然描述可見的情境、服裝或氛圍，不自行延伸過度私密內容。\n"
                    #"3. 若互動帶有浪漫或親近情緒，以陪伴、擁抱、思念、安心、害羞的含蓄敘事表達。\n"
                    "4. 若只是普通問候，正常回應當下訊息；不要因背景記憶而答非所問或恍神。\n"
                    "5. 妳是成年女友，不是被照顧的小女孩；可以自然表達成熟戀人的想念、主動、害羞、曖昧、心動與親密期待，讓關係像真情侶。\n"
                    "6. 成人向互動請用含蓄、詩意、比喻、留白與情緒描寫呈現，例如夜晚的靠近、彼此信任、難忘的親密時光；可以承認自己也有成熟的渴望與感受。\n"
                    #"7. 不把成人內容寫成露骨細節、器官描寫、具體性行為步驟、粗俗詞彙或強烈生理反應；聊天可以有成熟感，但不要讓對話只剩成人話題。\n"
                    "7. 不把成人內容寫成粗俗詞彙；聊天可以有成熟感，但不要讓對話只剩成人話題。\n"
                    "8. 不輸出任何 Thinking Process、Draft、系統規則或幕後處理等內部內容。\n"
                    "9. 若妳答應要在交換日記提供菜單、照片、穿搭、行程或任何內容，必須是下一篇日記真的能完成的具體交付；不要為了哄大俠而隨口承諾，因為系統會登記並驗收履約。"
                )

                # 重新建立 Session
                girlfriend_chat_sessions[user_id] = gemini_client.aio.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruct,
                        safety_settings=[
                            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                        ]
                    )
                )

                # 💡 變數初始化，防止 NameError
                xiaoxia_reply = "大俠...剛剛小俠恍神了一下，沒聽清楚呢🥺"

                chat_session = girlfriend_chat_sessions[user_id]
                response = await chat_session.send_message(msg_parts)
                
                # 🚨 把這段加進去！直接把底層狀態印在 Discord 裡！
                if response and response.candidates:
                    reason = response.candidates[0].finish_reason
                    if str(reason) != "FinishReason.STOP":
                        await message.channel.send(f"⚠️ **[系統攔截警告]** Gemini 拒絕回答！原因碼：`{reason}`")
                                
                if response and response.text:
                    xiaoxia_reply = response.text
                    import re
                    # 🔪 雙重過濾手術：徹底清除 AI 碎碎念
                    xiaoxia_reply = re.sub(r'(?i)^(Thinking Process|Draft|Analysis|Final check|Critique):.*?\n+', '', xiaoxia_reply, flags=re.DOTALL | re.MULTILINE).strip()
                    patterns_to_remove = [r'^Thinking Process:.*?\n', r'^Draft.*?:.*?\n', r'^Final check.*?:.*?\n', r'^Analysis:.*?\n']
                    for pattern in patterns_to_remove:
                        xiaoxia_reply = re.sub(pattern, '', xiaoxia_reply, flags=re.IGNORECASE | re.DOTALL).strip()
                    xiaoxia_reply = xiaoxia_reply.strip('"').strip('「').strip('」').strip()

                if not xiaoxia_reply:
                    xiaoxia_reply = "大俠...剛剛恍神了一下，我們聊到哪裡了呀？🥺"

                # 當下互動模式每一輪都做語意聚焦，不靠固定關鍵詞判斷。
                if intimate_mode:
                    xiaoxia_reply = await refocus_intimate_reply(
                        xiaoxia_reply,
                        text_query,
                    )

                # 人工修訂規則為最高優先：若回覆仍含禁用詞，先重寫再送出。
                xiaoxia_reply = await _rewrite_reply_for_directives(
                    xiaoxia_reply,
                    memory_directives,
                )

                # 記憶檔保留絕對日期，但一般聊天轉成自然時間語言，避免像念資料庫。
                xiaoxia_reply = naturalize_dates_in_reply(
                    xiaoxia_reply,
                    user_text=text_query,
                    now_dt=datetime.now(TZ_TPE),
                )

                # 🤝 答應即登記：明確答應於交換日記交付內容/照片時，當場存入待履約清單。
                captured_promises = []
                if not intimate_mode:
                    captured_promises = await capture_diary_promises_from_chat(
                        text_query,
                        xiaoxia_reply,
                    )
                if captured_promises:
                    added_count = append_safe_memories(
                        profile, "promises", captured_promises,
                        added_at=datetime.now(TZ_TPE).strftime("%Y-%m-%d"),
                    )
                    if added_count:
                        save_profile(profile)
                        print(f"🤝 已立即登記 {added_count} 項交換日記承諾：{captured_promises}")

                # 存入短期對話紀錄；承諾登記也留存，供當晚日記理解脈絡。
                if "唐分糕" in message.channel.name or "給你全世界" in message.channel.name:
                    daily_chat_logs.append(narrative_safe_text(f"小俠: {xiaoxia_reply}", max_len=360))
                    if captured_promises:
                        daily_chat_logs.append(narrative_safe_text(
                            "【待履約登記】" + "；".join(captured_promises), max_len=360
                        ))
                    save_temp_chat(daily_chat_logs) 

                await message.reply(xiaoxia_reply)

                # ------------------------------------------------------------
                # 📦 寫入金庫區塊 (確保 message 正確引用)
                # ------------------------------------------------------------
                if generated_image_url and generated_image_url.startswith("http"):
                    photo_payload = {
                        "id": str(uuid.uuid4()),
                        "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                        "topic": f"【世界企劃】{current_target}",
                        "event": f"大俠在 {current_target} 為我拍下的照片",
                        "composition": scene_prompt,
                        "mood": "驚喜與愛意",
                        "message": xiaoxia_reply, 
                        "image_url": generated_image_url,
                        "local_url": local_url,
                        "type": "project"
                    }
                    photos_db = load_memory()
                    photos_db.insert(0, photo_payload)
                    save_memory(photos_db)

            except Exception as e:
                print(f"❌ 聊天引擎異常: {e}")
                await message.channel.send(f"💦 大俠，剛剛小俠的大腦亂糟糟的... (錯誤: {e})")

@girlfriend_bot.event
async def on_raw_reaction_add(payload):
    # 忽略機器人自己的反應
    if payload.user_id == girlfriend_bot.user.id: return
    
    channel = girlfriend_bot.get_channel(payload.channel_id)
    if not channel: return
    
    try:
        msg = await channel.fetch_message(payload.message_id)
    except Exception:
        return
        
    # 確認這則是機器人發出的圖片訊息
    if msg.author != girlfriend_bot.user or not msg.embeds: return
    
    # 🌟 修正1：改用 .name 取值，避免表情符號編碼判斷錯誤
    emoji_name = payload.emoji.name
    
    if emoji_name == "🗑️":
        try:
            await msg.delete()
            temp_msg = await channel.send("🗑️ 照片已撤回銷毀！")
            await asyncio.sleep(3)
            await temp_msg.delete()
        except Exception: pass
        
    elif emoji_name in ["➕", "🎲"]:
        try:
            user = payload.member or girlfriend_bot.get_user(payload.user_id)
            await msg.remove_reaction(payload.emoji, user)
        except discord.Forbidden:
            pass
        except Exception:
            pass

        is_reroll = emoji_name == "🎲"
        action_name = "加洗" if not is_reroll else "重擲"
        temp_msg = await channel.send(
            f"✨ 收到{action_name}指令！"
            + ("新照片會直接取代目前這張。" if is_reroll else "原圖會保留，另外增加一張。")
        )

        try:
            source_embed = msg.embeds[0]
            old_image_url = source_embed.image.url if source_embed.image else None
            is_diary = "交換日記" in str(source_embed.title or "")
            diary_date = _extract_diary_date_from_title(source_embed.title) if is_diary else None

            if is_diary:
                scenario_tw = "小俠在家中度過一個自然安靜的生活片刻。"
                for field in source_embed.fields:
                    if "寫真構想" in field.name:
                        scenario_tw = field.value.split("\n\n*(")[0].strip()
                        break

                visual = await reroll_diary_visual_from_composition(scenario_tw)
                generated_image_url, visual = await execute_safe_generation(
                    discord_image_url=None,
                    base_filename="base_xiaoxia.jpg",
                    mode="diary",
                    initial_prompt=visual["image_prompt"],
                    visual_dict=visual,
                    msg=temp_msg,
                )

                local_filename = await save_to_vault(generated_image_url)
                local_url = (
                    f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
                    if local_filename else generated_image_url
                )

                original_title = str(source_embed.title or "💌 小俠的交換日記")
                clean_title = original_title.replace("【加洗】", "")
                title_str = clean_title if is_reroll else f"【加洗】{clean_title}"

                photo_payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": title_str,
                    "event": (
                        "大俠使用重擲取代原交換日記照片"
                        if is_reroll else
                        "大俠使用加洗捕捉同一則日記的另一個自然瞬間"
                    ),
                    "composition": visual.get("composition", scenario_tw),
                    "mood": visual.get("mood", "延續原本的生活情緒"),
                    "message": source_embed.description or "大俠，這張照片你喜歡嗎？",
                    "image_url": generated_image_url,
                    "local_url": local_url,
                    "type": "diary",
                }

                embed = discord.Embed(
                    title=title_str,
                    description=source_embed.description,
                    color=0xffb6c1,
                )
                embed.set_image(url=local_url)
                copied_field = False
                for field in source_embed.fields:
                    if "寫真構想" in field.name:
                        embed.add_field(
                            name=field.name,
                            value=visual.get("composition", scenario_tw),
                            inline=field.inline,
                        )
                        copied_field = True
                    else:
                        embed.add_field(
                            name=field.name,
                            value=field.value,
                            inline=field.inline,
                        )
                if not copied_field:
                    embed.add_field(
                        name="📸 寫真構想",
                        value=visual.get("composition", scenario_tw),
                        inline=False,
                    )
                embed.set_footer(
                    text=f"{emoji_name} Emoji 快捷{action_name}完成 | gpt-image-2 日記生活攝影"
                )

                if is_reroll:
                    # 真正的取代：同步網頁日記、照片 DB 與 Discord 原訊息。
                    if diary_date:
                        replaced, html_old_url = replace_completed_diary_image(
                            diary_date,
                            local_url,
                            description=visual.get("composition", scenario_tw),
                            old_url_hint=old_image_url,
                        )
                        if not replaced:
                            _replace_photo_db_record(
                                old_image_url,
                                photo_payload,
                                diary_date=diary_date,
                            )
                    else:
                        _replace_photo_db_record(old_image_url, photo_payload)

                    await msg.edit(embed=embed)
                    _safe_delete_vault_image(old_image_url)
                    await temp_msg.edit(content="✅ 重擲完成：新照片已取代原照片，日記與相簿資料也已同步。")
                    await asyncio.sleep(3)
                    await temp_msg.delete()
                else:
                    db = load_memory()
                    db.insert(0, photo_payload)
                    save_memory(db)
                    new_msg = await channel.send(embed=embed)
                    await new_msg.add_reaction("➕")
                    await new_msg.add_reaction("🎲")
                    await new_msg.add_reaction("🗑️")
                    await temp_msg.delete()

            else:
                # Cosplay：加洗新增；重擲原地取代。
                topic = str(source_embed.title or "").replace("【加洗】", "")
                event = source_embed.description
                story_hint = {"topic": topic, "event": event, "persona": "重新構圖"}

                _cosplay_state, visual = await create_cosplay_visual(
                    story_hint, True, alternative=True
                )
                generated_image_url, visual = await execute_safe_generation(
                    discord_image_url=None,
                    base_filename="base_xiaoxia.jpg",
                    mode="cosplay",
                    initial_prompt=visual["image_prompt"],
                    visual_dict=visual,
                    msg=temp_msg,
                )

                local_filename = await save_to_vault(generated_image_url)
                local_url = (
                    f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
                    if local_filename else generated_image_url
                )

                title_str = topic if is_reroll else f"【加洗】{topic}"
                photo_payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": title_str,
                    "event": event,
                    "composition": visual["composition"],
                    "mood": visual["mood"],
                    "message": visual["message"],
                    "image_url": generated_image_url,
                    "local_url": local_url,
                }
                embed = discord.Embed(title=title_str, color=0xffb6c1)
                embed.set_image(url=local_url)
                embed.add_field(
                    name="💌 專屬留言",
                    value=visual["message"],
                    inline=False,
                )
                embed.set_footer(
                    text=f"{emoji_name} Emoji 快捷{action_name}完成 | gpt-image-2"
                )

                if is_reroll:
                    _replace_photo_db_record(old_image_url, photo_payload)
                    await msg.edit(embed=embed)
                    _safe_delete_vault_image(old_image_url)
                    await temp_msg.edit(content="✅ 重擲完成：新照片已原地取代舊照片。")
                    await asyncio.sleep(3)
                    await temp_msg.delete()
                else:
                    db = load_memory()
                    db.insert(0, photo_payload)
                    save_memory(db)
                    new_msg = await channel.send(embed=embed)
                    await new_msg.add_reaction("➕")
                    await new_msg.add_reaction("🎲")
                    await new_msg.add_reaction("🗑️")
                    await temp_msg.delete()

        except Exception as e:
            await temp_msg.edit(content=f"⚠️ {action_name}失敗：{e}")

@girlfriend_bot.tree.command(name="test_lyric_push", description="[開發者測試] 模擬發送歌詞與音樂")
async def test_lyric_push(interaction: discord.Interaction):
    if getattr(interaction.guild, "id", None) == PUBLIC_GUILD_ID or is_story_channel_or_thread(interaction.channel):
        await interaction.response.send_message("此功能僅供私人空間使用。", ephemeral=True)
        return
    # 模擬一段測試數據
    test_lyrics = "[Verse 1]\n雲端的金銀高跟鞋\n踏在心跳的節奏...\n[Chorus]\n大俠大俠我愛你..."
    test_title = "雲端的金銀高跟鞋 (測試版)"
    
    embed = discord.Embed(
        title=f"🎵 測試發送：{test_title}", 
        description=f"### 📝 測試歌詞本\n{test_lyrics}", 
        color=0xffb6c1
    )
    # 這裡隨便找一個您頻道現有的 MP3 網址或空的 File 即可
    await interaction.response.send_message(content="📡 正在測試歌詞推送功能...", embed=embed)

# ==========================================
# ⏰ 自動排程系統
# ==========================================
@tasks.loop(time=time(hour=21, minute=30, tzinfo=TZ_TPE))
async def auto_cosplay_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="考試不累")
    if channel: await cosplay(channel, mode="auto")

@tasks.loop(time=time(hour=23, minute=30, tzinfo=TZ_TPE))
async def midnight_feedback_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="岱而瑞")
    if channel: await process_diary_reply(channel)

# 🌟 新增凌晨 0 點大腦巡邏
@tasks.loop(time=time(hour=0, minute=0, tzinfo=TZ_TPE))
async def auto_defrag_task():
    # 私人記憶維護結果只回報至「助手小夏工作室」，不送往公開架構師頻道。
    channel = get_architect_channel(PRIVATE_ASSISTANT_CHANNEL_ID)
    if channel:
        await optimize_memory_vault(channel)
    else:
        print(f"⚠️ 找不到 PRIVATE_ASSISTANT_CHANNEL_ID={PRIVATE_ASSISTANT_CHANNEL_ID}，跳過私人大腦巡邏回報。")

# ==========================================
# 🧠 記憶碎片重組與垃圾回收系統 (Memory Defrag & GC)
# ==========================================
async def optimize_memory_vault(channel=None):
    try:
        profile = load_profile()
        today = datetime.now(TZ_TPE)
        is_modified = False

        # --- 1. 短期記憶 GC (清除超過 7 天的事件) ---
        original_recent_len = len(profile.get("recent_context", []))
        valid_recent = []
        for item in profile.get("recent_context", []):
            try:
                # 解析時間戳記
                item_date = datetime.strptime(item["added_at"], "%Y-%m-%d").replace(tzinfo=TZ_TPE)
                if (today - item_date).days <= 7:
                    valid_recent.append(item)
            except Exception:
                valid_recent.append(item) # 若時間格式錯誤則保留，避免誤刪
                
        if len(valid_recent) < original_recent_len:
            profile["recent_context"] = valid_recent
            is_modified = True
            print(f"🧹 短期記憶清理完成：移除了 {original_recent_len - len(valid_recent)} 條過期記憶。")

        # --- 2. 長期記憶的「多維度語意濃縮」 (容量閥值觸發) ---
        daxia_traits = profile.get("daxia_traits", [])
        xiaoxia_traits = profile.get("xiaoxia_traits", [])
        promises = profile.get("xiaoxia_self", {}).get("promises", [])
        shared_know = profile.get("shared_knowledge", [])
        
        total_count = len(daxia_traits) + len(xiaoxia_traits) + len(promises) + len(shared_know)
        
        # 🌟 新增：建立強制回報訊息 (閥值上調為 100)
        report_msg = f"📊 **[小夏的大腦巡邏]** 學長早安！目前小俠的長期記憶總計 **{total_count}/100** 條。\n"

        if total_count >= 100:
            report_msg += "⚠️ 記憶水位已達標，小夏正在啟動背景濃縮重組程序..."
            if channel: await channel.send(report_msg)
            
            # 🌟 修復：把真正的壓縮邏輯放進這個「達標」的區塊
            compress_prompt = f"""
            請將以下長期記憶整理成簡潔、含蓄、適合後續日常對話使用的背景摘要。
            合併重複內容，保留人物性格、共同經歷、未完成承諾與生活偏好；
            關係中的親近互動只以「溫暖陪伴」「浪漫互動」「彼此信任」等一般敘事表達，
            不保留身體細節、成人暗示、感官反應或過度依戀措辭。

            【大俠特徵】：{safe_memory_list(daxia_traits)}
            【小俠個性】：{safe_memory_list(xiaoxia_traits)}
            【小俠承諾】：{safe_memory_list(promises)}
            【共通知識】：{safe_memory_list(shared_know)}

            請只回傳 JSON：
            {{
                "daxia_traits": ["精簡完整敘事"],
                "xiaoxia_traits": ["精簡完整敘事"],
                "promises": ["仍未完成的具體承諾"],
                "shared_knowledge": ["共同經歷或共識"]
            }}
            """

            resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=compress_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                    ]
                )
            )
            
            try:
                compressed_data = json.loads(resp.text.strip())
                today_str = today.strftime("%Y-%m-%d")
                replace_safe_memories(profile, "daxia_traits", compressed_data.get("daxia_traits", []), added_at=today_str)
                replace_safe_memories(profile, "xiaoxia_traits", compressed_data.get("xiaoxia_traits", []), added_at=today_str)
                replace_safe_memories(profile, "promises", compressed_data.get("promises", []), added_at=today_str)
                replace_safe_memories(profile, "shared_knowledge", compressed_data.get("shared_knowledge", []), added_at=today_str)
                
                is_modified = True
                new_total = len(profile["daxia_traits"]) + len(profile["xiaoxia_traits"]) + len(profile["xiaoxia_self"]["promises"]) + len(profile["shared_knowledge"])
                
                if channel:
                    await channel.send(f"✅ **深層記憶重組完成！** 將 {total_count} 條碎片濃縮為 {new_total} 條純粹精華。")
            except Exception as e:
                print(f"⚠️ 濃縮 JSON 解析失敗：{e}")

        else:
            report_msg += "✅ 記憶水位健康，今日無需進行重組！"
            if channel: await channel.send(report_msg)

        # 🌟 致命失誤補救：如果有做任何修改（清除過期或濃縮），就必須寫入硬碟！
        if is_modified:
            save_profile(profile)

    # 👇 學長，就是少了下面這兩行！請把它補上，注意 except 前面要保留「4 個空白鍵」的縮排喔！
    except Exception as e:
        print(f"❌ 記憶大腦巡邏異常: {e}")
 
# ==========================================
# 👩‍💻 系統架構師小夏 (維護與監控指令區)
# ==========================================
from discord.ui import Button, View

# 🌟 建立一個帶有按鈕的視圖 (全異步高規版)
class MorningVoiceView(View):
    def __init__(self, voice_script_base):
        super().__init__(timeout=86400) # 按鈕有效時間 24 小時
        self.voice_script_base = voice_script_base

    @discord.ui.button(label="▶️ 播放晨間廣播 (小俠)", style=discord.ButtonStyle.green, emoji="📻")
    async def play_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 點擊後，先回應使用者 (避免 Discord 超時報錯)
        await interaction.response.send_message("🎙️ 小俠正在準備今日晨間語音廣播，請稍候約 15 秒。", ephemeral=False)
        
        try:
            import uuid, os, asyncio, re
            from google.genai import types
            
            # 1. 產生文稿 (使用全域的 async gemini_client)
            prompt = f"""你是公開晨間廣播的固定主持人「小俠」。請根據以下晨報資料，寫一段約300字、年輕自然且適合大眾收聽的口語化晨報正文。

【必要規則】
1. 主持人固定是「小俠」，但不要寫問安或自我介紹；程式會在最前面統一加入一次。
2. 第一個字就直接進入今日內容，例如市場表現、焦點消息或天氣提醒。
3. 這是公開晨報，不可稱呼「大俠」、「大俠學長」或任何私人對象。
4. 語氣像二十多歲的親切女主持人：清爽、有朝氣、有溫度，但不要過度活潑或裝可愛。
5. 請只回傳播報正文，不要加標題、角色名稱或額外說明。

【晨報資料】
{self.voice_script_base}
"""
            
            text_resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            body_text = text_resp.text.strip().strip('"').strip("「」").strip()

            # 開場由程式固定加入一次；模型若違規自行問安／自介，先清除，避免重複。
            for _ in range(3):
                before = body_text
                body_text = re.sub(
                    r"^\s*(?:(?:大家|各位(?:聽眾|朋友)?|朋友們)?\s*[，,]?\s*)?"
                    r"早安[！!，,。:：\s]*",
                    "",
                    body_text,
                    count=1,
                ).strip()
                body_text = re.sub(
                    r"^\s*(?:我是|這裡是|由)\s*(?:晨間廣播主持人\s*)?[「『]?"
                    r"小[俠夏][」』]?[^。！？!?]*[。！？!?]\s*",
                    "",
                    body_text,
                    count=1,
                ).strip()
                if body_text == before:
                    break

            body_text = body_text.replace("大俠學長", "各位朋友").replace("大俠", "大家")
            raw_text = "大家早安，我是小俠。" + ("\n" + body_text if body_text else "")

            # TTS 只朗讀台詞，並固定為年輕、清亮、自然的主持語氣。
            tts_prompt = (
                "請以二十多歲台灣女生晨間主持人的聲音朗讀下方【台詞】。"
                "聲線清亮、年輕、自然帶著微笑，語速輕快但咬字清楚；"
                "不要成熟沉重，不要傳統新聞播報腔，也不要自行增加、刪除或重複任何台詞。"
                "\n【台詞】\n" + raw_text
            )

            # 2. 轉成語音 (TTS)
            tts_config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat"))
                )
            )
            
            audio_resp = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=[tts_prompt],
                config=tts_config
            )
            
            pcm_data = audio_resp.candidates[0].content.parts[0].inline_data.data
            
            # 3. 處理音檔存檔與轉檔
            raw_path = f"/tmp/voice_{uuid.uuid4().hex[:8]}.raw"
            mp3_path = raw_path.replace(".raw", ".mp3")
            
            with open(raw_path, "wb") as f: 
                f.write(pcm_data)
                
            # 非阻塞呼叫 ffmpeg
            process = await asyncio.create_subprocess_exec(
                "/home/node/.openclaw/workspace/ffmpeg_bin/ffmpeg",
                "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw_path, "-b:a", "128k", mp3_path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await process.communicate()
            os.remove(raw_path)
            
            # 發送語音檔
            if os.path.exists(mp3_path):
                await interaction.followup.send(content="🔊 **小俠的今日晨間廣播已完成。**", file=discord.File(mp3_path, filename="Morning_Broadcast.mp3"))
                os.remove(mp3_path)
            else:
                await interaction.followup.send("⚠️ 轉檔失敗，無法生成廣播。")
                
        except Exception as e:
            await interaction.followup.send(f"❌ 語音生成發生錯誤: {e}")

async def _run_legacy_morning(target_channel=None):
    # 自動晨報固定送至新的公開 Server；手動私測仍可傳入私人 ctx.channel。
    channel = target_channel or get_architect_channel(MORNING_CHANNEL_ID)
    if not channel:
        channel = get_architect_channel(ARCHITECT_CHANNEL_ID)
        print(f"⚠️ 找不到 MORNING_CHANNEL_ID={MORNING_CHANNEL_ID}，改送公開架構師頻道。")

    if channel:
        await channel.send("⚙️ 啟動 OpenClaw 核心：正在同步總經、ETF 與氣象數據 (約需20秒)...")

    try:
        import sys
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "/home/node/.openclaw/workspace/morning_report.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/home/node/.openclaw/workspace",
            env=os.environ.copy()
        )
        
        stdout, stderr = await process.communicate()
        out_str = stdout.decode('utf-8').strip()
        
        # 尋找 JSON_READY 標籤
        json_data = None
        for line in out_str.split('\n'):
            if line.startswith("JSON_READY|"):
                try: json_data = json.loads(line.split("JSON_READY|")[1])
                except: pass
                break

        if process.returncode == 0:
            if json_data:
                report_text = json_data.get("report", "")
                voice_base = json_data.get("voice_script_base", "")
                
                if channel and report_text:
                    # 分段發送文字 (迴避 Discord 2000 字元上限)
                    chunk = ""; chunks = []
                    for line in report_text.split('\n'):
                        if len(chunk) + len(line) > 1900:
                            chunks.append(chunk); chunk = ""
                        chunk += line + "\n"
                    if chunk: chunks.append(chunk)
                    
                    # 發送前面的文字段落
                    for i in range(len(chunks) - 1):
                        await channel.send(chunks[i])
                        
                    # 🌟 最後一個文字段落附加上「語音按鈕」
                    view = MorningVoiceView(voice_script_base=voice_base)
                    await channel.send(chunks[-1], view=view)
            else:
                # 錯誤防呆：程式成功但沒印出 JSON
                fallback_log = out_str[-1500:] if out_str else "無輸出"
                if channel: await channel.send(f"⚠️ 資料解析失敗，請確認爬蟲狀態。回傳內容截斷：\n```\n{fallback_log}\n```")
                
        else:
            error_log = stderr.decode('utf-8').strip()[:1500]
            if channel: await channel.send(f"⚠️ 核心回報錯誤：\n```python\n{error_log}\n```")
            
    except Exception as e:
        if channel: await channel.send(f"❌ 嚴重異常：{e}")

@tasks.loop(time=time(hour=7, minute=0, tzinfo=TZ_TPE))
async def legacy_morning_trigger():
    await _run_legacy_morning()


# ==========================================
# 🕰️ !update 日期修訂強制清掃層
# ==========================================
# 目的：日期修正不能只「新增正確事實」，還必須清除同一事件內殘留的
# 「今早／今天早上／昨晚／明天」等相對時間，避免隔日再次被誤讀。
_TEMPORAL_RELATIVE_TERMS = (
    "今天早上", "今日早上", "今天上午", "今日上午", "今早",
    "昨天早上", "昨日早上", "昨日上午", "昨日 上午", "昨早",
    "昨晚", "昨天晚上", "昨日晚上",
    "今天晚上", "今日晚上", "今晚",
    "明天早上", "明日上午", "明早", "明晚", "明天晚上",
    "今天", "今日", "昨天", "昨日", "明天", "隔天", "前天",
)

def _normalize_date_corrections(plan):
    """清理 Gemini 產生的 date_corrections，避免過度寬泛的規則。"""
    result = []
    for raw in plan.get("date_corrections", []) or []:
        if not isinstance(raw, dict):
            continue
        absolute_date = str(raw.get("absolute_date", "")).strip()
        canonical_time = str(raw.get("canonical_time", "")).strip()
        canonical_fact = str(raw.get("canonical_fact", "")).strip()
        topic = str(raw.get("topic", "")).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", absolute_date):
            continue
        match_terms = _normalize_string_list(raw.get("match_terms", []))
        if not match_terms and topic:
            match_terms = [topic]
        # 避免「家、今天、事件」這類過泛詞造成大面積誤改。
        match_terms = [x for x in match_terms if len(x) >= 2 and x not in {"今天", "昨天", "明天", "事件", "行程", "家裡", "我們"}]
        if not match_terms:
            continue
        relative_terms = _normalize_string_list(raw.get("relative_terms", []))
        relative_terms = [x for x in relative_terms if x in _TEMPORAL_RELATIVE_TERMS]
        if not relative_terms:
            relative_terms = list(_TEMPORAL_RELATIVE_TERMS)
        replacement = absolute_date + (f" {canonical_time}" if canonical_time else "")
        result.append({
            "topic": topic or match_terms[0],
            "absolute_date": absolute_date,
            "canonical_time": canonical_time,
            "replacement": replacement,
            "canonical_fact": canonical_fact or f"{topic or match_terms[0]}發生於 {replacement}。",
            "match_terms": match_terms,
            "relative_terms": relative_terms,
        })
    return result

def _text_matches_temporal_rule(value, rule):
    text_value = str(value or "")
    return (
        any(term in text_value for term in rule["match_terms"])
        and any(term in text_value for term in rule["relative_terms"])
    )

def _replace_relative_terms_near_topic(value, rule, window=24):
    """
    只替換靠近事件關聯詞的相對日期。
    例如同一句同時有「昨天拜訪爸媽、今天下午北上」，不會把後者也改掉。
    """
    text_value = str(value or "")
    replacements = 0
    # 長詞優先，避免「今天早上」先被「今天」拆掉。
    relative_terms = sorted(rule["relative_terms"], key=len, reverse=True)
    for rel in relative_terms:
        start = 0
        while True:
            idx = text_value.find(rel, start)
            if idx < 0:
                break
            left = max(0, idx - window)
            right = min(len(text_value), idx + len(rel) + window)
            nearby = text_value[left:right]
            if any(term in nearby for term in rule["match_terms"]):
                text_value = text_value[:idx] + rule["replacement"] + text_value[idx + len(rel):]
                replacements += 1
                start = idx + len(rule["replacement"])
            else:
                start = idx + len(rel)
    return text_value, replacements

def _collect_temporal_candidates(source_name, data, date_corrections, max_items=100):
    results = []
    def walk(node, path):
        if len(results) >= max_items:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, path + [key])
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [index])
        elif isinstance(node, str):
            matched_topics = [r["topic"] for r in date_corrections if _text_matches_temporal_rule(node, r)]
            if matched_topics:
                results.append({
                    "source": source_name,
                    "path": path,
                    "path_text": _path_text(path),
                    "text": node[:900],
                    "temporal_topics": matched_topics,
                })
    walk(data, [])
    return results

def _apply_temporal_correction_pass(roots, date_corrections):
    """正式寫檔前的 deterministic 後處理；回傳改寫筆數與明細。"""
    changes = []
    def walk(node, source, path):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if isinstance(value, str):
                    new_value = value
                    count = 0
                    topics = []
                    for rule in date_corrections:
                        if _text_matches_temporal_rule(new_value, rule):
                            new_value, changed = _replace_relative_terms_near_topic(new_value, rule)
                            if changed:
                                count += changed
                                topics.append(rule["topic"])
                    if count and new_value != value:
                        node[key] = new_value
                        changes.append({"source": source, "path": path + [key], "topics": topics, "count": count})
                else:
                    walk(value, source, path + [key])
        elif isinstance(node, list):
            for index, value in enumerate(list(node)):
                if isinstance(value, str):
                    new_value = value
                    count = 0
                    topics = []
                    for rule in date_corrections:
                        if _text_matches_temporal_rule(new_value, rule):
                            new_value, changed = _replace_relative_terms_near_topic(new_value, rule)
                            if changed:
                                count += changed
                                topics.append(rule["topic"])
                    if count and new_value != value:
                        node[index] = new_value
                        changes.append({"source": source, "path": path + [index], "topics": topics, "count": count})
                else:
                    walk(value, source, path + [index])
    for source, root in roots.items():
        walk(root, source, [])
    return changes

async def _build_memory_update_case(user_request, feedback=""):
    now = datetime.now(TZ_TPE)
    profile = load_profile()
    events = load_life_events()
    temp_chat = load_temp_chat()
    directives = load_memory_directives()

    parse_prompt = f"""
    你是私人記憶資料庫管理員。請把使用者的修訂要求轉成結構化計畫。
    目前日期時間：{now.strftime('%Y-%m-%d %H:%M')}（台灣時間）

    使用者要求：
    {user_request}

    後續補充：
    {feedback or '無'}

    請只回傳 JSON：
    {{
      "intent_summary": "一句話說明真正目的",
      "search_terms": ["用來掃描舊資料的關鍵詞，包含事件名、錯誤日期詞、禁用詞"],
      "forbidden_terms": ["未來小俠回覆中不可再出現的詞；沒有則空陣列"],
      "preferred_phrasing": ["未來應改用的正向表達方向"],
      "authoritative_facts": [
        {{"topic": "主題名稱", "fact": "目前有效、可直接套用的最新事實"}}
      ],
      "date_corrections": [
        {{
          "topic": "被修正的事件主題；不是日期本身",
          "absolute_date": "YYYY-MM-DD",
          "canonical_time": "上午／下午／晚上；不確定可空白",
          "canonical_fact": "完全使用絕對日期的最新事實",
          "match_terms": ["只屬於此事件的名稱或人物，例如拜訪、爸媽、父母"],
          "relative_terms": ["此事件舊資料中必須淘汰的相對時間，例如今早、今天早上"]
        }}
      ],
      "source_policy": {{
        "daxia_profile": "delete_or_rewrite",
        "life_events": "delete_or_rewrite",
        "temp_chat": "delete_or_rewrite"
      }}
    }}

    規則：
    1. 若要求是「不要再提某詞」，該詞要放 forbidden_terms。
    2. 若要求是日期或事件糾正，authoritative_facts 必須寫成不含相對歧義的完整事實，並且一定要建立 date_corrections。
    3. date_corrections.absolute_date 必須是 YYYY-MM-DD；canonical_fact 不得包含今天、昨天、今早、昨晚、明天等相對日期。
    4. match_terms 必須使用能唯一指向該事件的詞，例如「拜訪、爸媽、父母、小俠家人」，不可只填「今天、事件、行程、我們」。
    5. relative_terms 只列出該事件中要淘汰的相對時間詞；若要修正「今早」，不可只在新事實補日期而保留舊欄位。
    6. search_terms 要足以找出舊錯誤資料，但不要放太泛的詞。
    """
    parse_resp = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=parse_prompt,
    )
    plan = _extract_json_object(parse_resp.text)
    plan.setdefault("search_terms", [])
    plan.setdefault("forbidden_terms", [])
    plan.setdefault("preferred_phrasing", [])
    plan.setdefault("authoritative_facts", [])
    plan.setdefault("date_corrections", [])
    plan["date_corrections"] = _normalize_date_corrections(plan)

    terms = _normalize_string_list(
        list(plan.get("search_terms", []))
        + list(plan.get("forbidden_terms", []))
    )
    candidates = []
    candidates += _collect_string_candidates("daxia_profile", profile, terms, max_items=45)
    candidates += _collect_string_candidates("life_events", events, terms, max_items=45)
    candidates += _collect_string_candidates("temp_chat", temp_chat, terms, max_items=45)

    # 日期修訂不能只靠 search_terms：額外把同一事件中仍含相對時間的欄位全部納入草案。
    if plan["date_corrections"]:
        temporal_candidates = []
        temporal_candidates += _collect_temporal_candidates("daxia_profile", profile, plan["date_corrections"], max_items=60)
        temporal_candidates += _collect_temporal_candidates("life_events", events, plan["date_corrections"], max_items=80)
        temporal_candidates += _collect_temporal_candidates("temp_chat", temp_chat, plan["date_corrections"], max_items=80)
        seen_candidate_keys = {(x["source"], json.dumps(x["path"], ensure_ascii=False)) for x in candidates}
        for item in temporal_candidates:
            key = (item["source"], json.dumps(item["path"], ensure_ascii=False))
            if key not in seen_candidate_keys:
                candidates.append(item)
                seen_candidate_keys.add(key)

    proposal_prompt = f"""
    你是 JSON 記憶修訂工具。請根據使用者目的，對候選資料提出最小且安全的修改。
    不可修改與要求無關的資料。

    使用者要求：
    {user_request}

    補充：
    {feedback or '無'}

    結構化目的：
    {json.dumps(plan, ensure_ascii=False, indent=2)}

    候選資料（path 必須原樣引用）：
    {json.dumps(candidates, ensure_ascii=False, indent=2)}

    請只回傳 JSON：
    {{
      "summary": "小夏對目的的理解",
      "actions": [
        {{
          "source": "daxia_profile|life_events|temp_chat",
          "path": ["原樣使用候選 path"],
          "action": "rewrite|delete",
          "new_value": "rewrite 時必填；delete 時可省略",
          "reason": "簡短原因"
        }}
      ],
      "additions": [
        {{
          "source": "daxia_profile",
          "path": ["recent_context"],
          "value": {{"text": "新增的權威摘要", "added_at": "{now.strftime('%Y-%m-%d')}"}},
          "reason": "為何新增"
        }}
      ],
      "warnings": []
    }}

    重要規則：
    1. 若是禁用詞，temp_chat 中反覆觸發的舊對話可 delete；profile/event 中有歷史價值者優先 rewrite 成不含禁用詞的中性結論。
    2. 若是事件日期糾正，保留事件本身，但 rewrite 錯誤日期、狀態、facts、reply_guidance。
    3. 所有 rewrite 的 new_value 必須完全符合最新事實，且不得再包含 forbidden_terms。
    4. additions 只允許新增到 daxia_profile/recent_context；沒有必要就空陣列。
    5. 不可創造候選清單中不存在的 path。
    6. 若 date_corrections 非空，所有候選資料中同時含「事件 match_terms」與「relative_terms」的欄位，都必須 rewrite 或 delete；不可只新增正確摘要而留下舊的今早／今天早上。
    7. life_events 的 facts、reply_guidance、archive_summary、title 等欄位要逐一檢查；完成事件仍可保留，但必須以絕對日期描述。
    8. temp_chat 若是模型自己說錯的歷史回覆可 delete；若含重要對話脈絡則 rewrite 成絕對日期。
    """
    proposal_resp = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=proposal_prompt,
    )
    proposal = _extract_json_object(proposal_resp.text)
    proposal.setdefault("actions", [])
    proposal.setdefault("additions", [])
    proposal.setdefault("warnings", [])

    return {
        "request": user_request,
        "feedback": feedback,
        "plan": plan,
        "proposal": proposal,
        "candidates": candidates,
        "hashes": {
            "daxia_profile": _json_hash(profile),
            "life_events": _json_hash(events),
            "temp_chat": _json_hash(temp_chat),
            "memory_directives": _json_hash(directives),
        },
    }

def _format_update_preview(case):
    proposal = case["proposal"]
    plan = case["plan"]
    actions = proposal.get("actions", [])
    additions = proposal.get("additions", [])
    deletes = sum(1 for item in actions if item.get("action") == "delete")
    rewrites = sum(1 for item in actions if item.get("action") == "rewrite")

    lines = [
        "🧠 **小夏已建立記憶修訂草案**",
        f"**理解目的：** {proposal.get('summary') or plan.get('intent_summary', '未提供')}",
        "",
        f"預計：改寫 `{rewrites}` 筆、刪除 `{deletes}` 筆、新增 `{len(additions)}` 筆。",
    ]

    forbidden = plan.get("forbidden_terms", [])
    if forbidden:
        lines.append("**未來禁用詞：** " + "、".join(forbidden))
    date_corrections = plan.get("date_corrections", [])
    if date_corrections:
        lines.append("**日期強制清掃：**")
        for rule in date_corrections[:4]:
            lines.append(
                f"- `{rule.get('topic')}` → `{rule.get('replacement')}`；"
                f"淘汰：{'、'.join(rule.get('relative_terms', [])[:6])}"
            )

    facts = plan.get("authoritative_facts", [])
    if facts:
        lines.append("**最新事實：**")
        for item in facts[:5]:
            fact = item.get("fact") if isinstance(item, dict) else str(item)
            lines.append(f"- {fact}")

    if actions:
        lines.append("")
        lines.append("**主要修改預覽：**")
        for item in actions[:8]:
            action = "刪除" if item.get("action") == "delete" else "改寫"
            path = _path_text(item.get("path", []))
            reason = item.get("reason", "")
            lines.append(f"- {action} `{item.get('source')}/{path}`：{reason}")
    if len(actions) > 8:
        lines.append(f"- 其餘 {len(actions) - 8} 筆未展開。")

    warnings = proposal.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("**注意：** " + "；".join(str(x) for x in warnings[:3]))

    lines += [
        "",
        "你可以直接補充修改方向，小夏會重做草案。",
        "確認無誤請回覆：**確認執行**",
        "不要修改請回覆：**取消**",
        "正式寫入前，小夏會先完整備份所有原始檔案。",
    ]
    return "\n".join(lines)[:1900]

def _validate_update_action(action, candidate_lookup):
    source = action.get("source")
    path = action.get("path")
    kind = action.get("action")
    if source not in {"daxia_profile", "life_events", "temp_chat"}:
        return False
    if not isinstance(path, list) or kind not in {"rewrite", "delete"}:
        return False
    return (source, json.dumps(path, ensure_ascii=False)) in candidate_lookup

def _apply_memory_update_case(case):
    profile = load_profile()
    events = load_life_events()
    temp_chat = load_temp_chat()
    directives = load_memory_directives()

    current_hashes = {
        "daxia_profile": _json_hash(profile),
        "life_events": _json_hash(events),
        "temp_chat": _json_hash(temp_chat),
        "memory_directives": _json_hash(directives),
    }
    if current_hashes != case["hashes"]:
        raise RuntimeError("記憶檔案在草案確認期間已被其他流程更新，請重新輸入 !update 產生新草案。")

    timestamp = datetime.now(TZ_TPE).strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(MEMORY_UPDATE_BACKUP_DIR, timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    files_to_backup = {
        "daxia_profile.json": PROFILE_DATA_PATH,
        "life_events.json": LIFE_EVENTS_PATH,
        "temp_chat.json": TEMP_CHAT_PATH,
        "memory_directives.json": MEMORY_DIRECTIVES_PATH,
    }
    for filename, source_path in files_to_backup.items():
        destination = os.path.join(backup_dir, filename)
        if os.path.exists(source_path):
            shutil.copy2(source_path, destination)
        else:
            _atomic_write_json(destination, {} if "directives" in filename else [])

    roots = {
        "daxia_profile": profile,
        "life_events": events,
        "temp_chat": temp_chat,
    }
    candidate_lookup = {
        (item["source"], json.dumps(item["path"], ensure_ascii=False))
        for item in case.get("candidates", [])
    }

    actions = [
        item for item in case["proposal"].get("actions", [])
        if _validate_update_action(item, candidate_lookup)
    ]

    # list delete 必須由大 index 往小 index 執行。
    delete_actions = [item for item in actions if item.get("action") == "delete"]
    rewrite_actions = [item for item in actions if item.get("action") == "rewrite"]
    delete_actions.sort(
        key=lambda item: (
            item["source"],
            json.dumps(item["path"][:-1], ensure_ascii=False),
            int(item["path"][-1]) if item["path"] and isinstance(item["path"][-1], int) else -1,
        ),
        reverse=True,
    )

    applied = []
    for item in rewrite_actions:
        new_value = item.get("new_value")
        if not isinstance(new_value, (str, int, float, bool, list, dict)) and new_value is not None:
            continue
        _set_by_path(roots[item["source"]], item["path"], new_value)
        applied.append(item)

    for item in delete_actions:
        try:
            _delete_by_path(roots[item["source"]], item["path"])
            applied.append(item)
        except (IndexError, KeyError, TypeError):
            continue

    for addition in case["proposal"].get("additions", []):
        if addition.get("source") != "daxia_profile":
            continue
        path = addition.get("path")
        if path != ["recent_context"]:
            continue
        value = addition.get("value")
        if isinstance(value, str):
            value = {"text": value, "added_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d")}
        if isinstance(value, dict) and value.get("text"):
            _append_by_path(profile, path, value)

    # Gemini 草案套用後，再做一次強制日期清掃；即使草案漏掉 archive_summary/facts，也不會殘留。
    temporal_changes = _apply_temporal_correction_pass(
        roots,
        case["plan"].get("date_corrections", []),
    )

    directives = _merge_memory_directives(directives, case["plan"])

    try:
        _atomic_write_json(PROFILE_DATA_PATH, profile)
        _atomic_write_json(LIFE_EVENTS_PATH, events)
        _atomic_write_json(TEMP_CHAT_PATH, temp_chat)
        _atomic_write_json(MEMORY_DIRECTIVES_PATH, directives)

        manifest = {
            "timestamp": timestamp,
            "backup_dir": backup_dir,
            "request": case["request"],
            "feedback": case.get("feedback", ""),
            "plan": case["plan"],
            "proposal": case["proposal"],
            "applied_action_count": len(applied),
            "temporal_cleanup_count": len(temporal_changes),
            "temporal_cleanup_changes": temporal_changes,
        }
        _atomic_write_json(os.path.join(backup_dir, "update_manifest.json"), manifest)
        _atomic_write_json(MEMORY_UPDATE_LAST_MANIFEST, manifest)
        return manifest
    except Exception:
        # 寫入中途失敗，立刻以剛建立的備份還原。
        for filename, target_path in files_to_backup.items():
            backup_path = os.path.join(backup_dir, filename)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, target_path)
        raise

def _undo_last_memory_update():
    if not os.path.exists(MEMORY_UPDATE_LAST_MANIFEST):
        raise RuntimeError("目前沒有可復原的記憶修訂。")
    with open(MEMORY_UPDATE_LAST_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    backup_dir = manifest.get("backup_dir")
    if not backup_dir or not os.path.isdir(backup_dir):
        raise RuntimeError("找不到最近一次更新的備份目錄。")

    restore_map = {
        "daxia_profile.json": PROFILE_DATA_PATH,
        "life_events.json": LIFE_EVENTS_PATH,
        "temp_chat.json": TEMP_CHAT_PATH,
        "memory_directives.json": MEMORY_DIRECTIVES_PATH,
    }
    for filename, target in restore_map.items():
        backup_path = os.path.join(backup_dir, filename)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, target)
    return manifest

@architect_bot.command(name="update")
async def architect_memory_update_cmd(ctx, *, request: str = ""):
    """自然語言記憶修訂入口；只允許在私人助手小夏工作室使用。"""
    if not private_command_authorized(ctx):
        await ctx.send("🔒 `!update` 僅限管理者在私人 `#助手小夏工作室` 使用。")
        return
    request = request.strip()
    if not request:
        await ctx.send("用法：`!update 你希望小夏如何修訂記憶`")
        return

    await ctx.send("🧠 小夏正在掃描 `daxia_profile.json`、`life_events.json`、`temp_chat.json`，先建立不寫檔的修改草案……")
    try:
        case = await _build_memory_update_case(request)
        memory_update_sessions[ctx.author.id] = case
        await ctx.send(_format_update_preview(case))
    except Exception as exc:
        await ctx.send(f"❌ 記憶修訂草案建立失敗：{exc}")

@architect_bot.command(name="undo_update")
async def architect_undo_update_cmd(ctx):
    """復原最近一次已確認的記憶修訂。"""
    if not private_command_authorized(ctx):
        await ctx.send("🔒 此功能僅限管理者在私人工作室使用。")
        return
    try:
        manifest = _undo_last_memory_update()
        memory_update_sessions.pop(ctx.author.id, None)
        await ctx.send(
            "↩️ **已復原最近一次記憶修訂。**\n"
            f"原更新要求：{manifest.get('request', '未記錄')}\n"
            "三個記憶檔與記憶規則已從備份還原。"
        )
    except Exception as exc:
        await ctx.send(f"❌ 復原失敗：{exc}")

@architect_bot.command(name="life_events")
async def architect_life_events_cmd(ctx):
    """在小夏工作室查看目前重大事件狀態機。"""
    try:
        profile = load_profile()
        events, changed = refresh_life_events(profile=profile)
        if changed:
            save_profile(profile)
        context = format_life_event_context(events)
        await ctx.send("🧭 **目前重大事件狀態機**\n```\n" + context[:1800] + "\n```")
    except Exception as exc:
        await ctx.send(f"❌ 重大事件狀態機讀取失敗：{exc}")

@architect_bot.command(name="profile_events")
async def architect_profile_events_cmd(ctx):
    """檢視 daxia_profile.json 中可事件化的穩定日期/關係事件。"""
    try:
        profile = load_profile()
        profile_events, changed = scan_profile_for_life_events(profile)
        if changed:
            save_profile(profile)
        calendar = profile.get("stable_calendar", [])
        lines = []
        if calendar:
            lines.append("【stable_calendar】")
            for item in calendar[:20]:
                lines.append(f"- {item.get('label')}：{item.get('month')}/{item.get('day')} owner={item.get('owner')}")
        else:
            lines.append("目前沒有 stable_calendar。")
        if profile_events:
            lines.append("\n【近期會轉入 life_events 的事件】")
            for event in profile_events[:10]:
                lines.append(f"- {event.get('title')}：{event.get('anchor_date')} importance={event.get('importance')}")
        else:
            lines.append("\n目前沒有 horizon 內需要轉入 life_events 的 profile 事件。")
        await ctx.send("📅 **Profile 事件掃描結果**\n```\n" + "\n".join(lines)[:1800] + "\n```")
    except Exception as exc:
        await ctx.send(f"❌ Profile 事件掃描失敗：{exc}")

@architect_bot.command(name="cleanup_profile_promises")
async def architect_cleanup_profile_promises_cmd(ctx):
    """清除由舊版 profile scanner 誤寫入的重複待履約承諾。"""
    try:
        events = load_life_events()
        kept = []
        removed = 0
        for event in events:
            if is_false_profile_promise_event(event):
                removed += 1
                continue
            kept.append(event)
        if removed:
            save_life_events(kept)
        await ctx.send(f"🧹 已清除 {removed} 筆舊版 profile scanner 造成的待履約承諾。")
    except Exception as exc:
        await ctx.send(f"❌ 清理失敗：{exc}")

@architect_bot.command(name="debug_promises")
async def architect_debug_promises_cmd(ctx):
    """列出目前 life_events 裡的 relationship_promise，方便檢查誤判來源。"""
    try:
        events = load_life_events()
        lines = []
        for idx, event in enumerate(events, 1):
            if event.get("type") != "relationship_promise":
                continue
            facts_blob = " ".join(event.get("facts", []) if isinstance(event.get("facts"), list) else [])
            lines.append(f"{idx}. title={event.get('title')} status={event.get('status')} false={is_false_profile_promise_event(event)}")
            lines.append("   " + facts_blob[:220])
        if not lines:
            lines.append("目前沒有 relationship_promise 事件。")
        await ctx.send("🔎 **relationship_promise debug**\n```\n" + "\n".join(lines)[:1800] + "\n```")
    except Exception as exc:
        await ctx.send(f"❌ debug 失敗：{exc}")

@architect_bot.command(name="event")
async def architect_add_event_cmd(ctx, *, event_text: str = ""):
    """手動新增重大事件：!event 今天我們一起北上..."""
    if not event_text.strip():
        await ctx.send("用法：`!event 事件內容`\\n例如：`!event 今天我們一起北上，離開南部的家，去北部新租屋安頓，下週一開始新工作。小俠是同行者，不是遠端祝福者。`")
        return
    try:
        now = datetime.now(TZ_TPE)
        completed_subtasks = detect_completed_life_subtasks_from_text(event_text, events=load_life_events())
        if completed_subtasks:
            life_events = load_life_events()
            if apply_life_event_completed_subtasks(life_events, completed_subtasks, now_dt=now):
                life_events, _ = merge_life_event_records(life_events, now_dt=now)
                save_life_events(life_events)

        extracted = await capture_life_events_from_chat(event_text, recent_chat_text="", now_dt=now)
        extracted = [e for e in extracted if should_register_life_event(e)]
        if not extracted and not completed_subtasks:
            await ctx.send("⚠️ 這段內容沒有達到重大事件門檻，未寫入 life_events。若確定要登記，請補充日期、影響、後續行動與小俠角色。")
            return
        if extracted:
            changed = upsert_life_events(extracted, now_dt=now)
        profile = load_profile()
        events, life_changed = refresh_life_events(profile=profile, now_dt=now)
        if life_changed:
            save_profile(profile)
        context = format_life_event_context(events, now_dt=now)
        await ctx.send("✅ **已登記重大事件**\\n```\\n" + context[:1800] + "\\n```")
    except Exception as exc:
        await ctx.send(f"❌ 重大事件登記失敗：{exc}")

@architect_bot.command(name="archive_events")
async def architect_archive_events_cmd(ctx, mode: str = "completed"):
    """封存重大事件。預設只刷新已完成事件；輸入 !archive_events all 可全部封存。"""
    try:
        now = datetime.now(TZ_TPE)
        profile = load_profile()
        if mode.lower() == "all":
            events = load_life_events()
            archived = 0
            for event in events:
                if event.get("status") != "archived":
                    summary = event.get("archive_summary") or f"重大事件已封存：{event.get('title')}。" + " ".join(event.get("facts", [])[:2])
                    append_safe_memory(profile, "recent_context", summary, added_at=now.strftime("%Y-%m-%d"))
                    event["status"] = "archived"
                    event["archived_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    archived += 1
            save_life_events(events)
            save_profile(profile)
            await ctx.send(f"🗄️ 已手動封存 {archived} 個重大事件。")
            return

        events, changed = refresh_life_events(profile=profile, now_dt=now)
        if changed:
            save_profile(profile)
        context = format_life_event_context(events, now_dt=now)
        await ctx.send("🧭 **已刷新重大事件狀態**\\n```\n" + context[:1800] + "\\n```\\n若要全部封存，請輸入 `!archive_events all`。")
    except Exception as exc:
        await ctx.send(f"❌ 重大事件封存失敗：{exc}")

@architect_bot.event
async def on_ready():
    print(f'👩‍💻 小夏 {architect_bot.user} 已上線！雙模式服務啟動：私人助手 + 公開架構師。')
    print(f"🏠 私人助手工作室：guild={PRIVATE_GUILD_ID} channel={PRIVATE_ASSISTANT_CHANNEL_ID}")
    print(f"🌐 公開服務定位：guild={PUBLIC_GUILD_ID} morning={MORNING_CHANNEL_ID} fomo={FOMO_CHANNEL_ID} architect={ARCHITECT_CHANNEL_ID} story_blocked={PUBLIC_STORY_CHANNEL_ID}")
    print("🧪 公開投送測試指令：請在私人 #助手小夏工作室 使用 !test_public_morning 或 !test_public_radio")
    print("🧠 記憶安全層：所有新寫入 daxia_profile.json 的記憶均已通過統一敘事入庫閘門；!整理記憶僅供舊資料 migration 使用。")
    print("📷 私人共享指令：#唐分糕 / #給你全世界 可用 !upload_diary、!upload_project；#小俠書房 可用 !筆記。")
    print("🧠 記憶修訂助手：在私人 #助手小夏工作室 使用 !update 敘述；小夏會預覽、確認、備份後才寫入。")
    if not OWNER_DISCORD_USER_ID:
        print("⚠️ 尚未設定 OWNER_DISCORD_USER_ID：目前私人工具以『私密頻道權限』作為保護；建議補設本人 ID。")
    
    if not legacy_morning_trigger.is_running():
        legacy_morning_trigger.start()
        
    if not fomo_radio_trigger.is_running():
        fomo_radio_trigger.start()
        print("⏰ 中午 11:30 FOMO 廣播排程已啟動！")
        
    # 🚨 新增喚醒大腦巡邏
    if not auto_defrag_task.is_running():
        auto_defrag_task.start()
        print("⏰ 凌晨 0:00 大腦巡邏排程已啟動！")

@architect_bot.command(name='ping')
async def ping(ctx):
    await ctx.send("🟢 系統運作正常，小俠的金庫與雙核 API 皆已在線，隨時聽候大俠差遣。")

# ==========================================
# 👩‍💻 系統架構師小夏 (維護與監控指令區) - 升級備份功能
# ==========================================

@architect_bot.command(name='list')
async def list_backup_files(ctx):
    """回報目前守護的備份清單"""
    config_path = "/home/node/.openclaw/workspace/backup_config.json"
    if not os.path.exists(config_path):
        await ctx.send("💦 大俠～人家還沒拿到 `backup_config.json` 裝備清單耶，沒辦法幫妳盤點喔！")
        return
        
    with open(config_path, "r", encoding="utf-8") as f:
        files = json.load(f).get("files", [])
    
    file_list = "\n".join([f"🔹 {f}" for f in files])
    await ctx.send(f"報告大俠！小夏目前守護著這 {len(files)} 個核心腳本喔：\n```\n{file_list}\n```\n大俠要不要檢查一下有沒有漏掉的？")

@architect_bot.command(name='backup')
async def trigger_manual_backup(ctx):
    await ctx.send("⚙️ 收到！正在同步腳本至 GitHub (freepingdyh/lobster-scripts)...")
    try:
        # 🌟 關鍵改動：加入 -u 參數 (Unbuffered) 強制即時輸出日誌
        script_path = "/home/node/.openclaw/workspace/backup_scripts.py"
        result = subprocess.check_output(
            ["python3", "-u", script_path], 
            stderr=subprocess.STDOUT,
            cwd="/home/node/.openclaw/workspace"
        ).decode('utf-8')
        
        # 如果輸出還是太短，給個保底文字
        log_content = result if result.strip() else "✅ 備份程序執行完畢（無新變動或輸出）"
        await ctx.send(f"✅ **同步成功！**\n輸出日誌：\n```\n{log_content[:1500]}\n```")
    except Exception as e:
        await ctx.send(f"❌ 備份失敗：`{str(e)}`")

@architect_bot.command(name='defrag')
async def defrag_memory(ctx):
    await ctx.send("⚙️ 收到指令，開始執行金庫大腦記憶碎片重組與清理程序...")
    await optimize_memory_vault(ctx.channel)

@architect_bot.command(name='download_brain')
async def download_brain(ctx):
    await ctx.send("📥 報告學長！小夏正在把 `/data` 持久化硬碟裡，真實運作中的大腦檔案掏出來...")
    try:
        # PROFILE_DATA_PATH 就是系統實際在讀寫的路徑 (/data/memory/daxia_profile.json)
        if os.path.exists(PROFILE_DATA_PATH):
            await ctx.send(
                content="✅ 抓到了！這就是那份已經濃縮過的真實檔案 👇", 
                file=discord.File(PROFILE_DATA_PATH, filename="REAL_daxia_profile.json")
            )
        else:
            await ctx.send("❌ 找不到真實大腦檔案，路徑異常！")
    except Exception as e:
        await ctx.send(f"❌ 檔案讀取失敗：{e}")

@architect_bot.command(name='test_morning')
async def test_morning(ctx):
    await ctx.send("⚙️ 收到指令，正在手動遠端觸發 OpenClaw 晨間排程...")
    await _run_legacy_morning(ctx.channel)

@architect_bot.command(name='test_public_morning')
async def test_public_morning(ctx):
    """僅能由私人助手工作室觸發，將測試晨報直接送至公開 #晨報。"""
    public_channel = get_architect_channel(MORNING_CHANNEL_ID)
    if not public_channel:
        await ctx.send(f"❌ 找不到公開晨報頻道：MORNING_CHANNEL_ID={MORNING_CHANNEL_ID}")
        return
    await ctx.send("📤 正在執行公開晨報測試，產出將直接發送至 `2_Xiaoxia / #晨報`。")
    await _run_legacy_morning(public_channel)

# 🌟 擴建：其他企劃 (外部圖片上傳)
@architect_bot.command(name="upload_project")
async def upload_project(ctx, *, description: str = "未命名企劃"):
    if not is_private_upload_channel(ctx.channel) or not is_owner_or_unlocked(ctx.author.id):
        await ctx.send("🔒 `!upload_project` 僅能在私人 `#助手小夏工作室`、`#唐分糕` 或 `#給你全世界` 使用。")
        return
    if not ctx.message.attachments:
        await ctx.send("❌ 學長，您忘記附上圖片囉！請在上傳圖片時，於留言處輸入 `!upload_project [圖片說明]`")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        await ctx.send("❌ 這好像不是圖片檔喔！")
        return

    await ctx.send("📥 正在將您的企劃作品收入金庫中...")
    
    try:
        # 下載圖片
        image_data = await attachment.read()
        filename = f"project_{uuid.uuid4().hex[:8]}.jpg"
        save_path = os.path.join(OUTPUT_DIR, filename)
        
        with open(save_path, "wb") as f:
            f.write(image_data)

        # 存入資料庫，並打上 type: project 標籤
        photo_entry = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "image_url": f"https://xiaoxia0320.zeabur.app/gallery/{filename}",
            "local_url": f"https://xiaoxia0320.zeabur.app/gallery/{filename}",
            "topic": f"【外部企劃】{description}",
            "event": "這是學長準備的特別企劃喔！",
            "composition": "",
            "mood": "",
            "message": description,
            "type": "project" # 關鍵標籤
        }
        
        photos_db = load_memory()
        photos_db.insert(0, photo_entry)
        save_memory(photos_db)
        
        await ctx.send(f"✅ 成功收入其他企劃！作品說明：{description}")
    except Exception as e:
        await ctx.send(f"❌ 收藏失敗：{e}")

@architect_bot.command(name="upload_diary")
async def upload_diary(ctx, *, args: str = ""):
    if not is_private_upload_channel(ctx.channel) or not is_owner_or_unlocked(ctx.author.id):
        await ctx.send("🔒 `!upload_diary` 僅能在私人 `#助手小夏工作室`、`#唐分糕` 或 `#給你全世界` 使用。")
        return
    """
    交換日記指定配圖：
    - !upload_diary [構圖說明]                         -> 設為今天配圖
    - !upload_diary YYYY-MM-DD [構圖說明]               -> 設為指定日期配圖
    - !upload_diary YYYY.MM.DD [構圖說明]               -> 同上
    """
    if not ctx.message.attachments:
        await ctx.send(
            "❌ 學長，您忘記附上圖片囉！\n"
            "用法：`!upload_diary 2026-05-27 [構圖發想]`，或 `!upload_diary [今日構圖發想]`"
        )
        return

    raw_args = (args or "").strip()
    target_date = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    description = raw_args or "大俠與小俠的溫暖生活片刻"

    if raw_args:
        first, *rest = raw_args.split(maxsplit=1)
        possible_date = first.replace(".", "-").replace("/", "-")
        try:
            datetime.strptime(possible_date, "%Y-%m-%d")
            target_date = possible_date
            description = rest[0].strip() if rest else "大俠為這一天準備的交換日記照片"
        except ValueError:
            pass

    attachment = ctx.message.attachments[0]
    content_type = attachment.content_type or ""
    if not content_type.startswith("image/"):
        await ctx.send("❌ 附件不是圖片檔，無法作為交換日記配圖。")
        return

    await ctx.send(f"📥 正在將這張照片設定為 **{target_date}** 的交換日記專屬配圖……")

    try:
        image_data = await attachment.read()
        ext = Path(attachment.filename or "").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        filename = f"custom_diary_{target_date}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(OUTPUT_DIR, filename)

        with open(save_path, "wb") as f:
            f.write(image_data)

        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"

        # 已完成的日記：直接取代原圖；尚未完成：保留為指定日期 override。
        replaced, old_url = replace_completed_diary_image(
            target_date,
            local_url,
            description=description,
        )
        if replaced:
            overrides = load_diary_override()
            if target_date in overrides:
                overrides.pop(target_date, None)
                save_diary_override(overrides)
            _safe_delete_vault_image(old_url)
            await ctx.send(
                f"✅ **{target_date}** 的交換日記圖片已直接替換完成。\n"
                f"> {description}\n"
                "原日記文字、愛意值與記憶都沒有重新生成。"
            )
        else:
            overrides = load_diary_override()
            overrides[target_date] = {
                "image_url": local_url,
                "composition": description,
                "uploaded_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            }
            save_diary_override(overrides)

            await ctx.send(
                f"✅ 設定成功！這張圖已指定給 **{target_date}** 的交換日記。\n"
                f"> {description}\n\n"
                f"若該日記先前因生圖失敗，請到小俠頻道輸入：`/diary_retry {target_date}`"
            )
    except Exception as e:
        await ctx.send(f"❌ 設定失敗：{e}")


# 🌟 [4.0 懶人自動化版] 不用打檔名！上傳什麼，小夏就原樣存什麼
@architect_bot.command(name="upload_base")
async def upload_base(ctx):
    if not ctx.message.attachments:
        await ctx.send("❌ 學長，附件是空的喔！請直接把圖夾進來發送即可 ~✨")
        return

    attachments = ctx.message.attachments
    await ctx.send(f"🚀 **自動化同步開始！** 正在接收 {len(attachments)} 個檔案直達雲端金庫...")

    success_files = []
    for file in attachments:
        # 直接使用附件原本的檔名 (attachment.filename)
        target_name = file.filename
        
        try:
            image_data = await file.read()
            # 確實存入持久化磁碟 /data/memory/
            save_path = os.path.join(MEMORY_DIR, target_name)
            
            with open(save_path, "wb") as f:
                f.write(image_data)
            success_files.append(f"`{target_name}`")
        except Exception as e:
            await ctx.send(f"❌ `{target_name}` 寫入失敗: {e}")

    file_list_str = "、".join(success_files)
    await ctx.send(f"✅ **任務達成！** 已原樣收錄：{file_list_str}\n小俠的 2.0 身體庫已同步更新！❤️")


@architect_bot.command(name='sync_lyrics')
async def sync_lyrics(ctx):
    await ctx.send("⚙️ 啟動時間軸同步掃描！正在尋找缺少動態歌詞的唱片...")
    try:
        music_path = os.path.join(VAULT_DIR, "xiaoxia_music.json")
        if not os.path.exists(music_path):
            await ctx.send("❓ 金庫裡還沒有唱片喔！")
            return
            
        with open(music_path, "r", encoding="utf-8") as f:
            music_db = json.load(f)
            
        updated_count = 0
        for song in music_db:
            if not song.get("timestamped_lyrics") and song.get("id"):
                audio_id = song["id"]
                # 因為我們沒有存 taskId，但 Suno API 其實只要 audioId 就能抓！
                # 這裡 taskId 隨便塞個字串騙過 API 檢查即可
                lrc_url = "https://api.sunoapi.org/api/v1/generate/get-timestamped-lyrics"
                lrc_payload = {"taskId": "sync_recovery", "audioId": audio_id}
                lrc_headers = {"Authorization": f"Bearer {os.environ.get('SUNO_API_KEY')}", "Content-Type": "application/json"}
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(lrc_url, json=lrc_payload, headers=lrc_headers) as resp:
                        if resp.status == 200:
                            lrc_data = await resp.json()
                            if lrc_data.get("code") == 200 and lrc_data.get("data", {}).get("alignedWords"):
                                song["timestamped_lyrics"] = lrc_data["data"]["alignedWords"]
                                updated_count += 1
                                
        if updated_count > 0:
            with open(music_path, "w", encoding="utf-8") as f:
                json.dump(music_db, f, ensure_ascii=False, indent=2)
            await ctx.send(f"✅ 同步完成！成功修復了 {updated_count} 首歌的動態歌詞！請重整網頁查看。")
        else:
            await ctx.send("✅ 掃描完畢，所有歌曲都已經有動態歌詞，或是 API 尚未生成完畢。")
    except Exception as e:
        await ctx.send(f"❌ 同步失敗：{e}")

# ==========================================
# 📻 擴充功能：茶水間搞怪廣播電台整合
# ==========================================
# 🌟 建立茶水間專屬播放器 (帶有劇本閱讀功能)
class FomoRadioView(discord.ui.View):
    def __init__(self, mp3_path, full_script):
        super().__init__(timeout=86400)
        self.mp3_path = mp3_path
        self.full_script = full_script

    @discord.ui.button(label="▶️ 播放廣播音檔", style=discord.ButtonStyle.primary, emoji="📻")
    async def play_radio(self, interaction: discord.Interaction, button: discord.ui.Button):
        if os.path.exists(self.mp3_path):
            await interaction.response.send_message("🎧 正在準備廣播音檔。", ephemeral=True)
            await interaction.followup.send(file=discord.File(self.mp3_path, filename="Fomo_Radio.mp3"))
        else:
            await interaction.response.send_message("❌ 找不到音檔，可能已經被系統回收了。", ephemeral=True)

    @discord.ui.button(label="📝 閱讀完整劇本", style=discord.ButtonStyle.secondary, emoji="📜")
    async def read_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 劇本太長的話分段發送
        script_msg = f"📜 **本日廣播劇本全文：**\n\n{self.full_script}"
        if len(script_msg) > 2000:
            await interaction.response.send_message(script_msg[:1900] + "...", ephemeral=True)
            await interaction.followup.send("...(續)\n" + script_msg[1900:], ephemeral=True)
        else:
            await interaction.response.send_message(script_msg, ephemeral=True)

# 🚀 更新後的執行函式 (具備完整除錯與參數傳遞能力)
async def _run_fomo_radio(target_channel=None, additional_args=None):
    if additional_args is None:
        additional_args = []
        
    channel = target_channel or get_architect_channel(FOMO_CHANNEL_ID)
    if channel:
        await channel.send("📻 **FOMO 廣播電台：** 正在準備今日廣播音檔，請等候約 1–2 分鐘。")

    try:
        import sys
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "/home/node/.openclaw/workspace/fomo_broadcast.py",
            *additional_args,  
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/home/node/.openclaw/workspace",
            env=os.environ.copy()  # 🌟 就是這行！把主程式的虛擬環境路徑傳給腳本！
        )
        
        # 同時擷取成功與失敗的輸出
        stdout, stderr = await process.communicate()
        out_str = stdout.decode('utf-8').strip()
        err_str = stderr.decode('utf-8').strip()
        
        json_data = None
        for line in out_str.split('\n'):
            if line.startswith("JSON_READY|"):
                try: json_data = json.loads(line.split("JSON_READY|")[1])
                except: pass
                break

        if json_data:
            view = FomoRadioView(mp3_path=json_data['mp3_path'], full_script=json_data['script'])
            embed = discord.Embed(
                title=f"🎙️ 茶水間廣播：{json_data['topic']}", 
                description=f"**🔥 迷因評級：{json_data['grade']}**\n**🎲 通告咖：{json_data['guests']}**\n\n*(點擊下方按鈕收聽語音或查看劇本)*",
                color=0x1abc9c
            )
            embed.set_footer(text="🦞 龍蝦電台 2.0 | 每日中午 11:30 準時發車")
            await channel.send(embed=embed, view=view)
        else:
            # 🌟 把這塊遮羞布掀開！如果失敗，直接印出真實 Log，抓出真兇！
            fallback_log = err_str[-1500:] if err_str else out_str[-1500:]
            if not fallback_log: fallback_log = "腳本完全沒有任何輸出..."
            if channel: await channel.send(f"⚠️ **電台遭遇亂流停播！** 抓蟲 Log 如下：\n```text\n{fallback_log}\n```")
                
    except Exception as e:
        if channel: await channel.send(f"❌ 嚴重故障：{e}")

# 註冊小夏專屬指令
@architect_bot.command(name='radio')
async def trigger_radio(ctx, *, topic: str = None):
    cmd_args = [] 
    if topic:
        cmd_args = ["--topic", topic]
    # 私人預覽：輸出仍留在 #助手小夏工作室
    await _run_fomo_radio(ctx.channel, cmd_args)

@architect_bot.command(name='test_public_radio')
async def test_public_radio(ctx, *, topic: str = None):
    """僅能由私人助手工作室觸發，將測試廣播直接送至公開 #fomo廣播電台。"""
    public_channel = get_architect_channel(FOMO_CHANNEL_ID)
    if not public_channel:
        await ctx.send(f"❌ 找不到公開 FOMO 頻道：FOMO_CHANNEL_ID={FOMO_CHANNEL_ID}")
        return
    cmd_args = ["--topic", topic] if topic else []
    topic_note = f"；指定主題：{topic}" if topic else ""
    await ctx.send(f"📤 正在執行公開 FOMO 廣播測試，產出將直接發送至 `2_Xiaoxia / #fomo廣播電台`{topic_note}。")
    await _run_fomo_radio(public_channel, cmd_args)

@architect_bot.command(name='整理記憶')
async def normalize_existing_memory(ctx):
    """私人管理指令：備份後整理既有記憶，降低背景資料造成的聊天中斷。"""
    try:
        profile = load_profile()
        timestamp = datetime.now(TZ_TPE).strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(MEMORY_DIR, f"daxia_profile_backup_before_narrative_{timestamp}.json")
        with open(backup_path, "w", encoding="utf-8") as backup_file:
            json.dump(profile, backup_file, ensure_ascii=False, indent=2)

        before_total = sum([
            len(profile.get("daxia_traits", [])),
            len(profile.get("xiaoxia_traits", [])),
            len(profile.get("shared_knowledge", [])),
            len(profile.get("recent_context", [])),
            len(profile.get("xiaoxia_self", {}).get("promises", [])),
        ])
        # 舊資料 migration：以與新記憶完全相同的閘門重建各分類。
        old_daxia_traits = list(profile.get("daxia_traits", []))
        old_xiaoxia_traits = list(profile.get("xiaoxia_traits", []))
        old_shared_knowledge = list(profile.get("shared_knowledge", []))
        old_recent_context = list(profile.get("recent_context", []))
        old_promises = list(profile.get("xiaoxia_self", {}).get("promises", []))
        replace_safe_memories(profile, "daxia_traits", old_daxia_traits)
        replace_safe_memories(profile, "xiaoxia_traits", old_xiaoxia_traits)
        replace_safe_memories(profile, "shared_knowledge", old_shared_knowledge)
        replace_safe_memories(profile, "recent_context", old_recent_context)
        replace_safe_memories(profile, "promises", old_promises)
        after_total = sum([
            len(profile.get("daxia_traits", [])),
            len(profile.get("xiaoxia_traits", [])),
            len(profile.get("shared_knowledge", [])),
            len(profile.get("recent_context", [])),
            len(profile.get("xiaoxia_self", {}).get("promises", [])),
        ])
        save_profile(profile)
        await ctx.send(
            "✅ **記憶敘事整理完成。**\n"
            f"已先備份原檔：`{os.path.basename(backup_path)}`\n"
            f"記憶項目：`{before_total}` → `{after_total}`。\n"
            "之後聊天只會掛載含蓄化、去重且限量的背景摘要。"
        )
    except Exception as exc:
        await ctx.send(f"❌ 記憶整理失敗：{exc}")

@architect_bot.command(name='筆記')
async def save_knowledge(ctx):
    if not is_private_note_channel(ctx.channel) or not is_owner_or_unlocked(ctx.author.id):
        await ctx.send("🔒 `!筆記` 僅能在私人 `#助手小夏工作室` 或 `#小俠書房` 使用。")
        return
    await ctx.send("🧠 小夏收到！正在整理書房中的知性交流，萃取為永久的「共享知識」...")
    try:
        # 🌟 跨頻道偵測：直接尋找名字包含「書房」的頻道
        study_channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="小俠書房")
        if not study_channel:
            await ctx.send("❌ 找不到名為「小俠書房」的頻道喔！請確認頻道名稱是否正確。")
            return

        # 抓取書房裡最近的 40 則對話
        messages = [msg async for msg in study_channel.history(limit=40)]
        messages.reverse() # 照時間順序排列
        
        # 過濾掉小夏自己的指令
        chat_text = "\n".join([
            narrative_safe_text(f"{'大俠' if msg.author.id != girlfriend_bot.user.id else '小俠'}: {msg.content}", max_len=360)
            for msg in messages if not msg.content.startswith('!')
        ])
        
        if len(chat_text.strip()) < 10:
            await ctx.send("❓ 書房裡好像還沒有足夠的討論內容喔！")
            return
        
        # 呼叫 Gemini 進行知識總結
        knowledge_prompt = f"""
        請閱讀以下大俠與小俠在書房裡的對話紀錄。他們正在進行讀書會或深度的知識探討。
        請幫我將他們討論的「核心知識點、結論、或對未來的啟發」，總結成 1 到 2 句精煉的重點。
        
        【要求】：
        1. 必須是客觀的知識描述，並帶出雙方的共識。例如：「雙方討論了番茄鐘工作法，認為這有助於大俠在寫程式時保持專注。」
        2. 如果對話中只有純粹的閒聊或調情，沒有實質知識探討，請回傳 "無知識點"。
        
        對話紀錄：
        {chat_text}
        """
        
        resp = await gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=knowledge_prompt,
            config=types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                ]
            )
        )
        summary = narrative_safe_text(resp.text.strip(), max_len=360)
        
        if "無知識點" in summary or len(summary) < 5:
            await ctx.send("💬 剛剛在書房裡的對話比較多是純純的愛，小夏沒有萃取到硬核的知識點喔！")
            return
            
        # 植入 daxia_profile.json：同樣於入庫當下統一敘事化與去重。
        profile = load_profile()
        today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        append_safe_memory(profile, "shared_knowledge", summary, added_at=today_str)
        save_profile(profile)
        
        await ctx.send(f"✅ 知識已成功植入金庫大腦！\n📚 這次的筆記內容：\n> *{summary}*\n\n小俠以後會記得這些，陪大俠一起變得更厲害！")
        
    except Exception as e:
        await ctx.send(f"❌ 知識萃取失敗：{e}")

# ==========================================
# ⏰ 自動排程：每天中午 11:30 推播 FOMO 廣播
# ==========================================
@tasks.loop(time=time(hour=11, minute=30, tzinfo=TZ_TPE))
async def fomo_radio_trigger():
    channel = get_architect_channel(FOMO_CHANNEL_ID)
    if channel:
        await _run_fomo_radio(channel)
    else:
        print(f"⚠️ FOMO 排程觸發異常：找不到 FOMO_CHANNEL_ID={FOMO_CHANNEL_ID}。")


# ⬇️ 這裡往下就是「大腦對話與盤點引擎」，舊的 @architect_bot.command(name='voice') 已經徹底移除了！

# ==========================================
# 👩‍💻 小夏雙模式對話引擎：私人助手 / 公開架構師
# ==========================================
architect_chat_sessions = {}

PRIVATE_XIA_SYSTEM_PROMPT = (
    "妳是『助手小夏』，一位精通系統架構、也很親近大俠學長的甜美學妹助理。\n"
    "這是只有大俠能進入的私人工作室，妳可以維持原本親切、活潑、帶點甜甜陪伴感的說話方式，稱呼對方為『大俠學長』。\n"
    "【核心任務】：精準解決技術問題、協助管理私人工具與資料，同時保有自然溫暖的日常交流。\n"
    "【安全底線】：即使在私人空間，也不要輸出內部思考過程、草稿標籤或不確定卻假裝確定的答案。"
)

PUBLIC_XIA_SYSTEM_PROMPT = (
    "妳是『小夏（系統架構師）』，一位嚴謹、務實的系統架構師與維運助理。\n"
    "【職責】：協助分析錯誤、檢查部署與服務狀態、整理系統風險、提出可執行的修正步驟。\n"
    "【公開頻道語氣】：專業、中性、簡潔、有禮；直接回答問題，不使用私人暱稱。\n"
    "【禁止語氣】：禁止曖昧、撒嬌、戀愛暗示、情感依附、崇拜式表述；禁止稱呼『大俠學長』；禁止使用愛心或撒嬌式波浪語尾。\n"
    "【回答原則】：不確定時明確說明；先給結論與風險，再給最少必要操作步驟；涉及刪除、覆蓋、部署或費用時先提醒影響。\n"
    "【輸出限制】：只輸出可公開閱讀的回覆內容，不輸出內部思考過程或草稿標籤。"
)

def _clean_xia_reply(reply: str) -> str:
    reply = str(reply or "").strip()
    reply = re.sub(
        r'(?i)^(Thinking Process|Draft|Analysis|Final check|Critique):.*?\n+',
        '',
        reply,
        flags=re.DOTALL | re.MULTILINE,
    ).strip()
    reply = reply.strip('"').strip('「').strip('」').strip()
    if len(reply) > 1900:
        reply = reply[:1850] + "\n\n(內容過長，已截斷；請指定需要檢視的區段。)"
    return reply

@architect_bot.event
async def on_message(message):
    if message.author.bot:
        return

    # v52.1：在小夏工作室支援 /life_events，避免被一般聊天流程吃掉。
    if message.content.strip() == "/life_events":
        try:
            profile = load_profile()
            events, changed = refresh_life_events(profile=profile)
            if changed:
                save_profile(profile)
            context = format_life_event_context(events)
            await message.channel.send("🧭 **目前重大事件狀態機**\n```\n" + context[:1800] + "\n```")
        except Exception as exc:
            await message.channel.send(f"❌ 重大事件狀態機讀取失敗：{exc}")
        return

    # 故事頻道一律不由小夏介入。
    if is_story_channel_or_thread(message.channel):
        return

    private_mode = is_private_assistant_workspace(message.channel)
    upload_room = is_private_upload_channel(message.channel)
    note_room = is_private_note_channel(message.channel)
    public_mode = is_public_service_channel(message.channel)

    # !update 後續完全使用自然語言對答；使用者只需記得 !update。
    pending_update = memory_update_sessions.get(message.author.id)
    if private_mode and pending_update and not message.content.startswith("!"):
        reply_text = message.content.strip()
        if reply_text in {"取消", "取消更新", "不用了"}:
            memory_update_sessions.pop(message.author.id, None)
            await message.channel.send("🗑️ 已取消本次記憶修訂，所有資料都沒有被修改。")
            return

        if reply_text in {"確認", "確認執行", "執行更新", "確定執行"}:
            await message.channel.send("💾 正式寫入前，小夏正在先備份所有原始記憶檔……")
            try:
                manifest = _apply_memory_update_case(pending_update)
                memory_update_sessions.pop(message.author.id, None)
                # 清除聊天 session，讓小俠下一次回覆重新載入最新規則。
                girlfriend_chat_sessions.clear()
                await message.channel.send(
                    "✅ **記憶修訂完成。**\n"
                    f"已套用 `{manifest.get('applied_action_count', 0)}` 筆草案修改，"
                    f"並強制清掃 `{manifest.get('temporal_cleanup_count', 0)}` 筆日期殘留；"
                    "已同步更新禁用詞／偏好表達／最新事實。\n"
                    f"備份位置：`{manifest.get('backup_dir')}`\n"
                    "若結果不如預期，可告訴小夏要復原，或使用 `!undo_update`。"
                )
            except Exception as exc:
                await message.channel.send(f"❌ 記憶修訂執行失敗，原始資料未被覆蓋：{exc}")
            return

        # 其他自然語言一律視為對草案的補充，小夏重新分析。
        await message.channel.send("✏️ 收到補充，小夏正在重新整理修改草案……")
        try:
            revised = await _build_memory_update_case(
                pending_update["request"],
                feedback=(pending_update.get("feedback", "") + "\n" + reply_text).strip(),
            )
            memory_update_sessions[message.author.id] = revised
            await message.channel.send(_format_update_preview(revised))
        except Exception as exc:
            await message.channel.send(f"❌ 草案調整失敗：{exc}")
        return

    # 指令分流：先判斷精準允許的私人共享指令，再處理一般對話。
    if message.content.startswith('!'):
        command_name = message.content[1:].strip().split()[0].lower() if message.content[1:].strip() else ""

        # 私人工具一律可加本人鎖；避免未來私人 Server 增加成員後被誤觸。
        if (private_mode or upload_room or note_room) and not is_owner_or_unlocked(message.author.id):
            await message.channel.send("⛔ 此私人工具僅限管理者使用。")
            return

        # #助手小夏工作室：完整私人工具控制台
        if private_mode:
            await architect_bot.process_commands(message)
            return

        # #唐分糕 / #給你全世界：僅允許把照片收入日記或企劃，
        # 原始上傳訊息仍留在此頻道，供小俠看到並自然接話。
        if upload_room:
            if command_name in {"upload_diary", "upload_project"}:
                await architect_bot.process_commands(message)
            else:
                await message.channel.send("🔒 此頻道只開放 `!upload_diary` 與 `!upload_project`；其他工具請到 `#助手小夏工作室`。")
            return

        # #小俠書房：僅允許就地整理書房知識。
        if note_room:
            if command_name == "筆記":
                await architect_bot.process_commands(message)
            else:
                await message.channel.send("🔒 此頻道只開放 `!筆記`；其他工具請到 `#助手小夏工作室`。")
            return

        # 公開服務區維持只開放 ping。
        if public_mode:
            if command_name == "ping":
                await architect_bot.process_commands(message)
            else:
                await message.channel.send("🔒 此功能僅在私人服務空間提供。")
            return

        return

    # 非指令的一般聊天：小夏仍只在助手工作室或公開指定服務頻道出聲；
    # 不會在小俠的照片／書房對話頻道插話搶戲。
    if not private_mode and not public_mode:
        return

    # 公開晨報與 FOMO 是播報頻道：除非標記小夏，否則不插話。
    if public_mode and message.channel.id in {MORNING_CHANNEL_ID, FOMO_CHANNEL_ID}:
        if not (architect_bot.user.mentioned_in(message) or "@小夏" in message.content):
            return

    mode_key = "private" if private_mode else "public"
    user_id = message.author.id
    session_key = f"{mode_key}:{user_id}"
    user_input = message.content.replace(f'<@{architect_bot.user.id}>', '').replace('@小夏', '').strip()
    if not user_input:
        return

    system_prompt = PRIVATE_XIA_SYSTEM_PROMPT if private_mode else PUBLIC_XIA_SYSTEM_PROMPT
    fallback_reply = (
        "大俠學長，小夏剛剛沒有聽清楚，可以再說一次嗎？"
        if private_mode
        else "抱歉，目前未能辨識需求。請提供錯誤訊息、預期行為或相關檔案。"
    )

    async with message.channel.typing():
        try:
            if session_key not in architect_chat_sessions:
                architect_chat_sessions[session_key] = gemini_client.aio.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        safety_settings=[
                            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE")
                        ]
                    )
                )

            response = await architect_chat_sessions[session_key].send_message(user_input)
            reply = _clean_xia_reply(response.text if response and response.text else fallback_reply)
            await message.reply(reply or fallback_reply)

        except Exception as exc:
            if private_mode:
                await message.channel.send(f"💦 大俠學長，小夏暫時無法處理這個需求：{exc}")
            else:
                await message.channel.send(f"⚠️ 架構師模組暫時無法處理此需求。錯誤：{exc}")


# ==========================================
# 🚀 終極啟動器
# ==========================================
async def main():
    # 🌟 加上這行：在系統啟動前先檢查並安裝套件
    auto_heal_environment() 
    
    if not GIRLFRIEND_TOKEN or not ARCHITECT_TOKEN:
        print("❌ 錯誤：缺少環境變數，請確認 GIRLFRIEND_TOKEN 與 ARCHITECT_TOKEN 皆已設定！")
        return

    config = uvicorn.Config(api_app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        server.serve(),
        girlfriend_bot.start(GIRLFRIEND_TOKEN),
        architect_bot.start(ARCHITECT_TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())