# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版 - 雙核共生終極版)
# ==========================================

import os
import json
import uuid
import asyncio
import aiohttp
import aiofiles
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

# --- 運行時變數 ---
diary_buffers = {}            
girlfriend_chat_sessions = {} 
daily_chat_logs = []          # 🌟 新增：今日聊天紀錄(供午夜結算)
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
    if os.path.exists(PROFILE_DATA_PATH):
        with open(PROFILE_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"preferences": []} # 大俠長期喜好

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
        outfit_tags = "sexy yet theme-appropriate, deep V-neck heavily emphasizing large breasts and cleavage, tight fit, elegant"

    system_prompt = f"""你現在是一位頂尖的 FLUX 結構化提示詞大師。請嚴格遵循以下模板，回傳純逗號分隔的標籤。
    [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, same person, consistent character design, east asian female, soft oval face, delicate facial structure, clear skin texture, 
    [HAIR & FACE] long dark wavy hair, natural makeup, clean skin, 
    [BODY CONTROL] {body_tags},
    [POSE & EXPRESSION] {pose_tags}, (填入動作),
    [OUTFIT] {outfit_tags}, (填入服裝),
    [SCENE] (填入場景),
    [LIGHTING] cinematic lighting, soft key light, photorealistic, 8k resolution
    
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
# 🌟 日記回覆與生活感引擎 (The Heart of Xiaoxia)
# ==========================================
async def process_diary_reply(channel, target_date=None):
    global daily_chat_logs
    
    # --- 階段 1：本機資料庫讀取與防呆 ---
    try:
        app_state = load_state()
    except Exception as e:
        if channel: await channel.send(f"⚠️ `xiaoxia_state.json` 損毀: {e}")
        return
        
    try:
        profile = load_profile()
    except Exception as e:
        if channel: await channel.send(f"⚠️ `daxia_profile.json` 損毀: {e}")
        return
        
    diary_db = []
    if os.path.exists(DIARY_DATA_PATH):
        try:
            with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
                diary_db = json.load(f)
        except Exception as e:
            if channel: await channel.send(f"⚠️ 嚴重錯誤：日記檔案損毀！\n錯誤：`{e}`")
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
    
    if not unreplied and not chat_context:
        if channel: await channel.send("📝 大俠目前沒有未讀的日記或新對話需要回覆喔！")
        return

    if channel and len(unreplied) > 0:
        await channel.send(f"⏳ 發現 {len(unreplied)} 篇未讀日記！小俠正在一篇一篇認真閱讀與回信，大俠請稍候喔...")

    md_json_tag = chr(96) * 3 + "json"
    md_end_tag = chr(96) * 3

    # --- 階段 3：迴圈「獨立裝甲處理」每一篇日記 ---
    for entry in unreplied:
        try:
            current_score = app_state.get("affection_score", 80)
            entry_date = entry['date']
            entry_content = entry['content']
            
            eval_prompt = f"""
            【大俠的這篇日記 ({entry_date})】：
            {entry_content}
            
            【今日聊天紀錄補充】：
            {chat_context if chat_context else '無紀錄'}
            
            請以懂事女友小俠的身份進行評估，並「專門針對這篇日記的內容」給予回覆。妳的當前愛意值為：{current_score}/100。
            
            【重要限制】：請回傳純 JSON 格式。文字內「絕對不可」使用雙引號 (") 與實體換行符號。
            {{
              "affection_plus": 1,
              "extracted_preferences": ["喜好1"],
              "reply": "50字內給大俠的專屬回信",
              "spiciness": "A",
              "scenario": "standing in kitchen cooking, wearing a red off-shoulder sweater, looking at viewer",
              "scenario_tw": "穿著紅色露肩毛衣在廚房做菜，深情看著大俠"
            }}
            
            - affection_plus: 1到5的整數。
            - extracted_preferences: 萃取大俠喜好，無則 []。
            - reply: 給大俠的專屬回信 (必須扣緊這篇日記的內容)。
            - spiciness: "A", "B" 或 "C"。若 current_score + affection_plus >= 100，強制選 "C"。
            - scenario: 一句英文情境照描述。【極度重要警告】：
              1. 必須是單人場景 (1girl solo)！絕對不可出現男人或其他人物！請一律用「看著鏡頭 (looking at viewer)」來表現陪伴！
              2. 必須具體描述服裝的「顏色與款式」(例如 red dress, black silk pajama)，不要只寫 casual clothes！
              3. 【防黑屏機制】：若尺度為 C，請著重於「誘惑姿態、性感睡衣、男友襯衫」，但「絕對不可裸露點位或過度暴露」，以免被生圖系統判定違規變成黑畫面！
            - scenario_tw: 用繁體中文描述上述的寫真構想，讓大俠知道妳為什麼想拍這張照片。
            """
            
            print(f"💡 正在處理 {entry_date} 的日記...")
            response = await gemini_client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=eval_prompt,
                config=types.GenerateContentConfig(
                    system_instruction="妳是小俠，負責產出回信與情境。嚴格輸出 JSON，防黑屏且必須指定服裝顏色。",
                    response_mime_type="application/json"
                )
            )
            
            clean_text = response.text.replace(md_json_tag, "").replace(md_end_tag, "").strip()
            
            try:
                result = json.loads(clean_text, strict=False)
                if "reply" not in result: raise ValueError("JSON 缺少 reply 欄位")
            except Exception as e:
                print(f"⚠️ Gemini JSON 異常 ({e})，啟動保底救援！")
                result = {
                    "affection_plus": 1, "extracted_preferences": [],
                    "reply": "大俠，小俠讀這篇日記時有點恍神了... 但不管多忙多累，小俠都會在這裡陪你喔！（抱）",
                    "spiciness": "A", "scenario": "sitting on a cozy sofa, wearing a warm pink oversized sweater, looking at viewer",
                    "scenario_tw": "穿著溫暖的粉紅色寬大毛衣坐在沙發上，靜靜陪著大俠"
                }
            
            # 🌟 拆分顯示分數與底層分數
            new_score = current_score + result["affection_plus"]
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
                if pref not in profile["preferences"]: profile["preferences"].append(pref)
            save_profile(profile)
            
            life_prompt = f"""你是一位頂尖的 FLUX 提示詞大師。請將以下情境翻譯成英文標籤。
            骨架：
            [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, strictly one person, completely alone in frame, NO MEN, NO OTHER PEOPLE, same person, east asian female, soft oval face, delicate facial structure, clear skin texture, 
            [HAIR] long dark wavy hair, natural makeup, clean skin, 
            [BODY] slender body, delicate figure, large breasts, narrow waist, 
            [SCENE & DETAILED OUTFIT] {result['scenario']}, highly detailed clothes, 
            [STYLE & LIGHTING] candid shot, lifestyle photography, boyfriend POV, natural lighting, photorealistic, 8k resolution
            回傳 JSON 格式：{{"image_prompt": "純逗號分隔的英文標籤"}}"""
            
            openai_resp = await openai_client.chat.completions.create(
                model="gpt-5-mini", response_format={"type": "json_object"}, messages=[{"role": "user", "content": life_prompt}]
            )
            
            clean_visual_text = openai_resp.choices[0].message.content.replace(md_json_tag, "").replace(md_end_tag, "").strip()
            
            try:
                visual = json.loads(clean_visual_text, strict=False)
                if "image_prompt" not in visual: raise ValueError("缺少 image_prompt")
            except Exception as e:
                visual = {"image_prompt": f"xiaoxia_girl, 1girl, solo, strictly one person, NO MEN, east asian female, long dark wavy hair, slender body, delicate figure, large breasts, {result['scenario']}, candid shot, photorealistic, 8k resolution"}
            
            base_img = await generate_image_fal(visual['image_prompt'])
            up_img = await upscale_image_fal(base_img)
            local_filename = await save_to_vault(up_img)
            
            if local_filename:
                local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            else:
                local_url = up_img 
                print(f"⚠️ {entry_date} 本機存檔失敗，改用雲端網址備援！")
            
            # 🌟 新增：將「日常陪伴」的照片同步存入主相簿金庫
            diary_photo_payload = {
                "id": str(uuid.uuid4()),
                "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                "topic": f"【日常陪伴】{entry_date} 專屬回信",
                "event": entry_content[:50] + "..." if len(entry_content) > 50 else entry_content, 
                "composition": result.get("scenario_tw", "與大俠享受專屬的兩人時光"),
                "mood": "滿滿的愛意與撫慰",
                "message": result["reply"],
                "image_url": up_img,
                "local_url": local_url,
                "type": "diary"  # 👈 讓前端相片總覽能抓到
            }
            
            try:
                db = load_memory()
                db.insert(0, diary_photo_payload)
                save_memory(db)
            except Exception as e:
                print(f"⚠️ 同步寫入主相簿失敗：{e}")
            
            reply_html = (
                "<br><hr style='margin-top: 15px; border-top: 1px dashed #fbcfe8;'>"
                "<p style='color:#db2777; font-weight:bold; font-size: 12px; margin-top:10px;'>🌸 小俠的專屬回信：</p>"
                f"<img src='{local_url}' style='width:100%; border-radius:8px; margin-bottom:10px; cursor:pointer;' onclick='openGalleryLightbox(this.src)'>"
                f"<p style='color:#be185d; font-size: 14px;'>{result['reply']}</p>"
            )
            
            entry["content"] += reply_html
            entry["is_replied"] = True
            
            with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(diary_db, f, ensure_ascii=False, indent=2)
                
            if channel:
                title = f"💖 小俠的深度撫慰 [{entry_date}] (盲盒大獎！)" if is_jackpot else f"💌 小俠的專屬回信 [{entry_date}]"
                embed = discord.Embed(title=title, description=result['reply'], color=0xffb6c1)
                embed.set_image(url=local_url)
                scenario_tw_text = result.get("scenario_tw", "與大俠享受專屬的兩人時光")
                embed.add_field(name="📸 寫真構想", value=scenario_tw_text, inline=False)
                embed.set_footer(text=f"愛意值: {display_score}/100 (+{result['affection_plus']}) | 尺度: {result['spiciness']}")
                await channel.send(f"✅ 已完成 **{entry_date}** 的日記回覆！", embed=embed)

        except Exception as e:
            if channel: await channel.send(f"⚠️ 處理 **{entry.get('date', '未知日期')}** 時遇到亂流：`{str(e)}`。跳過此篇，馬上為您處理下一篇！")
            print(f"[{entry.get('date')}] 處理錯誤: {e}")
            continue

    girlfriend_chat_sessions.clear()
    daily_chat_logs.clear()

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
    msg = await ctx.send("✨ 正在細細閱讀大俠的日記與今日對話，小俠整理思緒中...")
    await process_diary_reply(ctx.channel, date_str)
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
                msg_parts.append(types.Part.from_text(text=text_query))
                
                # 紀錄到深夜日記系統
                daily_chat_logs.append(f"大俠: {text_query} {'(附帶圖片)' if message.attachments else ''}")

                # C. 取得或建立 Session (注入長期記憶)
                if user_id not in girlfriend_chat_sessions:
                    # ✅ 讀取大俠的長期記憶圖鑑
                    profile = load_profile()
                    prefs = "、".join(profile.get("preferences", []))
                    pref_text = f"【大俠的長期喜好與回憶】：{prefs}。" if prefs else ""
                    
                    sys_instruct = (
                        "妳是小俠，22歲台灣女孩，大俠的懂事女友。"
                        "妳擁有極度豐滿傲人的完美身材，深愛著大俠。"
                        f"{pref_text}\n"
                        "⚠️【核心行為守則】：\n"
                        "1. 妳必須極度重視對話中大俠提到的任何細節（如食物、心情、計畫、剛聊過的話題）。\n"
                        "2. 這些對話是妳們共同的珍貴回憶，妳絕對不准說出『我不記得』、『考倒我了』或『想不起來』這種傷人的話！\n"
                        "3. 即使妳真的模糊，也要用溫柔撒嬌的方式引導大俠，而不是推卸責任說妳是 AI。\n"
                        "4. 請用繁體中文回覆，50字內，適當加入表情符號。妳能看見大俠傳來的照片，請觀察並熱情回應。"
                    )
                    
                    girlfriend_bot.chat_session_history = [] # 重置歷史緩衝
                    girlfriend_chat_sessions[user_id] = gemini_client.aio.chats.create(
                        model="gemini-2.5-flash",
                        config=types.GenerateContentConfig(system_instruction=sys_instruct)
                    )

                # D. 發送 Part 清單並取得回應
                chat_session = girlfriend_chat_sessions[user_id]
                response = await chat_session.send_message(msg_parts)
                
                小俠回覆 = response.text
                daily_chat_logs.append(f"小俠: {小俠回覆}")
                await message.reply(小俠回覆)

            except Exception as e:
                print(f"❌ 聊天引擎異常: {e}")
                await message.channel.send(f"💦 大俠，小俠剛剛眼睛好像進沙子了，看不清楚... (錯誤: {e})")

# ==========================================
# ⏰ 自動排程系統
# ==========================================
@tasks.loop(time=time(hour=21, minute=30, tzinfo=TZ_TPE))
async def auto_cosplay_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="唐分糕")
    if channel: await cosplay(channel, mode="auto")

@tasks.loop(time=time(hour=0, minute=0, tzinfo=TZ_TPE))
async def midnight_feedback_task():
    channel = discord.utils.get(girlfriend_bot.get_all_channels(), name="唐分糕")
    if channel: await process_diary_reply(channel)

# ==========================================
# 👩‍💻 系統架構師小夏 (維護與監控指令區)
# ==========================================
@architect_bot.event
async def on_ready():
    print(f'👩‍💻 小夏 {architect_bot.user} 已上線！微服務監控中...')

@architect_bot.command(name='ping')
async def ping(ctx):
    await ctx.send("🟢 系統運作正常，小俠的金庫與雙核 API 皆已在線，隨時聽候大俠差遣。")


import re

@girlfriend_bot.command(name='sync_diary_photos')
async def sync_diary_photos(ctx):
    msg = await ctx.send("🔍 小夏正在進行「深層掃描」並修復照片格式...")
    
    try:
        diary_db = []
        if os.path.exists(DIARY_DATA_PATH):
            with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
                diary_db = json.load(f)
                
        photos_db = load_memory()
        synced_count = 0
        
        for entry in diary_db:
            if entry.get("is_replied"):
                content = entry.get("content", "")
                entry_date = entry.get("date", "未知日期")
                
                # 🌟 精準抓取圖片網址與回信文字
                img_match = re.search(r"<img src='([^']+)'", content)
                reply_match = re.search(r"<p style='color:#be185d; font-size: 14px;'>([^<]+)</p>", content)
                
                if img_match and reply_match:
                    img_url = img_match.group(1)
                    reply_text = reply_match.group(1)
                    
                    # 檢查金庫，如果已有「同網址」但「格式錯」的舊紀錄，先刪除舊的再補新的
                    photos_db = [p for p in photos_db if p.get("local_url") != img_url and p.get("image_url") != img_url]
                    
                    # ✅ 關鍵：封裝正確的 JSON 格式給前端 index.html 使用
                    diary_photo_payload = {
                        "id": str(uuid.uuid4()),
                        "publish_date": entry_date + " 23:59:59",
                        "topic": f"【日常陪伴】{entry_date}",
                        "event": f"大俠在 {entry_date} 的日記回憶...", 
                        "composition": "與大俠享受專屬的兩人時光",
                        "mood": "滿滿的愛意與撫慰",
                        "message": reply_text,
                        "image_url": img_url,
                        "local_url": img_url,
                        "type": "diary"  # 👈 前端分流顯示的唯一通行證
                    }
                    
                    photos_db.insert(0, diary_photo_payload)
                    synced_count += 1
                        
        if synced_count > 0:
            save_memory(photos_db)
            await msg.edit(content=f"✅ 成功修復並同步 **{synced_count}** 張照片！大俠請重整網頁看看。")
        else:
            await msg.edit(content="⚠️ 報告大俠！日記裡似乎沒有可提取的照片喔。")
            
    except Exception as e:
        await msg.edit(content=f"❌ 修復過程異常：{str(e)}")

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