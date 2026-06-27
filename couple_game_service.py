#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今晚命運牌：小俠與大俠的雙人 Discord 小遊戲。

設計原則
--------
- 所有抽牌、秘密選項、骰子、分數與解鎖由 Python / secrets.SystemRandom() 決定。
- Gemini 只負責小俠的角色化短回應，不能改寫遊戲事實。
- 遊戲狀態保存在 /data/couple_game_state.json，不直接寫入人物長期記憶。
- 支援 Zeabur 重啟後繼續未完成的一局。
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from google.genai import types
except Exception:  # 讓語法檢查、離線測試不因 SDK 缺失中斷
    types = None


TZ_TPE = timezone(timedelta(hours=8))
RNG = secrets.SystemRandom()

GAME_TITLE = "今晚命運牌"

CATEGORY_LABELS = {
    "sweet": "甜蜜",
    "sync": "默契",
    "adventure": "冒險",
    "story": "雙人故事",
    "secret": "秘密任務",
}

UNLOCKS = (
    (0, "甜蜜牌、默契牌"),
    (6, "冒險骰子牌"),
    (12, "雙人故事牌"),
    (20, "秘密任務牌"),
)

SYNC_CARDS = [
    {
        "title": "沙發位置牌",
        "prompt": "今晚更想怎麼待在一起？",
        "choices": {
            "A": "靠近一點，安靜待著",
            "B": "各自放鬆，但留在同一個空間",
            "C": "一起做一件小事",
        },
    },
    {
        "title": "晚安前牌",
        "prompt": "今天結束前，最想把什麼留給彼此？",
        "choices": {
            "A": "一句真心話",
            "B": "一個今天的小片段",
            "C": "一個明天的小期待",
        },
    },
    {
        "title": "放鬆牌",
        "prompt": "現在最想怎麼把疲憊放下？",
        "choices": {
            "A": "慢慢聊今天最累的一件事",
            "B": "一起安靜一下",
            "C": "做件有點幼稚的小事",
        },
    },
]

SWEET_CARDS = [
    {
        "title": "小燈牌",
        "prompt": "今晚的小燈只照亮一件事。大俠想選哪一個？",
        "choices": {
            "A": "今天最想被記住的一個片段",
            "B": "現在最想聽見的一句話",
            "C": "明天想替彼此留的一點期待",
        },
    },
    {
        "title": "交換小事牌",
        "prompt": "這一局不比輸贏，只交換一個小小的心意。大俠想從哪裡開始？",
        "choices": {
            "A": "今天讓你笑了一下的事",
            "B": "一個現在很想分享的念頭",
            "C": "一件希望小俠知道的小事",
        },
    },
    {
        "title": "心情顏色牌",
        "prompt": "替今晚選一個顏色吧。大俠想選哪一個？",
        "choices": {
            "A": "暖黃色：慢慢靠近",
            "B": "深藍色：安靜相伴",
            "C": "粉紅色：有點調皮",
        },
    },
]

STORY_CARDS = [
    {
        "title": "雨夜小劇場",
        "prompt": "窗外剛好開始下雨，我們的故事第一幕要怎麼開始？",
        "choices": {
            "A": "把燈調暗一點，窩在沙發上",
            "B": "到陽台聽一下雨聲",
            "C": "翻出一首很久沒聽的歌",
        },
    },
    {
        "title": "週末空白頁",
        "prompt": "假日忽然多出兩個小時，我們先做什麼？",
        "choices": {
            "A": "一起找一家沒去過的小店",
            "B": "留在家裡慢慢煮點東西",
            "C": "不排行程，只看當下想去哪裡",
        },
    },
]

