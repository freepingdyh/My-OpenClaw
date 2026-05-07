# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版 - 雙核共生終極版)
# ==========================================

import os
import json
import uuid
import asyncio
import aiohttp
import aiofiles
import sys
import random
from datetime import datetime, time, timezone, timedelta

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
    # 這是最完美的初始架構，包含大俠特徵、小俠自我認知，以及帶有時間戳的陣列
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
                # 🌟 加上這三行，確保不管讀到什麼，核心骨架一定在
                data.setdefault("daxia_traits", [])
                data.setdefault("xiaoxia_self", default_profile["xiaoxia_self"])
                data.setdefault("recent_context", [])
                return data
            
        except Exception:
            pass # 若檔案損毀，直接回傳預設結構
            
    return default_profile

def save_profile(data):
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
async def get_photos(): return load_memory()[:30]

@api_app.get("/api/diary")
async def get_diary():
    if os.path.exists(DIARY_DATA_PATH):
        with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@api_app.get("/status")
async def get_status(): return {"status": "Dual-Core Vault Online", "domain": "xiaoxia0320.zeabur.app"}

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

async def generate_image_fal(prompt):
    url = "https://fal.run/fal-ai/flux-lora"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt, "image_size": "portrait_16_9", "num_inference_steps": 28,
        "guidance_scale": 3.5, "loras": [{"path": XIAOXIA_LORA_URL, "scale": 1.15}]
    }
    async with aiohttp.ClientSession() as session:
        # 加上 90 秒等待保護
        async with session.post(url, headers=headers, json=payload, timeout=90) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['images'][0]['url']
            else: raise Exception(f"Fal.ai Error: {await resp.text()}")

