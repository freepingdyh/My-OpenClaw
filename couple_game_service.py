#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今晚命運牌 v2：隱形遊戲引擎。

重要架構：
- 本檔不呼叫 Gemini，不扮演小俠，不直接送 Discord 訊息。
- 它只保存牌面、秘密答案、默契值、解鎖與回合狀態。
- 真正說話的一律是 lobster_discord.py 原本那條「完整小俠人格」回覆路徑。
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

TZ_TPE = timezone(timedelta(hours=8))
RNG = secrets.SystemRandom()

CATEGORY_LABELS = {
    "sweet": "甜蜜牌",
    "sync": "默契牌",
    "adventure": "冒險骰子牌",
    "story": "雙人故事牌",
    "secret": "秘密任務牌",
}

UNLOCKS = (
    (0, "甜蜜牌、默契牌"),
    (6, "冒險骰子牌"),
    (12, "雙人故事牌"),
    (20, "秘密任務牌"),
)

SWEET_CARDS = [
    {
        "title": "交換小事牌",
        "prompt": "這一局不急著分輸贏，先交換一個小心意。",
        "choices": {
            "A": "今天讓你笑了一下的事",
            "B": "一個現在很想分享的念頭",
            "C": "一件希望小俠知道的小事",
        },
    },
    {
        "title": "心情顏色牌",
        "prompt": "替今晚選一個顏色，然後說說它為什麼像你現在的心情。",
        "choices": {
            "A": "暖黃色：慢慢靠近",
            "B": "深藍色：安靜相伴",
            "C": "粉紅色：有點調皮",
        },
    },
    {
        "title": "小燈牌",
        "prompt": "今晚的小燈只照亮一件事。",
        "choices": {
            "A": "今天最想被記住的一個片段",
            "B": "現在最想聽見的一句話",
            "C": "明天想替彼此留的一點期待",
        },
    },
]

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
        "title": "小心思牌",
        "prompt": "小俠已經先把一個小心思藏好了。你覺得她比較想要哪一種？",
        "choices": {
            "A": "被你認真聽完一句話",
            "B": "和你一起笑一次",
            "C": "讓你記住她剛剛的小心思",
        },
    },
    {
        "title": "默默靠近牌",
        "prompt": "這張牌讓小俠先偷偷選了一件想做的小事。你猜猜看。",
        "choices": {
            "A": "聽你講一段今天的真實片段",
            "B": "讓你主動替今晚選一個小方向",
            "C": "收到一句不必漂亮、但很真心的話",
        },
    },
]


