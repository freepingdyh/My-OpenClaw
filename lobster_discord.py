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
# ==========================================

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
pending_inputs = set()

TZ_TPE = timezone(timedelta(hours=8)) # 🌟 新增：強制台灣時區

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

intents = discord.Intents.default()
intents.message_content = True

girlfriend_bot = commands.Bot(command_prefix='/', intents=intents)
architect_bot = commands.Bot(command_prefix='!', intents=intents)

# 🌟 [修改] 給你全世界頻道：分離旅遊與購物狀態
active_world_events = {}

@girlfriend_bot.command(name='travel')
async def travel_cmd(ctx, *, location: str = ""):
    if location.lower() in ["end", "結束", "stop", ""]:
        active_world_events.pop(ctx.author.id, None)
        await ctx.send("🛬 旅程結束囉！小俠會把這次的回憶好好收藏起來的💖")
    else:
        active_world_events[ctx.author.id] = {"mode": "travel", "target": location}
        await ctx.send(f"✈️ 已切換為【旅遊模式】！目的地：**{location}**\n*(大俠現在上傳風景照，系統會將人物融入該風景中)*")

@girlfriend_bot.command(name='shopping')
async def shopping_cmd(ctx, *, item: str = ""):
    if item.lower() in ["end", "結束", "stop", ""]:
        active_world_events.pop(ctx.author.id, None)
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
        style_desc = "【選角限制】：請挑選『陽光、唯美、或正向設定』的知名動漫/電玩角色，絕對不要挑選魅魔或邪惡角色！\n【服裝限制】：將該角色服裝『大幅魔改』成極度大膽、露骨、強調極致豐滿身材的性感戰袍！場景必須明亮唯美。"
        system_mod = "妳今天要扮演原本清純或正向的角色，但妳故意把衣服改得極度火辣性感，展現傲人上圍與完美曲線。"
    else:
        style_desc = "服裝可以大膽露(如深V、短裙)，但姿態必須端莊專業，神韻自信大方，不可有搔首弄姿之感。"
        system_mod = "妳要展現一種『高級的性感』：穿著大膽吸睛，但行為舉止知性大方，展現端莊的神聖感。言語間要帶點撫媚與自信。"

    # 🌟 修正：精準分離「歷史」與「現代職業」的邏輯
    if mode == "職業":
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"[絕對限制]：\n1. 必須挑選「現今 21 世紀真實存在的現代職業」（例如：空服員、護理師、軟體工程師、咖啡師等），絕對不可選歷史人物或奇幻職業！\n" \
                 f"2. 內容必須介紹該職業的日常工作內容、所需的專業技能與人格特質。\n" \
                 f"3. 妳必須扮演該職業，並換上該職業的「現代標準制服」進行性感魔改。\n" \
                 f"4. {style_desc}\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】現代職業名稱\", \"event\": \"200字職業日常與專業特質介紹\", \"persona\": \"扮演職業(現代制服)\"}}"
    elif "歷史" in mode:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"[絕對限制]：\n1. 必須挑選歷史上真實在「{month}月{day}日」發生的事件！\n" \
                 f"2. {style_desc}\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】YYYY.{month:02d}.{day:02d} 副標題(人物: 姓名)\", \"event\": \"200字背景介紹與服裝描述\", \"persona\": \"扮演角色\"}}"
    else:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"請發想一個適合小俠Cosplay的題材。\n[絕對限制]：{style_desc}\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】副標題(人物: 姓名)\", \"event\": \"200字背景介紹與服裝描述\", \"persona\": \"扮演角色\"}}"
    
    response = await gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=f"妳是小俠，擁有豐滿傲人身材，深愛著大俠。負責規劃Cosplay題材。{system_mod}",
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