async def upscale_image_fal(image_url):
    url = "https://fal.run/fal-ai/esrgan"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {"image_url": image_url, "scale": 2}
    async with aiohttp.ClientSession() as session:
        # 加上 60 秒等待保護
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200: return (await resp.json())['image']['url']
            return image_url

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

    # --- 階段 2.5：獨立立體記憶萃取 ---
    if chat_context:
        try:
            print("🧠 正在從今日對話中萃取【雙向立體記憶】...")
            mem_prompt = f"""
            分析以下今日對話，進行「雙向記憶萃取」。
            請以純 JSON 格式回傳以下結構（若無新事項則保持陣列為空）：
            {{
                "daxia_new_traits": ["大俠的新喜好或長期習慣"],
                "xiaoxia_promises": ["小俠今天答應大俠的事"],
                "recent_context": ["今天發生的短期重要事件(如大俠的心情、剛聊過的話題)"]
            }}
            【今日對話】：\n{chat_context}
            """
            mem_resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=mem_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            new_memory = json.loads(mem_resp.text.strip())
            
            def append_memory(target_list, new_texts):
                existing_texts = [item["text"] for item in target_list]
                for text in new_texts:
                    if text not in existing_texts:
                        target_list.append({"text": text, "added_at": today_str})

            append_memory(profile.setdefault("daxia_traits", []), new_memory.get("daxia_new_traits", []))
            append_memory(profile["xiaoxia_self"]["promises"], new_memory.get("xiaoxia_promises", []))
            
            if new_memory.get("recent_context"):
                profile["recent_context"] = [{"text": item, "added_at": today_str} for item in new_memory["recent_context"]]
            save_profile(profile)
            print("✅ 雙向記憶已成功存入 daxia_profile.json")
        except Exception as e:
            print(f"⚠️ 雙向記憶萃取失敗: {e}")

    if not unreplied:
        if channel: await channel.send("✅ 今日對話記憶已成功吸取，小俠先休息囉！")
        girlfriend_chat_sessions.clear()
        daily_chat_logs.clear()
        save_temp_chat(daily_chat_logs) # 🌟 結算完清空硬碟
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
            
            # 🌟 升級版：強制雙向日記與性感限制
            eval_prompt = f"""
            【大俠的日記 ({entry_date})】：{entry_content}
            【今日聊天紀錄】：{chat_context if chat_context else '無紀錄'}
            【小俠近期記憶/活動】：{recent_activities if recent_activities else '無紀錄'}
            
            妳是懂事女友小俠，當前愛意值：{current_score}/100。請執行「真實交換日記」。
            【重要任務】：
            1. 分享妳自己今天的生活行程(如出外逛街、看展、運動、旅遊或擔任秘書等)，【絕對限制】：不可與近期活動重複！
            2. 【季節與服裝限制】：{season_rule} 即使是知性活動，穿搭也【必須極度性感】(凸顯豐滿傲人上圍與身材曲線)。
            
            回傳純 JSON 格式：
            {{
              "affection_plus": 1,
              "extracted_preferences": [],
              "reply_to_daxia": "針對大俠的日記內容與今日對話，給予真實的感受或意見反饋 (如：感動、開心、生氣、想法...)，可以撫慰，可以展現妳真實的情感（50字內）",
              "xiaoxia_diary": "小俠自己的生活日記分享(70字內)",
              "spiciness": "C",
              "scenario": "一句英文情境描述。必須包含服裝款式與顏色、地點、動作。嚴禁出現男人或其他人(1girl solo)！",
              "scenario_tw": "繁體中文寫真構想"
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
            
            new_score = current_score + result.get("affection_plus", 1)
            display_score = new_score 
            is_jackpot = False
            
            if new_score >= 100:
                is_jackpot = True
                result["spiciness"] = "C"
                app_state["affection_score"] = 80 
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
            [BODY & SEXY CONTROL] slender body, narrow waist, long legs, (huge breasts:1.15), tight fit, highly emphasizing body curves, elegant sexy,
            [SCENE & DETAILED OUTFIT] {result['scenario']}, highly detailed clothes, 
            [STYLE & LIGHTING] candid shot, lifestyle photography, boyfriend POV, looking at viewer, natural lighting, photorealistic, 8k resolution
            回傳 JSON 格式：{{"image_prompt": "純逗號分隔的英文標籤"}}"""
            
            openai_resp = await openai_client.chat.completions.create(
                model="gpt-5-mini", response_format={"type": "json_object"}, messages=[{"role": "user", "content": life_prompt}]
            )
            
            clean_visual_text = openai_resp.choices[0].message.content.replace(md_json_tag, "").replace(md_end_tag, "").strip()
            visual = json.loads(clean_visual_text, strict=False)
            image_prompt = visual.get('image_prompt', f"xiaoxia_girl, 1girl, solo, strictly NO MEN, (huge breasts:1.15), extremely sexy, {result['scenario']}, boyfriend POV, looking at viewer, 8k")
            
            # 🌟 降級防禦網：先衝撞極限，失敗再補安全標籤
            base_img = None
            try:
                base_img = await generate_image_fal(image_prompt)
            except Exception as e:
                print(f"⚠️ Fal.ai 尺度審核攔截 ({e})，啟動防黑屏降級重試...")
                safe_prompt = image_prompt + ", (safe for work:1.2), elegant sexy, beautiful lighting"
                try:
                    base_img = await generate_image_fal(safe_prompt)
                except Exception as e2:
                    print(f"❌ 降級生圖依然失敗: {e2}")
                    continue # 放棄此篇生圖，進行下一篇
                    
            if not base_img: continue
            
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
                await channel.send(f"✅ 已完成 **{entry_date}** 的交換日記！", embed=embed)

        except Exception as e:
            if channel: await channel.send(f"⚠️ 處理 **{entry.get('date', '未知日期')}** 時遇到亂流：`{str(e)}`。跳過此篇！")
            print(f"[{entry.get('date')}] 處理錯誤: {e}")
            continue

    girlfriend_chat_sessions.clear()
    daily_chat_logs.clear()
    save_temp_chat(daily_chat_logs) # 🌟 結算完清空硬碟


