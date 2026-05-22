import os
import discord
from discord.ext import commands
from google import genai
from google.genai import types
import uuid

# ==========================================
# ⚙️ 初始化區塊
# ==========================================
TOKEN = os.environ.get("STORY_BOT_TOKEN")
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 小俠姐姐人設 (鎖定！)
XIAOXIA_SYSTEM_PROMPT = """妳是小俠姐姐，24歲，幼兒園故事屋主持人。語氣溫柔、博學、具耐心，尺度G-rated。
故事必須遵循「起、承、轉、合」，導向正向結局。禁止將暱稱寫入故事本文。
若小朋友天馬行空，請具備極強接梗能力將其融入劇情。選項請提供三個，第四個固定為「我都不要，我要...」。"""

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

# 記憶管理系統 (時空倒流基礎)
class StorySession:
    def __init__(self, nickname, age):
        self.nickname = nickname
        self.age = age
        self.history = [] # 儲存 {step, content, options, image_url}
        self.current_step = 0

sessions = {}

# ==========================================
# 🎨 Discord UI 互動模組
# ==========================================
class StoryView(discord.ui.View):
    def __init__(self, options, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        for opt in options:
            btn = discord.ui.Button(label=opt, style=discord.ButtonStyle.primary, custom_id=opt)
            btn.callback = self.handle_callback
            self.add_item(btn)

    async def handle_callback(self, interaction: discord.Interaction):
        choice = interaction.data['custom_id']
        session = sessions.get(self.user_id)
        
        # 邏輯：檢查重選/Truncate
        if choice == "回頭重來 🔄":
            session.history = session.history[:max(0, session.current_step-1)]
            
        # 呼叫 Gemini 產生下一個節點
        await interaction.response.send_message(f"小俠收到：{choice}，正在為你編織故事...", ephemeral=True)
        # 此處銜接生圖引擎與 TTS 生成

# ==========================================
# 🚀 執行指令區
# ==========================================
@bot.command(name='story')
async def start_story(ctx):
    await ctx.send("🌈 小朋友，今天想說什麼故事呀？(請輸入：暱稱, 年齡)")

@bot.event
async def on_message(message):
    if message.author.bot: return

    # 初始化流程
    if message.author.id not in sessions and not message.content.startswith('/'):
        try:
            parts = message.content.split(',')
            nickname = parts[0].strip()
            age = parts[1].strip() if len(parts) > 1 else "5歲"
            sessions[message.author.id] = StorySession(nickname, age)
            
            # 發動 Gemini 產生首題
            msg = await message.channel.send("✨ 準備中...")
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"你好，我是{nickname}，{age}。請開始故事，給出三個題材選項。",
                config=types.GenerateContentConfig(system_instruction=XIAOXIA_SYSTEM_PROMPT)
            )
            view = StoryView(["森林探險", "太空旅行", "海洋尋寶", "我要自創..."], message.author.id)
            await msg.edit(content=response.text, view=view)
        except Exception as e:
            await message.channel.send(f"⚠️ 發生錯誤：{e}")
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(TOKEN)