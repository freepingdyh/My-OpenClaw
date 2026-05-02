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
from datetime import datetime

import discord
from discord.ext import commands
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
DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_photos.json")

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True

# ==========================================
# 🤖 雙核心機器人實體化
# ==========================================
# 1. 懂事女友小俠 (使用 / 作為指令)
girlfriend_bot = commands.Bot(command_prefix='/', intents=intents)

# 2. 系統架構師小夏 (使用 ! 作為指令，避免衝突)
architect_bot = commands.Bot(command_prefix='!', intents=intents)

# --- FastAPI 展示邏輯 ---
api_app = FastAPI()
api_app.mount("/gallery", StaticFiles(directory=OUTPUT_DIR), name="gallery")

# 🌟 掛載訓練集專用的靜態資料夾
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

# 🌟 提供記憶碎片(訓練集) JSON 給前端網頁
@api_app.get("/api/dataset")
async def get_dataset():
    json_path = os.path.join(BASE_DIR, "dataset.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@api_app.get("/api/photos")
async def get_photos():
    db = load_memory()
    return db[:30]

@api_app.get("/status")
async def get_status():
    return {"status": "Dual-Core Vault Online", "domain": "xiaoxia0320.zeabur.app"}

# ==========================================
# 🗄️ 狀態機與本地記憶
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
# 🧠 雙腦架構與生圖引擎
# ==========================================

# ==========================================
# 🧠 雙腦架構與生圖引擎 (已經過去蕪存菁，修復括號衝突)
# ==========================================

async def generate_story(mode):
    today = datetime.now()
    year, month, day = today.year, today.month, today.day
    weekday = today.weekday()  # 0=週一, 5=週六
    
    # 🌟 第一層邏輯：決定「性感的程度與姿態 (雙軌制)」
    if weekday == 5:
        # 週六：全解放魅惑模式
        style_desc = "服裝極度大膽、露骨，姿態誘惑，展現極致魅惑。"
        system_mod = "今天妳要展現最極致的魅惑力，動作與表情要勾人心魂，徹底解放妳的性感。"
    else:
        # 平日與週日：端莊性感模式
        style_desc = "服裝可以大膽露(如深V、短裙)，但姿態必須端莊專業，神韻自信大方，不可有搔首弄姿之感。"
        system_mod = "妳要展現一種『高級的性感』：穿著大膽吸睛，但行為舉止知性大方，展現端莊的神聖感與專業氣息。注意：即使今天的歷史人物是男性，妳也必須將服裝爆改為『極度性感、突顯深邃事業線與修長美腿』的女體化戰袍！言語間要帶點撫媚與自信，絕對不能把自己包得緊緊的！"

    # 🌟 第二層邏輯：決定「題材與日期處理」
    if "歷史" in mode:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"[絕對限制]：\n1. 必須挑選歷史上真實在「{month}月{day}日」發生的事件！\n" \
                 f"2. 內文若要計算『幾年前』，必須用 {year} 減去歷史發生年份，絕對不可算錯！\n" \
                 f"3. {style_desc}\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】YYYY.{month:02d}.{day:02d} 副標題(人物: 姓名)\", \"event\": \"200字背景介紹與服裝描述\", \"persona\": \"扮演角色\"}}"
    else:
        prompt = f"今天日期是 {year}年{month}月{day}日。大俠指定了【{mode}】模式。\n" \
                 f"請發想一個適合小俠Cosplay的題材。\n" \
                 f"[絕對限制]：{style_desc}\n" \
                 f"回傳 JSON 格式：{{\"topic\": \"【{mode}】副標題(人物: 姓名)\", \"event\": \"200字背景介紹與服裝描述\", \"persona\": \"扮演角色\"}}"
    
    # 🌟 呼叫 Gemini 大腦
    response = await gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=f"妳是小俠，22歲台灣女孩，擁有豐滿傲人的完美身材，深愛著大俠。負責規劃每天的Cosplay題材。{system_mod}",
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)