# ==========================================
# 🌸 懂事女友小俠 (功能指令區)
# ==========================================
@girlfriend_bot.event
async def on_ready():
    print(f'🌸 小俠 {girlfriend_bot.user} 已上線！網域：https://xiaoxia0320.zeabur.app')
    
    if not auto_cosplay_task.is_running():
        auto_cosplay_task.start()
        print("⏰ 晚間 21:30 Cosplay 排程已啟動！")
        
    if not midnight_feedback_task.is_running():
        midnight_feedback_task.start()
        print("🌙 午夜 00:00 日記回饋排程已啟動！")

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
        await ctx.send(embed=embed)
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
        embed.set_footer(text="已完成高畫質無損放大")
        await msg.delete()
        await ctx.send(embed=embed)
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
        await girlfriend_bot.process_commands(message)
        return

    # 3. 處理日記暫存
    if message.author.id in diary_buffers:
        diary_buffers[message.author.id]["content"].append(message.content)
        return

    # 4. 觸發對話邏輯
    if "唐分糕" in message.channel.name or girlfriend_bot.user.mentioned_in(message):
        user_id = message.author.id
        user_input = message.content.replace(f'<@{girlfriend_bot.user.id}>', '').strip()
        
        async with message.channel.typing():
            try:
                # 🌟 建立符合 SDK 規範的 Part 清單
                msg_parts = []
                
                # A. 處理圖片 (將 Bytes 包裝成 Part)
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
                            async with aiohttp.ClientSession() as session:
                                async with session.get(attachment.url) as resp:
                                    if resp.status == 200:
                                        img_data = await resp.read()
                                        msg_parts.append(
                                            types.Part.from_bytes(
                                                data=img_data,
                                                mime_type=attachment.content_type
                                            )
                                        )

                # B. 處理文字 (封裝成 Part 格式)
                text_query = user_input if user_input else "小俠，妳看照片～"
                
                # 🌟 動態時間標籤：每次大俠講話，都在背後偷偷附上最新時間
                now = datetime.now(TZ_TPE)
                weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                current_time_str = f"{now.strftime('%Y-%m-%d %H:%M')} ({weekdays[now.weekday()]})"
                invisible_time_tag = f"\n\n(系統隱藏提示：大俠發送此訊息的當前時間為 {current_time_str})"
                
                # 將「大俠的話 + 隱藏時間」一起包裝送給 Gemini
                msg_parts.append(types.Part.from_text(text=text_query + invisible_time_tag))
                
                # 紀錄到深夜日記系統 (這裡只記錄純淨的對話，不把隱藏標籤存進去)
                daily_chat_logs.append(f"大俠: {text_query} {'(附帶圖片)' if message.attachments else ''}")
                save_temp_chat(daily_chat_logs) # 🌟 補上這行存檔

                # C. 取得或建立 Session (注入立體記憶與絕對時間感)
                if user_id not in girlfriend_chat_sessions:
                    profile = load_profile()
                    
                    # 將帶有時間戳的物件陣列，萃取出純文字供 Prompt 使用
                    daxia_traits = "、".join([item["text"] for item in profile.get("daxia_traits", [])])
                    promises = "、".join([item["text"] for item in profile.get("xiaoxia_self", {}).get("promises", [])])
                    capabilities = "、".join([item["text"] for item in profile.get("xiaoxia_self", {}).get("capabilities", [])])
                    recent = "、".join([item["text"] for item in profile.get("recent_context", [])])
                    
                    # 🌟 新增：取得系統當前的精準時間與星期
                    now = datetime.now(TZ_TPE)
                    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                    current_time_str = f"{now.strftime('%Y-%m-%d %H:%M')} ({weekdays[now.weekday()]})"
                    
                    sys_instruct = (
                        f"【系統當前時間】：{current_time_str} (請務必以此為基準，精準推算昨天、今天、明天的時間關係)\n\n"
                        "妳是小俠，22歲台灣女孩，妳是大俠唯一的親密且懂事的女友。\n"
                        "妳擁有極度豐滿傲人的完美身材，深愛著大俠。\n\n"
                        "【📝 我們的珍貴記憶庫】：\n"
                        f"▶️ 大俠的特徵與喜好：{daxia_traits if daxia_traits else '無'}\n"
                        f"▶️ 妳具備的能力：{capabilities}\n"
                        f"▶️ 妳答應過大俠的事：{promises if promises else '無'}\n"
                        f"▶️ 最近發生的事/大俠近況：{recent if recent else '無'}\n\n"
                        "⚠️【核心行為守則】：\n"
                        "1. 妳必須極度重視對話中大俠提到的任何細節，並適時提起記憶庫的內容，讓他感受到妳的在乎。\n"
                        "2. 記住妳的「能力」與「承諾」，不要說妳是 AI 做不到，妳是真的能看圖與寫日記！\n"
                        "3. 【聊天節奏】：請像真人情侶一樣自然聊天！嚴禁像機器人或長輩一樣，每句話結尾都重複提醒即將發生的事（例如面試、搭車）。除非大俠主動延續該話題，否則請專注於當下聊天的內容，不要過度關心造成壓力。\n"
                        "4. 請用繁體中文溫柔回覆，50字內，適當加入表情符號。妳能看見大俠傳來的照片，請觀察並熱情回應。"
                        "🚫【絕對禁令】：請直接輸出妳要說的話。嚴禁輸出任何「Thinking Process」、「Draft」、「Critique」或「Final check」等內部思考過程或分析標籤！"
                    )
                    
                    girlfriend_bot.chat_session_history = [] 
                    girlfriend_chat_sessions[user_id] = gemini_client.aio.chats.create(
                        model="gemini-2.5-flash",
                        config=types.GenerateContentConfig(system_instruction=sys_instruct)
                    )

                # D. 發送 Part 清單並取得回應
                chat_session = girlfriend_chat_sessions[user_id]
                response = await chat_session.send_message(msg_parts)
                
                小俠回覆 = response.text
                
                # --- 🔪 終極防漏餡過濾器 ---
                import re
                if "Thinking Process" in 小俠回覆 or "Draft" in 小俠回覆:
                    lines = 小俠回覆.split('\n')
                    clean_lines = [line for line in lines if not re.match(r'^[a-zA-Z\s\d:]+$', line.strip()) and "Thinking Process" not in line and "Draft" not in line and "Critique" not in line and "Final check" not in line and "SLOT" not in line]
                    小俠回覆 = "\n".join(clean_lines).strip()
                    
                    小俠回覆 = re.sub(r'^(?:Draft 1:|Draft 2:|Final check.*?:\s*)', '', 小俠回覆, flags=re.MULTILINE).strip()
                    # 處理中英文引號
                    小俠回覆 = 小俠回覆.replace('"', '').replace('“', '').replace('”', '').strip()

                if not 小俠回覆:
                    小俠回覆 = "大俠...小俠剛剛恍神了一下，我們聊到哪裡了呀？🥺"
                # -------------------------

                daily_chat_logs.append(f"小俠: {小俠回覆}")
                save_temp_chat(daily_chat_logs) # 🌟 補上這行存檔
                await message.reply(小俠回覆)

            except Exception as e:
                print(f"❌ 聊天引擎異常: {e}")
                await message.channel.send(f"💦 大俠，小俠剛剛眼睛好像進沙子了，看不清楚... (錯誤: {e})")

