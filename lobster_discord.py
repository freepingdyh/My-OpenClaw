# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版)
# ==========================================

import os
import json
import uuid
import asyncio
import aiohttp
import aiofiles  # 必須加入此依賴
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 🧠 新版 SDK 導入
from google import genai
from google.genai import types
from openai import AsyncOpenAI

# 🌐 新增：Web 服務元件 (為了連動大俠的網域)
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# ==========================================
# 🔑 環境變數與初始化 (最小變動：加入 Zeabur 路徑判斷)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
FAL_KEY = os.environ.get("FAL_KEY")
XIAOXIA_LORA_URL = os.environ.get("XIAOXIA_LORA_URL")

# --- Zeabur 硬碟路徑重導向 ---
IS_ZEABUR = os.environ.get("ZEABUR") == "true"
VAULT_DIR = "/data" if IS_ZEABUR else BASE_DIR  # 若在 Zeabur 則指向 xiaoxia-vault

OUTPUT_DIR = os.path.join(VAULT_DIR, "output")
MEMORY_DIR = os.path.join(VAULT_DIR, "memory")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)
DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_photos.json")

# 初始化 LLM 客戶端 (全異步架構)
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 初始化 Discord Bot
intents = discord.Intents.default()
intents.message_content = True
# 為了啟動 Web 服務，我們微調 Bot 初始化
class LobsterBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        # 啟動 FastAPI 服務，對應大俠設定的 Port 8080
        config = uvicorn.Config(api_app, host="0.0.0.0", port=8080, log_level="warning")
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        print("🌐 網頁展示服務已在 Port 8080 啟動")

bot = LobsterBot()

# --- 新增：FastAPI 展示邏輯 ---
api_app = FastAPI()
api_app.mount("/gallery", StaticFiles(directory=OUTPUT_DIR), name="gallery")

# 👇 加上這一段，讓網頁有東西可以顯示
@api_app.get("/status")
async def get_status():
    return {"status": "Xiaoxia Vault Online", "domain": "xiaoxia0320.zeabur.app"}

# ==========================================
# 🗄️ 狀態機與本地記憶 (保留原邏輯)
# ==========================================
state = {
    "daily_gen_count": 0,
    "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
    "retry_count": 0,
    "current_topic_data": None
}

def load_memory():
    if not os.path.exists(DATA_PATH): return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(db):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def check_daily_limit():
    today = datetime.now().strftime("%Y-%m-%d")
    if state["last_reset_date"] != today:
        state["daily_gen_count"] = 0
        state["last_reset_date"] = today
        state["retry_count"] = 0
    return state["daily_gen_count"] < 6

# --- 新增：金庫備份函數 ---
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

# ==========================================
# 🧠 雙腦架構 (完全保留大俠原有的 Prompt 邏輯)
# ==========================================
async def generate_story(mode):
    today = datetime.now()
    year, month, day = today.year, today.month, today.day
    if "歷史" in mode:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"[絕對限制]：\n1. 必須挑選歷史上真實在「{month}月{day}日」發生的事件！\n" \
                 f"2. 內文若要計算『幾年前』，必須用 {year} 減去歷史發生年份，絕對不可算錯！\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】YYYY.{month:02d}.{day:02d} 副標題(人物: 姓名)\", \"event\": \"200字背景介紹\", \"persona\": \"扮演角色\"}}"
    else:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"請發想一個適合小俠Cosplay的題材。\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】副標題(人物: 姓名)\", \"event\": \"200字背景介紹\", \"persona\": \"扮演角色\"}}"
    
    response = await gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="妳是小俠，22歲台灣女孩，深愛著大俠。負責規劃每天的Cosplay題材。注意：即使今天的歷史人物是男性，妳也是以『女性化、性感的改良版服裝』進行Cosplay，絕對不能把自己當成老爺爺！",
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

