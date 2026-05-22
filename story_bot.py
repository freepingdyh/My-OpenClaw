import os
import discord
from discord.ext import commands
from google import genai
from google.genai import types

# 🚨 必須在 .env 設定 STORY_BOT_TOKEN
TOKEN = os.environ.get("STORY_BOT_TOKEN")
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 🧠 Session 管理：每個用戶一個 State
sessions = {}

class StorySession:
    def __init__(self, nickname, age):
        self.nickname = nickname
        self.age = age
        self.history = [] # 儲存 {step, content, options, image_url}
        self.current_step = 0

# 🤖 Bot 初始化
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.command(name='story')
async def start_story(ctx):
    # 初始化一個簡單的互動邏輯
    await ctx.send("🌈 小朋友你好！我是小俠姐姐。我們今天來說個故事吧！(請告訴我你的暱稱)")

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # 這裡會接住小朋友的暱稱輸入，並觸發第一個故事問題
    if message.author.id not in sessions and not message.content.startswith('/'):
        sessions[message.author.id] = StorySession(nickname=message.content, age="未知")
        await message.channel.send(f"好的！{message.content[-2:]} 平平，那我們要說什麼故事呢？(A: 森林冒險, B: 太空旅行)")
        return

    await bot.process_commands(message)

# 🚀 啟動
if __name__ == "__main__":
    bot.run(TOKEN)