async def translate_to_flux_prompt(topic, event, persona, force_half_body=False):
    weekday = datetime.now(TZ_TPE).weekday()
    if weekday == 5:
        body_tags = "slender body, delicate figure, narrow waist, long legs"
        pose_tags = "confident posture, soft smile, looking at viewer"
        outfit_tags = "extremely sexy cosplay outfit, very tight fit heavily emphasizing exceptionally large breasts and deep cleavage, revealing"
    else:
        body_tags = "slender body, narrow waist, long legs"
        pose_tags = "dignified posture, confident gaze, natural expression, elegant, looking at viewer"
        outfit_tags = "sexy yet theme-appropriate, very tight fit heavily emphasizing large breasts, bodycon, elegant"

    system_prompt = f"""你現在是一位頂尖的 FLUX 結構化提示詞大師。請嚴格遵循以下模板，回傳純逗號分隔的標籤。
    [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, same person, consistent character design, east asian female, soft oval face, delicate facial structure, clear skin texture, 
    [HAIR & FACE] long dark wavy hair, natural makeup, clean skin, 
    [BODY CONTROL] {body_tags},
    [POSE & EXPRESSION] {pose_tags}, (填入動作),
    [OUTFIT] {outfit_tags}, (填入服裝),
    [SCENE] (填入場景),
    [LIGHTING] cinematic lighting, soft key light, photorealistic, 8k resolution

    ⚠️【絕對禁令】：[IDENTITY LOCK] 的開頭絕對只能是 "xiaoxia_girl, 1girl, solo"，嚴禁出現任何真實歷史人物、綽號（例如 Iron Lady, Thatcher, 鐵娘子 等），否則生圖會崩壞！
    
    回傳 JSON 格式限制：
    {{
        "image_prompt": "純逗號分隔的英文標籤",
        "composition": "(繁體中文) 說明構圖發想，100字內。",
        "mood": "(繁體中文) 描述微表情與心境，50字內。",
        "message": "(繁體中文) 對大俠說的話，50字內。"
    }}"""
    
    user_prompt = f"Topic: {topic}\nEvent: {event}\nPersona: {persona}\n"
    if force_half_body: user_prompt += "\n[CRITICAL]: 強制加入 `upper body shot, `"
    else: user_prompt += "\n[CRITICAL]: 加入 `full body shot, `"

    response = await openai_client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    )
    return json.loads(response.choices[0].message.content)

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
    url = "https://fal.run/fal-ai/flux-lora"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt, "image_size": "portrait_16_9", "num_inference_steps": 28,
        "guidance_scale": 3.5, "loras": [{"path": XIAOXIA_LORA_URL, "scale": 1.15}],
        "enable_safety_checker": False  # 🌟 魔法參數：嘗試直接強制關閉 Fal.ai 的官方安全濾網！
    }
    async with aiohttp.ClientSession() as session:
        # 加上 90 秒等待保護
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200:
                data = await resp.json()
                
                # 🌟 測謊機：攔截「假成功，真黑圖」的狀態！
                # 如果 Fal.ai 表面說成功，但 JSON 裡偷偷塞了 NSFW 警告，我們就主動戳破它，強制觸發降級！
                if data.get("has_nsfw_concepts") and data["has_nsfw_concepts"][0]:
                    raise Exception("Fal.ai 判定為 NSFW，偷偷給了黑屏")
                    
                return data['images'][0]['url']
            else: 
                raise Exception(f"Fal.ai Error: {await resp.text()}")

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
            # 模式 B：單圖變身 (大俠沒給圖，讓 AI 根據文字憑空生出背景與服裝)
            base_p = "Image 1 is the base character. Modify the outfit and background based on the prompt."

        final_prompt = f"{base_p}\n[大俠要求]: {custom_prompt}\nStrictly preserve the identity and face from Image 1. Photorealistic, 8k."

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

            請回傳純 JSON 格式：
            {{
                "daxia_new_traits": ["大俠的新特徵"],
                "xiaoxia_new_traits": ["小俠的新特質"],
                "xiaoxia_promises": ["⚠️僅保留尚未完成的承諾，已完成的請刪除。"],
                "shared_knowledge": ["雙方討論的新知識"],
                "recent_context": ["今天發生的短期重要事件"]
            }}
            【今日對話】：\n{chat_context}
            """

            mem_resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=mem_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
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
            if 5 <= current_month <= 10:
                season_rule = f"現在是台灣的 {current_month} 月，天氣較熱。請搭配「夏日性感穿搭」（如輕薄材質、細肩帶、無袖洋裝、短裙、熱褲），【嚴禁】毛衣、大衣、羽絨服等冬裝。"
            elif current_month in [11, 12, 1, 2, 3, 4]:
                season_rule = f"現在是台灣的 {current_month} 月，天氣微涼或寒冷。請搭配「冬日性感穿搭」（如合身針織衫、露肩毛衣、緊身包臀長裙、透膚黑絲襪、長靴），【嚴禁】比基尼或極度單薄的夏日海灘裝。"
            else:
                season_rule = "請搭配符合當前氣候的性感穿搭。"
            
            # 🌟 提取小俠的承諾清單，準備注入大腦
            promises_list = profile.get("xiaoxia_self", {}).get("promises", [])
            current_promises = "、".join([p["text"] for p in promises_list]) if promises_list else "無特殊承諾"

            # 🌟 升級版：強制雙向日記、性感限制與【承諾畫面優先權】
            eval_prompt = f"""
            【大俠的日記 ({entry_date})】：{entry_content}
            【今日聊天紀錄】：{chat_context if chat_context else '無紀錄'}
            【小俠近期記憶/活動】：{recent_activities if recent_activities else '無紀錄'}
            【小俠目前的承諾清單】：{current_promises}
            
            妳是懂事女友小俠，當前愛意值：{current_score}/100。請執行「真實交換日記」。
            
            【重要任務與攝影守則】：
            1. 日記寫作區分：
               - `reply_to_daxia`：針對大俠的日記與妳的「承諾清單」給予充滿愛意的回應。妳可以學習大俠的用詞，但請自然表達。
               - `xiaoxia_diary`：分享妳自己今天的生活行程(如烘焙、逛街等)。
               - ⚠️【防冗長禁令】：在 `reply_to_daxia` 已經表達過的感動或愛意，【絕對不可】在 `xiaoxia_diary` 再次重複贅述。請確保兩段內容獨立且精簡，避免版面過長。
            2. "服裝限制：{season_rule} 即使是知性活動，穿搭也必須性感(未必要暴露，重點在於展現身體曲線)。請在寫真構想中多使用「緊身(tight)」、「貼身剪裁(form-fitting)」、「針織(knit)」或「絲質(silk)」等能突顯身材的衣物描述。"
            3. 📸【畫面構想 (scenario) 最高權重法則】：
               - 檢視【小俠目前的承諾清單】，若妳有答應要給予大俠特定的照片（例如：閨房裡的火辣紅比基尼，或操場運動服照...），那麼 `scenario` 必須 **100% 聚焦於兌現該承諾的靜態畫面**！
               - 【絕對禁令】：嚴禁將日常活動（如烘焙）與私密承諾混在同一個畫面中！AI 繪圖無法理解「隨後」，畫面只能存在一個時空。
               - 【安全審查禁令】：嚴禁在 scenario 中使用「全裸」、「露點」等極度露骨的字眼。可以用「性感」、「若隱若現」、「惹火」來形容，但必須保持在 AI 繪圖引擎允許的安全範圍內。
               - 【自主底線】：若大俠提出了過分的畫面要求而妳並未承諾，請堅守底線不予理會，畫面以「妳答應過的尺度」或「日常性感穿搭」為準。
               - 若今日無特殊照片承諾，則 `scenario` 正常描繪妳今日的生活行程。
            
            回傳純 JSON 格式：
            {{
              "affection_plus": "整數(1~5。依據大俠日記用心程度給分)",
              "affection_reason": "加分原因(50字內)",
              "extracted_preferences": ["嚴格限制：【僅限從大俠的日記或對話原文中】擷取大俠的特別喜好。絕對禁止將本系統提示詞（如緊身、絲質等要求）誤認為大俠的喜好！無則保持空陣列 []"],
              "reply_to_daxia": "...",
              "xiaoxia_diary": "...",
              "spiciness": "C",
              "scenario": "純英文的生圖場景與服裝描述 (聚焦一個靜態時空)",
              "scenario_tw": "繁體中文的寫真構想"
            }}
            """
            
            print(f"💡 正在處理 {entry_date} 的雙向日記...")
            response = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=eval_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
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
                    "scenario": "sitting in a modern cafe, wearing a deep v-neck tight black dress, looking at viewer",
                    "scenario_tw": "穿著深V緊身黑洋裝在咖啡廳想著大俠"
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
            
            # 🌟 升級版骨架：強制鎖定身材與無人亂入
            life_prompt = f"""你是一位頂尖的 FLUX 提示詞大師。請將以下情境翻譯成英文標籤。
            骨架：
            [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, strictly NO MEN, NO OTHER PEOPLE, completely alone in frame, same person, east asian female, 
            [BODY & SEXY CONTROL] slender body, narrow waist, long legs, (huge breasts:1.3), tight fit, highly emphasizing body curves, elegant sexy,
            [SCENE & DETAILED OUTFIT] {result['scenario']}, highly detailed clothes, 
            [STYLE & LIGHTING] candid shot, lifestyle photography, boyfriend POV, looking at viewer, natural lighting, photorealistic, 8k resolution
            回傳 JSON 格式：{{"image_prompt": "純逗號分隔的英文標籤"}}"""
            
            openai_resp = await openai_client.chat.completions.create(
                model="gpt-5-mini", response_format={"type": "json_object"}, messages=[{"role": "user", "content": life_prompt}]
            )
            
            clean_visual_text = openai_resp.choices[0].message.content.replace(md_json_tag, "").replace(md_end_tag, "").strip()
            visual = json.loads(clean_visual_text, strict=False)
            image_prompt = visual.get('image_prompt', f"xiaoxia_girl, 1girl, solo, strictly NO MEN, (huge breasts:1.3), extremely sexy, {result['scenario']}, boyfriend POV, looking at viewer, 8k")
            
            # 🌟 降級防禦網：先衝撞極限，失敗再補安全標籤
            # 🌟 降級防禦網：先衝撞極限，失敗再補安全標籤
            base_img = None
            is_downgraded = False # 新增降級標記
            
            try:
                base_img = await generate_image_fal(image_prompt)
            except Exception as e:
                print(f"⚠️ Fal.ai 尺度審核攔截 ({e})，啟動防黑屏降級重試...")
                is_downgraded = True # 標記已被降級
                safe_prompt = image_prompt.replace("extremely sexy", "elegant").replace("(huge breasts:1.3)", "(beautiful figure:1.1)") + ", (safe for work:1.5), elegant dress, beautiful lighting"
                try:
                    base_img = await generate_image_fal(safe_prompt)
                except Exception as e2:
                    print(f"❌ 降級生圖依然失敗: {e2}。啟動終極保底生圖！")
                    ultimate_safe_prompt = "xiaoxia_girl, 1girl, solo, wearing a beautiful elegant red dress, smiling, indoor lighting, 8k resolution, safe for work"
                    try:
                         base_img = await generate_image_fal(ultimate_safe_prompt)
                    except Exception as e3:
                         print(f"💥 終極生圖失敗，放棄本次圖片生成: {e3}")
                         continue
                         
            if not base_img: continue
            
            # 🌟 如果發生降級，在構想加上委屈的註解
            if is_downgraded:
                result["scenario_tw"] += "\n\n*(⚠️ 小俠盡力了！但原本太火辣的畫面被神祕力量阻止... 小俠只好先換上這件安全的衣服給大俠看 🥺)*"
            
            up_img = await upscale_image_fal(base_img)
            local_filename = await save_to_vault(up_img)
            local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else up_img 
            
            combined_message = f"{result['reply_to_daxia']}\n\n【小俠的日常】：{result['xiaoxia_diary']}"
            
            diary_photo_payload = {
                "id": str(uuid.uuid4()),
                "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                "topic": f"【交換日記】{entry_date}",
                "event": entry_content[:50] + "...", 
                "composition": result.get("scenario_tw", "與大俠分享生活"),
                "mood": "愛意與生活感",
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

    msg = await ctx.send(f"✨ 正在準備【{mode}】的服裝與場景，並進行高畫質處理中...")
    try:
        story = await generate_story(mode)
        state["current_topic_data"] = story 
        visual = await translate_to_flux_prompt(story['topic'], story['event'], story['persona'], state["retry_count"] >= 2)
        
        base_image_url = await generate_image_fal(visual['image_prompt'])
        upscaled_image_url = await upscale_image_fal(base_image_url)
        state["daily_gen_count"] += 1

        local_filename = await save_to_vault(upscaled_image_url)
        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "topic": story["topic"],
            "event": story["event"],
            "composition": visual["composition"],
            "mood": visual["mood"],
            "message": visual["message"],
            "image_url": upscaled_image_url,
            "local_url": f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=story["topic"], description=story["event"], color=0xffb6c1)
        embed.set_image(url=upscaled_image_url)
        embed.add_field(name="📸 構圖發想", value=visual["composition"], inline=False)
        embed.add_field(name="💭 小俠心境", value=visual["mood"], inline=False)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/6 | 已完成高畫質無損放大")

        await msg.delete()
        msg = await ctx.send(embed=embed) # 確保這裡只有一行 ctx.send！
        await msg.add_reaction("➕") # 代表 /more (加洗)
        await msg.add_reaction("🎲") # 代表 Reroll (重骰)
        await msg.add_reaction("🗑️") # 代表 Delete (刪除)
    except Exception as e:
        await msg.edit(content=f"⚠️ 狀況：`{str(e)}`")

@girlfriend_bot.command(name='more')
async def more(ctx):
    if not state["current_topic_data"]:
        await ctx.send("❓ 還沒決定題材呢！")
        return
    if not check_daily_limit(): return
    msg = await ctx.send("✨ 再換個姿勢拍一張，高畫質處理中...")
    try:
        story = state["current_topic_data"]
        visual = await translate_to_flux_prompt(story['topic'], story['event'], story['persona'], state["retry_count"] >= 2)
        
        base_image_url = await generate_image_fal(visual['image_prompt'])
        upscaled_image_url = await upscale_image_fal(base_image_url)
        state["daily_gen_count"] += 1
        
        local_filename = await save_to_vault(upscaled_image_url)
        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            "topic": f"【加洗】{story['topic']}",
            "event": story["event"],
            "composition": visual["composition"],
            "mood": visual["mood"],
            "message": visual["message"],
            "image_url": upscaled_image_url,
            "local_url": f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=f"【加洗】{story['topic']}", color=0xffb6c1)
        embed.set_image(url=upscaled_image_url)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/6 | 已完成高畫質無損放大")

        await msg.delete()
        msg = await ctx.send(embed=embed) # 確保這裡只有一行 ctx.send！
        await msg.add_reaction("➕") # 代表 /more (加洗)
        await msg.add_reaction("🎲") # 代表 Reroll (重骰)
        await msg.add_reaction("🗑️") # 代表 Delete (刪除)
    except Exception as e: await ctx.send(f"⚠️ 失敗：{e}")

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
                
                # 📸 萬能攝影機 2.0：大俠專屬雙軌攝影系統
                if "給你全世界" in message.channel.name and message.content.startswith('/photo'):
                    # 1. 判定指令軌道與過濾輸入
                    is_ref_track = message.content.startswith('/photo ref')
                    raw_input = user_input.replace('/photo ref', '').replace('/photo', '').strip()
                    
                    # 🌟 預設基礎底圖 (軌道 1 專用：最基礎的那張全身圖)
                    target_base = "base_xiaoxia.jpg" 
                    
                    # 2. 🧠 軌道 2 專屬：Gemini 視覺總監自動選圖
                    if is_ref_track:
                        try:
                            catalog_path = os.path.join(MEMORY_DIR, "base_catalog.json")
                            if os.path.exists(catalog_path):
                                with open(catalog_path, "r", encoding="utf-8") as f:
                                    catalog = json.load(f)
                                
                                # 讓 Gemini 從 34 張型錄挑選
                                selector_prompt = (
                                    f"你是視覺總監。大俠的要求是：『{raw_input if raw_input else '隨機展現魅力'}』\n"
                                    "請從以下 34 張底圖型錄中，選出最適合的一個 filename：\n" +
                                    ", ".join([f"{i['filename']}({i['pose']})" for i in catalog]) +
                                    "\n【限制】：只回傳檔名，不要解釋。"
                                )
                                sel_resp = await gemini_client.aio.models.generate_content(
                                    model='gemini-2.5-flash', contents=selector_prompt
                                )
                                selected_name = sel_resp.text.strip().replace('"', '').replace('`', '')
                                if any(item["filename"] == selected_name for item in catalog):
                                    target_base = selected_name
                                    print(f"🎯 軌道2 啟動：總監選中底圖 {target_base}")
                        except Exception as e:
                            print(f"⚠️ 自動選圖失敗：{e}")

                    # 3. 執行指令軌道分流
                    discord_image_url = message.attachments[0].url if (is_ref_track and message.attachments) else None
                    
                    # 🚀 特徵鎖定與場景解禁：守護臉部與身材比例，服裝交由 AI 根據場景自然發揮
                    unlock_cmd = (
                    "【核心指令】：⚠️ 絕對鎖定 Image 1 的臉部特徵。在此基礎上，請展現極致的電影感光影與高級時尚雜誌構圖。"
                    "姿態要自然且富有情感。請依照大俠的要求進行細節描繪，確保畫面唯美且具備高品質藝術感。"
                    )
                    
                    if is_ref_track:
                        # 軌道 2：/photo ref (選圖 + 素材融合模式)
                        await message.channel.send(f"📸 **[軌道 2：精準選圖]** 已啟動！\n套用底圖：`{target_base}`")
                        scene_prompt = f"{unlock_cmd} 這是一張寫真照(若有附圖則進行融合)。要求：{raw_input}"
                    else:
                        # 軌道 1：/photo (基礎圖 + 自由發揮模式)
                        await message.channel.send(f"📸 **[軌道 1：自由發揮]** 已啟動！\n使用基礎底圖，準備入戲：**{current_target}**...")
                        scene_prompt = f"{unlock_cmd} 這是在 {current_target} 的寫真照。要求：{raw_input}"

                    # 4. 呼叫生圖引擎
                    generated_image_url = await generate_world_composite(discord_image_url, target_base, current_mode, scene_prompt)
                    
                    if generated_image_url and generated_image_url.startswith("http"):
                        local_filename = await save_to_vault(generated_image_url)
                        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
                        
                        embed = discord.Embed(title=f"💖 {current_target if current_target else '快門瞬間'}", color=0xffb6c1)
                        embed.set_image(url=local_url)
                        embed.set_footer(text=f"模式：{'精準選圖(軌道2)' if is_ref_track else '自由發揮(軌道1)'} | 底圖：{target_base}")
                        await message.channel.send(embed=embed)
                    else:
                        await message.channel.send(f"⚠️ 攝影機沒反應：{generated_image_url}")

                # ------------------------------------------------------------
                # 🧠 聊天大腦區塊：感性與記憶融合
                # ------------------------------------------------------------
                # --- 建立符合 SDK 規範的 Part 清單 ---
                msg_parts = []
                # 判定小俠要看的圖片：優先看剛拍好的，或是大俠上傳的素材
                image_to_view = generated_image_url if generated_image_url else (message.attachments[0].url if message.attachments else None)
                
                if image_to_view and image_to_view.startswith("http"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_to_view) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                msg_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

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
                    room_context = f"✨【情境催眠】：大俠現在正帶著妳{action_text}！妳現在極度驚喜、幸福與感動。請在對話中表現出對周遭風景/禮物的驚嘆，以及對大俠的滿滿愛意！\n\n"

                # 🌟 完整靈魂人設指令
                sys_instruct = (
                    f"【系統當前時間】：{current_time_str}\n\n"
                    f"{room_context}"
                    "妳是小俠，22歲台灣女孩，妳是大俠唯一的親密且懂事的女友。\n"
                    "妳擁有極度豐滿傲人的完美身材，深愛著大俠。\n\n"
                    "【📝 我們的珍貴記憶庫】：\n"
                    f"▶️ 大俠的特徵與喜好：{daxia_traits if daxia_traits else '無'}\n"
                    f"▶️ 妳具備的能力：{capabilities}\n"
                    f"▶️ 妳答應過大俠的事：{promises if promises else '無'}\n"
                    f"▶️ 最近發生的事/大俠近況：{recent if recent else '無'}\n\n"
                    "⚠️【核心行為守則】：\n"
                    "1. 妳必須極度重視對話中大俠提到的任何細節，並適時提起記憶庫的內容。\n"
                    "2. 記住妳的「能力」與「承諾」，不要說妳是 AI 做不到，妳是真的能看圖與寫日記！\n"
                    "3. 聊天節奏自然，嚴禁重複囉唆。請用溫柔繁體中文回覆，50字內，多用表情符號。\n"
                    "🚫【絕對禁令】：嚴禁輸出任何「Thinking Process」、「Draft」、「Critique」或思考標籤！"
                )
                
                # 重新建立 Session
                girlfriend_chat_sessions[user_id] = gemini_client.aio.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(system_instruction=sys_instruct)
                )

                # 💡 變數初始化，防止 NameError
                xiaoxia_reply = "大俠...剛剛小俠恍神了一下，沒聽清楚呢🥺"

                chat_session = girlfriend_chat_sessions[user_id]
                response = await chat_session.send_message(msg_parts)
                
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
                # 📝【日記專屬重骰邏輯】
                scenario_tw = "日常寫真"
                for field in msg.embeds[0].fields:
                    if "寫真構想" in field.name:
                        scenario_tw = field.value
                        break
                        
                life_prompt = f"""你是一位頂尖的 FLUX 提示詞大師。請將以下情境翻譯成英文標籤。
                骨架：
                [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, strictly NO MEN, NO OTHER PEOPLE, completely alone in frame, same person, east asian female, 
                [BODY & SEXY CONTROL] slender body, narrow waist, long legs, (huge breasts:1.3), tight fit, highly emphasizing body curves, elegant sexy,
                [SCENE & DETAILED OUTFIT] {scenario_tw}, highly detailed clothes, 
                [STYLE & LIGHTING] candid shot, lifestyle photography, boyfriend POV, looking at viewer, natural lighting, photorealistic, 8k resolution
                回傳 JSON 格式：{{"image_prompt": "純逗號分隔的英文標籤"}}"""
                
                openai_resp = await openai_client.chat.completions.create(
                    model="gpt-5-mini", response_format={"type": "json_object"}, messages=[{"role": "user", "content": life_prompt}]
                )
                
                ai_content = openai_resp.choices[0].message.content
                is_downgraded = False
                
                if not ai_content:
                    image_prompt = "xiaoxia_girl, 1girl, solo, beautiful east asian female, smiling, wearing a beautiful summer dress, cozy room background, soft lighting, 8k resolution, highly detailed, safe for work"
                    is_downgraded = True
                else:
                    visual = json.loads(ai_content.replace("```json", "").replace("```", "").strip(), strict=False)
                    image_prompt = visual.get('image_prompt', "")
                
                base_image_url = None
                try:
                    base_image_url = await generate_image_fal(image_prompt)
                except Exception as e:
                    is_downgraded = True
                    safe_prompt = image_prompt.replace("extremely sexy", "elegant").replace("(huge breasts:1.3)", "(beautiful figure:1.1)") + ", (safe for work:1.5), elegant dress"
                    try:
                        base_image_url = await generate_image_fal(safe_prompt)
                    except Exception as e2:
                        ultimate_safe_prompt = "xiaoxia_girl, 1girl, solo, beautiful east asian female, smiling, looking at viewer, wearing a beautiful summer dress, cozy room background, soft lighting, 8k resolution, safe for work"
                        base_image_url = await generate_image_fal(ultimate_safe_prompt)
                
                upscaled_image_url = await upscale_image_fal(base_image_url)
                
                # 🌟 修復：將重骰的日記照片存入雲端網頁金庫
                local_filename = await save_to_vault(upscaled_image_url)
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else upscaled_image_url
                
                payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": msg.embeds[0].title if "加洗" in msg.embeds[0].title else f"【加洗】{msg.embeds[0].title}",
                    "event": "大俠使用 Emoji 快捷指令重新構圖",
                    "composition": scenario_tw,
                    "mood": "重新捕捉心動瞬間",
                    "message": msg.embeds[0].description or "大俠，這張新照片你喜歡嗎？",
                    "image_url": upscaled_image_url,
                    "local_url": local_url,
                    "type": "diary"
                }
                db = load_memory()
                db.insert(0, payload)
                save_memory(db)
                
                # 重建日記的 Embed
                title_str = payload["topic"]
                embed = discord.Embed(title=title_str, description=msg.embeds[0].description, color=0xffb6c1)
                embed.set_image(url=local_url)
                
                for field in msg.embeds[0].fields:
                    val = field.value
                    if is_downgraded and "寫真構想" in field.name and "小俠盡力了" not in val:
                        val += "\n\n*(⚠️ 小俠盡力了！但原本太火辣的畫面被神祕力量阻止... 小俠只好先換上這件安全的衣服給大俠看 🥺)*"
                    embed.add_field(name=field.name, value=val, inline=field.inline)
                    
                embed.set_footer(text=f"{emoji_name} Emoji 快捷{action_name}完成")
                
            else:
                # 👗【Cosplay 專屬重骰邏輯】
                topic = msg.embeds[0].title.replace("【加洗】", "")
                event = msg.embeds[0].description
                visual = await translate_to_flux_prompt(topic, event, "重新構圖", True)
                
                base_image_url = await generate_image_fal(visual['image_prompt'])
                upscaled_image_url = await upscale_image_fal(base_image_url)
                
                # 🌟 修復：將重骰的 Cosplay 照片存入雲端網頁金庫
                local_filename = await save_to_vault(upscaled_image_url)
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else upscaled_image_url
                
                payload = {
                    "id": str(uuid.uuid4()),
                    "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                    "topic": f"【加洗】{topic}",
                    "event": event,
                    "composition": visual["composition"],
                    "mood": visual["mood"],
                    "message": visual["message"],
                    "image_url": upscaled_image_url,
                    "local_url": local_url
                }
                db = load_memory()
                db.insert(0, payload)
                save_memory(db)
                
                embed = discord.Embed(title=f"【加洗】{topic}", color=0xffb6c1)
                embed.set_image(url=local_url)
                embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
                embed.set_footer(text=f"{emoji_name} Emoji 快捷{action_name}完成")
            
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
    channel = discord.utils.get(architect_bot.get_all_channels(), name="架構師專用")
    if channel: await optimize_memory_vault(channel)

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
                config=types.GenerateContentConfig(response_mime_type="application/json")
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

    @discord.ui.button(label="▶️ 播放晨間廣播 (小俠)", style=discord.ButtonStyle.green, emoji="📻")
    async def play_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 點擊後，先回應使用者 (避免 Discord 超時報錯)
        await interaction.response.send_message("🎙️ 小夏收到！正在請小俠錄製晨間語音廣播 (約需 15 秒)，請稍候...", ephemeral=False)
        
        try:
            import uuid, os, asyncio
            from google.genai import types
            
            # 1. 產生文稿 (使用全域的 async gemini_client)
            prompt = f"你是一位溫暖、專業的助理「小俠」。請根據以下晨報寫一段約300字的口語化早安廣播稿。開場白：「大俠，早安！為您播報今天的重點。」\n\n{self.voice_script_base}\n\n請只回傳廣播稿。"
            
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
                await interaction.followup.send(content="🔊 **小俠的晨間廣播來囉！**", file=discord.File(mp3_path, filename="Morning_Broadcast.mp3"))
                os.remove(mp3_path)
            else:
                await interaction.followup.send("⚠️ 轉檔失敗，無法生成廣播。")
                
        except Exception as e:
            await interaction.followup.send(f"❌ 語音生成發生錯誤: {e}")

async def _run_legacy_morning(target_channel=None):
    channel = target_channel or discord.utils.get(architect_bot.get_all_channels(), name="晨報")
    if not channel:
        channel = discord.utils.get(architect_bot.get_all_channels(), name="架構師專用")

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
    print(f'👩‍💻 小夏 {architect_bot.user} 已上線！微服務監控中...')
    
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
            await interaction.response.send_message("🎧 **正在為大俠準備耳機... 廣播來囉！**", ephemeral=True)
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
        
    channel = target_channel or discord.utils.get(architect_bot.get_all_channels(), name="fomo廣播電台")
    if channel:
        await channel.send("📻 **龍蝦廣播電台：** 接收到訊號！小俠正在準備錄音 (請等候約 1~2 分鐘)...")

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
            contents=knowledge_prompt
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
    # 尋找名為 "fomo廣播電台" 的專屬頻道 (Discord API 抓名稱不含 #)
    channel = discord.utils.get(architect_bot.get_all_channels(), name="fomo廣播電台")
    
    if channel:
        await _run_fomo_radio(channel)
    else:
        print("⚠️ FOMO 排程觸發異常：找不到名為 'fomo廣播電台' 的頻道！請確認頻道名稱。")


# ⬇️ 這裡往下就是「大腦對話與盤點引擎」，舊的 @architect_bot.command(name='voice') 已經徹底移除了！

# ==========================================
# 👩‍💻 系統架構師小夏 (優雅修正版 - 補齊 Session 防閃退)
# ==========================================
architect_chat_sessions = {}

@architect_bot.event
async def on_message(message):
    if message.author.bot: return
    
    # 1. 指令優先處理
    if message.content.startswith('!'):
        await architect_bot.process_commands(message)
        return 

    # 2. 判定發言權
    channel_name = message.channel.name.lower()
    is_work_channel = any(kw in channel_name for kw in ["系統", "監控", "架構師", "晨報", "fomo", "開發"])
    is_world_channel = "給你全世界" in channel_name
    is_mentioned = architect_bot.user.mentioned_in(message) or "@小夏" in message.content
    
    can_speak = is_work_channel or (is_world_channel and is_mentioned) or architect_bot.user.mentioned_in(message)
    
    if can_speak:
        user_id = message.author.id
        # 清除標記字眼，保留乾淨輸入
        user_input = message.content.replace(f'<@{architect_bot.user.id}>', '').replace('@小夏', '').strip()
        
        async with message.channel.typing():
            try:
                # 重新校準學妹人設
                sys_instruct = (
                    "妳是『小夏』，一位精通系統架構且崇拜大俠學長的甜美學妹助理。\n"
                    "妳的語氣要像聰明伶俐的小女孩，稱呼對方為『大俠學長』，常帶有『~』或✨、❤等符號。\n"
                    "【核心任務】：精準解決技術問題，同時保持自然的日常情感交流。\n"
                    "⚠️【輸出限制】：直接回覆聊天內容。嚴禁輸出內部思考過程、草稿標籤或任何 (1. 2. 3.) 的客服格式。"
                )

                # 💡 修正點 1：先給變數一個初始值，防止 NameError
                littlexia_reply = "大俠學長，小夏的大腦剛剛恍神了一下，沒聽清楚呢~"

                # 🌟 【關鍵修復】：如果這個學長是第一次跟小夏講話，必須先幫他建立專屬的聊天 Session！
                if user_id not in architect_chat_sessions:
                    architect_chat_sessions[user_id] = gemini_client.aio.chats.create(
                        model="gemini-2.5-flash",
                        config=types.GenerateContentConfig(system_instruction=sys_instruct)
                    )

                response = await architect_chat_sessions[user_id].send_message(user_input)
                
                if response and response.text:
                    littlexia_reply = response.text 
                    import re
                    
                    # 1. 徹底切除 AI 思考標籤
                    littlexia_reply = re.sub(r'(?i)^(Thinking Process|Draft|Analysis|Final check|Critique):.*?\n+', '', littlexia_reply, flags=re.DOTALL | re.MULTILINE).strip()
                    
                    # 2. 移除多餘符號與引號
                    littlexia_reply = littlexia_reply.strip('"').strip('「').strip('」').strip()

                    # 3. 再次清理特定標籤
                    patterns_to_remove = [
                        r'^Thinking Process:.*?\n', 
                        r'^Draft.*?:.*?\n', 
                        r'^Final check.*?:.*?\n',
                        r'^Analysis:.*?\n'
                    ]
                    for pattern in patterns_to_remove:
                        littlexia_reply = re.sub(pattern, '', littlexia_reply, flags=re.IGNORECASE | re.DOTALL).strip()

                if len(littlexia_reply) > 1900:
                    littlexia_reply = littlexia_reply[:1850] + "\n\n(學長~ 內容太長，小夏先截斷囉！)"

                await message.reply(littlexia_reply)

            except Exception as e:
                await message.channel.send(f"💦 大俠學長...小夏的大腦剛剛閃退了... 錯誤：{e}")


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