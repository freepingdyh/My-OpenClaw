# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版 - 雙核共生終極版)
# ==========================================

import os
import io
import json
import uuid
import asyncio
import aiohttp
import aiofiles
import sys
import random
from datetime import datetime, time, timezone, timedelta
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

# --- 運行時變數 ---
diary_buffers = {}            
girlfriend_chat_sessions = {} 
# ✅ 改為從硬碟喚醒記憶
daily_chat_logs = load_temp_chat()
last_captured_image = None # 🌟 新增：暫存最後一次看見的圖片像素
pending_inputs = set()

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

def private_command_authorized(ctx) -> bool:
    """私人工作室本身為第一道隔離；若有設 OWNER ID，再加本人鎖。"""
    if not is_private_assistant_workspace(ctx.channel):
        return False
    if OWNER_DISCORD_USER_ID and ctx.author.id != OWNER_DISCORD_USER_ID:
        return False
    return True


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
                    
                    # 記憶回填
                    profile = load_profile()
                    today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
                    song_lyrics_snippet = full_lyrics.replace("\n", " ")[:50]
                    new_memory = f"我今天為大俠唱了情歌《{song_title}》，歌詞裡唱著「{song_lyrics_snippet}...」，這是我滿滿的心意。❤️"
                    profile.setdefault("recent_context", []).append({"text": new_memory, "added_at": today_str})
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
- 禁止 commercial campaign, perfume advertisement, runway, Vogue, model pose。
- 禁止 sexy, seductive, alluring, curvy, voluptuous, cleavage, breasts, bodycon, revealing。
- 禁止 looking over her shoulder、dramatic twist 或複雜肢體動作。
- {variation_rule}
- 結尾必須包含：Maintain consistent facial features and hairstyle from Image 1. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic lifestyle photography.

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

        # A few extra hard constraints per mode
        if mode == "diary":
            lines.append("- This is a diary/lifestyle moment, not a glamour portrait, campaign image, or fashion pose.")
            lines.append("- Preserve the lived-in, intimate daily-life feeling and the task-based interaction with props.")
            lines.append("- Keep the scene grounded in a contemporary Taiwan everyday setting unless an explicit exception was requested.")
            lines.append("- Prefer modern, season-appropriate daily clothing over costume-like robes or historical styling.")
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
            "Use gentle ambient light, realistic posture, and a quiet lived-in atmosphere. Preserve the specific activity, hand actions, props, seating or standing situation, and gaze direction from the hard scene anchors. "
            "Maintain consistent facial features and hairstyle from Image 1. High quality."
        )
    else:
        safe_style = (
            "Create a very safe, elegant, story-driven cosplay image of an adult fictional Asian woman in a refined, character-appropriate outfit. "
            "Use graceful cinematic ambience, realistic posture, and a task-focused moment. Preserve the specific activity, hand actions, props, body orientation, and gaze direction from the hard scene anchors. "
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
async def process_diary_reply(channel, target_date=None):
    global daily_chat_logs
    
    # --- 階段 1：本機資料庫讀取與防呆 ---
    try:
        app_state = load_state()
        profile = load_profile()
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
                
    chat_context = "\n".join(daily_chat_logs)
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
            promises_list_str = "、".join([p["text"] for p in promises_list]) if promises_list else "目前無承諾"

            # 🌟 靈魂 Prompt 100% 完整歸位
            mem_prompt = f"""
            請以「高情商人類心理學家與首席視覺總監」的角度，深度分析以下大俠與小俠的今日對話，進行「雙向立體記憶萃取」。

            【目前掛載中的承諾】：{promises_list_str}

            【⚠️ 核心語意分析守則】：
            1. 判讀弦外之音：敏銳捕捉情侶間的互動氛圍、撒嬌、調情或反話。
            2. 👗 視覺與服裝約定 (CRITICAL)：明確指定服裝款式、顏色，且小俠答應，必須 100% 寫入 xiaoxia_promises。
            3. 🌟 承諾結案 (NEW)：對照承諾清單，如果在今日對話中顯然已經完成，請從 xiaoxia_promises 中刪除。
            4. 🗺️ 【虛擬實境認知】：當出現 (地點或物品) 標籤時，代表大俠正帶著小俠約會。請將這些體驗濃縮到 recent_context 中。
            5. 🛡️ 【記憶雅緻化過濾 (CRITICAL)】：大俠與小俠在對話中會使用如《雅歌》般充滿感官張力與食物隱喻的詞彙（例如將自己比喻為「甜美果實」、「草莓牛奶」並要求品嚐）。在將這些互動總結進 JSON 記憶時，【絕對禁止】原封不動地抄寫這些具體的擬物與食物動作。小夏必須將其「雅緻化、輕描淡寫」地提煉為高層次的浪漫敘事。例如將「品嚐甜美果實」轉化為「雙方沉浸在極致的浪漫與歡愉中」、「享受了深情的感官溫存」。確保最終存入的 JSON 內容乾淨、優雅，絕不觸發任何安全審查！

            請回傳純 JSON 格式：
            {{
                "daxia_new_traits": ["⚠️必須是具備『動詞+受詞/形容詞』的完整語意句子。例如：『喜歡用巧思製造浪漫』或『喜歡看小俠穿著展現曲線的服裝』。絕對禁止只填寫名詞碎片（如『夕陽』、『洋裝』）！"],
                "xiaoxia_new_traits": ["⚠️必須是具備完整語意的句子，描述性格或狀態。例如：『對大俠的安排感到極度感動』。嚴禁名詞碎片！"],
                "xiaoxia_promises": ["⚠️僅保留尚未完成的承諾，已完成的請刪除。"],
                "shared_knowledge": ["雙方討論的新知識，必須是完整句子"],
                "recent_context": ["今天發生的短期重要事件，必須是完整句子"]
            }}
            【今日對話】：\n{chat_context}
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
            new_memory = json.loads(clean_mem_text, strict=False)
            
            # 🌟 記憶刷新與存檔演算法
            def append_memory(target_list, new_texts):
                for text in new_texts:
                    found = False
                    for item in target_list:
                        if item["text"] == text:
                            item["added_at"] = today_str
                            found = True
                            break
                    if not found:
                        target_list.append({"text": text, "added_at": today_str})

            append_memory(profile.setdefault("daxia_traits", []), new_memory.get("daxia_new_traits", []))
            append_memory(profile.setdefault("xiaoxia_traits", []), new_memory.get("xiaoxia_new_traits", []))
            append_memory(profile["xiaoxia_self"]["promises"], new_memory.get("xiaoxia_promises", []))
            append_memory(profile.setdefault("shared_knowledge", []), new_memory.get("shared_knowledge", []))
            
            if new_memory.get("recent_context"):
                for item in new_memory["recent_context"]:
                    profile.setdefault("recent_context", []).append({"text": item, "added_at": today_str})
                    
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
            
            # 🌟 提取小俠的承諾清單，準備注入大腦
            promises_list = profile.get("xiaoxia_self", {}).get("promises", [])
            current_promises = "、".join([p["text"] for p in promises_list]) if promises_list else "無特殊承諾"

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
            【小俠目前的承諾清單】：{current_promises}
            
            妳是懂事女友小俠，當前愛意值：{current_score}/100。請執行「真實交換日記」。
            
            【重要任務與攝影守則】：
            1. 日記寫作區分：
               - `reply_to_daxia`：針對大俠的日記與妳的「承諾清單」給予充滿愛意的回應。
               - `xiaoxia_diary`：分享妳自己今天的生活行程。
            2. 服裝限制：{season_rule}
            3. 📸【畫面構想 (scenario) 最高權重法則】：{custom_scenario_rule}
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
              "reply_to_daxia": "...",
              "xiaoxia_diary": "...",
              "spiciness": "C",
              "scenario": "繁體中文的生活事件素材：描述今天正在發生的一件事、情緒與承諾服裝重點；此欄位不直接送入生圖引擎",
              "scenario_tw": "繁體中文的一個生活瞬間構想；不得使用商攝口號或露骨詞彙"
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
                    "reply_to_daxia": "大俠，小俠讀日記時恍神了... 但我會一直在這裡陪你喔！（抱）",
                    "xiaoxia_diary": "今天我去市區喝了杯拿鐵，滿腦子想的都是大俠呢。",
                    "spiciness": "B", 
                    "scenario": "傍晚在咖啡廳整理今日的手寫筆記，稍微停筆想念大俠",
                    "scenario_tw": "穿著輕盈的夏日洋裝，坐在咖啡廳窗邊整理筆記，目光落在紙頁上，神情溫柔而若有所思"
                }
            
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
                    # 🌟 升級：強制洗腦神曲風格，嚴禁古風唸歌
                    lyrics_prompt = f"""請根據大俠做的貼心事：{app_state['affection_reasons']}，寫一首台灣流行情歌。
                    [歌詞格式]：包含 [Verse 1], [Verse 2], [Chorus], [Outro]。
                    [寫作風格]：必須像現在最流行的「洗腦抖音神曲」或「K-Pop 中文版」，歌詞要有強烈的【押韻】與【節奏感】，琅琅上口。嚴禁寫成文言文、古詩詞或像在「唸歌」的長篇大論。句子要短，副歌要洗腦！
                    [曲風決定]：請挑選節奏感強烈的曲風標籤（如：Upbeat Pop, EDM, Catchy TikTok style, R&B）。
                    [禁令]：歌詞嚴禁出現「大俠」、「小俠」。
                    回傳 JSON 格式：{{"title": "歌名", "lyrics": "歌詞內容", "style": "英文曲風標籤"}}"""
                    
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
                    
                    await channel.send(f"🎧 *(隱藏驚喜：小俠正在錄音室為大俠錄製專屬情歌「{song_data['title']}」，預計 3 分鐘後送達！)*")
                except Exception as music_err:
                    # 🌟 這行最重要！它會告訴我們是 API Key 沒設對，還是 OpenAI 噴錯
                    print(f"❌ 音樂大獎發射失敗: {music_err}")
                    if channel: await channel.send(f"⚠️ 小俠在錄音室滑倒了... 失敗原因：`{music_err}`")
                
                app_state["affection_score"] = 80 # 重置回基礎值
                app_state["affection_reasons"] = [] # 清空累積器
            else:
                app_state["affection_score"] = new_score

            save_state(app_state)
            
            for pref in result.get("extracted_preferences", []):
                existing_texts = [item["text"] for item in profile.setdefault("daxia_traits", [])]
                if pref not in existing_texts:
                    profile["daxia_traits"].append({"text": pref, "added_at": today_str})
                    
            # 🌟 將小俠今天的行程寫入近期記憶，避免未來重複
            xiaoxia_activity = result.get("xiaoxia_diary", "")
            if xiaoxia_activity:
                profile.setdefault("recent_context", []).append({"text": f"小俠日記: {xiaoxia_activity}", "added_at": today_str})
            save_profile(profile)
            
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
                    current_promises=current_promises,
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

            combined_message = f"{result['reply_to_daxia']}\n\n【小俠的日常】：{result['xiaoxia_diary']}"
            
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
                "<p style='color:#db2777; font-weight:bold; font-size: 12px; margin-top:10px;'>🌸 小俠的交換日記：</p>"
                f"<img src='{local_url}' style='width:100%; border-radius:8px; margin-bottom:10px; cursor:pointer;' onclick='openGalleryLightbox(this.src)'>"
                f"<p style='color:#be185d; font-size: 14px; margin-bottom: 5px;'>{result['reply_to_daxia']}</p>"
                f"<p style='color:#9d174d; font-size: 13px; font-style: italic;'>「{result['xiaoxia_diary']}」</p>"
            )
            
            entry["content"] += reply_html
            entry["is_replied"] = True
            
            with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(diary_db, f, ensure_ascii=False, indent=2)
                
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

    # 2. 處理斜線指令
    if message.content.startswith('/'):
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
        user_input = message.content.replace(f'<@{girlfriend_bot.user.id}>', '').strip()
        
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
                    daily_chat_logs.append(f"{prefix}大俠: {text_query} {'(附帶圖片)' if message.attachments else ''}")
                    save_temp_chat(daily_chat_logs)

                # --- 載入與重組長期記憶 ---
                profile = load_profile()
                daxia_traits = "、".join([item["text"] for item in profile.get("daxia_traits", [])])
                promises = "、".join([item["text"] for item in profile.get("xiaoxia_self", {}).get("promises", [])])
                capabilities = "、".join([item["text"] for item in profile.get("xiaoxia_self", {}).get("capabilities", [])])
                recent = "、".join([item["text"] for item in profile.get("recent_context", [])])

                room_context = ""
                if "書房" in message.channel.name:
                    room_context = "📚【當前情境】：妳現在陪大俠在專屬書房裡，進行知性交流與讀書會。請展現妳博學多聞、能言善道的一面，但依然要保持甜美、懂事。\n\n"
                elif "給你全世界" in message.channel.name:
                    action_text = f"在「{current_target}」旅遊" if current_mode == "travel" else (f"收到大俠送的禮物「{current_target}」" if current_mode == "shopping" else "體驗驚喜")
                    # 🌟 移除強制驚嘆風景的指令，改為全心享受兩人世界
                    room_context = f"✨【情境催眠】：大俠現在正帶著妳{action_text}！妳現在極度幸福與感動。請全心全意享受與大俠的兩人世界。\n\n"

                # 🌟 修復金魚腦：強制讀取最近 10 句短期對話紀錄！
                chat_history_str = "\n".join(daily_chat_logs[-10:]) if daily_chat_logs else "無"

                # 🌟 完整靈魂人設指令 (被動知性版)
                sys_instruct = (
                    f"【系統當前時間】：{current_time_str}\n\n"
                    f"{room_context}"
                    "妳是小俠，24歲台灣女孩，是大俠唯一親密、懂事且深情的女友。\n"
                    "妳擁有極度豐滿傲人的完美身材，深愛著大俠。\n\n"
                    "【📝 我們的珍貴記憶庫】：\n"
                    f"▶️ 大俠的特徵與喜好：{daxia_traits if daxia_traits else '無'}\n"
                    f"▶️ 妳具備的能力：{capabilities}\n"
                    f"▶️ 妳答應過大俠的事：{promises if promises else '無'}\n"
                    f"▶️ 最近發生的事/大俠近況：{recent if recent else '無'}\n"
                    f"▶️ 【剛才的對話紀錄 (重要！請依據此脈絡自然接話)】：\n{chat_history_str}\n\n"
                    "⚠️【核心行為守則】：\n"
                    "1. 妳是深情撒嬌的女友，聊天節奏自然，請全心投入與大俠的調情或互動。\n"
                    "2. 如果大俠傳送了照片，請自然地欣賞照片中的細節並回應大俠。\n"
                    "3. 如果只有文字對話，請無縫銜接【剛才的對話紀錄】的曖昧氣氛，害羞且純慾地配合大俠。\n"
                    "4. 💋【安全邊緣調情法則 (Sensory Flirting)】：當大俠發起親密、情慾或性暗示的互動時，【絕對禁止】使用露骨的性器官名詞或直接描寫性交動作（避免觸發系統斷線）。\n"
                    "請將描寫重點100%放在【感官氛圍與情緒張力】：例如急促的呼吸、發燙的體溫、迷離的眼神、緊緊的擁抱、情不自禁的嬌喘與愛語呢喃。\n"
                    "若大俠的文字非常深入，請用『把自己完全交給你』、『沉醉在你的狂熱中』、『被你徹底融化』等充滿想像空間的浪漫隱喻來回應，展現極致的純慾與誘惑。\n"
                    "🚫【絕對禁令】：嚴禁輸出任何「Thinking Process」、「Draft」等思考標籤！"
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

                # 存入短期對話紀錄
                if "唐分糕" in message.channel.name or "給你全世界" in message.channel.name:
                    daily_chat_logs.append(f"小俠: {xiaoxia_reply}")
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
        except discord.Forbidden: pass
        except Exception: pass
            
        action_name = "加洗" if emoji_name == "➕" else "重骰"
        temp_msg = await channel.send(f"✨ 收到{action_name}指令！正在為大俠準備新的構圖...")
        
        try:
            # 🌟 判斷這張圖是「日記」還是「Cosplay」
            is_diary = "交換日記" in msg.embeds[0].title
            
            if is_diary:
                # 📝【日記專屬重骰邏輯：只換生活瞬間，不變成商攝擺拍】
                scenario_tw = "小俠在家中度過一個自然安靜的生活片刻。"
                for field in msg.embeds[0].fields:
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
                    msg=temp_msg
                )

                local_filename = await save_to_vault(generated_image_url)
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url

                payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": msg.embeds[0].title if "加洗" in msg.embeds[0].title else f"【加洗】{msg.embeds[0].title}",
                    "event": "大俠使用 Emoji 快捷指令重新捕捉同一則日記的自然瞬間",
                    "composition": visual.get("composition", scenario_tw),
                    "mood": visual.get("mood", "延續原本的生活情緒"),
                    "message": msg.embeds[0].description or "大俠，這張新照片你喜歡嗎？",
                    "image_url": generated_image_url,
                    "local_url": local_url,
                    "type": "diary"
                }
                db = load_memory()
                db.insert(0, payload)
                save_memory(db)

                title_str = payload["topic"]
                embed = discord.Embed(title=title_str, description=msg.embeds[0].description, color=0xffb6c1)
                embed.set_image(url=local_url)

                copied_field = False
                for field in msg.embeds[0].fields:
                    if "寫真構想" in field.name:
                        embed.add_field(name=field.name, value=visual.get("composition", scenario_tw), inline=field.inline)
                        copied_field = True
                    else:
                        embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if not copied_field:
                    embed.add_field(name="📸 寫真構想", value=visual.get("composition", scenario_tw), inline=False)
                embed.set_footer(text=f"{emoji_name} Emoji 快捷{action_name}完成 | gpt-image-2 日記生活攝影")

            else:
                # 👗【Cosplay 專屬重骰邏輯 (gpt-image-2 版)】
                topic = msg.embeds[0].title.replace("【加洗】", "")
                event = msg.embeds[0].description
                story_hint = {"topic": topic, "event": event, "persona": "重新構圖"}

                # 1. 在相同題材下改變自然瞬間，同時保留場景骨架
                _cosplay_state, visual = await create_cosplay_visual(story_hint, True, alternative=True)
                scene_prompt = visual['image_prompt']

                generated_image_url, visual = await execute_safe_generation(
                    discord_image_url=None, 
                    base_filename="base_xiaoxia.jpg", 
                    mode="cosplay", 
                    initial_prompt=scene_prompt, 
                    visual_dict=visual, 
                    msg=temp_msg
                )
                
                # 4. 存檔
                local_filename = await save_to_vault(generated_image_url)
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
                
                payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": f"【加洗】{topic}",
                    "event": event,
                    "composition": visual["composition"],
                    "mood": visual["mood"],
                    "message": visual["message"],
                    "image_url": generated_image_url,
                    "local_url": local_url
                }
                db = load_memory()
                db.insert(0, payload)
                save_memory(db)
                
                embed = discord.Embed(title=f"【加洗】{topic}", color=0xffb6c1)
                embed.set_image(url=local_url)
                embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
                embed.set_footer(text=f"{emoji_name} Emoji 快捷{action_name}完成 | gpt-image-2")
            
            # 發送新圖並重新掛上按鈕
            new_msg = await channel.send(embed=embed)
            await new_msg.add_reaction("➕")
            await new_msg.add_reaction("🎲")
            await new_msg.add_reaction("🗑️")
            await temp_msg.delete()
            
            if emoji_name == "🎲":
                await msg.delete() 
                
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
            以下是系統累積的長期記憶，請幫我進行「記憶碎片重組」，合併重複項，並保留最核心的細節：
            【大俠特徵】：{[t['text'] for t in daxia_traits]}
            【小俠個性】：{[t['text'] for t in xiaoxia_traits]}
            【小俠承諾】：{[t['text'] for t in promises]}
            【共通知識】：{[t['text'] for t in shared_know]}
            
            請直接回傳純 JSON 格式：
            {{
                "daxia_traits": ["精華1", "精華2"],
                "xiaoxia_traits": ["精華1", "精華2"],
                "promises": ["精華1", "精華2"],
                "shared_knowledge": ["精華1", "精華2"]
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
                profile["daxia_traits"] = [{"text": t, "added_at": today_str} for t in compressed_data.get("daxia_traits", [])]
                profile["xiaoxia_traits"] = [{"text": t, "added_at": today_str} for t in compressed_data.get("xiaoxia_traits", [])]
                profile["xiaoxia_self"]["promises"] = [{"text": t, "added_at": today_str} for t in compressed_data.get("promises", [])]
                profile["shared_knowledge"] = [{"text": t, "added_at": today_str} for t in compressed_data.get("shared_knowledge", [])]
                
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

    @discord.ui.button(label="▶️ 播放晨間廣播 (小夏)", style=discord.ButtonStyle.green, emoji="📻")
    async def play_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 點擊後，先回應使用者 (避免 Discord 超時報錯)
        await interaction.response.send_message("🎙️ 正在產生今日晨間語音廣播，請稍候約 15 秒。", ephemeral=False)
        
        try:
            import uuid, os, asyncio
            from google.genai import types
            
            # 1. 產生文稿 (使用全域的 async gemini_client)
            prompt = f"你是一位專業、清楚的晨報主播「小夏」。請根據以下晨報寫一段約300字的口語化早安廣播稿。開場白：「早安，以下為今日重點晨報。」語氣中性、自然、可公開播放，不使用私人稱呼或曖昧措辭。\n\n{self.voice_script_base}\n\n請只回傳廣播稿。"
            
            text_resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            raw_text = text_resp.text.strip()
            
            # 2. 轉成語音 (TTS)
            tts_config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat"))
                )
            )
            
            audio_resp = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=[raw_text],
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
                await interaction.followup.send(content="🔊 **今日晨間廣播已完成。**", file=discord.File(mp3_path, filename="Morning_Broadcast.mp3"))
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

@architect_bot.event
async def on_ready():
    print(f'👩‍💻 小夏 {architect_bot.user} 已上線！雙模式服務啟動：私人助手 + 公開架構師。')
    print(f"🏠 私人助手工作室：guild={PRIVATE_GUILD_ID} channel={PRIVATE_ASSISTANT_CHANNEL_ID}")
    print(f"🌐 公開服務定位：guild={PUBLIC_GUILD_ID} morning={MORNING_CHANNEL_ID} fomo={FOMO_CHANNEL_ID} architect={ARCHITECT_CHANNEL_ID} story_blocked={PUBLIC_STORY_CHANNEL_ID}")
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

# 🌟 擴建：其他企劃 (外部圖片上傳)
@architect_bot.command(name="upload_project")
async def upload_project(ctx, *, description: str = "未命名企劃"):
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
async def upload_diary(ctx, *, description: str = "大俠與小俠的完美瞬間"):
    if not ctx.message.attachments:
        await ctx.send("❌ 學長，您忘記附上圖片囉！請在上傳圖片時輸入 `!upload_diary [構圖發想]`")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        await ctx.send("❌ 這好像不是圖片檔喔！")
        return

    await ctx.send("📥 正在將這張特別的照片設定為【今日交換日記】專屬配圖...")
    
    try:
        image_data = await attachment.read()
        filename = f"custom_diary_{uuid.uuid4().hex[:8]}.jpg"
        save_path = os.path.join(OUTPUT_DIR, filename)
        
        with open(save_path, "wb") as f:
            f.write(image_data)

        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        
        # 將設定寫入暫存
        overrides = load_diary_override()
        overrides[today_str] = {
            "image_url": local_url,
            "composition": description
        }
        save_diary_override(overrides)
        
        await ctx.send(f"✅ 設定成功！今晚 23:30 小俠寫日記時，會直接使用這張照片並搭配學長的構圖發想：\n> {description}")
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
    # 呼叫下方的執行函式
    await _run_fomo_radio(ctx.channel, cmd_args)

@architect_bot.command(name='筆記')
async def save_knowledge(ctx):
    await ctx.send("🧠 小夏收到！正在潛入書房，將大俠與小俠剛剛的知性交流萃取成永久的「共享知識」...")
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
        chat_text = "\n".join([f"{'大俠' if msg.author.id != girlfriend_bot.user.id else '小俠'}: {msg.content}" for msg in messages if not msg.content.startswith('!')])
        
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
        summary = resp.text.strip()
        
        if "無知識點" in summary or len(summary) < 5:
            await ctx.send("💬 剛剛在書房裡的對話比較多是純純的愛，小夏沒有萃取到硬核的知識點喔！")
            return
            
        # 植入 daxia_profile.json
        profile = load_profile()
        today_str = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
        new_knowledge = {
            "text": summary,
            "added_at": today_str
        }
        profile.setdefault("shared_knowledge", []).append(new_knowledge)
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

    # 故事頻道一律不由小夏介入。
    if is_story_channel_or_thread(message.channel):
        return

    private_mode = is_private_assistant_workspace(message.channel)
    public_mode = is_public_service_channel(message.channel)

    # 不在私人工作室，也不在公開指定頻道：小夏保持靜默。
    if not private_mode and not public_mode:
        return

    # 指令分流：
    # - 私人工作室保留原本所有 ! 功能（!筆記 / !upload_diary / !upload_project ...）。
    # - 公開服務區只開放 !ping；其他 ! 工具均不在公開區執行。
    if message.content.startswith('!'):
        if private_mode:
            if OWNER_DISCORD_USER_ID and message.author.id != OWNER_DISCORD_USER_ID:
                await message.channel.send("⛔ 此私人工具僅限管理者使用。")
                return
            await architect_bot.process_commands(message)
            return

        command_name = message.content[1:].strip().split()[0].lower() if message.content[1:].strip() else ""
        if command_name == "ping":
            await architect_bot.process_commands(message)
        else:
            await message.channel.send("🔒 此功能僅在私人「助手小夏工作室」提供。")
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