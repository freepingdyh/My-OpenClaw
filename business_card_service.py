import os
import io
import re
import json
import uuid
import base64
import mimetypes
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib.parse import quote

import aiohttp
import discord
from google import genai
from google.genai import types


TZ_TPE = timezone(timedelta(hours=8))

MAIN_HEADERS = [
    "person_id", "created_at", "updated_at", "uploaded_by", "discord_message_url",
    "card_front_image_url", "card_back_image_url", "name_zh", "name_en",
    "primary_organization", "primary_department", "primary_job_title",
    "affiliations_json", "mobile", "phone", "phone_extension", "fax", "email",
    "postal_code", "address", "websites", "line_id", "tax_id", "card_language",
    "ocr_confidence", "match_status", "review_status", "raw_extracted_text", "notes",
]

HISTORY_HEADERS = [
    "history_id", "person_id", "archived_at", "change_reason",
    "replaced_by_message_url", "name_zh", "name_en", "primary_organization",
    "primary_department", "primary_job_title", "affiliations_json", "mobile",
    "phone", "phone_extension", "fax", "email", "postal_code", "address",
    "websites", "line_id", "tax_id", "card_front_image_url",
    "card_back_image_url", "raw_extracted_text", "notes",
]


def _now_str() -> str:
    return datetime.now(TZ_TPE).strftime("%Y-%m-%d %H:%M:%S")


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _normalize_phone(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _json_text(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _extract_json(raw: str) -> dict:
    value = str(raw or "").strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(value)
    except Exception:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise ValueError("Gemini 未回傳有效 JSON")
        return json.loads(match.group(0))


def _message_url(message: discord.Message) -> str:
    if not message.guild:
        return ""
    return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"


class GoogleWorkspaceClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        spreadsheet_id: str,
        main_sheet: str,
        history_sheet: str,
        drive_folder_id: str,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.spreadsheet_id = spreadsheet_id
        self.main_sheet = main_sheet
        self.history_sheet = history_sheet
        self.drive_folder_id = drive_folder_id
        self._access_token = ""
        self._token_expiry = 0.0
        self._lock = asyncio.Lock()
        self._formatted_sheet_names = set()

    async def access_token(self) -> str:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if self._access_token and now < self._token_expiry - 60:
                return self._access_token

            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://oauth2.googleapis.com/token",
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 300:
                        raise RuntimeError(f"Google OAuth 更新失敗：{response.status} {data}")
                    self._access_token = data["access_token"]
                    self._token_expiry = now + int(data.get("expires_in", 3600))
                    return self._access_token

    async def _request_json(self, method: str, url: str, **kwargs) -> dict:
        token = await self.access_token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
                **kwargs,
            ) as response:
                raw = await response.text()
                try:
                    data = json.loads(raw) if raw else {}
                except Exception:
                    data = {"raw": raw}
                if response.status >= 300:
                    raise RuntimeError(f"Google API 失敗：{response.status} {data}")
                return data

    async def read_table(self, sheet_name: str) -> tuple[list[str], list[dict]]:
        range_name = aiohttp.helpers.quote(f"{sheet_name}!A:ZZ", safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.spreadsheet_id}/values/{range_name}"
            f"?valueRenderOption=FORMULA"
        )
        data = await self._request_json("GET", url)
        values = data.get("values", [])
        if not values:
            return [], []
        headers = [str(x).strip() for x in values[0]]
        rows = []
        for sheet_row_number, raw_row in enumerate(values[1:], start=2):
            row = {
                headers[index]: raw_row[index] if index < len(raw_row) else ""
                for index in range(len(headers))
            }
            row["_sheet_row_number"] = sheet_row_number
            rows.append(row)
        return headers, rows

    async def append_row(self, sheet_name: str, headers: list[str], row: dict) -> None:
        range_name = aiohttp.helpers.quote(f"{sheet_name}!A1", safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}"
            f"/values/{range_name}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        values = [[row.get(header, "") for header in headers]]
        await self._request_json("POST", url, json={"values": values})

    async def update_row(
        self,
        sheet_name: str,
        headers: list[str],
        sheet_row_number: int,
        row: dict,
    ) -> None:
        end_col = self._column_letter(len(headers))
        range_name = aiohttp.helpers.quote(
            f"{sheet_name}!A{sheet_row_number}:{end_col}{sheet_row_number}",
            safe="",
        )
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}"
            f"/values/{range_name}?valueInputOption=USER_ENTERED"
        )
        values = [[row.get(header, "") for header in headers]]
        await self._request_json("PUT", url, json={"values": values})

    @staticmethod
    def _column_letter(number: int) -> str:
        result = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result
        return result

    async def _sheet_id(self, sheet_name: str) -> int:
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}"
            f"?fields=sheets(properties(sheetId,title))"
        )
        data = await self._request_json("GET", url)
        for sheet in data.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == sheet_name:
                return int(properties["sheetId"])
        raise RuntimeError(f"找不到 Google Sheets 分頁：{sheet_name}")

    async def ensure_compact_layout(self, sheet_name: str, headers: list[str]) -> None:
        if sheet_name in self._formatted_sheet_names:
            return

        sheet_id = await self._sheet_id(sheet_name)
        header_index = {name: index for index, name in enumerate(headers)}
        requests = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "verticalAlignment": "MIDDLE",
                            "wrapStrategy": "CLIP",
                        }
                    },
                    "fields": (
                        "userEnteredFormat.textFormat.bold,"
                        "userEnteredFormat.verticalAlignment,"
                        "userEnteredFormat.wrapStrategy"
                    ),
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 1,
                    },
                    "properties": {"pixelSize": 42},
                    "fields": "pixelSize",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {"verticalAlignment": "MIDDLE"}
                    },
                    "fields": "userEnteredFormat.verticalAlignment",
                }
            },
        ]

        for column_name in ("raw_extracted_text", "notes"):
            column_index = header_index.get(column_name)
            if column_index is None:
                continue
            requests.extend([
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": column_index,
                            "endColumnIndex": column_index + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "wrapStrategy": "CLIP",
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": (
                            "userEnteredFormat.wrapStrategy,"
                            "userEnteredFormat.verticalAlignment"
                        ),
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": column_index,
                            "endIndex": column_index + 1,
                        },
                        "properties": {"pixelSize": 120},
                        "fields": "pixelSize",
                    }
                },
            ])

        for column_name in ("card_front_image_url", "card_back_image_url"):
            column_index = header_index.get(column_name)
            if column_index is None:
                continue
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": column_index,
                        "endIndex": column_index + 1,
                    },
                    "properties": {"pixelSize": 115},
                    "fields": "pixelSize",
                }
            })

        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.spreadsheet_id}:batchUpdate"
        )
        await self._request_json("POST", url, json={"requests": requests})
        self._formatted_sheet_names.add(sheet_name)

    @staticmethod
    def _hyperlink_formula(url: str, label: str) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        safe_url = value.replace('"', '""')
        safe_label = str(label or "開啟").replace('"', '""')
        return f'=HYPERLINK("{safe_url}","{safe_label}")'

    @staticmethod
    def _single_line(value: Any, max_chars: int = 180) -> str:
        compact = re.sub(r"\s+", " ", str(value or "")).strip()
        if max_chars and len(compact) > max_chars:
            return compact[:max_chars].rstrip("，、；,. ") + "…"
        return compact

    @staticmethod
    def _normalize_website_url(value: Any) -> str:
        url = str(value or "").strip()
        if not url:
            return ""
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            url = "https://" + url.lstrip("/")
        return url

    def _websites_formula(self, websites: Any) -> str:
        """
        Google Sheets 單一儲存格很難可靠保存多個獨立可點連結。
        第一版將第一個網站做成可點的 HYPERLINK；
        其餘網站保留在 notes 精簡摘要中，不會遺失。
        """
        if isinstance(websites, str):
            raw = websites.strip()
            try:
                parsed = json.loads(raw)
                values = parsed if isinstance(parsed, list) else [raw]
            except Exception:
                values = [raw]
        elif isinstance(websites, list):
            values = websites
        else:
            values = []

        cleaned = []
        for item in values:
            url = self._normalize_website_url(item)
            if url and url not in cleaned:
                cleaned.append(url)

        if not cleaned:
            return ""

        label = "🌐 開啟網站" if len(cleaned) == 1 else f"🌐 開啟網站（共{len(cleaned)}個）"
        return GoogleWorkspaceClient._hyperlink_formula(cleaned[0], label)

    async def upload_drive_image(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> dict:
        token = await self.access_token()
        metadata = {
            "name": filename,
            "parents": [self.drive_folder_id],
        }

        form = aiohttp.FormData()
        form.add_field(
            "metadata",
            json.dumps(metadata, ensure_ascii=False),
            content_type="application/json; charset=UTF-8",
        )
        form.add_field(
            "file",
            content,
            filename=filename,
            content_type=mime_type or "image/jpeg",
        )

        url = (
            "https://www.googleapis.com/upload/drive/v3/files"
            "?uploadType=multipart&fields=id,name,webViewLink,thumbnailLink"
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as response:
                raw = await response.text()
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"raw": raw}
                if response.status >= 300:
                    raise RuntimeError(f"Google Drive 上傳失敗：{response.status} {data}")
                return data


class PossibleMatchView(discord.ui.View):
    def __init__(
        self,
        service: "BusinessCardService",
        message_author_id: int,
        candidates: list[dict],
        card: dict,
        image_items: list[dict],
        source_message: discord.Message,
    ):
        super().__init__(timeout=600)
        self.service = service
        self.message_author_id = message_author_id
        self.candidates = candidates
        self.card = card
        self.image_items = image_items
        self.source_message = source_message
        self.selected_index = 0

        options = []
        for index, candidate in enumerate(candidates[:20]):
            label = candidate.get("name_zh") or candidate.get("name_en") or "未命名聯絡人"
            company = candidate.get("primary_organization") or "公司未填"
            role = candidate.get("primary_job_title") or "職稱未填"
            options.append(
                discord.SelectOption(
                    label=f"{index + 1}. {label}"[:100],
                    description=f"{company}｜{role}"[:100],
                    value=str(index),
                )
            )
        self.match_select = discord.ui.Select(
            placeholder="選擇要更新的既有聯絡人",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.match_select.callback = self._select_callback
        self.add_item(self.match_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.message_author_id:
            await interaction.response.send_message("只有原上傳者可以決定這筆名片。", ephemeral=True)
            return False
        return True

    async def _select_callback(self, interaction: discord.Interaction):
        self.selected_index = int(self.match_select.values[0])
        candidate = self.candidates[self.selected_index]
        await interaction.response.send_message(
            f"已選擇：{candidate.get('name_zh') or candidate.get('name_en')}｜"
            f"{candidate.get('primary_organization') or '公司未填'}",
            ephemeral=True,
        )

    @discord.ui.button(label="更新既有資料", style=discord.ButtonStyle.primary, emoji="♻️")
    async def update_existing(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        candidate = self.candidates[self.selected_index]
        try:
            result = await self.service.finalize_update(
                candidate,
                self.card,
                self.image_items,
                self.source_message,
                match_status="USER_CONFIRMED_MATCH",
            )
            await interaction.followup.send(result)
            self.stop()
        except Exception as exc:
            await interaction.followup.send(f"❌ 更新名片失敗：{exc}")

    @discord.ui.button(label="建立新聯絡人", style=discord.ButtonStyle.success, emoji="➕")
    async def create_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        try:
            result = await self.service.finalize_new(
                self.card,
                self.image_items,
                self.source_message,
                match_status="USER_CONFIRMED_NEW",
            )
            await interaction.followup.send(result)
            self.stop()
        except Exception as exc:
            await interaction.followup.send(f"❌ 新增名片失敗：{exc}")

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("已取消，Google Drive 與 Sheets 都沒有寫入。")
        self.stop()


class BusinessCardService:
    def __init__(self, architect_channel_id: int):
        self.architect_channel_id = int(architect_channel_id)
        self.vision_model = os.environ.get(
            "BUSINESS_CARD_VISION_MODEL",
            "gemini-2.5-flash",
        )
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.sheet_id = os.environ.get("BUSINESS_CARD_SHEET_ID", "")
        self.main_sheet = os.environ.get("BUSINESS_CARD_MAIN_SHEET", "Business_Cards")
        self.history_sheet = os.environ.get(
            "BUSINESS_CARD_HISTORY_SHEET",
            "Business_Card_History",
        )
        self.drive_folder_id = os.environ.get(
            "GOOGLE_DRIVE_BUSINESS_CARD_FOLDER_ID",
            "",
        )
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.google_refresh_token = (
            os.environ.get("GOOGLE_REFRESH_TOKEN")
            or os.environ.get("Google_Refresh_Token")
            or ""
        )

        # Google Sheets 顯示策略：預設不保存冗長 OCR 原文。
        self.store_raw_text = (
            os.environ.get("BUSINESS_CARD_STORE_RAW_TEXT", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        try:
            self.notes_max_chars = max(
                0,
                int(os.environ.get("BUSINESS_CARD_NOTES_MAX_CHARS", "180")),
            )
        except ValueError:
            self.notes_max_chars = 180

        try:
            self.query_max_results = max(
                1,
                min(20, int(os.environ.get("BUSINESS_CARD_QUERY_MAX_RESULTS", "8"))),
            )
        except ValueError:
            self.query_max_results = 8

        self.config_errors = []
        checks = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "BUSINESS_CARD_SHEET_ID": self.sheet_id,
            "GOOGLE_DRIVE_BUSINESS_CARD_FOLDER_ID": self.drive_folder_id,
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "GOOGLE_REFRESH_TOKEN / Google_Refresh_Token": self.google_refresh_token,
        }
        for name, value in checks.items():
            if not value:
                self.config_errors.append(name)

        self.gemini = (
            genai.Client(api_key=self.gemini_api_key)
            if self.gemini_api_key
            else None
        )
        self.google = (
            GoogleWorkspaceClient(
                client_id=self.google_client_id,
                client_secret=self.google_client_secret,
                refresh_token=self.google_refresh_token,
                spreadsheet_id=self.sheet_id,
                main_sheet=self.main_sheet,
                history_sheet=self.history_sheet,
                drive_folder_id=self.drive_folder_id,
            )
            if not self.config_errors
            else None
        )

    @staticmethod
    def _single_line(value: Any, max_chars: int = 180) -> str:
        """將 OCR/備註壓成單行，避免 Google Sheets 列高被長文字撐大。"""
        compact = re.sub(r"\s+", " ", str(value or "")).strip()
        if max_chars and len(compact) > max_chars:
            return compact[:max_chars].rstrip("，、；,. ") + "…"
        return compact

    @staticmethod
    def _normalize_website_url(value: Any) -> str:
        """補齊網站協定，讓 Google Sheets HYPERLINK 可以正常開啟。"""
        url = str(value or "").strip()
        if not url:
            return ""
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            url = "https://" + url.lstrip("/")
        return url

    def _websites_formula(self, websites: Any) -> str:
        """
        將第一個網站轉成 Google Sheets 可點擊 HYPERLINK。
        其他網站會保留在 notes。
        """
        if isinstance(websites, str):
            raw = websites.strip()
            try:
                parsed = json.loads(raw)
                values = parsed if isinstance(parsed, list) else [raw]
            except Exception:
                values = [raw]
        elif isinstance(websites, list):
            values = websites
        else:
            values = []

        cleaned = []
        for item in values:
            url = self._normalize_website_url(item)
            if url and url not in cleaned:
                cleaned.append(url)

        if not cleaned:
            return ""

        label = (
            "🌐 開啟網站"
            if len(cleaned) == 1
            else f"🌐 開啟網站（共{len(cleaned)}個）"
        )
        return GoogleWorkspaceClient._hyperlink_formula(cleaned[0], label)

    @staticmethod
    def _formula_url(value: Any) -> str:
        """從 =HYPERLINK("url","label") 或一般 URL 取出實際網址。"""
        raw = str(value or "").strip()
        match = re.match(
            r'^=HYPERLINK\("((?:[^"]|"")*)"\s*,',
            raw,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).replace('""', '"')
        if raw.startswith(("http://", "https://")):
            return raw
        return ""

    @staticmethod
    def _query_text(value: Any) -> str:
        """用於搜尋的正規化文字：忽略空白、標點與大小寫。"""
        raw = str(value or "").lower()
        raw = re.sub(r"\s+", "", raw)
        raw = re.sub(r"[，。！？、：:；;（）()【】\[\]「」『』\-_/\\.]", "", raw)
        return raw

    @staticmethod
    def _query_candidate(text: str) -> bool:
        """
        只做低成本的候選判斷，真正意圖仍交給 Gemini。
        避免 #架構師專用每一句普通聊天都呼叫名片查詢。
        """
        value = str(text or "").strip()
        if not value or value.startswith(("!", "/")):
            return False
        patterns = [
            r"名片|聯絡人|聯絡方式|聯繫方式",
            r"(幫我|替我)?(找|查|搜尋|查詢|看看).{0,30}(人|公司|電話|手機|信箱|email|職稱|名片)",
            r"(誰是|哪一位|哪些人|有誰).{0,30}(經理|主管|工程師|秘書長|公司|協會|部門)",
            r"(電話|手機|email|信箱|分機|地址|網站).{0,12}(是什麼|多少|在哪|給我|查一下)",
            r"給我看.{0,20}(名片|聯絡資料|資料)",
        ]
        return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)

    async def _classify_text_query(self, user_text: str) -> dict:
        prompt = f"""
你是企業名片資料庫查詢意圖分析器。

使用者訊息：
{user_text}

判斷這是否是在查詢 Google Sheets 名片／聯絡人資料。
一般技術問答、聊天、要求寫程式、晨報或其他工作，不是名片查詢。

只回傳 JSON：
{{
  "is_business_card_query": true,
  "query_type": "detail",
  "search_terms": ["劉哲輔"],
  "filters": {{
    "name": "",
    "organization": "",
    "department": "",
    "job_title": "",
    "phone": "",
    "email": "",
    "address": "",
    "affiliation": ""
  }},
  "wants_card_image": false,
  "wants_full_detail": true
}}

query_type 可用：
- detail：查單一人的完整或部分資料
- list：查某公司、部門、職稱有哪些人
- image：要求看名片圖片
- contact：只問電話、Email、地址等聯絡資料

規則：
- search_terms 放最具辨識力的姓名、公司、部門、職稱、電話尾碼或 Email 片段。
- 不要把「幫我、請問、查一下」放入 search_terms。
- 若不是名片查詢，is_business_card_query=false。
"""
        response = await asyncio.to_thread(
            self.gemini.models.generate_content,
            model=self.vision_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        result = _extract_json(response.text)
        result.setdefault("is_business_card_query", False)
        result.setdefault("query_type", "detail")
        result.setdefault("search_terms", [])
        result.setdefault("filters", {})
        result.setdefault("wants_card_image", False)
        result.setdefault("wants_full_detail", False)
        return result

    def _score_query_row(self, row: dict, query: dict) -> int:
        searchable_fields = {
            "name": ["name_zh", "name_en"],
            "organization": ["primary_organization"],
            "department": ["primary_department"],
            "job_title": ["primary_job_title"],
            "phone": ["mobile", "phone", "phone_extension", "fax"],
            "email": ["email"],
            "address": ["postal_code", "address"],
            "affiliation": ["affiliations_json"],
            "general": [
                "name_zh", "name_en", "primary_organization",
                "primary_department", "primary_job_title", "affiliations_json",
                "mobile", "phone", "phone_extension", "fax", "email",
                "postal_code", "address", "websites", "tax_id", "notes",
            ],
        }

        score = 0
        matched_terms = 0

        filters = query.get("filters") or {}
        for filter_name, raw_term in filters.items():
            term = self._query_text(raw_term)
            if not term:
                continue
            fields = searchable_fields.get(filter_name, searchable_fields["general"])
            values = [self._query_text(row.get(field, "")) for field in fields]
            if any(term == value for value in values if value):
                score += 100
                matched_terms += 1
            elif any(term in value for value in values if value):
                score += 55
                matched_terms += 1
            else:
                return 0  # 明確 filter 未命中即排除

        for raw_term in query.get("search_terms") or []:
            term = self._query_text(raw_term)
            if not term:
                continue
            best = 0
            for field in searchable_fields["general"]:
                value = self._query_text(row.get(field, ""))
                if not value:
                    continue
                if term == value:
                    best = max(best, 90)
                elif term in value:
                    best = max(best, 45)
                elif len(term) >= 3 and value in term:
                    best = max(best, 20)
            # 電話尾碼與 email 片段
            digits = re.sub(r"\D+", "", str(raw_term))
            if len(digits) >= 4:
                for field in ("mobile", "phone", "fax"):
                    row_digits = re.sub(r"\D+", "", str(row.get(field, "")))
                    if row_digits.endswith(digits):
                        best = max(best, 80)
            if best:
                score += best
                matched_terms += 1

        # 至少一個條件命中；沒有 terms/filters 時不回傳全表。
        return score if matched_terms else 0

    def _search_rows(self, rows: list[dict], query: dict) -> list[dict]:
        scored = []
        for row in rows:
            score = self._score_query_row(row, query)
            if score > 0:
                scored.append((score, row))
        scored.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("name_zh") or item[1].get("name_en") or ""),
            )
        )
        return [row for _, row in scored[: self.query_max_results]]

    @staticmethod
    def _dialable_number(value: Any) -> str:
        """建立 tel: 使用的主號碼；分機由 phone_extension 另外顯示。"""
        raw = str(value or "").strip()
        if not raw:
            return ""
        digits = re.sub(r"\D+", "", raw)
        return f"+{digits}" if digits else ""

    @classmethod
    def _phone_markdown(cls, value: Any) -> str:
        """產生可點擊撥號連結，同時保留原始號碼文字。"""
        raw = str(value or "").strip()
        if not raw:
            return "未提供"
        dialable = cls._dialable_number(raw)
        return f"[{raw}](tel:{dialable})" if dialable else raw

    @staticmethod
    def _gmail_markdown(email: Any) -> str:
        """點擊後開啟 Gmail 撰寫頁，並自動帶入收件人。"""
        raw = str(email or "").strip()
        if not raw:
            return "未提供"
        gmail_url = (
            "https://mail.google.com/mail/?view=cm&fs=1&to="
            + quote(raw, safe="")
        )
        return f"[{raw}]({gmail_url})"

    def _contact_summary(self, row: dict, include_links: bool = True) -> str:
        name = row.get("name_zh") or row.get("name_en") or "未命名聯絡人"
        name_en = row.get("name_en", "")
        organization = row.get("primary_organization") or "機構未填"
        department = row.get("primary_department") or ""
        role = row.get("primary_job_title") or ""
        mobile_raw = row.get("mobile") or ""
        phone_raw = row.get("phone") or ""
        extension = row.get("phone_extension") or ""
        email_raw = row.get("email") or ""
        address = row.get("address") or "未提供"

        mobile = self._phone_markdown(mobile_raw)
        phone = self._phone_markdown(phone_raw)
        email = self._gmail_markdown(email_raw)

        lines = [f"**{name}" + (f"（{name_en}）**" if name_en and name_en != name else "**")]
        lines.append(f"機構：{organization}")
        if department:
            lines.append(f"部門：{department}")
        if role:
            lines.append(f"職稱：{role}")
        lines.append(f"手機：{mobile}")
        lines.append(f"電話：{phone}" + (f" 分機 {extension}" if extension else ""))
        lines.append(f"Email：{email}")
        lines.append(f"地址：{address}")

        affiliations = str(row.get("affiliations_json") or "").strip()
        if affiliations:
            try:
                parsed = json.loads(affiliations)
                if isinstance(parsed, list) and parsed:
                    rendered = []
                    for item in parsed:
                        if not isinstance(item, dict):
                            continue
                        org = item.get("organization", "")
                        dept = item.get("department", "")
                        role_value = item.get("role", "")
                        text = "｜".join(x for x in (org, dept, role_value) if x)
                        if text:
                            rendered.append(text)
                    if rendered:
                        lines.append("其他身分：" + "；".join(rendered[:5]))
            except Exception:
                pass

        if include_links:
            website_url = self._formula_url(row.get("websites"))
            front_url = self._formula_url(row.get("card_front_image_url"))
            back_url = self._formula_url(row.get("card_back_image_url"))
            link_parts = []
            if website_url:
                link_parts.append(f"[網站]({website_url})")
            if front_url:
                link_parts.append(f"[名片正面]({front_url})")
            if back_url:
                link_parts.append(f"[名片背面]({back_url})")
            if link_parts:
                lines.append("連結：" + "｜".join(link_parts))

        return "\n".join(lines)

    def _format_query_results(self, rows: list[dict], query: dict) -> str:
        if not rows:
            terms = "、".join(str(x) for x in query.get("search_terms") or [])
            return f"🔎 找不到符合「{terms or '這個條件'}」的名片資料。"

        query_type = query.get("query_type", "detail")
        wants_full = bool(query.get("wants_full_detail"))
        wants_image = bool(query.get("wants_card_image")) or query_type == "image"

        if len(rows) == 1:
            return "📇 **找到 1 位聯絡人**\n\n" + self._contact_summary(
                rows[0],
                include_links=True,
            )

        lines = [f"📇 **找到 {len(rows)} 位符合的聯絡人**"]
        for index, row in enumerate(rows, start=1):
            name = row.get("name_zh") or row.get("name_en") or "未命名"
            company = row.get("primary_organization") or "機構未填"
            role = row.get("primary_job_title") or "職稱未填"
            email = row.get("email") or ""
            mobile = row.get("mobile") or ""
            line = f"{index}. **{name}**｜{company}｜{role}"
            if query_type == "contact":
                contact = email or mobile
                if contact:
                    line += f"\n   {contact}"
            if wants_image:
                front_url = self._formula_url(row.get("card_front_image_url"))
                if front_url:
                    line += f"｜[名片]({front_url})"
            lines.append(line)

        lines.append("\n可再直接問「顯示某人的完整資料」。")
        return "\n".join(lines)

    async def handle_text_query(self, message: discord.Message) -> bool:
        user_text = str(message.content or "").strip()
        if not self._query_candidate(user_text):
            return False
        if not self.ready:
            await message.channel.send(
                "❌ 名片服務尚未完成設定：" + "、".join(self.config_errors)
            )
            return True

        try:
            query = await self._classify_text_query(user_text)
            if not query.get("is_business_card_query"):
                return False

            headers, rows = await self.google.read_table(self.main_sheet)
            self._validate_headers(headers, MAIN_HEADERS, self.main_sheet)
            results = self._search_rows(rows, query)
            await message.channel.send(self._format_query_results(results, query))
            return True
        except Exception as exc:
            await message.channel.send(f"❌ 名片查詢失敗：{exc}")
            return True

    @property
    def ready(self) -> bool:
        return not self.config_errors and self.gemini is not None and self.google is not None

    def status_text(self) -> str:
        if self.ready:
            return (
                f"ready | channel={self.architect_channel_id} | "
                f"sheet={self.main_sheet}/{self.history_sheet} | "
                f"model={self.vision_model} | natural_query=on"
            )
        return "missing: " + ", ".join(self.config_errors)

    async def handle_message(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False
        if getattr(message.channel, "id", None) != self.architect_channel_id:
            return False

        image_attachments = [
            attachment
            for attachment in message.attachments
            if (
                str(attachment.content_type or "").startswith("image/")
                or str(attachment.filename).lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                )
            )
        ]
        if not image_attachments:
            return await self.handle_text_query(message)

        if not self.ready:
            await message.channel.send(
                "❌ 名片服務尚未完成設定："
                + "、".join(self.config_errors)
            )
            return True

        progress = await message.channel.send("📇 小夏正在判斷圖片是否為名片並擷取資料……")
        try:
            image_items = []
            for attachment in image_attachments[:2]:
                content = await attachment.read()
                image_items.append(
                    {
                        "filename": attachment.filename,
                        "mime_type": attachment.content_type
                        or mimetypes.guess_type(attachment.filename)[0]
                        or "image/jpeg",
                        "content": content,
                    }
                )

            analysis = await self._analyze_images(image_items)
            if not analysis.get("is_business_card"):
                await progress.delete()
                return False

            cards = analysis.get("cards") or []
            if not cards:
                raise RuntimeError("判定為名片，但沒有擷取到聯絡人資料。")
            if len(cards) > 1:
                await progress.edit(
                    content="⚠️ 目前第一版一次只處理一位聯絡人；這張圖疑似包含多張名片，請分開拍攝後重新上傳。"
                )
                return True

            card = self._normalize_card(cards[0], analysis)
            headers, rows = await self.google.read_table(self.main_sheet)
            self._validate_headers(headers, MAIN_HEADERS, self.main_sheet)
            await self.google.ensure_compact_layout(self.main_sheet, headers)

            exact, possible = self._find_matches(card, rows)
            if exact:
                result = await self.finalize_update(
                    exact,
                    card,
                    image_items,
                    message,
                    match_status="AUTO_MATCHED",
                )
                await progress.edit(content=result)
                return True

            if possible:
                await progress.edit(
                    content=self._possible_match_text(card, possible),
                    view=PossibleMatchView(
                        self,
                        message.author.id,
                        possible,
                        card,
                        image_items,
                        message,
                    ),
                )
                return True

            result = await self.finalize_new(
                card,
                image_items,
                message,
                match_status="NEW",
            )
            await progress.edit(content=result)
            return True

        except Exception as exc:
            await progress.edit(content=f"❌ 名片處理失敗：{exc}")
            return True

    async def _analyze_images(self, image_items: list[dict]) -> dict:
        prompt = """
你是企業名片辨識與資料結構化系統。請分析附圖。

第一步判斷它是否為名片。名片通常含姓名、組織、職稱、電話、Email、地址、網站等。
一般文件、聊天截圖、設備照片、簡報或風景照不得誤判為名片。

若為名片，請逐字辨識，不可猜測未印出的內容。圖片可能旋轉、斜拍，請自行校正閱讀方向。
同一則訊息的兩張圖可能是同一張名片正反面，必須合併成一位聯絡人。
若一張圖片內明顯包含多張不同名片，cards 陣列可回傳多筆。

只回傳 JSON：
{
  "is_business_card": true,
  "classification_confidence": 0,
  "reason": "",
  "cards": [
    {
      "name_zh": "",
      "name_en": "",
      "primary_organization": "",
      "primary_department": "",
      "primary_job_title": "",
      "affiliations": [
        {"organization": "", "department": "", "role": ""}
      ],
      "mobile": "",
      "phone": "",
      "phone_extension": "",
      "fax": "",
      "email": "",
      "postal_code": "",
      "address": "",
      "websites": [],
      "line_id": "",
      "tax_id": "",
      "card_language": "zh-TW",
      "ocr_confidence": 0,
      "raw_extracted_text": "",
      "notes": ""
    }
  ]
}

規則：
- confidence 使用 0 到 100。
- 電話與 Email 忠實保留原意。
- 多重協會身分放 affiliations，不要擠進主要職稱。
- primary_organization 應是主要任職機構。
- 沒印出的英文名、Line ID 等留空。
"""
        parts = [types.Part.from_text(text=prompt)]
        for item in image_items:
            parts.append(
                types.Part.from_bytes(
                    data=item["content"],
                    mime_type=item["mime_type"],
                )
            )

        response = await asyncio.to_thread(
            self.gemini.models.generate_content,
            model=self.vision_model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return _extract_json(response.text)

    def _normalize_card(self, card: dict, analysis: dict) -> dict:
        normalized = {key: card.get(key, "") for key in MAIN_HEADERS}
        normalized["affiliations_json"] = _json_text(card.get("affiliations", []))

        raw_websites = card.get("websites", [])
        normalized["websites"] = self._websites_formula(raw_websites)

        normalized["ocr_confidence"] = card.get(
            "ocr_confidence",
            analysis.get("classification_confidence", 0),
        )
        normalized["raw_extracted_text"] = (
            self._single_line(card.get("raw_extracted_text", ""), max_chars=1200)
            if self.store_raw_text
            else ""
        )
        notes_value = self._single_line(
            card.get("notes", ""),
            max_chars=self.notes_max_chars,
        )

        # 若有多個網站，第一個放在 websites 可點欄位，其餘保留在 notes。
        website_values = raw_websites if isinstance(raw_websites, list) else []
        extra_websites = [
            self._normalize_website_url(item)
            for item in website_values[1:]
            if self._normalize_website_url(item)
        ]
        if extra_websites:
            extra_text = "其他網站：" + "、".join(extra_websites)
            notes_value = self._single_line(
                f"{notes_value}；{extra_text}" if notes_value else extra_text,
                max_chars=self.notes_max_chars,
            )

        normalized["notes"] = notes_value
        normalized["card_language"] = card.get("card_language", "")
        normalized["review_status"] = (
            "AUTO_SAVED"
            if float(normalized.get("ocr_confidence") or 0) >= 90
            else "NEEDS_REVIEW"
        )
        return normalized

    @staticmethod
    def _validate_headers(actual: list[str], required: list[str], sheet_name: str):
        missing = [header for header in required if header not in actual]
        if missing:
            raise RuntimeError(
                f"{sheet_name} 缺少欄位：{', '.join(missing)}"
            )

    def _find_matches(
        self,
        card: dict,
        rows: list[dict],
    ) -> tuple[Optional[dict], list[dict]]:
        email = _normalize_email(card.get("email"))
        mobile = _normalize_phone(card.get("mobile"))
        name_zh = _compact(card.get("name_zh"))
        name_en = _compact(card.get("name_en"))

        exact = []
        possible = []
        for row in rows:
            row_email = _normalize_email(row.get("email"))
            row_mobile = _normalize_phone(row.get("mobile"))
            row_name_zh = _compact(row.get("name_zh"))
            row_name_en = _compact(row.get("name_en"))

            email_match = bool(email and row_email and email == row_email)
            mobile_match = bool(mobile and row_mobile and mobile == row_mobile)

            if email_match or mobile_match:
                # 聯絡方式相同但姓名明顯完全不同，仍交由人工確認。
                names_conflict = (
                    (name_zh and row_name_zh and name_zh != row_name_zh)
                    and (name_en and row_name_en and name_en != row_name_en)
                )
                if names_conflict:
                    possible.append(row)
                else:
                    exact.append(row)
                continue

            same_name = (
                bool(name_zh and row_name_zh and name_zh == row_name_zh)
                or bool(name_en and row_name_en and name_en == row_name_en)
            )
            if same_name:
                possible.append(row)

        if len(exact) == 1:
            return exact[0], possible
        if len(exact) > 1:
            return None, exact + possible
        return None, possible

    async def _upload_images(
        self,
        person_id: str,
        image_items: list[dict],
    ) -> tuple[str, str]:
        urls = []
        for index, item in enumerate(image_items[:2]):
            side = "front" if index == 0 else "back"
            extension = PathLike.extension(item["filename"], item["mime_type"])
            filename = f"{person_id}_{side}{extension}"
            uploaded = await self.google.upload_drive_image(
                filename,
                item["content"],
                item["mime_type"],
            )
            urls.append(uploaded.get("webViewLink", ""))
        return (
            urls[0] if urls else "",
            urls[1] if len(urls) > 1 else "",
        )

    async def finalize_new(
        self,
        card: dict,
        image_items: list[dict],
        source_message: discord.Message,
        match_status: str,
    ) -> str:
        headers, _ = await self.google.read_table(self.main_sheet)
        self._validate_headers(headers, MAIN_HEADERS, self.main_sheet)
        await self.google.ensure_compact_layout(self.main_sheet, headers)

        person_id = (
            f"BC-{datetime.now(TZ_TPE).strftime('%Y%m%d')}-"
            f"{uuid.uuid4().hex[:6].upper()}"
        )
        front_url, back_url = await self._upload_images(person_id, image_items)
        now = _now_str()
        row = dict(card)
        row.update(
            {
                "person_id": person_id,
                "created_at": now,
                "updated_at": now,
                "uploaded_by": str(source_message.author),
                "discord_message_url": _message_url(source_message),
                "card_front_image_url": self.google._hyperlink_formula(
                    front_url,
                    "📇 查看正面",
                ),
                "card_back_image_url": self.google._hyperlink_formula(
                    back_url,
                    "📇 查看背面",
                ),
                "match_status": match_status,
            }
        )
        await self.google.append_row(self.main_sheet, headers, row)
        return self._success_text("新增", row)

    async def finalize_update(
        self,
        existing: dict,
        card: dict,
        image_items: list[dict],
        source_message: discord.Message,
        match_status: str,
    ) -> str:
        main_headers, _ = await self.google.read_table(self.main_sheet)
        history_headers, _ = await self.google.read_table(self.history_sheet)
        self._validate_headers(main_headers, MAIN_HEADERS, self.main_sheet)
        self._validate_headers(
            history_headers,
            HISTORY_HEADERS,
            self.history_sheet,
        )
        await self.google.ensure_compact_layout(self.main_sheet, main_headers)
        await self.google.ensure_compact_layout(self.history_sheet, history_headers)

        person_id = existing.get("person_id") or (
            f"BC-{datetime.now(TZ_TPE).strftime('%Y%m%d')}-"
            f"{uuid.uuid4().hex[:6].upper()}"
        )
        front_url, back_url = await self._upload_images(person_id, image_items)
        now = _now_str()

        history = {
            "history_id": f"HIST-{uuid.uuid4().hex[:10].upper()}",
            "person_id": person_id,
            "archived_at": now,
            "change_reason": "新名片更新既有聯絡人",
            "replaced_by_message_url": _message_url(source_message),
        }
        for header in HISTORY_HEADERS:
            if header not in history:
                history[header] = existing.get(header, "")
        await self.google.append_row(self.history_sheet, history_headers, history)

        updated = dict(existing)
        for key, value in card.items():
            if value not in ("", None, [], "{}"):
                updated[key] = value
        updated.update(
            {
                "person_id": person_id,
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
                "uploaded_by": str(source_message.author),
                "discord_message_url": _message_url(source_message),
                "card_front_image_url": (
                    self.google._hyperlink_formula(front_url, "📇 查看正面")
                    if front_url
                    else existing.get("card_front_image_url", "")
                ),
                "card_back_image_url": (
                    self.google._hyperlink_formula(back_url, "📇 查看背面")
                    if back_url
                    else existing.get("card_back_image_url", "")
                ),
                "match_status": match_status,
            }
        )
        sheet_row_number = int(existing["_sheet_row_number"])
        await self.google.update_row(
            self.main_sheet,
            main_headers,
            sheet_row_number,
            updated,
        )
        return self._success_text("更新", updated)

    @staticmethod
    def _success_text(action: str, row: dict) -> str:
        confidence = row.get("ocr_confidence", "")
        name = row.get("name_zh") or row.get("name_en") or "未辨識姓名"
        company = row.get("primary_organization") or "未辨識公司"
        role = row.get("primary_job_title") or "未辨識職稱"
        email = row.get("email") or "未提供"
        mobile = row.get("mobile") or "未提供"
        return (
            f"📇 **名片已{action}完成**\n"
            f"姓名：{name}\n"
            f"機構：{company}\n"
            f"職稱：{role}\n"
            f"手機：{mobile}\n"
            f"Email：{email}\n"
            f"辨識可信度：{confidence or '未提供'}\n"
            f"狀態：`{row.get('review_status') or 'NEEDS_REVIEW'}`"
        )

    @staticmethod
    def _possible_match_text(card: dict, candidates: list[dict]) -> str:
        lines = [
            "⚠️ **找到可能相同的聯絡人，尚未寫入 Drive 或 Sheets。**",
            "",
            "新名片：",
            f"{card.get('name_zh') or card.get('name_en') or '未辨識姓名'}｜"
            f"{card.get('primary_organization') or '公司未填'}｜"
            f"{card.get('primary_job_title') or '職稱未填'}",
            "",
            "既有候選：",
        ]
        for index, row in enumerate(candidates[:5], start=1):
            lines.append(
                f"{index}. {row.get('name_zh') or row.get('name_en') or '未命名'}｜"
                f"{row.get('primary_organization') or '公司未填'}｜"
                f"{row.get('primary_job_title') or '職稱未填'}"
            )
        lines.append("")
        lines.append("請先在選單選擇既有聯絡人，再決定更新或建立新資料。")
        return "\n".join(lines)


class PathLike:
    @staticmethod
    def extension(filename: str, mime_type: str) -> str:
        suffix = os.path.splitext(str(filename or ""))[1].lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return suffix
        guessed = mimetypes.guess_extension(mime_type or "")
        return guessed or ".jpg"