async def translate_to_flux_prompt(topic, event, persona, force_half_body=False):
    system_prompt = """你是一位專精於 FLUX 模型的視覺總監。
    核心不可變條件：
    1. [終極臉部鎖定] 提示詞開頭必須嚴格是：`xiaoxia_girl, 1girl, solo, masterpiece, extremely detailed beautiful face, heavy eyelids, bedroom eyes, smooth fair skin, `。
    2. [絕對禁止]：絕對不可生成男性(boy, man, old man)、不可生成老人、不可長鬍子！
    3. [強制女體化]：將服裝強制轉譯為「為性感年輕女性量身訂做的 Cosplay 服裝」(例如：sexy plunging neckline, revealing, tight fit)。
    4. 其餘特徵：強調 `slender yet voluptuous hourglass figure`。
    5. 品質後綴：`ultra clean image, soft cinematic lighting.` (這段必須加在 image_prompt 的最後面，絕對不可跑到 message 裡！)
    
    回傳 JSON 格式限制 (嚴格遵守語言規定)：
    {
        "image_prompt": "(必須是英文) 逗號分隔的英文標籤。臉部鎖定放最前面，品質後綴放最後面。",
        "composition": "(必須是繁體中文) 說明構圖與光影發想，100字內。",
        "mood": "(必須是繁體中文) 描述小俠的微表情與肢體心境，50字內。",
        "message": "(必須是繁體中文) 以懂事女友的口吻對大俠說的話，50字內。"
    }"""

    user_prompt = f"Topic: {topic}\nEvent: {event}\nPersona: {persona}\n"
    if force_half_body:
        user_prompt += "\n[CRITICAL]: 強制使用半身構圖 (upper body shot, cowboy shot)，不允許全身照。"
    else:
        user_prompt += "\n[CRITICAL]: 允許全身構圖 (full body shot)。"

    response = await openai_client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# 🎨 生圖引擎：Fal.ai (保留原邏輯)
# ==========================================
async def generate_image_fal(prompt):
    if not XIAOXIA_LORA_URL: raise ValueError("XIAOXIA_LORA_URL 尚未在 .env 中設定！")
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
            else:
                raise Exception(f"Fal.ai Error: {await resp.text()}")

# ==========================================
# 🤖 Discord 指令區 (保留原 258 行所有指令邏輯)
# ==========================================
@bot.event
async def on_ready():
    print(f'✅ 小俠已上線！網域：https://xiaoxia0320.zeabur.app')

@bot.command(name='start_friend')
async def start_friend(ctx, *, mode: str = "歷史上的今天"):
    if not check_daily_limit():
        await ctx.send("💦 大俠～小俠今天累了，明天再拍好不好？（抱）")
        return
    msg = await ctx.send(f"✨ 正在準備【{mode}】的服裝...")
    try:
        story = await generate_story(mode)
        state["current_topic_data"] = story 
        visual = await translate_to_flux_prompt(story['topic'], story['event'], story['persona'], state["retry_count"] >= 2)
        
        image_url = await generate_image_fal(visual['image_prompt'])
        state["daily_gen_count"] += 1

        # --- 最小變動：加入下載與金庫紀錄 ---
        local_filename = await save_to_vault(image_url)
        
        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": story["topic"],
            "event": story["event"],
            "composition": visual["composition"],
            "mood": visual["mood"],
            "message": visual["message"],
            "image_url": image_url,
            "local_url": f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=story["topic"], description=story["event"], color=0xffb6c1)
        embed.set_image(url=image_url)
        embed.add_field(name="📸 構圖發想", value=visual["composition"], inline=False)
        embed.add_field(name="💭 小俠心境", value=visual["mood"], inline=False)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/6 | 網頁已同步備份")

        await msg.delete()
        await ctx.send(embed=embed)
    except Exception as e:
        await msg.edit(content=f"⚠️ 狀況：`{str(e)}`")

@bot.command(name='more')
async def more(ctx):
    if not state["current_topic_data"]:
        await ctx.send("❓ 還沒決定題材呢！")
        return
    if not check_daily_limit(): return
    msg = await ctx.send("✨ 再換個姿勢拍一張...")
    try:
        story = state["current_topic_data"]
        visual = await translate_to_flux_prompt(story['topic'], story['event'], story['persona'], state["retry_count"] >= 2)
        image_url = await generate_image_fal(visual['image_prompt'])
        state["daily_gen_count"] += 1
        embed = discord.Embed(title=f"【加洗】{story['topic']}", color=0xffb6c1)
        embed.set_image(url=image_url)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        await msg.delete()
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"⚠️ 失敗：{e}")

@bot.command(name='undo')
async def undo(ctx):
    db = load_memory()
    if not db: return
    db.pop(0)
    save_memory(db)
    state["retry_count"] += 1
    state["daily_gen_count"] = max(0, state["daily_gen_count"] - 1)
    await ctx.send(f"🗑️ 已銷毀最後一張照片！")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)