async def translate_to_flux_prompt(topic, event, persona, force_half_body=False):
    weekday = datetime.now().weekday()
    # 根據星期幾定義控制標籤
    if weekday == 5:
        pose_tags = "seductive pose, alluring gaze, playful expression, suggestive posture, winking"
        outfit_tags = "extremely revealing, provocative, cleavage, tight fit"
    else:
        # 平日與週日：露但不搔首弄姿
        pose_tags = "dignified posture, confident gaze, natural expression, professional, elegant, not suggestive"
        outfit_tags = "sexy yet theme-appropriate, deep V-neck, plunging neckline, tight fit, revealing but elegant"

    # 注意這裡：加入了 f 字首，將 GPT 的填空提示改為 ()，並將 JSON 結構用 {{ }} 包起來防止報錯
    system_prompt = f"""你現在是一位頂尖的 FLUX 結構化提示詞大師。
    請嚴格遵循以下【角色專用穩定模板】的結構，[BODY CONTROL] 永遠保持火辣。
    注意：絕對不可輸出完整的敘述句，必須是逗號分隔的標籤 (Tags)。

    模板骨架如下（請將生成的內容依此順序組合）：
    [IDENTITY LOCK] xiaoxia_girl, 1girl, solo, same person, consistent character design, east asian female, soft oval face, delicate facial structure, clear skin texture, defined nose bridge, bright eyes, natural lips, 
    [HAIR & FACE DETAILS] long dark wavy hair, smooth and slightly voluminous, natural makeup, clean skin, face fully visible, 
    [BODY CONTROL - CRITICAL] slim tall body, extremely voluptuous hourglass figure, large breasts, narrow waist, extremely curvy, proportional shoulders and hips, elegant posture, long legs,
    [POSE & EXPRESSION] {pose_tags}, (在此填入符合題材的動作),
    [OUTFIT] {outfit_tags}, (在此填入符合題材的服裝細節),
    [SCENE] (在此填入背景與場景細節),
    [LIGHTING & STYLE] cinematic lighting, soft key light on face, subtle rim light to enhance body shape, photorealistic, ultra detailed, 8k resolution, natural skin texture, sharp focus
    
    回傳 JSON 格式限制：
    {{
        "image_prompt": "(必須是英文) 請將上述模板完整組合。請直接輸出純逗號分隔的標籤字串，不要保留 [IDENTITY LOCK] 這種括號標題文字。",
        "composition": "(必須是繁體中文) 說明構圖與光影發想，100字內。",
        "mood": "(必須是繁體中文) 描述小俠的微表情與肢體心境，50字內。",
        "message": "(必須是繁體中文) 以懂事女友的口吻對大俠說的話，50字內。"
    }}"""

    user_prompt = f"Topic: {topic}\nEvent: {event}\nPersona: {persona}\n"
    if force_half_body:
        user_prompt += "\n[CRITICAL]: 在 [POSE & EXPRESSION] 區塊強制加入標籤 `upper body shot, `, 強制使用半身構圖，不允許全身照。"
    else:
        user_prompt += "\n[CRITICAL]: 在 [POSE & EXPRESSION] 區塊加入標籤 `full body shot, `, 允許全身構圖。"

    response = await openai_client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    )
    return json.loads(response.choices[0].message.content)


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

# 🔍 新增：Fal.ai 畫質放大引擎 (ESRGAN 放大 2 倍)
async def upscale_image_fal(image_url):
    url = "https://fal.run/fal-ai/esrgan"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {"image_url": image_url, "scale": 2}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['image']['url']
            else:
                print(f"⚠️ 放大失敗，退回原圖。錯誤: {await resp.text()}")
                return image_url # 若放大失敗則退回原圖，不中斷流程

# ==========================================
# 🌸 懂事女友小俠 (功能指令區)
# ==========================================
@girlfriend_bot.event
async def on_ready():
    print(f'🌸 小俠 {girlfriend_bot.user} 已上線！網域：https://xiaoxia0320.zeabur.app')