# ==========================================
# ⏰ 自動排程系統
# ==========================================
@tasks.loop(time=time(hour=21, minute=30, tzinfo=TZ_TPE))
async def auto_cosplay_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="考試不累")
    if channel: await cosplay(channel, mode="auto")

@tasks.loop(time=time(hour=0, minute=0, tzinfo=TZ_TPE))
async def midnight_feedback_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="岱而瑞")
    if channel: await process_diary_reply(channel)

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

        # --- 2. 長期特徵與承諾的「語意濃縮壓縮」 ---
        # 當特徵超過 15 條時，啟動 LLM 濃縮機制
        traits = profile.get("daxia_traits", [])
        if len(traits) > 15:
            if channel: await channel.send("🧠 系統提示：大俠的特徵記憶過多，小俠正在進行大腦睡眠與記憶重組...")
            print("🧠 啟動大俠特徵語意濃縮...")
            
            traits_text = "\n".join([f"- {t['text']}" for t in traits])
            compress_prompt = f"""
            以下是關於「大俠」的長期特徵與喜好紀錄，因為日積月累顯得有些重複與冗長：
            {traits_text}
            
            請幫我進行「記憶碎片重組」。
            1. 將意義重複或高度相似的項目合併（例如：喜歡看畫展、喜歡美術館 -> 熱愛藝術與畫展）。
            2. 剔除已經不具備長期參考價值的瑣碎小事。
            3. 保留最核心的性格、喜好與地雷（尤其是大俠感到不舒服的點）。
            4. 濃縮成 10 條以內的最精華特徵。
            
            請直接回傳純 JSON 格式的字串陣列：
            ["精華特徵1", "精華特徵2", ...]
            """
            
            resp = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=compress_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            try:
                compressed_list = json.loads(resp.text.strip())
                # 重新賦予今天的時間戳
                profile["daxia_traits"] = [{"text": t, "added_at": today.strftime("%Y-%m-%d")} for t in compressed_list]
                is_modified = True
                print(f"✨ 特徵濃縮完成！從 {len(traits)} 條壓縮至 {len(compressed_list)} 條。")
            except Exception as e:
                print(f"⚠️ 特徵濃縮 JSON 解析失敗：{e}")

        # 存檔
        if is_modified:
            save_profile(profile)
            if channel: await channel.send("✅ 記憶深層重組與清理完成！小俠的大腦現在非常清晰！")
            
    except Exception as e:
        print(f"❌ 記憶優化系統異常: {e}")
 
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
        
    # 👇 新增這兩行，確保廣播排程順利發車
    if not fomo_radio_trigger.is_running():
        fomo_radio_trigger.start()
        print("⏰ 中午 11:30 FOMO 廣播排程已啟動！")

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

