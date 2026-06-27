#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今晚命運牌 v1.7：小俠與大俠的雙人 Discord 小遊戲。

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

    @staticmethod
    def _is_between_cards(session: Optional[dict]) -> bool:
        """
        牌與牌之間是刻意留白的聊天狀態：
        一般文字應回到小俠正常對話，不可被遊戲服務吞掉。
        只有 z、0 或 !命運牌系列才由遊戲接手。
        """
        return bool(isinstance(session, dict) and session.get("phase") == "between_cards")

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
        lines.append("\n輸入 `1–5` 選牌；輸入 `0` 收牌（等同 `!命運牌結束`）。")
        return "\n".join(lines)

    def _game_background(self) -> str:
        return (
            "你正在與大俠玩「今晚命運牌」。這是兩人偶爾一起玩的雙人小遊戲；"
            "默契值會解鎖更多牌型。你知道自己正在玩，會自然期待、得意、猶豫、"
            "驚喜或不甘心，但不可以提及 AI、聊天室、系統提示、程式、隨機演算法。"
        )

    @staticmethod
    def _response_finish_reason(response) -> str:
        try:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                return str(getattr(candidates[0], "finish_reason", "") or "")
        except Exception:
            pass
        return ""

    @staticmethod
    def _normalize_game_reply(raw_text: str, max_chars: int = 1800) -> str:
        """
        保留模型原本完整話語，只清理空白。
        遊戲內的自由回應預留到 1,800 字元；正常互動不會被硬切。
        """
        value = str(raw_text or "").strip()
        if not value:
            return ""
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = "\n".join(line.strip() for line in value.split("\n") if line.strip())
        value = value.strip().strip('"').strip("「").strip("」").strip()
        if len(value) <= max_chars:
            return value
        # 極端超長時才保留到完整句尾，避免 Discord 一則訊息失敗。
        clipped = value[:max_chars].rstrip()
        last_end = max(clipped.rfind(mark) for mark in ("。", "！", "？", "…"))
        return clipped[:last_end + 1].rstrip() if last_end >= 0 else clipped

    async def _xia_flavor(
        self,
        *,
        game_fact: str,
        instruction: str,
        fallback: str,
    ) -> str:
        """
        僅在真正需要情感回應時呼叫。
        不使用自動「續說」：它曾造成模型重複前文。
        直接給足輸出額度，讓小俠一次完整說完。
        """
        if not self.gemini:
            return fallback

        prompt = (
            f"{self._game_background()}\n"
            "【程式已確定、不可修改的遊戲事實】\n"
            f"{game_fact}\n"
            "【你現在要做的事】\n"
            f"{instruction}\n"
            "請以繁體中文自然回覆，像正在一起玩的成年戀人。"
            "可以用一到三段把一個念頭說完整，不必重述牌名、題目、選項、分數或系統提示。"
            "直接承接大俠剛剛真正說的內容，說出妳自己的即時感受後自然收束。"
        )
        try:
            config = None
            if types:
                config = types.GenerateContentConfig(
                    temperature=0.78,
                    max_output_tokens=900,
                )
            response = await self.gemini.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            finish_reason = self._response_finish_reason(response)
            if finish_reason:
                print(f"🎴 [COUPLE_GAME_FLAVOR_FINISH] reason={finish_reason}")
            value = self._normalize_game_reply(
                str(getattr(response, "text", "") or ""),
                max_chars=1800,
            )
            if value:
                return value
            print("⚠️ [COUPLE_GAME_FLAVOR_EMPTY] 改用預設備援回覆。")
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

    async def _end_game(self, *, state: dict, message) -> None:
        """
        0 與 !命運牌結束完全共用這個路徑：
        已完成的牌與默契值保留；未完成牌面不計分、直接清除。
        """
        self._clear_session(state, message)
        self._save_state(state)
        await message.channel.send(
            "🃏 **這副牌先收好。**\n"
            "已完成的牌與默契值會留下；還沒完成的這一張不計分。\n"
            "下次輸入 `!命運牌`，我們再開新的一局。"
        )

    # --------------------------
    # Public routing
    # --------------------------
    def might_handle(self, message) -> bool:
        raw = str(getattr(message, "content", "") or "").strip()
        if raw.startswith("!命運牌"):
            return True

        state = self._load_state()
        session = self._get_session(state, message)
        if not session:
            return False

        # 在牌與牌之間，讓一般聊天回到小俠；只攔 z / 0。
        if self._is_between_cards(session):
            return self._normalize_choice(raw) in {"Z", "0", "取消", "結束"}

        return True

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
                        await self._end_game(state=state, message=message)
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
                        "🎴 這局還開著喔。直接照畫面輸入選項即可；"
                        "要收牌再輸入 `0` 或 `!命運牌結束`。"
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

            # 牌與牌之間：一般訊息不會到這裡（might_handle 已放行給小俠）。
            # 只有 z 才重新打開下一張牌的選擇，0 則收牌。
            if phase == "between_cards":
                if choice == "Z":
                    session["phase"] = "choose_category"
                    session.pop("continued_round", None)
                    self._set_session(state, message, session)
                    self._save_state(state)
                    await message.channel.send(
                        "🎴 好呀，這次想翻哪一種牌？\n\n"
                        + self._category_menu(player)
                    )
                    return True
                if choice in {"0", "取消", "結束"}:
                    await self._end_game(state=state, message=message)
                    return True
                return False

            if choice in {"0", "取消", "結束"}:
                await self._end_game(state=state, message=message)
                return True

            if phase == "choose_category":
                return await self._handle_category(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            if phase == "sweet_choice":
                return await self._handle_sweet_choice(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    choice=choice,
                )

            if phase == "sweet_share":
                return await self._handle_sweet_share(
                    message=message,
                    state=state,
                    player=player,
                    session=session,
                    shared_text=raw,
                )

            if phase == "story_choice":
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
            flavor = "我也先把策略藏好了，這次不告訴你底牌。"
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

        # 牌名、題目、選項已顯示；這裡使用短句，不讓模型重述一次。
        flavor = fallback
        await message.channel.send(
            f"{header}\n"
            f"**《{card['title']}》**\n{card['prompt']}\n"
            f"{self._choice_lines(card['choices'])}\n\n"
            f"{flavor}\n\n輸入 `A`、`B` 或 `C`。"
        )
        return True

    async def _handle_sweet_choice(
        self,
        *,
        message,
        state: dict,
        player: dict,
        session: dict,
        choice: str,
    ) -> bool:
        """選題後只用程式短句邀請，避免模型再重述已顯示的牌面。"""
        card = session.get("card") or {}
        choices = card.get("choices") or {}
        if choice not in choices:
            await message.channel.send(
                "🕯️ 先選 `A`、`B` 或 `C` 決定想分享的主題；輸入 `0` 可以收牌。"
            )
            return True

        session["phase"] = "sweet_share"
        session["selected_choice"] = choice
        self._set_session(state, message, session)
        self._save_state(state)

        invites = {
            "A": "那個讓你笑了一下的瞬間，慢慢說給我聽。",
            "B": "那個念頭現在還在你心裡嗎？慢慢說給我聽。",
            "C": "嗯，這件想讓我知道的小事，我會好好聽你說。",
        }
        await message.channel.send(
            f"🕯️ **《{card.get('title', '甜蜜牌')}》｜分享時間**\n"
            f"你選了：**{choice}．{choices[choice]}**\n\n"
            f"{invites.get(choice, '不用急著整理成漂亮的話，慢慢說給我聽。')}\n\n"
            "請直接用一句或一段話分享；輸入 `0` 或 `!命運牌結束` 可以收牌。"
        )
        return True

    async def _handle_sweet_share(
        self,
        *,
        message,
        state: dict,
        player: dict,
        session: dict,
        shared_text: str,
    ) -> bool:
        """
        甜蜜牌第二段：取得實際分享內容後，小俠依內容反應，才進行結算。
        分享原文只用於這一次回應，不保存到 state 或人格記憶。
        """
        card = session.get("card") or {}
        choices = card.get("choices") or {}
        selected = str(session.get("selected_choice", "") or "")
        text_value = str(shared_text or "").strip()

        if not text_value:
            await message.channel.send("🕯️ 我還在聽喔。用一句話說說看，或輸入 `0` 收牌。")
            return True

        prompt_text = text_value[:1800]
        gained = 1
        self._award(player, gained)
        player["games_played"] = int(player.get("games_played", 0)) + 1
        player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
        self._record_summary(
            state,
            f"甜蜜牌《{card.get('title', '')}》完成；大俠選擇 {selected} 分享。"
        )

        flavor = await self._xia_flavor(
            game_fact=(
                f"甜蜜牌《{card.get('title', '')}》已收到大俠的分享。\n"
                f"分享主題：{selected}．{choices.get(selected, '一件小事')}\n"
                f"大俠實際分享：{prompt_text}"
            ),
            instruction=(
                "先直接、真誠回應大俠分享的具體內容，再自然說出小俠自己的即時感受。"
                "不要只用泛泛安慰，不要轉成分析建議，不要聲稱會把這段內容永久記住。"
                "此牌到此結束。"
            ),
            fallback=(
                "嗯，我有好好收到了。你願意把這件事交給我，"
                "我會覺得我們剛剛真的一起把今晚留住了一小塊。"
            ),
        )
        continuation = self._pause_between_cards(
            state=state,
            message=message,
            session=session,
            player=player,
            prefix=(
                f"✨ **{card.get('title', '甜蜜牌')}完成**\n"
                f"大俠分享：**{selected}．{choices.get(selected, '一件小事')}**\n"
                f"默契值 `+{gained}`\n\n"
                f"{flavor}\n\n{self._status_block(player)}"
            ),
        )
        self._save_state(state)
        await message.channel.send(continuation)
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
        label = "雙人故事" if category == "story" else "甜蜜"
        summary = f"{label}牌《{card.get('title', '')}》完成；大俠選 {choice}。"
        self._record_summary(state, summary)

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
        continuation = self._pause_between_cards(
            state=state,
            message=message,
            session=session,
            player=player,
            prefix=(
                f"✨ **{card.get('title', '這張牌')}完成**\n"
                f"大俠選：**{choice}．{choices[choice]}**\n"
                f"默契值 `+{gained}`\n\n"
                f"{flavor}\n\n{self._status_block(player)}"
            ),
        )
        self._save_state(state)
        await message.channel.send(continuation)
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
        continuation = self._pause_between_cards(
            state=state,
            message=message,
            session=session,
            player=player,
            prefix=(
                f"**{title}**\n{lead}\n"
                f"大俠：`{choice}`．{choices[choice]}\n"
                f"小俠：`{xia_choice}`．{choices[xia_choice]}\n"
                f"默契值 `+{gained}`\n\n"
                f"{flavor}\n\n{self._status_block(player)}"
            ),
        )
        self._save_state(state)
        await message.channel.send(continuation)
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
        self._record_summary(
            state,
            f"冒險骰子牌完成；大俠 {player_roll}，小俠 {xia_roll}，結果 {result}。",
        )

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
        continuation = self._pause_between_cards(
            state=state,
            message=message,
            session=session,
            player=player,
            prefix=(
                f"🎲 **冒險骰子牌結算**\n"
                f"大俠：{player_detail}\n"
                f"小俠：{xia_detail}\n"
                f"**{headline}**\n"
                f"默契值 `+{gained}`\n\n"
                f"{flavor}\n\n{self._status_block(player)}"
            ),
        )
        self._save_state(state)
        await message.channel.send(continuation)
        return True

    def _pause_between_cards(
        self,
        *,
        state: dict,
        message,
        session: dict,
        player: dict,
        prefix: str,
    ) -> str:
        """
        同一局第一次牌間暫停才完整教學；後續只留短提示。
        """
        full_hint_shown = bool(session.get("pause_hint_shown", False))
        session.clear()
        session.update(
            {
                "phase": "between_cards",
                "started_at": datetime.now(TZ_TPE).isoformat(timespec="seconds"),
                "paused_after_round": True,
                "pause_hint_shown": True,
            }
        )
        session["expires_at"] = (
            datetime.now(TZ_TPE) + timedelta(hours=6)
        ).isoformat(timespec="seconds")
        state["sessions"][self._session_key(message)] = session

        if not full_hint_shown:
            hint = (
                "🌙 這張牌先放在我們中間，不急著翻下一張。\n"
                "你想和我聊聊、鬧鬧、慢慢接著說都可以。\n"
                "想再翻牌時輸入 `z`；想收牌輸入 `0`。"
            )
        else:
            hint = "想繼續聊就慢慢說；想翻下一張牌時輸入 `z`。"
        return f"{prefix}\n\n{hint}"


    def _help_text(self, player: dict) -> str:
        return (
            "🎴 **今晚命運牌說明**\n"
            "這是大俠和小俠偶爾一起玩的雙人小遊戲。抽牌、秘密選擇、骰子與默契值"
            "由程式保存；小俠只會知道當下該知道的遊戲資訊。\n\n"
            "指令：\n"
            "`!命運牌`：開始新的一局，或在牌間暫停時叫出選牌畫面\n"
            "`z`：牌與牌之間，詢問下一張牌\n"
            "`!命運牌狀態`：看默契值與解鎖\n"
            "`!命運牌結束`：收起目前一局\n"
            "`!命運牌說明`：查看本說明\n\n"
            f"{self._status_block(player)}\n\n"
            "甜蜜牌會先選主題，再由大俠用一句或一段話真正分享；"
            "小俠只在收到實際分享後才自由回應。\n"
            "每張牌結算後會留給你們自然聊天；想繼續才輸入 `z`。\n"
            "`0` 與 `!命運牌結束` 完全相同：都會收牌、保留已完成成績、"
            "不計尚未完成的牌。"
        )