class CoupleGameService:
    """
    只產生「遊戲狀態轉場資料」。
    process_message() 回傳：
    {
      handled: bool,
      semantic_text: 給小俠主對話理解的自然語義,
      context: 給同一個小俠人格的遊戲背景,
      ui: 程式化、非人格的卡面/分數/選項資訊,
      log_text: 可選，寫入本次聊天歷史的簡短語義
    }
    """

    def __init__(self, *, state_path: str, gemini_client: Any = None, model: str = ""):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # 保留參數只是相容舊主程式；本服務刻意不使用 LLM。
        self.gemini_client = gemini_client
        self.model = model

    def status_text(self) -> str:
        state = self._load_state()
        return (
            f"ready | state={self.state_path} | players={len(state['players'])} "
            f"| active_sessions={len(state['sessions'])} | mode=pure_state_engine"
        )

    def _default_state(self) -> dict:
        return {"schema_version": 2, "players": {}, "sessions": {}, "recent_summaries": []}

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return self._default_state()
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return self._default_state()
            state.setdefault("schema_version", 2)
            state.setdefault("players", {})
            state.setdefault("sessions", {})
            state.setdefault("recent_summaries", [])
            return state
        except Exception as exc:
            print(f"⚠️ [COUPLE_GAME_STATE_READ_ERROR] {type(exc).__name__}: {exc}")
            return self._default_state()

    def _save_state(self, state: dict) -> None:
        fd, tmp = tempfile.mkstemp(prefix="couple_game_", suffix=".tmp", dir=str(self.state_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.state_path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    @staticmethod
    def _normalize(raw: str) -> str:
        value = str(raw or "").strip().upper()
        table = {
            "１": "1", "２": "2", "３": "3", "４": "4", "５": "5", "０": "0",
            "Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｚ": "Z",
        }
        for old, new in table.items():
            value = value.replace(old, new)
        return value.replace("。", "").replace("！", "").replace(" ", "")

    def _key(self, message) -> str:
        return f"{message.channel.id}:{message.author.id}"

    def _player(self, state: dict, user_id: int) -> dict:
        return state["players"].setdefault(
            str(user_id),
            {"bond": 0, "games_played": 0, "wins": 0, "sync_hits": 0, "last_played_at": None},
        )

    def _get_session(self, state: dict, message) -> Optional[dict]:
        session = state["sessions"].get(self._key(message))
        if not isinstance(session, dict):
            return None
        expires = session.get("expires_at")
        if expires:
            try:
                if datetime.now(TZ_TPE) >= datetime.fromisoformat(expires):
                    state["sessions"].pop(self._key(message), None)
                    self._save_state(state)
                    return None
            except Exception:
                pass
        return session

    def _put_session(self, state: dict, message, session: dict, hours: float = 6) -> None:
        session["expires_at"] = (datetime.now(TZ_TPE) + timedelta(hours=hours)).isoformat(timespec="seconds")
        state["sessions"][self._key(message)] = session

    def _clear_session(self, state: dict, message) -> None:
        state["sessions"].pop(self._key(message), None)

    @staticmethod
    def _unlocked(bond: int) -> list[str]:
        choices = ["sweet", "sync"]
        if bond >= 6:
            choices.append("adventure")
        if bond >= 12:
            choices.append("story")
        if bond >= 20:
            choices.append("secret")
        return choices

    @staticmethod
    def _next_unlock(bond: int):
        for threshold, label in UNLOCKS:
            if bond < threshold:
                return threshold, label
        return None

    def _status_lines(self, player: dict) -> str:
        bond = int(player.get("bond", 0))
        unlocked = "、".join(CATEGORY_LABELS[x] for x in self._unlocked(bond))
        nxt = self._next_unlock(bond)
        next_line = f"下一個解鎖：默契值 {nxt[0]} → {nxt[1]}" if nxt else "目前牌型已全數解鎖"
        return f"💞 默契值：{bond}\n已解鎖：{unlocked}\n{next_line}"

    def _menu_ui(self, player: dict) -> str:
        bond = int(player.get("bond", 0))
        rows = [
            "🎴 **今晚命運牌**",
            self._status_lines(player),
            "",
            "1．甜蜜牌：交換一個小心意",
            "2．默契牌：看看我們會不會想到同一件事",
            "3．冒險骰子牌" if bond >= 6 else "3．🔒 冒險骰子牌：默契值 6 解鎖",
            "4．雙人故事牌" if bond >= 12 else "4．🔒 雙人故事牌：默契值 12 解鎖",
            "5．秘密任務牌" if bond >= 20 else "5．🔒 秘密任務牌：默契值 20 解鎖",
            "",
            "輸入 1–5 選牌；輸入 0 收牌。",
        ]
        return "\n".join(rows)

    @staticmethod
    def _card_ui(kind: str, card: dict, extra: str = "") -> str:
        lines = [
            f"🎴 **{CATEGORY_LABELS[kind]}｜《{card['title']}》**",
            card["prompt"],
            "",
        ]
        for k, v in card["choices"].items():
            lines.append(f"{k}．{v}")
        if extra:
            lines += ["", extra]
        return "\n".join(lines)

    @staticmethod
    def _turn(semantic_text: str, context: str, ui: str = "", log_text: str = "") -> dict:
        return {
            "handled": True,
            "semantic_text": semantic_text,
            "context": context,
            "ui": ui,
            "log_text": log_text or semantic_text,
        }

    def might_handle(self, message) -> bool:
        raw = str(getattr(message, "content", "") or "").strip()
        norm = self._normalize(raw)
        if raw.startswith("!命運牌"):
            return True
        state = self._load_state()
        session = self._get_session(state, message)
        if not session:
            return False

        phase = session.get("phase")
        # 遊戲等待時不吞正常聊天；只攔截明確有效的遊戲輸入。
        if phase == "between_cards":
            return norm in {"Z", "0", "取消", "結束"}
        if phase == "choose_category":
            return norm in {"1", "2", "3", "4", "5", "0", "取消", "結束"}
        if phase in {"sweet_choice", "sync_choice", "story_choice", "secret_choice"}:
            return norm in {"A", "B", "C", "0", "取消", "結束"}
        if phase == "sweet_share":
            # 任何文字都是分享，但指令不應誤變分享。
            return bool(raw) and not raw.startswith("!")
        if phase == "adventure_strategy":
            return norm in {"1", "2", "3", "0", "取消", "結束"}
        return False

    def _pick_card(self, kind: str) -> dict:
        source = {
            "sweet": SWEET_CARDS,
            "sync": SYNC_CARDS,
            "story": STORY_CARDS,
            "secret": SECRET_CARDS,
        }.get(kind)
        if not source:
            raise ValueError(kind)
        return RNG.choice(source)

    def _end(self, state: dict, message, player: dict) -> dict:
        self._clear_session(state, message)
        self._save_state(state)
        return self._turn(
            "大俠想先把今晚的命運牌收好。",
            "【命運牌狀態】本局已收牌。已完成的默契值保留；未完成牌不計分。"
            "妳不是遊戲主持人，請以女友小俠的自然口吻溫柔收束，不必解釋規則。",
            f"🃏 **本局先收好**\n已完成的牌與默契值保留；未完成的牌不計分。\n\n{self._status_lines(player)}",
            "命運牌本局已收好。",
        )

    async def process_message(self, message) -> dict:
        """
        所有需要遊戲回應的輸入都回傳「給主小俠」的語境。
        不在這裡 send，不在這裡呼叫 LLM。
        """
        raw = str(getattr(message, "content", "") or "").strip()
        state = self._load_state()
        player = self._player(state, message.author.id)
        session = self._get_session(state, message)
        norm = self._normalize(raw)

        # Command family
        if raw.startswith("!命運牌"):
            suffix = raw[len("!命運牌"):].strip()
            if suffix in {"狀態", "状态"}:
                self._save_state(state)
                return self._turn(
                    "大俠想看看我們今晚命運牌目前的默契值。",
                    "【命運牌狀態查詢】請自然、簡短地陪大俠看目前進度；不要把自己說成系統或主持人。",
                    self._status_lines(player),
                    "大俠查看命運牌狀態。",
                )
            if suffix in {"說明", "帮助", "幫助"}:
                self._save_state(state)
                return self._turn(
                    "大俠想聽你們的命運牌怎麼玩。",
                    "【命運牌說明】請用小俠自然口吻簡短說明：這是兩人偶爾玩的互動引子；"
                    "牌後可正常聊天，z 才問下一張，0 收牌。不要像操作手冊長篇講解。",
                    "🎴 **命運牌快速說明**\n"
                    "甜蜜牌：選題後分享一句話，小俠會回應。\n"
                    "默契牌：各自選 A/B/C，再揭曉。\n"
                    "牌與牌之間可正常聊天；輸入 z 才問下一張，0 收牌。",
                    "大俠查看命運牌說明。",
                )
            if suffix in {"結束", "结束", "收牌", "取消"}:
                if session:
                    return self._end(state, message, player)
                self._save_state(state)
                return self._turn(
                    "大俠想收牌，但現在沒有進行中的命運牌。",
                    "【命運牌】目前沒有開著的牌局。請自然回應，不必特別解釋系統。",
                    "🃏 目前沒有進行中的命運牌。",
                    "大俠查看命運牌狀態。",
                )
            if suffix:
                return self._turn(
                    "大俠剛剛輸入了命運牌指令。",
                    "【命運牌】請自然邀請他從下面牌型開始，不需要解釋未知指令。",
                    self._menu_ui(player),
                    "大俠打開命運牌。",
                )

            # !命運牌 = open or reopen menu; no need to reset a between-card session.
            self._put_session(state, message, {"phase": "choose_category", "pause_hint_shown": bool(session and session.get("pause_hint_shown"))})
            self._save_state(state)
            return self._turn(
                "大俠剛剛把今晚的命運牌拿出來，想和你一起玩。",
                "【命運牌當下】妳正在和大俠玩，但妳仍是同一個日常的小俠，不是主持人。"
                "先用一兩句自然、帶點期待的女友語氣接住他；不要重述卡面選項，卡面會另外顯示。",
                self._menu_ui(player),
                "大俠打開今晚命運牌。",
            )

        if not session:
            return {"handled": False}

        if norm in {"0", "取消", "結束"}:
            return self._end(state, message, player)

        phase = session.get("phase")

        if phase == "between_cards":
            if norm != "Z":
                return {"handled": False}
            session["phase"] = "choose_category"
            self._put_session(state, message, session)
            self._save_state(state)
            return self._turn(
                "大俠說 z，想再翻下一張牌。",
                "【命運牌當下】大俠在剛才的聊天後想再翻一張。"
                "請像同一個女友自然接住這個小動作，簡短帶著期待；不要重述卡面選項。",
                self._menu_ui(player),
                "大俠想翻下一張命運牌。",
            )

        if phase == "choose_category":
            mapping = {"1": "sweet", "2": "sync", "3": "adventure", "4": "story", "5": "secret"}
            kind = mapping.get(norm)
            if not kind:
                return {"handled": False}
            if kind not in self._unlocked(int(player["bond"])):
                self._save_state(state)
                need = {"adventure": 6, "story": 12, "secret": 20}[kind]
                return self._turn(
                    f"大俠想翻 {CATEGORY_LABELS[kind]}，但現在的默契值還差一點。",
                    f"【命運牌】這個牌型尚未解鎖，需要默契值 {need}。"
                    "請用女友小俠口吻俏皮但不挫折地接住他，不要主持人腔。",
                    f"🔒 {CATEGORY_LABELS[kind]}尚未解鎖：需要默契值 {need}。\n\n{self._status_lines(player)}",
                    f"大俠嘗試翻尚未解鎖的{CATEGORY_LABELS[kind]}。",
                )

            if kind == "adventure":
                session = {"phase": "adventure_strategy", "kind": kind, "xia_strategy": RNG.choice(["1", "2", "3"])}
                self._put_session(state, message, session)
                self._save_state(state)
                return self._turn(
                    "大俠選擇了冒險骰子牌。",
                    "【命運牌當下】妳已偷偷選好策略，但不能透露。"
                    "請用同一個小俠的俏皮語氣表示妳把底牌藏好了，別重述策略列表。",
                    "🎲 **冒險骰子牌**\n"
                    "1．穩穩骰：骰 1 顆六面骰\n"
                    "2．雙骰保守：骰 2 顆，取較低的一顆\n"
                    "3．撒嬌重擲：骰 2 次，取較高的一次",
                    "大俠選擇冒險骰子牌。",
                )

            card = self._pick_card(kind)
            phase_map = {"sweet": "sweet_choice", "sync": "sync_choice", "story": "story_choice", "secret": "secret_choice"}
            session = {"phase": phase_map[kind], "kind": kind, "card": card}
            if kind in {"sync", "secret"}:
                session["xia_choice"] = RNG.choice(list(card["choices"]))
            self._put_session(state, message, session)
            self._save_state(state)

            contextual = {
                "sweet": "請用自然女友口吻邀請大俠選一個想分享的方向；別把這變成任務。",
                "sync": "請自然說妳已經先選好，但不透露答案；別重述選項。",
                "story": "請像你們一起開始一個小情境那樣，等大俠先選方向；別預先展開故事。",
                "secret": "請帶點小心思，但別透露秘密答案、也別像主持人。",
            }[kind]
            return self._turn(
                f"大俠選擇翻 {CATEGORY_LABELS[kind]}。",
                f"【命運牌當下】抽到《{card['title']}》。{contextual}",
                self._card_ui(kind, card, "輸入 A、B 或 C。"),
                f"大俠翻到《{card['title']}》。",
            )

        if phase == "sweet_choice":
            card = session["card"]
            if norm not in card["choices"]:
                return {"handled": False}
            session["phase"] = "sweet_share"
            session["selected"] = norm
            self._put_session(state, message, session)
            self._save_state(state)
            topic = card["choices"][norm]
            return self._turn(
                f"大俠在《{card['title']}》選了「{topic}」。",
                "【命運牌當下】他選好要分享的方向，現在輪到妳真正聽他說。"
                "不要結算、不要加分、不要重述牌名；請像女友自然邀他把這件事說出來。",
                f"🕯️ **分享時間**\n大俠選了：{norm}．{topic}\n\n請直接用一句或一段話分享；輸入 0 可以收牌。",
                f"大俠選擇分享主題：{topic}。",
            )

        if phase == "sweet_share":
            # raw is actual relationship conversation, don't change it into a synthetic line.
            share = raw
            card = session["card"]
            selected = session.get("selected", "")
            topic = card["choices"].get(selected, "一件小事")
            player["bond"] = int(player["bond"]) + 1
            player["games_played"] = int(player["games_played"]) + 1
            player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
            session = {
                "phase": "between_cards",
                "pause_hint_shown": bool(session.get("pause_hint_shown", False)),
            }
            self._put_session(state, message, session)
            self._save_state(state)
            first_hint = not session.get("pause_hint_shown", False)
            # store the correct marker for subsequent states
            session["pause_hint_shown"] = True
            self._put_session(state, message, session)
            self._save_state(state)

            pause = (
                "🌙 這張牌先放在我們中間。想繼續聊就慢慢說；"
                "想再翻牌時輸入 z，想收牌輸入 0。"
                if first_hint else
                "想繼續聊就慢慢說；想翻下一張牌時輸入 z。"
            )
            return self._turn(
                share,
                "【命運牌當下】大俠剛剛真的分享了內容。"
                f"這是《{card['title']}》的「{topic}」。"
                "請完全以同一個日常女友小俠回應他的實際話語：先接住內容，再說妳自己的即時感受。"
                "遊戲只是背景，絕不能搶走你們正在說的話；不要重述牌名、題目、選項或分數。",
                f"✨ 本張完成｜默契值 +1\n{self._status_lines(player)}\n\n{pause}",
                f"大俠在甜蜜牌分享：{share[:400]}",
            )

        if phase in {"sync_choice", "secret_choice"}:
            card = session["card"]
            if norm not in card["choices"]:
                return {"handled": False}
            xia = session["xia_choice"]
            matched = norm == xia
            gained = 2 if matched else 1
            player["bond"] = int(player["bond"]) + gained
            player["games_played"] = int(player["games_played"]) + 1
            if matched:
                player["sync_hits"] = int(player["sync_hits"]) + 1
            player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
            first_hint = not bool(session.get("pause_hint_shown", False))
            new_session = {"phase": "between_cards", "pause_hint_shown": True}
            self._put_session(state, message, new_session)
            self._save_state(state)
            kind = session["kind"]
            pause = (
                "🌙 這張牌先放在我們中間。想繼續聊就慢慢說；想再翻牌時輸入 z，想收牌輸入 0。"
                if first_hint else "想繼續聊就慢慢說；想翻下一張牌時輸入 z。"
            )
            result = "剛好選到同一個答案" if matched else "選到不同答案"
            return self._turn(
                f"大俠在《{card['title']}》選了 {norm}；小俠先前選了 {xia}，你們{result}。",
                "【命運牌當下】結果已揭曉。請以同一個女友小俠的自然反應接住這件事："
                "相同時可以有默契與小得意；不同時把差異變成更認識彼此的一點趣味。"
                "不要重述卡面選項或像裁判公布結果。",
                f"✨ 本張完成｜默契值 +{gained}\n"
                f"大俠：{norm}．{card['choices'][norm]}\n"
                f"小俠：{xia}．{card['choices'][xia]}\n"
                f"{self._status_lines(player)}\n\n{pause}",
                f"命運牌《{card['title']}》揭曉。",
            )

        if phase == "story_choice":
            card = session["card"]
            if norm not in card["choices"]:
                return {"handled": False}
            player["bond"] = int(player["bond"]) + 2
            player["games_played"] = int(player["games_played"]) + 1
            player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
            first_hint = not bool(session.get("pause_hint_shown", False))
            self._put_session(state, message, {"phase": "between_cards", "pause_hint_shown": True})
            self._save_state(state)
            pause = (
                "🌙 這張牌先放在我們中間。想繼續聊就慢慢說；想再翻牌時輸入 z，想收牌輸入 0。"
                if first_hint else "想繼續聊就慢慢說；想翻下一張牌時輸入 z。"
            )
            selected = card["choices"][norm]
            return self._turn(
                f"大俠替你們的《{card['title']}》選了「{selected}」。",
                "【命運牌當下】大俠剛剛替你們的小情境選了方向。"
                "請像同一個小俠自然接住這個畫面，延續一兩個有感覺的細節，"
                "然後回到你們可以正常聊天的狀態。不要講解遊戲。",
                f"✨ 本張完成｜默契值 +2\n大俠選：{norm}．{selected}\n{self._status_lines(player)}\n\n{pause}",
                f"大俠替雙人故事選擇：{selected}。",
            )

        if phase == "adventure_strategy":
            if norm not in {"1", "2", "3"}:
                return {"handled": False}
            def roll(strategy: str):
                if strategy == "1":
                    n = RNG.randint(1, 6)
                    return n, f"穩穩骰 {n}"
                if strategy == "2":
                    a,b = RNG.randint(1, 6), RNG.randint(1, 6)
                    return min(a,b), f"雙骰保守 {a}、{b}，取 {min(a,b)}"
                a,b = RNG.randint(1, 6), RNG.randint(1, 6)
                return max(a,b), f"撒嬌重擲 {a}、{b}，取 {max(a,b)}"
            your, your_text = roll(norm)
            xia_s = session["xia_strategy"]
            xia, xia_text = roll(xia_s)
            if your > xia:
                gained = 2
                player["wins"] = int(player["wins"]) + 1
                outcome = "大俠贏了這局"
            elif your < xia:
                gained = 1
                outcome = "小俠這局剛好贏了"
            else:
                gained = 1
                outcome = "這局平手"
            player["bond"] = int(player["bond"]) + gained
            player["games_played"] = int(player["games_played"]) + 1
            player["last_played_at"] = datetime.now(TZ_TPE).isoformat(timespec="seconds")
            first_hint = not bool(session.get("pause_hint_shown", False))
            self._put_session(state, message, {"phase": "between_cards", "pause_hint_shown": True})
            self._save_state(state)
            pause = (
                "🌙 這張牌先放在我們中間。想繼續聊就慢慢說；想再翻牌時輸入 z，想收牌輸入 0。"
                if first_hint else "想繼續聊就慢慢說；想翻下一張牌時輸入 z。"
            )
            return self._turn(
                f"冒險骰子牌結算：大俠 {your}，小俠 {xia}，{outcome}。",
                "【命運牌當下】骰子結果已定。請以同一個女友小俠自然反應，"
                "可以俏皮或小得意，但不要像播報員公布比分，也不要假裝早知道骰子結果。",
                f"🎲 本張完成｜{outcome}｜默契值 +{gained}\n"
                f"大俠：{your_text}\n小俠：{xia_text}\n{self._status_lines(player)}\n\n{pause}",
                "命運牌冒險骰子結算。",
            )

        return {"handled": False}