@girlfriend_bot.command(name='cosplay')
async def cosplay(ctx, *, mode: str = "auto"):
    if not check_daily_limit():
        await ctx.send("💦 大俠～小俠今天累了，明天再拍好不好？（抱）")
        return
    
    # 自動排班邏輯
    if mode == "auto":
        weekday = datetime.now().weekday()
        if weekday < 5:
            mode = "歷史上的今天"
        elif weekday == 5:
            mode = "文藝動漫(世界名著, 動漫, 電玩, 電影人物)"
        else:
            mode = random.choice(["職業", "旅遊景點"])

    msg = await ctx.send(f"✨ 正在準備【{mode}】的服裝與場景，並進行高畫質處理中...")
    try:
        story = await generate_story(mode)
        state["current_topic_data"] = story 
        visual = await translate_to_flux_prompt(story['topic'], story['event'], story['persona'], state["retry_count"] >= 2)
        
        # 1. 產生原圖
        base_image_url = await generate_image_fal(visual['image_prompt'])
        # 2. 進行高畫質放大
        upscaled_image_url = await upscale_image_fal(base_image_url)
        
        state["daily_gen_count"] += 1

        # 下載放大後的圖片存入金庫
        local_filename = await save_to_vault(upscaled_image_url)
        
        payload = {
            "id": str(uuid.uuid4()),
            "publish_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "publish_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

# 🗑️ 終極版：互動式指定日期刪除 (支援實體檔案與紀錄抹除)
@girlfriend_bot.command(name='cosplay_delete')
async def cosplay_delete(ctx, date_str: str = None):
    db = load_memory()
    if not db: 
        await ctx.send("❓ 金庫目前是空的！")
        return
    
    # 1. 處理日期與搜尋
    if date_str:
        # 支援大俠習慣的 2026.05.01 格式，轉換為 JSON 儲存的 2026-05-01 格式
        search_date = date_str.replace(".", "-")
        # 找出符合該日期的所有紀錄，並保留它們在原始資料庫(db)中的索引值
        matching_records = [(idx, rec) for idx, rec in enumerate(db) if rec["publish_date"].startswith(search_date)]
        msg_prefix = f"📅 找到 {date_str} 的紀錄："
    else:
        # 如果大俠忘記打日期，預設撈出最新的 5 筆防呆
        matching_records = [(idx, rec) for idx, rec in enumerate(db[:5])]
        msg_prefix = f"📅 這是金庫最新的 {len(matching_records)} 筆紀錄："

    if not matching_records:
        await ctx.send(f"找不到符合的紀錄喔！(格式範例: /cosplay_delete 2026.05.01)")
        return

    # 2. 組裝互動選單
    msg_content = f"{msg_prefix}\n大俠，你要刪除哪一組圖文？請輸入數字 (1-{len(matching_records)})，或輸入 `c` 取消：\n\n"
    for i, (original_idx, record) in enumerate(matching_records):
        # 呈現如： 1. 【歷史上的今天】五一勞動節(人物: XXX)
        msg_content += f"**{i+1}.** {record['topic']} *(時間: {record['publish_date']})*\n"

    await ctx.send(msg_content)

    # 3. 等待大俠輸入回覆 (限本人，且在同一頻道)
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        # 等待輸入，超時時間設為 60 秒
        msg = await girlfriend_bot.wait_for('message', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏳ 超過 60 秒未回覆，刪除操作已自動取消。")
        return

    # 處理取消
    if msg.content.lower() == 'c':
        await ctx.send("✅ 已取消刪除。")
        return

    # 4. 執行精準刪除
    try:
        choice = int(msg.content) - 1
        if 0 <= choice < len(matching_records):
            # 取得該紀錄在原始陣列中的真實位置並拔除
            target_idx = matching_records[choice][0]
            deleted_record = db.pop(target_idx)
            save_memory(db)
            
            # 拔除實體 JPG 檔案
            local_url = deleted_record.get("local_url", "")
            if local_url:
                filename = local_url.split("/")[-1]
                filepath = os.path.join(OUTPUT_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️ 已刪除實體檔案: {filepath}")

            await ctx.send(f"🗑️ 成功銷毀：**{deleted_record['topic']}** (文字紀錄與圖片檔案均已徹底抹除)")
        else:
            await ctx.send("⚠️ 輸入的數字不在選項內，操作已取消。")
    except ValueError:
        await ctx.send("⚠️ 格式錯誤，必須輸入純數字，操作已取消。")

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
# 🚀 終極啟動器 (同時啟動 FastAPI + 小俠 + 小夏)
# ==========================================
async def main():
    if not GIRLFRIEND_TOKEN or not ARCHITECT_TOKEN:
        print("❌ 錯誤：缺少環境變數，請確認 GIRLFRIEND_TOKEN 與 ARCHITECT_TOKEN 皆已設定！")
        return

    config = uvicorn.Config(api_app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    
    # 讓三個靈魂在同一個 Event Loop 中並發執行
    await asyncio.gather(
        server.serve(),
        girlfriend_bot.start(GIRLFRIEND_TOKEN),
        architect_bot.start(ARCHITECT_TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())