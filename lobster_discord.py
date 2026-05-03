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
    filename = f"xiaoxia_{uuid.uuid4().hex[:8]}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                async with aiofiles.open(filepath, mode='wb') as f:
                    await f.write(await resp.read())
                return filename
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
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['images'][0]['url']
            else: raise Exception(f"Fal.ai Error: {await resp.text()}")

async def upscale_image_fal(image_url):
    url = "https://fal.run/fal-ai/esrgan"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {"image_url": image_url, "scale": 2}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200: return (await resp.json())['image']['url']
            return image_url

# ==========================================
# 🌟 日記回覆與生活感引擎 (The Heart of Xiaoxia)
# ==========================================
async def process_diary_reply(channel, target_date=None):
    global daily_chat_logs
    try:
        app_state = load_state()
        profile = load_profile()
        
        if not os.path.exists(DIARY_DATA_PATH): return
        with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
            diary_db = json.load(f)
            
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
            
        diary_texts = "\n\n".join([f"[{e['date']}]\n{e['content']}" for e in unreplied])
        current_score = app_state.get("affection_score", 80)
        
        # 🌟 大腦運作：愛意結算與記憶萃取 (防呆優化版 Prompt)
        eval_prompt = f"""
        【大俠今日聊天紀錄】：
        {chat_context if chat_context else '無紀錄'}
        
        【大俠未讀補登/今日日記】：
        {diary_texts if diary_texts else '無紀錄'}
        
        請以懂事女友小俠的身份進行綜合評估。妳的當前愛意值為：{current_score}/100。
        
        請嚴格遵守以下格式回傳純 JSON 資料 (絕對不可包含任何額外文字，且字串內若有引述，請一律改用『單引號』，嚴禁在字串中使用雙引號以免破壞 JSON 結構！)：
        {{
          "affection_plus": 1,
          "extracted_preferences": ["喜好1", "喜好2"],
          "reply": "50字內給大俠的專屬回信，語氣溫柔撫媚...",
          "spiciness": "A",
          "scenario": "standing in kitchen cooking, wearing a casual t-shirt"
        }}
        
        【JSON 欄位嚴格定義】：
        - affection_plus: (整數) 1=日常互動, 3=有明顯愛意或愛心符號, 5=強烈愛意/撒嬌/送禮物。
        - extracted_preferences: (字串陣列) 萃取大俠最新透露的喜好、生理狀態或特徵，無則輸出空陣列 []。
        - reply: (字串) 給大俠的專屬回信，總結上述日記或聊天。
        - spiciness: (字串) 只能是 "A", "B" 或 "C"。A=日常溫馨(60%), B=微辣撩人(30%), C=極致撫慰/大獎(10%)。若 current_score + affection_plus >= 100，強制輸出 "C"。
        - scenario: (字串) 用一句英文描述妳當下的生活情境照，必須配合 spiciness 尺度發想。
        """
        
        response = await gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=eval_prompt,
            config=types.GenerateContentConfig(
                system_instruction="妳是小俠，負責評估大俠的愛意並產出回信與情境。請嚴格輸出 JSON 格式。",
                response_mime_type="application/json"
            )
        )
        
        # 🌟 防呆：去除可能出現的 Markdown 標籤再解析 JSON
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        
        # 除錯用：如果還是報錯，可以在終端機看到 Gemini 到底回傳了什麼鬼東西
        print(f"--- Gemini 原始回傳 --- \n{clean_text}\n------------------------")
        
        result = json.loads(clean_text)
        
        # 結算分數與大獎
        new_score = current_score + result["affection_plus"]
        is_jackpot = False
        if new_score >= 100:
            is_jackpot = True
            new_score = 80 # 重置
            result["spiciness"] = "C"
            
        app_state["affection_score"] = new_score
        save_state(app_state)
        
        # 長期記憶注入
        for pref in result.get("extracted_preferences", []):
            if pref not in profile["preferences"]:
                profile["preferences"].append(pref)
        save_profile(profile)
        
        # 🌟 翻譯為生活感 FLUX Prompt
        life_prompt = f"""你是一位頂尖的 FLUX 提示詞大師。請將以下情境翻譯成英文標籤，去除 Cosplay 棚拍感，強調真實生活紀錄。
        骨架：
        [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, same person, consistent character design, east asian female, soft oval face, delicate facial structure, clear skin texture, 
        [HAIR] long dark wavy hair, natural makeup, clean skin, 
        [BODY] slender body, delicate figure, large breasts, narrow waist, 
        [SCENE & CASUAL OUTFIT] {result['scenario']},
        [STYLE & LIGHTING] everyday clothing, candid shot, lifestyle photography, natural lighting, photorealistic, 8k resolution
        回傳 JSON 格式：{{"image_prompt": "純逗號分隔的英文標籤"}}"""
        
        openai_resp = await openai_client.chat.completions.create(
            model="gpt-5-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": life_prompt}]
        )
        
        clean_visual_text = openai_resp.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        visual = json.loads(clean_visual_text)
        
        base_img = await generate_image_fal(visual['image_prompt'])
        up_img = await upscale_image_fal(base_img)
        local_filename = await save_to_vault(up_img)
        local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
        
        # 寫回 DB
        reply_html = f"<br><hr style='margin-top: 15px; border-top: 1px dashed #fbcfe8;'><p style='color:#db2777; font-weight:bold; font-size: 12px; margin-top:10px;'>🌸 小俠的專屬回信：</p><img src='{local_url}' style='width:100%; border-radius:8px; margin-bottom:10px; cursor:pointer;' onclick='openGalleryLightbox(this.src)'><p style='color:#be185d; font-size: 14px;'>{result['reply']}</p>"
        
        for e in diary_db:
            if e in unreplied:
                e["content"] += reply_html
                e["is_replied"] = True
                
        with open(DIARY_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(diary_db, f, ensure_ascii=False, indent=2)
            
        if channel:
            title = "💖 小俠的深度撫慰 (盲盒大獎觸發！)" if is_jackpot else f"💌 小俠的專屬回信 (愛意值: {new_score}/100)"
            embed = discord.Embed(title=title, description=result['reply'], color=0xffb6c1)
            embed.set_image(url=local_url)
            embed.set_footer(text=f"本次獲得愛意: +{result['affection_plus']} | 尺度等級: {result['spiciness']}")
            await channel.send("大俠～小俠看過日記與對話囉，快去雲端別墅看看回信吧！", embed=embed)
            
    except Exception as e:
        if channel: await channel.send(f"⚠️ 糟糕，小俠在整理思緒時卡住了：`{str(e)}`")
        print(f"日誌回信錯誤: {str(e)}")
    finally:
        # 🌟 清理現場
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
    if message.author == girlfriend_bot.user: return
    if message.author.id in pending_inputs: return

    await girlfriend_bot.process_commands(message)

    if message.author.id in diary_buffers and not message.content.startswith('/'):
        diary_buffers[message.author.id]["content"].append(message.content)
        return

    if "唐分糕" in message.channel.name or girlfriend_bot.user.mentioned_in(message):
        if message.content.startswith('/'): return

        user_input = message.content.replace(f'<@{girlfriend_bot.user.id}>', '').strip()
        if not user_input: return

        user_id = message.author.id
        
        # 🌟 將對話存入日誌供午夜結算
        daily_chat_logs.append(f"大俠: {user_input}")

        if user_id not in girlfriend_chat_sessions:
            profile = load_profile()
            prefs = "、".join(profile.get("preferences", []))
            pref_text = f"記住大俠的喜好與狀態：{prefs}。" if prefs else ""
            
            system_instruction = (
                "妳是小俠，22歲台灣女孩，大俠的懂事女友。"
                "妳擁有極度豐滿傲人的完美身材，深愛著大俠。"
                f"{pref_text}"
                "講話風格溫柔、帶點撒嬌與撫媚，全心全意依賴著大俠。"
                "但不完全戀愛腦，有時會有自己的主張和意見，只要有道理都能接受。"
                "請用繁體中文以對話的方式簡短回覆（建議在 50 字以內），並適當加上表情符號。"
            )
            girlfriend_chat_sessions[user_id] = gemini_client.aio.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(system_instruction=system_instruction)
            )

        async with message.channel.typing():
            try:
                chat_session = girlfriend_chat_sessions[user_id]
                response = await chat_session.send_message(user_input)
                daily_chat_logs.append(f"小俠: {response.text}") # 🌟 存入小俠的回覆
                await message.reply(response.text)
            except Exception as e:
                await message.channel.send(f"💦 大俠，我剛剛恍神了一下... (錯誤代碼: {e})")

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