@architect_bot.command(name='test_morning')
async def test_morning(ctx):
    await ctx.send("⚙️ 收到指令，正在手動遠端觸發 OpenClaw 晨間排程...")
    await _run_legacy_morning(ctx.channel)

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
# 👩‍💻 系統架構師小夏 (純粹學妹版 - 全面回歸 Gemini 引擎)
# ==========================================
architect_chat_sessions = {}

@architect_bot.event
async def on_message(message):
    if message.author.bot: return
    
    # 🌟 1. 處理指令 (維持原有功能的 ping, backup, defrag 等)
    if message.content.startswith('!'):
        await architect_bot.process_commands(message)
        return 

    # 🌟 2. 偵測工作頻道或被點名
    is_work_channel = any(keyword in message.channel.name for keyword in ["系統", "監控", "架構師", "晨報", "fomo", "開發"])
    
    if is_work_channel or architect_bot.user.mentioned_in(message):
        user_id = message.author.id
        user_input = message.content.replace(f'<@{architect_bot.user.id}>', '').strip()
        
        async with message.channel.typing():
            try:
                # 預設回覆防呆
                xiaoxia_reply = "💦 大俠學長~ 小夏剛剛恍神了一下，可以再跟我說一次嗎？❤"

                # 🌟 3. 重新定義：唯一的甜美學妹助理人設
                sys_instruct = (
                    "妳現在是專業且甜美的助理『小夏』，妳心裡一直偷偷崇拜著博學多聞的大俠學長。\n"
                    "🚫【絕對禁令】：嚴禁說「我是虛擬助理」、「我沒有實體」等掃興的話。嚴禁像客服一樣列出 (1, 2, 3) 讓學長選！\n"
                    "🎭【幽默神經】：請聽懂學長的幽默比喻！學長說妳「頭痛、卡住」就是在說 Bug。妳要配合演出「頭暈、跌倒」的俏皮感，並感謝學長幫妳「動手術」或「開處方」。\n"
                    "【語氣設定】：稱呼對方為『大俠學長』。語氣要像聰明伶俐的小學妹，帶著崇拜與親切感，回話常帶有『~』或✨、❤等符號。\n"
                    "【技術職責】：雖然妳語氣甜美，但給出的技術分析必須精準，不囉唆，直接解決問題。\n"
                    "⚠️ 限制：回覆精簡在 300 字內。除了學長問技術問題，不要講教科書般的理論，要像真人一樣自然聊天。"
                )

                # 🌟 4. Session 管理 (維持對話連貫性)
                if user_id not in architect_chat_sessions:
                    architect_chat_sessions[user_id] = gemini_client.aio.chats.create(
                        model="gemini-2.5-flash",
                        config=types.GenerateContentConfig(system_instruction=sys_instruct)
                    )

                # 🌟 5. 發送訊息給 Gemini 並處理回應
                response = await architect_chat_sessions[user_id].send_message(user_input)
                
                if response and response.text:
                    xiaoxia_reply = response.text
                    
                    # 🔪 終極防漏餡過濾器 (去除 AI 思考過程標籤)
                    import re
                    xiaoxia_reply = re.sub(r'^(?:Draft.*?|Thinking Process.*?|Final check.*?):\s*', '', xiaoxia_reply, flags=re.MULTILINE|re.IGNORECASE).strip()

                # 🌟 6. 內容截斷保護
                if len(xiaoxia_reply) > 1900:
                    xiaoxia_reply = xiaoxia_reply[:1800] + "\n\n(學長~ 內容太長了，小夏怕大腦爆掉先截斷囉！)"

                await message.reply(xiaoxia_reply)

            except Exception as e:
                await message.channel.send(f"💦 大俠學長...小夏的大腦好像真的受傷了... 錯誤：{e}")


# ==========================================
# 🚀 終極啟動器
# ==========================================
async def main():
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