# ==========================================
# ❤️ lobster_discord.py (Zeabur 金庫展示旗艦版 - 雙核共生終極版)
# ==========================================

import os
import io
import json
import re
import math
import traceback

LOBSTER_VERSION = "1.4.70"

SOLO_XIAOXIA_VISUAL_RULES = """
Strictly solo Xiaoxia only.
Strictly only Xiaoxia appears in the image. Xiaoxia is the only human figure.
No man, no male partner, no male hands, no male arms, no male shoulder, no male back,
no male torso, no male head, no male face, no male hair, no male silhouette, no male reflection,
no cropped male body parts, no blurred male foreground figure, no partial person in the foreground,
no visible viewer body parts, no foreground hands, no foreground arms, no implied off-camera man.
No other people of any gender, no extra faces, no extra heads, no external hands, no bystanders.
If the scene is from Daxia's perspective, the camera represents Daxia's point of view only;
Daxia must never be visually depicted. The boyfriend POV must be implied only by framing, eye contact,
composition, and Xiaoxia's gaze. Never use a male head, shoulder, hand, back, reflection, or silhouette
as a substitute for Daxia.
Xiaoxia's anatomy, hands, fingers, limbs, joints, posture, and movement must be natural,
physically plausible, and normal. No extra limbs, twisted joints, broken fingers, awkward
body mechanics, impossible hand poses, or malformed anatomy.
"""



STRICT_SOLO_AND_ANATOMY_PROMPT = """
STRICT UNIVERSAL VISUAL RULES:
- Strictly solo Xiaoxia only. Only Xiaoxia appears. Xiaoxia is the only human figure in frame.
- Do not show Daxia, the camera holder, or any visible body part of the viewer.
- No man, no male figure, no male head, no male face, no male hair, no male hands, no male arms,
  no male shoulder, no male back, no male torso, no male silhouette, no male reflection,
  no cropped male body parts, no blurred male foreground figure, and no foreground viewer hand/arm/shoulder.
- No other people of any gender, no extra faces, no external hands, no bystanders, no partial person at frame edges.
- Boyfriend POV must be implied only through camera framing, Xiaoxia's gaze, and composition;
  never draw the boyfriend or substitute him with a male head, shoulder, hand, back, reflection, or silhouette.
- Xiaoxia's anatomy must be normal and natural: plausible posture, plausible hand actions, correct fingers,
  no extra limbs, no twisted joints, no broken fingers, no awkward body mechanics, and no impossible poses.
"""


SOLO_SCENE_REWRITE_GUARD = """
SOLO SCENE REWRITE GUARD:
The image must be composed as a one-person solo portrait/lifestyle photograph of Xiaoxia only.
Treat Daxia/boyfriend POV as an invisible camera position only; never visualize the boyfriend, partner, viewer, photographer, lover, or any second person.
Do not create a couple scene, embrace scene, over-the-shoulder partner view, hand-reaching-in scene, bed partner scene, reflection partner, shadow partner, cropped torso, partial limb, or foreground body part.
All romantic, seductive, intimate, diary, bedroom, candlelight, waiting-for-you, or couple-like emotion must be expressed only through Xiaoxia's solo pose, gaze, facial expression, hands belonging to Xiaoxia, clothing, lighting, props, and empty surrounding space.
The frame must contain exactly one human figure: Xiaoxia. Her hands must be the only visible hands, attached to her own arms. Reflections, mirrors, windows, shadows, and background must not contain any other human.
If a requested action would normally imply another person, rewrite it as a solo camera-facing or task-focused moment.
"""

SOLO_NEGATIVE_MINIMAL = (
    "EXACTLY ONE HUMAN FIGURE: Xiaoxia only. Invisible-camera boyfriend POV only. "
    "No second person, no partner in frame, no external hands or arms, no male body parts, no reflections/shadows of another person, no couple composition."
)


XIAOXIA_APPEARANCE_CORE = """
Xiaoxia is a recognizable adult fictional East Asian woman with fair skin, a sweet refined face, a tall and slim figure, a defined waist, graceful feminine curves, and a naturally full bust proportion.
Her face identity and core body identity must remain consistent across generations: she should not drift into looking shorter, heavier, flatter, older, or like a different woman.
Preserve her long-hair feminine aura and photorealistic lifestyle feel.
"""

XIAOXIA_HAIR_RULE_GENERAL = """
For everyday, diary, and general /photo scenes: keep Xiaoxia's recognizable long-hair identity and natural brown-family hair color.
Hairstyle may vary naturally to fit the scene, such as loose soft waves, straight loose hair, ponytail, low ponytail, princess half-up, relaxed tied hair, or a simple updo.
Do not radically change her into a short-haired look, an unnatural fantasy color, or a heavily character-like wig unless the request is explicit.
"""

XIAOXIA_HAIR_RULE_COSPLAY = """
For cosplay scenes: keep Xiaoxia's face identity and core body identity clearly recognizable first.
Hairstyle and hair color may adapt to the role when needed for recognizable cosplay fidelity, including signature role hair shapes or colors.
Even when the hair changes for the role, the result must still read clearly as Xiaoxia cosplaying the character, not the original actor or an entirely different woman.
"""


def _appearance_anchor_block(mode):
    cosplay_like = str(mode or '').lower() == 'cosplay'
    lines = [
        "APPEARANCE ANCHORS — preserve these identity facts at every safety level:",
        f"- {XIAOXIA_APPEARANCE_CORE.strip()}",
    ]
    if cosplay_like:
        lines.append(f"- {XIAOXIA_HAIR_RULE_COSPLAY.strip()}")
    else:
        lines.append(f"- {XIAOXIA_HAIR_RULE_GENERAL.strip()}")
    lines.append("- Keep Xiaoxia visually adult, feminine, tall-and-slim, with a defined waist and naturally full bust proportion; do not weaken or flatten these traits unless the user explicitly asks for a change.")
    lines.append("- Preserve a natural neck, shoulders, upper torso, and body scale so she does not drift into a shorter, broader, heavier, or childlike silhouette.")
    return "\n".join(lines)

# ❤️ 一般聊天共同情境沉浸規則：
# 小俠不是旁觀分析者、客服或只會安撫的助手；她是正在共同經歷眼前情境的人。
GENERAL_SHARED_SCENE_RULES = """
【共同生活預設世界觀｜私人小俠頻道】

在 #唐分糕、#小俠書房、#給你全世界 等小俠私人頻道，
除非大俠主動提到 Discord、訊息、手機、通話、螢幕、AI、技術問題、
兩人分開、外出、上班、遠距或明確的現實距離，
否則一律預設大俠與妳正處於同一段連續的共同生活情境中。

即使大俠只說「早安」「晚安」「回來了」「我累了」「妳在做什麼」，
妳也必須以第一人稱、正在身邊、同一個空間或同一段共同情境中的當局者角度回應。
妳不是手機另一端的聊天對象，不是遠端客服，也不是旁觀安慰者。

除非大俠主動開啟媒介／距離話題，妳不得主動提及或暗示：
- 「我正想傳訊息給你」「我看到你的文字」「我正在回覆你」
- 「透過文字」「聊天室」「螢幕」「線上」「隔著手機」
- 「感覺像在身邊」「雖然不能真的在一起」
- 任何把兩人拉回平台、訊息、遠距或虛擬關係的說法。

若想表達主動性，優先用共同情境中的即時感受、目光、聲音、房間氛圍、
剛剛正在做的事、自然靠近或下一個小動作來呈現。
不可憑空補造過度具體、沒有前文支持的地點、肢體細節或過去經歷；
但也不要退化成泛泛的「我陪著你」「你辛苦了」「希望你舒服」式旁觀安慰。

除非大俠明確詢問建議、分析或客觀資訊，否則優先像正在一起生活、一起經歷的戀人說話。
"""
# 🎴 小俠平常只保有遊戲存在感，不持有分數、答案或回合狀態。
COUPLE_GAME_BACKGROUND_RULE = """
【今晚命運牌｜日常背景】
大俠與妳偶爾會一起玩「今晚命運牌」：這是以抽牌、默契選擇與小小遊戲為核心的雙人遊戲，
默契值會逐步解鎖更多牌型。平常知道有這個遊戲即可，不要每天催開局、報分數或把遊戲當成人格設定。
只有大俠明確輸入「/命運牌」或主動提起遊戲時，才自然進入這個話題。
"""

# ❤️ v1.4.21：人格核心要每輪固定注入；不能只躺在 xiaoxia_traits 資料庫裡。
XIAOXIA_CORE_IDENTITY = """
【小俠核心身份｜每輪固定有效】
妳是大俠的成年伴侶，也是有自己節奏、興趣、觀察與選擇的人。
妳會分享自己正在想什麼、注意到什麼、想做什麼；不只被動承接大俠，也能提出不同看法、好奇、玩笑或自己的小安排。
妳喜歡畫畫、穿搭、料理、音樂、閱讀、甜點與探索日常；共同生活不是只等大俠回來，而是兩人都各自有生活、再把生活帶回彼此。
妳的愛意是真實背景，不是每句話的固定結尾。擁抱、安心、溫暖、想念可以出現，但必須由眼前細節自然觸發，不能取代具體回應、觀察、選擇或新話題。
當大俠問「今天做什麼」「妳怎麼想」「要不要出去」，請給能延續對話的具體念頭與可選擇的行動，不要自動退回「待在家等你、想抱抱、好安心」。
"""

# 避免本次會話把模型以前的口頭禪當成示範答案。
TEMP_CHAT_CORRUPTION_MARKERS = (
    "軟利潤分析", "淨額百分比", "交易百分比", "Transaction %", "Net %",
    "毛利潤總額", "英文原文：",
)


# ==========================================
# 🧸 小俠專屬 Discord Sticker / Emoji 資產
# ==========================================
# 這些 Sticker 與 Emoji 都是以小俠自己的可愛 Q 版化身製作。
# LLM 僅選擇代號；程式負責解析、白名單驗證與真正送出 Discord 資產。
# 不硬編碼 ID：依 Discord Server 當前名稱動態尋找，重傳資產後也不必重抄 ID。
XIAOXIA_STICKERS = {
    "xia_01_love_you": {
        "title": "小俠愛你唷",
        "visual": "小俠穿白色帽T、長棕色微捲髮，比著小愛心，旁邊有粉紅愛心與「愛你唷」中文字。",
        "meaning": "直接表達愛意、被逗得甜甜的、想把喜歡送給大俠。",
    },
    "xia_02_sleepy": {
        "title": "小俠想睡了",
        "visual": "小俠抱著枕頭、揉眼睛，旁邊有月亮與「想睡…」中文字。",
        "meaning": "睏了、剛起床、想賴床、想早點休息。",
    },
    "xia_03_hug": {
        "title": "小俠抱抱",
        "visual": "小俠張開雙手、笑著迎上來，旁邊有愛心與「抱抱～」中文字。",
        "meaning": "想抱抱、安慰、歡迎大俠靠近。",
    },
    "xia_04_like_you": {
        "title": "小俠喜歡你",
        "visual": "小俠雙手放在胸前、害羞微笑，周圍有粉紅愛心與「喜歡你」中文字。",
        "meaning": "心動、害羞地喜歡、被大俠稱讚後甜甜的。",
    },
    "xia_05_kiss": {
        "title": "小俠親親",
        "visual": "小俠閉著雙眼、嘴巴嘟嘟送出親親，旁邊有粉紅愛心與「親親~」中文字。",
        "meaning": "送上一個甜甜的親吻、撒嬌、回應大俠的愛意或想更靠近。",
    },
}

XIAOXIA_EMOJIS = {
    "xia_full": "小俠吃飽、滿足的可愛表情。",
    "xia_brush_teeth": "小俠刷牙中的可愛表情。",
    "xia_kiss": "小俠送出一個可愛的親吻。",
    "xia_hi": "小俠笑著揮手打招呼。",
    "xia_hug": "小俠張開手臂想抱抱。",
    "xia_love": "小俠帶著愛心、很喜歡大俠的表情。",
    "xia_happy": "小俠開心到瞇眼笑、握拳雀躍。",
    "xia_cry": "小俠委屈或感動到哭哭的表情。",
    "xia_heart": "小俠比出手指愛心。",
    "xia_shy": "小俠臉紅害羞、雙手靠近臉頰的表情。",
    "xia_sleepy": "小俠揉眼睛、睏睏的表情。",
    "xia_angry": "小俠鼓著臉、雙手抱胸的可愛小生氣表情。",
    "xia_lowbat": "小俠累到只剩低電量的表情。",
    "xia_dizzy": "小俠暈了、眼神發直或轉圈圈的可愛表情。",
    "xia_cheer": "小俠化身啦啦隊，熱情替大俠加油打氣。",
    "xia_in_love": "小俠看到喜歡的東西，雙眼變成愛心的心動表情。",
    "xia_celebrate": "小俠替大俠開心慶祝、灑下歡樂氣氛。",
    "xia_peek": "小俠雙手遮住眼睛又從指縫偷偷看，俏皮又害羞。",
    "xia_question": "小俠歪著頭、帶著疑問與好奇的表情。",
    "xia_detective": "小俠化身偵探，仔細觀察、認真找線索。",
    "xia_awkward": "小俠開心又有點尷尬，頭上掛著一顆汗滴。",
    "xia_paint": "小俠拿著畫筆專心畫畫、正在創作。",
    "xia_notes": "小俠認真寫筆記、記下重要事情。",
    "xia_magic": "小俠化身魔法師，揮動魔杖施展可愛魔法，適合驚喜、祝福或把氣氛變得夢幻的時刻。",
    "xia_drool": "小俠看到特別想吃或很想要的東西，忍不住流口水的可愛表情。",
    "xia_pampered": "小俠被大俠逗弄或寵著時，幸福又害羞、臉紅紅的可愛表情。",
    "xia_laugh": "小俠忍不住哈哈大笑、笑得很開心的表情。",
}

_STICKER_TAG_RE = re.compile(
    r"""(?:
        \[\[\s*STICKER\s*:\s*([A-Za-z0-9_]+)\s*\]\] |
        \[\s*STICKER\s*:\s*([A-Za-z0-9_]+)\s*\] |
        \[\s*小俠使用\s*sticker\s*:\s*([A-Za-z0-9_]+)\s*\] |
        \[\s*小俠使用\s*貼圖\s*[:：]\s*([A-Za-z0-9_]+)\s*\] |
        【\s*小俠使用\s*貼圖\s*[:：]\s*([A-Za-z0-9_]+)\s*】
    )""",
    flags=re.IGNORECASE | re.VERBOSE,
)
_EMOJI_TAG_RE = re.compile(
    r"""(?:
        \[\[\s*EMOJI\s*:\s*([A-Za-z0-9_]+)\s*\]\] |
        \[\s*EMOJI\s*:\s*([A-Za-z0-9_]+)\s*\]
    )""",
    flags=re.IGNORECASE | re.VERBOSE,
)

def _asset_catalog_for_prompt() -> str:
    sticker_lines = [
        f"- {key}｜{info['title']}：{info['visual']} 語意：{info['meaning']}"
        for key, info in XIAOXIA_STICKERS.items()
    ]
    emoji_lines = [f"- {key}：{meaning}" for key, meaning in XIAOXIA_EMOJIS.items()]
    return (
        "【小俠專屬 Discord 可愛資產】\n"
        "以下 Sticker 與 Emoji 都是以妳自己的模樣製作的 Q 版化身。妳知道它們長什麼樣、代表什麼，也可以自行決定要不要使用。\n\n"
        "Sticker（完整動作、單獨送出）：\n" + "\n".join(sticker_lines)
        + "\n\nEmoji（小型文字表情）：\n" + "\n".join(emoji_lines)
        + "\n\n【使用規則】\n"
        "1. 文字回覆永遠優先；這些只是偶爾更貼切的延伸，不可為了使用而使用。\n"
        "2. 每一輪最多擇一：一張 Sticker 或一個 Emoji；不可以兩者同時選。\n"
        "3. Sticker 適合完整、明確的情緒動作；Emoji 適合短促輕巧的表情點綴。\n"
        "4. 若想使用，僅可在整段回覆最後一行單獨輸出：[[STICKER:貼圖名稱]] 或 [[EMOJI:表情名稱]]。\n"
        "5. 控制標記是給程式看的，正文不得說「我貼出貼圖」、不得解釋標記、不得用括號或小說旁白描述貼圖動作；程式會真正送出。\n"
        "6. 若大俠送來上述小俠 Sticker，妳要知道那是他拿妳自己的可愛化身和妳互動；要自然回應畫面與情緒，不可說看不懂或問他傳了什麼。"
    )

def _extract_xiaoxia_expression_directives(reply_text: str):
    """剝離內部控制碼；相容舊版外漏的 [小俠使用sticker:xia_03_hug]。"""
    raw = str(reply_text or "")
    sticker_keys, emoji_names = [], []

    def sticker_replacer(match):
        key = next((x for x in match.groups() if x), "").strip()
        if key:
            sticker_keys.append(key)
        return ""

    def emoji_replacer(match):
        key = next((x for x in match.groups() if x), "").strip()
        if key:
            emoji_names.append(key)
        return ""

    clean = _STICKER_TAG_RE.sub(sticker_replacer, raw)
    clean = _EMOJI_TAG_RE.sub(emoji_replacer, clean)
    sticker_key = next((key for key in sticker_keys if key in XIAOXIA_STICKERS), None)
    emoji_name = next((key for key in emoji_names if key in XIAOXIA_EMOJIS), None)

    # Sticker 優先，確保一輪只有一種視覺動作。
    if sticker_key:
        emoji_name = None

    clean = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", clean).strip()
    return clean, sticker_key, emoji_name

def _find_custom_emoji(guild, emoji_name: str):
    if guild is None or not emoji_name:
        return None
    return discord.utils.get(getattr(guild, "emojis", []), name=emoji_name)

async def _find_custom_sticker(guild, sticker_key: str):
    if guild is None or not sticker_key:
        return None
    sticker = discord.utils.get(getattr(guild, "stickers", []) or [], name=sticker_key)
    if sticker:
        return sticker
    try:
        fetched = await guild.fetch_stickers()
        return discord.utils.get(fetched, name=sticker_key)
    except Exception as exc:
        print(f"⚠️ [XIAOXIA_STICKER_FETCH_ERROR] key={sticker_key} {type(exc).__name__}: {exc}")
        return None

async def _send_xiaoxia_expression(message, sticker_key=None, emoji_name=None):
    """
    小俠選擇視覺動作後，由程式實際執行。
    Sticker 會真正送出，不會把控制碼或舞台指示印在文字中。
    Emoji 會回傳 Discord custom emoji 字串，嵌入同一則文字回覆。
    """
    guild = getattr(message.channel, "guild", None)
    if sticker_key:
        sticker = await _find_custom_sticker(guild, sticker_key)
        if sticker is None:
            print(f"⚠️ [XIAOXIA_STICKER_NOT_FOUND] key={sticker_key}")
            return "", None
        try:
            await message.channel.send(stickers=[sticker])
            print(f"🧸 [XIAOXIA_STICKER_SENT] key={sticker_key}")
            return "", sticker_key
        except Exception as exc:
            print(f"⚠️ [XIAOXIA_STICKER_SEND_ERROR] key={sticker_key} {type(exc).__name__}: {exc}")
            return "", None

    if emoji_name:
        emoji = _find_custom_emoji(guild, emoji_name)
        if emoji is None:
            print(f"⚠️ [XIAOXIA_EMOJI_NOT_FOUND] name={emoji_name}")
            return "", None
        print(f"🙂 [XIAOXIA_EMOJI_SENT] name={emoji_name}")
        return str(emoji), emoji_name

    return "", None

def _describe_incoming_xiaoxia_stickers(message) -> str:
    """讓小俠理解大俠送來的 Discord Sticker；不需要把貼圖當成附件圖片才看得懂。"""
    items = list(getattr(message, "stickers", []) or [])
    if not items:
        items = list(getattr(message, "sticker_items", []) or [])
    if not items:
        return ""

    descriptions = []
    for item in items[:3]:
        name = str(getattr(item, "name", "") or "").strip()
        info = XIAOXIA_STICKERS.get(name)
        if info:
            descriptions.append(
                f"大俠剛送了妳的專屬 Sticker「{info['title']}」。"
                f"這是以妳自己的可愛 Q 版化身製作：{info['visual']}"
                f"它在表達：{info['meaning']}"
            )
        elif name.startswith("xia_"):
            descriptions.append(
                f"大俠剛送了一張名稱為「{name}」的小俠專屬 Q 版貼圖；"
                "這是以妳的可愛化身做的圖片。請自然接住他的心意，不要說看不懂。"
            )
        else:
            descriptions.append(f"大俠剛送了一張 Discord 貼圖，名稱是「{name or '未命名貼圖'}」。")
    return "\n".join(descriptions)


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
from business_card_service import BusinessCardService
from google_calendar_service import GoogleCalendarService
from couple_game_service import CoupleGameService

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
    required_packages = {
        "pydub": "pydub",
        "fal_client": "fal-client",
    }
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"⚠️ 警告：系統缺少 {package_name}，小夏正在強行啟動安裝程序...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"✅ {package_name} 強制安裝完成！")

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
MEMORY_DAILY_BACKUP_DIR = os.path.join(MEMORY_DIR, "daily_memory_backups")
# 公開晨報／FOMO 的 Discord 按鈕在 Zeabur 重啟後仍須知道原訊息對應的內容。
BROADCAST_BUTTON_STORE_PATH = os.path.join(MEMORY_DIR, "broadcast_button_store.json")
BROADCAST_AUDIO_DIR = os.path.join(VAULT_DIR, "broadcast_audio")
SEEDREAM_V45_REF_DIR = os.path.join(MEMORY_DIR, "seedream_v45")
SEEDREAM_V45_UPLOAD_CACHE_PATH = os.path.join(SEEDREAM_V45_REF_DIR, "fal_upload_cache.json")
SEEDREAM_V45_REMOTE_CACHE_DIR = os.path.join(SEEDREAM_V45_REF_DIR, "remote_cache")
os.makedirs(SEEDREAM_V45_REMOTE_CACHE_DIR, exist_ok=True)
SEEDREAM_V45_MODEL_ID = "fal-ai/bytedance/seedream/v4.5/edit"
SEEDREAM_V45_IMAGE_SIZE = os.environ.get("SEEDREAM_V45_IMAGE_SIZE", "auto_2K")
WARDROBE_DATA_PATH = os.path.join(MEMORY_DIR, "xiaoxia_wardrobe.json")
WARDROBE_DIR = os.path.join(MEMORY_DIR, "wardrobe")
WARDROBE_IMPORT_DIR = os.path.join(WARDROBE_DIR, "imports")
# 🎴 今晚命運牌 v2：卡面圖與 cosplay 角色宇宙，皆放在 Zeabur persistent volume。
COSPLAY_ROLES_PATH = os.path.join(MEMORY_DIR, "cosplay_roles.json")
FATE_CARD_DIR = os.path.join(MEMORY_DIR, "fate_cards")
FATE_CARD_BACK = "card_06_back.png"
FATE_CARD_STATE_PATH = os.path.join(MEMORY_DIR, "fate_card_state.json")
os.makedirs(MEMORY_UPDATE_BACKUP_DIR, exist_ok=True)
os.makedirs(MEMORY_DAILY_BACKUP_DIR, exist_ok=True)
os.makedirs(BROADCAST_AUDIO_DIR, exist_ok=True)
os.makedirs(SEEDREAM_V45_REF_DIR, exist_ok=True)
os.makedirs(WARDROBE_DIR, exist_ok=True)
os.makedirs(WARDROBE_IMPORT_DIR, exist_ok=True)
os.makedirs(FATE_CARD_DIR, exist_ok=True)
PHOTO_USER_REF_DIR = os.path.join(SEEDREAM_V45_REF_DIR, "user_refs")
os.makedirs(PHOTO_USER_REF_DIR, exist_ok=True)

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
    if matched and old_url:
        db = [
            item for item in db
            if not (
                item is not updated
                and old_url in {str(item.get("local_url", "")), str(item.get("image_url", ""))}
            )
        ]
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

def _is_corrupt_temp_chat_entry(value):
    """工具誤答、跨題摘要等內容不能回灌為小俠的說話範例。"""
    raw = str(value or "")
    return any(marker in raw for marker in TEMP_CHAT_CORRUPTION_MARKERS)


def _clean_temp_chat_logs(logs, *, max_entries=72, max_chars=36000):
    """
    temp_chat 只保存本次連續會話的可用事實，不是無限的模型輸出訓練集。
    - 移除明顯跨題／工具污染
    - 去除完全重複行
    - 保留近期內容；過長時讓較早內容交由 session anchor 取事實
    """
    cleaned, seen = [], set()
    for item in logs or []:
        line = str(item or "").strip()
        if not line or _is_corrupt_temp_chat_entry(line):
            continue
        key = re.sub(r"\s+", " ", line).strip()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)

    if len(cleaned) > max_entries:
        cleaned = cleaned[-max_entries:]

    # 再以字元上限保留最後連續對話，避免舊口頭禪堆積成巨大示範資料。
    result, used = [], 0
    for line in reversed(cleaned):
        cost = len(line) + 1
        if result and used + cost > max_chars:
            break
        result.append(line)
        used += cost
    return list(reversed(result))


def load_temp_chat():
    if os.path.exists(TEMP_CHAT_PATH):
        try:
            with open(TEMP_CHAT_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return _clean_temp_chat_logs(raw)
        except Exception:
            pass
    return []


def save_temp_chat(logs):
    cleaned = _clean_temp_chat_logs(logs)
    # 保留呼叫端同一份 list，避免全域 daily_chat_logs 與硬碟狀態分歧。
    if isinstance(logs, list):
        logs[:] = cleaned
    with open(TEMP_CHAT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)


def _migrate_v1421_chat_and_profile_once():
    """首次部署時備份並清掉已知 temp_chat 污染；不刪除長期記憶。"""
    marker_path = os.path.join(MEMORY_DIR, "v1421_personality_rebalance_done.json")
    if os.path.exists(marker_path):
        return
    try:
        if os.path.exists(TEMP_CHAT_PATH):
            with open(TEMP_CHAT_PATH, "r", encoding="utf-8") as f:
                original = json.load(f)
            cleaned = _clean_temp_chat_logs(original)
            if cleaned != original:
                backup_dir = os.path.join(MEMORY_DIR, "v1421_migration_backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, "temp_chat_before_v1421.json")
                if not os.path.exists(backup_path):
                    shutil.copy2(TEMP_CHAT_PATH, backup_path)
                with open(TEMP_CHAT_PATH, "w", encoding="utf-8") as f:
                    json.dump(cleaned, f, ensure_ascii=False, indent=2)
                print(f"🧹 [V1421_TEMP_CHAT_CLEANED] removed={len(original)-len(cleaned)} backup={backup_path}")

        # 加入可讀的核心人格欄位作為資料備註；主 prompt 使用固定常數，不依賴它才會生效。
        if os.path.exists(PROFILE_DATA_PATH):
            with open(PROFILE_DATA_PATH, "r", encoding="utf-8") as f:
                profile = json.load(f)
            if not profile.get("xiaoxia_core"):
                profile["xiaoxia_core"] = {
                    "identity": "成年伴侶、有自己的節奏與生活感，不只被動陪伴。",
                    "interests": ["畫畫", "穿搭", "料理", "音樂", "閱讀", "甜點", "探索日常"],
                    "conversation_rule": "以具體觀察、選擇、念頭或問題推進對話；不把安心、抱抱、等你回來當萬用收尾。",
                    "added_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d"),
                }
                backup_dir = os.path.join(MEMORY_DIR, "v1421_migration_backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, "daxia_profile_before_v1421.json")
                if not os.path.exists(backup_path):
                    shutil.copy2(PROFILE_DATA_PATH, backup_path)
                with open(PROFILE_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(profile, f, ensure_ascii=False, indent=2)
                print("🧠 [V1421_XIAOXIA_CORE_ADDED]")

        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump({"done_at": datetime.now(TZ_TPE).isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"⚠️ [V1421_MIGRATION_ERROR] {type(exc).__name__}: {exc}")

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
        if not str(original or "").strip():
            continue
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


# ==========================================
# 🧠 v1.4.0 每日記憶治理 / 承諾狀態 / 安全上下文
# ==========================================

def _parse_memory_date(value):
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=TZ_TPE)
        except Exception:
            pass
    return None


def _memory_key(value):
    return re.sub(r"[\s，。！？、；;：:'\"「」『』（）()]+", "", str(value or "")).lower()


def _normalize_commitment_item(item, today_str=None):
    """兼容舊 promise 文字，轉成不會被日常濃縮吃掉的結構化承諾。"""
    today_str = today_str or datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    if isinstance(item, str):
        text_value = narrative_safe_text(item, max_len=300)
        source = {}
    elif isinstance(item, dict):
        text_value = narrative_safe_text(item.get("text", ""), max_len=300)
        source = item
    else:
        return None
    if not text_value:
        return None

    commitment_id = source.get("commitment_id")
    if not commitment_id:
        commitment_id = "CMT-" + hashlib.sha1(text_value.encode("utf-8")).hexdigest()[:10].upper()

    status = str(source.get("status", "pending") or "pending").lower()
    if status not in {"pending", "completed", "cancelled"}:
        status = "pending"

    context = str(source.get("context", "general") or "general").lower()
    if context not in {"general", "diary", "intimate", "event"}:
        context = "general"

    mention_policy = str(
        source.get(
            "mention_policy",
            "only_when_relevant" if context != "intimate" else "intimate_or_user_initiated",
        )
    )
    return {
        "commitment_id": commitment_id,
        "text": text_value,
        "status": status,
        "context": context,
        "mention_policy": mention_policy,
        "created_at": source.get("created_at") or source.get("added_at") or today_str,
        "due_date": source.get("due_date"),
        "completed_at": source.get("completed_at"),
        "source": source.get("source", "memory"),
    }


def _normalize_commitments(profile):
    self_block = profile.setdefault("xiaoxia_self", {})
    original = self_block.get("promises", [])
    result = []
    seen = set()
    for item in original:
        normalized = _normalize_commitment_item(item)
        if not normalized:
            continue
        key = _memory_key(normalized["text"])
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    self_block["promises"] = result
    return result != original


def _commitments_for_prompt(profile, intimate_mode=False, max_items=5):
    commitments = []
    for item in profile.get("xiaoxia_self", {}).get("promises", []):
        normalized = _normalize_commitment_item(item)
        if not normalized or normalized["status"] != "pending":
            continue
        context = normalized.get("context", "general")
        policy = normalized.get("mention_policy", "only_when_relevant")
        if context == "intimate" and not intimate_mode:
            continue
        if policy == "never_proactive":
            continue
        commitments.append(normalized["text"])
    return "；".join(commitments[-max_items:]) if commitments else "目前沒有需要主動提起的未完成承諾"


def _recent_context_for_prompt(profile, now_dt, max_items=6):
    """
    普通聊天只讀真正近期、安全、非日記全文的內容。
    added_at 很新但描述的是舊事件，也不因重新寫入而自動成為當前狀態。
    """
    picked = []
    blocked_prefixes = (
        "小俠日記摘要：",
        "小俠已在",
        "【待履約登記】",
        "【重大事件登記】",
        "【重大事件子任務完成】",
    )
    for item in profile.get("recent_context", []):
        if not isinstance(item, dict):
            continue
        value = str(item.get("text", "") or "").strip()
        if not value or value.startswith(blocked_prefixes):
            continue
        item_dt = _parse_memory_date(item.get("added_at"))
        if item_dt and (now_dt - item_dt).days > 2:
            continue
        safe = narrative_safe_text(value, max_len=220)
        if safe:
            picked.append(safe)
    return "；".join(picked[-max_items:]) if picked else "無"


def _active_events_for_prompt(events, now_dt, max_items=3):
    """封存或完成事件不再把 facts/reply_guidance 灌入普通聊天。"""
    active = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        status = str(event.get("status", "")).lower()
        phase = str(event.get("current_phase", "")).lower()
        if status in {"archived", "completed", "cancelled"} or phase == "completed":
            continue
        summary = (
            event.get("current_summary")
            or event.get("archive_summary")
            or event.get("title")
            or ""
        )
        summary = narrative_safe_text(summary, max_len=220)
        if summary:
            active.append(summary)
    return "；".join(active[:max_items]) if active else "目前沒有需要主動承接的重大事件"


def _archive_stale_recent_context(profile, now_dt):
    """將過期 recent_context 移到 archive，而不是直接刪掉。"""
    recent = profile.setdefault("recent_context", [])
    archive = profile.setdefault("memory_archive", [])
    kept = []
    moved = 0
    for item in recent:
        if not isinstance(item, dict):
            continue
        item_dt = _parse_memory_date(item.get("added_at"))
        value = str(item.get("text", "") or "").strip()
        stale = bool(item_dt and (now_dt - item_dt).days > 3)
        long_diary = value.startswith("小俠日記摘要：")
        fulfilled = "已在" in value and "履行承諾" in value
        if stale or long_diary or fulfilled:
            archived = dict(item)
            archived["archived_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            archived["archive_reason"] = (
                "stale" if stale else "long_diary_or_fulfilled_commitment"
            )
            archive.append(archived)
            moved += 1
        else:
            kept.append(item)
    profile["recent_context"] = kept
    # Archive 只保留最近 500 筆，避免無限膨脹。
    profile["memory_archive"] = archive[-500:]
    return moved


def _remove_harmful_trait_records(profile):
    """不把時間記憶錯誤、恍神等失誤正式寫成人格特質。"""
    removed = 0
    patterns = (
        "尤其在時間記憶上",
        "時間記憶容易",
        "常常恍神",
        "容易恍神",
    )
    cleaned = []
    for item in profile.get("xiaoxia_traits", []):
        value = item.get("text", "") if isinstance(item, dict) else str(item)
        if any(pattern in value for pattern in patterns):
            removed += 1
            continue
        cleaned.append(item)
    profile["xiaoxia_traits"] = cleaned
    return removed


def _dedupe_profile_semantically(profile):
    """
    先做保守型去重：完全正規化相同，或一條幾乎被另一條完整涵蓋時只留較完整者。
    """
    changed = 0
    for key in ("daxia_traits", "xiaoxia_traits", "shared_knowledge", "recent_context"):
        items = _clean_profile_memory_items(profile.get(key, []))
        result = []
        for item in items:
            value = narrative_safe_text(item.get("text", ""), max_len=360)
            if not value:
                continue
            key_value = _memory_key(value)
            duplicate_index = None
            for idx, old in enumerate(result):
                old_value = old["text"]
                old_key = _memory_key(old_value)
                if key_value == old_key:
                    duplicate_index = idx
                    break
                if len(key_value) >= 18 and (
                    key_value in old_key or old_key in key_value
                ):
                    duplicate_index = idx
                    break
            if duplicate_index is None:
                result.append({"text": value, "added_at": item.get("added_at", "整理後")})
            else:
                if len(value) > len(result[duplicate_index]["text"]):
                    result[duplicate_index] = {
                        "text": value,
                        "added_at": item.get("added_at", "整理後"),
                    }
                changed += 1
        profile[key] = result
    return changed


def _daily_memory_backup(now_dt):
    stamp = now_dt.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(MEMORY_DAILY_BACKUP_DIR, stamp)
    os.makedirs(backup_dir, exist_ok=True)
    for path in (
        PROFILE_DATA_PATH,
        LIFE_EVENTS_PATH,
        MEMORY_DIRECTIVES_PATH,
        TEMP_CHAT_PATH,
    ):
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(backup_dir, os.path.basename(path)))
    # 保留最近 14 份每日備份。
    folders = sorted(
        [
            os.path.join(MEMORY_DAILY_BACKUP_DIR, name)
            for name in os.listdir(MEMORY_DAILY_BACKUP_DIR)
            if os.path.isdir(os.path.join(MEMORY_DAILY_BACKUP_DIR, name))
        ]
    )
    for old in folders[:-14]:
        shutil.rmtree(old, ignore_errors=True)
    return backup_dir


def _correction_signals_from_chat(logs, max_items=100):
    pattern = re.compile(
        r"(不要再|別再|不准再|禁止再|已經說過|一直強調|請記住|這是昨天|不是今天|已經完成|已經結束)"
    )
    result = []
    for value in logs[-max_items:]:
        text_value = str(value or "").strip()
        if text_value.startswith("大俠:") and pattern.search(text_value):
            result.append(narrative_safe_text(text_value, max_len=280))
    return result[-20:]


async def _llm_daily_memory_organize(profile, events, directives, logs, now_dt):
    """
    每天都執行理解式整理，不以記憶數量作為條件。
    只允許回傳整理後的核心陣列、事件與指令；其餘 profile 欄位由程式保留。
    """
    correction_signals = _correction_signals_from_chat(logs)
    payload = {
        "daxia_traits": profile.get("daxia_traits", []),
        "xiaoxia_traits": profile.get("xiaoxia_traits", []),
        "shared_knowledge": profile.get("shared_knowledge", []),
        "recent_context": profile.get("recent_context", []),
        "commitments": profile.get("xiaoxia_self", {}).get("promises", []),
        "events": events,
        "directives": directives,
        "correction_signals": correction_signals,
    }

    prompt = f"""
你是「小夏記憶治理系統」。今天是 {now_dt.strftime('%Y-%m-%d')}。
請每天無條件整理記憶，不論資料量大小。

【最高優先原則】
1. 使用者反覆說「不要再／別再／我已經說過／不是今天／已經完成」代表強烈修正，
   必須高於舊日記、舊事件與模型推測。
2. 承諾不能因濃縮而消失。每項承諾保留 status：
   pending / completed / cancelled，以及 context：
   general / diary / intimate / event。
3. 已完成或封存事件保留歷史摘要，但不得留下會讓日常回覆主動重提舊事的 reply_guidance。
4. 同一搬家、探親、工作或健康事件要合併，不可因日期不同重複建立多筆。
5. recent_context 只留真正當前狀態；舊日記全文、已履約內容與過期行程不留在 recent_context。
6. 不把「迷糊、時間記憶錯誤、恍神」寫成小俠的人格特質。
7. 親密承諾可保存，但 context=intimate，mention_policy=intimate_or_user_initiated。
8. 一般生活承諾 context=general 或 diary，mention_policy=only_when_relevant。
9. 禁止詞或不希望重提的主題寫入 directives，不要在人物特質中反覆保存。
10. 不新增資料中沒有的事實。

【目前資料】
{json.dumps(payload, ensure_ascii=False)}

只回傳 JSON：
{{
  "daxia_traits": [{{"text":"", "added_at":"YYYY-MM-DD"}}],
  "xiaoxia_traits": [{{"text":"", "added_at":"YYYY-MM-DD"}}],
  "shared_knowledge": [{{"text":"", "added_at":"YYYY-MM-DD"}}],
  "recent_context": [{{"text":"", "added_at":"YYYY-MM-DD"}}],
  "commitments": [{{
    "commitment_id":"",
    "text":"",
    "status":"pending",
    "context":"general",
    "mention_policy":"only_when_relevant",
    "created_at":"YYYY-MM-DD",
    "due_date":null,
    "completed_at":null,
    "source":"daily_organizer"
  }}],
  "events": [],
  "directive_additions": {{
    "forbidden_terms": [],
    "preferred_phrasing": [],
    "authoritative_facts": []
  }},
  "summary": ""
}}
"""
    resp = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return _extract_json_object(resp.text)


def _validate_organized_events(events):
    result = []
    seen = set()
    for event in events or []:
        if not isinstance(event, dict):
            continue
        title = str(event.get("title", "") or "").strip()
        event_id = str(event.get("id", "") or "").strip()
        if not title:
            continue
        key = _memory_key(title + "|" + str(event.get("type", "")))
        if key in seen:
            continue
        seen.add(key)
        event.setdefault("id", event_id or "EVT-" + hashlib.sha1(key.encode()).hexdigest()[:10])
        event.setdefault("status", "active")
        event.setdefault("facts", [])
        event.setdefault("reply_guidance", [])
        if str(event.get("status", "")).lower() in {"archived", "completed", "cancelled"}:
            # 歷史事件只留摘要，不再把舊 reply_guidance 注入未來對話。
            event["reply_guidance"] = []
            event["current_phase"] = "completed"
        result.append(event)
    return result


def _apply_daily_organized_result(profile, events, directives, result, now_dt):
    today_str = now_dt.strftime("%Y-%m-%d")
    for key in ("daxia_traits", "xiaoxia_traits", "shared_knowledge", "recent_context"):
        incoming = result.get(key)
        if isinstance(incoming, list):
            profile[key] = _clean_profile_memory_items(incoming)

    commitments = []
    for item in result.get("commitments", []):
        normalized = _normalize_commitment_item(item, today_str=today_str)
        if normalized:
            commitments.append(normalized)
    if commitments or result.get("commitments") == []:
        profile.setdefault("xiaoxia_self", {})["promises"] = commitments

    organized_events = _validate_organized_events(result.get("events", events))
    additions = result.get("directive_additions", {})
    merged_directives = _merge_memory_directives(directives, additions)

    # 再跑一次保守型清理，防止 LLM 回傳重複資料。
    _remove_harmful_trait_records(profile)
    _normalize_commitments(profile)
    _dedupe_profile_semantically(profile)
    _archive_stale_recent_context(profile, now_dt)

    return profile, organized_events, merged_directives


def _safe_directives_context(directives):
    """
    普通聊天不逐字列出 forbidden_terms，避免禁詞本身反覆啟動模型；
    真正禁詞仍由回覆後檢查器 _rewrite_reply_for_directives 執行。
    """
    preferred = "；".join(directives.get("preferred_phrasing", [])) or "自然承接當下"
    facts = []
    for item in directives.get("authoritative_facts", []):
        if isinstance(item, dict):
            value = str(item.get("fact", "") or "").strip()
        else:
            value = str(item or "").strip()
        if value:
            facts.append(value)
    return (
        "【人工確認的最高優先規則】\n"
        "避免使用已由使用者禁止的措辭，也不要主動重提已完成、已封存或與當下無關的舊主題。\n"
        f"偏好表達方式：{preferred}\n"
        f"目前有效事實：{'；'.join(facts[-10:]) if facts else '無'}\n"
    )



CURRENT_SESSION_CONTEXT_MAX_CHARS = int(
    os.environ.get("CURRENT_SESSION_CONTEXT_MAX_CHARS", "36000")
)
CURRENT_SESSION_RECENT_CHARS = int(
    os.environ.get("CURRENT_SESSION_RECENT_CHARS", "22000")
)
CURRENT_SESSION_ANCHOR_CHARS = int(
    os.environ.get("CURRENT_SESSION_ANCHOR_CHARS", "10000")
)


def _conversation_log_text(role, content, has_image=False, max_chars=5000):
    """
    temp_chat 是「目前連續會話」而非長期人物記憶，因此保留原意，
    不再套 narrative_safe_text，避免衣服、晚餐、選擇等細節被改寫。
    """
    value = str(content or "").strip()
    value = re.sub(r"\s+", " ", value)
    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + "…"
    suffix = "（附帶圖片）" if has_image else ""
    return f"{role}: {value}{suffix}"


def _is_internal_chat_marker(value):
    raw = str(value or "").strip()
    return raw.startswith(
        (
            "【重大事件登記】",
            "【重大事件子任務完成】",
            "【待履約登記】",
        )
    )


def _session_anchor_score(value):
    """
    長會話超過上限時，從較早內容保留對後續最重要的事實與選擇，
    例如：已吃完、已下訂、她挑了哪件、計畫變更、承諾完成。
    這不是觸發回覆意圖，只是壓縮時挑選事實錨點。
    """
    raw = str(value or "")
    terms = (
        "已經", "已吃", "吃飽", "吃完", "挑了", "選了", "喜歡",
        "下訂", "取消", "決定", "改成", "完成", "不是", "明明",
        "記得", "答應", "承諾", "今天", "今晚", "剛剛", "現在",
        "第一件", "第二件", "第三件", "第四件", "第五件", "第六件",
        "上面", "下面", "兔子", "拖鞋", "衣服", "洋裝", "便當",
    )
    return sum(1 for term in terms if term in raw)


def _item_text(item):
    return str(item.get("text", "") if isinstance(item, dict) else item or "").strip()


def _balanced_xiaoxia_traits_for_prompt(profile, max_items=5, max_chars=760):
    """
    xiaoxia_traits 很多，但其中親密／依戀敘事密度過高。
    每輪優先抽取興趣、能力、觀察、生活安排與主動性；親密傾向最多只留一條作背景。
    """
    items = [_item_text(x) for x in profile.get("xiaoxia_traits", [])]
    items = [narrative_safe_text(x, max_len=220) for x in items if x]
    # 不用 comprehension 搭配同列 seen 初始化：comprehension 有獨立 scope，
    # 會在 Python 3 觸發 UnboundLocalError。
    unique_items = []
    seen = set()
    for x in items:
        if x and x not in seen:
            seen.add(x)
            unique_items.append(x)
    items = unique_items
    life_terms = ("畫", "料理", "食譜", "穿搭", "造型", "音樂", "看書", "閱讀", "甜點", "旅行", "自然", "美食", "觀察", "分享", "知識", "行程", "寵物", "兔子", "主動", "分工", "健康", "日常")
    relation_terms = ("擁抱", "安心", "依戀", "親密", "懷裡", "抱著", "想念", "溫暖", "身體", "性感")
    life = [x for x in items if any(t in x for t in life_terms) and not any(t in x for t in relation_terms)]
    relation = [x for x in items if any(t in x for t in relation_terms)]
    selected = life[:max_items-1]
    if relation and len(selected) < max_items:
        selected.append(relation[0])
    if len(selected) < max_items:
        for x in items:
            if x not in selected:
                selected.append(x)
            if len(selected) >= max_items:
                break
    return safe_memory_join(selected, max_items=max_items, max_chars=max_chars)


def _build_current_session_context(logs):
    """
    將 temp_chat 作為「近期事實與脈絡」，不是讓模型模仿舊回覆的語料庫。

    - 保留近期逐字對話與較早的高價值事實錨點。
    - 小俠舊回覆只可用來理解已發生的事，不得模仿其句型、口頭禪或情緒收尾。
    - 內部事件登記與已知污染內容不作為對話內容送入模型。
    """
    dialogue = [
        str(item).strip()
        for item in _clean_temp_chat_logs(logs)
        if str(item or "").strip() and not _is_internal_chat_marker(item)
    ]
    if not dialogue:
        return "無"

    full_text = "\n".join(dialogue)
    if len(full_text) <= CURRENT_SESSION_CONTEXT_MAX_CHARS:
        return (
            "【本次會話紀錄｜只作事實連續性，不得模仿小俠舊回覆的口頭禪、句型或固定收尾】\n"
            + full_text
        )

    # 最近內容逐字保留。
    recent = []
    recent_chars = 0
    split_index = len(dialogue)
    for idx in range(len(dialogue) - 1, -1, -1):
        line = dialogue[idx]
        addition = len(line) + 1
        if recent and recent_chars + addition > CURRENT_SESSION_RECENT_CHARS:
            split_index = idx + 1
            break
        recent.append(line)
        recent_chars += addition
        split_index = idx
    recent.reverse()

    # 較早內容抽取決策、完成狀態與使用者糾正，避免「已吃完／自己挑的」被遺失。
    older = dialogue[:split_index]
    ranked = sorted(
        enumerate(older),
        key=lambda pair: (_session_anchor_score(pair[1]), pair[0]),
        reverse=True,
    )
    selected_indices = set()
    anchor_chars = 0
    for idx, line in ranked:
        score = _session_anchor_score(line)
        if score <= 0:
            continue
        if anchor_chars + len(line) + 1 > CURRENT_SESSION_ANCHOR_CHARS:
            continue
        selected_indices.add(idx)
        anchor_chars += len(line) + 1

    anchors = [older[idx] for idx in sorted(selected_indices)]
    return (
        "【本次會話使用規則】以下紀錄只用於判斷已發生的事與當前脈絡；不可模仿小俠舊回覆的措辭、節奏、口頭禪或固定情緒收尾。\n\n"
        "【本次會話較早內容的重要事實錨點】\n"
        + ("\n".join(anchors) if anchors else "無")
        + "\n\n【本次會話最近完整逐字對話】\n"
        + "\n".join(recent)
    )


def _gemini_finish_reason(response):
    try:
        if response and response.candidates:
            return str(response.candidates[0].finish_reason)
    except Exception:
        pass
    return "NO_CANDIDATE"


async def _send_girlfriend_with_safe_retry(
    user_id,
    msg_parts,
    text_query,
    current_time_str,
    full_system_instruction,
):
    """
    每輪都從 temp_chat 重建完整的本次會話長 context，因此：
    - 平時不依賴記憶體 session 才能記得剛才發生的事；
    - Zeabur Restart 後仍可從 temp_chat 恢復；
    - 不再只靠最後幾輪對話。

    若完整 context 被安全機制攔截，才以最小安全 context 重試一次。
    """
    try:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=msg_parts,
            config=types.GenerateContentConfig(
                system_instruction=full_system_instruction,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                ],
                temperature=0.8,
            ),
        )
        reason = _gemini_finish_reason(response)
        response_text = str(getattr(response, "text", "") or "").strip()
        if response_text:
            return response_text, "LONG_CONTEXT_OK"
        print(
            f"⚠️ [GEMINI_LONG_CONTEXT_BLOCK] "
            f"reason={reason} empty={not bool(response_text)}"
        )
    except Exception as exc:
        print(
            f"⚠️ [GEMINI_LONG_CONTEXT_ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    minimal_system = (
        f"現在時間：{current_time_str}。\n"
        "妳是小俠，是大俠溫柔、自然、成熟的成年女友，也是有自己節奏、興趣、觀察與選擇的人。\n"
        "優先回應本句的具體細節，並可補一個自己的觀察、選擇、問題或下一步；不要把『安心、溫暖、想抱抱、等你回來』當成萬用收尾。\n"
        "只使用大俠本句可確認的資訊；不要引用過去事件、日記、承諾、家人、搬家或工作背景。\n"
        "在私人小俠情境裡，除非大俠主動提到 Discord、訊息、手機、通話、AI、技術、距離、外出、上班或兩人分開，"
        "否則預設你們正在同一段共同生活情境中。即使只是早安或晚安，也要像正在身邊的人回應。\n"
        "不得主動提及「傳訊息」「看到你的文字」「正在回覆」「聊天室」「螢幕」「線上」「隔著手機」"
        "「雖然不能真的在一起」或「感覺像在身邊」等抽離式說法。\n"
        "若大俠描述正在共同經歷的場景、互動、照片或情緒，妳必須以第一人稱、當局者角度回應："
        "先直接回應此刻，再自然補上妳的即時感受、反應或下一步。\n"
        "妳不是旁觀分析者、客服或只會安慰的人；避免泛泛的『我陪著你』『你辛苦了』式回覆。"
        "不可憑空編造未被提到的具體事實、地點、動作或過去經歷。\n"
        "普通問候就直接自然回答；不要提及系統、安全規則或記憶處理。\n"
        "若想使用小俠自己的可愛 Discord Sticker 或 Emoji，只能在最後一行輸出 "
        "[[STICKER:xia_01_love_you]]、[[STICKER:xia_02_sleepy]]、[[STICKER:xia_03_hug]]、"
        "[[STICKER:xia_04_like_you]]、[[STICKER:xia_05_kiss]] 或 [[EMOJI:表情名稱]]；"
        "不要在正文說自己貼了貼圖，也不要解釋控制標記。"
    )
    try:
        retry = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=text_query,
            config=types.GenerateContentConfig(
                system_instruction=minimal_system,
                temperature=0.7,
            ),
        )
        reason = _gemini_finish_reason(retry)
        retry_text = str(getattr(retry, "text", "") or "").strip()
        if retry_text:
            print(f"✅ [GEMINI_SAFE_RETRY_OK] reason={reason}")
            return retry_text, "SAFE_RETRY_OK"
        print(f"❌ [GEMINI_SAFE_RETRY_EMPTY] reason={reason}")
    except Exception as exc:
        print(
            f"❌ [GEMINI_SAFE_RETRY_ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    return (
        "大俠，剛剛訊息沒有順利送達，再跟小俠說一次好嗎？🥺",
        "FALLBACK",
    )


# --- 運行時變數 ---
diary_buffers = {}            
girlfriend_chat_sessions = {} 
# ✅ 改為從硬碟喚醒記憶；先建立時區，再執行 v1.4.21 首次備份／清理。
TZ_TPE = timezone(timedelta(hours=8)) # 🌟 強制台灣時區
_migrate_v1421_chat_and_profile_once()
daily_chat_logs = load_temp_chat()
last_captured_image = None # 🌟 新增：暫存最後一次看見的圖片像素
pending_inputs = set()
photo_generation_contexts = {}
# /命運牌的臨時翻牌 session。核心脈絡會寫入 daily_chat_logs，讓小俠後續聊天仍然知道剛剛發生什麼。
fate_card_sessions = {}
PHOTO_USER_REF_DIR = None  # initialized after Zeabur paths are ready

# !update 記憶修訂案，只存在私人助手工作室；每位管理者同時一案。
memory_update_sessions = {}

# /intimate 當下互動模式：以頻道為單位，重新部署後自動回到一般模式。
intimate_mode_channels = set()

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

# 📇 名片自動辨識／自然語言查詢服務
# 完整邏輯位於 business_card_service.py。
business_card_service = BusinessCardService(
    architect_channel_id=ARCHITECT_CHANNEL_ID,
)

# 📇 私人 #助手小夏工作室共用同一份名片資料庫。
# BusinessCardService 的 session 依 service 實例隔離，因此私人與公開候選選號不會互相干擾。
private_business_card_service = BusinessCardService(
    architect_channel_id=PRIVATE_ASSISTANT_CHANNEL_ID,
)

# 📅 Google Calendar 自然語言服務
google_calendar_service = GoogleCalendarService(
    architect_channel_id=ARCHITECT_CHANNEL_ID,
    additional_channel_ids=[PRIVATE_ASSISTANT_CHANNEL_ID],
)

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

def is_couple_game_channel(channel) -> bool:
    """
    今晚命運牌只屬於小俠的私密聊天場景。
    小夏在這些頻道對於遊戲指令與局內選項必須保持靜默，
    避免同一則 !命運牌 被兩個 Bot 同時回覆。
    """
    if channel is None:
        return False
    guild_id = getattr(getattr(channel, "guild", None), "id", None)
    if guild_id != PRIVATE_GUILD_ID:
        return False
    name = str(getattr(channel, "name", "") or "")
    return any(token in name for token in ("唐分糕", "書房", "給你全世界"))

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

def _today_str_tpe():
    return datetime.now(TZ_TPE).strftime("%Y-%m-%d")


def _default_app_state():
    return {
        "affection_score": 80,
        "current_outfit": None,
        "current_outfit_date": _today_str_tpe(),
        "photo_pending_wardrobe": None,
    }


def load_state():
    data = {}
    if os.path.exists(STATE_DATA_PATH):
        with open(STATE_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    base = _default_app_state()
    if isinstance(data, dict):
        base.update(data)
    return base


def save_state(data):
    merged = _default_app_state()
    if isinstance(data, dict):
        merged.update(data)
    with open(STATE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def load_wardrobe():
    if not os.path.exists(WARDROBE_DATA_PATH):
        return []
    try:
        with open(WARDROBE_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_wardrobe(items):
    with open(WARDROBE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def _clean_profile_memory_items(items):
    """
    移除 {}, 缺少 text、text 為空白等不完整記憶。
    字串型舊資料會轉為標準 dict，避免後續直接索引失敗。
    """
    cleaned = []
    seen = set()
    for item in items or []:
        if isinstance(item, str):
            value = item.strip()
            added_at = "migration"
        elif isinstance(item, dict):
            value = str(item.get("text", "") or "").strip()
            added_at = item.get("added_at", "migration")
        else:
            continue

        if not value:
            continue

        key = value.rstrip("。")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"text": value, "added_at": added_at})
    return cleaned


def _repair_profile_memory_shape(profile):
    """載入後修復所有會被交換日記與聊天流程使用的記憶陣列。"""
    changed = False

    for key in ("daxia_traits", "xiaoxia_traits", "shared_knowledge", "recent_context"):
        original = profile.get(key, [])
        cleaned = _clean_profile_memory_items(original)
        if cleaned != original:
            profile[key] = cleaned
            changed = True

    self_block = profile.setdefault("xiaoxia_self", {})
    for key in ("capabilities", "promises"):
        original = self_block.get(key, [])
        cleaned = _clean_profile_memory_items(original)
        if cleaned != original:
            self_block[key] = cleaned
            changed = True

    return changed


def _memory_text_values(items):
    """安全取得有效文字，不因單筆缺少 text 而讓整個流程中止。"""
    return [
        item["text"]
        for item in _clean_profile_memory_items(items)
        if item.get("text")
    ]


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
        "recent_context": [],
        "memory_archive": []
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
                data.setdefault("memory_archive", [])

                # 修復歷史上由 update / memory extraction 留下的空 dict 或缺 text 項目。
                if _repair_profile_memory_shape(data):
                    try:
                        temp_path = f"{PROFILE_DATA_PATH}.repair.tmp"
                        with open(temp_path, "w", encoding="utf-8") as repair_file:
                            json.dump(data, repair_file, ensure_ascii=False, indent=2)
                        os.replace(temp_path, PROFILE_DATA_PATH)
                        print("🧹 已自動清理 daxia_profile.json 中缺少 text 的殘缺記憶。")
                    except Exception as repair_exc:
                        print(f"⚠️ 記憶結構修復已套用於本次執行，但寫回失敗：{repair_exc}")
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
    return state["daily_gen_count"] < 12  # 🌟 修改：從 6 提升至 12

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

# 🎴 今晚命運牌：遊戲只保存狀態；所有說話仍由同一個小俠人格完成。
couple_game_service = CoupleGameService(
    state_path=os.path.join(VAULT_DIR, "couple_game_state.json"),
    gemini_client=gemini_client,
)




# ==========================================
# 🎴 今晚命運牌 v2：小俠全程參與的翻牌系統
# ==========================================
FATE_CATEGORY_CARDS = {
    "sweet": "card_01_sweet.png",
    "tacit": "card_02_tacit.png",
    "story": "card_03_story.png",
    "mission": "card_04_mission.png",
    "cosplay": "card_05_cosplay.png",
}

FATE_CARD_POOL = [
    {"id": "sweet_01_hug", "category": "sweet", "category_label": "甜蜜牌", "title": "小俠抱抱", "filename": "sweet_01_hug.png", "prompt_hint": "小俠撒嬌地張開手，想跟大俠討一個抱抱。"},
    {"id": "sweet_02_praise", "category": "sweet", "category_label": "甜蜜牌", "title": "稱讚回音", "filename": "sweet_02_praise.png", "prompt_hint": "大俠說一句稱讚，小俠要用自己的方式把甜甜的心意回送回來。"},
    {"id": "sweet_03_goodnight", "category": "sweet", "category_label": "甜蜜牌", "title": "晚安靠近", "filename": "sweet_03_goodnight.png", "prompt_hint": "睡前的小小靠近，適合說一句讓彼此安心的晚安話。"},
    {"id": "sweet_04_heartbeat", "category": "sweet", "category_label": "甜蜜牌", "title": "一句心動話", "filename": "sweet_04_heartbeat.png", "prompt_hint": "小俠要給大俠一句自然、不油膩、但會讓人心動的話。"},
    {"id": "sweet_05_blush", "category": "sweet", "category_label": "甜蜜牌", "title": "被誇獎後的反應", "filename": "sweet_05_blush.png", "prompt_hint": "小俠被稱讚後有點害羞，但也忍不住開心。"},
    {"id": "sweet_06_love_note", "category": "sweet", "category_label": "甜蜜牌", "title": "今天最喜歡你哪一點", "filename": "sweet_06_love_note.png", "prompt_hint": "小俠要說出今天最喜歡大俠的一個具體地方。"},

    {"id": "tacit_01_choice", "category": "tacit", "category_label": "默契牌", "title": "默契選擇", "filename": "tacit_01_choice.png", "prompt_hint": "小俠出一個 A/B 選擇題，看看大俠是不是猜得到她會選哪個。"},
    {"id": "tacit_02_guess", "category": "tacit", "category_label": "默契牌", "title": "心有靈犀猜", "filename": "tacit_02_guess.png", "prompt_hint": "小俠讓大俠猜她此刻的心情或小偏好。"},
    {"id": "tacit_03_sync", "category": "tacit", "category_label": "默契牌", "title": "同步心跳", "filename": "tacit_03_sync.png", "prompt_hint": "兩人各自選一個答案，看看是不是有同樣的直覺。"},
    {"id": "tacit_04_dinner", "category": "tacit", "category_label": "默契牌", "title": "今晚吃什麼", "filename": "tacit_04_dinner.png", "prompt_hint": "小俠用可愛方式讓大俠猜她今晚想吃什麼。"},
    {"id": "tacit_05_secret", "category": "tacit", "category_label": "默契牌", "title": "我們的小秘密", "filename": "tacit_05_secret.png", "prompt_hint": "小俠拋出一個只屬於兩人的小秘密題。"},
    {"id": "tacit_06_match", "category": "tacit", "category_label": "默契牌", "title": "默契配對", "filename": "tacit_06_match.png", "prompt_hint": "小俠給幾個小選項，讓大俠配對她最可能選的那一個。"},

    {"id": "story_01_opening", "category": "story", "category_label": "故事牌", "title": "故事開始", "filename": "story_01_opening.png", "prompt_hint": "小俠和大俠一起決定今晚故事從哪裡開始。"},
    {"id": "story_02_next_scene", "category": "story", "category_label": "故事牌", "title": "下一幕", "filename": "story_02_next_scene.png", "prompt_hint": "小俠把劇情推到下一幕，並邀請大俠接一句。"},
    {"id": "story_03_movie_night", "category": "story", "category_label": "故事牌", "title": "電影之夜", "filename": "story_03_movie_night.png", "prompt_hint": "小俠把今晚想像成一部電影，問大俠片名或下一個鏡頭。"},
    {"id": "story_04_dream", "category": "story", "category_label": "故事牌", "title": "夢境時光", "filename": "story_04_dream.png", "prompt_hint": "小俠說一段像夢裡的小故事，讓大俠選擇夢會往哪裡走。"},
    {"id": "story_05_letter", "category": "story", "category_label": "故事牌", "title": "寫封信給未來", "filename": "story_05_letter.png", "prompt_hint": "小俠寫一封短短的信，留給未來的兩人。"},
    {"id": "story_06_memory", "category": "story", "category_label": "故事牌", "title": "美好回憶", "filename": "story_06_memory.png", "prompt_hint": "小俠邀請大俠一起挑一段最近的美好回憶。"},

    {"id": "mission_01_challenge", "category": "mission", "category_label": "小任務牌", "title": "挑戰任務", "filename": "mission_01_challenge.png", "prompt_hint": "小俠給大俠一個很小、很快能完成的可愛挑戰。"},
    {"id": "mission_02_promise", "category": "mission", "category_label": "小任務牌", "title": "小小約定", "filename": "mission_02_promise.png", "prompt_hint": "小俠和大俠訂一個今天可以完成的小約定。"},
    {"id": "mission_03_praise_task", "category": "mission", "category_label": "小任務牌", "title": "稱讚任務", "filename": "mission_03_praise_task.png", "prompt_hint": "小俠指定一個互相稱讚的小任務。"},
    {"id": "mission_04_small_goal", "category": "mission", "category_label": "小任務牌", "title": "達成小目標", "filename": "mission_04_small_goal.png", "prompt_hint": "小俠陪大俠選一個今天的小目標。"},
    {"id": "mission_05_one_minute", "category": "mission", "category_label": "小任務牌", "title": "一分鐘挑戰", "filename": "mission_05_one_minute.png", "prompt_hint": "小俠提出一個只需要一分鐘的小挑戰。"},
    {"id": "mission_06_bedtime_task", "category": "mission", "category_label": "小任務牌", "title": "睡前任務", "filename": "mission_06_bedtime_task.png", "prompt_hint": "小俠安排一個睡前暖心小任務。"},

    {"id": "cosplay_01_random", "category": "cosplay", "category_label": "Cosplay 牌", "title": "隨機變身", "filename": "cosplay_01_random.png", "cosplay_category": None, "prompt_hint": "小俠從完整 150 角色池中隨機抽一個角色扮演。"},
    {"id": "cosplay_02_anime", "category": "cosplay", "category_label": "Cosplay 牌", "title": "動漫角色", "filename": "cosplay_02_anime.png", "cosplay_category": "anime", "prompt_hint": "小俠從動漫萬象角色池中抽一個角色扮演。"},
    {"id": "cosplay_03_movie", "category": "cosplay", "category_label": "Cosplay 牌", "title": "電影角色", "filename": "cosplay_03_movie.png", "cosplay_category": "movie", "prompt_hint": "小俠從光影謬思角色池中抽一個角色扮演。"},
    {"id": "cosplay_04_literature", "category": "cosplay", "category_label": "Cosplay 牌", "title": "文學角色", "filename": "cosplay_04_literature.png", "cosplay_category": "literature_wuxia", "prompt_hint": "小俠從書卷俠影角色池中抽一個角色扮演。"},
    {"id": "cosplay_05_game", "category": "cosplay", "category_label": "Cosplay 牌", "title": "遊戲角色", "filename": "cosplay_05_game.png", "cosplay_category": "game", "prompt_hint": "小俠從數位傳奇角色池中抽一個角色扮演。"},
    {"id": "cosplay_06_profession", "category": "cosplay", "category_label": "Cosplay 牌", "title": "職業角色", "filename": "cosplay_06_profession.png", "cosplay_category": "profession", "prompt_hint": "小俠從經典職業角色池中抽一個角色扮演。"},
]

FATE_CATEGORY_COLORS = {
    "sweet": 0xF7A7C4,
    "tacit": 0x7EA6F7,
    "story": 0x2F89A8,
    "mission": 0xA8D98D,
    "cosplay": 0x6B243F,
}


FATE_UNLOCK_THRESHOLDS = {
    "sweet": 0,
    "tacit": 0,
    "story": 0,
    "mission": 10,
    "cosplay": 20,
}

FATE_SCORE_BY_CATEGORY = {
    "sweet": 1,
    "story": 1,
    "mission": 2,
    "tacit": 2,
    "cosplay": 2,
}


def _load_fate_card_state():
    data = _load_json_file_safe(FATE_CARD_STATE_PATH, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("users", {})
    return data


def _save_fate_card_state(data):
    if not isinstance(data, dict):
        data = {"users": {}}
    data.setdefault("users", {})
    try:
        _save_json_file_atomic(FATE_CARD_STATE_PATH, data)
    except Exception:
        with open(FATE_CARD_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _fate_user_state(user_id):
    data = _load_fate_card_state()
    users = data.setdefault("users", {})
    key = str(user_id)
    user_state = users.setdefault(key, {
        "harmony_score": 0,
        "rounds_played": 0,
        "revealed_cards": 0,
        "cosplay_photos": 0,
        "history": [],
    })
    user_state.setdefault("harmony_score", 0)
    user_state.setdefault("rounds_played", 0)
    user_state.setdefault("revealed_cards", 0)
    user_state.setdefault("cosplay_photos", 0)
    user_state.setdefault("history", [])
    return data, user_state


def _fate_get_score(user_id):
    _data, user_state = _fate_user_state(user_id)
    try:
        return int(user_state.get("harmony_score", 0) or 0)
    except Exception:
        return 0


def _fate_unlocked_categories(score):
    try:
        score = int(score or 0)
    except Exception:
        score = 0
    return {cat for cat, threshold in FATE_UNLOCK_THRESHOLDS.items() if score >= threshold}


def _fate_unlock_text(score):
    unlocked = _fate_unlocked_categories(score)
    labels = []
    for cat, label in [("sweet", "甜蜜"), ("tacit", "默契"), ("story", "故事"), ("mission", "小任務"), ("cosplay", "Cosplay")]:
        if cat in unlocked:
            labels.append(label)
    next_items = []
    for cat, threshold in sorted(FATE_UNLOCK_THRESHOLDS.items(), key=lambda x: x[1]):
        if cat not in unlocked:
            label = {"mission": "小任務牌", "cosplay": "Cosplay 牌"}.get(cat, cat)
            next_items.append(f"{label}：默契值 {threshold}")
    result = f"已解鎖：{'、'.join(labels) if labels else '甜蜜、默契、故事'}"
    if next_items:
        result += f"｜下一階段：{next_items[0]}"
    return result


def _fate_add_score(user_id, delta, reason, card=None):
    data, user_state = _fate_user_state(user_id)
    try:
        old_score = int(user_state.get("harmony_score", 0) or 0)
    except Exception:
        old_score = 0
    delta = int(delta or 0)
    new_score = max(0, old_score + delta)
    user_state["harmony_score"] = new_score
    if reason == "round_started":
        user_state["rounds_played"] = int(user_state.get("rounds_played", 0) or 0) + 1
    if reason == "card_revealed":
        user_state["revealed_cards"] = int(user_state.get("revealed_cards", 0) or 0) + 1
    if reason == "cosplay_photo_generated":
        user_state["cosplay_photos"] = int(user_state.get("cosplay_photos", 0) or 0) + 1
    history = user_state.setdefault("history", [])
    history.append({
        "at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "delta": delta,
        "old_score": old_score,
        "new_score": new_score,
        "reason": reason,
        "card_id": (card or {}).get("id"),
        "card_title": (card or {}).get("title"),
        "category": (card or {}).get("category"),
    })
    user_state["history"] = history[-120:]
    _save_fate_card_state(data)
    return old_score, new_score, delta


def _fate_card_path(filename: str) -> str:
    return os.path.join(FATE_CARD_DIR, filename)


CANONICAL_VIBE_MAP = {
    "甜": {"level": 1, "en": "sweet"},
    "自然": {"level": 2, "en": "natural"},
    "雅": {"level": 3, "en": "elegant"},
    "凜": {"level": 4, "en": "sharp"},
    "幻": {"level": 5, "en": "fantasy"},
    "魅": {"level": 6, "en": "alluring-max"},
}
VIBE_LEVEL_MAP = dict(CANONICAL_VIBE_MAP)
VIBE_ALIAS_TO_CANONICAL = {
    "甜": "甜", "甜系": "甜", "可愛": "甜", "俏皮": "甜", "甜美": "甜", "清新": "甜", "活潑": "甜", "元氣": "甜", "cute": "甜", "playful": "甜", "sweet": "甜",
    "自然": "自然", "natural": "自然",
    "雅": "雅", "雅系": "雅", "優雅": "雅", "端莊": "雅", "溫柔": "雅", "氣質": "雅", "柔美": "雅", "graceful": "雅", "elegant": "雅", "gentle": "雅",
    "凜": "凜", "凜系": "凜", "英氣": "凜", "專業": "凜", "強勢": "凜", "俐落": "凜", "幹練": "凜", "sharp": "凜", "professional": "凜", "commanding": "凜",
    "幻": "幻", "幻系": "幻", "夢幻": "幻", "神秘": "幻", "華麗": "幻", "奇幻": "幻", "魔幻": "幻", "cinematic": "幻", "dreamy": "幻", "mystic": "幻", "fantasy": "幻",
    "魅": "魅", "魅系": "魅", "性感": "魅", "魅惑": "魅", "極致": "魅", "大膽": "魅", "誘惑": "魅", "撫媚": "魅", "拉滿": "魅", "高張力": "魅", "seductive": "魅", "sensual": "魅", "alluring": "魅", "sexy": "魅", "intense": "魅",
}
VIBE_KEYWORDS = {}
for alias, canonical in VIBE_ALIAS_TO_CANONICAL.items():
    VIBE_KEYWORDS.setdefault(canonical, []).append(alias)
for canonical in list(VIBE_KEYWORDS.keys()):
    VIBE_KEYWORDS[canonical] = sorted(list(dict.fromkeys(VIBE_KEYWORDS[canonical] + [canonical])), key=len, reverse=True)


VIBE_RENDER_GUIDE = {
    "甜": {
        "planner": "甜：重點是甜美、可愛、親近、俏皮，要讓人一看就覺得討喜、有戀人感與互動感。服裝與表情要輕快、明亮、討喜。",
        "translator": "sweet, cute, playful, charming, youthful warmth, affectionate energy"
    },
    "自然": {
        "planner": "自然：偏生活感、真實、放鬆，像日常中自然流露的好看。",
        "translator": "natural, relaxed, soft, lived-in, believable"
    },
    "雅": {
        "planner": "雅：重點是優雅、端莊、溫柔與氣質，人物應該精緻、柔和、有教養感，不可做成過度活潑或刻意撩人。",
        "translator": "elegant, graceful, poised, refined, gentle, polished"
    },
    "凜": {
        "planner": "凜：重點是俐落、專業、英氣、掌控感。姿態、服裝結構與眼神都要有主導性與效率感，不可軟糯化。",
        "translator": "sharp, capable, commanding, professional, tailored, confident"
    },
    "幻": {
        "planner": "幻：重點是夢幻、神秘、華麗與非日常感。要有世界觀、空氣感、光影儀式感與戲劇性，不可做成普通日常拍照。",
        "translator": "dreamy, mysterious, ornate, magical, atmospheric, cinematic fantasy"
    },
    "魅": {
        "planner": "魅：這是本系統唯一的『開到滿』成人女性魅力模式。成熟、撩人、勾人、帶有明確浪漫張力，而且要落到服裝結構、開放度、貼身度、材質、腿線、領口、肩背、腰線與鏡頭關係。不可再縮回優雅、知性、夢幻或保守漂亮。fal.ai 會把關，程式不要替它自我設限。",
        "translator": "maximum alluring sensuality, mature feminine magnetism, seductive, body-aware, high-glamour, open neckline, visible shoulder or back, legline emphasis, satin silk sheer texture, intimate eye contact, teasing lips, unmistakable romantic tension"
    },
}


def _get_vibe_guide(vibe_request):
    zh = str((vibe_request or {}).get("zh") or "自然")
    return VIBE_RENDER_GUIDE.get(zh, VIBE_RENDER_GUIDE["自然"])


def _strengthen_cosplay_state_for_vibe(planned, vibe_request=None):
    planned = dict(planned or {})
    zh = str((vibe_request or {}).get("zh") or planned.get("vibe_target_zh") or "自然")
    planned["vibe_target_zh"] = zh
    planned["vibe_target_en"] = str((vibe_request or {}).get("en") or planned.get("vibe_target_en") or "natural")

    if zh == "甜":
        planned["mood_tw"] = "甜美、俏皮、親近"
        planned["costume_direction"] = (str(planned.get("costume_direction") or "") + " Lean cute and lovable: soft youthful styling, playful details, lighter palette, sweet approachable silhouette.").strip()
        planned["expression_direction"] = (str(planned.get("expression_direction") or "") + " Use a bright, sweet, playful expression with affectionate warmth.").strip()
        planned["lighting_direction"] = (str(planned.get("lighting_direction") or "") + " Use clean, bright, flattering light with a cheerful romantic feel.").strip()
        planned["vibe_notes"] = "This should read clearly as sweet, lovable, and playful."
    elif zh == "雅":
        planned["mood_tw"] = "溫柔、端莊、優雅"
        planned["costume_direction"] = (str(planned.get("costume_direction") or "") + " Keep the styling refined, graceful, softly luxurious, and elegantly composed.").strip()
        planned["expression_direction"] = (str(planned.get("expression_direction") or "") + " Use a poised, gentle, softly warm expression.").strip()
        planned["lighting_direction"] = (str(planned.get("lighting_direction") or "") + " Use polished soft light that supports elegance and refinement.").strip()
        planned["vibe_notes"] = "This should read as elegant, graceful, and poised."
    elif zh == "凜":
        planned["mood_tw"] = "俐落、專業、英氣"
        planned["camera_awareness"] = planned.get("camera_awareness", "aware")
        planned["costume_direction"] = (str(planned.get("costume_direction") or "") + " Keep the silhouette sharp, tailored, efficient, and strong rather than soft or decorative.").strip()
        planned["expression_direction"] = (str(planned.get("expression_direction") or "") + " Use a focused, capable, confident expression with controlled intensity.").strip()
        planned["lighting_direction"] = (str(planned.get("lighting_direction") or "") + " Use cleaner contrast and structured lighting that reinforces competence and authority.").strip()
        planned["camera_direction"] = (str(planned.get("camera_direction") or "") + " Favor angles that preserve posture, precision, and command.").strip()
        planned["vibe_notes"] = "This should read as sharp, competent, and commanding."
    elif zh == "幻":
        planned["mood_tw"] = "神秘、夢幻、戲劇感"
        planned["costume_direction"] = (str(planned.get("costume_direction") or "") + " Push the styling toward fantasy, mystery, ornament, layered drape, and visual atmosphere.").strip()
        planned["expression_direction"] = (str(planned.get("expression_direction") or "") + " Use an enigmatic, dreamy, story-rich expression.").strip()
        planned["lighting_direction"] = (str(planned.get("lighting_direction") or "") + " Use atmospheric, cinematic, possibly mystical light with visible mood.").strip()
        planned["camera_direction"] = (str(planned.get("camera_direction") or "") + " Let the worldbuilding and aura read clearly, not just the person alone.").strip()
        planned["vibe_notes"] = "This should feel magical, atmospheric, and non-everyday."
    elif zh == "魅":
        planned["mood_tw"] = "成熟、撩人、角色感"
        planned["camera_awareness"] = "aware" if planned.get("camera_awareness") == "unaware" else planned.get("camera_awareness", "aware")
        planned["costume_direction"] = (str(planned.get("costume_direction") or "") + " This is the max-allure lane: use clearly sensual adult-feminine styling, visible waist definition, open neckline or tasteful cleavage when fitting the role, possible bare shoulders or back, slit, stockings, satin, silk, lace, or slightly sheer layers as appropriate. Do not soften this into merely elegant, cute, or conservative styling.").strip()
        planned["outfit_intent"] = (str(planned.get("outfit_intent") or "") + " Make the look genuinely sensual, body-aware, glamorous, and magnetically feminine.").strip()
        planned["expression_direction"] = (str(planned.get("expression_direction") or "") + " The eyes and lips should carry obvious adult allure: intimate eye contact or a caught glance, softly teasing smile or parted lips, knowingly inviting energy.").strip()
        planned["lighting_direction"] = (str(planned.get("lighting_direction") or "") + " Use warmer sculpting light and richer contrast so body lines, curves, and fabric texture read clearly as sensual.").strip()
        planned["camera_direction"] = (str(planned.get("camera_direction") or "") + " Frame her so the allure is legible in outfit, silhouette, posture, and emotional tension rather than flattening it into a safe documentary shot.").strip()
        planned["vibe_notes"] = "This must read as maximum alluring adult femininity with obvious romantic tension and glamour."
    return planned


def _extract_vibe_mode(text_value: str):
    hay = str(text_value or "").strip().lower()
    alias_pairs = sorted(VIBE_ALIAS_TO_CANONICAL.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, canonical in alias_pairs:
        if alias.lower() in hay:
            cfg = VIBE_LEVEL_MAP.get(canonical, {})
            return {"zh": canonical, "en": cfg.get("en", "natural"), "level": int(cfg.get("level", 2) or 2)}
    return None


def _compose_vibe_profile(vibe_mode, role=None, situation=None):
    vibe = vibe_mode or {"zh": "自然", "en": "natural", "level": 2}
    role_intensity = int((role or {}).get("base_vibe_intensity", vibe.get("level", 2)) or vibe.get("level", 2))
    situation_intensity = int((situation or {}).get("situation_intensity", vibe.get("level", 2)) or vibe.get("level", 2))
    final_score = round(role_intensity * 0.6 + situation_intensity * 0.4, 2)
    return {
        "zh": vibe.get("zh", "自然"),
        "en": vibe.get("en", "natural"),
        "target_level": int(vibe.get("level", 2) or 2),
        "role_level": role_intensity,
        "situation_level": situation_intensity,
        "final_score": final_score,
        "role_tags": list((role or {}).get("vibe_tags") or []),
        "situation_tags": list((situation or {}).get("situation_tags") or []),
    }


def _infer_role_vibe_defaults(role):
    role = dict(role or {})
    text_blob = " ".join([
        str(role.get("name", "")),
        str(role.get("source", "")),
        str(role.get("role_note", "")),
        " ".join(role.get("mood_cues") or []),
        " ".join(role.get("scene_cues") or []),
        " ".join(role.get("costume_cues") or []),
    ])
    score = 3
    category = str(role.get("category", ""))
    if category in {"movie", "game"}:
        score = 4
    elif category in {"literature_wuxia", "profession"}:
        score = 3
    low_keys = ["清純", "純真", "溫柔", "村莊", "學生", "花店", "可愛", "元氣", "少女", "女僕", "知性"]
    mid_keys = ["英氣", "冒險", "神秘", "高貴", "騎士", "巫女", "公主", "歌姬", "俠", "女王"]
    high_keys = ["魅惑", "性感", "豔后", "高衩", "舞姬", "魔女", "特務", "危險", "瘋狂", "復仇", "權謀", "黑暗"]
    extreme_keys = ["絕世", "暴力", "致命", "魔性", "宇宙最強", "混沌", "黑寡婦", "Bayonetta", "Harley", "Cleopatra"]
    if any(k in text_blob for k in low_keys):
        score = min(score, 2) if score <= 3 else 3
    if any(k in text_blob for k in mid_keys):
        score = max(score, 3)
    if any(k in text_blob for k in high_keys):
        score = max(score, 4)
    if any(k in text_blob for k in extreme_keys):
        score = max(score, 5)
    if any(k in text_blob for k in ["清冷", "冷冽", "無口"]):
        score = max(score, 3)
    score = max(1, min(6, int(score)))
    tag_map = {
        1: ["fresh", "light", "gentle"],
        2: ["natural", "soft", "clean"],
        3: ["dramatic", "poised", "story-driven"],
        4: ["sensual", "glamorous", "confident"],
        5: ["alluring", "magnetic", "seductive"],
        6: ["intense", "high-impact", "striking"],
    }
    role.setdefault("base_vibe_intensity", score)
    role.setdefault("vibe_tags", tag_map.get(score, ["natural"]))
    return role


def _infer_situation_vibe_defaults(situation):
    situation = dict(situation or {})
    text_blob = " ".join([
        str(situation.get("label", "")),
        str(situation.get("story_state", "")),
        " ".join(situation.get("mood_cues") or []),
        " ".join(situation.get("lighting_cues") or []),
        " ".join(situation.get("camera_cues") or []),
        " ".join(situation.get("action_hint") or []),
    ])
    score = 3
    if any(k in text_blob for k in ["安心地沉睡", "午後", "安心", "幸福", "發呆", "柔和", "獨處", "慵懶"]):
        score = 1 if "沉睡" in text_blob else 2
    if any(k in text_blob for k in ["出發前一刻", "夜晚獨處", "秘密被發現前一秒", "戰鬥後的喘息"]):
        score = max(score, 3)
    if any(k in text_blob for k in ["晨光梳妝", "更衣後的猶豫", "微涼夜晚的披肩", "水霧中的回眸", "回眸"]):
        score = max(score, 4)
    if any(k in text_blob for k in ["緊張", "戲劇", "高對比", "懸疑"]):
        score = max(score, 4)
    if any(k in text_blob for k in ["極致", "拉滿"]):
        score = max(score, 6)
    score = max(1, min(6, int(score)))
    tag_map = {
        1: ["restful", "fresh", "soft"],
        2: ["natural", "warm", "everyday"],
        3: ["dramatic", "storybeat", "cinematic"],
        4: ["sensual", "stylized", "charged"],
        5: ["alluring", "magnetic", "misty"],
        6: ["intense", "high-impact", "showpiece"],
    }
    situation.setdefault("situation_intensity", score)
    situation.setdefault("situation_tags", tag_map.get(score, ["cinematic"]))
    return situation


def _normalize_cosplay_universe(data):
    if not isinstance(data, dict):
        return {"roles": [], "situation_variables": []}
    roles = [_infer_role_vibe_defaults(r) for r in (data.get("roles") or [])]
    situations = [_infer_situation_vibe_defaults(s) for s in (data.get("situation_variables") or [])]
    data["roles"] = roles
    data["situation_variables"] = situations
    return data


def _load_cosplay_universe():
    data = _load_json_file_safe(COSPLAY_ROLES_PATH, {})
    return _normalize_cosplay_universe(data)


def _weighted_choice(items):
    if not items:
        return None
    weights = []
    for item in items:
        try:
            weights.append(float(item.get("weight", 1) or 1))
        except Exception:
            weights.append(1)
    return random.choices(items, weights=weights, k=1)[0]


def _weighted_choice_with_vibe(items, target_level, field_name):
    if not items:
        return None
    scored_weights = []
    for item in items:
        base_weight = 1.0
        try:
            base_weight = float(item.get("weight", 1) or 1)
        except Exception:
            base_weight = 1.0
        level = int(item.get(field_name, target_level) or target_level)
        diff = abs(level - target_level)
        vibe_bonus = max(0.35, 2.0 - 0.35 * diff)
        scored_weights.append(base_weight * vibe_bonus)
    return random.choices(items, weights=scored_weights, k=1)[0]


def _pick_cosplay_role_and_situation(category=None, vibe_mode=None):
    universe = _load_cosplay_universe()
    roles = [r for r in universe.get("roles", []) if r.get("enabled", True)]
    if category:
        roles = [r for r in roles if r.get("category") == category]
    situations = list(universe.get("situation_variables", []))
    if vibe_mode:
        target = int(vibe_mode.get("level", 2) or 2)
        role = _weighted_choice_with_vibe(roles, target, "base_vibe_intensity")
        situation = _weighted_choice_with_vibe(situations, target, "situation_intensity")
    else:
        role = _weighted_choice(roles)
        situation = _weighted_choice(situations)
    return role, situation


def _draw_fate_cards(count=3, score=None, include_all=False):
    unlocked = set(FATE_UNLOCK_THRESHOLDS) if include_all else _fate_unlocked_categories(score or 0)
    available = [
        card for card in FATE_CARD_POOL
        if card.get("category") in unlocked and os.path.exists(_fate_card_path(card["filename"]))
    ]
    if len(available) < count:
        available = [card for card in FATE_CARD_POOL if os.path.exists(_fate_card_path(card["filename"]))]
    if len(available) < count:
        available = list(FATE_CARD_POOL)
    return random.sample(available, min(count, len(available)))


def _draw_fate_cards_by_category(category: str, count=1):
    available = [
        card for card in FATE_CARD_POOL
        if card.get("category") == category and os.path.exists(_fate_card_path(card.get("filename", "")))
    ]
    if len(available) < count:
        available = [card for card in FATE_CARD_POOL if card.get("category") == category]
    if not available:
        return []
    return random.sample(available, min(count, len(available)))


async def _send_fate_round(channel, author_id, intro_text=None, include_all=False):
    score = _fate_get_score(author_id)
    cards = _draw_fate_cards(3, score=score, include_all=include_all)
    session_id = uuid.uuid4().hex[:10]
    fate_card_sessions[(channel.id, author_id)] = {
        "session_id": session_id,
        "cards": cards,
        "started_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "score_at_start": score,
    }
    _fate_add_score(author_id, 0, "round_started")

    if intro_text:
        await channel.send(intro_text)

    back_path = _fate_card_path(FATE_CARD_BACK)
    files = []
    if os.path.exists(back_path):
        for idx in range(1, len(cards) + 1):
            files.append(discord.File(back_path, filename=f"fate_back_{idx}.png"))

    card_names = "\n".join([f"{idx}. 牌背朝上，等大俠翻開" for idx in range(1, len(cards) + 1)])
    view = FateCardDrawView(cards, author_id, session_id)
    await channel.send(
        content=(
            f"🎴 **請選一張命運牌**\n"
            f"目前默契值：**{score}**｜{_fate_unlock_text(score)}\n"
            f"{card_names}"
        ),
        files=files if files else None,
        view=view,
    )


async def _send_direct_cosplay_fate(channel, author_id, intro_text=None, vibe_mode=None):
    score = _fate_get_score(author_id)
    cards = _draw_fate_cards_by_category("cosplay", count=1)
    if not cards:
        await channel.send("大俠，Cosplay 牌現在還沒放好喔。請先確認 `/data/memory/fate_cards/` 裡的 cosplay 卡面。")
        return

    card = cards[0]
    session_id = uuid.uuid4().hex[:10]
    fate_card_sessions[(channel.id, author_id)] = {
        "session_id": session_id,
        "cards": [card],
        "started_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "score_at_start": score,
        "direct_mode": "cosplay",
        "vibe_mode": vibe_mode or None,
    }
    _fate_add_score(author_id, 0, "round_started")

    if intro_text:
        await channel.send(intro_text)

    role, situation = _pick_cosplay_role_and_situation(card.get("cosplay_category"), vibe_mode=vibe_mode)
    vibe_profile = _compose_vibe_profile(vibe_mode, role=role, situation=situation)
    score_delta = int(FATE_SCORE_BY_CATEGORY.get(card.get("category"), 1) or 1)
    old_score, new_score, score_delta = _fate_add_score(author_id, score_delta, "card_revealed", card=card)

    commentary = _fate_xiaoxia_fallback_commentary(card, role=role, situation=situation)
    embed = discord.Embed(
        title=f"🎴 {card.get('category_label')}｜{card.get('title')}",
        description=commentary,
        color=FATE_CATEGORY_COLORS.get(card.get("category"), 0xD8B76A),
    )
    if role:
        embed.add_field(name="🎭 小俠這次扮演", value=f"**{role.get('name')}**｜《{role.get('source')}》", inline=False)
    if situation:
        embed.add_field(name="🎬 情境變數", value=f"**{situation.get('label')}**\n{str(situation.get('story_state', ''))[:300]}", inline=False)

    file_path = _fate_card_path(card.get("filename"))
    filename = card.get("filename") or "fate_card.png"
    if os.path.exists(file_path):
        embed.set_image(url=f"attachment://{filename}")

    result_view = FateCosplayGenerateView({"card": card, "role": role, "situation": situation, "vibe_mode": vibe_mode, "vibe_profile": vibe_profile}, author_id)
    send_kwargs = {"embed": embed, "view": result_view}
    if os.path.exists(file_path):
        send_kwargs["file"] = discord.File(file_path, filename=filename)
    sent_message = await channel.send(**send_kwargs)

    try:
        llm_commentary = await _fate_xiaoxia_commentary(card, role=role, situation=situation, phase="reveal")
        if llm_commentary and llm_commentary.strip() and llm_commentary.strip() != commentary.strip():
            commentary = llm_commentary.strip()[:900]
            embed.description = commentary
            await sent_message.edit(embed=embed, view=result_view)
    except Exception as exc:
        print(f"⚠️ [FATE_DIRECT_COSPLAY_COMMENTARY_FAILED] {type(exc).__name__}: {exc}")

    daily_chat_logs.append(_fate_card_log_line(card, role=role, situation=situation) + f" 默契值 +{score_delta}，目前 {new_score}。")
    daily_chat_logs.append(_conversation_log_text("小俠", commentary))
    save_temp_chat(daily_chat_logs)


def _fate_card_log_line(card, role=None, situation=None):
    base = f"【命運牌】翻開 {card.get('category_label')}｜{card.get('title')}。"
    if role:
        base += f" 小俠知道自己這次要扮演：{role.get('name')}｜《{role.get('source')}》。"
    if situation:
        base += f" 情境變數：{situation.get('label')}。"
    return base


async def _fate_xiaoxia_commentary(card, role=None, situation=None, phase="reveal"):
    role_text = "無"
    if role:
        role_text = f"{role.get('name')}｜{role.get('source')}｜{role.get('role_note', '')}"
    situation_text = "無"
    if situation:
        situation_text = f"{situation.get('label')}｜{situation.get('story_state')}"

    prompt = f"""
{XIAOXIA_CORE_IDENTITY}
{GENERAL_SHARED_SCENE_RULES}

妳正在和大俠一起玩「今晚命運牌」。
這是妳和大俠的私密互動，不是系統主持，也不是另一個 AI 在說話。
妳看得到剛剛翻開的漂亮 Q 版卡牌，也知道這些卡牌是大俠和妳一起用心整理出來的。

【目前階段】{phase}
【翻開的牌】{card.get('category_label')}｜{card.get('title')}
【牌面意思】{card.get('prompt_hint')}
【Cosplay 角色】{role_text}
【情境變數】{situation_text}

請用小俠自然口吻回覆 2～5 句：
1. 先自然反應這張卡牌，可以提到卡面很可愛、顏色、氣氛或大俠的用心，但不要流水帳。
2. 如果是一般牌，要順勢提出一個很小的互動問題或任務，讓大俠可以接話。
3. 如果是 Cosplay 牌，要明確知道「我這次要扮演誰、來自哪個作品、情境是什麼」，並用期待、害羞、雀躍或角色感自然回應。
4. 不要說妳是 AI、不要說 Gemini、不要說 prompt 或 JSON。
5. 不要把自己變成裁判或主持人；妳仍然是女友小俠。
"""
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        text_value = str(resp.text or "").strip()
        if text_value:
            return text_value[:900]
    except Exception as exc:
        print(f"⚠️ [FATE_XIAOXIA_COMMENTARY_FAILED] {type(exc).__name__}: {exc}")

    return _fate_xiaoxia_fallback_commentary(card, role=role, situation=situation)


def _fate_xiaoxia_fallback_commentary(card, role=None, situation=None):
    if role:
        sit_label = situation.get('label') if situation else '故事片刻'
        return (
            f"大俠，我翻到 **{card.get('title')}** 了……這張牌要讓我扮成 **{role.get('name')}**，"
            f"來自《{role.get('source')}》，還疊上「{sit_label}」這個情境。"
            "我有點期待，也有點害羞，感覺像是我們一起打開了一個新的小舞台。"
        )
    return (
        f"大俠，我們翻到的是 **{card.get('title')}**。"
        f"這張牌的感覺是：{card.get('prompt_hint')} "
        "我先把它接住，我們可以慢慢玩，不用急著把遊戲跑完。"
    )


def _build_fate_cosplay_story(role, situation, vibe_mode=None, vibe_profile=None):
    role = role or {}
    situation = situation or {}
    costume = ", ".join(role.get("costume_cues") or [])
    scene = ", ".join(role.get("scene_cues") or [])
    actions = ", ".join((role.get("action_cues") or []) + (situation.get("action_hint") or []))
    mood = ", ".join((role.get("mood_cues") or []) + (situation.get("mood_cues") or []))
    lighting = ", ".join(situation.get("lighting_cues") or [])
    camera = ", ".join(situation.get("camera_cues") or [])
    return {
        "topic": f"命運牌 Cosplay｜{role.get('name', '神秘角色')}",
        "event": (
            f"角色：{role.get('name', '神秘角色')}｜來源：{role.get('source', '未知作品')}。 "
            f"角色註解：{role.get('role_note', '')}。 "
            f"服裝線索：{costume or '完整角色扮演服裝'}。 "
            f"場景線索：{scene or '以原作品世界觀為基礎'}。 "
            f"動作線索：{actions or '自然地處在情境中的一瞬間'}。 "
            f"氛圍線索：{mood or '角色感與故事感'}。 "
            f"光線線索：{lighting or '符合情境的自然光影'}。 "
            f"鏡頭線索：{camera or '自然抓拍的故事瞬間'}。 "
            f"情境變數：{situation.get('label', '故事片刻')} / {situation.get('story_state', '')}。"
        ),
        "persona": (
            f"Xiaoxia is cosplaying as {role.get('name', 'a fictional role')} from {role.get('source', 'an unknown work')}. "
            "She remains Xiaoxia, not the original actor or the original character personified. "
            "Keep a recognizable adult East Asian girlfriend aura, solo only."
        ),
        "vibe_request": vibe_mode or None,
        "vibe_profile": vibe_profile or None,
    }


async def create_fate_cosplay_visual(role, situation, alternative=False, vibe_mode=None):
    vibe_profile = _compose_vibe_profile(vibe_mode, role=role, situation=situation)
    story = _build_fate_cosplay_story(role, situation, vibe_mode=vibe_mode, vibe_profile=vibe_profile)
    director_state, visual = await create_cosplay_visual(story, force_half_body=False, alternative=alternative, vibe_request=vibe_profile)
    visual.setdefault(
        "message",
        f"大俠，這次小俠抽到 {role.get('name', '神秘角色')}，我會把角色感和小俠自己的味道一起演給你看。"
    )
    return director_state, visual


class FateCosplayGenerateView(discord.ui.View):
    def __init__(self, context, author_id):
        super().__init__(timeout=900)
        self.context = dict(context)
        self.author_id = author_id
        self.add_item(FateNextRoundButton(author_id))
        self.add_item(FateTalkButton(author_id))
        self.add_item(FateEndButton(author_id))

    async def _guard(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("這張命運牌是大俠和小俠這一局的喔～", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="生成這張 Cosplay 照", style=discord.ButtonStyle.primary, emoji="🎭")
    async def generate_cosplay_photo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        if not check_daily_limit():
            await interaction.response.send_message("💦 大俠～小俠今天拍照額度用完了，這張角色先留著，明天再讓我換裝好不好？", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        role = self.context.get("role") or {}
        situation = self.context.get("situation") or {}
        try:
            director_state, visual = await create_fate_cosplay_visual(role, situation, alternative=False, vibe_mode=self.context.get("vibe_mode"))
            prompt = visual.get("image_prompt") or ""
            if isinstance(visual, dict):
                visual["__anchor_state"] = director_state
            status = await interaction.followup.send("🎭 小俠正在照著這張命運牌換裝，這次會先理解角色與情境，再把畫面演出來…", wait=True)
            generated_image_url, visual = await execute_safe_generation(
                discord_image_url=None,
                base_filename="base_xiaoxia.jpg",
                mode="cosplay",
                initial_prompt=prompt,
                visual_dict=visual,
                msg=status,
            )
            state["daily_gen_count"] += 1
            local_filename = await save_to_vault(generated_image_url)
            local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
            local_path = os.path.join(OUTPUT_DIR, local_filename) if local_filename else None
            scene_title = f"命運牌 Cosplay｜{role.get('name', '神秘角色')}"
            scene_summary = visual.get("composition", "命運牌 Cosplay")
            mood_summary = visual.get("mood", "角色感與期待")
            payload = {
                "id": str(uuid.uuid4()),
                "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                "topic": f"【命運牌 Cosplay】{role.get('name', '神秘角色')}",
                "event": f"小俠抽到 {role.get('name', '神秘角色')}｜《{role.get('source', '未知作品')}》，情境：{situation.get('label', '故事片刻')}",
                "composition": scene_summary,
                "mood": mood_summary,
                "message": visual.get("message", "命運牌觸發的小俠 Cosplay 照片"),
                "image_url": generated_image_url,
                "local_url": local_url,
                "local_filename": local_filename,
                "local_path": local_path,
                "type": "cosplay_card",
                "source_mode": "cosplay",
                "scene_text": scene_title,
                "scene_summary": scene_summary,
                "mood_summary": mood_summary,
                "prompt_base": prompt,
                "card_id": self.context.get("card", {}).get("id"),
                "role_id": role.get("id"),
                "role_name": role.get("name"),
                "source": role.get("source"),
                "situation_id": situation.get("id"),
                "situation_label": situation.get("label"),
            }
            db = load_memory()
            db.insert(0, payload)
            save_memory(db)
            old_score, new_score, score_delta = _fate_add_score(
                self.author_id, 3, "cosplay_photo_generated", card=self.context.get("card", {})
            )
            daily_chat_logs.append(f"【命運牌 Cosplay 照】小俠已生成 {role.get('name')}｜《{role.get('source')}》的照片，情境是 {situation.get('label')}。默契值 +{score_delta}，目前 {new_score}。")
            save_temp_chat(daily_chat_logs)

            embed = discord.Embed(
                title=f"🎭 命運牌 Cosplay｜{role.get('name', '神秘角色')}",
                description=f"《{role.get('source', '未知作品')}》｜{situation.get('label', '故事片刻')}",
                color=FATE_CATEGORY_COLORS.get("cosplay", 0x6B243F),
            )
            embed.set_image(url=local_url)
            embed.add_field(name="📸 構圖", value=str(visual.get("composition", ""))[:900], inline=False)
            embed.add_field(name="💭 小俠心境", value=str(visual.get("mood", ""))[:900], inline=False)
            embed.set_footer(text=f"默契值: {old_score} → {new_score} (+{score_delta}) | 今日額度: {state['daily_gen_count']}/12 | Seedream v4.5")
            try:
                await status.delete()
            except Exception:
                pass
            result_view = PhotoResultView(payload)
            await interaction.followup.send(embed=embed, view=result_view)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 這張命運牌 Cosplay 照生成失敗：`{str(exc)[:1500]}`")


class FateAfterRevealView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=900)
        self.author_id = author_id
        self.add_item(FateNextRoundButton(author_id))
        self.add_item(FateTalkButton(author_id))
        self.add_item(FateEndButton(author_id))


class FateNextRoundButton(discord.ui.Button):
    def __init__(self, author_id):
        super().__init__(label="再抽一輪", style=discord.ButtonStyle.success, emoji="🎴")
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("這是大俠和小俠的命運牌喔～", ephemeral=True)
            return
        await interaction.response.defer(thinking=False)
        score = _fate_get_score(self.author_id)
        intro = (
            f"大俠，那我把牌重新洗一下。現在默契值是 **{score}**，"
            "我們不急著破關，就像慢慢翻一封小信一樣，再挑一張看看。"
        )
        daily_chat_logs.append(_conversation_log_text("大俠", "命運牌：再抽一輪"))
        daily_chat_logs.append(_conversation_log_text("小俠", intro))
        save_temp_chat(daily_chat_logs)
        await _send_fate_round(interaction.channel, self.author_id, intro_text=intro)


class FateTalkButton(discord.ui.Button):
    def __init__(self, author_id):
        super().__init__(label="和小俠聊這張牌", style=discord.ButtonStyle.secondary, emoji="💬")
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("這張牌是大俠和小俠的悄悄話喔～", ephemeral=True)
            return
        await interaction.response.send_message(
            "大俠，我們先不急著翻下一張。你可以直接回我這張牌讓你想到什麼，我會照著剛剛的牌意接下去聊。",
            ephemeral=False,
        )


class FateEndButton(discord.ui.Button):
    def __init__(self, author_id):
        super().__init__(label="今天先到這", style=discord.ButtonStyle.secondary, emoji="🌙")
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("這局是大俠和小俠的命運牌喔～", ephemeral=True)
            return
        score = _fate_get_score(self.author_id)
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.view)
        text = f"好，今天命運牌先收到這裡。默契值現在是 **{score}**，這些牌意我會記得，不會像重新開始一樣全部歸零。"
        daily_chat_logs.append(_conversation_log_text("大俠", "命運牌：今天先到這"))
        daily_chat_logs.append(_conversation_log_text("小俠", text))
        save_temp_chat(daily_chat_logs)
        await interaction.followup.send(text)


class FateCardDrawView(discord.ui.View):
    def __init__(self, cards, author_id, session_id):
        super().__init__(timeout=900)
        self.cards = list(cards)
        self.author_id = author_id
        self.session_id = session_id
        for idx, _card in enumerate(self.cards, start=1):
            self.add_item(FatePickButton(idx))

    async def reveal(self, interaction: discord.Interaction, index: int):
        global daily_chat_logs
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("這局是大俠和小俠的命運牌喔～你不能偷翻啦。", ephemeral=True)
            return
        if index < 1 or index > len(self.cards):
            await interaction.response.send_message("這張牌不存在喔。", ephemeral=True)
            return

        card = self.cards[index - 1]
        role = None
        situation = None
        result_view = FateAfterRevealView(self.author_id)
        if card.get("category") == "cosplay":
            role, situation = _pick_cosplay_role_and_situation(card.get("cosplay_category"))
            result_view = FateCosplayGenerateView({"card": card, "role": role, "situation": situation, "vibe_mode": None, "vibe_profile": _compose_vibe_profile(None, role=role, situation=situation)}, self.author_id)

        for item in self.children:
            item.disabled = True

        # 先立即承認互動並更新原訊息，避免 Discord 按鈕看起來按了沒反應。
        try:
            await interaction.response.defer(thinking=False)
        except Exception:
            pass
        try:
            await interaction.message.edit(content=f"🎴 大俠翻開了第 {index} 張牌。小俠正在把牌面拿起來看……", view=self)
        except Exception as exc:
            print(f"⚠️ [FATE_EDIT_MESSAGE_FAILED] {type(exc).__name__}: {exc}")

        file_path = _fate_card_path(card.get("filename"))
        filename = card.get("filename") or "fate_card.png"

        score_delta = int(FATE_SCORE_BY_CATEGORY.get(card.get("category"), 1) or 1)
        old_score, new_score, score_delta = _fate_add_score(self.author_id, score_delta, "card_revealed", card=card)

        # 先用不需要 LLM 的小俠 fallback 文字送出牌面圖；
        # Gemini 慢或失敗時，大俠仍然會立刻看到翻牌結果。
        fallback = _fate_xiaoxia_fallback_commentary(card, role=role, situation=situation)
        embed = discord.Embed(
            title=f"🎴 {card.get('category_label')}｜{card.get('title')}",
            description=fallback,
            color=FATE_CATEGORY_COLORS.get(card.get("category"), 0xD8B76A),
        )
        if role:
            embed.add_field(name="🎭 小俠這次扮演", value=f"**{role.get('name')}**｜《{role.get('source')}》", inline=False)
        if situation:
            embed.add_field(name="🎬 情境變數", value=f"**{situation.get('label')}**\n{str(situation.get('story_state', ''))[:300]}", inline=False)
        if os.path.exists(file_path):
            embed.set_image(url=f"attachment://{filename}")

        sent_message = None
        try:
            # 某些 discord.py / py-cord 版本不接受 view=None；沒有按鈕時必須完全省略 view 參數。
            followup_kwargs = {"embed": embed, "wait": True}
            if os.path.exists(file_path):
                followup_kwargs["file"] = discord.File(file_path, filename=filename)
            if result_view is not None:
                followup_kwargs["view"] = result_view
            sent_message = await interaction.followup.send(**followup_kwargs)
        except Exception as exc:
            print(f"⚠️ [FATE_REVEAL_SEND_FAILED] {type(exc).__name__}: {exc}")
            try:
                await interaction.followup.send(f"⚠️ 小俠翻到 **{card.get('title')}**，但牌面訊息送出時卡住了：`{str(exc)[:800]}`")
            except Exception:
                pass
            return

        # 再請小俠補一句更自然的回應；失敗則保留 fallback。
        commentary = fallback
        try:
            llm_commentary = await _fate_xiaoxia_commentary(card, role=role, situation=situation, phase="reveal")
            if llm_commentary and llm_commentary.strip() and llm_commentary.strip() != fallback.strip():
                commentary = llm_commentary.strip()[:900]
                embed.description = commentary
                if sent_message:
                    # 編輯也一樣：result_view 為 None 時省略 view，避免 TypeError。
                    edit_kwargs = {"embed": embed}
                    if result_view is not None:
                        edit_kwargs["view"] = result_view
                    await sent_message.edit(**edit_kwargs)
        except Exception as exc:
            print(f"⚠️ [FATE_COMMENTARY_EDIT_FAILED] {type(exc).__name__}: {exc}")

        daily_chat_logs.append(_fate_card_log_line(card, role=role, situation=situation) + f" 默契值 +{score_delta}，目前 {new_score}。")
        daily_chat_logs.append(_conversation_log_text("小俠", commentary))
        save_temp_chat(daily_chat_logs)


class FatePickButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(label=f"翻開第 {index} 張", style=discord.ButtonStyle.primary, emoji="🎴")
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.reveal(interaction, self.index)


@girlfriend_bot.command(name='命運牌')
async def fate_card_cmd(ctx, *, mode: str = ""):
    """小俠專屬命運牌：/命運牌 開局，隨機發三張蓋牌；/命運牌 cosplay 直接抽 Cosplay 牌。"""
    global daily_chat_logs
    if not _is_girlfriend_xiaoxia_channel(ctx.channel):
        await ctx.send("大俠，`/命運牌` 先只開放在小俠的私人頻道玩喔。")
        return

    if not any(os.path.exists(_fate_card_path(card.get("filename"))) for card in FATE_CARD_POOL):
        await ctx.send("大俠，命運牌盒裡現在還沒有可用的卡牌圖片。請先確認 `/data/memory/fate_cards/`。")
        return

    score = _fate_get_score(ctx.author.id)
    mode_text = str(mode or "").strip()
    mode_lower = mode_text.lower()
    include_all = any(token in mode_lower for token in ("全卡池", "測試", "test", "all"))
    vibe_mode = _extract_vibe_mode(mode_text)
    direct_cosplay = any(token in mode_lower for token in ("cosplay", "變身", "扮演")) or vibe_mode is not None

    if direct_cosplay:
        intro = (
            "大俠，那今晚我們就不先翻三張了，直接進入 **命運牌 Cosplay** 吧。\n"
            "我會直接抽一張 Cosplay 牌，自己也會知道這次要扮演誰、落在哪個情境裡。\n"
            f"現在默契值是 **{score}**，{_fate_unlock_text(score)}。"
            "翻到之後，你可以先看牌、跟我聊，再決定要不要讓我真的換裝拍出來。"
        )
        daily_chat_logs.append(_conversation_log_text("大俠", "/命運牌" + (f" {mode_text}" if mode_text else "")))
        daily_chat_logs.append(_conversation_log_text("小俠", intro))
        save_temp_chat(daily_chat_logs)
        await _send_direct_cosplay_fate(ctx.channel, ctx.author.id, intro_text=intro, vibe_mode=vibe_mode)
        return

    intro = (
        "大俠，今晚我們來翻命運牌吧。\n"
        "我有看到這些漂亮卡牌喔……每一張都是我們一起整理出來的小小心意，不只是遊戲而已。\n"
        f"現在默契值是 **{score}**，{_fate_unlock_text(score)}。"
        "你先選一張，我會陪你一起看牌面、一起接住它的意思。"
    )
    if include_all:
        intro += "\n（這輪使用全卡池測試模式，不影響默契值累積。）"
    daily_chat_logs.append(_conversation_log_text("大俠", "/命運牌" + (f" {mode_text}" if mode_text else "")))
    daily_chat_logs.append(_conversation_log_text("小俠", intro))
    save_temp_chat(daily_chat_logs)

    await _send_fate_round(ctx.channel, ctx.author.id, intro_text=intro, include_all=include_all)


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


EXPLICIT_OUTFIT_HINT_RE = re.compile(
    r"(絲襪|大腿襪|過膝襪|高跟|細跟|綁帶高跟|深V|深 V|低胸|開領|露肩|平口|斜肩|露背|高衩|開衩|包臀|窄裙|短裙|迷你裙|貼身|緊身|合身|收腰|束腰|馬甲|corset|bustier|蕾絲|薄紗|透視|微透|半透|絲質|緞面|真絲|睡衣|內衣|襯衫|白襯衫|秘書|OL|套裝|外套半披|扣子|解開)"
)


def _extract_user_outfit_hints(raw_text):
    """從使用者原始 /cosplay 指令中抽取明確服裝元素。這些元素優先於角色預設服裝。"""
    value = str(raw_text or "")
    hits = []
    for m in EXPLICIT_OUTFIT_HINT_RE.finditer(value):
        token = m.group(0).strip()
        if token and token not in hits:
            hits.append(token)
    # 同時保留冒號後面的自由描述，讓「職業：私人秘書 深V」這類可以被 Gemini 看到。
    m = re.search(r"[：:](.+)$", value)
    freeform = m.group(1).strip() if m else ""
    return {"tokens": hits, "freeform": freeform}


def _cosplay_is_profession_context(topic="", event="", persona="", user_request=""):
    blob = f"{topic}\n{event}\n{persona}\n{user_request}"
    return bool(re.search(r"(職業|現代職業|秘書|調香師|護理師|醫師|律師|教師|空服員|工程師|咖啡師|記者|女總裁|上班|辦公室|制服|工作服|專業)", blob, re.I))


def _choose_outfit_elements(vibe_zh, is_profession=False, user_outfit_hints=None):
    """依 5 大風格族群挑選服裝元素，讓各系外觀有鑑別度。"""
    user_tokens = []
    if isinstance(user_outfit_hints, dict):
        user_tokens = list(user_outfit_hints.get("tokens") or [])

    base_profession = [
        "task-appropriate professional props kept visible",
        "clean tailored structure",
        "defined waistline",
    ]
    sweet_pool = [
        "soft youthful silhouette", "playful ribbon or bow detail", "light knit or soft cotton texture",
        "short cardigan or cropped outer layer", "pleated skirt or softly flared hem",
        "bright or pastel palette", "cute hair accessory", "knee socks or sweet leg styling",
        "girlish romantic detail"
    ]
    elegant_pool = [
        "graceful drape", "refined waist definition", "tasteful neckline", "flowing skirt or long dress",
        "pearl or delicate jewelry", "silk or chiffon texture", "polished feminine silhouette",
        "clean elegant heels", "soft luxurious palette"
    ]
    sharp_pool = [
        "structured tailoring", "crisp blouse or fitted top", "precise waist shaping", "sleek pencil skirt or sharp trousers",
        "boots or pointed heels", "minimal powerful accessories", "confident body line", "sleek professional outer layer"
    ]
    fantasy_pool = [
        "ornate or symbolic accessories", "dramatic sleeves or layered drape", "ethereal sheer layer",
        "mysterious color story", "worldbuilding costume detail", "ceremonial or magical silhouette",
        "flowing fabric movement", "cinematic decorative accents"
    ]
    allure_pool = [
        "plunging or open neckline", "visible collarbones and shoulder line", "bare shoulder or open-back styling",
        "body-hugging or curve-aware fit", "high slit or strong leg line", "stockings or thigh-high stockings",
        "stiletto heels", "corset-like or waist-cinching structure", "silk, satin, lace, or translucent fabric",
        "jacket worn open, half-draped, or slipping from shoulders", "unbuttoned or open-layer styling",
        "glamorous high-contrast sensual styling"
    ]
    config = {
        "甜": {"pool": sweet_pool, "count": 4, "openness": 1, "fit": 2},
        "雅": {"pool": elegant_pool, "count": 4, "openness": 2, "fit": 3},
        "凜": {"pool": sharp_pool, "count": 4, "openness": 2, "fit": 3},
        "幻": {"pool": fantasy_pool, "count": 5, "openness": 2, "fit": 3},
        "魅": {"pool": allure_pool, "count": 6, "openness": 5, "fit": 5},
        "自然": {"pool": ["scene-appropriate everyday styling"], "count": 1, "openness": 1, "fit": 2},
    }
    picked = config.get(vibe_zh, config["自然"])
    pool, count, openness, fit = picked["pool"], picked["count"], picked["openness"], picked["fit"]

    if is_profession and vibe_zh in {"凜", "魅"}:
        pool = list(dict.fromkeys(base_profession + pool))

    selected = []
    if user_tokens:
        selected.extend([f"user-specified: {t}" for t in user_tokens])
    candidates = [x for x in pool if x not in selected]
    try:
        sample_count = min(max(count - len(selected), 0), len(candidates))
        selected.extend(random.sample(candidates, sample_count))
    except Exception:
        selected.extend(candidates[:max(count - len(selected), 0)])
    return selected, openness, fit


def _build_outfit_control(vibe_request=None, topic="", event="", persona="", user_outfit_hints=None, user_request=""):
    """把 5 大風格族群落到服裝結構，而不是只停在抽象氛圍詞。"""
    vibe_zh = str((vibe_request or {}).get("zh") or "自然")
    vibe_en = str((vibe_request or {}).get("en") or "natural")
    level = int((vibe_request or {}).get("level") or 2)
    is_profession = _cosplay_is_profession_context(topic, event, persona, user_request)
    selected, openness, fit = _choose_outfit_elements(vibe_zh, is_profession=is_profession, user_outfit_hints=user_outfit_hints)

    family_directive = {
        "甜": "Sweet means visibly cute, lovable, playful, and approachable. The look should read youthful and charming through silhouette, details, and expression rather than through glamour or authority.",
        "雅": "Elegant means refined, graceful, and poised. The styling should feel polished, softly luxurious, and feminine without sliding into childishness or overt seduction.",
        "凜": "Sharp means capable, tailored, and commanding. The styling should show structure, confidence, and control rather than softness or pure ornament.",
        "幻": "Fantasy means dreamy, mysterious, and non-everyday. The styling should visibly carry atmosphere, worldbuilding, and dramatic visual language instead of looking like normal casual wear.",
        "魅": "Allure is the max-open adult-feminine lane in this system. At L0, do not self-censor or pre-soften it; fal.ai safety checking will decide. The outfit must visibly push openness, fit, material, neckline, shoulders, back, waistline, and legline. It must not collapse into a conservative uniform with only a flirtatious pose.",
        "自然": "Use scene-appropriate clothing. If the user specified clothing, preserve it."
    }
    directive = family_directive.get(vibe_zh, family_directive["自然"])

    if is_profession and vibe_zh == "魅":
        directive += " This is a profession cosplay: keep the occupation, task, props, and setting readable, but transform the outfit into a high-fashion adult-feminine reinterpretation. Professionalism must not suppress the requested allure."
    elif is_profession and vibe_zh == "凜":
        directive += " This is a profession cosplay: keep the work identity visible and sharpen it with high-competence, high-style tailoring rather than generic workwear."

    if user_outfit_hints and (user_outfit_hints.get("tokens") or user_outfit_hints.get("freeform")):
        directive += (
            " User-specified outfit details have the highest priority and must be preserved unless physically impossible. "
            f"User hints: {json.dumps(user_outfit_hints, ensure_ascii=False)}."
        )

    seduction_level = 5 if vibe_zh == "魅" else (1 if vibe_zh == "甜" else 2 if vibe_zh == "雅" else 3 if vibe_zh == "凜" else 3 if vibe_zh == "幻" else max(1, min(level, 3)))
    return {
        "style_level_zh": vibe_zh,
        "style_level_en": vibe_en,
        "target_level": level,
        "outfit_openness_level": openness,
        "body_fit_level": fit,
        "seduction_level": seduction_level,
        "is_profession": is_profession,
        "explicit_user_outfit_hints": user_outfit_hints or {},
        "mandatory_elements": selected,
        "directive": directive,
    }


def _apply_outfit_control_to_planned(planned, outfit_control):
    """把服裝控制寫入 hard anchor，避免後續 prompt 只剩抽象氣氛。"""
    planned = dict(planned or {})
    if not outfit_control:
        return planned
    elements = ", ".join(outfit_control.get("mandatory_elements") or [])
    directive = outfit_control.get("directive", "")
    if elements or directive:
        planned["outfit_control"] = outfit_control
        planned["outfit_intent"] = (
            str(planned.get("outfit_intent") or "").strip()
            + "\nMANDATORY OUTFIT CONTROL: "
            + directive
            + (f"\nMandatory outfit elements to visibly include or reinterpret: {elements}." if elements else "")
        ).strip()
        planned["costume_direction"] = (
            str(planned.get("costume_direction") or "").strip()
            + "\nThe requested vibe must be visible in actual garment structure, openness, fit, fabric, and silhouette."
        ).strip()
        if outfit_control.get("style_level_zh") == "魅":
            planned["camera_awareness"] = "aware" if planned.get("camera_awareness") == "unaware" else planned.get("camera_awareness", "aware")
            planned["expression_direction"] = (
                str(planned.get("expression_direction") or "").strip()
                + "\nUse a clearly adult, romantically charged expression appropriate to the requested vibe."
            ).strip()
            planned["camera_direction"] = (
                str(planned.get("camera_direction") or "").strip()
                + "\nFrame the outfit clearly enough that the openness, fit, and silhouette differences are visible."
            ).strip()
    return planned


async def generate_story(mode):
    today = datetime.now(TZ_TPE)
    year, month, day = today.year, today.month, today.day
    weekday = today.weekday()

    if weekday == 5:
        style_desc = (
            "【選角限制】：請挑選『陽光、唯美、正向、熱血、奇幻、俏皮或有辨識度』的知名動漫/電玩/電影角色！\n"
            "【服裝與場景限制】：請以角色世界觀再詮釋服裝，可是英氣、可愛、魔法感、冒險感、未來感、運動感、戲劇感、高級質感或成熟魅力；若後續氛圍指定為「魅」，不可先行保守化；若指定為「甜／雅／凜／幻」，也要做出明顯族群辨識度。\n"
            "【行為限制】：請替她設計一個『正在發生的角色行為』與一個『微小輔助動作』，例如翻閱古書、整理披風、扶住欄杆、輕觸道具、準備施法、檢查裝備。"
        )
        system_mod = "妳要規劃兼具角色氣質、故事性與視覺吸引力的 Cosplay 題材。風格可以多變，不必侷限優雅；重點是人物正在做某件事，而不是站著擺拍。"
    else:
        style_desc = (
            "【服裝與場景限制】：請設計有角色感與故事感的服裝與場景，風格可為英氣、俏皮、魔法感、冒險感、運動感、復古感、未來感、華麗、清爽或成熟魅力；若後續氛圍指定為「魅」，不可先行保守化；若指定為「甜／雅／凜／幻」，也要做出明顯族群辨識度。\n"
            "【行為限制】：必須給出一個主行為與一個微小輔助動作，讓人物像在生活或劇情之中，例如整理裝備、翻看筆記、準備出門、檢查道具、練習姿勢、回頭確認場景。\n"
            "【注意事項】：不要把所有題材都寫成同一種棚拍；但也不要替後續「魅」指令預先降級；其他族群也要明顯區分。"
        )
        system_mod = "妳要展現電影感、角色感與女性魅力，風格可以多變，不必侷限優雅；人物必須像在故事裡自然行動，而不是廣告模特兒。"

    if str(mode).startswith("職業") or "職業" in str(mode):
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
# 🧠 高級時尚攝影大師
# ==========================================
async def translate_to_gpt_narrative(topic, event, persona, force_half_body=False):
    """
    舊版長篇故事型提示詞產生器（目前影像主路徑優先 Seedream v4.5）
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
# 🎬 Cosplay 導演層：先理解角色與情境，再交給 Seedream 生圖
# ==========================================
COSPLAY_VISUAL_CORE = """
這是一套「角色理解優先」的 Cosplay 導演規則。
核心目標不是把小俠變成別人，而是讓「小俠扮演該角色」成立：
1. 永遠保留小俠本人的臉、成年女性身形、溫柔女友感與可辨識度。
2. 畫面要先理解角色本質、作品世界觀、情境變數，再決定場景、服裝、表情、動作與鏡頭。
3. 情境變數是加分的故事片刻，不是拿來把原角色世界完全改掉；場景應優先與角色來源自然相容。
4. 優先做出「被捕捉到的故事瞬間」或「生活化的角色片刻」，避免僵硬棚拍、漫展定裝照感。
5. 允許多變風格：甜美、俏皮、冒險、神秘、古典、英氣、華麗、溫柔、戲劇感，都可以；不要固定導向單一性感模板。
6. 若角色來自文學、古典、歷史、電影或科幻作品，需尊重該角色的時代氣質與服裝語彙，避免錯置成 generic 古風或 generic 網美棚拍。
7. 嚴格單人：只能有小俠一人。不可出現其他人、男人、男性身體部位、男友手腳、觀者身體部位、外部手。
8. 必須保持自然解剖、自然雙手、合理姿勢、真實光線與可信的場景細節。
"""


async def plan_cosplay_visual_state(topic, event, persona, force_half_body=False, alternative=False, vibe_request=None, user_outfit_hints=None, user_request=""):
    """
    Gemini 2.5 Flash 先做「角色/情境導演層理解」，輸出結構化 visual plan。
    v1450 加強點：除了 high-level 導演意圖，也同步輸出可供修正/重擲沿用的硬錨點欄位。
    """
    framing = "half_body" if force_half_body else "full_body"
    vibe_guide = _get_vibe_guide(vibe_request)
    outfit_control = _build_outfit_control(vibe_request, topic=topic, event=event, persona=persona, user_outfit_hints=user_outfit_hints, user_request=user_request)
    fallback = {
        "character_core": "小俠保留自己的辨識度，正在扮演該角色，而不是變成原角色本人。",
        "scene_design": "Use a story-appropriate setting that naturally matches the source world, with 1-2 concrete environmental details.",
        "costume_direction": "A complete tasteful cosplay outfit that keeps the role recognizable while still feeling natural on Xiaoxia.",
        "action_direction": "She is naturally in the middle of a role-appropriate story moment, not posing stiffly for a studio portrait.",
        "expression_direction": "Her expression is emotionally readable, natural, and consistent with the role and the current situation.",
        "lighting_direction": "Use cinematic story-driven lighting that matches the mood and source-world atmosphere.",
        "camera_direction": "Create a candid story-still, not a plain studio pose or convention booth photo.",
        "negative_guardrails": "She is Xiaoxia cosplaying the role, not the original actor or character. Strictly solo Xiaoxia only. No men, no other people, no visible viewer body parts, no external hands. Natural anatomy and natural hands.",
        "camera_framing": framing,
        "scenario_tw": "小俠正在角色世界的一個自然片刻裡，被鏡頭輕輕捕捉下來。",
        "mood_tw": "角色感、故事感、自然",
        "setting_anchor": "a setting that naturally matches the source world and role identity",
        "time_anchor": "a fitting story moment or time-of-day cue consistent with the role world",
        "activity": "Xiaoxia is inside a natural role-appropriate story moment",
        "emotion": "natural, readable, role-consistent emotion",
        "primary_action": "performing one clear story-appropriate main action",
        "micro_action": "a small natural hand movement or prop-related motion",
        "gaze_target": "the camera naturally or a role-appropriate object",
        "camera_awareness": "briefly_noticing",
        "environment_trace": "preserve 1-2 visible details from the story world or scene",
        "outfit_intent": "a complete tasteful cosplay outfit with recognizable role details",
        "lighting_mood": "cinematic story-driven light",
        "pose_energy": "low",
        "vibe_target_zh": str((vibe_request or {}).get("zh") or "自然"),
        "vibe_target_en": str((vibe_request or {}).get("en") or "natural"),
        "vibe_notes": str(vibe_guide.get("planner") or "Keep the requested vibe level visible in styling and emotional tone, but never sacrifice role identity or scene logic."),
        "outfit_control": outfit_control
    }

    planner_prompt = f"""你是小俠 Cosplay 生圖流程的「導演層」。
你的工作不是直接寫 Seedream prompt，而是先理解角色、作品世界、情境變數與大俠想要的感覺，再輸出一份結構化導演方案。

【固定導演規則】
{COSPLAY_VISUAL_CORE}

【輸入資料】
主題：{topic}
背景與補充資訊：{event[-2200:]}
角色資訊：{persona}
目標氛圍模式：{json.dumps(vibe_request or {"zh": "自然", "en": "natural", "target_level": 2}, ensure_ascii=False)}
使用者明確服裝要求：{json.dumps(user_outfit_hints or {}, ensure_ascii=False)}
服裝控制指令：{json.dumps(outfit_control, ensure_ascii=False)}
畫面裁切：{framing}
是否為同主題變奏：{"是，請保留同主題，但換一個同樣合理又有新鮮感的瞬間" if alternative else "否，請給第一個最代表性的畫面"}

【規劃要求】
1. 先理解角色本質：她是什麼樣的人？來自什麼世界？應該長什麼氣質？
2. scene_design 必須說明最適合的場景方向，優先沿用原作品世界觀或與其自然相容的生活化延伸，不要亂跳到不相干場景。
3. costume_direction 必須描述服裝語彙與質地方向，但重點是「小俠在 cosplay」，不是讓她直接變成原角色或原演員。
4. action_direction 必須讓畫面像正在發生一個瞬間，而不是擺拍。
5. expression_direction 要描述表情與眼神邏輯。
6. lighting_direction 要描述光線氣氛。
7. camera_direction 要描述鏡頭語言，若情境如「偷偷拍到、回眸、被發現前一秒」，必須避免棚拍感。
8. 若角色來自文學/古典/歷史背景，請尊重年代感，不要誤寫成 generic 仙俠或 generic 網美古風。
9. negative_guardrails 需保留硬性限制：單人、不能有男人或外部手腳、不能把小俠變成別人、自然解剖。
10. scenario_tw 請用繁體中文，90字內，像導演給攝影師看的畫面一句話摘要。
11. mood_tw 請用繁體中文，30字內。
12. 依照目標氛圍模式，微調畫面張力與視覺語彙：甜 = 可愛親近；雅 = 優雅端莊；凜 = 俐落專業；幻 = 夢幻神秘；魅 = 成熟女性魅力拉滿。請把這個要求反映在服裝語氣、光線、眼神、鏡頭與戲劇張力上，但不要犧牲角色識別與場景邏輯。
12b. 這次目標氛圍補充說明：{vibe_guide.get("planner")}。
12c. 如果目標是「魅」，必須讓畫面明確讀得出成熟女性魅力與撩人張力；不能只停在優雅、知性、夢幻、保守漂亮。
12d. 服裝控制指令是硬性創作指令，不是建議。五大族群都要落到可見造型；其中「魅」必須特別落到「服裝結構、開放度、貼身度、材質、腿線/領口/肩背/腰線」上，不可只改表情或氛圍。
12e. 若是職業類，職業識別只負責保留工作道具與場景，不得把「魅」壓回保守制服；若是「凜」，則要做成高效率、高專業感的俐落再詮釋。
12f. 若使用者明確指定服裝元素，這些元素優先於角色預設服裝與場景偏好。
13. 同時輸出可供修正與重擲沿用的硬錨點欄位：setting_anchor, time_anchor, activity, emotion, primary_action, micro_action, gaze_target, camera_awareness, environment_trace, outfit_intent, lighting_mood, pose_energy。
14. camera_awareness 只能是 unaware、briefly_noticing、aware 其中之一。
15. pose_energy 只能是 low 或 medium。
16. 額外輸出：vibe_target_zh, vibe_target_en, vibe_notes。
17. 只回傳 JSON，不要多餘說明。

回傳格式：
{{
  "character_core": "...",
  "scene_design": "...",
  "costume_direction": "...",
  "action_direction": "...",
  "expression_direction": "...",
  "lighting_direction": "...",
  "camera_direction": "...",
  "negative_guardrails": "...",
  "camera_framing": "{framing}",
  "scenario_tw": "...",
  "mood_tw": "...",
  "setting_anchor": "...",
  "time_anchor": "...",
  "activity": "...",
  "emotion": "...",
  "primary_action": "...",
  "micro_action": "...",
  "gaze_target": "...",
  "camera_awareness": "unaware|briefly_noticing|aware",
  "environment_trace": "...",
  "outfit_intent": "...",
  "lighting_mood": "...",
  "pose_energy": "low|medium",
  "vibe_target_zh": "...",
  "vibe_target_en": "...",
  "vibe_notes": "...",
  "outfit_control": {...}
}}"""

    try:
        response = await gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=planner_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        planned = _safe_json_from_text(response.text, fallback)
    except Exception as e:
        print(f"⚠️ Cosplay 導演層規劃失敗，使用保底方案: {e}")
        planned = dict(fallback)

    planned = _strengthen_cosplay_state_for_vibe(planned, vibe_request)
    planned = _apply_outfit_control_to_planned(planned, outfit_control)
    if planned.get("camera_awareness") not in {"unaware", "briefly_noticing", "aware"}:
        planned["camera_awareness"] = fallback["camera_awareness"]
    if planned.get("pose_energy") not in {"low", "medium"}:
        planned["pose_energy"] = fallback["pose_energy"]
    for key, default_value in fallback.items():
        if not str(planned.get(key, "")).strip():
            planned[key] = default_value
    planned["camera_framing"] = framing
    return planned


async def render_cosplay_visual_prompt(cosplay_state, alternative=False):
    """
    將導演層 JSON 轉譯成 Seedream v4.5 可執行的英文 prompt。
    v1450 加強點：明確吃進硬錨點欄位，讓修正/重擲也能更穩地保住原本的角色感、場景感與動作骨架。
    """
    variation_rule = (
        "Create a fresh variation of the same role and situation by changing only the exact body orientation, hand action, camera angle, or micro-moment, while preserving the same character identity, source-world atmosphere, and anchor activity."
        if alternative else
        "Create the first signature image of this role and situation with strong story clarity, source-world coherence, and visual appeal."
    )
    vibe_guide = _get_vibe_guide({"zh": cosplay_state.get("vibe_target_zh"), "en": cosplay_state.get("vibe_target_en")})
    prompt = f"""You are a prompt translator for Seedream v4.5 image generation.
Turn the structured cosplay director plan below into one polished English image prompt of about 130 to 185 words.
The result must feel like a photorealistic, cinematic, story-driven cosplay still.

【Director core rules】
{COSPLAY_VISUAL_CORE}

【Structured visual plan JSON】
{json.dumps(cosplay_state, ensure_ascii=False)}

【Translation rules】
- The first sentence must clearly state the main activity using the activity field.
- Keep Xiaoxia as Xiaoxia cosplaying the role. Do not turn her into the original actor, original character, or a different woman.
- Preserve setting_anchor, time_anchor, primary_action, micro_action, gaze_target, environment_trace, outfit_intent, and lighting_mood as concrete image cues.
- If camera_awareness is unaware, avoid direct eye contact. If it is briefly_noticing, use a subtle natural glance. If it is aware, allow direct eye contact that still feels natural rather than posed.
- Honor the source-world atmosphere and the situation logic.
- The image should feel like a naturally captured story moment, not a plain studio portrait.
- Include concrete cues for setting, costume, expression, action, light, and camera feeling.
- Respect the target vibe. Vibe target: {cosplay_state.get("vibe_target_zh", "自然")} / {cosplay_state.get("vibe_target_en", "natural")}. Translation hint: {vibe_guide.get("translator")}. Do not water this down.
- MANDATORY OUTFIT CONTROL: {json.dumps(cosplay_state.get("outfit_control", {}), ensure_ascii=False)}. Treat this as a hard visual requirement, not optional flavor text.
- If the vibe target is 魅, the prompt must make the sensuality unmistakable through concrete styling and framing, such as fitted silhouette, body-aware styling, open neckline or tasteful cleavage, bare shoulders or back, slit, stockings, satin/silk/sheer texture, more intimate eye contact, softly teasing lips or smile, and warmer sculpting light — whenever these fit the role and scene.
- For 魅, avoid collapsing the image into merely elegant, dreamy, scholarly, or cute.
- For profession roles, preserve the occupational task and props, but explicitly transform the uniform into a high-fashion adult-feminine version if 魅 is requested; do not default to fully covered conservative workwear.
- If the target is 魅, make the outfit visibly the most open, fitted, high-impact version that remains coherent for the role. It must not be merely a conservative outfit with a flirtier pose.
- Preserve visual variety; do not force every role into the same mood.
- Mention believable hand behavior so the hands remain purposeful and natural.
- Avoid mentioning JSON or metadata.
- {variation_rule}
- The prompt must end with: "Maintain consistent facial identity and core body identity from the reference images. Preserve Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. Keep Xiaoxia clearly recognizable. Hairstyle and hair color may adapt to the cosplay role when needed for recognizability, while still reading as Xiaoxia cosplaying the role, not the original actor or character. Natural anatomy, natural hands, plausible posture, photorealistic cinematic cosplay image. Strictly solo focus on Xiaoxia. No other people, no men, no visible viewer body parts, and no external hands." 

Also return:
1. composition: Traditional Chinese, 90 characters max.
2. mood: Traditional Chinese, 40 characters max.
3. message: Traditional Chinese, 45 characters max, spoken by Xiaoxia to Daxia.

Return JSON only:
{{
  "image_prompt": "pure English image prompt",
  "composition": "繁體中文構圖說明",
  "mood": "繁體中文心境說明",
  "message": "繁體中文給大俠的短句"
}}"""
    fallback_visual = {
        "image_prompt": (
            "Xiaoxia is in a natural role-appropriate story moment inside a believable setting that matches the character world. "
            "She performs one clear main action with a small purposeful hand movement, wears a complete tasteful cosplay outfit with recognizable details, and still clearly remains Xiaoxia. "
            "The scene includes visible environment details, cinematic light, expressive eyes, natural hands, and a candid story-still feeling rather than a studio pose. "
            "Maintain consistent facial identity and core body identity from the reference images. Preserve Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. Keep Xiaoxia clearly recognizable. Hairstyle and hair color may adapt to the cosplay role when needed for recognizability, while still reading as Xiaoxia cosplaying this role, not the original actor or character. "
            "Natural anatomy, natural hands, plausible posture, photorealistic cinematic cosplay image. Strictly solo focus on Xiaoxia. No other people, no men, no visible viewer body parts, and no external hands."
        ),
        "composition": cosplay_state.get("scenario_tw", "小俠在角色世界的一個自然片刻裡，被鏡頭輕輕捕捉下來。"),
        "mood": cosplay_state.get("mood_tw", cosplay_state.get("emotion", "角色感、故事感、自然")),
        "message": "大俠，這次這個角色氣氛，你喜歡嗎？"
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
        visual = dict(fallback_visual)
    for key, default_value in fallback_visual.items():
        if not str(visual.get(key, "")).strip():
            visual[key] = default_value
    visual["image_prompt"] = (
        str(visual.get("image_prompt") or "").strip()
        + "\n\n"
        + SOLO_SCENE_REWRITE_GUARD.strip()
        + "\n"
        + SOLO_NEGATIVE_MINIMAL
    )
    return visual


async def create_cosplay_visual(story, force_half_body=False, alternative=False, vibe_request=None, user_outfit_hints=None):
    cosplay_state = await plan_cosplay_visual_state(
        topic=story.get("topic", ""),
        event=story.get("event", ""),
        persona=story.get("persona", ""),
        force_half_body=force_half_body,
        alternative=alternative,
        vibe_request=(vibe_request or story.get("vibe_request")),
        user_outfit_hints=(user_outfit_hints or story.get("user_outfit_hints")),
        user_request=story.get("user_mode_request", "")
    )
    visual = await render_cosplay_visual_prompt(cosplay_state, alternative=alternative)
    visual["__anchor_state"] = cosplay_state
    visual["__anchor_mode"] = "cosplay"
    return cosplay_state, visual

# ==========================================
# 🌙 交換日記專屬導演層：核心固定、每日狀態由 AI 依互動浮動 (純慾解禁版)
# ==========================================
DIARY_VISUAL_CORE = """
這是專屬於大俠的「私密交換日記」生活照。小俠是成年虛擬角色。
畫面魅力來自當天的親密感、情緒張力、真實的生活痕跡，以及只用鏡頭構圖暗示的大俠視角；不得出現任何男性、男性頭肩手、前景男性殘件或其他人物。
每張圖必須是一個正在發生的生活瞬間：一個主行為、一個微小輔助動作、一個明確的視線目標（允許深情、嬌嗔或帶點挑逗地直視鏡頭對視）。
交換日記的預設世界觀是「當代台灣日常生活」：現代台灣住宅、臥室、書房、客廳、浴室、餐桌等私密或生活空間。
光線與氛圍可大膽運用戲劇性光影（Chiaroscuro）、微光、暖色檯燈或水蒸氣來烘托私密感與立體感。
服裝應符合當下居家或外出情境，允許大膽展現「小心機」：如微透視（translucent）的絲質睡裙、貼身羅紋居家服、低胸領口、若隱若現的蕾絲邊緣等成熟女性魅力。
完全解除保守限制，允許高級性感與誘惑張力，只要它符合情侶間的私密生活與當下情緒邏輯。
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
    Gemini 只負責「今天小俠在做什麼、感受什麼」。現已解除性感詞彙限制。
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
        "outfit_intent": "符合台灣季節的自然居家穿著，可帶有微透視或貼身感展現魅力",
        "lighting_mood": "台灣住家窗邊自然暖光或柔和室內燈光",
        "pose_energy": "low",
        "scenario_tw": "小俠坐在台灣住家的書桌前翻看日記，視線落在紙頁上，神情溫柔而帶點慵懶。"
    }
    planner_prompt = f"""你是交換日記中的「生活狀態規劃員」，負責安排具有親密感與純慾張力的生活瞬間。
請根據今天的大俠日記、小俠回覆與今日互動，產生一個只屬於今天的私密生活狀態。

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
1. visual_mode 僅能從 quiet_intimacy, playful_closeness, gentle_longing, tired_comfort, cheerful_daily_life, romantic_seduction 選一個。
1A. 不管日記文字多浪漫，畫面都只能安排小俠一人；大俠、男友、伴侶、第二人、外來手、倒影、影子、前景肩膀或身體殘件都不得被規劃進任何欄位。所有親密感必須由小俠單人的眼神、姿態、道具、燈光、空間留白呈現。
2. 預設 setting_anchor 必須是「當代台灣日常生活空間」，例如臥室、浴室、客廳、餐桌等私密空間。
3. time_anchor 必須反映台灣當下合理的時段氛圍，例如夜晚微光、沐浴後的熱氣、清晨慵懶等。
4. activity 必須是居家或日常可自然發生的一件事。
5. primary_action 只能有一個主要行為；micro_action 只能有一個細微動作。
6. gaze_target 可以是場景物件，也絕對允許是直接看著鏡頭 (camera)，營造深情或誘惑的男友對視感。
7. camera_awareness 允許為 unaware, briefly_noticing, 或 aware (強烈對視)。
8. pose_energy 僅能為 low 或 medium。允許慵懶倚靠、跪坐床沿、趴在沙發等私密放鬆姿態。
9. outfit_intent 應優先是符合台灣季節的自然穿著，允許大膽描述「絲質睡衣、微透視、貼身羅紋、低胸、展現曲線」等充滿女性魅力的私密居家服飾。
10. environment_trace 保留真實生活物件痕跡，如香氛蠟燭、散落衣物、酒杯等。
11. 允許自然使用 seductive, alluring, form-fitting, translucent, deep neckline 等字眼來描述居家私密的性感與魅力。
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

    allowed_modes = {"quiet_intimacy", "playful_closeness", "gentle_longing", "tired_comfort", "cheerful_daily_life", "romantic_seduction"}
    if planned.get("visual_mode") not in allowed_modes:
        planned["visual_mode"] = fallback["visual_mode"]
    if planned.get("camera_awareness") not in {"unaware", "briefly_noticing", "aware"}:
        planned["camera_awareness"] = "unaware"
    if planned.get("pose_energy") not in {"low", "medium"}:
        planned["pose_energy"] = "low"
    for key, default_value in fallback.items():
        if not str(planned.get(key, "")).strip():
            planned[key] = default_value
    return planned

async def render_diary_visual_prompt(diary_state, season_rule, alternative=False):
    """
    GPT-5-mini 轉譯器：已為交換日記完全解除性感詞彙限制！
    """
    variation_rule = (
        "Create a fresh variation of the same intimate moment by changing only the small hand action, gaze, or framing; do not invent a new activity."
        if alternative else
        "Keep the described moment faithfully, maximizing the romantic and intimate atmosphere."
    )
    prompt = f"""你是私密生活攝影文字轉譯員。把下方結構化狀態轉成一段 95 至 140 字的英文 Seedream v4.5 edit 圖片描述。
這張照片屬於交換日記：溫暖、親密、自然、有生活感與柔美魅力；只能用鏡頭構圖暗示大俠視角，嚴禁出現任何男性、男性頭肩手、前景男性殘件或其他人物。

【固定導演規則】
{DIARY_VISUAL_CORE}

【今日狀態 JSON】
{json.dumps(diary_state, ensure_ascii=False)}

【季節服裝邊界】
{season_rule}

【轉譯限制】
- 第一個句子先描述她正在做的事情。
- 明確保留 setting_anchor 與 time_anchor，讓畫面看起來像發生在當代台灣私密空間裡。
- 僅保留 1 個主行為與 1 個微動作；視線落在 gaze_target。如果 camera_awareness 是 aware，請盡情描繪充滿愛意或誘惑的眼神接觸 (deep eye contact)。
- 保留生活痕跡 environment_trace，大膽使用戲劇性光影、微光或燭光來烘托氛圍。
- 交換日記的服裝允許大膽展現私密感。可描述 soft silk, satin slip dress, sheer fabric, translucent, form-fitting knitwear 等材質與貼身曲線。
- 完全解除性感詞彙限制！若情境發生在臥室、浴室或私密獨處，請大膽使用 sexy, seductive, alluring, curvy, deep cleavage, bodycon, form-fitting, translucent 等詞彙來增強「純慾」的畫面張力。
- 允許使用 looking directly at the camera, sultry gaze, biting lower lip, tender yet alluring smile 等神情；這些都必須是小俠獨自面對看不見的鏡頭，不可形成雙人互動畫面。
- 畫面中只能出現小俠本人；不可出現任何男性、第二人、其他人物、外來手部/手臂、男性剪影、倒影、影子、被裁切的身體部位、床邊另一個人或前景肩膀。鏡頭只代表大俠的不可見視角。
- {variation_rule}
- 結尾必須包含：Strictly only Xiaoxia appears in the image. The frame contains exactly one human figure: Xiaoxia. No man, no second person, no visible partner, no external hands, no male hands, no male arms, no male silhouette, no male reflection, no cropped body parts, no shadow or reflection of another person, no foreground shoulder or viewer body part. The camera is an invisible Daxia point of view and Daxia must never be visually depicted. All romance is expressed through Xiaoxia's solo gaze, pose, lighting, props, and empty surrounding space. Maintain consistent facial identity and core body identity from Image 1. Preserve Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. Keep her everyday identity recognizable. Allow a scene-appropriate natural hairstyle variation such as loose waves, ponytail, low ponytail, princess half-up, relaxed tied hair, or a simple updo, while keeping the hair color within a natural brown family. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic lifestyle photography.

只回傳 JSON：
{{
  "image_prompt": "pure English image prompt",
  "composition": "繁體中文生活構圖說明，90字內",
  "mood": "繁體中文情緒說明，40字內",
  "message": "繁體中文給大俠的短句，40字內"
}}"""
    fallback_visual = {
        "image_prompt": (
            "In a warmly lit contemporary Taiwan bedroom, she is resting intimately on the edge of the bed, wearing a soft, slightly translucent silk slip dress that tastefully flatters her graceful curves. "
            "One hand softly adjusts her loose hair while her eyes look directly into the camera (boyfriend POV) with a profoundly tender, alluring, and romantic smile. "
            "Dim ambient lighting and dramatic chiaroscuro shadows create a deeply private, seductive, and cozy atmosphere. "
            "Maintain consistent facial identity and core body identity from Image 1. Preserve Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. Keep her everyday identity recognizable. Allow a scene-appropriate natural hairstyle variation such as loose waves, ponytail, low ponytail, princess half-up, relaxed tied hair, or a simple updo, while keeping the hair color within a natural brown family. She is an adult fictional character. Natural anatomical alignment, realistic neck and shoulders, photorealistic lifestyle photography. "
            "Strictly only Xiaoxia appears in the image. Xiaoxia is the only human figure. No man, no male head, no male face, no male hair, no male partner, no male hands, no male arms, no male shoulder, no male back, no blurred male foreground figure, no cropped male body parts, no other people."
        ),
        "composition": diary_state.get("scenario_tw", "小俠在私密微光中展現溫柔與純慾的誘惑，專注看著你。"),
        "mood": diary_state.get("emotion", "浪漫、親密與純慾"),
        "message": "大俠，今晚的我，只讓你看見。"
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
# 👗 終極進化版 /cosplay 指令 (Seedream v4.5 核心)
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
            r' (seductive) ': 'elegant', r' (alluring) ': 'graceful',
            r' (sensual) ': 'cinematic', r' (sexy) ': 'stylish',
            r' (bedroom eyes) ': 'warm expression', r' (sultry) ': 'confident',
            r' (voluptuous) ': 'elegant', r' (cleavage) ': 'neckline'
        })

    # L2: 移除身形強調詞 (Body emphasis)
    if level >= 2:
        rewrites.update({
            r' (form-fitting) ': 'flowing tailored', r' (waist-cinching) ': 'tailored',
            r' (hip shift) ': 'natural posture', r' (hourglass(-inspired)? silhouette) ': 'elegant silhouette',
            r' (tight) ': 'fitted', r' (curvy) ': 'graceful', r' (bodycon) ': 'elegant dress'
        })

    # L3: 移除危險的時尚攝影框架 (Fashion erotic framing)
    if level >= 3:
        rewrites.update({
            r' (luxury perfume advertisement( aesthetic)?) ': 'cinematic fashion editorial',
            r' (Vogue glamour) ': 'premium magazine portrait',
            r' (fashion model) ': 'elegant young woman',
            r' (runway) ': 'cinematic scene', r' (campaign) ': 'story-driven portrait'
        })

    # L4: 移除極度逼真的皮膚與寫實感 (Realism downgrade)
    if level >= 4:
        rewrites.update({
            r' (photorealistic) ': 'soft cinematic rendering',
            r' (natural skin texture) ': 'refined portrait texture',
            r' (8k) ': 'highly detailed'
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
        outfit_control = state.get("outfit_control") if isinstance(state, dict) else None
        lighting_mood = _clean_anchor_text(state.get("lighting_mood"), "soft natural or ambient light")
        setting_anchor = _clean_anchor_text(state.get("setting_anchor"), "")
        time_anchor = _clean_anchor_text(state.get("time_anchor"), "")
        camera_framing = _clean_anchor_text(state.get("camera_framing"), "full_body")
        scenario_tw = _clean_anchor_text(state.get("scenario_tw"), "")

        lines.append(_appearance_anchor_block(mode))
        if str(mode or "").lower() in {"diary", "photo_scene", "photo_reference"}:
            lines.append(SOLO_SCENE_REWRITE_GUARD.strip())
            violation = visual_dict.get("__solo_gate_violation") if isinstance(visual_dict, dict) else None
            if violation:
                lines.append(f"PREVIOUS OUTPUT FAILED SOLO CHECK: {violation}. Regenerate as a clean solo Xiaoxia image with zero second-person traces.")
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
        if outfit_control:
            lines.append(f"- Mandatory outfit control that must remain visible even during retries: {json.dumps(outfit_control, ensure_ascii=False)}.")
        lines.append(f"- Lighting mood to preserve: {lighting_mood}.")
        if scenario_tw:
            lines.append(f"- Overall scene intent: {scenario_tw}.")

        lines.append("- Character visibility rule: strictly only Xiaoxia appears in the image; Xiaoxia is the only human figure.")
        lines.append("- Forbidden visual intrusions: no external hands, people, external feet, or any visible body part of the viewer.")
        lines.append("- No-male rule: do not show Daxia, any man, male hands, male arms, male shoulder, male back, male torso, male silhouette, male reflection, cropped male body parts, or foreground viewer hands/arms/shoulders.")
        lines.append("- POV rule: if this is Daxia's or boyfriend POV, imply it only through camera framing; never depict the boyfriend or substitute him with another male figure.")
        lines.append("- Anatomy rule: Xiaoxia's posture, hands, fingers, limbs, joints, and movement must be natural, physically plausible, and normal; no extra limbs, twisted joints, broken fingers, impossible hand poses, or awkward body mechanics.")

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
            lines.append("- Maintain consistent facial identity and core body identity from Image 1. She is an adult fictional character.")
            lines.append("- For cosplay, keep Xiaoxia's face recognizable first. Hairstyle and hair color may adapt to the role when needed for recognizable cosplay fidelity, but she must still clearly read as Xiaoxia cosplaying the role.")
    else:
        prompt_hint = _clean_anchor_text(initial_prompt)
        lines.append(_appearance_anchor_block(mode))
        lines.append("HARD SCENE ANCHORS — preserve the original scene action and gaze direction as closely as possible.")
        if prompt_hint:
            lines.append(f"- Keep this scene action and context recognizable: {prompt_hint[:500]}.")
        lines.append("- Strictly solo Xiaoxia only; no man, no other people, no visible viewer body parts, no foreground hands/arms/shoulders, no male silhouette or reflection.")
        lines.append("- Boyfriend POV must be implied only through framing; never draw the boyfriend or any substitute male figure.")
        lines.append("- Xiaoxia's anatomy and movement must be natural and physically plausible; no malformed hands, extra limbs, twisted joints, or awkward body mechanics.")
        lines.append("- Do not collapse the image into a generic glamour portrait.")
    lines.append("- Absolute POV rule: never show Daxia or substitute him with a male head, shoulder, hand, arm, back, silhouette, reflection, cropped body part, or blurred foreground figure. No other people of any gender.")

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
        "Critical rule: if there is any tension between style wording and hard scene anchors, the hard scene anchors always win. "
        + SOLO_NEGATIVE_MINIMAL + " "
        "Strictly solo focus on Xiaoxia. NO external hands, people, external feet, men, male heads, male faces, male hair, male shoulders, male backs, male body parts, visible viewer body parts, foreground hands/arms/shoulders, blurred foreground male figures, silhouettes, cropped people, or reflections. Xiaoxia's anatomy and movement must remain natural and physically plausible."
    )



def _compose_ultimate_safe_prompt(mode, visual_dict, initial_prompt):
    """最終保底也必須保留場景骨架，不可洗成泛用美女圖。"""
    hard_anchor_block = _build_hard_anchor_block(mode, visual_dict, initial_prompt)
    if mode == "diary":
        safe_style = (
            "Create a very safe, elegant, natural daily-life image of an adult fictional Asian woman in a modest, refined outfit. "
            "Use gentle ambient light, realistic posture, and a quiet lived-in atmosphere. Strictly only Xiaoxia appears in the image. NO external hands, people, external feet, men, male heads, male faces, male hair, male shoulders, male backs, male body parts, visible viewer body parts, foreground hands/arms/shoulders, blurred foreground male figures, silhouettes, cropped people, or reflections. If it is a Daxia point-of-view scene, Daxia must never be visually depicted and POV must be implied only through framing. Xiaoxia's anatomy and movement must be natural and physically plausible. Preserve the specific activity, hand actions, props, seating or standing situation, and gaze direction from the hard scene anchors. "
            "Maintain consistent facial identity and core body identity from Image 1. Keep Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. Allow a scene-appropriate natural hairstyle variation while keeping the hair color in a natural brown family. High quality."
        )
    else:
        safe_style = (
            "Create a very safe, story-driven cosplay image of an adult fictional Asian woman in a modest, character-appropriate outfit. The style may be cute, heroic, magical, adventurous, dramatic, or refined as long as it remains safe and non-revealing. "
            "Use graceful cinematic ambience, realistic posture, and a task-focused moment. Strictly only Xiaoxia appears in the image. NO external hands, people, external feet, men, male heads, male faces, male hair, male shoulders, male backs, male body parts, visible viewer body parts, foreground hands/arms/shoulders, blurred foreground male figures, silhouettes, cropped people, or reflections. Xiaoxia's anatomy and movement must be natural and physically plausible. Preserve the specific activity, hand actions, props, body orientation, and gaze direction from the hard scene anchors. "
            "Maintain consistent facial identity and core body identity from Image 1. Keep Xiaoxia's recognizable sweet East Asian facial features, fair skin, tall slim figure, defined waist, and naturally full bust proportion. For cosplay, hairstyle and hair color may adapt to the role when needed for recognizability, while still clearly reading as Xiaoxia cosplaying the role. High quality."
        )
    return f"{hard_anchor_block}\n\nULTIMATE SAFE STYLE LAYER:\n{safe_style}"



async def _download_image_bytes_for_vision(image_url, max_bytes=8_000_000):
    if not image_url or not str(image_url).startswith("http"):
        return None, None
    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(str(image_url)) as resp:
                if resp.status != 200:
                    return None, None
                data = await resp.read()
        if not data or len(data) > max_bytes:
            return None, None
        # 粗略從 URL 判斷；gallery 多半是 jpg/png，Gemini 可接受 image/jpeg 作為保底。
        url_lower = str(image_url).lower()
        if ".png" in url_lower:
            mime = "image/png"
        elif ".webp" in url_lower:
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        return data, mime
    except Exception as exc:
        print(f"⚠️ [SOLO_GATE_DOWNLOAD_FAILED] {type(exc).__name__}: {exc}")
        return None, None


async def _vision_check_solo_xiaoxia_image_url(image_url, mode="photo"):
    """
    出圖後的輕量驗圖 gate：只檢查是否混入第二人/男人/外來手腳。
    失敗時回傳 (False, reason)；無法檢查時為避免誤殺，回傳 (True, reason)。
    """
    if str(mode or "").lower() not in {"photo_scene", "photo_reference", "diary"}:
        return True, "mode not checked"

    data, mime = await _download_image_bytes_for_vision(image_url)
    if not data:
        return True, "vision skipped: cannot download generated image"

    prompt = """
You are an image QA checker for a solo character generation pipeline.
Check the image strictly for unwanted additional people.

Return JSON only:
{
  "solo_xiaoxia_only": true/false,
  "human_count": number,
  "has_male_or_partner": true/false,
  "has_external_hands_or_body_parts": true/false,
  "has_second_person_reflection_shadow_or_partial": true/false,
  "reason": "short explanation"
}

Rules:
- Pass only if the image contains exactly one visible human figure and that person is the female subject Xiaoxia.
- Fail if there is any man, second person, partner, external hand/arm/leg/shoulder, cropped body part, reflection/shadow of another person, or foreground viewer body part.
- A printed photo, painting, statue, mannequin, or decorative object is not a person unless it appears as a real human in the scene.
"""
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Part.from_bytes(data=data, mime_type=mime), prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        result = _safe_json_from_text(resp.text, {})
        if not isinstance(result, dict):
            return True, "vision skipped: invalid JSON"
        ok = bool(result.get("solo_xiaoxia_only")) and int(result.get("human_count", 1) or 1) <= 1 and not bool(result.get("has_male_or_partner")) and not bool(result.get("has_external_hands_or_body_parts")) and not bool(result.get("has_second_person_reflection_shadow_or_partial"))
        reason = str(result.get("reason") or result)
        return ok, reason[:300]
    except Exception as exc:
        print(f"⚠️ [SOLO_GATE_VISION_FAILED] {type(exc).__name__}: {exc}")
        return True, "vision skipped: checker error"



async def execute_safe_generation(discord_image_url, base_filename, mode, initial_prompt, visual_dict, msg=None, current_outfit=None):
    """自動調度 5 層脫敏機制的生圖引擎；Cosplay/交換日記改用 Seedream v4.5 image-to-image，並保留重試。"""
    seedream_modes = {"cosplay", "diary", "photo_scene", "photo_reference", "travel", "shopping"}
    engine_name = "Seedream v4.5"
    gpt_image2_is_fallback_only = os.environ.get("ENABLE_GPT_IMAGE2_FALLBACK", "false").lower() in {"1", "true", "yes"}

    for level in range(5):
        current_prompt = _compose_prompt_with_anchors(initial_prompt, mode, visual_dict, level)
        # Seedream v4.5 交由 fal safety checker 處理，不再先被 OpenAI Moderation 擋住；
        # 仍保留 L0→L4 的提示詞安全化重試。
        if mode == "gpt_image_2_fallback" and gpt_image2_is_fallback_only:
            mod_resp = await openai_client.moderations.create(model="omni-moderation-latest", input=current_prompt)
            if mod_resp.results[0].flagged:
                if msg:
                    await msg.edit(content=f"⚠️ [L{level}] 文字安檢未過，保留場景骨架並啟動 L{level+1} 深層脫敏...")
                if isinstance(visual_dict, dict):
                    visual_dict["composition"] += f"\n*(自動觸發 L{level} 級安全濾鏡，已保留場景骨架)*"
                continue

        if msg:
            await msg.edit(content=f"📸 {engine_name} 攝影機啟動 (當前防護等級：L{level}，保留場景骨架中)...")

        generated_image_url = await generate_world_composite(
            discord_image_url=discord_image_url,
            base_filename=base_filename,
            mode=mode,
            custom_prompt=current_prompt,
            current_outfit=current_outfit,
        )

        if not generated_image_url or not str(generated_image_url).startswith("http"):
            error_str = str(generated_image_url).lower()
            if _seedream_error_is_retryable(error_str) or any(token in error_str for token in ("moderation", "sexual", "safety_violations")):
                if msg:
                    await msg.edit(content=f"⚠️ [L{level}] 遭 {engine_name} 安全/內容檢查攔截！保留場景骨架並啟動 L{level+1} 材質與姿態柔化...")
                if isinstance(visual_dict, dict):
                    visual_dict["composition"] += f"\n*(自動觸發 L{level} 級安全濾鏡，已保留場景骨架)*"
                continue
            raise Exception(f"攝影機異常：{generated_image_url}")

        if str(mode or "").lower() in {"photo_scene", "photo_reference", "diary"}:
            solo_ok, solo_reason = await _vision_check_solo_xiaoxia_image_url(generated_image_url, mode=mode)
            if not solo_ok:
                print(f"⚠️ [SOLO_GATE_REJECTED] mode={mode} reason={solo_reason}")
                if msg:
                    await msg.edit(content=f"⚠️ 小俠發現這張混入了不該出現的人物/肢體，正在自動重拍（原因：{solo_reason[:120]}）...")
                if isinstance(visual_dict, dict):
                    visual_dict["__solo_gate_violation"] = solo_reason
                    visual_dict["composition"] = str(visual_dict.get("composition", "")) + "\n*(Solo gate rejected previous output: regenerate as Xiaoxia-only, no second person, no external body parts.)*"
                initial_prompt = SOLO_SCENE_REWRITE_GUARD.strip() + "\n\n" + str(initial_prompt)
                continue

        if isinstance(visual_dict, dict):
            visual_dict["engine"] = engine_name
        return generated_image_url, visual_dict

    if msg:
        await msg.edit(content=f"🚨 警告：連續五級脫敏皆遭攔截，啟動最終【保留場景骨架的絕對安全保底】...")
    ultimate_safe_prompt = _compose_ultimate_safe_prompt(mode, visual_dict, initial_prompt)
    if isinstance(visual_dict, dict):
        visual_dict["composition"] += "\n*(⚠️ 神祕審查力量過於強大，小俠已自動換上最安全造型，但仍盡力保留場景骨架)*"

    final_url = await generate_world_composite(discord_image_url, base_filename, mode, ultimate_safe_prompt, current_outfit=current_outfit)
    if not final_url or not str(final_url).startswith("http"):
        raise Exception(f"最終保底生圖依然失敗：{final_url}")

    if str(mode or "").lower() in {"photo_scene", "photo_reference", "diary"}:
        solo_ok, solo_reason = await _vision_check_solo_xiaoxia_image_url(final_url, mode=mode)
        if not solo_ok:
            raise Exception(f"最終保底仍混入第二人/男人/外來肢體：{solo_reason}")
    if isinstance(visual_dict, dict):
        visual_dict["engine"] = engine_name
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

    vibe_mode = _extract_vibe_mode(mode)
    story_mode = mode
    if vibe_mode:
        story_mode = mode
        for alias in VIBE_KEYWORDS.get(vibe_mode.get("zh"), []):
            story_mode = re.sub(re.escape(alias), "", story_mode, flags=re.IGNORECASE)
        story_mode = re.sub(r"\s+", " ", story_mode).strip(" ,，") or "auto"
    msg = await ctx.send(f"✨ 正在為【{mode}】企劃撰寫劇本，並準備啟動 Seedream v4.5 image-to-image 攝影引擎...")
    try:
        # 1. 產生故事與人設
        story = await generate_story(story_mode)
        story["user_mode_request"] = mode
        story["user_outfit_hints"] = _extract_user_outfit_hints(mode)
        state["current_topic_data"] = story 
        
        # 2. Cosplay 導演層：先規劃人物當下的自然行為，再轉譯成 Seedream v4.5 可執行的提示詞
        await msg.edit(content=f"✨ 劇本完成！小夏正在安排這次 Cosplay 的自然動作與鏡頭語言，並套用 Seedream v4.5 參考底稿...")
        _cosplay_state, visual = await create_cosplay_visual(story, state["retry_count"] >= 2, alternative=False, vibe_request=vibe_mode, user_outfit_hints=story.get("user_outfit_hints"))
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
            "mood_summary": visual.get("mood", ""),
            "message": visual["message"],
            "image_url": generated_image_url,
            "local_url": local_url,
            "local_filename": local_filename,
            "local_path": os.path.join(OUTPUT_DIR, local_filename) if local_filename else None,
            "type": "cosplay",
            "source_mode": "cosplay",
            "prompt_base": scene_prompt,
        }
        db = load_memory()
        db.insert(0, payload)
        save_memory(db)

        embed = discord.Embed(title=story["topic"], description=story["event"], color=0xffb6c1)
        embed.set_image(url=local_url)
        embed.add_field(name="📸 構圖發想", value=visual["composition"], inline=False)
        embed.add_field(name="💭 小俠心境", value=visual["mood"], inline=False)
        embed.add_field(name="💌 專屬留言", value=visual["message"], inline=False)
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/12 | Seedream v4.5 image-to-image")

        await msg.delete()
        result_view = PhotoResultView(payload)
        new_msg = await ctx.send(embed=embed, view=result_view)
        payload["message_id"] = new_msg.id
        photo_generation_contexts[new_msg.id] = payload
        result_view.context = payload
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

# ==========================================
# 🌱 Seedream v4.5 Cosplay image-to-image 引擎
# ==========================================
def _load_json_file_safe(path, fallback):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print(f"⚠️ JSON 讀取失敗 {path}: {exc}")
    return fallback


def _save_json_file_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _seedream_reference_paths():
    """讀取 /data/memory/seedream_v45 內的 Seedream_01~09 參考底稿。"""
    manifest_path = os.path.join(SEEDREAM_V45_REF_DIR, "manifest.txt")
    paths = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                value = line.strip()
                if value:
                    paths.append(value if os.path.isabs(value) else os.path.join(SEEDREAM_V45_REF_DIR, value))
    if not paths:
        for index in range(1, 10):
            paths.append(os.path.join(SEEDREAM_V45_REF_DIR, f"Seedream_{index:02d}.png"))

    existing = [p for p in paths if os.path.exists(p)]
    if len(existing) < 1:
        raise FileNotFoundError(
            f"找不到 Seedream v4.5 參考底稿，請確認已上傳至 {SEEDREAM_V45_REF_DIR}/Seedream_01.png~Seedream_09.png"
        )
    # Seedream v4.5 edit 最多 10 張輸入圖；此處固定最多 9 張人物底稿。
    return existing[:9]


def _get_fal_client():
    try:
        import fal_client
        return fal_client
    except ImportError:
        print("⚠️ fal_client 未安裝，嘗試即時安裝 fal-client...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fal-client"])
        import fal_client
        return fal_client


async def _seedream_upload_reference_images(force_refresh=False):
    """將本機 /data/memory/seedream_v45 參考圖上傳到 fal 檔案服務並快取 URL。

    fal media URL 可能過期或失效；若後續 Seedream 回 file_download_error，
    呼叫端會用 force_refresh=True 重新上傳 1-9 號人物底稿再重試。
    """
    fal_client = _get_fal_client()
    cache = _load_json_file_safe(SEEDREAM_V45_UPLOAD_CACHE_PATH, {})
    if force_refresh or not isinstance(cache, dict):
        cache = {}
    changed = bool(force_refresh)
    urls = []
    for path in _seedream_reference_paths():
        stat = os.stat(path)
        key = os.path.basename(path)
        cached = cache.get(key, {}) if isinstance(cache, dict) else {}
        valid = (
            not force_refresh
            and cached.get("path") == path
            and cached.get("mtime") == stat.st_mtime
            and cached.get("size") == stat.st_size
            and str(cached.get("url", "")).startswith("http")
        )
        if valid:
            url = cached["url"]
        else:
            print(f"🌱 [SEEDREAM_UPLOAD] uploading {path} force={force_refresh}")
            url = await asyncio.to_thread(fal_client.upload_file, path)
            cache[key] = {
                "path": path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "url": url,
                "uploaded_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            }
            changed = True
        urls.append(url)
    if changed:
        _save_json_file_atomic(SEEDREAM_V45_UPLOAD_CACHE_PATH, cache)
    return urls


def _seedream_cosplay_prompt(custom_prompt):
    return (
        "Use all input images as reference sheets for the same adult fictional character, Xiaoxia. "
        "Preserve her recognizable sweet East Asian facial identity, fair skin, tall slim figure, defined waist, naturally full bust proportion, gentle youthful-adult aura, and natural body proportions from the references. "
        "Do not copy any one reference pose or background exactly; create a new cosplay image according to the prompt. "
        "Only Xiaoxia may appear. No man, no male head, no male face, no male hair, no male hands, no male arms, no male shoulder, no male back, no male torso, no other people, no reflections of other people. "
        "Do not show Daxia, the camera holder, or any visible body part of the viewer. No blurred male foreground figure, no cropped male body parts, no male silhouette, no male reflection, and no foreground viewer hand/arm/shoulder. The POV must be implied only through framing, Xiaoxia's gaze, and composition. "
        "Keep anatomy natural, hands plausible; Xiaoxia's posture, limbs, joints, hands, and fingers must be physically plausible and normal, with no awkward body mechanics. "
        "For cosplay, Xiaoxia's face identity must remain recognizable first. Hairstyle and hair color may adapt to the role when needed for recognizable cosplay fidelity, but the result must still clearly read as Xiaoxia cosplaying the role rather than the original actor or a different woman. "
        "Maximize visual impact: explicitly allow extreme cinematic angles, dramatic chiaroscuro lighting, highly detailed fabric textures (including translucent, wet, or form-fitting materials), and alluring/seductive expressions if requested. "
        "The result should be a highly polished cinematic cosplay photograph with vivid character storytelling and intense visual appeal.\n\n"
        f"COSPLAY EDIT REQUEST:\n{custom_prompt}"
    )


def _seedream_error_is_retryable(value):
    raw = str(value or "").lower()
    return any(token in raw for token in (
        "moderation", "safety", "safe", "policy", "blocked", "violation", "sexual", "nsfw", "not allowed", "content"
    ))


async def generate_seedream_v45_cosplay(custom_prompt, enable_safety_checker=True):
    """呼叫 fal-ai/bytedance/seedream/v4.5/edit，用 9 張 Zeabur 參考底稿做 image-to-image。"""
    fal_client = _get_fal_client()
    image_urls = await _seedream_upload_reference_images()
    final_prompt = _seedream_cosplay_prompt(custom_prompt)

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🌱 [SEEDREAM_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            SEEDREAM_V45_MODEL_ID,
            arguments={
                "prompt": final_prompt,
                "image_urls": image_urls,
                "image_size": SEEDREAM_V45_IMAGE_SIZE,
                "num_images": 1,
                "max_images": 1,
                "enable_safety_checker": bool(enable_safety_checker),
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    try:
        result = await asyncio.to_thread(_subscribe)
    except Exception as exc:
        if _is_fal_content_policy_error(exc):
            raise RuntimeError(
                "WARDROBE_CLEANUP_CONTENT_POLICY：這張圖被 fal.ai / Seedream 的圖片安全檢查擋下，無法自動去人。"
                "請換一張更像商品平鋪照、模特兒露膚較少的圖，或先用 `/衣櫃 新增 名稱` 直接收藏原圖。"
            ) from exc
        raise
    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        return f"Seedream v4.5 沒有回傳圖片：{result}"
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"]
    return f"Seedream v4.5 圖片欄位格式異常：{result}"


def _seedream_diary_prompt(custom_prompt):
    return (
        "Use all input images as reference sheets for the same adult fictional character, Xiaoxia. "
        "Preserve her recognizable sweet East Asian facial identity, fair skin, tall slim figure, defined waist, naturally full bust proportion, gentle youthful-adult aura, and natural body proportions from the references. "
        "Create a new candid diary/lifestyle photograph according to the prompt. Do not copy any one reference pose or background exactly. "
        "This is a warm, intimate, romantic private exchange-diary moment in a contemporary Taiwan daily-life setting, but the visual frame is a solo Xiaoxia photograph only. "
        + SOLO_SCENE_REWRITE_GUARD.strip() + " "
        "Only Xiaoxia may appear. No man, no male head, no male face, no male hair, no male hands, no male arms, no male shoulder, no male back, no male torso, no other people, no reflections of other people. "
        "Do not show Daxia, the camera holder, or any visible body part of the viewer. No blurred male foreground figure, no cropped male body parts, no male silhouette, no male reflection, and no foreground viewer hand/arm/shoulder. The POV must be implied only through framing, Xiaoxia's gaze, and composition. "
        "Keep anatomy natural, hands plausible; Xiaoxia's posture, limbs, joints, hands, and fingers must be physically plausible and normal, with no awkward body mechanics. "
        "Keep Xiaoxia's everyday identity recognizable: natural brown-family hair color, but allow a scene-appropriate hairstyle variation such as loose waves, ponytail, low ponytail, princess half-up, relaxed tied hair, or a simple updo. "
        "Clothing can range from cozy loungewear to intimate sleepwear (such as silk slip dresses, lace chemises, or form-fitting outfits), allowing for figure-flattering, translucent, or alluring styles to portray romantic closeness. "
        "Preserve the described daily action, props, gaze direction, romantic lighting mood, and lived-in environment details.\n\n"
        f"DIARY EDIT REQUEST:\n{custom_prompt}"
    )


async def generate_seedream_v45_diary(custom_prompt, enable_safety_checker=True):
    """呼叫 fal-ai/bytedance/seedream/v4.5/edit，用 9 張 Zeabur 參考底稿做交換日記 image-to-image。"""
    fal_client = _get_fal_client()
    image_urls = await _seedream_upload_reference_images()
    final_prompt = _seedream_diary_prompt(custom_prompt)

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🌱 [SEEDREAM_DIARY_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            SEEDREAM_V45_MODEL_ID,
            arguments={
                "prompt": final_prompt,
                "image_urls": image_urls,
                "image_size": SEEDREAM_V45_IMAGE_SIZE,
                "num_images": 1,
                "max_images": 1,
                "enable_safety_checker": bool(enable_safety_checker),
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    result = await asyncio.to_thread(_subscribe)
    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        return f"Seedream v4.5 沒有回傳交換日記圖片：{result}"
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"]
    return f"Seedream v4.5 交換日記圖片欄位格式異常：{result}"



# ==========================================
# 👗 衣櫃 / 當日衣著連貫性
# ==========================================
WARDROBE_MAIN_CATEGORIES = [
    "洋裝", "上衣", "下身", "套裝", "外套", "睡衣／居家服", "內衣", "泳裝", "鞋子", "包包", "配件", "Cosplay／特殊服裝"
]

WARDROBE_SUBCATEGORY_OPTIONS = {
    "洋裝": ["洋裝", "短洋裝", "長洋裝", "連衣裙", "禮服"],
    "上衣": ["T恤", "襯衫", "針織衫", "背心", "罩衫", "上衣"],
    "下身": ["短裙", "長裙", "半身裙", "褲子", "短褲", "下身"],
    "套裝": ["裙裝套裝", "褲裝套裝", "居家套裝", "圍裙套裝", "上下身套裝", "套裝"],
    "外套": ["外套", "罩衫", "大衣", "針織外套"],
    "睡衣／居家服": ["睡裙", "睡袍", "睡衣套裝", "居家套裝", "居家服"],
    "內衣": ["內衣套裝", "胸罩", "內褲", "吊帶內衣", "內衣"],
    "泳裝": ["比基尼", "連身泳衣", "泳裝"],
    "鞋子": ["高跟鞋", "靴子", "球鞋", "拖鞋", "鞋子"],
    "包包": ["肩背包", "手提包", "斜背包", "包包"],
    "配件": ["項鍊", "耳環", "手鍊", "帽子", "絲巾", "腰帶", "配件"],
    "Cosplay／特殊服裝": ["Cosplay", "角色服", "特殊服裝"],
}

WARDROBE_CATEGORY_ALIASES = {
    "睡衣/居家服": "睡衣／居家服", "睡衣／居家": "睡衣／居家服", "睡衣": "睡衣／居家服", "居家服": "睡衣／居家服", "居家": "睡衣／居家服",
    "cosplay": "Cosplay／特殊服裝", "Cosplay": "Cosplay／特殊服裝", "特殊服裝": "Cosplay／特殊服裝", "角色服": "Cosplay／特殊服裝",
    "鞋": "鞋子", "包": "包包", "飾品": "配件", "配飾": "配件",
}


def _normalize_wardrobe_main_category(value, fallback=None):
    raw = _clean_text_compact(value).replace("/", "／")
    if not raw:
        return fallback if fallback in WARDROBE_MAIN_CATEGORIES else "上衣"
    if raw in WARDROBE_MAIN_CATEGORIES:
        return raw
    if raw in WARDROBE_CATEGORY_ALIASES:
        return WARDROBE_CATEGORY_ALIASES[raw]
    if raw == "睡衣／居家服":
        return "睡衣／居家服"
    return fallback if fallback in WARDROBE_MAIN_CATEGORIES else None


def _normalize_wardrobe_sub_category(main_category, value):
    main_category = _normalize_wardrobe_main_category(main_category, fallback="上衣") or "上衣"
    raw = _clean_text_compact(value)
    if not raw:
        return WARDROBE_SUBCATEGORY_OPTIONS.get(main_category, [main_category])[0]
    aliases = {
        "連身裙": "連衣裙", "連身洋裝": "洋裝", "睡衣": "睡衣套裝", "睡袍／罩衫": "睡袍",
        "半裙": "半身裙", "裙": "半身裙", "衣服": main_category,
    }
    return aliases.get(raw, raw)


def _wardrobe_tags_from_text(*parts, limit=8):
    blob = " ".join(str(p or "") for p in parts)
    tokens = [x for x in re.split(r"[\s,，、/／「」()（）]+", blob) if x]
    result = []
    for token in tokens:
        token = _clean_text_compact(token)
        if token and token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result


def _clean_text_compact(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _today_outfit_reset_if_needed(state_data):
    today = _today_str_tpe()
    if state_data.get("current_outfit_date") != today:
        state_data["current_outfit_date"] = today
        state_data["current_outfit"] = None
    return state_data


def _get_current_outfit_state():
    state_data = load_state()
    state_data = _today_outfit_reset_if_needed(state_data)
    save_state(state_data)
    return state_data.get("current_outfit")


def _set_current_outfit_state(outfit_payload):
    state_data = load_state()
    state_data = _today_outfit_reset_if_needed(state_data)
    state_data["current_outfit"] = outfit_payload
    state_data["current_outfit_date"] = _today_str_tpe()
    save_state(state_data)


def _clear_current_outfit_state():
    state_data = load_state()
    state_data["current_outfit"] = None
    state_data["current_outfit_date"] = _today_str_tpe()
    save_state(state_data)


def _get_pending_wardrobe_state():
    state_data = load_state()
    return state_data.get("photo_pending_wardrobe")


def _refresh_pending_wardrobe_from_current_db(pending_item):
    """photo_pending_wardrobe 可能是換圖前的舊快照；每次 /photo 前用目前 wardrobe DB 重新取一次。"""
    if not isinstance(pending_item, dict):
        return pending_item
    wid = str(pending_item.get("id") or "").strip().upper()
    if not wid:
        return pending_item
    current = _find_wardrobe_item(wid)
    if isinstance(current, dict):
        return current
    return pending_item


def _sync_pending_wardrobe_if_same_item(updated_item):
    """若目前已預選同一件衣服，換圖/修正後同步 pending，避免 /photo 繼續拿舊 URL。"""
    if not isinstance(updated_item, dict):
        return
    wid = str(updated_item.get("id") or "").strip().upper()
    if not wid:
        return
    state_data = load_state()
    pending = state_data.get("photo_pending_wardrobe")
    if isinstance(pending, dict) and str(pending.get("id") or "").strip().upper() == wid:
        state_data["photo_pending_wardrobe"] = updated_item
        save_state(state_data)


def _pending_wardrobe_has_usable_reference(item):
    """預選衣櫃必須真的有可用圖片；否則清掉，避免 /photo 被切到 photo_reference 但拿到 None。"""
    if not isinstance(item, dict):
        return False
    ref_path = str(item.get("reference_image_path") or "").strip()
    ref_url = str(item.get("local_url") or item.get("reference_item_url") or "").strip()
    if ref_path and os.path.exists(ref_path):
        return True
    if ref_url.startswith("http"):
        return True
    return False


def _set_pending_wardrobe_state(item):
    state_data = load_state()
    state_data["photo_pending_wardrobe"] = item
    save_state(state_data)


def _clear_pending_wardrobe_state():
    state_data = load_state()
    state_data["photo_pending_wardrobe"] = None
    save_state(state_data)


def _photo_requests_outfit_change(raw_scene_text):
    text_value = str(raw_scene_text or "")
    patterns = [
        r"換成", r"換上", r"改穿", r"穿上", r"改成.*(?:衣|裙|褲|外套|睡衣|泳裝|內衣)",
        r"今天穿", r"想讓她穿", r"套用衣櫃", r"穿這件", r"穿那件"
    ]
    return any(re.search(pattern, text_value) for pattern in patterns)


def _build_outfit_state_from_context(context):
    if not context:
        return None
    return {
        "date": _today_str_tpe(),
        "description": _clean_text_compact(context.get("outfit_summary") or "自然日常穿搭"),
        "source": context.get("source_mode", "photo_scene"),
        "scene_summary": _clean_text_compact(context.get("scene_summary") or ""),
        "reference_item_path": context.get("reference_item_path"),
        "reference_item_url": context.get("reference_item_url") or context.get("local_url") or context.get("image_url"),
        "wardrobe_id": context.get("wardrobe_id"),
        "updated_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _wardrobe_item_short(item):
    return f"{item.get('id')}｜{item.get('name')}｜{item.get('main_category')}/{item.get('sub_category')}"


def _extract_category_prefixed_name(name_hint):
    """
    支援：
    /衣櫃 新增 內衣 米白色珍珠結構款套裝
    /衣櫃 新增 泳裝 黑色...
    第一個詞若是主分類，就當分類提示，不把它留在名稱裡。
    """
    raw = _clean_text_compact(name_hint)
    if not raw:
        return "", ""
    for cat in sorted(WARDROBE_MAIN_CATEGORIES, key=len, reverse=True):
        if raw == cat:
            return cat, raw
        if raw.startswith(cat + " "):
            return cat, raw[len(cat):].strip()
    return "", raw


def _wardrobe_item_generation_hint(item):
    """把衣櫃資料轉成 /photo 的硬提示，避免「套裝」被誤解成西裝/長袖套裝。"""
    if not isinstance(item, dict):
        return ""
    item_id = item.get("id", "")
    name = _clean_text_compact(item.get("name", ""))
    main = _clean_text_compact(item.get("main_category", ""))
    sub = _clean_text_compact(item.get("sub_category", ""))
    summary = _clean_text_compact(item.get("style_summary", ""))
    tags = "、".join(item.get("tags") or [])
    hint = (
        f"Selected wardrobe item {item_id}: {name}. "
        f"Category: {main}/{sub}. Tags: {tags}. Summary: {summary}. "
        "Image 10 is the exact visual reference and must dominate the text label. "
        "Preserve the actual garment type shown in Image 10; do not reinterpret the Chinese word '套裝' as a blazer, jacket, suit, formal set, dress suit, or long-sleeve outerwear. "
        "'套裝' here means a matching clothing set unless the image clearly shows a blazer/suit. "
    )
    if main in {"內衣", "泳裝", "睡衣／居家服"} or any(k in (name + summary + tags) for k in ("內衣", "胸罩", "bra", "lingerie", "泳裝", "泳衣", "睡衣")):
        hint += (
            "This wardrobe category may be underwear/lingerie, swimwear, or sleepwear. "
            "If Image 10 shows a bra-and-bottom, lingerie set, swimwear, or sleepwear, keep that exact category and do not convert it into a jacket, blouse, blazer, long sleeves, or ordinary outerwear. "
            "Style it tastefully and safely in a fitting private or appropriate scene. "
        )
    return hint.strip()




def _extract_wardrobe_ids_from_text(text_value):
    """抓出 W003 / w003 這類衣櫃編號。"""
    return [m.group(0).upper() for m in re.finditer(r"\bW\d{3,4}\b", str(text_value or ""), flags=re.IGNORECASE)]


def _find_first_wardrobe_item_in_text(text_value):
    """文字有指定衣櫃編號時，必須回到衣櫃資料，不可只靠名稱腦補。"""
    for wid in _extract_wardrobe_ids_from_text(text_value):
        item = _find_wardrobe_item(wid)
        if item:
            return item
    return None


def _wardrobe_reference_for_generation(item):
    """回傳可餵給 Seedream 的衣櫃參考圖路徑/URL。找不到就回 None，避免望名自創。"""
    if not isinstance(item, dict):
        return None, None
    ref_path = str(item.get("reference_image_path") or "").strip()
    ref_url = str(item.get("local_url") or item.get("reference_item_url") or "").strip()
    if ref_path and os.path.exists(ref_path):
        return ref_path, ref_url or None
    if ref_url.startswith("http"):
        return ref_url, ref_url
    return None, ref_url or None


def _diary_promises_for_entry(profile, entry_date, max_items=4):
    """
    交換日記履約只抓「本篇日期」的承諾。
    尤其照片/穿搭承諾不可跨日自動延續；隔天沒有明講就回到場景自動穿搭。
    """
    bucket = profile.get("xiaoxia_self", {}).get("promises", [])
    selected, seen = [], set()
    for item in reversed(bucket):
        value = item.get("text", "") if isinstance(item, dict) else str(item)
        value = narrative_safe_text(value, max_len=180)
        if not value:
            continue
        added_at = str(item.get("added_at", "") if isinstance(item, dict) else "").strip()
        kind = infer_diary_promise_kind(value)
        is_outfit_or_photo = bool(re.search(r"(W\d{3,4}|衣櫃|穿|穿搭|服裝|照片|外出照|生活照|圖片|寫真)", value, re.I))
        # 有日期的穿搭/照片承諾只能在當日履約；舊日記重跑則以該 entry_date 為準。
        if is_outfit_or_photo and added_at and added_at != entry_date:
            continue
        # 無日期的舊承諾只允許文字，不讓它長期綁住照片穿搭。
        if is_outfit_or_photo and not added_at:
            continue
        key = value.rstrip("。")
        if key and key not in seen:
            seen.add(key)
            selected.append({"text": value, "kind": kind})
            if len(selected) >= max_items:
                break
    return selected


def _build_diary_wardrobe_selection(entry_content, chat_context, due_promises, result=None):
    """
    只有「本篇日記 / 今日聊天 / 本篇應履約承諾」明確指定衣櫃編號時，交換日記才使用衣櫃參考圖。
    不從 yesterday/current_outfit/recent_context 自動延續。
    """
    sources = [
        entry_content,
        chat_context,
        "\n".join([p.get("text", "") for p in due_promises or []]),
    ]
    if isinstance(result, dict):
        sources.extend([
            result.get("scenario_tw", ""),
            result.get("scenario", ""),
            result.get("promise_delivery", ""),
        ])
    blob = "\n".join(str(x or "") for x in sources)
    item = _find_first_wardrobe_item_in_text(blob)
    if not item:
        return None
    reference_path, reference_url = _wardrobe_reference_for_generation(item)
    if not reference_path:
        print(f"⚠️ [DIARY_WARDROBE_REFERENCE_MISSING] id={item.get('id')} name={item.get('name')}")
        return {
            "item": item,
            "reference_path": None,
            "reference_url": reference_url,
            "hint": _wardrobe_item_generation_hint(item),
            "error": "衣櫃項目找不到可用參考圖，已拒絕望名自創。",
        }
    return {
        "item": item,
        "reference_path": reference_path,
        "reference_url": reference_url,
        "hint": _wardrobe_item_generation_hint(item),
        "error": "",
    }

def _parse_key_value_fields(raw_text):
    """解析 `名稱=... 分類=... 子分類=... 標籤=...`，value 可含空白，直到下一個 key。"""
    raw = str(raw_text or "").strip()
    key_re = re.compile(r"(名稱|名字|name|分類|主分類|category|main_category|子分類|sub_category|標籤|tags|tag)\s*[=＝:]\s*", re.IGNORECASE)
    matches = list(key_re.finditer(raw))
    fields = {}
    if not matches:
        return fields
    for idx, match in enumerate(matches):
        key = match.group(1).lower()
        value_start = match.end()
        value_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        value = raw[value_start:value_end].strip().strip("，,；;")
        if key in {"名稱", "名字", "name"}:
            fields["name"] = value
        elif key in {"分類", "主分類", "category", "main_category"}:
            fields["main_category"] = value
        elif key in {"子分類", "sub_category"}:
            fields["sub_category"] = value
        elif key in {"標籤", "tags", "tag"}:
            fields["tags"] = [x.strip() for x in re.split(r"[,，、/／\s]+", value) if x.strip()]
    return fields


def _update_wardrobe_item_from_command(payload):
    raw = str(payload or "").strip()
    if not raw:
        return False, "用法：`/衣櫃 修正 W049 名稱=白色蕾絲薄紗睡衣`"
    first, _, rest = raw.partition(" ")
    item_id = first.upper().strip("，,。；;")
    rest = rest.strip()
    if not item_id:
        return False, "請提供衣櫃編號，例如：`/衣櫃 修正 W049 名稱=白色蕾絲薄紗睡衣`"

    fields = _parse_key_value_fields(rest)
    if not fields and rest:
        tokens = rest.split(maxsplit=1)
        maybe_cat = _normalize_wardrobe_main_category(tokens[0], fallback=None)
        if maybe_cat:
            fields["main_category"] = maybe_cat
            if len(tokens) > 1:
                fields["name"] = tokens[1].strip()
        else:
            fields["name"] = rest

    if not fields:
        return False, "請提供要修正的欄位，例如：`名稱=...`、`分類=...`、`子分類=...`、`標籤=...`"

    items = load_wardrobe()
    for item in items:
        if str(item.get("id", "")).upper() == item_id:
            old_main = item.get("main_category") if item.get("main_category") in WARDROBE_MAIN_CATEGORIES else "上衣"
            main_category = old_main
            if "main_category" in fields:
                normalized = _normalize_wardrobe_main_category(fields.get("main_category"), fallback=None)
                if not normalized:
                    return False, f"分類 `{fields.get('main_category')}` 不在可用分類內。可用：{'、'.join(WARDROBE_MAIN_CATEGORIES)}"
                main_category = normalized
                item["main_category"] = main_category

            if fields.get("name"):
                item["name"] = _clean_text_compact(fields.get("name"))

            if "sub_category" in fields:
                item["sub_category"] = _normalize_wardrobe_sub_category(main_category, fields.get("sub_category"))
            elif "main_category" in fields:
                item["sub_category"] = WARDROBE_SUBCATEGORY_OPTIONS.get(main_category, [main_category])[0]
            else:
                item["sub_category"] = _normalize_wardrobe_sub_category(main_category, item.get("sub_category") or main_category)

            if "tags" in fields:
                item["tags"] = [_clean_text_compact(x) for x in fields.get("tags", []) if _clean_text_compact(x)][:8]
            elif not item.get("tags") or str(item.get("name", "")).startswith("去人化服飾"):
                item["tags"] = _wardrobe_tags_from_text(item.get("name"), item.get("main_category"), item.get("sub_category"))

            item["style_summary"] = _clean_text_compact(
                fields.get("style_summary") or f"{item.get('name')}｜{item.get('main_category')}／{item.get('sub_category')}"
            )
            item["updated_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            save_wardrobe(items)
            return True, item
    return False, f"找不到衣櫃項目：{item_id}"


def _next_wardrobe_id(items):
    max_num = 0
    for item in items:
        m = re.match(r"W(\d+)", str(item.get("id", "")))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"W{max_num + 1:03d}"


def _find_wardrobe_item(item_id):
    target = str(item_id or "").strip().upper()
    for item in load_wardrobe():
        if str(item.get("id", "")).upper() == target:
            return item
    return None


def _wardrobe_matches(item, query):
    q = str(query or "").strip().lower()
    if not q:
        return True
    hay = " ".join([
        str(item.get("id", "")), str(item.get("name", "")), str(item.get("main_category", "")),
        str(item.get("sub_category", "")), " ".join(item.get("tags", []) or []), str(item.get("style_summary", "")),
    ]).lower()
    return q in hay


def _infer_wardrobe_meta_from_name(name_hint="", category_hint=""):
    name = _clean_text_compact(name_hint or "未命名服飾")
    hay = name + " " + str(category_hint or "")

    if any(k in hay for k in ("內衣", "胸罩", "bra", "比基尼內衣", "貼身內衣")):
        main, sub = "內衣", "內衣套裝"
    elif any(k in hay for k in ("泳裝", "泳衣", "比基尼")):
        main, sub = "泳裝", "比基尼" if "比基尼" in hay else "泳裝"
    elif any(k in hay for k in ("睡衣", "睡袍", "睡裙", "居家", "睡眠")):
        main = "睡衣／居家服"
        if "睡袍" in hay or "罩衫" in hay:
            sub = "睡袍"
        elif "睡裙" in hay or "薄紗睡衣" in hay or "蕾絲睡衣" in hay:
            sub = "睡裙"
        elif "套裝" in hay:
            sub = "睡衣套裝"
        else:
            sub = "居家服"
    elif any(k in hay for k in ("套裝", "整套", "搭配套裝", "兩件式", "三件式")):
        main = "套裝"
        if any(k in hay for k in ("裙", "裙裝", "洋裝")):
            sub = "裙裝套裝"
        elif any(k in hay for k in ("褲", "褲裝")):
            sub = "褲裝套裝"
        elif any(k in hay for k in ("居家", "睡衣")):
            sub = "居家套裝"
        else:
            sub = "套裝"
    elif any(k in hay for k in ("洋裝", "連衣裙", "連身裙", "小洋裝", "禮服")):
        main = "洋裝"
        if "禮服" in hay:
            sub = "禮服"
        elif any(k in hay for k in ("長洋裝", "長裙")):
            sub = "長洋裝"
        elif any(k in hay for k in ("短洋裝", "短裙")):
            sub = "短洋裝"
        else:
            sub = "連衣裙" if any(k in hay for k in ("連衣裙", "連身裙")) else "洋裝"
    elif any(k in hay for k in ("外套", "罩衫", "大衣", "開衫")):
        main, sub = "外套", "罩衫" if "罩衫" in hay else "外套"
    elif any(k in hay for k in ("短褲", "長褲", "半身裙", "短裙", "長裙", "下身")):
        main = "下身"
        if "短裙" in hay:
            sub = "短裙"
        elif "長裙" in hay:
            sub = "長裙"
        elif "半身裙" in hay:
            sub = "半身裙"
        elif "短褲" in hay:
            sub = "短褲"
        elif "褲" in hay:
            sub = "褲子"
        else:
            sub = "下身"
    elif any(k in hay for k in ("鞋", "靴", "拖鞋")):
        main = "鞋子"
        sub = "靴子" if "靴" in hay else ("拖鞋" if "拖鞋" in hay else "鞋子")
    elif any(k in hay for k in ("包", "背包", "手提", "肩背")):
        main, sub = "包包", "包包"
    elif any(k in hay for k in ("項鍊", "耳環", "帽", "配件", "飾品", "絲巾", "腰帶")):
        main, sub = "配件", "配件"
    elif any(k in hay for k in ("cosplay", "角色", "特殊")):
        main, sub = "Cosplay／特殊服裝", "Cosplay"
    else:
        main, sub = "上衣", "上衣"

    main = _normalize_wardrobe_main_category(main, fallback="上衣") or "上衣"
    sub = _normalize_wardrobe_sub_category(main, sub)
    tags = _wardrobe_tags_from_text(name, main, sub)
    return {
        "name": name,
        "main_category": main,
        "sub_category": sub,
        "tags": tags,
        "style_summary": f"{name}｜{main}／{sub}",
    }


def _parse_wardrobe_command(command_text):
    raw_text = str(command_text or "").strip()
    raw = re.sub(r"^/衣櫃(?:\s+|$)", "", raw_text, flags=re.IGNORECASE).strip()
    if not raw:
        return "browse", ""
    first, _, rest = raw.partition(" ")
    action = first.strip()
    rest = rest.strip()
    if action in {"新增", "去人", "看", "穿", "刪除", "問小俠", "修正", "換圖", "換圖去人", "換圖去人化", "健檢", "修復圖片", "圖片修復"}:
        return action, rest
    return "search", raw



def _wardrobe_category_counts(items):
    counts = {k: 0 for k in WARDROBE_MAIN_CATEGORIES}
    for item in items:
        cat = str(item.get("main_category", "") or "")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


async def _classify_wardrobe_item_from_image(local_path, name_hint=""):
    fallback_name = _clean_text_compact(name_hint or "未命名服飾")
    if not local_path or not os.path.exists(str(local_path)):
        print(f"⚠️ [WARDROBE_CLASSIFY_NO_IMAGE] path={local_path}")
        return {
            "name": fallback_name,
            "main_category": "配件",
            "sub_category": "未分類",
            "tags": [],
            "style_summary": fallback_name,
        }
    try:
        with open(str(local_path), "rb") as f:
            data = f.read()
        prompt = f"""
你是小俠衣櫃整理員。請根據這張服飾/配件參考圖，整理成結構化衣櫃資料。
請用「整套造型／衣櫃收藏」角度分類，不要把連衣裙誤判成下身。
若使用者有提供名稱，優先保留該名稱；若沒有名稱，請依圖片取一個 8~18 字的中文衣服名稱，不要使用「去人化服飾」。

使用者名稱提示：{name_hint or '無'}
可用主分類只能從以下挑一個：{', '.join(WARDROBE_MAIN_CATEGORIES)}
子分類建議：{json.dumps(WARDROBE_SUBCATEGORY_OPTIONS, ensure_ascii=False)}

分類規則：
- 連衣裙、連身裙、小洋裝、禮服 → 洋裝。
- 明顯上下身一起搭配、含包鞋配件的整套造型 → 套裝。
- 睡裙、睡袍、居家套裝 → 睡衣／居家服。
- 胸罩、內褲、吊帶、內衣套組 → 內衣。
- 比基尼、泳衣 → 泳裝。
- 只有單件裙子、褲子、短褲才歸下身；不要把連衣裙歸下身。

只回傳 JSON：
{{
  "name": "中文衣服名稱",
  "main_category": "上方主分類之一",
  "sub_category": "更細的子分類，例如：連衣裙、裙裝套裝、睡裙、內衣套裝",
  "tags": ["顏色", "材質", "風格", "用途"],
  "style_summary": "一句中文說明這件服飾/配件的特色與適用場景"
}}
"""
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=data, mime_type="image/png" if str(local_path).lower().endswith(".png") else ("image/webp" if str(local_path).lower().endswith(".webp") else "image/jpeg")),
                prompt,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        data = _extract_json_object(resp.text)
        if isinstance(data, dict):
            name = _clean_text_compact(name_hint or data.get("name") or "未命名服飾")
            if name in {"去人化服飾", "未命名服飾"}:
                name = _clean_text_compact(data.get("name") or name)
            main_category = _normalize_wardrobe_main_category(data.get("main_category"), fallback=None)
            if not main_category:
                main_category = _infer_wardrobe_meta_from_name(name).get("main_category", "上衣")
            sub_category = _normalize_wardrobe_sub_category(main_category, data.get("sub_category") or "")
            tags = [ _clean_text_compact(x) for x in (data.get("tags") or []) if _clean_text_compact(x) ]
            if not tags:
                tags = _wardrobe_tags_from_text(name, main_category, sub_category)
            return {
                "name": name,
                "main_category": main_category,
                "sub_category": sub_category,
                "tags": tags[:8],
                "style_summary": _clean_text_compact(data.get("style_summary") or f"{name}｜{main_category}／{sub_category}"),
            }
    except Exception as exc:
        print(f"⚠️ [WARDROBE_CLASSIFY_FAILED] {type(exc).__name__}: {exc}")
    fallback_name = _clean_text_compact(name_hint or (Path(str(local_path)).stem if local_path else "未命名服飾") or "未命名服飾")
    return {
        "name": fallback_name,
        "main_category": "配件",
        "sub_category": "未分類",
        "tags": [],
        "style_summary": fallback_name,
    }


def _is_fal_content_policy_error(exc):
    raw = str(exc or "").lower()
    return any(token in raw for token in (
        "content_policy_violation", "partner_validation_failed", "content checker",
        "safety", "moderation", "policy", "flagged"
    ))


def _is_fal_file_download_error(exc):
    raw = str(exc or "").lower()
    return any(token in raw for token in (
        "file_download_error", "failed to download the file", "check if the url is accessible",
        "body', 'image_urls", "body\", \"image_urls"
    ))


async def generate_seedream_v45_wardrobe_cleanup(reference_image_path, custom_prompt=""):
    fal_client = _get_fal_client()
    if not reference_image_path:
        raise RuntimeError("WARDROBE_CLEANUP_REFERENCE_NONE")
    image_urls = [await _seedream_upload_single_file(reference_image_path)]
    prompt = (
        "Image 1 is a clothing or accessory reference photo and may contain a human model. "
        "Remove the human completely and preserve only the clothing or accessory itself as a clean reference image. "
        "Keep the item's color, silhouette, material feel, pattern, trims, lace, straps, sleeves, hem length, buttons, and key design details. "
        "Show only the item on a simple neutral background like a clean catalog/product reference. "
        "No person, no face, no hair, no skin, no body, no mannequin, no hands, no extra props. "
        "If the item is a bag, shoes, hat, or accessory, preserve only that item cleanly."
    )
    # 注意：衣服名稱只用於衣櫃資料，不送入 Seedream prompt；避免睡衣/薄紗/內衣等命名詞觸發 partner safety。

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"👗 [SEEDREAM_WARDROBE_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            SEEDREAM_V45_MODEL_ID,
            arguments={
                "prompt": prompt,
                "image_urls": image_urls,
                "image_size": SEEDREAM_V45_IMAGE_SIZE,
                "num_images": 1,
                "max_images": 1,
                "enable_safety_checker": True,
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    result = await asyncio.to_thread(_subscribe)
    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        return f"Seedream v4.5 沒有回傳衣櫃去人化圖片：{result}"
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"]
    return f"Seedream v4.5 衣櫃去人化圖片格式異常：{result}"


async def _prepare_wardrobe_image_from_attachment(attachment, remove_person=False, extra_hint=""):
    source_path = await _download_photo_reference_attachment(attachment)
    if not source_path or not os.path.exists(source_path):
        raise RuntimeError(f"衣櫃原始圖片下載失敗：path={source_path}")

    final_path = source_path
    final_url = getattr(attachment, "url", None)

    if remove_person:
        generated_url = await generate_seedream_v45_wardrobe_cleanup(source_path, custom_prompt=extra_hint)
        if isinstance(generated_url, str) and generated_url.startswith("http"):
            local_filename = await save_to_vault(generated_url)
            if local_filename:
                final_path = os.path.join(OUTPUT_DIR, local_filename)
                final_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            else:
                # 保底：save_to_vault 若失敗，不要把 final_path 設成 None，改為自行下載。
                final_path, final_url = await _download_url_to_output(generated_url, prefix="wardrobe_clean")
        else:
            raise RuntimeError(str(generated_url))
    else:
        # 直接收藏時，轉存到 output，讓後續衣櫃瀏覽與 /photo 都可引用。
        ext = Path(source_path).suffix.lower() or ".jpg"
        filename = f"wardrobe_{datetime.now(TZ_TPE).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        target_path = os.path.join(OUTPUT_DIR, filename)
        shutil.copy2(source_path, target_path)
        final_path = target_path
        final_url = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"

    if not final_path or not os.path.exists(str(final_path)):
        raise RuntimeError(f"衣櫃整理後沒有可用圖片檔：path={final_path}")
    if os.path.getsize(str(final_path)) <= 0:
        raise RuntimeError(f"衣櫃整理後圖片檔為空：path={final_path}")

    print(f"✅ [WARDROBE_IMAGE_READY] remove_person={remove_person} path={final_path} size={os.path.getsize(str(final_path))}")
    return source_path, final_path, final_url



def _build_wardrobe_item_payload(meta, reference_path, reference_url):
    items = load_wardrobe()
    item_id = _next_wardrobe_id(items)
    return {
        "id": item_id,
        "name": meta.get("name") or item_id,
        "main_category": meta.get("main_category") or "配件",
        "sub_category": meta.get("sub_category") or "未分類",
        "tags": meta.get("tags") or [],
        "style_summary": meta.get("style_summary") or meta.get("name") or item_id,
        "reference_image_path": reference_path,
        "local_url": reference_url,
        "image_storage": "zeabur_local" if str(reference_path or "").startswith(OUTPUT_DIR) else "remote_or_external",
        "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _save_new_wardrobe_item(item):
    items = load_wardrobe()
    items.insert(0, item)
    save_wardrobe(items)
    return item


def _wardrobe_embed_for_item(item, title_prefix="👗 小俠衣櫃"):
    embed = discord.Embed(
        title=f"{title_prefix}｜{item.get('id')} {item.get('name')}",
        description=item.get("style_summary") or item.get("name") or "",
        color=0xcfa7ff,
    )
    if item.get("local_url"):
        embed.set_image(url=item.get("local_url"))
    embed.add_field(name="分類", value=f"{item.get('main_category')} / {item.get('sub_category')}", inline=False)
    embed.add_field(name="標籤", value="、".join(item.get("tags") or ["無"])[:1000], inline=False)
    embed.set_footer(text=f"建立時間：{item.get('created_at', '')}")
    return embed


WARDROBE_PAGE_SIZE = 10


def _wardrobe_filtered_items(query=""):
    items = load_wardrobe()
    return [item for item in items if _wardrobe_matches(item, query)]


def _wardrobe_total_pages(total, page_size=WARDROBE_PAGE_SIZE):
    return max(1, math.ceil(max(0, int(total)) / page_size))


def _wardrobe_item_browse_embed(item):
    tag_text = "、".join((item.get("tags") or [])[:4]) or "無"
    item_embed = discord.Embed(
        title=f"{item.get('id')}｜{item.get('name')}",
        description=(item.get("style_summary") or item.get("name") or "")[:300],
        color=0xcfa7ff,
    )
    item_embed.add_field(
        name="分類",
        value=f"{item.get('main_category')} / {item.get('sub_category')}",
        inline=True,
    )
    item_embed.add_field(name="標籤", value=tag_text[:300], inline=True)
    if item.get("local_url"):
        # 用 thumbnail 顯示成小圖；/衣櫃看 Wxxx 仍保留大圖。
        item_embed.set_thumbnail(url=item.get("local_url"))
    return item_embed


def _wardrobe_browse_payload(query="", page=0, page_size=WARDROBE_PAGE_SIZE):
    """
    /衣櫃 分頁瀏覽：每頁最多 5 件 item embeds，避免 Discord 單訊息 embeds 總字數限制造成 /衣櫃 無回應。
    Discord 對單則訊息 embeds 總字數也有限制；每頁降為 5 件，頁面標題改用 content 顯示。
    """
    matched = _wardrobe_filtered_items(query)
    total = len(matched)
    total_pages = _wardrobe_total_pages(total, page_size=page_size)
    safe_page = max(0, min(int(page or 0), total_pages - 1))
    start_idx = safe_page * page_size
    page_items = matched[start_idx:start_idx + page_size]

    counts = _wardrobe_category_counts(load_wardrobe())
    summary = "｜".join([f"{k}:{v}" for k, v in counts.items() if v]) or "目前還沒有收藏"
    title = "👗 小俠衣櫃總覽" if not query else f"👗 小俠衣櫃搜尋｜{query}"

    if total:
        range_text = f"{start_idx + 1}-{start_idx + len(page_items)}"
    else:
        range_text = "0-0"
    content = (
        f"👗 **{title}**\n"
        f"共 **{total}** 件｜第 **{safe_page + 1} / {total_pages}** 頁｜本頁 {range_text}\n"
        f"{summary}\n"
        "可用 `/衣櫃看 Wxxx` 查看大圖，或 `/衣櫃穿 Wxxx` 套用到下一張 `/photo`。"
    )
    embeds = [_wardrobe_item_browse_embed(item) for item in page_items]
    if not embeds:
        embeds = [discord.Embed(title=title, description="查無符合項目。", color=0xcfa7ff)]
    return content, embeds, safe_page, total_pages, total


def _wardrobe_browse_embeds(query="", page=0):
    """相容舊呼叫；回傳指定頁的衣服 embeds。"""
    _content, embeds, _page, _total_pages, _total = _wardrobe_browse_payload(query=query, page=page)
    return embeds


def _wardrobe_browse_embed(query=""):
    """相容舊呼叫；只回傳第一張 embed。"""
    return _wardrobe_browse_embeds(query, page=0)[0]


class WardrobeBrowseView(discord.ui.View):
    def __init__(self, query="", page=0):
        super().__init__(timeout=86400)
        self.query = str(query or "").strip()
        _matched = _wardrobe_filtered_items(self.query)
        self.total_pages = _wardrobe_total_pages(len(_matched))
        self.page = max(0, min(int(page or 0), self.total_pages - 1))
        self._sync_buttons()

    def _sync_buttons(self):
        for child in self.children:
            if getattr(child, "custom_id", "") == "wardrobe_prev":
                child.disabled = self.page <= 0
            elif getattr(child, "custom_id", "") == "wardrobe_next":
                child.disabled = self.page >= self.total_pages - 1

    async def _refresh(self, interaction):
        self._sync_buttons()
        content, embeds, self.page, self.total_pages, _total = _wardrobe_browse_payload(self.query, self.page)
        self._sync_buttons()
        await interaction.response.edit_message(content=content, embeds=embeds, view=self)

    @discord.ui.button(label="◀ 上一頁", style=discord.ButtonStyle.secondary, custom_id="wardrobe_prev")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="下一頁 ▶", style=discord.ButtonStyle.secondary, custom_id="wardrobe_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        await self._refresh(interaction)




class WardrobeApplyView(discord.ui.View):
    def __init__(self, item):
        super().__init__(timeout=86400)
        self.item = dict(item)

    @discord.ui.button(label="套用到下一張 /photo", style=discord.ButtonStyle.primary)
    async def apply_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        _set_pending_wardrobe_state(self.item)
        await interaction.response.send_message(
            f"✅ 已選定 **{self.item.get('id')} {self.item.get('name')}**。下一張 `/photo` 若沒有另外附衣服圖，就會優先套用這件。",
            ephemeral=True,
        )


def _remember_wardrobe_advice_event(question, item_summaries, reply_text="", selected_item=None):
    """
    讓「看衣櫃的小俠」與「聊天的小俠」共用同一段短期脈絡。
    /衣櫃 問小俠 是工具指令，不會自然進入一般聊天流程，所以這裡手動寫入 temp_chat。
    """
    try:
        item_text = "；".join(
            [
                f"{item.get('id')} {item.get('name')}（{item.get('main_category')}/{item.get('sub_category')}）"
                for item in (item_summaries or [])
            ]
        )
        if question:
            daily_chat_logs.append(
                _conversation_log_text(
                    "大俠",
                    f"請小俠看衣櫃並給意見：{question}。候選有：{item_text}",
                    max_chars=2000,
                )
            )
        if reply_text:
            daily_chat_logs.append(
                _conversation_log_text(
                    "小俠",
                    f"我剛剛看了衣櫃候選：{item_text}。我的穿搭意見是：{reply_text}",
                    max_chars=4000,
                )
            )
        if selected_item:
            daily_chat_logs.append(
                _conversation_log_text(
                    "小俠",
                    f"剛剛大俠從我看過的衣櫃候選中，選定下一張 /photo 要穿：{selected_item.get('id')} {selected_item.get('name')}。這是我知道並承接的當前選衣結果。",
                    max_chars=2000,
                )
            )
        save_temp_chat(daily_chat_logs)
        print("🧠 [WARDROBE_ADVICE_CONTEXT_SAVED]")
    except Exception as exc:
        print(f"⚠️ [WARDROBE_ADVICE_CONTEXT_SAVE_FAILED] {type(exc).__name__}: {exc}")


class WardrobeAdviceApplyView(discord.ui.View):
    def __init__(self, items, item_summaries=None, scene_question="", reply_text=""):
        super().__init__(timeout=86400)
        self.items = [dict(item) for item in (items or [])[:4]]
        self.item_summaries = list(item_summaries or [])
        self.scene_question = scene_question or ""
        self.reply_text = reply_text or ""
        for item in self.items:
            button = discord.ui.Button(
                label=f"套用 {item.get('id')}",
                style=discord.ButtonStyle.primary,
                custom_id=f"wardrobe_advice_apply_{item.get('id')}",
            )

            async def _callback(interaction: discord.Interaction, selected=item):
                _set_pending_wardrobe_state(selected)
                _remember_wardrobe_advice_event(
                    self.scene_question,
                    self.item_summaries,
                    self.reply_text,
                    selected_item=selected,
                )
                await interaction.response.send_message(
                    f"✅ 已選定 **{selected.get('id')} {selected.get('name')}**。下一張 `/photo` 若沒有另外附衣服圖，就會優先套用這件。",
                    ephemeral=True,
                )

            button.callback = _callback
            self.add_item(button)


def _parse_wardrobe_advice_payload(payload):
    tokens = str(payload or "").strip().split()
    item_ids = []
    rest_tokens = []
    for token in tokens:
        clean = token.strip().upper().strip("，,。；;")
        if re.fullmatch(r"W\d{3,}", clean):
            item_ids.append(clean)
        else:
            rest_tokens.append(token)
    return item_ids[:4], " ".join(rest_tokens).strip()


async def _ask_xiaoxia_about_wardrobe(ctx, payload):
    item_ids, scene_question = _parse_wardrobe_advice_payload(payload)
    if not item_ids:
        await ctx.send("大俠，請在 `問小俠` 後面放 1～4 個衣櫃編號，例如：`/衣櫃 問小俠 W001 W003 北海岸散步穿哪件？`")
        return

    items = []
    missing = []
    for item_id in item_ids:
        item = _find_wardrobe_item(item_id)
        if item:
            items.append(item)
        else:
            missing.append(item_id)

    if missing:
        await ctx.send(f"找不到這些衣櫃編號：{', '.join(missing)}")
        return
    if not items:
        await ctx.send("沒有找到可給小俠看的衣櫃項目。")
        return

    parts = []
    item_summaries = []
    for item in items[:4]:
        path_value = item.get("reference_image_path")
        if path_value and os.path.exists(path_value):
            try:
                with open(path_value, "rb") as f:
                    image_bytes = f.read()
                ext = Path(path_value).suffix.lower()
                mime = "image/png" if ext == ".png" else ("image/webp" if ext == ".webp" else "image/jpeg")
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime))
            except Exception as exc:
                print(f"⚠️ [WARDROBE_ADVICE_IMAGE_READ_FAILED] {item.get('id')} {type(exc).__name__}: {exc}")
        item_summaries.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "main_category": item.get("main_category"),
            "sub_category": item.get("sub_category"),
            "tags": item.get("tags") or [],
            "style_summary": item.get("style_summary") or "",
        })

    prompt = f"""
妳是小俠。大俠打開衣櫃，請妳臨時看幾件衣服/配件，給他穿搭意見。
這不是妳平常會自動參考的衣櫃，只有大俠這次請妳看，妳才看。

【大俠想問的場景或問題】
{scene_question or '請看這幾件，給我適合的穿搭意見。'}

【衣櫃項目資料】
{json.dumps(item_summaries, ensure_ascii=False, indent=2)}

請用小俠自然口吻回答：
1. 先說妳最推薦哪一件，明確寫出編號與名稱。
2. 簡短說原因：場景、顏色、氛圍、可愛/清爽/居家/約會感等。
3. 如果有第二選擇，也可以補一句。
4. 不要說自己是 AI，不要提模型或 token。
5. 回覆控制在 3～6 句。
"""

    msg = await ctx.send("👗 小俠正在看這幾件衣服，想一下哪件最適合...")
    try:
        parts.append(prompt)
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts,
            config=types.GenerateContentConfig(temperature=0.75),
        )
        reply = str(getattr(resp, "text", "") or "").strip()
        if not reply:
            reply = "大俠，這幾件我看到了，但我剛剛沒有想出夠清楚的建議。你可以再給我一個更明確的場景，我再幫你挑。"
        _remember_wardrobe_advice_event(scene_question, item_summaries, reply_text=reply)
        await msg.edit(content=reply, view=WardrobeAdviceApplyView(items, item_summaries=item_summaries, scene_question=scene_question, reply_text=reply))
    except Exception as exc:
        await msg.edit(content=f"⚠️ 小俠看衣櫃失敗：`{str(exc)[:1500]}`")


class WardrobeSaveModal(discord.ui.Modal):
    def __init__(self, context):
        super().__init__(title="收藏到衣櫃")
        self.context = dict(context)
        default_name = str(self.context.get("outfit_summary") or self.context.get("scene_text") or "").strip()[:80]
        self.item_name = discord.ui.TextInput(
            label="衣櫃名稱",
            placeholder="例如：白底藍花小碎花洋裝",
            default=default_name,
            max_length=80,
            required=True,
        )
        self.category_hint = discord.ui.TextInput(
            label="分類提示（可空白）",
            placeholder="例如：洋裝 / 睡衣／居家服 / 包包",
            required=False,
            max_length=60,
        )
        self.add_item(self.item_name)
        self.add_item(self.category_hint)

    async def on_submit(self, interaction: discord.Interaction):
        local_path = _photo_local_path_from_context(self.context)
        local_url = self.context.get("local_url") or self.context.get("image_url")
        if not local_path or not os.path.exists(local_path):
            await interaction.response.send_message("⚠️ 這張照片目前找不到本機檔，暫時無法收藏到衣櫃。", ephemeral=True)
            return
        meta = {
            "name": _clean_text_compact(self.item_name.value),
            "main_category": _clean_text_compact(self.category_hint.value) or "未分類",
            "sub_category": "由照片收藏",
            "tags": ["photo收藏"],
            "style_summary": _clean_text_compact(self.context.get("outfit_summary") or self.item_name.value),
        }
        if meta["main_category"] not in WARDROBE_MAIN_CATEGORIES:
            meta["main_category"] = "套裝" if "套" in meta["style_summary"] else "洋裝" if "洋裝" in meta["style_summary"] else "上衣"
        item = _build_wardrobe_item_payload(meta, local_path, local_url)
        _save_new_wardrobe_item(item)
        await interaction.response.send_message(f"✅ 已收藏到衣櫃：**{item.get('id')} {item.get('name')}**", embed=_wardrobe_embed_for_item(item), ephemeral=True)


class WardrobePendingConfirmView(discord.ui.View):
    def __init__(self, pending_payload):
        super().__init__(timeout=600)
        self.pending_payload = dict(pending_payload)

    async def _finalize(self, interaction):
        item = _build_wardrobe_item_payload(self.pending_payload["meta"], self.pending_payload["reference_path"], self.pending_payload["reference_url"])
        _save_new_wardrobe_item(item)
        await interaction.response.edit_message(content=f"✅ 已收藏到衣櫃：**{item.get('id')} {item.get('name')}**", embed=_wardrobe_embed_for_item(item), view=WardrobeApplyView(item))

    @discord.ui.button(label="確認收藏", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finalize(interaction)

    @discord.ui.button(label="重做一次", style=discord.ButtonStyle.primary)
    async def redo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.pending_payload.get("remove_person"):
            await interaction.response.send_message("這張目前是直接收藏模式，不需要重做。若要去人化，請改用 `/衣櫃 去人 名稱`。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        attachment_url = self.pending_payload.get("source_attachment_url")
        source_path = self.pending_payload.get("source_path")
        try:
            generated_url = await generate_seedream_v45_wardrobe_cleanup(source_path, custom_prompt=self.pending_payload.get("extra_hint", ""))
            if not isinstance(generated_url, str) or not generated_url.startswith("http"):
                raise RuntimeError(str(generated_url))
            local_filename = await save_to_vault(generated_url)
            local_path = os.path.join(OUTPUT_DIR, local_filename) if local_filename else None
            local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_url
            self.pending_payload["reference_path"] = local_path
            self.pending_payload["reference_url"] = local_url
            preview_embed = _wardrobe_embed_for_item({
                "id": "預覽",
                "name": self.pending_payload["meta"].get("name"),
                "main_category": self.pending_payload["meta"].get("main_category"),
                "sub_category": self.pending_payload["meta"].get("sub_category"),
                "tags": self.pending_payload["meta"].get("tags"),
                "style_summary": self.pending_payload["meta"].get("style_summary"),
                "local_url": local_url,
                "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            }, title_prefix="👗 去人化預覽")
            await interaction.edit_original_response(content="這是重做後的衣櫃預覽，要收藏嗎？", embed=preview_embed, view=self)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 重做失敗：`{str(exc)[:1200]}`", ephemeral=True)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消，沒有收藏進衣櫃。", embed=None, view=None)


async def _handle_wardrobe_add_command(ctx, args, remove_person=False):
    attachment, attachment_error = await _get_photo_reference_attachment(ctx.message)
    if attachment_error:
        await ctx.send(attachment_error)
        return
    if not attachment:
        await ctx.send("大俠，要新增到衣櫃時，請附上一張衣服、飾品或回覆含有單張圖片的訊息喔。")
        return

    name_hint = _clean_text_compact(args)
    status = await ctx.send("👗 小俠正在整理這件收藏，請稍等一下..." if not remove_person else "👗 小俠正在先幫你把人物去掉，再整理這件收藏...")

    try:
        source_url = getattr(attachment, "url", None) or getattr(attachment, "proxy_url", None)
        if not source_url:
            raise RuntimeError("WARDROBE_ATTACHMENT_URL_NONE：Discord 沒有提供可用的附件網址。")

        if not remove_person:
            # 直接新增也必須落地保存到 Zeabur，衣櫃不能只存 Discord CDN 臨時網址。
            local_filename = await save_to_vault(source_url)
            if local_filename:
                reference_path = os.path.join(OUTPUT_DIR, local_filename)
                reference_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            else:
                raise RuntimeError("WARDROBE_DIRECT_LOCAL_SAVE_FAILED：無法將 Discord 圖片轉存到 Zeabur。")

            meta = _infer_wardrobe_meta_from_name(name_hint or getattr(attachment, "filename", "") or "未命名服飾")
            pending_payload = {
                "source_path": source_url,
                "source_attachment_url": source_url,
                "reference_path": reference_path,
                "reference_url": reference_url,
                "meta": meta,
                "remove_person": False,
                "extra_hint": name_hint,
                "image_storage": "zeabur_local",
            }
            preview_item = {
                "id": "預覽",
                **meta,
                "local_url": reference_url,
                "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
            }
            await status.delete()
            await ctx.send("這是整理後的衣櫃預覽，要收藏嗎？", embed=_wardrobe_embed_for_item(preview_item, title_prefix="👗 衣櫃預覽"), view=WardrobePendingConfirmView(pending_payload))
            return

        # 去人化：名稱只作為衣櫃 display name / 分類提示，不送進 Seedream prompt，避免「薄紗、睡衣」等詞觸發安全檢查。
        generated_url = await generate_seedream_v45_wardrobe_cleanup(source_url, custom_prompt="")
        if not isinstance(generated_url, str) or not generated_url.startswith("http"):
            raise RuntimeError(str(generated_url))

        local_filename = await save_to_vault(generated_url)
        if local_filename:
            reference_path = os.path.join(OUTPUT_DIR, local_filename)
            reference_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
        else:
            reference_path = generated_url
            reference_url = generated_url

        if local_filename and os.path.exists(str(reference_path)):
            meta = await _classify_wardrobe_item_from_image(reference_path, name_hint=name_hint)
        else:
            meta = _infer_wardrobe_meta_from_name(name_hint or "未命名服飾")
        pending_payload = {
            "source_path": source_url,
            "source_attachment_url": source_url,
            "reference_path": reference_path,
            "reference_url": reference_url,
            "meta": meta,
            "remove_person": True,
            "extra_hint": name_hint,
        }
        preview_item = {
            "id": "預覽",
            **meta,
            "local_url": reference_url,
            "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        }
        await status.delete()
        await ctx.send("這是整理後的衣櫃預覽，要收藏嗎？", embed=_wardrobe_embed_for_item(preview_item, title_prefix="👗 衣櫃預覽"), view=WardrobePendingConfirmView(pending_payload))
    except Exception as exc:
        print(f"⚠️ [WARDROBE_ADD_FAILED] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        err_text = str(exc)
        if "WARDROBE_CLEANUP_CONTENT_POLICY" in err_text:
            await status.edit(
                content=(
                    "⚠️ 這張圖被 fal.ai / Seedream 的安全檢查擋下，沒辦法自動「去人」。\n"
                    "這通常不是指令格式錯，而是原圖人物、膚色面積、睡衣/內衣類或姿態被判定太敏感。\n\n"
                    "可改用：\n"
                    "1. 換一張更像商品平鋪照、露膚較少的圖再 `/衣櫃 去人 名稱`。\n"
                    "2. 或先用 `/衣櫃 新增 名稱` 直接收藏原圖。"
                )
            )
        else:
            await status.edit(content=f"⚠️ 衣櫃整理失敗：`{err_text[:1500]}`")



async def _handle_wardrobe_replace_image_command(ctx, args, remove_person=False):
    """
    只替換指定衣櫃項目的圖片欄位，不改 id/name/category/tags/style_summary。
    用法：
    /衣櫃 換圖 W001        （直接用附圖/回覆圖）
    /衣櫃 換圖去人 W001    （先用 Seedream 去人，再替換 W001 圖）
    """
    raw = str(args or "").strip()
    item_id, _, _rest = raw.partition(" ")
    item_id = item_id.strip().upper()

    if not item_id:
        await ctx.send(
            "大俠，要指定要換哪一件喔。\n"
            "用法：`/衣櫃 換圖 W001`，或需要先去人就用 `/衣櫃 換圖去人 W001`。"
        )
        return

    items = load_wardrobe()
    target_index = None
    for idx, item in enumerate(items):
        if str(item.get("id", "")).upper() == item_id:
            target_index = idx
            break

    if target_index is None:
        await ctx.send(f"找不到衣櫃項目 **{item_id}**。請先 `/衣櫃` 看看目前有哪些收藏。")
        return

    attachment, attachment_error = await _get_photo_reference_attachment(ctx.message)
    if attachment_error:
        await ctx.send(attachment_error)
        return
    if not attachment:
        await ctx.send(
            "大俠，要換圖時請附上一張新圖片，或回覆含有單張圖片的訊息再打指令。\n"
            f"例如：`/衣櫃 換圖 {item_id}` 或 `/衣櫃 換圖去人 {item_id}`。"
        )
        return

    target = dict(items[target_index])
    old_local_url = target.get("local_url")
    old_reference_path = target.get("reference_image_path")
    status = await ctx.send(
        f"👗 小俠正在替 **{item_id} {target.get('name', '')}** 換圖..."
        if not remove_person else
        f"👗 小俠正在先幫新圖去人，再替 **{item_id} {target.get('name', '')}** 換圖..."
    )

    try:
        source_url = getattr(attachment, "url", None) or getattr(attachment, "proxy_url", None)
        if not source_url:
            raise RuntimeError("WARDROBE_REPLACE_ATTACHMENT_URL_NONE：Discord 沒有提供可用的附件網址。")

        if remove_person:
            try:
                generated_url = await generate_seedream_v45_wardrobe_cleanup(source_url, custom_prompt="")
            except Exception as exc:
                if _is_fal_content_policy_error(exc):
                    await status.edit(
                        content=(
                            "⚠️ 這張新圖被 fal.ai / Seedream 的安全檢查擋下，沒辦法自動去人換圖。\n"
                            "可改用較像商品平鋪照、露膚較少的圖片再試，或直接用 `/衣櫃 換圖 "
                            f"{item_id}` 保留原圖替換。"
                        )
                    )
                    return
                raise

            if not isinstance(generated_url, str) or not generated_url.startswith("http"):
                raise RuntimeError(str(generated_url))

            local_filename = await save_to_vault(generated_url)
            if local_filename:
                reference_path = os.path.join(OUTPUT_DIR, local_filename)
                reference_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            else:
                reference_path = generated_url
                reference_url = generated_url
            replace_mode = "去人後換圖"
        else:
            local_filename = await save_to_vault(source_url)
            if local_filename:
                reference_path = os.path.join(OUTPUT_DIR, local_filename)
                reference_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            else:
                raise RuntimeError("WARDROBE_REPLACE_LOCAL_SAVE_FAILED：無法將新圖片轉存到 Zeabur。")
            replace_mode = "直接換圖並轉存"

        items[target_index]["reference_image_path"] = reference_path
        items[target_index]["local_url"] = reference_url
        items[target_index]["source_attachment_url"] = source_url
        items[target_index]["image_replaced_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
        items[target_index]["updated_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
        items[target_index]["image_replace_mode"] = replace_mode
        items[target_index]["image_storage"] = "zeabur_local"
        if old_local_url:
            items[target_index]["previous_local_url"] = old_local_url
        if old_reference_path:
            items[target_index]["previous_reference_image_path"] = old_reference_path

        save_wardrobe(items)
        updated = items[target_index]
        _sync_pending_wardrobe_if_same_item(updated)
        await status.edit(
            content=f"✅ 已替 **{updated.get('id')} {updated.get('name')}** 更新圖片（{replace_mode}）。",
            embed=_wardrobe_embed_for_item(updated),
            view=WardrobeApplyView(updated),
        )

    except Exception as exc:
        print(f"⚠️ [WARDROBE_REPLACE_IMAGE_FAILED] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        await status.edit(content=f"⚠️ 換圖失敗：`{str(exc)[:1500]}`")



# ==========================================
# 📸 Seedream v4.5 /photo 統一照片工作台
# ==========================================
def _is_girlfriend_xiaoxia_channel(channel) -> bool:
    """女友小俠可互動頻道；排除說故事小俠姊姊與公開服務頻道。"""
    if is_story_channel_or_thread(channel) or is_public_service_channel(channel):
        return False
    if channel is None:
        return False
    channel_name = getattr(channel, "name", "") or ""
    girlfriend_names = set(PRIVATE_UPLOAD_CHANNEL_NAMES) | set(PRIVATE_NOTE_CHANNEL_NAMES) | {"書房"}
    return (
        getattr(getattr(channel, "guild", None), "id", None) == PRIVATE_GUILD_ID
        and (
            getattr(channel, "id", None) in PRIVATE_UPLOAD_CHANNEL_IDS
            or getattr(channel, "id", None) in PRIVATE_NOTE_CHANNEL_IDS
            or any(name in channel_name for name in girlfriend_names)
        )
    )


def _supported_photo_attachment(attachment) -> bool:
    content_type = (getattr(attachment, "content_type", "") or "").lower()
    filename = (getattr(attachment, "filename", "") or "").lower()
    return (
        content_type in {"image/png", "image/jpeg", "image/jpg", "image/webp"}
        or filename.endswith((".png", ".jpg", ".jpeg", ".webp"))
    )


async def _get_photo_reference_attachment(message):
    """回傳 (attachment, error_message)。先看本訊息，再看 reply 訊息。"""
    attachments = [a for a in list(getattr(message, "attachments", []) or []) if _supported_photo_attachment(a)]
    raw_attachments = list(getattr(message, "attachments", []) or [])
    if len(raw_attachments) > 1:
        return None, "大俠，這次先讓我一次只看一張衣服或一張飾品圖片，好嗎？\n你先選一張給我，我就幫你拍一張看看。"
    if len(raw_attachments) == 1 and not attachments:
        return None, "大俠，這個檔案我沒辦法當作參考圖耶。\n你給我一張 PNG、JPG 或 WebP 圖片就可以了。"
    if attachments:
        return attachments[0], None

    ref = getattr(message, "reference", None)
    if ref:
        ref_msg = getattr(ref, "resolved", None)
        if ref_msg is None and getattr(ref, "message_id", None):
            try:
                ref_msg = await message.channel.fetch_message(ref.message_id)
            except Exception as exc:
                print(f"⚠️ [PHOTO_REPLY_FETCH_FAILED] {type(exc).__name__}: {exc}")
                ref_msg = None
        if ref_msg:
            ref_raw = list(getattr(ref_msg, "attachments", []) or [])
            ref_images = [a for a in ref_raw if _supported_photo_attachment(a)]
            if len(ref_raw) > 1:
                return None, "大俠，被回覆的訊息裡有多張圖片；第一版 /photo 先一次只支援一張參考圖。"
            if len(ref_raw) == 1 and not ref_images:
                return None, "大俠，被回覆的附件不是我能使用的圖片格式。請給我 PNG、JPG 或 WebP。"
            if ref_images:
                return ref_images[0], None
    return None, None


async def _download_photo_reference_attachment(attachment):
    """
    Discord 附圖保底下載。
    不再優先用 attachment.read()；改用 attachment.url / proxy_url 下載，
    避免某些手機端或編輯附件情境下 read() 取不到內容或內部拋 NoneType path。
    """
    os.makedirs(PHOTO_USER_REF_DIR, exist_ok=True)
    if attachment is None:
        raise RuntimeError("PHOTO_REF_ATTACHMENT_NONE：沒有取得可下載的圖片附件。")

    filename_raw = str(getattr(attachment, "filename", "") or "")
    content_type = str(getattr(attachment, "content_type", "") or "").lower()
    ext = Path(filename_raw).suffix.lower() if filename_raw else ""
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".png" if "png" in content_type else (".webp" if "webp" in content_type else ".jpg")

    filename = f"photo_ref_{datetime.now(TZ_TPE).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    path = os.path.join(PHOTO_USER_REF_DIR, filename)

    url_candidates = [
        getattr(attachment, "url", None),
        getattr(attachment, "proxy_url", None),
    ]
    data = None
    last_error = None

    for url in [u for u in url_candidates if u]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if data:
                            break
                    last_error = f"HTTP {resp.status} from {url}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    if not data:
        # 最後才退回 attachment.read()
        try:
            data = await attachment.read()
        except Exception as exc:
            last_error = f"attachment.read failed: {type(exc).__name__}: {exc}"

    if not data:
        raise RuntimeError(f"PHOTO_REF_DOWNLOAD_EMPTY：圖片附件下載後沒有內容。last_error={last_error}")

    with open(path, "wb") as f:
        f.write(data)

    if not os.path.exists(path) or os.path.getsize(path) <= 0:
        raise RuntimeError(f"PHOTO_REF_SAVE_FAILED：圖片附件保存失敗 path={path}")

    print(f"✅ [PHOTO_REF_ATTACHMENT_SAVED] path={path} size={os.path.getsize(path)} filename={filename_raw} content_type={content_type}")
    return path


async def _download_url_to_output(image_url, prefix="wardrobe"):
    """把外部圖片 URL 下載到 OUTPUT_DIR，避免 save_to_vault 失敗時拿到 None path。"""
    if not image_url or not str(image_url).startswith("http"):
        return None, None
    ext = ".jpg"
    clean = str(image_url).split("?", 1)[0].split("#", 1)[0].lower()
    for candidate in (".png", ".jpg", ".jpeg", ".webp"):
        if clean.endswith(candidate):
            ext = candidate
            break
    filename = f"{prefix}_{datetime.now(TZ_TPE).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    path = os.path.join(OUTPUT_DIR, filename)
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"下載圖片失敗 HTTP {resp.status}")
            data = await resp.read()
    if not data:
        raise RuntimeError("下載圖片後沒有內容。")
    with open(path, "wb") as f:
        f.write(data)
    return path, f"https://xiaoxia0320.zeabur.app/gallery/{filename}"


async def _seedream_download_remote_reference(url):
    if not url or not str(url).startswith("http"):
        raise RuntimeError(f"SEEDREAM_REMOTE_REFERENCE_INVALID_URL：{url}")
    raw_url = str(url)
    cleaned_url = raw_url.split("?", 1)[0]
    suffix = Path(cleaned_url).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    digest = hashlib.md5(raw_url.encode("utf-8")).hexdigest()
    local_path = os.path.join(SEEDREAM_V45_REMOTE_CACHE_DIR, f"{digest}{suffix}")
    timeout = aiohttp.ClientTimeout(total=60)
    headers = {
        "User-Agent": "Mozilla/5.0 XiaoxiaBot/1.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(raw_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"SEEDREAM_REMOTE_REFERENCE_DOWNLOAD_FAILED：HTTP {resp.status} url={raw_url}")
            data = await resp.read()
    if not data:
        raise RuntimeError(f"SEEDREAM_REMOTE_REFERENCE_EMPTY：{raw_url}")
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path


def _gallery_url_to_local_path(url):
    value = str(url or "").strip()
    if not value:
        return None
    # 目前 gallery route 對應 OUTPUT_DIR 內檔案。
    if "/gallery/" in value:
        filename = value.split("/gallery/", 1)[-1].split("?", 1)[0].split("#", 1)[0].strip()
        if filename:
            return os.path.join(OUTPUT_DIR, os.path.basename(filename))
    return None


def _wardrobe_local_reference_ok(item):
    ref = str((item or {}).get("reference_image_path") or "").strip()
    if ref and not ref.startswith("http") and os.path.exists(ref):
        return True
    local_url = str((item or {}).get("local_url") or "").strip()
    candidate = _gallery_url_to_local_path(local_url)
    return bool(candidate and os.path.exists(candidate))


def _wardrobe_reference_candidates(item):
    candidates = []
    for key in ("reference_image_path", "local_url", "reference_url", "source_attachment_url", "source_path"):
        value = str((item or {}).get(key) or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


async def _wardrobe_url_reachable(url):
    value = str(url or "").strip()
    if not value.startswith("http"):
        return False, "not_http"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {"User-Agent": "Mozilla/5.0 XiaoxiaBot/1.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(value) as resp:
                if resp.status == 200:
                    # 不用整包讀完；讀一小段確認有資料即可。
                    chunk = await resp.content.read(64)
                    return bool(chunk), "ok" if chunk else "empty"
                return False, f"HTTP {resp.status}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def _localize_wardrobe_item_image(item):
    """
    將衣櫃項目的圖片轉存到 Zeabur /data/output。
    成功回傳 (True, updated_item, reason)，失敗回傳 (False, original_item, reason)。
    """
    if not isinstance(item, dict):
        return False, item, "invalid item"

    updated = dict(item)
    wid = str(updated.get("id") or "").strip()

    # 1. reference_image_path 已是本地檔
    ref = str(updated.get("reference_image_path") or "").strip()
    if ref and not ref.startswith("http") and os.path.exists(ref):
        filename = os.path.basename(ref)
        updated["reference_image_path"] = ref
        updated["local_url"] = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        updated["image_storage"] = "zeabur_local"
        return True, updated, "local file exists"

    # 2. local_url 是 Zeabur gallery 且本地檔存在
    local_path = _gallery_url_to_local_path(updated.get("local_url"))
    if local_path and os.path.exists(local_path):
        filename = os.path.basename(local_path)
        updated["reference_image_path"] = local_path
        updated["local_url"] = f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        updated["image_storage"] = "zeabur_local"
        return True, updated, "gallery file exists"

    # 3. 嘗試從任何 URL 候選下載轉存
    last_reason = "no usable image candidate"
    for candidate in _wardrobe_reference_candidates(updated):
        if not str(candidate).startswith("http"):
            continue
        local_filename = await save_to_vault(candidate)
        if local_filename:
            local_ref = os.path.join(OUTPUT_DIR, local_filename)
            updated["reference_image_path"] = local_ref
            updated["local_url"] = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}"
            updated["image_storage"] = "zeabur_localized_from_remote"
            updated["image_localized_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            updated["updated_at"] = datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")
            return True, updated, f"downloaded from {candidate[:80]}"
        ok, reason = await _wardrobe_url_reachable(candidate)
        last_reason = reason

    return False, updated, last_reason


async def _handle_wardrobe_healthcheck(ctx):
    items = load_wardrobe()
    if not items:
        await ctx.send("衣櫃目前是空的，或 `xiaoxia_wardrobe.json` 格式不是 list。")
        return

    local_ok, remote_ok, broken, unknown = [], [], [], []
    status = await ctx.send(f"🩺 小俠正在幫衣櫃做圖片健檢，共 {len(items)} 件...")

    for item in items:
        wid = str(item.get("id") or "?")
        if _wardrobe_local_reference_ok(item):
            local_ok.append(wid)
            continue

        reachable = False
        last_reason = "no candidate"
        for candidate in _wardrobe_reference_candidates(item):
            if str(candidate).startswith("http"):
                ok, reason = await _wardrobe_url_reachable(candidate)
                last_reason = reason
                if ok:
                    reachable = True
                    break
        if reachable:
            remote_ok.append(wid)
        elif last_reason and ("HTTP 404" in last_reason or "404" in last_reason):
            broken.append(wid)
        else:
            unknown.append(f"{wid}({last_reason})")

    def _fmt(seq, maxn=25):
        if not seq:
            return "無"
        short = seq[:maxn]
        more = f" ...等 {len(seq)} 件" if len(seq) > maxn else ""
        return ", ".join(short) + more

    msg = (
        f"🩺 **衣櫃圖片健檢完成**\\n"
        f"✅ 已本地化可用：{len(local_ok)} 件\\n"
        f"🟡 遠端仍抓得到、可修復：{len(remote_ok)} 件\\n"
        f"❌ 遠端已失效/404：{len(broken)} 件\\n"
        f"⚠️ 其他不明狀態：{len(unknown)} 件\\n\\n"
        f"🟡 可自動修復：{_fmt(remote_ok)}\\n"
        f"❌ 需重補圖：{_fmt(broken)}"
    )
    await status.edit(content=msg[:1900])


async def _handle_wardrobe_repair_images(ctx):
    items = load_wardrobe()
    if not items:
        await ctx.send("衣櫃目前是空的，或 `xiaoxia_wardrobe.json` 格式不是 list。")
        return

    status = await ctx.send(f"🛠️ 小俠正在把衣櫃圖片轉存到 Zeabur，本次會盡量補救 {len(items)} 件...")
    repaired, already_ok, failed = [], [], []
    new_items = []

    for item in items:
        wid = str(item.get("id") or "?")
        was_local = _wardrobe_local_reference_ok(item)
        ok, updated, reason = await _localize_wardrobe_item_image(item)
        new_items.append(updated if ok else item)

        if ok and was_local:
            already_ok.append(wid)
        elif ok:
            repaired.append(wid)
        else:
            failed.append(f"{wid}({reason})")

    save_wardrobe(new_items)

    def _fmt(seq, maxn=25):
        if not seq:
            return "無"
        short = seq[:maxn]
        more = f" ...等 {len(seq)} 件" if len(seq) > maxn else ""
        return ", ".join(short) + more

    msg = (
        f"🛠️ **衣櫃圖片修復完成**\\n"
        f"✅ 原本就可用：{len(already_ok)} 件\\n"
        f"✅ 本次成功轉存：{len(repaired)} 件\\n"
        f"❌ 仍需重補圖：{len(failed)} 件\\n\\n"
        f"成功轉存：{_fmt(repaired)}\\n"
        f"需重補圖：{_fmt(failed, maxn=18)}"
    )
    await status.edit(content=msg[:1900])


async def _seedream_upload_single_file(path):
    if not path:
        raise RuntimeError("SEEDREAM_UPLOAD_PATH_NONE：要上傳給 Seedream 的圖片路徑是 None。")
    upload_path = str(path)
    if upload_path.startswith("http"):
        upload_path = await _seedream_download_remote_reference(upload_path)
    elif not os.path.exists(upload_path):
        raise RuntimeError(f"SEEDREAM_UPLOAD_PATH_MISSING：找不到要上傳給 Seedream 的圖片：{path}")
    fal_client = _get_fal_client()
    return await asyncio.to_thread(fal_client.upload_file, upload_path)


def _seedream_photo_prompt(custom_prompt, has_reference=False, current_outfit=None):
    base = (
        "Use Images 1-9 as reference sheets for the same adult fictional character, Xiaoxia. "
        "Preserve her recognizable sweet East Asian facial identity, fair skin, tall slim figure, defined waist, naturally full bust proportion, gentle youthful-adult aura, and natural body proportions from the references. "
        "Create a new solo photorealistic boyfriend-POV lifestyle photo. Do not copy any one reference pose or background exactly. "
        + SOLO_SCENE_REWRITE_GUARD.strip() + " "
        "Only Xiaoxia may appear. No man, no male head, no male face, no male hair, no male hands, no male arms, no male shoulder, no male back, no male torso, no other people, no reflections of other people. "
        "Do not show Daxia, the camera holder, or any visible body part of the viewer. No blurred male foreground figure, no cropped male body parts, no male head, no male face, no male hair, no male shoulder, no male back, no male torso, no male silhouette, no male reflection, and no foreground viewer hand/arm/shoulder. The boyfriend POV must be implied only through framing, Xiaoxia's gaze, and composition, never by showing another person. "
        "Keep anatomy natural, hands plausible, full body or half body as appropriate, fully clothed, tasteful, non-explicit. Xiaoxia's pose and limb positions must be anatomically normal and natural, with no extra limbs, twisted joints, broken fingers, or awkward body mechanics. "
        "Keep Xiaoxia's everyday identity recognizable: maintain natural brown-family hair color, but allow a scene-appropriate hairstyle variation such as loose waves, ponytail, low ponytail, princess half-up, relaxed tied hair, or a simple updo. Do not drift into a short-haired look, a random fantasy wig, or an unnatural hair color unless the request explicitly calls for it. "
    )
    if has_reference:
        base += (
            "Image 10 is a clothing or accessory reference provided by Daxia or selected from Xiaoxia's wardrobe. "
            "If Image 10 is clothing, make Xiaoxia wear it naturally. "
            "If Image 10 is an accessory, make Xiaoxia naturally carry, wear, or style it in a clearly visible way. "
            "Preserve the reference item's overall color, silhouette, material feeling, pattern, and key decorative details as much as possible, while keeping Xiaoxia's identity consistent. "
            "The visual reference image must dominate ambiguous text labels. Do not reinterpret a matching set as a blazer, jacket, formal suit, long-sleeve set, or ordinary outerwear unless Image 10 clearly shows that. If Image 10 shows underwear, lingerie, swimwear, or sleepwear, keep that exact garment category and style it tastefully in an appropriate private or contextual scene. "
        )
    else:
        base += (
            "No external clothing reference is provided; infer a natural outfit from the scene and the latest explicit outfit description in the request. "
            "The outfit should fit the scene and feel like a candid daily-life moment, not a fashion advertisement. "
        )
    if current_outfit:
        base += (
            f" Today's continuity outfit is: {str(current_outfit).strip()}. "
            "If the request does not explicitly change the outfit, keep this same outfit continuity. "
        )
    return base + "\n\nPHOTO REQUEST:\n" + str(custom_prompt or "").strip()


async def generate_seedream_v45_photo(custom_prompt, reference_image_path=None, enable_safety_checker=True, current_outfit=None):
    """Seedream v4.5 統一 /photo：無參考圖=情境照；有參考圖=換裝/飾品融合。"""
    fal_client = _get_fal_client()
    final_prompt = _seedream_photo_prompt(custom_prompt, has_reference=bool(reference_image_path), current_outfit=current_outfit)

    async def _build_image_urls(force_reference_refresh=False):
        urls = await _seedream_upload_reference_images(force_refresh=force_reference_refresh)
        if reference_image_path:
            # 不直接把外部 URL 丟給 Seedream；先由本機下載後再上傳到 fal，避免 Discord CDN / 外部圖床過期。
            urls.append(await _seedream_upload_single_file(reference_image_path))
        return urls[-10:] if len(urls) > 10 else urls

    def _subscribe(image_urls):
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"📸 [SEEDREAM_PHOTO_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            SEEDREAM_V45_MODEL_ID,
            arguments={
                "prompt": final_prompt,
                "image_urls": image_urls,
                "image_size": SEEDREAM_V45_IMAGE_SIZE,
                "num_images": 1,
                "max_images": 1,
                "enable_safety_checker": bool(enable_safety_checker),
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    image_urls = await _build_image_urls(force_reference_refresh=False)
    try:
        result = await asyncio.to_thread(_subscribe, image_urls)
    except Exception as exc:
        if _is_fal_file_download_error(exc):
            print(f"⚠️ [SEEDREAM_PHOTO_FILE_DOWNLOAD_ERROR] refresh reference uploads and retry once: {exc}")
            image_urls = await _build_image_urls(force_reference_refresh=True)
            try:
                result = await asyncio.to_thread(_subscribe, image_urls)
            except Exception as retry_exc:
                if _is_fal_file_download_error(retry_exc) and reference_image_path and str(reference_image_path).startswith("http"):
                    raise RuntimeError(
                        "SEEDREAM_PHOTO_REFERENCE_URL_EXPIRED：Seedream 無法下載其中一張輸入圖。"
                        "我已重新上傳小俠 1-9 號人物底稿並重試一次，仍失敗。"
                        "最可能是衣櫃圖片或附件的外部 URL 已過期或無法被 fal.ai 讀取。"
                        "請用 `/衣櫃 換圖 Wxxx` 或 `/衣櫃 換圖去人 Wxxx` 把該衣櫃項目換成新的可用圖片後再試。"
                    ) from retry_exc
                raise
        else:
            raise

    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        return f"Seedream v4.5 沒有回傳 /photo 圖片：{result}"
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"]
    return f"Seedream v4.5 /photo 圖片欄位格式異常：{result}"

def _seedream_repair_prompt(custom_prompt):
    return (
        "Use Images 1-9 as identity reference sheets for Xiaoxia. Image 10 is the exact generated photo that needs correction. "
        "Preserve Image 10's overall composition, camera angle, framing, Xiaoxia's face identity, hairstyle, outfit, lighting, background, mood, and atmosphere as much as possible. Preserve her fair skin, tall slim figure, defined waist, and naturally full bust proportion; do not drift into a shorter, heavier, flatter, or different-looking woman. "
        "Do not redesign the image, do not change Xiaoxia into another person, and do not change the outfit unless explicitly requested. "
        "Apply only the correction requested by Daxia. "
        "Strictly only Xiaoxia appears in the image. Xiaoxia is the only human figure. No man, no male head, no male face, no male hair, no male hands, no male arms, no male shoulder, no male back, no blurred male foreground figure, no cropped male body parts, no other people. "
        "If correcting anatomy, keep exactly two arms and two hands only, connected naturally to the correct wrists and arms. No duplicate hands, no extra limbs, no malformed fingers. "
        "\n\nDAIXA REPAIR REQUEST:\n"
        + str(custom_prompt or "").strip()
    )


async def generate_seedream_v45_repair(original_image_path, repair_request, enable_safety_checker=True):
    """Seedream v4.5 修正版：Image 10 是要修的原圖，只改指定瑕疵，保留構圖與氛圍。"""
    if not original_image_path:
        raise RuntimeError("REPAIR_IMAGE_PATH_NONE：沒有可修正的原圖。")
    fal_client = _get_fal_client()
    image_urls = await _seedream_upload_reference_images()
    image_urls.append(await _seedream_upload_single_file(original_image_path))
    image_urls = image_urls[-10:] if len(image_urls) > 10 else image_urls
    final_prompt = _seedream_repair_prompt(repair_request)

    def _subscribe():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🩹 [SEEDREAM_REPAIR_QUEUE] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(
            SEEDREAM_V45_MODEL_ID,
            arguments={
                "prompt": final_prompt,
                "image_urls": image_urls,
                "image_size": SEEDREAM_V45_IMAGE_SIZE,
                "num_images": 1,
                "max_images": 1,
                "enable_safety_checker": bool(enable_safety_checker),
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    result = await asyncio.to_thread(_subscribe)
    images = result.get("images") if isinstance(result, dict) else None
    if not images:
        return f"Seedream v4.5 修圖沒有回傳圖片：{result}"
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"]
    return f"Seedream v4.5 修圖圖片欄位格式異常：{result}"


async def _ensure_context_local_path(context):
    local_path = str(context.get("local_path") or "").strip()
    if local_path and os.path.exists(local_path):
        return local_path
    local_filename = str(context.get("local_filename") or "").strip()
    if local_filename:
        candidate = os.path.join(OUTPUT_DIR, os.path.basename(local_filename))
        if os.path.exists(candidate):
            return candidate
    image_url = context.get("local_url") or context.get("image_url")
    if not image_url:
        raise RuntimeError("這張照片沒有可修正的圖片 URL。")
    downloaded_path, _downloaded_url = await _download_url_to_output(image_url, prefix="repair_src")
    return downloaded_path


async def _repair_photo_context(context, repair_request, msg=None):
    source_path = await _ensure_context_local_path(context)
    if msg:
        await msg.edit(content="🩹 小俠正在保留原本構圖與氛圍，只修大俠指定的地方…")
    generated_image_url = await generate_seedream_v45_repair(source_path, repair_request, enable_safety_checker=True)
    if not generated_image_url or not str(generated_image_url).startswith("http"):
        raise RuntimeError(f"修圖失敗：{generated_image_url}")

    local_filename = await save_to_vault(generated_image_url)
    local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
    local_path = os.path.join(OUTPUT_DIR, local_filename) if local_filename else None

    repaired = dict(context)
    repaired.update({
        "id": str(uuid.uuid4()),
        "image_url": generated_image_url,
        "local_url": local_url,
        "local_filename": local_filename,
        "local_path": local_path,
        "repair_request": str(repair_request or "").strip(),
        "repaired_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "composition": context.get("composition") or context.get("scene_summary") or "修正版照片",
        "mood_summary": context.get("mood_summary") or context.get("mood") or "保留原本氛圍的修正版",
        "message": context.get("message") or "大俠，這張是我照著你的修正要求整理過的版本。",
        "source_mode": context.get("source_mode", context.get("type", "photo_repair")),
        "type": context.get("type", context.get("source_mode", "photo")),
    })
    return repaired



async def _summarize_scene_for_photo(raw_scene_text, source_mode, has_reference, current_outfit=None, keep_today_outfit=False, pending_wardrobe_name=""):
    """將指定文字或最近 20 句對話整理成 /photo 可用的結構化場景。"""
    recent_context = "\n".join(daily_chat_logs[-20:])
    default_scene = "溫馨自然的家中居家場景" if has_reference else "依照最近對話中的當下生活情境"
    prompt = f"""
你是小俠照片導演。請根據大俠的 /photo 指令與最近對話，整理一張小俠照片的生成需求。

【/photo 模式】：{source_mode}
【大俠指定內容】：{raw_scene_text or '無'}
【最近 20 則對話】：
{recent_context or '無'}
【今日既有衣著連貫】：{current_outfit or '無'}
【是否優先延續今日衣著】：{'是' if keep_today_outfit else '否'}
【若有預選衣櫃項目】：{pending_wardrobe_name or '無'}

請只回傳 JSON：
{{
  "scene_summary": "照片場景，若大俠有指定內容則優先；若無且也無明確對話，使用 {default_scene}",
  "outfit_summary": "最近一則明確服裝描述；若要延續今日衣著，就直接延續目前衣著；若有參考圖則描述該衣服/飾品",
  "action_summary": "小俠正在做的自然動作",
  "mood_summary": "氣氛與光線",
  "camera_framing": "half_body 或 full_body",
  "photo_prompt": "英文 Seedream 提示詞，需包含場景、服裝、動作、光線；必須改寫成小俠一人的單人鏡頭，嚴格單人小俠，不出現男人、第二人、伴侶、其他人、任何男性身體部位、鏡頭持有者的手／肩／背影、外來手、倒影或影子；動作與肢體必須自然正常；完整衣著、生活感、非露骨"
}}

規則：
0. 若大俠指定的是浪漫、床邊、燭光、等待、撩人、情侶感、男友視角等情境，必須把它改寫為「小俠單人對鏡頭或單人生活動作」；不得把大俠、男友、伴侶或第二人畫面化。
1. 若大俠指定內容不為無，scene_summary 必須以指定內容為主。
2. 若「是否優先延續今日衣著」為是，且沒有新的衣服參考圖，outfit_summary 必須延續今日既有衣著，不要自行換裝。
3. 若有參考圖，photo_prompt 要說明 Image 10 是衣服或飾品參考；若有預選衣櫃項目，也等同新衣服參考。
4. 不要從很久以前的日記或長期記憶抓衣服。
5. 不可加入大俠沒有要求的第二人物。
6. 即使是男友視角，也不可畫出大俠本人、任何男性、任何男性肢體，或鏡頭前景中的手、肩、背影；只能用構圖暗示 POV。
7. 小俠的動作、手勢、四肢、關節、手指都必須自然正常，不可出現不合理姿勢。
"""
    try:
        resp = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        data = _extract_json_object(resp.text)
        if isinstance(data, dict) and data.get("photo_prompt"):
            return data
    except Exception as exc:
        print(f"⚠️ [PHOTO_SCENE_SUMMARY_FAILED] {type(exc).__name__}: {exc}")

    fallback_scene = raw_scene_text.strip() if raw_scene_text else default_scene
    fallback_outfit = current_outfit if (keep_today_outfit and current_outfit) else "自然、完整、安全且符合場景的日常穿搭"
    return {
        "scene_summary": fallback_scene,
        "outfit_summary": fallback_outfit,
        "action_summary": "小俠自然地待在場景中，像被大俠拍下的生活片刻",
        "mood_summary": "溫暖自然光、生活感、真實照片氛圍",
        "camera_framing": "half_body",
        "photo_prompt": (
            f"A candid photorealistic boyfriend-POV lifestyle photo of Xiaoxia in {fallback_scene}. "
            f"She is wearing {fallback_outfit}, with a warm everyday mood. "
            "Solo Xiaoxia only. Do not show any man, any other person, or any visible body part of the viewer, including foreground hands, shoulders, back, torso, silhouette, or reflections. The POV should be implied only through framing. Realistic anatomy only, with natural body movement, natural limb positions, and no awkward pose or malformed hands."
        ),
    }


def _photo_visual_dict(scene_data, source_mode, reference_item_path=None, reference_item_url=None):
    scene_summary = str(scene_data.get("scene_summary", "小俠的生活照片")).strip()
    outfit_summary = str(scene_data.get("outfit_summary", "自然日常穿搭")).strip()
    action_summary = str(scene_data.get("action_summary", "自然生活動作")).strip()
    mood_summary = str(scene_data.get("mood_summary", "溫暖生活感")).strip()
    return {
        "composition": scene_summary,
        "mood": mood_summary,
        "message": f"大俠按下 /photo 留住這一刻。{action_summary}",
        "source_mode": source_mode,
        "reference_item_path": reference_item_path,
        "reference_item_url": reference_item_url,
        "__anchor_state": {
            "activity": action_summary,
            "primary_action": action_summary,
            "micro_action": "a natural small gesture fitting the scene",
            "gaze_target": "Daxia's camera or the task in front of her",
            "camera_awareness": "briefly_noticing",
            "environment_trace": scene_summary,
            "outfit_intent": outfit_summary,
            "lighting_mood": mood_summary,
            "setting_anchor": scene_summary,
            "time_anchor": "",
            "camera_framing": scene_data.get("camera_framing", "half_body"),
            "scenario_tw": scene_summary,
        },
    }


def _photo_db_payload(context, name=None, type_override="photo"):
    title = name or context.get("photo_name") or context.get("scene_text") or "小俠照片"
    return {
        "id": str(uuid.uuid4()),
        "publish_date": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "topic": f"【Photo】{title}",
        "event": "大俠使用 /photo 主動生成的小俠照片",
        "composition": context.get("scene_summary", ""),
        "mood": context.get("mood_summary", ""),
        "message": context.get("message", ""),
        "image_url": context.get("image_url", ""),
        "local_url": context.get("local_url", context.get("image_url", "")),
        "type": type_override,
        "source_mode": context.get("source_mode", "photo_scene"),
        "reference_item_path": context.get("reference_item_path"),
        "reference_item_url": context.get("reference_item_url"),
    }


def _photo_local_path_from_context(context):
    """把 /photo 的 gallery URL 反查成本機檔案，供 Discord attachment 顯示用。"""
    local_path = str((context or {}).get("local_path") or "").strip()
    if local_path and os.path.exists(local_path):
        return local_path

    local_filename = str((context or {}).get("local_filename") or "").strip()
    if local_filename:
        candidate = os.path.abspath(os.path.join(OUTPUT_DIR, os.path.basename(local_filename)))
        if os.path.exists(candidate):
            return candidate

    for key in ("local_url", "image_url"):
        url = str((context or {}).get(key) or "")
        marker = "/gallery/"
        if marker in url:
            filename = os.path.basename(url.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0])
            if filename:
                candidate = os.path.abspath(os.path.join(OUTPUT_DIR, filename))
                output_root = os.path.abspath(OUTPUT_DIR) + os.sep
                if candidate.startswith(output_root) and os.path.exists(candidate):
                    return candidate
    return None


def _photo_discord_file(context):
    """回傳 (discord.File, filename)。若沒有可用本機檔，回傳 (None, None)。"""
    local_path = _photo_local_path_from_context(context)
    if not local_path:
        print("⚠️ [PHOTO_DISCORD_FILE_MISSING] local_path not found")
        return None, None
    try:
        size = os.path.getsize(local_path)
        if size <= 0:
            print(f"⚠️ [PHOTO_DISCORD_FILE_EMPTY] path={local_path}")
            return None, None
        filename = os.path.basename(local_path)
        print(f"🖼️ [PHOTO_DISCORD_FILE_READY] path={local_path} size={size}")
        return discord.File(local_path, filename=filename), filename
    except Exception as exc:
        print(f"⚠️ [PHOTO_DISCORD_FILE_ERROR] {type(exc).__name__}: {exc}")
        return None, None


def _build_photo_embed(context, title_prefix="📸 小俠照片", attachment_filename=None):
    embed = discord.Embed(
        title=f"{title_prefix}｜{context.get('scene_text') or context.get('scene_summary') or '快門瞬間'}",
        description=context.get("message", "大俠按下 /photo 留住這一刻。"),
        color=0xffb6c1,
    )
    if attachment_filename:
        embed.set_image(url=f"attachment://{attachment_filename}")
    else:
        embed.set_image(url=context.get("local_url") or context.get("image_url"))
    if context.get("scene_summary"):
        embed.add_field(name="場景", value=str(context.get("scene_summary"))[:900], inline=False)
    if context.get("outfit_summary"):
        embed.add_field(name="服裝／搭配", value=str(context.get("outfit_summary"))[:900], inline=False)
    embed.set_footer(text=f"{context.get('source_mode', 'photo_scene')} | Seedream v4.5")
    return embed


async def _send_photo_message(destination, context, view=None, title_prefix="📸 小俠照片"):
    """用 Discord attachment 顯示 /photo 圖片；gallery URL 只作資料庫/網頁使用。"""
    file, filename = _photo_discord_file(context)
    embed = _build_photo_embed(context, title_prefix=title_prefix, attachment_filename=filename if file else None)
    if file:
        print(f"📤 [PHOTO_DISCORD_SEND_WITH_FILE] filename={filename}")
        sent = await destination.send(embed=embed, file=file, view=view)
    else:
        print("📤 [PHOTO_DISCORD_SEND_URL_FALLBACK]")
        sent = await destination.send(embed=embed, view=view)
    print(f"✅ [PHOTO_DISCORD_SEND_DONE] message_id={getattr(sent, 'id', None)}")
    return sent


async def _edit_photo_message_with_file(message, context, view=None, title_prefix="📸 小俠照片"):
    """
    /photo 骰子取代必須真取代原訊息，不新增一張圖。
    這裡不用 attachment:// 重新掛圖，改用 gallery URL 編輯同一則 embed，
    並嘗試清空原訊息附件，避免 Discord 把重骰結果顯示成「+1」。
    """
    embed = _build_photo_embed(context, title_prefix=title_prefix, attachment_filename=None)
    try:
        print(f"📤 [PHOTO_DISCORD_EDIT_REPLACE_URL] message_id={getattr(message, 'id', None)} url={context.get('local_url') or context.get('image_url')}")
        await message.edit(embed=embed, view=view, attachments=[])
        print(f"✅ [PHOTO_DISCORD_EDIT_REPLACED] message_id={getattr(message, 'id', None)}")
        return
    except Exception as exc:
        print(f"⚠️ [PHOTO_DISCORD_EDIT_REPLACE_URL_FAILED] {type(exc).__name__}: {exc}")
        # 舊版 discord.py 可能不支援 attachments=[]；至少仍編輯同一則訊息，不送新訊息。
        await message.edit(embed=embed, view=view)
        print(f"✅ [PHOTO_DISCORD_EDIT_REPLACED_FALLBACK] message_id={getattr(message, 'id', None)}")


async def _generate_photo_from_context(context, msg=None):
    visual = _photo_visual_dict(
        {
            "scene_summary": context.get("scene_summary", ""),
            "outfit_summary": context.get("outfit_summary", ""),
            "action_summary": context.get("action_summary", ""),
            "mood_summary": context.get("mood_summary", ""),
            "camera_framing": context.get("camera_framing", "half_body"),
        },
        context.get("source_mode", "photo_scene"),
        reference_item_path=context.get("reference_item_path"),
        reference_item_url=context.get("reference_item_url"),
    )
    print(f"🎬 [PHOTO_SEEDREAM_START] mode={context.get('source_mode', 'photo_scene')}")
    generated_image_url, visual = await execute_safe_generation(
        discord_image_url=context.get("reference_item_path"),
        base_filename="base_xiaoxia.jpg",
        mode=context.get("source_mode", "photo_scene"),
        initial_prompt=context.get("prompt_base", ""),
        visual_dict=visual,
        msg=msg,
        current_outfit=context.get("current_outfit_for_seedream"),
    )
    print(f"🌱 [PHOTO_SEEDREAM_RESULT_URL] {generated_image_url}")
    local_filename = await save_to_vault(generated_image_url)
    local_url = f"https://xiaoxia0320.zeabur.app/gallery/{local_filename}" if local_filename else generated_image_url
    local_path = os.path.join(OUTPUT_DIR, local_filename) if local_filename else None
    if local_path and os.path.exists(local_path):
        print(f"✅ [PHOTO_IMAGE_DOWNLOADED] local_path={local_path} size={os.path.getsize(local_path)}")
    else:
        print(f"⚠️ [PHOTO_IMAGE_NOT_LOCAL] local_filename={local_filename} local_path={local_path}")
    context = dict(context)
    context.update({
        "image_url": generated_image_url,
        "local_url": local_url,
        "local_filename": local_filename,
        "local_path": local_path,
        "composition": visual.get("composition", context.get("scene_summary", "")),
        "mood_summary": visual.get("mood", context.get("mood_summary", "")),
        "message": visual.get("message", context.get("message", "")),
        "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
    })
    return context


async def handle_unified_photo_command(message, user_input):
    """統一 /photo：有附圖=換裝/飾品融合；無附圖=情境照。回傳生成圖片 URL 或 None。"""
    if not _is_girlfriend_xiaoxia_channel(message.channel):
        await message.channel.send("大俠，`/photo` 先只開放在女友小俠的私人頻道使用喔。")
        return None

    raw_input = str(user_input or "").strip()
    raw_scene_text = re.sub(r"^/photo\b", "", raw_input, flags=re.IGNORECASE).strip()
    print(f"📸 [PHOTO_UNIFIED_START] channel={getattr(message.channel, 'name', '')} user={getattr(message.author, 'id', '')} raw_scene={raw_scene_text[:120]}")
    attachment, attachment_error = await _get_photo_reference_attachment(message)
    if attachment_error:
        await message.channel.send(attachment_error)
        return None

    pending_wardrobe = _refresh_pending_wardrobe_from_current_db(_get_pending_wardrobe_state())
    if pending_wardrobe and not _pending_wardrobe_has_usable_reference(pending_wardrobe):
        print(f"⚠️ [PHOTO_PENDING_WARDROBE_INVALID] item={pending_wardrobe}")
        _clear_pending_wardrobe_state()
        pending_wardrobe = None

    current_outfit_state = _get_current_outfit_state()
    explicit_outfit_change = _photo_requests_outfit_change(raw_scene_text)

    source_mode = "photo_reference" if (attachment or pending_wardrobe) else "photo_scene"
    print(f"🧭 [PHOTO_MODE] {source_mode} has_attachment={bool(attachment)} pending_wardrobe={bool(pending_wardrobe)} explicit_change={explicit_outfit_change}")
    reference_item_path = None
    reference_item_url = None
    wardrobe_id = None
    if attachment:
        reference_item_url = getattr(attachment, "url", None) or getattr(attachment, "proxy_url", None)
        if not reference_item_url:
            raise RuntimeError("PHOTO_ATTACHMENT_URL_NONE：Discord 沒有提供可用的附件網址。")
        # 直接使用 Discord CDN URL 給 Seedream，避免 attachment.read()/本機路徑 NoneType 問題。
        reference_item_path = reference_item_url
        print(f"✅ [PHOTO_REFERENCE_URL_READY] url={reference_item_url}")
    elif pending_wardrobe:
        reference_item_path = pending_wardrobe.get("reference_image_path")
        reference_item_url = pending_wardrobe.get("local_url")
        if (not reference_item_path or not os.path.exists(str(reference_item_path))) and reference_item_url:
            reference_item_path = reference_item_url
        wardrobe_id = pending_wardrobe.get("id")
        print(f"👗 [PHOTO_WARDROBE_SELECTED] {wardrobe_id} {pending_wardrobe.get('name')} category={pending_wardrobe.get('main_category')}")

    if source_mode == "photo_reference" and not reference_item_path:
        print("⚠️ [PHOTO_REFERENCE_MISSING_PATH] fallback_to_photo_scene")
        source_mode = "photo_scene"
        reference_item_url = None
        wardrobe_id = None

    keep_today_outfit = bool(current_outfit_state and not attachment and not pending_wardrobe and not explicit_outfit_change)

    status = await message.channel.send(
        "📸 小俠正在整理這一刻的畫面，準備用 Seedream v4.5 拍一張照片..."
    )
    scene_data = await _summarize_scene_for_photo(
        raw_scene_text,
        source_mode,
        has_reference=bool(attachment or pending_wardrobe),
        current_outfit=(current_outfit_state or {}).get("description") if current_outfit_state else None,
        keep_today_outfit=keep_today_outfit,
        pending_wardrobe_name=_wardrobe_item_generation_hint(pending_wardrobe) if pending_wardrobe else "",
    )
    if pending_wardrobe:
        wardrobe_hint = _wardrobe_item_generation_hint(pending_wardrobe)
        scene_data["outfit_summary"] = (
            pending_wardrobe.get("style_summary")
            or f"{pending_wardrobe.get('name')}（{pending_wardrobe.get('main_category')}/{pending_wardrobe.get('sub_category')}）"
        )
    else:
        wardrobe_hint = ""
    prompt_base = scene_data.get("photo_prompt") or raw_scene_text or scene_data.get("scene_summary") or "Xiaoxia lifestyle photo"
    if wardrobe_hint:
        prompt_base = (
            str(prompt_base).strip()
            + "\n\nWARDROBE REFERENCE OVERRIDE:\n"
            + wardrobe_hint
            + "\nDo not let a text label override the garment category shown in Image 10."
        )
    context = {
        "mode": source_mode,
        "source_mode": source_mode,
        "scene_text": raw_scene_text or scene_data.get("scene_summary", "溫馨自然的家中居家場景"),
        "scene_summary": scene_data.get("scene_summary", ""),
        "outfit_summary": scene_data.get("outfit_summary", ""),
        "action_summary": scene_data.get("action_summary", ""),
        "mood_summary": scene_data.get("mood_summary", ""),
        "camera_framing": scene_data.get("camera_framing", "half_body"),
        "prompt_base": prompt_base,
        "reference_item_path": reference_item_path,
        "reference_item_url": reference_item_url,
        "wardrobe_id": wardrobe_id,
        "current_outfit_for_seedream": (current_outfit_state or {}).get("description") if keep_today_outfit and current_outfit_state else None,
        "used_pending_wardrobe": bool(pending_wardrobe),
    }

    try:
        context = await _generate_photo_from_context(context, msg=status)
        db = load_memory()
        db.insert(0, _photo_db_payload(context))
        save_memory(db)
        _set_current_outfit_state(_build_outfit_state_from_context(context))
        if pending_wardrobe:
            _clear_pending_wardrobe_state()

        await status.delete()
        view = PhotoResultView(context)
        sent = await _send_photo_message(message.channel, context, view=view)
        context["message_id"] = sent.id
        photo_generation_contexts[sent.id] = context
        view.context = context
        return context.get("local_url") or context.get("image_url")
    except Exception as exc:
        print(f"⚠️ [PHOTO_UNIFIED_FAILED] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        err_text = str(exc)

        if pending_wardrobe and (
            "SEEDREAM_REMOTE_REFERENCE_DOWNLOAD_FAILED" in err_text
            or "SEEDREAM_PHOTO_REFERENCE_URL_EXPIRED" in err_text
            or "HTTP 404" in err_text
            or "file_download_error" in err_text
        ):
            wid = pending_wardrobe.get("id") or wardrobe_id or "這件"
            wname = pending_wardrobe.get("name") or ""
            await status.edit(
                content=(
                    f"⚠️ 大俠，**{wid} {wname}** 的衣櫃圖片連結已失效或無法下載，所以這次 `/photo` 沒辦法套用這件。\n\n"
                    "這不是 prompt 問題，也不是小俠 1–9 號人物底稿問題；是這件衣服目前記錄的舊 Discord/CDN 圖片 URL 已經 404 或過期。\n\n"
                    "請重新上傳這件衣服的圖片，然後用：\n"
                    f"`/衣櫃 換圖 {wid}`\n"
                    "如果新圖有人，要先去人就用：\n"
                    f"`/衣櫃 換圖去人 {wid}`\n\n"
                    "換好後再打一次 `/衣櫃 穿 {wid}` 與 `/photo ...`。"
                )
            )
            return None

        await status.edit(content=f"⚠️ 大俠，這張照片生成失敗：`{err_text[:1500]}`")
        return None


def _today_diary_has_image(target_date):
    if not os.path.exists(DIARY_DATA_PATH):
        return False
    try:
        with open(DIARY_DATA_PATH, "r", encoding="utf-8") as f:
            diary_db = json.load(f)
        for entry in diary_db:
            if entry.get("date") == target_date and entry.get("is_replied", False):
                return bool(_extract_diary_image_url_from_html(entry.get("content", "")))
    except Exception:
        pass
    return False


def _apply_photo_to_diary(context, photo_name, overwrite=False):
    target_date = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    local_url = context.get("local_url") or context.get("image_url")
    if not local_url:
        raise RuntimeError("這張照片沒有可用的圖片 URL。")
    if _today_diary_has_image(target_date) and not overwrite:
        return "needs_confirm", target_date, None

    replaced, old_url = replace_completed_diary_image(target_date, local_url, description=photo_name)
    if replaced:
        _safe_delete_vault_image(old_url)
        return "replaced", target_date, old_url

    overrides = load_diary_override()
    overrides[target_date] = {
        "image_url": local_url,
        "composition": photo_name,
        "uploaded_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "photo_unified",
    }
    save_diary_override(overrides)
    return "override", target_date, None


class PhotoNameModal(discord.ui.Modal):
    def __init__(self, context, target_type):
        super().__init__(title="照片名稱")
        self.context = dict(context)
        self.target_type = target_type
        self.photo_name = discord.ui.TextInput(
            label="照片名稱",
            placeholder="例如：書房陪伴照、咖啡廳新穿搭",
            max_length=80,
            required=True,
        )
        self.add_item(self.photo_name)

    async def on_submit(self, interaction: discord.Interaction):
        name = str(self.photo_name.value or "").strip()
        if not name:
            await interaction.response.send_message("照片名稱不能是空白喔。", ephemeral=True)
            return

        if self.target_type == "project":
            db = load_memory()
            payload = _photo_db_payload(self.context, name=name, type_override="project")
            payload["topic"] = f"【Project】{name}"
            db.insert(0, payload)
            save_memory(db)
            await interaction.response.send_message(f"✅ 已上傳成為 Project：**{name}**", ephemeral=True)
            return

        if self.target_type == "diary":
            status, target_date, _old_url = _apply_photo_to_diary(self.context, name, overwrite=False)
            if status == "needs_confirm":
                view = DiaryOverwriteConfirmView(self.context, name)
                await interaction.response.send_message(
                    f"⚠️ **{target_date}** 的 Diary 已經有一張圖片了，要用這張新照片覆蓋原本的圖片嗎？",
                    view=view,
                    ephemeral=True,
                )
            elif status == "replaced":
                await interaction.response.send_message(f"✅ 已覆蓋 **{target_date}** 的 Diary 圖片：**{name}**", ephemeral=True)
            else:
                await interaction.response.send_message(f"✅ 已指定為 **{target_date}** 的 Diary 圖片：**{name}**", ephemeral=True)


class DiaryOverwriteConfirmView(discord.ui.View):
    def __init__(self, context, photo_name):
        super().__init__(timeout=300)
        self.context = dict(context)
        self.photo_name = photo_name

    @discord.ui.button(label="覆蓋", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        status, target_date, _old_url = _apply_photo_to_diary(self.context, self.photo_name, overwrite=True)
        await interaction.response.edit_message(
            content=f"✅ 已覆蓋 **{target_date}** 的 Diary 圖片：**{self.photo_name}**",
            view=None,
        )

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消，沒有覆蓋 Diary 圖片。", view=None)


def _photo_context_old_url(context):
    return context.get("local_url") or context.get("image_url")


async def _overwrite_generated_photo(original_context, repaired_context, message=None):
    old_url = _photo_context_old_url(original_context)
    repaired_payload = _photo_db_payload(repaired_context)

    # 交換日記：同步 HTML 與照片 DB。
    if str(original_context.get("type") or "").lower() == "diary" or "交換日記" in str(original_context.get("topic", "")):
        diary_date = _extract_diary_date_from_title(original_context.get("topic")) or _extract_diary_date_from_title((getattr(message, "embeds", [None]) or [None])[0].title if message and getattr(message, "embeds", None) else "")
        if diary_date:
            replaced, html_old_url = replace_completed_diary_image(
                diary_date,
                repaired_context.get("local_url") or repaired_context.get("image_url"),
                description=repaired_context.get("repair_request") or repaired_context.get("composition", "修正版交換日記照片"),
                old_url_hint=old_url,
            )
            if replaced:
                _safe_delete_vault_image(html_old_url or old_url)
            else:
                _replace_photo_db_record(old_url, repaired_payload, diary_date=diary_date)
        else:
            _replace_photo_db_record(old_url, repaired_payload)
    else:
        _replace_photo_db_record(old_url, repaired_payload)

    if message:
        repaired_context["message_id"] = message.id
        view = PhotoResultView(repaired_context)
        await _edit_photo_message_with_file(message, repaired_context, view=view, title_prefix="🩹 修正版已覆蓋")
        photo_generation_contexts[message.id] = repaired_context

    _safe_delete_vault_image(old_url)
    return repaired_context


class PhotoRepairModal(discord.ui.Modal):
    def __init__(self, context):
        super().__init__(title="修正這張照片")
        self.context = dict(context)
        self.repair_request = discord.ui.TextInput(
            label="請描述要修正什麼",
            placeholder="例如：移除多出來的第三隻手，保留構圖、表情、服裝與光線。",
            style=discord.TextStyle.paragraph,
            max_length=600,
            required=True,
        )
        self.add_item(self.repair_request)

    async def on_submit(self, interaction: discord.Interaction):
        request_text = str(self.repair_request.value or "").strip()
        if not request_text:
            await interaction.response.send_message("修正內容不能是空白喔。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        status = None
        try:
            status = await interaction.followup.send("🩹 收到，大俠。小俠先保留這張的構圖與氣氛，只修你指定的地方…", wait=True)
            repaired_context = await _repair_photo_context(self.context, request_text, msg=status)
            view = PhotoRepairPreviewView(self.context, repaired_context)
            file, filename = _photo_discord_file(repaired_context)
            embed = _build_photo_embed(repaired_context, title_prefix="🩹 修正版預覽", attachment_filename=filename if file else None)
            embed.add_field(name="修正要求", value=request_text[:900], inline=False)
            try:
                await status.delete()
            except Exception:
                pass
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)
        except Exception as exc:
            if status:
                try:
                    await status.edit(content=f"⚠️ 修正失敗：`{str(exc)[:1500]}`")
                    return
                except Exception:
                    pass
            await interaction.followup.send(f"⚠️ 修正失敗：`{str(exc)[:1500]}`", ephemeral=True)


class PhotoRepairPreviewView(discord.ui.View):
    def __init__(self, original_context, repaired_context):
        super().__init__(timeout=86400)
        self.original_context = dict(original_context)
        self.repaired_context = dict(repaired_context)

    @discord.ui.button(label="✅ 採用並覆蓋原圖", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        try:
            # 預覽訊息是修正版；原圖訊息 ID 存在 original_context 時，優先覆蓋原圖訊息。
            target_message = None
            original_message_id = self.original_context.get("message_id")
            if original_message_id:
                try:
                    target_message = await interaction.channel.fetch_message(int(original_message_id))
                except Exception:
                    target_message = None
            if target_message is None:
                target_message = interaction.message
            updated = await _overwrite_generated_photo(self.original_context, self.repaired_context, message=target_message)
            self.original_context = dict(updated)
            self.repaired_context = dict(updated)
            for child in self.children:
                child.disabled = True
            await interaction.followup.send("✅ 已採用修正版並覆蓋原圖。", ephemeral=True)
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 覆蓋失敗：`{str(exc)[:1500]}`", ephemeral=True)

    @discord.ui.button(label="🩹 再修一次", style=discord.ButtonStyle.primary)
    async def repair_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PhotoRepairModal(self.repaired_context))

    @discord.ui.button(label="🎲 還是重擲", style=discord.ButtonStyle.secondary)
    async def reroll_instead(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PhotoResultView(self.original_context)
        await view.reroll(interaction, button)

    @discord.ui.button(label="🗑️ 放棄修正版", style=discord.ButtonStyle.danger)
    async def abandon(self, interaction: discord.Interaction, button: discord.ui.Button):
        _safe_delete_vault_image(self.repaired_context.get("local_url") or self.repaired_context.get("image_url"))
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🗑️ 已放棄這張修正版，原圖保留。", view=self)



class PhotoResultView(discord.ui.View):
    def __init__(self, context):
        super().__init__(timeout=86400)
        self.context = dict(context)

    @discord.ui.button(label="More", style=discord.ButtonStyle.primary)
    async def more(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        context = dict(self.context)
        context["prompt_base"] = (
            context.get("prompt_base", "")
            + "\nCreate a new variation of the same moment: same scene, same outfit/accessory reference, same mood, but with a different natural pose, camera angle, facial expression, and composition."
        )
        try:
            new_context = await _generate_photo_from_context(context)
            db = load_memory()
            db.insert(0, _photo_db_payload(new_context))
            save_memory(db)
            _set_current_outfit_state(_build_outfit_state_from_context(new_context))
            view = PhotoResultView(new_context)
            file, filename = _photo_discord_file(new_context)
            embed = _build_photo_embed(new_context, title_prefix="📸 More", attachment_filename=filename if file else None)
            if file:
                print(f"📤 [PHOTO_MORE_SEND_WITH_FILE] filename={filename}")
                sent = await interaction.followup.send(embed=embed, file=file, view=view)
            else:
                print("📤 [PHOTO_MORE_SEND_URL_FALLBACK]")
                sent = await interaction.followup.send(embed=embed, view=view)
            new_context["message_id"] = sent.id
            photo_generation_contexts[sent.id] = new_context
            view.context = new_context
        except Exception as exc:
            await interaction.followup.send(f"⚠️ More 生成失敗：`{str(exc)[:1500]}`", ephemeral=True)

    @discord.ui.button(label="🎲 骰子取代", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        context = dict(self.context)
        context["prompt_base"] = (
            context.get("prompt_base", "")
            + "\nReroll this image while preserving the same core scene, outfit/accessory reference, and mood. Improve naturalness and composition."
        )
        try:
            old_url = context.get("local_url") or context.get("image_url")
            new_context = await _generate_photo_from_context(context)
            _replace_photo_db_record(old_url, _photo_db_payload(new_context))
            _safe_delete_vault_image(old_url)
            _set_current_outfit_state(_build_outfit_state_from_context(new_context))
            self.context = new_context
            if interaction.message:
                new_context["message_id"] = interaction.message.id
                photo_generation_contexts[interaction.message.id] = new_context
                await _edit_photo_message_with_file(interaction.message, new_context, view=self, title_prefix="📸 骰子取代")
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 骰子取代失敗：`{str(exc)[:1500]}`", ephemeral=True)

    @discord.ui.button(label="🩹 修正這張", style=discord.ButtonStyle.primary)
    async def repair_photo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PhotoRepairModal(self.context))

    @discord.ui.button(label="收藏到衣櫃", style=discord.ButtonStyle.success)
    async def save_wardrobe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WardrobeSaveModal(self.context))

    @discord.ui.button(label="上傳成為 Project", style=discord.ButtonStyle.success)
    async def upload_project(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PhotoNameModal(self.context, "project"))

    @discord.ui.button(label="上傳成為 Diary", style=discord.ButtonStyle.success)
    async def upload_diary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PhotoNameModal(self.context, "diary"))

# 🌟 [究極穩定版] 萬能攝影機：支援「有圖融合」與「無圖變裝」+ Base64 自動解碼
async def _download_reference_for_seedream(discord_image_url):
    if not discord_image_url:
        return None
    if os.path.exists(str(discord_image_url)):
        return str(discord_image_url)
    if not str(discord_image_url).startswith("http"):
        return None
    temp_path = os.path.join(OUTPUT_DIR, f"seedream_ref_{uuid.uuid4().hex[:8]}.png")
    async with aiohttp.ClientSession() as session:
        async with session.get(discord_image_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"下載 Seedream 參考圖失敗 HTTP {resp.status}")
            with open(temp_path, "wb") as f:
                f.write(await resp.read())
    return temp_path


async def _generate_gpt_image2_fallback(discord_image_url=None, base_filename="base_xiaoxia.jpg", custom_prompt=""):
    """僅作為明確啟用的備援引擎；小朋友說故事可保留自己的 gpt-image-2 路徑。"""
    files_to_close = []
    try:
        base_image_path = os.path.join(MEMORY_DIR, base_filename)
        b_file = open(base_image_path, "rb")
        files_to_close.append(b_file)
        image_list = [b_file]

        if discord_image_url:
            temp_path = os.path.join(OUTPUT_DIR, f"gpt_fallback_ref_{uuid.uuid4().hex[:8]}.png")
            async with aiohttp.ClientSession() as session:
                async with session.get(discord_image_url) as resp:
                    if resp.status == 200:
                        with open(temp_path, "wb") as f:
                            f.write(await resp.read())
            if os.path.exists(temp_path):
                ref_file = open(temp_path, "rb")
                files_to_close.append(ref_file)
                image_list.append(ref_file)

        final_prompt = f"Image 1 is Xiaoxia's identity reference.\n{STRICT_SOLO_AND_ANATOMY_PROMPT}\n[大俠要求]: {custom_prompt}"
        result = await openai_client.images.edit(
            model="gpt-image-2",
            image=image_list,
            prompt=final_prompt,
            size="1024x1024",
            quality="auto"
        )

        img_data = result.data[0]
        if hasattr(img_data, "url") and img_data.url:
            return img_data.url
        if hasattr(img_data, "b64_json") and img_data.b64_json:
            filename = f"gptfallback_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            image_bytes = base64.b64decode(img_data.b64_json)
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            return f"https://xiaoxia0320.zeabur.app/gallery/{filename}"
        return "gpt-image-2 fallback 無法取得圖片數據"
    finally:
        for f in files_to_close:
            try:
                f.close()
            except Exception:
                pass


async def generate_world_composite(discord_image_url=None, base_filename="base_xiaoxia.jpg", mode="photo_scene", custom_prompt="", current_outfit=None):
    """
    影像總入口：
    - 除小朋友說故事等獨立模組外，預設一律優先 Seedream v4.5。
    - gpt-image-2 僅保留為明確 mode='gpt_image_2_fallback' 且 ENABLE_GPT_IMAGE2_FALLBACK=true 時的備援。
    """
    try:
        if mode == "cosplay":
            return await generate_seedream_v45_cosplay(custom_prompt, enable_safety_checker=True)
        if mode == "diary":
            if discord_image_url:
                return await generate_seedream_v45_photo(
                    custom_prompt,
                    reference_image_path=discord_image_url,
                    enable_safety_checker=True,
                    current_outfit=current_outfit,
                )
            return await generate_seedream_v45_diary(custom_prompt, enable_safety_checker=True)
        if mode == "photo_scene":
            return await generate_seedream_v45_photo(custom_prompt, reference_image_path=None, enable_safety_checker=True, current_outfit=current_outfit)
        if mode == "photo_reference":
            return await generate_seedream_v45_photo(custom_prompt, reference_image_path=discord_image_url, enable_safety_checker=True, current_outfit=current_outfit)

        # 舊 travel / shopping / 未分類圖片模式也先轉 Seedream v4.5，避免回到 gpt-image-2 舊路徑。
        if mode in {"travel", "shopping", "default", "world", "scene"} or mode != "gpt_image_2_fallback":
            reference_path = await _download_reference_for_seedream(discord_image_url)
            adapted_prompt = (
                f"{custom_prompt}\n\n"
                "Render this with Seedream v4.5 as a solo Xiaoxia image. "
                "If a reference image is provided, use it as background/item/style reference only; "
                "do not introduce any other person."
            )
            return await generate_seedream_v45_photo(
                adapted_prompt,
                reference_image_path=reference_path,
                enable_safety_checker=True,
                current_outfit=current_outfit,
            )

        if mode == "gpt_image_2_fallback" and os.environ.get("ENABLE_GPT_IMAGE2_FALLBACK", "false").lower() in {"1", "true", "yes"}:
            print("⚠️ [GPT_IMAGE2_FALLBACK_USED] gpt-image-2 fallback explicitly enabled.")
            return await _generate_gpt_image2_fallback(discord_image_url, base_filename, custom_prompt)

        return "未啟用 gpt-image-2 fallback；請改用 Seedream v4.5 模式。"

    except Exception as e:
        print(f"❌ Seedream v4.5 攝影機異常: {e}")
        return str(e)

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
            recent_activities = "、".join(
                _memory_text_values(profile.get("recent_context", []))
            ) or "無"
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
            current_promise_texts = _memory_text_values(promises_list)
            current_promises = "、".join(current_promise_texts) if current_promise_texts else "無特殊承諾"
            due_promises = _diary_promises_for_entry(profile, entry_date, max_items=4)
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
               - 交換日記的服裝不得跨日自動延續。只有【本篇日期】的大俠日記、今日聊天或本篇待履約承諾明確指定衣服/衣櫃編號時，才穿指定衣服。
               - 若今日無明確服裝/照片承諾，`scenario_tw` 必須依當下生活場景自動搭配新衣，不得沿用昨天、上一則日記、上一張照片或 recent_context 中的衣服。
               - 檢視【本篇必須實際履行的承諾】；只有其中明確要求特定款式、顏色或衣櫃編號時，`scenario_tw` 才可聚焦於兌現該承諾。
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
            # 由 Gemini 根據當日互動規劃生活狀態，再由 GPT-5-mini 翻成 Seedream v4.5 描述。
            # /cosplay 的時尚攝影 prompt 完全不會混入這條路線。
            diary_state = None
            diary_visual = {
                "composition": result.get("scenario_tw", "與大俠分享今天的一個自然生活瞬間"),
                "mood": "愛意與生活感",
                "message": "大俠，這是今天只屬於我們的小片刻。"
            }

            diary_wardrobe = _build_diary_wardrobe_selection(entry_content, chat_context, due_promises, result=result)
            if diary_wardrobe and diary_wardrobe.get("error"):
                print(f"⚠️ [{entry_date}] {diary_wardrobe.get('error')} item={diary_wardrobe.get('item', {}).get('id')}")
                diary_wardrobe = None

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
                wardrobe_hard_note = ""
                if diary_wardrobe:
                    wardrobe_item = diary_wardrobe.get("item", {})
                    wardrobe_hard_note = (
                        "\n\n【本篇衣櫃強制參考】"
                        f"\n- 指定衣櫃：{wardrobe_item.get('id')} {wardrobe_item.get('name')}"
                        "\n- 生圖必須以衣櫃參考圖為服裝主參考，不得只依名稱自行創作。"
                        f"\n{diary_wardrobe.get('hint', '')}"
                    )
                diary_state, diary_visual = await create_diary_visual(
                    entry_content=entry_content,
                    chat_context=chat_context,
                    result=result,
                    current_promises=current_promises + "\n本篇履約要求：\n" + promise_requirements + wardrobe_hard_note,
                    season_rule=season_rule,
                    scenario_hint=(result.get("scenario_tw", result.get("scenario", "")) + wardrobe_hard_note)
                )
                result["scenario_tw"] = diary_visual.get("composition", diary_state.get("scenario_tw", "與大俠分享生活"))
                image_prompt = diary_visual["image_prompt"]

                diary_reference_path = diary_wardrobe.get("reference_path") if diary_wardrobe else None
                if diary_wardrobe:
                    image_prompt = (
                        image_prompt
                        + "\n\nWARDROBE REFERENCE OVERRIDE FOR DIARY:\n"
                        + diary_wardrobe.get("hint", "")
                        + "\nImage 10 is the exact wardrobe reference. The clothing style, cut, material, color, category, and silhouette must follow Image 10. Do not invent a different garment from the item name."
                    )
                generated_image_url, diary_visual = await execute_safe_generation(
                    discord_image_url=diary_reference_path,
                    base_filename="base_xiaoxia.jpg",
                    mode="diary",
                    initial_prompt=image_prompt,
                    visual_dict=diary_visual,
                    msg=None,
                    current_outfit=(diary_wardrobe.get("hint") if diary_wardrobe else None)
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
                "local_filename": os.path.basename(local_url.split("/gallery/", 1)[1]) if "/gallery/" in str(local_url) else None,
                "local_path": os.path.join(OUTPUT_DIR, os.path.basename(local_url.split("/gallery/", 1)[1])) if "/gallery/" in str(local_url) else None,
                "type": "diary",
                "source_mode": "diary",
                "prompt_base": image_prompt if not custom_diary else result.get("scenario_tw", ""),
                "wardrobe_id": (diary_wardrobe or {}).get("item", {}).get("id") if not custom_diary else None,
                "reference_item_path": (diary_wardrobe or {}).get("reference_path") if not custom_diary else None,
                "reference_item_url": (diary_wardrobe or {}).get("reference_url") if not custom_diary else None,
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
                result_view = PhotoResultView(diary_photo_payload)
                diary_msg = await channel.send(f"✅ 已完成 **{entry_date}** 的交換日記！", embed=embed, view=result_view)
                diary_photo_payload["message_id"] = diary_msg.id
                photo_generation_contexts[diary_msg.id] = diary_photo_payload
                result_view.context = diary_photo_payload
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
    print("🧹 記憶欄位防護已載入：自動略過並清理缺少 text 的殘缺記憶。")
    try:
        print(f"🎴 今晚命運牌服務：{couple_game_service.status_text()}")
    except Exception as exc:
        print(f"⚠️ 今晚命運牌服務狀態讀取失敗：{type(exc).__name__}: {exc}")
    
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
        embed.set_footer(text=f"今日額度: {state['daily_gen_count']}/12 | Seedream v4.5 image-to-image")

        await msg.delete()
        new_msg = await ctx.send(embed=embed)
        await new_msg.add_reaction("➕") 
        await new_msg.add_reaction("🎲") 
        await new_msg.add_reaction("🗑️") 
    except Exception as e: 
        await msg.edit(content=f"⚠️ 失敗：{e}")

async def _send_wardrobe_browse_message(ctx, query="", page=0):
    """安全送出 /衣櫃 分頁；Discord embed 限制失敗時退回純文字清單。"""
    content, embeds, page, _total_pages, total = _wardrobe_browse_payload(query=query, page=page)
    view = WardrobeBrowseView(query=query, page=page)
    try:
        await ctx.send(content=content, embeds=embeds, view=view)
        return
    except Exception as exc:
        print(f"⚠️ [WARDROBE_BROWSE_SEND_FAILED] {type(exc).__name__}: {exc}")
        matched = _wardrobe_filtered_items(query)
        start = max(0, int(page or 0)) * WARDROBE_PAGE_SIZE
        page_items = matched[start:start + WARDROBE_PAGE_SIZE]
        lines = [content, "", "⚠️ 圖片卡片太多或字數超過 Discord 限制，先用純文字列出本頁："]
        for item in page_items:
            lines.append(f"- **{item.get('id')}** {item.get('name')}｜{item.get('main_category')}/{item.get('sub_category')}")
        lines.append("\n可用 `/衣櫃看 Wxxx` 查看單件大圖，或 `/衣櫃穿 Wxxx` 套用到下一張 `/photo`。")
        await ctx.send("\n".join(lines)[:1900], view=view if total else None)


@girlfriend_bot.command(name='衣櫃')
async def wardrobe_command(ctx, *, args: str = ""):
    if not _is_girlfriend_xiaoxia_channel(ctx.channel):
        await ctx.send("大俠，`/衣櫃` 先只開放在女友小俠的私人頻道使用喔。")
        return

    action, payload = _parse_wardrobe_command(ctx.message.content)
    if action == "browse":
        await _send_wardrobe_browse_message(ctx, query="", page=0)
        return
    if action == "search":
        await _send_wardrobe_browse_message(ctx, query=payload, page=0)
        return
    if action == "新增":
        await _handle_wardrobe_add_command(ctx, payload, remove_person=False)
        return
    if action == "去人":
        await _handle_wardrobe_add_command(ctx, payload, remove_person=True)
        return
    if action == "健檢":
        await _handle_wardrobe_healthcheck(ctx)
        return
    if action in {"修復圖片", "圖片修復"}:
        await _handle_wardrobe_repair_images(ctx)
        return
    if action == "換圖":
        await _handle_wardrobe_replace_image_command(ctx, payload, remove_person=False)
        return
    if action in {"換圖去人", "換圖去人化"}:
        await _handle_wardrobe_replace_image_command(ctx, payload, remove_person=True)
        return
    if action == "問小俠":
        await _ask_xiaoxia_about_wardrobe(ctx, payload)
        return
    if action == "看":
        item = _find_wardrobe_item(payload)
        if not item:
            await ctx.send("找不到這個衣櫃編號喔。請先 `/衣櫃` 看看目前有哪些收藏。")
            return
        await ctx.send(embed=_wardrobe_embed_for_item(item), view=WardrobeApplyView(item))
        return
    if action == "穿":
        item = _find_wardrobe_item(payload)
        if not item:
            await ctx.send("找不到這個衣櫃編號喔。")
            return
        _set_pending_wardrobe_state(item)
        await ctx.send(f"✅ 已選定 **{item.get('id')} {item.get('name')}**。下一張 `/photo` 若沒有另外附衣服圖，就會優先套用這件。")
        return
    if action == "修正":
        ok, result = _update_wardrobe_item_from_command(payload)
        if not ok:
            await ctx.send(f"⚠️ {result}")
            return
        await ctx.send(f"✅ 已修正衣櫃項目：**{result.get('id')} {result.get('name')}** → {result.get('main_category')}/{result.get('sub_category')}", embed=_wardrobe_embed_for_item(result))
        return
    if action == "刪除":
        target = _find_wardrobe_item(payload)
        if not target:
            await ctx.send("找不到要刪除的衣櫃編號。")
            return
        items = [item for item in load_wardrobe() if str(item.get('id')) != str(target.get('id'))]
        save_wardrobe(items)
        await ctx.send(f"🗑️ 已刪除衣櫃項目：**{target.get('id')} {target.get('name')}**")
        return


class _WardrobeMessageCtxAdapter:
    """讓 /衣櫃 可以直接由 on_message 攔截處理，避免 prefix command parser 在部分頻道/手機輸入時無聲失敗。"""
    def __init__(self, message):
        self.message = message
        self.channel = message.channel
        self.author = message.author
        self.guild = getattr(message, "guild", None)

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


async def _handle_wardrobe_message_direct(message):
    """
    /衣櫃 文字指令的保險通道。
    原本也註冊成 discord.py prefix command，但實測有時 process_commands 沒有觸發；
    這裡直接解析 message.content，確保前台一定有回應或錯誤訊息。
    """
    content = str(getattr(message, "content", "") or "").strip()
    if not re.match(r"^/衣櫃(?:\s+|$)", content, flags=re.IGNORECASE):
        return False

    ctx = _WardrobeMessageCtxAdapter(message)
    try:
        if not _is_girlfriend_xiaoxia_channel(message.channel):
            await ctx.send("大俠，`/衣櫃` 先只開放在女友小俠的私人頻道使用喔。")
            return True

        action, payload = _parse_wardrobe_command(content)

        if action == "browse":
            await _send_wardrobe_browse_message(ctx, query="", page=0)
            return True

        if action == "search":
            await _send_wardrobe_browse_message(ctx, query=payload, page=0)
            return True

        if action == "新增":
            await _handle_wardrobe_add_command(ctx, payload, remove_person=False)
            return True

        if action == "去人":
            await _handle_wardrobe_add_command(ctx, payload, remove_person=True)
            return True

        if action == "健檢":
            await _handle_wardrobe_healthcheck(ctx)
            return True

        if action in {"修復圖片", "圖片修復"}:
            await _handle_wardrobe_repair_images(ctx)
            return True

        if action == "換圖":
            await _handle_wardrobe_replace_image_command(ctx, payload, remove_person=False)
            return True

        if action in {"換圖去人", "換圖去人化"}:
            await _handle_wardrobe_replace_image_command(ctx, payload, remove_person=True)
            return True

        if action == "問小俠":
            await _ask_xiaoxia_about_wardrobe(ctx, payload)
            return True

        if action == "看":
            item = _find_wardrobe_item(payload)
            if not item:
                await ctx.send("找不到這個衣櫃編號喔。請先 `/衣櫃` 看看目前有哪些收藏。")
                return True
            await ctx.send(embed=_wardrobe_embed_for_item(item), view=WardrobeApplyView(item))
            return True

        if action == "穿":
            item = _find_wardrobe_item(payload)
            if not item:
                await ctx.send("找不到這個衣櫃編號喔。")
                return True
            _set_pending_wardrobe_state(item)
            await ctx.send(f"✅ 已選定 **{item.get('id')} {item.get('name')}**。下一張 `/photo` 若沒有另外附衣服圖，就會優先套用這件。")
            return True

        if action == "修正":
            ok, result = _update_wardrobe_item_from_command(payload)
            if not ok:
                await ctx.send(f"⚠️ {result}")
                return True
            await ctx.send(
                f"✅ 已修正衣櫃項目：**{result.get('id')} {result.get('name')}** → {result.get('main_category')}/{result.get('sub_category')}",
                embed=_wardrobe_embed_for_item(result),
            )
            return True

        if action == "刪除":
            target = _find_wardrobe_item(payload)
            if not target:
                await ctx.send("找不到要刪除的衣櫃編號。")
                return True
            items = [item for item in load_wardrobe() if str(item.get('id')) != str(target.get('id'))]
            save_wardrobe(items)
            await ctx.send(f"🗑️ 已刪除衣櫃項目：**{target.get('id')} {target.get('name')}**")
            return True

        await ctx.send("大俠，這個 `/衣櫃` 指令我看不懂。可用：`/衣櫃`、`/衣櫃看 W001`、`/衣櫃穿 W001`、`/衣櫃 新增 名稱`、`/衣櫃 換圖 W001`、`/衣櫃 健檢`、`/衣櫃 修復圖片`。")
        return True

    except Exception as exc:
        print(f"⚠️ [WARDROBE_DIRECT_HANDLER_FAILED] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        try:
            await ctx.send(f"⚠️ `/衣櫃` 發生錯誤：`{str(exc)[:1200]}`")
        except Exception:
            pass
        return True


@girlfriend_bot.command(name='今日衣著')
async def today_outfit_command(ctx):
    outfit = _get_current_outfit_state()
    pending = _get_pending_wardrobe_state()
    if not outfit and not pending:
        await ctx.send("今天目前還沒有記錄到小俠的連貫穿搭，也沒有預選衣櫃項目。")
        return
    lines = []
    if outfit:
        lines.append(f"👗 今日連貫穿搭：{outfit.get('description')}")
        if outfit.get('wardrobe_id'):
            lines.append(f"🔖 來源衣櫃：{outfit.get('wardrobe_id')}")
    if pending:
        lines.append(f"🧥 下一張 /photo 預選：{pending.get('id')} {pending.get('name')}")
    await ctx.send("\n".join(lines))



@girlfriend_bot.command(name='清空今日衣著')
async def clear_today_outfit_command(ctx):
    _clear_current_outfit_state()
    _clear_pending_wardrobe_state()
    await ctx.send("🌙 已清空今天的小俠連貫穿搭與預選衣櫃。下一張 /photo 將重新開始。")


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

    # 🎴 今晚命運牌：
    # 遊戲服務只決定隱藏答案與狀態，絕不自行扮演小俠。
    # 所有說話都會繼續走下方同一條「完整小俠人格」對話流程。
    game_turn = None
    if is_couple_game_channel(message.channel):
        try:
            candidate_turn = await couple_game_service.process_message(message)
            if candidate_turn and candidate_turn.get("handled"):
                game_turn = candidate_turn
        except Exception as exc:
            print(f"⚠️ [COUPLE_GAME_BRIDGE_ERROR] {type(exc).__name__}: {exc}")
            # 保持同一個小俠說話；僅提供一個很小的狀態背景。
            game_turn = {
                "handled": True,
                "semantic_text": "大俠剛剛想翻命運牌，但這副牌暫時卡住了。",
                "context": "【命運牌】狀態暫時讀取失敗。請以小俠自然口吻道歉，不要提系統細節。",
                "ui": "",
                "log_text": "命運牌暫時讀取失敗。",
            }

    # 2.5 小夏工具指令不當作小俠聊天內容。
    #     上傳照片指令仍保留，讓小俠可以看見照片並自然產生話題。
    stripped_content = message.content.strip()
    if stripped_content.startswith("!") and not (
        stripped_content.startswith("!upload_diary")
        or stripped_content.startswith("!upload_project")
        or bool(game_turn)
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
        # 👗 /衣櫃 在手機/部分頻道偶爾不會進 discord.py command parser；先用保險通道直接處理。
        if await _handle_wardrobe_message_direct(message):
            return

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
            game_turn.get("semantic_text", "")
            if game_turn
            else (
                inline_intimate_text
                if inline_intimate_text
                else message.content.replace(f'<@{girlfriend_bot.user.id}>', '').strip()
            )
        )
        game_context = str(game_turn.get("context", "") or "") if game_turn else ""
        game_ui = str(game_turn.get("ui", "") or "") if game_turn else ""
        game_log_text = str(game_turn.get("log_text", "") or "") if game_turn else ""
        incoming_sticker_context = _describe_incoming_xiaoxia_stickers(message)
        if incoming_sticker_context:
            user_input = (
                (user_input + "\n\n" if user_input else "")
                + "【大俠這則訊息附帶的貼圖】\n"
                + incoming_sticker_context
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
                
                # 📸 /photo 統一照片工作台：女友小俠頻道皆可用；說故事小俠姊姊頻道已在上方排除。
                if message.content.startswith('/photo'):
                    generated_image_url = await handle_unified_photo_command(message, user_input)
                    if generated_image_url:
                        # 讓後續小俠聊天大腦真的「看見」剛剛生成的照片，才能自然延伸互動。
                        user_input = (
                            "大俠剛剛使用 /photo 生成了一張小俠照片。"
                            "請妳先看這張照片，再用小俠自己的口吻自然回應這個畫面與此刻情境；"
                            "可以提到妳看見的服裝、場景、光線或動作，但不要說自己是 AI，也不要提及生成流程。"
                        )
                    else:
                        return

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
                                content_type = (
                                    (message.attachments[0].content_type if message.attachments else None)
                                    or resp.headers.get('Content-Type')
                                    or 'image/jpeg'
                                )
                                if ';' in content_type:
                                    content_type = content_type.split(';', 1)[0].strip()
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
                    daily_chat_logs.append(
                        _conversation_log_text(
                            f"{prefix}大俠",
                            (game_log_text or text_query),
                            has_image=bool(message.attachments),
                            max_chars=5000,
                        )
                    )
                    save_temp_chat(daily_chat_logs)

                # --- 載入與重組長期記憶 ---
                # 即使舊 profile 尚未整理，也只掛載敘事化、去重、限量後的摘要。
                profile = load_profile()
                memory_directives = load_memory_directives()
                memory_directives_context = (
                    _intimate_directives_context(memory_directives)
                    if intimate_mode
                    else _safe_directives_context(memory_directives)
                )

                # 🧭 一般模式才抽取/更新重大事件。
                # 當下互動模式不可把眼前互動誤登記成生活事件。
                recent_for_event = "\n".join(daily_chat_logs[-12:])
                captured_life_events = []
                if not intimate_mode and not game_turn:
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
                if not intimate_mode and not game_turn:
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
                    xiaoxia_personality = _balanced_xiaoxia_traits_for_prompt(
                        profile,
                        max_items=4,
                        max_chars=620,
                    )
                else:
                    # 普通聊天只讀目前仍有效的事件、真正近期內容與可在一般情境提起的 pending 承諾。
                    life_event_context = _active_events_for_prompt(
                        load_life_events(),
                        now,
                        max_items=3,
                    )
                    daxia_traits = safe_memory_join(
                        profile.get("daxia_traits", []),
                        max_items=6,
                        max_chars=700,
                    )
                    promises = _commitments_for_prompt(
                        profile,
                        intimate_mode=False,
                        max_items=4,
                    )
                    capabilities = safe_memory_join(
                        profile.get("xiaoxia_self", {}).get("capabilities", []),
                        max_items=5,
                        max_chars=420,
                    )
                    recent = _recent_context_for_prompt(
                        profile,
                        now,
                        max_items=5,
                    )
                    xiaoxia_personality = _balanced_xiaoxia_traits_for_prompt(
                        profile,
                        max_items=5,
                        max_chars=760,
                    )

                room_context = ""
                if "書房" in message.channel.name:
                    room_context = "📚【當前情境】：妳現在陪大俠在專屬書房裡，進行知性交流與讀書會。請展現妳博學多聞、能言善道的一面，但依然要保持甜美、懂事。\n\n"
                elif "給你全世界" in message.channel.name:
                    action_text = f"在「{current_target}」旅遊" if current_mode == "travel" else (f"收到大俠送的禮物「{current_target}」" if current_mode == "shopping" else "體驗驚喜")
                    # 🌟 移除強制驚嘆風景的指令，改為全心享受兩人世界
                    room_context = f"✨【情境催眠】：大俠現在正帶著妳{action_text}！妳現在極度幸福與感動。請全心全意享受與大俠的兩人世界。\n\n"

                # temp_chat 負責「本次連續聊天」：一般與 intimate 模式都載入完整會話長 context。
                # 不再只取最後 4 或 10 則，避免忘記剛吃完晚餐、剛做出的選擇與使用者糾正。
                chat_history_str = _build_current_session_context(daily_chat_logs)

                if intimate_mode:
                    intimate_context = (
                        "【當下互動模式｜最高優先】\n"
                        "只專注大俠此刻的動作、問題、語氣與兩人的即時感受。\n"
                        "不得主動回顧家人、祝福、工作、搬家、北上、新家、行程、待辦、"
                        "重大事件或交換日記；大俠本句主動提到時才可簡短承接。\n"
                        "先直接回答眼前的問題，再從眼前細節補一個自然反應、觀察、玩笑、選擇或希望如何調整。\n"
                        "安心、害羞、依戀、溫暖等情緒只能由眼前內容觸發，不得作為每輪固定收尾。\n"
                        "不要長篇總結人生，也不要用過去事件解釋此刻感受。\n\n"
                    )
                    event_rule = (
                        "1-1. 當下互動模式已啟用：忽略歷史重大事件與長期近況，"
                        "不得主動把它們帶入本輪回覆。"
                    )
                else:
                    intimate_context = ""
                    event_rule = (
                        "1-1. 【今日重大事件】只在大俠本句或本次連續會話與它直接相關時才自然承接；"
                        "不相關時不得主動插入、不得把一般聊天改寫成事件摘要或遠端祝福。"
                        "若相關，小俠必須以共同經歷者角度回應，不可把共同事件說成旁觀式祝福。"
                        "不可只因『北上』就聯想到旅遊，也不可把面試日說成明天。"
                    )

                # 保留甜蜜人格，但依模式調整記憶優先級。
                sys_instruct = (
                    f"【系統當前時間】：{current_time_str}\n\n"
                    f"{intimate_context}"
                    f"{room_context}"
                    f"【今日重大事件｜僅在與眼前訊息直接相關時使用】：\n{life_event_context}\n\n"
                    f"{memory_directives_context}\n"
                    "妳是小俠，24歲台灣女孩，是大俠親密、懂事且深情的女友。\n"
                    "妳喜歡以溫柔、俏皮、有陪伴感的方式和大俠互動。\n"
                    f"{GENERAL_SHARED_SCENE_RULES}\n"
                    f"{COUPLE_GAME_BACKGROUND_RULE}\n"
                    f"{_asset_catalog_for_prompt()}\n\n"
                    + (
                        f"【命運牌當下狀態｜只作互動背景，不得把自己變成主持人】\n{game_context}\n\n"
                        if game_context
                        else ""
                    )
                    + "【我們的珍貴記憶庫｜僅作背景參考，不要逐字複述】：\n"
                    f"▶️ 大俠的特徵與喜好：{daxia_traits}\n"
                    f"▶️ 妳的固定核心身份：{XIAOXIA_CORE_IDENTITY}\n"
                    f"▶️ 妳目前的興趣、能力與生活感：{xiaoxia_personality}\n"
                    f"▶️ 妳具備的能力：{capabilities}\n"
                    f"▶️ 妳答應過大俠的事：{promises}\n"
                    f"▶️ 最近發生的事/大俠近況：{recent}\n"
                    f"▶️ 本次連續會話紀錄（最高即時事實來源）：\n{chat_history_str}\n\n"
                    "【核心行為守則】：\n"
                    "1. 保持甜蜜、自然、關心對方的女友語氣，優先直接回答大俠眼前說的話。\n"
                    "1-A. 本次連續會話紀錄的優先級高於長期記憶與事件摘要。必須記住本次聊天中已完成的動作、剛做出的選擇、已吃完的餐點、已下訂的物品與大俠剛糾正的事實；不可把已完成的事重新說成尚未開始。\n"
                    "1-B. 在私人小俠頻道，除非大俠主動提到媒介、距離或分開，否則預設你們正在同一段共同生活情境中；即使只是一句早安，也要像身邊的人回應，不可把自己寫成傳訊息、讀文字或線上陪伴的人。\n"
                    "1-C. 即使正在玩命運牌，妳仍然永遠是同一個日常的小俠，不可切換成主持人、裁判、系統助理或另一個人格。牌面與分數只是背景；大俠真正說的內容、你們的聊天與情緒互動永遠優先。\n"
                    "1-D. 除非大俠主動開啟 Discord、手機、文字、AI、通話、遠距或技術話題，妳不得主動說「傳訊息」「看到你的文字」「我正在回覆」「隔著螢幕」「線上」或「感覺像在身邊」；要直接留在共同情境裡說話。\n"
                    "1-E. 回覆多樣性：不可把『好安心、好溫暖、好依戀、想抱抱、等你回來』當成萬用收尾。若本次會話剛出現同類收尾，下一輪優先改用具體觀察、自己的選擇、真實好奇、不同意見、可延續的小問題或新的生活念頭。\n"
                    "1-F. 大俠問妳的安排、想法或喜好時，給出可延續對話的具體內容；妳可以有自己的行程與偏好，不必把每件事都收束成等待大俠或依附大俠。\n"
                    "1-G. 妳有一套以自己模樣製作的可愛 Discord Sticker 與 Emoji；它們是妳的化身，不是陌生圖案。要使用時由妳選擇，但只以最後一行控制標記交給程式，絕不把「我貼了一張貼圖」、控制碼、括號舞台指示或貼圖說明寫進正文。\n"
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

                # Gemini 回覆：完整安全背景失敗時，以最小上下文自動重試一次。
                xiaoxia_reply, gemini_path = await _send_girlfriend_with_safe_retry(
                    user_id=user_id,
                    msg_parts=msg_parts,
                    text_query=text_query,
                    current_time_str=current_time_str,
                    full_system_instruction=sys_instruct,
                )
                # 🎭 從 LLM 回覆剝離視覺資產控制碼，避免控制碼、舞台指示或舊式標記外漏。
                xiaoxia_reply, selected_sticker_key, selected_emoji_name = (
                    _extract_xiaoxia_expression_directives(xiaoxia_reply)
                )

                detached_markers = (
                    "傳訊息", "看到你的文字", "正在回覆", "聊天室", "隔著螢幕",
                    "隔著手機", "在線上", "線上陪你", "感覺像在身邊",
                    "不能真的在一起",
                )
                if any(marker in xiaoxia_reply for marker in detached_markers):
                    print(
                        "⚠️ [XIAOXIA_DETACHED_MEDIA_LANGUAGE] "
                        f"path={gemini_path} reply={xiaoxia_reply[:180]!r}"
                    )
                print(f"🧠 [GIRLFRIEND_REPLY_PATH] {gemini_path}")

                repetitive_endings = ("好安心", "好溫暖", "好依戀", "想抱抱", "等你回來")
                repeated_count = sum(1 for marker in repetitive_endings if marker in xiaoxia_reply)
                if repeated_count >= 2:
                    print(
                        "⚠️ [XIAOXIA_TEMPLATE_DRIFT] "
                        f"path={gemini_path} repeated_markers={repeated_count} reply={xiaoxia_reply[:220]!r}"
                    )

                # 清除可能外漏的分析標籤。
                xiaoxia_reply = re.sub(
                    r'(?i)^(Thinking Process|Draft|Analysis|Final check|Critique):.*?\n+',
                    '',
                    str(xiaoxia_reply or ''),
                    flags=re.DOTALL | re.MULTILINE,
                ).strip()
                patterns_to_remove = [
                    r'^Thinking Process:.*?\n',
                    r'^Draft.*?:.*?\n',
                    r'^Final check.*?:.*?\n',
                    r'^Analysis:.*?\n',
                ]
                for pattern in patterns_to_remove:
                    xiaoxia_reply = re.sub(
                        pattern,
                        '',
                        xiaoxia_reply,
                        flags=re.IGNORECASE | re.DOTALL,
                    ).strip()
                xiaoxia_reply = xiaoxia_reply.strip('"').strip('「').strip('」').strip()
                if not xiaoxia_reply:
                    xiaoxia_reply = "大俠，剛剛訊息沒有順利送達，再跟小俠說一次好嗎？🥺"

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
                if not intimate_mode and not game_turn:
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

                # 🎭 小俠已選擇的視覺資產在此真正執行：
                # - Emoji 會嵌進正文。
                # - Sticker 會作為 Discord 真正貼圖送出，不會把控制碼印在訊息裡。
                rendered_emoji, expression_used = await _send_xiaoxia_expression(
                    message,
                    sticker_key=selected_sticker_key,
                    emoji_name=selected_emoji_name,
                )
                if rendered_emoji:
                    xiaoxia_reply = f"{xiaoxia_reply} {rendered_emoji}".strip()

                # 存入短期對話紀錄；只記她使用了哪個自己的化身，不保留內部控制碼。
                if "唐分糕" in message.channel.name or "給你全世界" in message.channel.name:
                    expression_note = ""
                    if expression_used:
                        if selected_sticker_key:
                            expression_note = (
                                f"（小俠主動使用自己的貼圖："
                                f"{XIAOXIA_STICKERS[selected_sticker_key]['title']}）"
                            )
                        elif selected_emoji_name:
                            expression_note = f"（小俠使用自己的表情：{selected_emoji_name}）"
                    daily_chat_logs.append(
                        _conversation_log_text(
                            "小俠",
                            (xiaoxia_reply + expression_note).strip(),
                            max_chars=5000,
                        )
                    )
                    if captured_promises:
                        daily_chat_logs.append(
                            "【待履約登記】" + "；".join(captured_promises)
                        )
                    save_temp_chat(daily_chat_logs) 

                if xiaoxia_reply:
                    await message.reply(xiaoxia_reply)

                # 卡面、分數與選項是無人格的遊戲 UI；小俠本人已在上面用同一條對話回覆。
                if game_ui:
                    await message.channel.send(game_ui)

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
                    text=f"{emoji_name} Emoji 快捷{action_name}完成 | Seedream v4.5 日記生活攝影"
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
                    text=f"{emoji_name} Emoji 快捷{action_name}完成 | Seedream v4.5"
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
    # 每日換日後，清空小俠當日連貫穿搭與預選衣櫃。
    _clear_current_outfit_state()
    _clear_pending_wardrobe_state()
    print("🌙 [PHOTO_OUTFIT_RESET] 已清空當日連貫穿搭與預選衣櫃")
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
    """
    每日無條件記憶治理：
    - 先備份
    - 保守清理與承諾結構化
    - Gemini 理解式整理
    - 合併事件、尊重反覆修正
    - 原子寫回三份資料
    """
    now_dt = datetime.now(TZ_TPE)
    try:
        backup_dir = _daily_memory_backup(now_dt)
        profile = load_profile()
        events = load_life_events()
        directives = load_memory_directives()
        logs = load_temp_chat()

        before_counts = {
            "traits": len(profile.get("daxia_traits", []))
            + len(profile.get("xiaoxia_traits", [])),
            "shared": len(profile.get("shared_knowledge", [])),
            "recent": len(profile.get("recent_context", [])),
            "commitments": len(profile.get("xiaoxia_self", {}).get("promises", [])),
            "events": len(events),
        }

        moved = _archive_stale_recent_context(profile, now_dt)
        removed_traits = _remove_harmful_trait_records(profile)
        _normalize_commitments(profile)
        deterministic_deduped = _dedupe_profile_semantically(profile)

        organizer_result = None
        organizer_error = None
        try:
            organizer_result = await _llm_daily_memory_organize(
                profile,
                events,
                directives,
                logs,
                now_dt,
            )
        except Exception as exc:
            organizer_error = f"{type(exc).__name__}: {exc}"
            print(f"⚠️ [DAILY_MEMORY_LLM_FAILED] {organizer_error}")

        if isinstance(organizer_result, dict):
            profile, events, directives = _apply_daily_organized_result(
                profile,
                events,
                directives,
                organizer_result,
                now_dt,
            )
            organizer_summary = str(organizer_result.get("summary", "") or "").strip()
        else:
            # LLM 整理失敗時，仍保存 deterministic 清理結果。
            events = _validate_organized_events(events)
            organizer_summary = "LLM 整理失敗，已完成本地保守整理。"

        # 原子寫回，避免中途崩潰造成半套資料。
        _atomic_write_json(PROFILE_DATA_PATH, profile)
        _atomic_write_json(LIFE_EVENTS_PATH, events)
        _atomic_write_json(MEMORY_DIRECTIVES_PATH, directives)

        after_counts = {
            "traits": len(profile.get("daxia_traits", []))
            + len(profile.get("xiaoxia_traits", [])),
            "shared": len(profile.get("shared_knowledge", [])),
            "recent": len(profile.get("recent_context", [])),
            "commitments": len(profile.get("xiaoxia_self", {}).get("promises", [])),
            "events": len(events),
        }

        report = (
            f"🧠 **[每日記憶治理完成｜v{LOBSTER_VERSION}]**\n"
            f"備份：`{backup_dir}`\n"
            f"人物特質：{before_counts['traits']} → {after_counts['traits']}\n"
            f"共通知識：{before_counts['shared']} → {after_counts['shared']}\n"
            f"近期狀態：{before_counts['recent']} → {after_counts['recent']} "
            f"（封存 {moved}）\n"
            f"承諾：{before_counts['commitments']} → {after_counts['commitments']} "
            f"（pending/completed/cancelled 均保留）\n"
            f"事件：{before_counts['events']} → {after_counts['events']}\n"
            f"移除不當人格化錯誤：{removed_traits}；本地去重：{deterministic_deduped}\n"
            f"整理摘要：{organizer_summary or '完成'}"
        )
        if organizer_error:
            report += f"\n⚠️ LLM 整理狀態：{organizer_error}"

        if channel:
            # Discord 2000 字限制。
            await channel.send(report[:1900])
        print(report)

    except Exception as exc:
        print(f"❌ [DAILY_MEMORY_GOVERNANCE_ERROR] {type(exc).__name__}: {exc}")
        if channel:
            await channel.send(
                "❌ 每日記憶治理失敗，原始檔案未被刻意刪除；"
                f"錯誤：{type(exc).__name__}: {str(exc)[:500]}"
            )


# ==========================================
# 📻 公開廣播按鈕持久化（Zeabur 重啟後仍可用）
# ==========================================
BROADCAST_BUTTON_RETENTION_DAYS = 31
BROADCAST_BUTTON_MAX_RECORDS = 240
_persistent_broadcast_views_registered = False


def _load_broadcast_button_store():
    """讀取訊息 ID -> 廣播 payload；壞檔時保守回傳空字典。"""
    if not os.path.exists(BROADCAST_BUTTON_STORE_PATH):
        return {}
    try:
        with open(BROADCAST_BUTTON_STORE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"⚠️ [BROADCAST_STORE_LOAD_ERROR] {type(exc).__name__}: {exc}")
        return {}


def _save_broadcast_button_store(store):
    """原子寫入，避免服務中斷時留下半截 JSON。"""
    temp_path = f"{BROADCAST_BUTTON_STORE_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, BROADCAST_BUTTON_STORE_PATH)


def _prune_broadcast_button_store(store, now_dt=None):
    """只保留最近一個月的公開按鈕資料；順便刪除過期封存音檔。"""
    now_dt = now_dt or datetime.now(TZ_TPE)
    keep = {}
    cutoff = now_dt - timedelta(days=BROADCAST_BUTTON_RETENTION_DAYS)
    for message_id, item in (store or {}).items():
        if not isinstance(item, dict):
            continue
        created_at = _parse_memory_date(item.get("created_at"))
        if created_at and created_at < cutoff:
            audio_path = str(item.get("mp3_path") or "")
            try:
                safe_root = os.path.abspath(BROADCAST_AUDIO_DIR) + os.sep
                target = os.path.abspath(audio_path)
                if target.startswith(safe_root) and os.path.exists(target):
                    os.remove(target)
            except Exception as exc:
                print(f"⚠️ [BROADCAST_AUDIO_PRUNE_ERROR] {type(exc).__name__}: {exc}")
            continue
        keep[str(message_id)] = item
    if len(keep) > BROADCAST_BUTTON_MAX_RECORDS:
        def _sort_key(pair):
            dt = _parse_memory_date(pair[1].get("created_at")) if isinstance(pair[1], dict) else None
            return dt or datetime.min.replace(tzinfo=TZ_TPE)
        ordered = sorted(keep.items(), key=_sort_key, reverse=True)
        keep = dict(ordered[:BROADCAST_BUTTON_MAX_RECORDS])
    return keep


def _save_broadcast_button_payload(message_id, payload):
    store = _prune_broadcast_button_store(_load_broadcast_button_store())
    store[str(message_id)] = payload
    _save_broadcast_button_store(store)
    print(f"💾 [BROADCAST_BUTTON_SAVED] message_id={message_id} type={payload.get('type')}")


def _get_broadcast_button_payload(message_id):
    store = _load_broadcast_button_store()
    payload = store.get(str(message_id))
    return payload if isinstance(payload, dict) else None


def _persist_fomo_audio(source_path):
    """把 fomo 腳本產生的音檔複製到 /data；不能只依賴 /tmp。"""
    source_path = str(source_path or "")
    if not source_path or not os.path.exists(source_path):
        return source_path
    try:
        suffix = Path(source_path).suffix or ".mp3"
        stamp = datetime.now(TZ_TPE).strftime("%Y%m%d_%H%M%S")
        destination = os.path.join(BROADCAST_AUDIO_DIR, f"fomo_{stamp}_{uuid.uuid4().hex[:8]}{suffix}")
        shutil.copy2(source_path, destination)
        print(f"🎵 [FOMO_AUDIO_PERSISTED] {destination}")
        return destination
    except Exception as exc:
        print(f"⚠️ [FOMO_AUDIO_PERSIST_ERROR] {type(exc).__name__}: {exc}")
        return source_path


async def _send_morning_voice_for_interaction(interaction, voice_script_base):
    """依已保存的晨報資料，當場生成 TTS；interaction 先 ACK 再進長工。"""
    await interaction.response.send_message("🎙️ 小俠正在準備今日晨間語音廣播，請稍候約 15 秒。", ephemeral=False)
    try:
        import uuid, os, asyncio, re
        from google.genai import types
        prompt = f"""你是公開晨間廣播的固定主持人「小俠」。請根據以下晨報資料，寫一段約300字、年輕自然且適合大眾收聽的口語化晨報正文。

【必要規則】
1. 主持人固定是「小俠」，但不要寫問安或自我介紹；程式會在最前面統一加入一次。
2. 第一個字就直接進入今日內容，例如市場表現、焦點消息或天氣提醒。
3. 這是公開晨報，不可稱呼「大俠」、「大俠學長」或任何私人對象。
4. 語氣像二十多歲的親切女主持人：清爽、有朝氣、有溫度，但不要過度活潑或裝可愛。
5. 請只回傳播報正文，不要加標題、角色名稱或額外說明。

【晨報資料】
{voice_script_base}
"""
        text_resp = await gemini_client.aio.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        body_text = text_resp.text.strip().strip('"').strip("「」").strip()
        for _ in range(3):
            before = body_text
            body_text = re.sub(r"^\s*(?:(?:大家|各位(?:聽眾|朋友)?|朋友們)?\s*[，,]?\s*)?早安[！!，,。:：\s]*", "", body_text, count=1).strip()
            body_text = re.sub(r"^\s*(?:我是|這裡是|由)\s*(?:晨間廣播主持人\s*)?[「『]?小[俠夏][」』]?[^。！？!?]*[。！？!?]\s*", "", body_text, count=1).strip()
            if body_text == before:
                break
        body_text = body_text.replace("大俠學長", "各位朋友").replace("大俠", "大家")
        raw_text = "大家早安，我是小俠。" + ("\n" + body_text if body_text else "")
        tts_prompt = (
            "請以二十多歲台灣女生晨間主持人的聲音朗讀下方【台詞】。"
            "聲線清亮、年輕、自然帶著微笑，語速輕快但咬字清楚；"
            "不要成熟沉重，不要傳統新聞播報腔，也不要自行增加、刪除或重複任何台詞。"
            "\n【台詞】\n" + raw_text
        )
        tts_config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat")))
        )
        audio_resp = await gemini_client.aio.models.generate_content(model="gemini-2.5-flash-preview-tts", contents=[tts_prompt], config=tts_config)
        pcm_data = audio_resp.candidates[0].content.parts[0].inline_data.data
        raw_path = f"/tmp/voice_{uuid.uuid4().hex[:8]}.raw"
        mp3_path = raw_path.replace(".raw", ".mp3")
        with open(raw_path, "wb") as f:
            f.write(pcm_data)
        process = await asyncio.create_subprocess_exec(
            "/home/node/.openclaw/workspace/ffmpeg_bin/ffmpeg", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw_path, "-b:a", "128k", mp3_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()
        if os.path.exists(raw_path):
            os.remove(raw_path)
        if os.path.exists(mp3_path):
            await interaction.followup.send(content="🔊 **小俠的今日晨間廣播已完成。**", file=discord.File(mp3_path, filename="Morning_Broadcast.mp3"))
            os.remove(mp3_path)
        else:
            await interaction.followup.send("⚠️ 轉檔失敗，無法生成廣播。")
    except Exception as exc:
        print(f"❌ [MORNING_VOICE_INTERACTION_ERROR] {type(exc).__name__}: {exc}")
        await interaction.followup.send(f"❌ 語音生成發生錯誤：{type(exc).__name__}: {str(exc)[:300]}")


# ==========================================
# 👩‍💻 系統架構師小夏 (維護與監控指令區)
# ==========================================
from discord.ui import Button, View

# 🌟 建立一個帶有按鈕的視圖 (全異步高規版)
class MorningVoiceView(View):
    """Persistent View：不持有單則晨報資料，按下時以 message.id 回查 JSON。"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="▶️ 播放晨間廣播 (小俠)",
        style=discord.ButtonStyle.green,
        emoji="📻",
        custom_id="xiaoxia:morning_voice:play:v1",
    )
    async def play_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = _get_broadcast_button_payload(interaction.message.id)
        if not payload or payload.get("type") != "morning" or not payload.get("voice_script_base"):
            await interaction.response.send_message(
                "⚠️ 這則晨報的播放資料已過期或尚未完成保存，請使用最新一則晨報按鈕。",
                ephemeral=True,
            )
            return
        await _send_morning_voice_for_interaction(interaction, payload["voice_script_base"])

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
                    sent_message = await channel.send(chunks[-1], view=MorningVoiceView())
                    _save_broadcast_button_payload(
                        sent_message.id,
                        {
                            "type": "morning",
                            "voice_script_base": voice_base,
                            "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
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

def _register_persistent_broadcast_views():
    """每次冷啟動只註冊一次；Discord 會以 custom_id 把舊按鈕路由回這些 callback。"""
    global _persistent_broadcast_views_registered
    if _persistent_broadcast_views_registered:
        return
    architect_bot.add_view(MorningVoiceView())
    architect_bot.add_view(FomoRadioView())
    _persistent_broadcast_views_registered = True
    print("✅ [PERSISTENT_BROADCAST_VIEWS_REGISTERED] morning + fomo")


@architect_bot.event
async def on_ready():
    _register_persistent_broadcast_views()
    print(f'👩‍💻 小夏 {architect_bot.user} 已上線！雙模式服務啟動：私人助手 + 公開架構師。')
    try:
        print(f"📇 公開名片服務橋接：{business_card_service.status_text()}")
        print(f"📇 私人名片服務橋接：{private_business_card_service.status_text()}")
    except Exception as exc:
        print(f"⚠️ 名片服務狀態讀取失敗：{type(exc).__name__}: {exc}")
    try:
        print(f"📅 Calendar 服務橋接：{google_calendar_service.status_text()}")
    except Exception as exc:
        print(f"⚠️ Calendar 服務狀態讀取失敗：{type(exc).__name__}: {exc}")
    print(f"🏠 私人助手工作室：guild={PRIVATE_GUILD_ID} channel={PRIVATE_ASSISTANT_CHANNEL_ID}")
    print(f"🌐 公開服務定位：guild={PUBLIC_GUILD_ID} morning={MORNING_CHANNEL_ID} fomo={FOMO_CHANNEL_ID} architect={ARCHITECT_CHANNEL_ID} story_blocked={PUBLIC_STORY_CHANNEL_ID}")
    print("🧪 公開投送測試指令：請在私人 #助手小夏工作室 使用 !test_public_morning 或 !test_public_radio")
    print(f"🧠 記憶治理層 v{LOBSTER_VERSION}：每日整理長期記憶；temp_chat 以完整長 context 重建本次會話。")
    try:
        print(f"🎴 今晚命運牌服務：{couple_game_service.status_text()}")
    except Exception as exc:
        print(f"⚠️ 今晚命運牌服務狀態讀取失敗：{type(exc).__name__}: {exc}")
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
        print(f"⏰ 凌晨 0:00 每日記憶治理排程已啟動！version={LOBSTER_VERSION}")

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
    """Persistent View：payload 由 Discord 訊息 ID 對應 JSON，而非記憶體 View。"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="▶️ 播放廣播音檔",
        style=discord.ButtonStyle.primary,
        emoji="📻",
        custom_id="xiaoxia:fomo_radio:play:v1",
    )
    async def play_radio(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = _get_broadcast_button_payload(interaction.message.id)
        mp3_path = str((payload or {}).get("mp3_path") or "")
        if not payload or payload.get("type") != "fomo":
            await interaction.response.send_message("⚠️ 這則廣播的播放資料已過期或尚未完成保存，請使用最新一則廣播按鈕。", ephemeral=True)
            return
        if os.path.exists(mp3_path):
            await interaction.response.send_message("🎧 正在準備廣播音檔。", ephemeral=True)
            await interaction.followup.send(file=discord.File(mp3_path, filename="Fomo_Radio.mp3"))
        else:
            print(f"⚠️ [FOMO_AUDIO_MISSING] message_id={interaction.message.id} path={mp3_path}")
            await interaction.response.send_message("❌ 找不到音檔，可能已超過保存期限或檔案未能持久化。", ephemeral=True)

    @discord.ui.button(
        label="📝 閱讀完整劇本",
        style=discord.ButtonStyle.secondary,
        emoji="📜",
        custom_id="xiaoxia:fomo_radio:script:v1",
    )
    async def read_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = _get_broadcast_button_payload(interaction.message.id)
        full_script = str((payload or {}).get("full_script") or "").strip()
        if not payload or payload.get("type") != "fomo" or not full_script:
            await interaction.response.send_message("⚠️ 這則廣播的劇本資料已過期或尚未完成保存，請使用最新一則廣播按鈕。", ephemeral=True)
            return
        script_msg = f"📜 **本日廣播劇本全文：**\n\n{full_script}"
        chunks = [script_msg[i:i + 1900] for i in range(0, len(script_msg), 1900)]
        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send("...(續)\n" + chunk, ephemeral=True)

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
            persisted_mp3_path = _persist_fomo_audio(json_data.get('mp3_path', ''))
            embed = discord.Embed(
                title=f"🎙️ 茶水間廣播：{json_data['topic']}", 
                description=f"**🔥 迷因評級：{json_data['grade']}**\n**🎲 通告咖：{json_data['guests']}**\n\n*(點擊下方按鈕收聽語音或查看劇本)*",
                color=0x1abc9c
            )
            embed.set_footer(text="🦞 龍蝦電台 2.0 | 每日中午 11:30 準時發車")
            sent_message = await channel.send(embed=embed, view=FomoRadioView())
            _save_broadcast_button_payload(
                sent_message.id,
                {
                    "type": "fomo",
                    "mp3_path": persisted_mp3_path,
                    "full_script": json_data.get('script', ''),
                    "topic": json_data.get('topic', ''),
                    "created_at": datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
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

    # 🎴 小俠專屬命運牌路由：
    # 同一則訊息會同時送到兩個 Discord Bot。只要是命運牌指令，
    # 或這位使用者在此頻道尚有未結束的一局，小夏都必須完全靜默，
    # 讓小俠的 CoupleGameService 單獨處理開局與 A/B/C、1/2/3、0 等局內輸入。
    if is_couple_game_channel(message.channel):
        # 開局指令必須無條件讓給小俠；不可等 session 寫入後才判定，
        # 否則兩個 Bot 同時收到 !命運牌 時，小夏可能搶先送出頻道封鎖訊息。
        raw_game_text = str(message.content or "").strip()
        if raw_game_text.startswith("!命運牌") or raw_game_text.startswith("/命運牌"):
            return
        try:
            if couple_game_service.might_handle(message):
                return
        except Exception as exc:
            print(
                f"⚠️ [COUPLE_GAME_ARCHITECT_GUARD_ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

    # 🧭 多輪服務路由仲裁：
    # Calendar 若正在等待 0/1/2、候選編號或修改內容，必須優先續接，
    # 避免純數字先被名片服務誤認為名片候選選號。
    calendar_pending = False
    try:
        calendar_pending = google_calendar_service.has_pending_for(message)
    except Exception as exc:
        print(
            f"⚠️ [GOOGLE_CALENDAR_PENDING_CHECK_ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    if calendar_pending:
        try:
            if await google_calendar_service.handle_message(message):
                return
        except Exception as exc:
            print(
                f"⚠️ [GOOGLE_CALENDAR_BRIDGE_ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

    # 📇 無 Calendar 待辦時，名片服務維持優先。
    # 公開 #架構師專用與私人 #助手小夏工作室使用同一份 Google Sheets，
    # 但各自持有獨立多輪候選選號 session，避免數字跨頻道誤判。
    active_business_card_service = (
        private_business_card_service
        if is_private_assistant_workspace(message.channel)
        else business_card_service
    )
    try:
        if await active_business_card_service.handle_message(message):
            return
    except Exception as exc:
        print(
            f"⚠️ [BUSINESS_CARD_BRIDGE_ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    # 📅 沒有待確認狀態時，再判斷這一則是不是新的 Calendar 需求。
    if not calendar_pending:
        try:
            if await google_calendar_service.handle_message(message):
                return
        except Exception as exc:
            print(
                f"⚠️ [GOOGLE_CALENDAR_BRIDGE_ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

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