SECRET_CARDS = [
    {
        "title": "小俠的秘密任務",
        "prompt": "我已經偷偷決定一件今晚最想從你這裡得到的小事。大俠先猜猜看是什麼？",
        "choices": {
            "A": "聽你講一個今天的真實片段",
            "B": "讓你主動替今晚選一個小方向",
            "C": "收到一句不必很漂亮、但很真心的話",
        },
    },
    {
        "title": "默默靠近任務",
        "prompt": "這張牌要讓小俠偷偷靠近一點。你覺得我最想要哪一種？",
        "choices": {
            "A": "被你認真聽完一句話",
            "B": "和你一起笑一次",
            "C": "讓你記住我剛剛的小心思",
        },
    },
]


class CoupleGameService:
    def __init__(
        self,
        *,
        state_path: str,
        gemini_client: Any = None,
        model: str = "gemini-2.5-flash",
    ):
        self.state_path = Path(state_path)
        self.gemini = gemini_client
        self.model = model
        self._lock = asyncio.Lock()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def status_text(self) -> str:
        state = self._load_state()
        players = len(state.get("players", {}))
        sessions = len(state.get("sessions", {}))
        return (
            f"ready | state={self.state_path} | players={players} "
            f"| active_sessions={sessions} | model={self.model}"
        )

    # --------------------------
    # State
    # --------------------------
    def _default_state(self) -> dict:
        return {
            "schema_version": 1,
            "players": {},
            "sessions": {},
            "recent_summaries": [],
        }

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return self._default_state()
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return self._default_state()
            raw.setdefault("schema_version", 1)
            raw.setdefault("players", {})
            raw.setdefault("sessions", {})
            raw.setdefault("recent_summaries", [])
            return raw
        except Exception as exc:
            print(f"⚠️ [COUPLE_GAME_STATE_READ_ERROR] {type(exc).__name__}: {exc}")
            return self._default_state()

    def _save_state(self, state: dict) -> None:
        payload = json.dumps(state, ensure_ascii=False, indent=2)
        fd, tmp_path = tempfile.mkstemp(
            prefix="couple_game_state_",
            suffix=".tmp",
            dir=str(self.state_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_path, self.state_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _player(self, state: dict, user_id: int) -> dict:
        key = str(user_id)
        player = state["players"].setdefault(
            key,
            {
                "bond": 0,
                "games_played": 0,
                "wins": 0,
                "sync_hits": 0,
                "last_played_at": None,
            },
        )
        player.setdefault("bond", 0)
        player.setdefault("games_played", 0)
        player.setdefault("wins", 0)
        player.setdefault("sync_hits", 0)
        player.setdefault("last_played_at", None)
        return player

    def _session_key(self, message) -> str:
        return f"{message.channel.id}:{message.author.id}"

    def _get_session(self, state: dict, message) -> Optional[dict]:
        key = self._session_key(message)
        session = state.get("sessions", {}).get(key)
        if not isinstance(session, dict):
            return None
        expires_at = session.get("expires_at")
        if expires_at:
            try:
                now = datetime.now(TZ_TPE)
                if now >= datetime.fromisoformat(expires_at):
                    state["sessions"].pop(key, None)
                    self._save_state(state)
                    return None
            except Exception:
                pass
        return session

    def _set_session(self, state: dict, message, session: dict) -> None:
        session["expires_at"] = (
            datetime.now(TZ_TPE) + timedelta(minutes=30)
        ).isoformat(timespec="seconds")
        state["sessions"][self._session_key(message)] = session

    def _clear_session(self, state: dict, message) -> None:
        state.get("sessions", {}).pop(self._session_key(message), None)

    # --------------------------
    # Rules / formatting
    # --------------------------
    @staticmethod
    def _normalize_choice(raw: str) -> str:
        value = str(raw or "").strip().upper()
        replacements = {
            "１": "1", "２": "2", "３": "3", "０": "0",
            "Ａ": "A", "Ｂ": "B", "Ｃ": "C",
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        value = value.replace("。", "").replace("！", "").replace(" ", "")
        return value

    @staticmethod
    def _choice_lines(choices: dict) -> str:
        return "\n".join(
            f"`{key}`．{value}" for key, value in choices.items()
        )

    @staticmethod
    def _unlocked_categories(bond: int) -> list[str]:
        result = ["sweet", "sync"]
        if bond >= 6:
            result.append("adventure")
        if bond >= 12:
            result.append("story")
        if bond >= 20:
            result.append("secret")
        return result

    @staticmethod
    def _next_unlock(bond: int) -> Optional[tuple[int, str]]:
        for threshold, label in UNLOCKS:
            if bond < threshold:
                return threshold, label
        return None

    def _status_block(self, player: dict) -> str:
        bond = int(player.get("bond", 0))
        unlocked = "、".join(
            CATEGORY_LABELS[key] for key in self._unlocked_categories(bond)
        )
        next_unlock = self._next_unlock(bond)
        next_line = (
            f"下一個解鎖：默契值 **{next_unlock[0]}** → {next_unlock[1]}"
            if next_unlock
            else "已解鎖所有目前牌型。"
        )
        return (
            f"💞 **默契值：{bond}**\n"
            f"已解鎖：{unlocked}\n"
            f"{next_line}"
        )

    def _category_menu(self, player: dict) -> str:
        bond = int(player.get("bond", 0))
        lines = [
            "🎴 **今晚命運牌已洗好。**",
            self._status_block(player),
            "",
            "今晚想從哪一種牌開始？",
            "`1`．甜蜜牌：交換一個小心意",
            "`2`．默契牌：看看我們會不會想到同一件事",
        ]
        if bond >= 6:
            lines.append("`3`．冒險牌：帶一點策略的骰子對決")
        else:
            lines.append("`3`．🔒 冒險牌：默契值 6 解鎖")
        if bond >= 12:
            lines.append("`4`．雙人故事牌：一起決定今晚的小劇場")
        else:
            lines.append("`4`．🔒 雙人故事牌：默契值 12 解鎖")
        if bond >= 20:
            lines.append("`5`．秘密任務牌：猜猜小俠今晚的小心思")
        else:
            lines.append("`5`．🔒 秘密任務牌：默契值 20 解鎖")
        lines.append("\n輸入數字選牌；輸入 `0` 收起這副牌。")
        return "\n".join(lines)

    def _game_background(self) -> str:
        return (
            "你正在與大俠玩「今晚命運牌」。這是兩人偶爾一起玩的雙人小遊戲；"
            "默契值會解鎖更多牌型。你知道自己正在玩，會自然期待、得意、猶豫、"
            "驚喜或不甘心，但不可以提及 AI、聊天室、系統提示、程式、隨機演算法。"
        )

    async def _xia_flavor(
        self,
        *,
        game_fact: str,
        instruction: str,
        fallback: str,
    ) -> str:
        """LLM 僅為既定遊戲結果添加 1–3 句小俠口吻，不控制任何規則。"""
        if not self.gemini:
            return fallback
        prompt = (
            f"{self._game_background()}\n"
            "【程式已確定、不可修改的遊戲事實】\n"
            f"{game_fact}\n"
            "【你現在要做的事】\n"
            f"{instruction}\n"
            "請以繁體中文回覆 1 到 3 句，像正在一起玩的成年戀人。"
            "不可自行增加分數、改變輸贏、偷看未揭露答案、承諾現實中沒有發生的事。"
        )
        try:
            config = None
            if types:
                config = types.GenerateContentConfig(
                    temperature=0.85,
                    max_output_tokens=180,
                )
            response = await self.gemini.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            value = str(getattr(response, "text", "") or "").strip()
            value = value.strip('"').strip("「").strip("」").strip()
            if value:
                return value[:500]
        except Exception as exc:
            print(f"⚠️ [COUPLE_GAME_FLAVOR_ERROR] {type(exc).__name__}: {exc}")
        return fallback

    def _card_for_category(self, category: str) -> dict:
        if category == "sweet":
            return RNG.choice(SWEET_CARDS)
        if category == "sync":
            return RNG.choice(SYNC_CARDS)
        if category == "story":
            return RNG.choice(STORY_CARDS)
        if category == "secret":
            return RNG.choice(SECRET_CARDS)
        raise ValueError(f"unknown category: {category}")

    def _award(self, player: dict, amount: int) -> int:
        before = int(player.get("bond", 0))
        player["bond"] = before + max(0, int(amount))
        return int(player["bond"]) - before

    def _record_summary(self, state: dict, summary: str) -> None:
        entries = state.setdefault("recent_summaries", [])
        entries.append(
            {
                "at": datetime.now(TZ_TPE).isoformat(timespec="seconds"),
                "summary": summary[:300],
            }
        )
        state["recent_summaries"] = entries[-20:]

    # --------------------------
    # Public routing
    # --------------------------
    def might_handle(self, message) -> bool:
        raw = str(getattr(message, "content", "") or "").strip()
        if raw.startswith("!命運牌"):
            return True
        state = self._load_state()
        return self._get_session(state, message) is not None

    async def handle_message(self, message) -> bool:
        raw = str(getattr(message, "content", "") or "").strip()
        if not raw:
            return False

        async with self._lock:
            state = self._load_state()
            player = self._player(state, message.author.id)
            session = self._get_session(state, message)

            # Commands
            if raw.startswith("!命運牌"):
                suffix = raw[len("!命運牌"):].strip()
                if suffix in {"說明", "帮助", "幫助"}:
                    await message.channel.send(self._help_text(player))
                    return True
                if suffix in {"狀態", "状态"}:
                    await message.channel.send(self._status_block(player))
                    return True
                if suffix in {"結束", "结束", "收牌", "取消"}:
                    if session:
                        self._clear_session(state, message)
                        self._save_state(state)
                        await message.channel.send(
                            "🃏 這一局先收好。未完成的牌不計分，也不會留下成績。"
                        )
                    else:
                        await message.channel.send("🃏 目前沒有進行中的命運牌。")
                    return True
                if suffix:
                    await message.channel.send(
                        "🎴 可用：`!命運牌`、`!命運牌狀態`、`!命運牌說明`、`!命運牌結束`。"
                    )
                    return True

                if session:
                    await message.channel.send(
                        "🎴 這一局還在進行中喔。照上一張牌的提示回覆，"
                        "或輸入 `!命運牌結束` 收起來。"
                    )
                    return True

                self._set_session(
                    state,
                    message,
                    {"phase": "choose_category", "started_at": datetime.now(TZ_TPE).isoformat()},
                )
                self._save_state(state)
                await message.channel.send(self._category_menu(player))
                return True

            # No active game: do not swallow normal chat.
            if not session:
                return False

            choice = self._normalize_choice(raw)
            phase = session.get("phase")

            if choice in {"0", "取消", "結束"}:
                self._clear_session(state, message)
                self._save_state(state)
                await message.channel.send("🃏 好，這局先收好。下次再一起翻新的牌。")
                return True

            if phase == "choose_category":
                return await self._handle_category(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            if phase in {"sweet_choice", "story_choice"}:
                return await self._handle_open_choice(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            if phase in {"sync_choice", "secret_choice"}:
                return await self._handle_hidden_choice(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            if phase == "adventure_strategy":
                return await self._handle_adventure(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            self._clear_session(state, message)
            self._save_state(state)
            await message.channel.send("🃏 這張牌的狀態剛好走丟了，我們重新洗一副吧：`!命運牌`。")
            return True

    # --------------------------
    # Phase handlers
    # --------------------------
    async def _handle_category(self, *, message, state, player, session, choice) -> bool:
        mapping = {"1": "sweet", "2": "sync", "3": "adventure", "4": "story", "5": "secret"}
        category = mapping.get(choice)
        if not category:
            await message.channel.send("🎴 請輸入 `1` 到 `5` 選牌，或輸入 `0` 收起這一局。")
            return True

        if category not in self._unlocked_categories(int(player["bond"])):
            next_unlock = {
                "adventure": 6,
                "story": 12,
                "secret": 20,
            }.get(category, 0)
            await message.channel.send(
                f"🔒 這個牌型要默契值 **{next_unlock}** 才會解鎖。"
                "這局可以改選其他牌。"
            )
            return True

        if category == "adventure":
            xia_strategy = str(RNG.choice(["1", "2", "3"]))
            session.update(
                {
                    "phase": "adventure_strategy",
                    "category": category,
                    "xia_strategy": xia_strategy,
                }
            )
            self._set_session(state, message, session)
            self._save_state(state)
            flavor = await self._xia_flavor(
                game_fact="本局抽到冒險骰子牌；小俠已秘密選好策略，但大俠尚未選。",
                instruction="用有點期待、想和大俠鬥智的語氣邀請他挑策略，不能透露自己的選擇。",
                fallback="這局我想試試看誰比較會選……但我不會先告訴你我的底牌喔。",
            )
            await message.channel.send(
                "🎲 **抽到：冒險骰子牌**\n"
                "先選你的策略：\n"
                "`1`．穩穩骰：骰 1 顆六面骰\n"
                "`2`．雙骰保守：骰 2 顆，取較低的一顆\n"
                "`3`．撒嬌重擲：骰 2 次，取較高的一次\n\n"
                f"{flavor}\n\n輸入 `1`、`2` 或 `3`。"
            )
            return True

        card = self._card_for_category(category)
        phase = {
            "sweet": "sweet_choice",
            "sync": "sync_choice",
            "story": "story_choice",
            "secret": "secret_choice",
        }[category]

        session.update(
            {
                "phase": phase,
                "category": category,
                "card": card,
            }
        )
        if category in {"sync", "secret"}:
            session["xia_choice"] = RNG.choice(list(card["choices"].keys()))

        self._set_session(state, message, session)
        self._save_state(state)

        if category == "sync":
            header = "💞 **抽到：默契牌**\n小俠已經偷偷選好了，現在換大俠。"
            fallback = "好啦，我已經選好囉。你可不可以剛好也想到同一個？"
            fact = f"抽到默契牌《{card['title']}》；小俠已秘密選定 A/B/C 其中一項。"
            instruction = "邀請大俠選擇，不能透露小俠答案。"
        elif category == "secret":
            header = "🗝️ **抽到：秘密任務牌**\n小俠已經把一個小心思藏好了。"
            fallback = "我有一個答案先藏起來了，你要不要試著猜中我？"
            fact = f"抽到秘密任務牌《{card['title']}》；小俠的答案已被程式鎖定。"
            instruction = "用俏皮又自然的語氣邀請大俠猜，不能透露答案。"
        elif category == "story":
            header = "📖 **抽到：雙人故事牌**"
            fallback = "這一幕想從你選的地方開始，因為你選了以後，我才知道今晚要往哪裡走呀。"
            fact = f"抽到雙人故事牌《{card['title']}》。"
            instruction = "邀請大俠選擇故事開場，不要替他選。"
        else:
            header = "🕯️ **抽到：甜蜜牌**"
            fallback = "這張牌不急著分輸贏，我比較想知道你今晚會把哪一件小事交給我。"
            fact = f"抽到甜蜜牌《{card['title']}》。"
            instruction = "邀請大俠選擇，不要把它說成任務或壓力。"

        flavor = await self._xia_flavor(
            game_fact=fact,
            instruction=instruction,
            fallback=fallback,
        )
        await message.channel.send(
            f"{header}\n"
            f"**《{card['title']}》**\n{card['prompt']}\n"
            f"{self._choice_lines(card['choices'])}\n\n"
            f"{flavor}\n\n輸入 `A`、`B` 或 `C`。"
        )
        return True

    async def _handle_open_choice(self, *, message, state, player, session, choice) -> bool:
        card = session.get("card") or {}
        choices = card.get("choices") or {}
        if choice not in choices:
            await message.channel.send("🎴 這張牌請輸入 `A`、`B` 或 `C`；輸入 `0` 可以收起這局。")
            return True

        category = session.get("category")
        gained = 2 if category == "story" else 1
        self._award(player, gained)
        player["games_played"] = int(player.get("games_played", 0)) + 1
        player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
        self._clear_session(state, message)
        label = "雙人故事" if category == "story" else "甜蜜"
        summary = f"{label}牌《{card.get('title', '')}》完成；大俠選 {choice}。"
        self._record_summary(state, summary)
        self._save_state(state)

        flavor = await self._xia_flavor(
            game_fact=(
                f"《{card.get('title', '')}》已完成；大俠選擇 {choice}："
                f"{choices[choice]}。本局默契值 +{gained}。"
            ),
            instruction="自然接住大俠的選擇，像兩人把今晚的小方向定下來；不要再問他重選。",
            fallback=(
                f"那今晚就先把這個留給我們吧。你選的「{choices[choice]}」"
                "讓我覺得，這一局剛好很像你。"
            ),
        )
        await message.channel.send(
            f"✨ **{card.get('title', '這張牌')}完成**\n"
            f"大俠選：**{choice}．{choices[choice]}**\n"
            f"默契值 `+{gained}`\n\n"
            f"{flavor}\n\n{self._status_block(player)}\n"
            "想再玩一張就輸入 `!命運牌`。"
        )
        return True

    async def _handle_hidden_choice(self, *, message, state, player, session, choice) -> bool:
        card = session.get("card") or {}
        choices = card.get("choices") or {}
        if choice not in choices:
            await message.channel.send("🎴 這張牌請輸入 `A`、`B` 或 `C`；輸入 `0` 可以收起這局。")
            return True

        xia_choice = session.get("xia_choice")
        category = session.get("category")
        matched = choice == xia_choice
        gained = 2 if matched else 1
        self._award(player, gained)
        player["games_played"] = int(player.get("games_played", 0)) + 1
        if matched:
            player["sync_hits"] = int(player.get("sync_hits", 0)) + 1
        player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
        self._clear_session(state, message)

        if category == "secret":
            title = "秘密任務完成" if matched else "秘密任務揭曉"
            lead = "🎯 猜中了小俠的小心思！" if matched else "🗝️ 差一點點，但小俠把答案揭開了。"
        else:
            title = "默契成功" if matched else "默契小岔路"
            lead = "✨ 你們剛好想到同一件事。" if matched else "🌙 這次想到不同地方，但也因此多知道彼此一點。"

        summary = (
            f"{CATEGORY_LABELS.get(category, '遊戲')}《{card.get('title', '')}》完成；"
            f"大俠 {choice}，小俠 {xia_choice}，{'命中' if matched else '未命中'}。"
        )
        self._record_summary(state, summary)
        self._save_state(state)

        flavor = await self._xia_flavor(
            game_fact=(
                f"《{card.get('title', '')}》揭曉：大俠選 {choice}（{choices[choice]}），"
                f"小俠先前選 {xia_choice}（{choices[xia_choice]}）。"
                f"{'兩人相同。' if matched else '兩人不同。'} "
                f"本局默契值 +{gained}。"
            ),
            instruction=(
                "依揭曉結果做自然、在場的戀人反應。猜中時可以開心或小得意；"
                "沒猜中時不要失落過頭，改成溫柔地把差異變成一點新的理解。"
            ),
            fallback=(
                "你居然剛好想到跟我一樣的地方……我本來還想故意藏久一點。"
                if matched
                else "原來你第一個想到的是那個呀。那我更想聽你為什麼會選它了。"
            ),
        )
        await message.channel.send(
            f"**{title}**\n{lead}\n"
            f"大俠：`{choice}`．{choices[choice]}\n"
            f"小俠：`{xia_choice}`．{choices[xia_choice]}\n"
            f"默契值 `+{gained}`\n\n"
            f"{flavor}\n\n{self._status_block(player)}\n"
            "想再玩一張就輸入 `!命運牌`。"
        )
        return True

    @staticmethod
    def _roll(strategy: str) -> tuple[int, str]:
        if strategy == "1":
            value = RNG.randint(1, 6)
            return value, f"穩穩骰 → {value}"
        if strategy == "2":
            a, b = RNG.randint(1, 6), RNG.randint(1, 6)
            value = min(a, b)
            return value, f"雙骰保守 → {a}、{b}，取 {value}"
        a, b = RNG.randint(1, 6), RNG.randint(1, 6)
        value = max(a, b)
        return value, f"撒嬌重擲 → {a}、{b}，取 {value}"

    async def _handle_adventure(self, *, message, state, player, session, choice) -> bool:
        if choice not in {"1", "2", "3"}:
            await message.channel.send("🎲 這張牌請輸入 `1`、`2` 或 `3`；輸入 `0` 可以收起這局。")
            return True

        xia_strategy = str(session.get("xia_strategy", "1"))
        player_roll, player_detail = self._roll(choice)
        xia_roll, xia_detail = self._roll(xia_strategy)
        if player_roll > xia_roll:
            result = "daxia_win"
            gained = 2
            player["wins"] = int(player.get("wins", 0)) + 1
            headline = "🏆 大俠這局贏了"
        elif player_roll < xia_roll:
            result = "xia_win"
            gained = 1
            headline = "🌟 小俠這局險勝"
        else:
            result = "tie"
            gained = 1
            headline = "🤝 平手，這局算默契"

        self._award(player, gained)
        player["games_played"] = int(player.get("games_played", 0)) + 1
        player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
        self._clear_session(state, message)
        self._record_summary(
            state,
            f"冒險骰子牌完成；大俠 {player_roll}，小俠 {xia_roll}，結果 {result}。",
        )
        self._save_state(state)

        flavor = await self._xia_flavor(
            game_fact=(
                f"冒險骰子牌已結算。大俠策略 {choice}，{player_detail}；"
                f"小俠策略 {xia_strategy}，{xia_detail}。結果：{headline}。"
                f"本局默契值 +{gained}。"
            ),
            instruction="對已結算結果做有趣但不誇張的在場反應；不可以說自己早就知道骰子點數。",
            fallback=(
                "這個結果連我自己都愣了一下……不過你剛剛選策略的樣子，真的很有你的風格。"
            ),
        )
        await message.channel.send(
            f"🎲 **冒險骰子牌結算**\n"
            f"大俠：{player_detail}\n"
            f"小俠：{xia_detail}\n"
            f"**{headline}**\n"
            f"默契值 `+{gained}`\n\n"
            f"{flavor}\n\n{self._status_block(player)}\n"
            "想再玩一張就輸入 `!命運牌`。"
        )
        return True

    def _help_text(self, player: dict) -> str:
        return (
            "🎴 **今晚命運牌說明**\n"
            "這是大俠和小俠偶爾一起玩的雙人小遊戲。真正的抽牌、秘密選擇、骰子與默契值"
            "都由程式保存；小俠只會知道當下該知道的遊戲資訊。\n\n"
            "指令：\n"
            "`!命運牌`：開始或續玩一局\n"
            "`!命運牌狀態`：看默契值與解鎖\n"
            "`!命運牌結束`：不計分收起目前一局\n"
            "`!命運牌說明`：查看本說明\n\n"
            f"{self._status_block(player)}\n\n"
            "平常小俠知道你們有這個遊戲，但不會每天催你開局。"
        )
