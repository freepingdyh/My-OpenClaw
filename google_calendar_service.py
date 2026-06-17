#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Calendar 自然語言服務
- 共用 Google OAuth refresh token
- 讀取、建立、修改、刪除事件
- Discord 多輪預覽／確認
- 不依賴 google-api-python-client
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types


TZ_NAME = os.environ.get("GOOGLE_TIMEZONE", "Asia/Taipei")
TZ = ZoneInfo(TZ_NAME)
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarError(RuntimeError):
    pass


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return default


def _extract_json(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise GoogleCalendarError("Gemini 沒有回傳可解析的 JSON")
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}


def _parse_iso(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise GoogleCalendarError("缺少日期或時間")
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(TZ).isoformat(timespec="seconds")


WEEKDAY_ZH = ("一", "二", "三", "四", "五", "六", "日")
WEEKDAY_NAME_ZH = (
    "星期一", "星期二", "星期三", "星期四",
    "星期五", "星期六", "星期日",
)
ZH_WEEKDAY_TO_INDEX = {
    "一": 0, "二": 1, "三": 2, "四": 3,
    "五": 4, "六": 5, "日": 6, "天": 6,
}


def _day_start(value: datetime) -> datetime:
    return value.astimezone(TZ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _week_monday(value: datetime) -> datetime:
    day = _day_start(value)
    return day - timedelta(days=day.weekday())


def _format_zh_date(value: datetime) -> str:
    value = value.astimezone(TZ)
    return (
        f"{value.year}年{value.month}月{value.day}日"
        f"（{WEEKDAY_NAME_ZH[value.weekday()]}）"
    )


def _relative_date_map(now: Optional[datetime] = None) -> dict[str, datetime]:
    """
    所有「本週／下週」都以台灣時區、週一到週日為一週。
    本週五永遠是本週一 + 4 天，不交給 LLM 做日期算術。
    """
    now = (now or datetime.now(TZ)).astimezone(TZ)
    today = _day_start(now)
    monday = _week_monday(now)

    result: dict[str, datetime] = {
        "今天": today,
        "今日": today,
        "明天": today + timedelta(days=1),
        "明日": today + timedelta(days=1),
        "後天": today + timedelta(days=2),
        "昨天": today - timedelta(days=1),
        "昨日": today - timedelta(days=1),
        "前天": today - timedelta(days=2),
        "本週末": monday + timedelta(days=5),
        "這週末": monday + timedelta(days=5),
        "下週末": monday + timedelta(days=12),
        "上週末": monday - timedelta(days=2),
    }

    for label, week_offset in (
        ("本週", 0),
        ("這週", 0),
        ("本星期", 0),
        ("這星期", 0),
        ("下週", 1),
        ("下星期", 1),
        ("上週", -1),
        ("上星期", -1),
    ):
        base = monday + timedelta(days=7 * week_offset)
        for zh, index in ZH_WEEKDAY_TO_INDEX.items():
            result[f"{label}{zh}"] = base + timedelta(days=index)

    return result


def _matched_relative_dates(
    text: str,
    now: Optional[datetime] = None,
) -> list[tuple[str, datetime]]:
    raw = str(text or "")
    mapping = _relative_date_map(now)

    # 長詞優先，避免「本週末」先匹配成其他片段。
    matches = []
    for token in sorted(mapping, key=len, reverse=True):
        if token in raw:
            matches.append((token, mapping[token]))

    # 去除同一位置語意重疊，例如同一句不應重複顯示「明天／明日」。
    deduped = []
    seen_dates = set()
    for token, value in matches:
        key = value.date().isoformat()
        if key in seen_dates:
            continue
        seen_dates.add(key)
        deduped.append((token, value))
    return deduped


def _annotate_relative_dates(
    text: str,
    now: Optional[datetime] = None,
) -> str:
    """
    在交給 Gemini 前加入不可誤解的絕對日期。
    原句仍保留，方便模型理解自然語意。
    """
    raw = str(text or "").strip()
    matches = _matched_relative_dates(raw, now)
    if not matches:
        return raw

    annotations = "；".join(
        f"{token}＝{value:%Y-%m-%d}（{WEEKDAY_NAME_ZH[value.weekday()]}）"
        for token, value in matches
    )
    return f"{raw}\n\n【程式已確定的日期，不可改算】{annotations}"


def _date_reference_table(now: Optional[datetime] = None) -> str:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    monday = _week_monday(now)
    next_monday = monday + timedelta(days=7)

    lines = [
        f"現在台灣時間：{now:%Y-%m-%d %H:%M:%S}（{WEEKDAY_NAME_ZH[now.weekday()]}）",
        f"今天：{now:%Y-%m-%d}",
        "本週（週一至週日）："
        + "、".join(
            f"週{WEEKDAY_ZH[index]}={monday + timedelta(days=index):%Y-%m-%d}"
            for index in range(7)
        ),
        "下週（週一至週日）："
        + "、".join(
            f"週{WEEKDAY_ZH[index]}={next_monday + timedelta(days=index):%Y-%m-%d}"
            for index in range(7)
        ),
    ]
    return "\n".join(lines)


def _is_direct_date_question(text: str) -> bool:
    raw = re.sub(r"\s+", "", str(text or ""))
    if not _matched_relative_dates(raw):
        return False
    question_terms = (
        "幾號", "日期", "哪一天", "哪天", "星期幾",
        "是幾月幾日", "是哪一天", "是什麼日子",
    )
    return any(term in raw for term in question_terms)


def _direct_date_answer(text: str) -> Optional[str]:
    matches = _matched_relative_dates(text)
    if not matches:
        return None
    lines = [
        f"📅 **{token}**是 **{_format_zh_date(value)}**。"
        for token, value in matches
    ]
    return "\n".join(lines)


def _event_start_dt(event: dict) -> Optional[datetime]:
    start = event.get("start", {}) or {}
    value = start.get("dateTime")
    if value:
        try:
            return _parse_iso(value)
        except Exception:
            return None
    date_value = start.get("date")
    if date_value:
        try:
            return datetime.fromisoformat(date_value).replace(tzinfo=TZ)
        except Exception:
            return None
    return None


def _event_end_dt(event: dict) -> Optional[datetime]:
    end = event.get("end", {}) or {}
    value = end.get("dateTime")
    if value:
        try:
            return _parse_iso(value)
        except Exception:
            return None
    date_value = end.get("date")
    if date_value:
        try:
            return datetime.fromisoformat(date_value).replace(tzinfo=TZ)
        except Exception:
            return None
    return None


class GoogleCalendarClient:
    """同步 REST client；Discord async 流程會透過 asyncio.to_thread 呼叫。"""

    def __init__(self, calendar_id: Optional[str] = None):
        self.client_id = _env_first("GOOGLE_CLIENT_ID", "Google_OAuth")
        self.client_secret = _env_first("GOOGLE_CLIENT_SECRET")
        self.refresh_token = _env_first(
            "GOOGLE_REFRESH_TOKEN",
            "Google_Refresh_Token",
        )
        self.calendar_id = (
            calendar_id
            or _env_first("GOOGLE_CALENDAR_ID", default="primary")
            or "primary"
        )
        self._access_token = ""
        self._access_token_expiry = datetime.min.replace(tzinfo=TZ)

    @property
    def ready(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def status_text(self) -> str:
        missing = []
        if not self.client_id:
            missing.append("GOOGLE_CLIENT_ID/Google_OAuth")
        if not self.client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not self.refresh_token:
            missing.append("GOOGLE_REFRESH_TOKEN/Google_Refresh_Token")
        if missing:
            return "not_ready | missing=" + ",".join(missing)
        return f"ready | calendar={self.calendar_id} | timezone={TZ_NAME}"

    def _get_access_token(self, force_refresh: bool = False) -> str:
        now = datetime.now(TZ)
        if (
            not force_refresh
            and self._access_token
            and now < self._access_token_expiry
        ):
            return self._access_token

        if not self.ready:
            raise GoogleCalendarError(
                "Google OAuth 環境變數不完整：" + self.status_text()
            )

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        request = urllib.request.Request(
            TOKEN_URL,
            data=urllib.parse.urlencode(params).encode("utf-8"),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GoogleCalendarError(
                f"Google OAuth 更新 access token 失敗 HTTP {exc.code}: {body}"
            ) from exc
        except Exception as exc:
            raise GoogleCalendarError(
                f"Google OAuth 更新 access token 失敗：{exc}"
            ) from exc

        token = payload.get("access_token")
        if not token:
            raise GoogleCalendarError(
                f"Google OAuth 回應缺少 access_token：{payload}"
            )
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._access_token_expiry = now + timedelta(
            seconds=max(60, expires_in - 120)
        )
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        retry_auth: bool = True,
    ) -> dict:
        encoded_path = path
        url = CALENDAR_API_BASE + encoded_path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)

        data = None
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401 and retry_auth:
                self._get_access_token(force_refresh=True)
                return self._request(
                    method,
                    path,
                    params=params,
                    body=body,
                    retry_auth=False,
                )
            raise GoogleCalendarError(
                f"Google Calendar API HTTP {exc.code}: {response_body}"
            ) from exc
        except Exception as exc:
            raise GoogleCalendarError(
                f"Google Calendar API 呼叫失敗：{exc}"
            ) from exc

    def list_events(
        self,
        start: datetime,
        end: datetime,
        *,
        query: str = "",
        max_results: int = 50,
    ) -> list[dict]:
        params = {
            "timeMin": _rfc3339(start),
            "timeMax": _rfc3339(end),
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeZone": TZ_NAME,
            "maxResults": str(max_results),
        }
        if query:
            params["q"] = query
        path = (
            "/calendars/"
            + urllib.parse.quote(self.calendar_id, safe="")
            + "/events"
        )
        payload = self._request("GET", path, params=params)
        return payload.get("items", []) or []

    def create_event(self, payload: dict) -> dict:
        path = (
            "/calendars/"
            + urllib.parse.quote(self.calendar_id, safe="")
            + "/events"
        )
        body = {
            "summary": payload["title"],
            "location": payload.get("location", ""),
            "description": payload.get("description", ""),
            "start": {
                "dateTime": _rfc3339(_parse_iso(payload["start"])),
                "timeZone": TZ_NAME,
            },
            "end": {
                "dateTime": _rfc3339(_parse_iso(payload["end"])),
                "timeZone": TZ_NAME,
            },
        }
        if payload.get("recurrence"):
            body["recurrence"] = payload["recurrence"]
        return self._request("POST", path, body=body)

    def patch_event(self, event_id: str, changes: dict) -> dict:
        path = (
            "/calendars/"
            + urllib.parse.quote(self.calendar_id, safe="")
            + "/events/"
            + urllib.parse.quote(event_id, safe="")
        )
        body = {}
        if "title" in changes:
            body["summary"] = changes["title"]
        if "location" in changes:
            body["location"] = changes["location"]
        if "description" in changes:
            body["description"] = changes["description"]
        if changes.get("start"):
            body["start"] = {
                "dateTime": _rfc3339(_parse_iso(changes["start"])),
                "timeZone": TZ_NAME,
            }
        if changes.get("end"):
            body["end"] = {
                "dateTime": _rfc3339(_parse_iso(changes["end"])),
                "timeZone": TZ_NAME,
            }
        if not body:
            raise GoogleCalendarError("沒有可修改的欄位")
        return self._request("PATCH", path, body=body)

    def delete_event(self, event_id: str) -> None:
        path = (
            "/calendars/"
            + urllib.parse.quote(self.calendar_id, safe="")
            + "/events/"
            + urllib.parse.quote(event_id, safe="")
        )
        self._request("DELETE", path)

    def today_events_text(self) -> str:
        now = datetime.now(TZ)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = self.list_events(start, end, max_results=50)
        if not events:
            return "今日沒有設定行程"

        lines = []
        for event in events:
            title = event.get("summary", "（無標題）")
            location = str(event.get("location", "") or "").strip()
            description = re.sub(
                r"<[^<]+>",
                "",
                str(event.get("description", "") or "").strip(),
            )
            start_dt = _event_start_dt(event)
            end_dt = _event_end_dt(event)
            if event.get("start", {}).get("date"):
                lines.append(f"• 【{title}】（全天）")
            elif start_dt and end_dt:
                lines.append(
                    f"• 【{title}】（{start_dt:%H:%M}~{end_dt:%H:%M}）"
                )
            else:
                lines.append(f"• 【{title}】")
            if location:
                lines.append(f"  📍 {location}")
            if description:
                lines.append(f"  📝 {description}")
        return "\n".join(lines)


@dataclass
class PendingAction:
    action: str
    payload: dict
    expires_at: datetime
    source_text: str


class GoogleCalendarService:
    """
    Discord 自然語言 Calendar 助手。
    寫入操作全部需要「確認」；查詢可直接執行。
    """

    def __init__(
        self,
        architect_channel_id: int,
        *,
        additional_channel_ids: Optional[list[int]] = None,
        gemini_client: Optional[genai.Client] = None,
        calendar_id: Optional[str] = None,
    ):
        self.architect_channel_id = int(architect_channel_id)
        self.allowed_channel_ids = {self.architect_channel_id}
        for channel_id in additional_channel_ids or []:
            try:
                self.allowed_channel_ids.add(int(channel_id))
            except Exception:
                pass
        self.client = GoogleCalendarClient(calendar_id=calendar_id)
        self.gemini = gemini_client or genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY")
        )
        self.model = os.environ.get(
            "GOOGLE_CALENDAR_ROUTER_MODEL",
            "gemini-2.5-flash",
        )
        self.sessions: dict[tuple[int, int], PendingAction] = {}
        self.session_minutes = max(
            2,
            min(
                60,
                int(
                    os.environ.get(
                        "GOOGLE_CALENDAR_CONFIRM_MINUTES",
                        "15",
                    )
                ),
            ),
        )

    def status_text(self) -> str:
        channels = ",".join(str(value) for value in sorted(self.allowed_channel_ids))
        return (
            self.client.status_text()
            + f" | router={self.model}"
            + f" | confirm={self.session_minutes}m"
            + f" | channels={channels}"
        )

    def _key(self, message) -> tuple[int, int]:
        return (int(message.channel.id), int(message.author.id))

    def _pending(self, message) -> Optional[PendingAction]:
        key = self._key(message)
        item = self.sessions.get(key)
        if not item:
            return None
        if datetime.now(TZ) >= item.expires_at:
            self.sessions.pop(key, None)
            return None
        return item

    def _save_pending(
        self,
        message,
        action: str,
        payload: dict,
        source_text: str,
    ) -> PendingAction:
        item = PendingAction(
            action=action,
            payload=payload,
            source_text=source_text,
            expires_at=datetime.now(TZ)
            + timedelta(minutes=self.session_minutes),
        )
        self.sessions[self._key(message)] = item
        return item

    async def _route(
        self,
        user_text: str,
        pending: Optional[PendingAction],
    ) -> dict:
        now = datetime.now(TZ)
        deterministic_user_text = _annotate_relative_dates(user_text, now)
        date_reference = _date_reference_table(now)
        pending_json = (
            json.dumps(
                {
                    "action": pending.action,
                    "payload": pending.payload,
                },
                ensure_ascii=False,
            )
            if pending
            else "無"
        )
        prompt = f"""
你是 Google Calendar 意圖解析器。
時區：{TZ_NAME}

【Python 已計算的日期基準，具有最高優先級】
{date_reference}

使用者訊息：
{deterministic_user_text}

待確認操作：
{pending_json}

判斷 intent：
- general：不是行事曆需求。
- create：新增行程。
- list：查詢行程。
- update：修改既有行程。
- delete：刪除既有行程。
- confirm：確認目前待確認操作。
- cancel：取消目前待確認操作。
- revise_pending：修改目前待確認操作內容。
- clarify：是行事曆需求但缺少必要資訊。

要求：
1. 日期不得自行心算；凡訊息中已有「程式已確定的日期」，必須逐字採用。
2. 「本週」固定指目前週一至週日；「下週」固定指下一個週一至週日。
3. 使用 RFC3339 +08:00。
3. 建立事件必須有 title、start、end。
4. 使用者只給單一時間，例如「明早八點開會」，預設 60 分鐘。
5. 「八點四十到九點，台南大學，走路運動」：
   title=走路運動，location=台南大學。
6. 不可將一般技術問題誤判成行事曆。
7. 修改或刪除時，target_query 保存原事件名稱／地點關鍵字；
   search_start/search_end 提供合理搜尋區間。
8. 查詢「明天有哪些行程」要回 list。
9. 待確認存在時，「改成九點開始」為 revise_pending；
   「確認」「好，建立」為 confirm；「取消」為 cancel。

只回傳 JSON：
{{
  "intent": "general",
  "action": "",
  "title": "",
  "location": "",
  "description": "",
  "start": "",
  "end": "",
  "search_start": "",
  "search_end": "",
  "target_query": "",
  "changes": {{
    "title": "",
    "location": "",
    "description": "",
    "start": "",
    "end": ""
  }},
  "clarifying_question": ""
}}
"""
        response = await asyncio.to_thread(
            self.gemini.models.generate_content,
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        route = _extract_json(response.text)
        return self._enforce_deterministic_route_dates(
            route,
            user_text=user_text,
            now=now,
        )

    def _enforce_deterministic_route_dates(
        self,
        route: dict,
        *,
        user_text: str,
        now: Optional[datetime] = None,
    ) -> dict:
        """
        Gemini 若仍把「本週五」算錯，程式會把 start/end/search range
        平移到 Python 算出的正確日期，保留原本時間與時長。
        """
        matches = _matched_relative_dates(user_text, now)
        if not matches or not isinstance(route, dict):
            return route

        # 一句建立／修改指令通常以第一個明確相對日期為事件日期。
        target_day = matches[0][1].date()

        def move_iso_to_target(value: Any) -> Any:
            if not value:
                return value
            try:
                original = _parse_iso(value)
            except Exception:
                return value
            corrected = original.replace(
                year=target_day.year,
                month=target_day.month,
                day=target_day.day,
            )
            return _rfc3339(corrected)

        intent = str(route.get("intent", "") or "")
        if intent == "create":
            route["start"] = move_iso_to_target(route.get("start"))
            route["end"] = move_iso_to_target(route.get("end"))

        elif intent == "update":
            changes = route.get("changes")
            if isinstance(changes, dict):
                changes["start"] = move_iso_to_target(changes.get("start"))
                changes["end"] = move_iso_to_target(changes.get("end"))
                route["changes"] = changes

        if intent in {"list", "update", "delete"}:
            # 搜尋區間若有相對日期，至少覆蓋該日全天。
            start_of_day = datetime.combine(
                target_day,
                datetime.min.time(),
                tzinfo=TZ,
            )
            route["search_start"] = _rfc3339(start_of_day)
            route["search_end"] = _rfc3339(
                start_of_day + timedelta(days=1)
            )

        return route


    async def _revise_pending(
        self,
        user_text: str,
        pending: PendingAction,
    ) -> dict:
        now = datetime.now(TZ)
        deterministic_user_text = _annotate_relative_dates(user_text, now)
        date_reference = _date_reference_table(now)
        prompt = f"""
時區：{TZ_NAME}
【Python 已計算的日期基準，具有最高優先級】
{date_reference}
目前待確認操作：
{json.dumps({"action": pending.action, "payload": pending.payload}, ensure_ascii=False)}

使用者補充：
{deterministic_user_text}

請將補充內容合併進 payload，不可刪除未被修改的欄位。
若只改開始時間且原事件有固定時長，維持原時長並同步更新 end。
只回傳 JSON：
{{
  "payload": {{}},
  "clarifying_question": ""
}}
"""
        response = await asyncio.to_thread(
            self.gemini.models.generate_content,
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        result = _extract_json(response.text)
        payload = result.get("payload")
        if not isinstance(payload, dict):
            raise GoogleCalendarError("無法解析修改後的行程內容")

        matches = _matched_relative_dates(user_text, now)
        if matches:
            target_day = matches[0][1].date()
            for key in ("start", "end"):
                if payload.get(key):
                    try:
                        original = _parse_iso(payload[key])
                        corrected = original.replace(
                            year=target_day.year,
                            month=target_day.month,
                            day=target_day.day,
                        )
                        payload[key] = _rfc3339(corrected)
                    except Exception:
                        pass
            changes = payload.get("changes")
            if isinstance(changes, dict):
                for key in ("start", "end"):
                    if changes.get(key):
                        try:
                            original = _parse_iso(changes[key])
                            corrected = original.replace(
                                year=target_day.year,
                                month=target_day.month,
                                day=target_day.day,
                            )
                            changes[key] = _rfc3339(corrected)
                        except Exception:
                            pass
                payload["changes"] = changes

        result["payload"] = payload
        return result

    def _format_event(self, event: dict, index: Optional[int] = None) -> str:
        title = event.get("summary", "（無標題）")
        start_dt = _event_start_dt(event)
        end_dt = _event_end_dt(event)
        location = str(event.get("location", "") or "").strip()
        prefix = f"{index}. " if index is not None else ""
        if event.get("start", {}).get("date"):
            time_text = "全天"
        elif start_dt and end_dt:
            time_text = (
                f"{start_dt:%Y-%m-%d %H:%M}–{end_dt:%H:%M}"
            )
        else:
            time_text = "時間不明"
        line = f"{prefix}**{title}**｜{time_text}"
        if location:
            line += f"｜📍 {location}"
        return line

    def _format_preview(self, action: str, payload: dict) -> str:
        if action == "create":
            start = _parse_iso(payload["start"])
            end = _parse_iso(payload["end"])
            return (
                "📅 **準備新增行程**\n"
                f"標題：{payload.get('title') or '（無標題）'}\n"
                f"日期：{start:%Y-%m-%d}\n"
                f"時間：{start:%H:%M}–{end:%H:%M}\n"
                f"地點：{payload.get('location') or '未設定'}\n"
                f"說明：{payload.get('description') or '無'}\n\n"
                + self._format_numeric_controls("create")
            )

        event = payload.get("event", {})
        base = self._format_event(event)
        if action == "delete":
            return (
                "🗑️ **準備刪除行程**\n"
                f"{base}"
                + self._format_numeric_controls("delete")
            )

        changes = payload.get("changes", {})
        lines = [
            "✏️ **準備修改行程**",
            f"原行程：{base}",
        ]
        if changes.get("title"):
            lines.append(f"新標題：{changes['title']}")
        if changes.get("start"):
            start = _parse_iso(changes["start"])
            lines.append(f"新開始：{start:%Y-%m-%d %H:%M}")
        if changes.get("end"):
            end = _parse_iso(changes["end"])
            lines.append(f"新結束：{end:%Y-%m-%d %H:%M}")
        if changes.get("location"):
            lines.append(f"新地點：{changes['location']}")
        if changes.get("description"):
            lines.append(f"新說明：{changes['description']}")
        return "\n".join(lines) + self._format_numeric_controls("update")

    def _default_search_range(self, route: dict) -> tuple[datetime, datetime]:
        now = datetime.now(TZ)
        start_raw = route.get("search_start")
        end_raw = route.get("search_end")
        if start_raw:
            start = _parse_iso(start_raw)
        else:
            start = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            ) - timedelta(days=1)
        if end_raw:
            end = _parse_iso(end_raw)
        else:
            end = start + timedelta(days=62)
        if end <= start:
            end = start + timedelta(days=1)
        return start, end

    def _score_event(self, event: dict, query: str) -> int:
        terms = [
            term
            for term in re.split(r"[\s，,、]+", str(query or "").strip())
            if term
        ]
        blob = " ".join(
            [
                str(event.get("summary", "") or ""),
                str(event.get("location", "") or ""),
                str(event.get("description", "") or ""),
            ]
        ).lower()
        if not terms:
            return 1
        return sum(3 if term.lower() in blob else 0 for term in terms)

    async def _find_candidates(self, route: dict) -> list[dict]:
        start, end = self._default_search_range(route)
        query = str(route.get("target_query", "") or "").strip()
        events = await asyncio.to_thread(
            self.client.list_events,
            start,
            end,
            query="",
            max_results=100,
        )
        scored = [
            (self._score_event(event, query), event)
            for event in events
        ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(
            key=lambda item: (
                -item[0],
                _event_start_dt(item[1]) or datetime.max.replace(tzinfo=TZ),
            )
        )
        return [event for _, event in scored[:10]]

    @staticmethod
    def _direct_control_intent(user_text: str, pending: Optional[PendingAction]):
        """
        對待確認狀態直接解析，不再把「確認」交給 Gemini 猜。
        """
        raw = re.sub(r"\s+", "", str(user_text or "")).lower()
        if not pending:
            return None

        if raw in {"0", "取消", "不要", "算了", "取消操作"}:
            return "cancel"

        if raw in {
            "1", "確認", "確認建立", "確認修改", "確認刪除",
            "確定", "好", "執行", "建立", "送出",
        }:
            return "confirm"

        if raw in {"2", "修改", "修改內容", "我要修改"}:
            return "request_revision"

        if re.fullmatch(r"\d+", raw):
            return ("number", int(raw))

        return None

    def _format_numeric_controls(self, action: str) -> str:
        verb = {
            "create": "建立",
            "update": "修改",
            "delete": "刪除",
        }.get(action, "執行")
        return (
            f"\n\n請輸入：\n"
            f"**1**＝確認{verb}\n"
            f"**2**＝修改內容\n"
            f"**0**＝取消"
        )

    async def _handle_candidate_selection(
        self,
        message,
        pending: PendingAction,
        selected_number: int,
    ) -> bool:
        candidates = pending.payload.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            self.sessions.pop(self._key(message), None)
            await message.channel.send("⚠️ 候選行程已失效，請重新操作。")
            return True

        if selected_number < 1 or selected_number > len(candidates):
            await message.channel.send(
                f"請輸入 **1～{len(candidates)}** 選擇行程，或輸入 **0** 取消。"
            )
            return True

        event = candidates[selected_number - 1]
        target_action = pending.payload.get("target_action")

        if target_action == "delete":
            payload = {"event": event}
        elif target_action == "update":
            changes = pending.payload.get("changes", {})
            if not isinstance(changes, dict) or not changes:
                await message.channel.send(
                    "已選取行程，但尚未指定修改內容。"
                    "請直接輸入，例如：「改成上午九點到九點半」。"
                )
                pending.payload = {
                    "event": event,
                    "changes": {},
                    "awaiting_update_details": True,
                }
                pending.action = "update"
                pending.expires_at = datetime.now(TZ) + timedelta(
                    minutes=self.session_minutes
                )
                return True
            payload = {"event": event, "changes": changes}
        else:
            self.sessions.pop(self._key(message), None)
            await message.channel.send("⚠️ 無法判斷要修改或刪除，請重新操作。")
            return True

        pending.action = target_action
        pending.payload = payload
        pending.expires_at = datetime.now(TZ) + timedelta(
            minutes=self.session_minutes
        )
        await message.channel.send(
            self._format_preview(target_action, payload)
        )
        return True


    async def _execute(self, pending: PendingAction) -> dict:
        if pending.action == "create":
            return await asyncio.to_thread(
                self.client.create_event,
                pending.payload,
            )
        if pending.action == "update":
            event = pending.payload["event"]
            return await asyncio.to_thread(
                self.client.patch_event,
                event["id"],
                pending.payload["changes"],
            )
        if pending.action == "delete":
            event = pending.payload["event"]
            await asyncio.to_thread(
                self.client.delete_event,
                event["id"],
            )
            return event
        raise GoogleCalendarError(
            f"未知 Calendar 操作：{pending.action}"
        )

    async def handle_message(self, message) -> bool:
        if int(getattr(message.channel, "id", 0)) not in self.allowed_channel_ids:
            return False
        if getattr(message.author, "bot", False):
            return False

        user_text = str(message.content or "").strip()
        if not user_text or user_text.startswith(("!", "/")):
            return False

        pending = self._pending(message)

        # 純日期詢問直接由 Python 回答，不讓一般小夏或 Calendar LLM 心算。
        if not pending and _is_direct_date_question(user_text):
            answer = _direct_date_answer(user_text)
            if answer:
                await message.channel.send(answer)
                return True

        # 待確認狀態優先採用確定性指令，不把 0/1/2/確認 交給 LLM。
        direct_control = self._direct_control_intent(user_text, pending)
        if direct_control == "cancel":
            self.sessions.pop(self._key(message), None)
            await message.channel.send("🗑️ 已取消本次 Calendar 操作。")
            return True

        if direct_control == "request_revision":
            await message.channel.send(
                "✏️ 請直接輸入要修改的內容，例如："
                "「改成上午九點到九點半」或「地點改成台南大學操場」。"
            )
            return True

        if isinstance(direct_control, tuple) and direct_control[0] == "number":
            if pending and pending.action == "select_candidate":
                return await self._handle_candidate_selection(
                    message,
                    pending,
                    direct_control[1],
                )

        if direct_control == "confirm":
            intent = "confirm"
            route = {"intent": "confirm"}
        else:
            route = await self._route(user_text, pending)
            intent = str(route.get("intent", "general") or "general")

        if intent == "general":
            return False

        if intent == "cancel":
            if pending:
                self.sessions.pop(self._key(message), None)
                await message.channel.send("🗑️ 已取消本次 Calendar 操作。")
            else:
                await message.channel.send("目前沒有等待確認的 Calendar 操作。")
            return True

        if intent == "confirm":
            if not pending:
                await message.channel.send(
                    "目前沒有等待確認的 Calendar 操作，請先描述要建立、修改或刪除的行程。"
                )
                return True
            try:
                result = await self._execute(pending)
                self.sessions.pop(self._key(message), None)
                title = result.get("summary", "（無標題）")
                html_link = result.get("htmlLink", "")
                verb = {
                    "create": "建立",
                    "update": "修改",
                    "delete": "刪除",
                }[pending.action]
                reply = f"✅ 行程已{verb}：**{title}**"
                if html_link and pending.action != "delete":
                    reply += f"\n[在 Google Calendar 開啟]({html_link})"
                await message.channel.send(reply)
            except Exception as exc:
                await message.channel.send(f"❌ Calendar 操作失敗：{exc}")
            return True

        if (
            pending
            and pending.action == "update"
            and pending.payload.get("awaiting_update_details")
            and direct_control is None
        ):
            try:
                revised = await self._revise_pending(user_text, pending)
                question = str(
                    revised.get("clarifying_question", "") or ""
                ).strip()
                if question:
                    await message.channel.send(f"📅 {question}")
                    return True
                payload = revised.get("payload", {})
                if not payload.get("event"):
                    payload["event"] = pending.payload.get("event")
                payload.pop("awaiting_update_details", None)
                pending.payload = payload
                pending.expires_at = datetime.now(TZ) + timedelta(
                    minutes=self.session_minutes
                )
                await message.channel.send(
                    self._format_preview("update", pending.payload)
                )
            except Exception as exc:
                await message.channel.send(f"❌ 行程調整失敗：{exc}")
            return True

        if intent == "revise_pending":
            if not pending:
                await message.channel.send(
                    "目前沒有可修改的待確認行程，請重新描述完整需求。"
                )
                return True
            try:
                revised = await self._revise_pending(user_text, pending)
                question = str(
                    revised.get("clarifying_question", "") or ""
                ).strip()
                if question:
                    await message.channel.send(f"📅 {question}")
                    return True
                pending.payload = revised["payload"]
                pending.expires_at = datetime.now(TZ) + timedelta(
                    minutes=self.session_minutes
                )
                await message.channel.send(
                    self._format_preview(pending.action, pending.payload)
                )
            except Exception as exc:
                await message.channel.send(f"❌ 行程調整失敗：{exc}")
            return True

        if intent == "clarify":
            question = (
                str(route.get("clarifying_question", "") or "").strip()
                or "請補充行程日期、開始時間、結束時間與標題。"
            )
            await message.channel.send(f"📅 {question}")
            return True

        if intent == "list":
            try:
                start, end = self._default_search_range(route)
                events = await asyncio.to_thread(
                    self.client.list_events,
                    start,
                    end,
                    query=str(route.get("target_query", "") or ""),
                    max_results=50,
                )
                if not events:
                    await message.channel.send("📅 指定期間沒有行程。")
                else:
                    lines = ["📅 **Google Calendar 行程**"]
                    for index, event in enumerate(events[:20], start=1):
                        lines.append(self._format_event(event, index))
                    if len(events) > 20:
                        lines.append(f"另有 {len(events) - 20} 筆未顯示。")
                    await message.channel.send("\n".join(lines)[:1900])
            except Exception as exc:
                await message.channel.send(f"❌ Calendar 查詢失敗：{exc}")
            return True

        if intent == "create":
            payload = {
                "title": str(route.get("title", "") or "").strip(),
                "location": str(route.get("location", "") or "").strip(),
                "description": str(
                    route.get("description", "") or ""
                ).strip(),
                "start": str(route.get("start", "") or "").strip(),
                "end": str(route.get("end", "") or "").strip(),
            }
            if not payload["title"] or not payload["start"] or not payload["end"]:
                await message.channel.send(
                    "📅 我還缺少標題或完整時間，請再說一次，例如："
                    "「明天早上八點四十到九點，台南大學，走路運動」。"
                )
                return True
            try:
                if _parse_iso(payload["end"]) <= _parse_iso(payload["start"]):
                    raise GoogleCalendarError("結束時間必須晚於開始時間")
                self._save_pending(
                    message,
                    "create",
                    payload,
                    user_text,
                )
                await message.channel.send(
                    self._format_preview("create", payload)
                )
            except Exception as exc:
                await message.channel.send(f"❌ 行程時間解析失敗：{exc}")
            return True

        if intent in {"update", "delete"}:
            try:
                candidates = await self._find_candidates(route)
                if not candidates:
                    await message.channel.send(
                        "🔎 找不到符合條件的 Calendar 行程，請提供更明確的日期或標題。"
                    )
                    return True
                if len(candidates) > 1:
                    shown = candidates[:8]
                    changes = route.get("changes", {})
                    if not isinstance(changes, dict):
                        changes = {}
                    changes = {
                        key: value
                        for key, value in changes.items()
                        if value not in ("", None)
                    }
                    self._save_pending(
                        message,
                        "select_candidate",
                        {
                            "target_action": intent,
                            "candidates": shown,
                            "changes": changes,
                        },
                        user_text,
                    )
                    lines = [
                        f"🔎 找到 {len(shown)} 筆可能行程，請直接輸入編號選擇："
                    ]
                    for index, event in enumerate(shown, start=1):
                        lines.append(self._format_event(event, index))
                    lines.append("\n輸入 **0** 取消。")
                    await message.channel.send("\n".join(lines)[:1900])
                    return True

                event = candidates[0]
                if intent == "delete":
                    payload = {"event": event}
                else:
                    changes = route.get("changes", {})
                    if not isinstance(changes, dict):
                        changes = {}
                    changes = {
                        key: value
                        for key, value in changes.items()
                        if value not in ("", None)
                    }
                    if not changes:
                        await message.channel.send(
                            "✏️ 找到行程，但還不知道要修改什麼。"
                        )
                        return True
                    payload = {
                        "event": event,
                        "changes": changes,
                    }
                self._save_pending(
                    message,
                    intent,
                    payload,
                    user_text,
                )
                await message.channel.send(
                    self._format_preview(intent, payload)
                )
            except Exception as exc:
                await message.channel.send(f"❌ Calendar 搜尋失敗：{exc}")
            return True

        return False
