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
MODULE_VERSION = "1.5.1"

MAIN_HEADERS = ['person_id', 'created_at', 'updated_at', 'uploaded_by', 'discord_message_url', 'card_front_image_url', 'card_back_image_url', 'name_zh', 'name_en', 'primary_organization', 'primary_department', 'primary_job_title', 'affiliations_json', 'country_code', 'mobile', 'mobile_normalized', 'phone', 'phone_normalized', 'phone_extension', 'fax', 'fax_normalized', 'email', 'postal_code', 'address', 'websites', 'line_id', 'tax_id', 'card_language', 'ocr_confidence', 'critical_confidence', 'match_status', 'review_status', 'raw_extracted_text', 'notes']

HISTORY_HEADERS = ['history_id', 'person_id', 'archived_at', 'change_reason', 'replaced_by_message_url', 'name_zh', 'name_en', 'primary_organization', 'primary_department', 'primary_job_title', 'affiliations_json', 'country_code', 'mobile', 'mobile_normalized', 'phone', 'phone_normalized', 'phone_extension', 'fax', 'fax_normalized', 'email', 'postal_code', 'address', 'websites', 'line_id', 'tax_id', 'card_front_image_url', 'card_back_image_url', 'ocr_confidence', 'critical_confidence', 'review_status', 'raw_extracted_text', 'notes']


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

    @staticmethod
    def _sheet_safe_value(header: str, value: Any) -> Any:
        """
        valueInputOption=USER_ENTERED is required for HYPERLINK formulas,
        but phone numbers such as 886-3-4527005 would otherwise be evaluated
        as subtraction. Prefix literal text with an apostrophe; Sheets displays
        the text without the apostrophe.
        """
        if value is None:
            return ""

        raw = str(value)

        formula_headers = {
            "card_front_image_url",
            "card_back_image_url",
            "websites",
        }
        if header in formula_headers and raw.startswith("="):
            return raw

        text_headers = {
            "person_id", "history_id",
            "uploaded_by",
            "name_zh", "name_en",
            "primary_organization", "primary_department",
            "primary_job_title", "affiliations_json",
            "country_code",
            "mobile", "mobile_normalized",
            "phone", "phone_normalized", "phone_extension",
            "fax", "fax_normalized",
            "email",
            "postal_code", "address",
            "line_id", "tax_id", "card_language",
            "match_status", "review_status",
            "raw_extracted_text", "notes",
        }

        if header in text_headers:
            return "'" + raw

        # Protect any other string that starts like a formula.
        if raw.startswith(("=", "+", "-")):
            return "'" + raw

        return value

    @classmethod
    def _sheet_safe_row(cls, headers: list[str], row: dict) -> list[Any]:
        return [
            cls._sheet_safe_value(header, row.get(header, ""))
            for header in headers
        ]

    async def append_row(self, sheet_name: str, headers: list[str], row: dict) -> None:
        range_name = aiohttp.helpers.quote(f"{sheet_name}!A1", safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}"
            f"/values/{range_name}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        values = [self._sheet_safe_row(headers, row)]
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
        values = [self._sheet_safe_row(headers, row)]
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

        try:
            self.query_session_minutes = max(
                1,
                min(60, int(os.environ.get("BUSINESS_CARD_QUERY_SESSION_MINUTES", "10"))),
            )
        except ValueError:
            self.query_session_minutes = 10

        self.query_sessions = {}

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

    def _session_key(self, message: discord.Message) -> tuple[int, int]:
        return (int(getattr(message.channel, "id", 0)), int(getattr(message.author, "id", 0)))

    def _get_query_session(self, message: discord.Message) -> Optional[dict]:
        key = self._session_key(message)
        session = self.query_sessions.get(key)
        if not session:
            return None
        if datetime.now(TZ_TPE) >= session.get("expires_at"):
            self.query_sessions.pop(key, None)
            return None
        return session

    def _save_query_session(self, message: discord.Message, results: list[dict], last_query: str) -> None:
        self.query_sessions[self._session_key(message)] = {
            "results": results,
            "last_query": last_query,
            "expires_at": datetime.now(TZ_TPE) + timedelta(minutes=self.query_session_minutes),
        }

    @staticmethod
    def _catalog_for_router(rows: list[dict], max_items: int = 80) -> str:
        items, seen = [], set()
        for row in rows:
            for field, label in (("name_zh", "姓名"), ("name_en", "英文名"), ("primary_organization", "機構"), ("primary_department", "部門"), ("primary_job_title", "職稱")):
                value = str(row.get(field, "") or "").strip()
                key = (field, value)
                if value and key not in seen:
                    seen.add(key); items.append(f"{label}:{value}")
                    if len(items) >= max_items:
                        return "\n".join(items)
        return "\n".join(items) or "資料庫目前沒有資料"

    @staticmethod
    def _session_context_for_router(session: Optional[dict]) -> str:
        if not session:
            return "無上一輪名片查詢候選。"
        lines = ["上一輪名片查詢候選："]
        for index, row in enumerate(session.get("results", [])[:20], start=1):
            lines.append(f"{index}. {row.get('name_zh') or row.get('name_en') or '未命名'}｜{row.get('primary_organization') or '機構未填'}｜{row.get('primary_job_title') or '職稱未填'}")
        return "\n".join(lines)

    async def _classify_text_query(self, user_text: str, rows: list[dict], session: Optional[dict]) -> dict:
        catalog = self._catalog_for_router(rows)
        session_context = self._session_context_for_router(session)
        prompt = f"""
你是「系統架構師小夏」的意圖路由器與名片資料庫查詢解析器。

【使用者本輪訊息】
{user_text}

【上一輪名片查詢狀態】
{session_context}

【名片資料庫中實際存在的姓名、機構、部門、職稱】
{catalog}

請判斷本輪應交給哪個功能：
1. business_card_search：搜尋、查看、列出或詢問名片／聯絡人／電話／Email／公司人員。
2. business_card_select：在上一輪候選中選擇某一位，例如「2」「第二位」「林典永那位」。
3. general_architect_chat：一般技術問答、程式、工作討論或其他非名片需求。
4. clarify：可能是名片需求，但資訊不足，需要澄清。

請理解同義與縮寫，不要依賴固定關鍵詞。例如「金屬中心」可依資料庫內容理解為「金屬工業研究發展中心」。

只回傳 JSON：
{{
  "intent": "business_card_search",
  "action": "detail",
  "selection_index": null,
  "selected_name": "",
  "search_terms": [],
  "filters": {{"name":"","organization":"","department":"","job_title":"","phone":"","email":"","address":"","affiliation":""}},
  "wants_card_image": false,
  "wants_full_detail": false,
  "clarifying_question": ""
}}

action 可用：detail、list、image、contact、select_result。
selection_index 使用 1 開始。若上一輪已有候選，而本輪只輸入數字或序號，必須判定 business_card_select。
"""
        response = await asyncio.to_thread(
            self.gemini.models.generate_content,
            model=self.vision_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
        )
        result = _extract_json(response.text)
        result.setdefault("intent", "general_architect_chat")
        result.setdefault("action", "detail")
        result.setdefault("selection_index", None)
        result.setdefault("selected_name", "")
        result.setdefault("search_terms", [])
        result.setdefault("filters", {})
        result.setdefault("wants_card_image", False)
        result.setdefault("wants_full_detail", False)
        result.setdefault("clarifying_question", "")
        return result

    def _score_query_row(self, row: dict, query: dict) -> int:
        searchable_fields = {
            "name": ["name_zh", "name_en"],
            "organization": ["primary_organization"],
            "department": ["primary_department"],
            "job_title": ["primary_job_title"],
            "phone": [
                "mobile", "mobile_normalized",
                "phone", "phone_normalized",
                "phone_extension",
                "fax", "fax_normalized",
            ],
            "email": ["email"],
            "address": ["postal_code", "address"],
            "affiliation": ["affiliations_json"],
            "general": [
                "name_zh", "name_en", "primary_organization",
                "primary_department", "primary_job_title", "affiliations_json",
                "country_code",
                "mobile", "mobile_normalized",
                "phone", "phone_normalized", "phone_extension",
                "fax", "fax_normalized", "email",
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
    def _phone_markdown(
        cls,
        value: Any,
        normalized: Any = "",
    ) -> str:
        """顯示易讀格式，tel: 使用 normalized 國際格式。"""
        raw = str(value or "").strip()
        if not raw:
            return "未提供"
        dialable = str(normalized or "").strip() or cls._dialable_number(raw)
        return f"[{raw}](tel:{dialable})" if dialable else raw

    @staticmethod
    def _email_markdown(email: Any) -> str:
        """使用 mailto: 交給手機預設郵件 App，並帶入收件人。"""
        raw = str(email or "").strip()
        if not raw:
            return "未提供"
        return f"[{raw}](mailto:{quote(raw, safe='@._+-')})"

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

        mobile = self._phone_markdown(
            mobile_raw,
            row.get("mobile_normalized", ""),
        )
        phone = self._phone_markdown(
            phone_raw,
            row.get("phone_normalized", ""),
        )
        email = self._email_markdown(email_raw)

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
        if not user_text or user_text.startswith(("!", "/")):
            return False
        if not self.ready:
            return False
        try:
            headers, rows = await self.google.read_table(self.main_sheet)
            self._validate_headers(headers, MAIN_HEADERS, self.main_sheet)
            session = self._get_query_session(message)
            route = await self._classify_text_query(user_text, rows, session)
            intent = route.get("intent")
            if intent == "general_architect_chat":
                return False
            if intent == "clarify":
                await message.channel.send("🔎 " + (route.get("clarifying_question") or "你想查哪一位聯絡人、公司、部門或職稱？"))
                return True
            if intent == "business_card_select":
                if not session or not session.get("results"):
                    await message.channel.send("🔎 目前沒有可接續選擇的名片清單，請重新說明要找的人。")
                    return True
                selected = None
                try:
                    if route.get("selection_index") is not None:
                        idx = int(route["selection_index"]) - 1
                        if 0 <= idx < len(session["results"]): selected = session["results"][idx]
                except (TypeError, ValueError):
                    pass
                if selected is None and route.get("selected_name"):
                    target = self._query_text(route["selected_name"])
                    for row in session["results"]:
                        names = (self._query_text(row.get("name_zh", "")), self._query_text(row.get("name_en", "")))
                        if target and any(target in v or v in target for v in names if v):
                            selected = row; break
                if selected is None:
                    await message.channel.send("🔎 我無法確定你選的是哪一位，請回覆候選編號或姓名。")
                    return True
                self._save_query_session(message,[selected],user_text)
                await message.channel.send("📇 **聯絡人完整資料**\n\n" + self._contact_summary(selected, include_links=True))
                return True
            query = dict(route)
            query["query_type"] = route.get("action", "detail")
            results = self._search_rows(rows, query)
            if not results:
                terms = "、".join(str(x) for x in query.get("search_terms") or [])
                filters = query.get("filters") or {}
                filters_text = "、".join(str(v) for v in filters.values() if str(v or "").strip())
                await message.channel.send(f"🔎 找不到符合「{terms or filters_text or user_text}」的名片資料。")
                return True
            self._save_query_session(message,results,user_text)
            await message.channel.send(self._format_query_results(results,query))
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
                f"version={MODULE_VERSION} | "
                f"sheet={self.main_sheet}/{self.history_sheet} | "
                f"model={self.vision_model} | llm_router=on | "
                f"query_session=on | mailto=on"
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

            verified = await self._verify_critical_fields(
                image_items,
                cards[0],
            )
            merged_card = dict(cards[0])

            # 第二階段只覆蓋有明確辨識結果的關鍵欄位。
            for field in (
                "name_zh",
                "name_en",
                "primary_organization",
                "primary_department",
                "primary_job_title",
                "mobile",
                "phone",
                "phone_extension",
                "fax",
                "email",
                "country_code",
                "postal_code",
                "address",
            ):
                value = verified.get(field)
                if value not in (None, ""):
                    merged_card[field] = value

            merged_card["_critical_confidence"] = verified.get(
                "critical_confidence",
                0,
            )
            merged_card["_needs_review"] = bool(
                verified.get("needs_review", False)
            )
            merged_card["_review_reason"] = str(
                verified.get("review_reason", "") or ""
            ).strip()
            merged_card["_english_notes"] = str(
                verified.get("english_notes", "") or ""
            ).strip()

            card = self._normalize_card(merged_card, analysis)
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
      "country_code": "",
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
- 電話、手機、傳真與 Email 必須逐字逐碼忠實抄錄名片原文。
- 對每組數字至少重新核對兩次；任何看不清楚的數字不得猜測。
- 例如名片印「886-981058187」，不可漏字、換位或自行改成其他號碼。
- country_code 使用 ISO 兩碼，例如 TW、CN、JP、KR、US；無法可靠判斷時留空。
- 不要自行在原始電話欄位增刪國碼；格式統一會由程式完成。
- 多重協會身分放 affiliations，不要擠進主要職稱。
- primary_organization 應是主要任職機構。
- 名片同時有繁體中文與英文時：
  1. primary_organization 必須優先填繁體中文正式名稱。
  2. primary_department 必須優先填繁體中文正式名稱。
  3. primary_job_title 必須優先填繁體中文職稱。
  4. address 必須優先填繁體中文地址。
  5. 英文名稱與英文地址可放 notes，但不可取代上述主要欄位。
- name_zh 必須逐字核對，不可依英文名猜中文姓氏或用相近字替代。
- mobile 必須擷取完整號碼；若只看得到尾碼、局部號碼或內容模糊，請留空。
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

    async def _verify_critical_fields(
        self,
        image_items: list[dict],
        first_card: dict,
    ) -> dict:
        """
        第二次只核對最容易造成實務錯誤的欄位。
        不接受第一階段 confidence 作為依據，必須重新看圖。
        """
        prompt = f"""
你是企業名片的第二階段校對員。請重新查看附圖，不要直接相信第一次辨識結果。

第一次辨識：
{json.dumps(first_card, ensure_ascii=False)}

請只核對以下關鍵欄位：
- name_zh
- name_en
- primary_organization
- primary_department
- primary_job_title
- mobile
- phone
- phone_extension
- fax
- email
- country_code
- postal_code
- address

要求：
1. 中文姓名逐字核對，特別注意「蓁／蔡／秦／真」等相近字，不可猜測。
2. 名片有繁體中文時，primary_organization、primary_department、primary_job_title、
   address 一律使用繁體中文正式名稱或地址；英文只可放 english_notes。
3. 若同時存在中文與英文地址，address 必須填中文地址；只有沒有中文地址時，
   才可使用英文地址。
4. 手機必須完整。若只辨識到尾碼、局部、破折號後數字，mobile 留空。
4. 電話、分機、傳真不得混在手機欄位。
5. country_code 使用 ISO 兩碼；台灣為 TW，中國為 CN。
6. postal_code 只放郵遞區號；address 不得重複包含郵遞區號。
7. 看不清楚就留空，不能補猜。
8. critical_confidence 是你對上述關鍵欄位整體可靠度，0 到 100。

只回傳 JSON：
{{
  "name_zh": "",
  "name_en": "",
  "primary_organization": "",
  "primary_department": "",
  "primary_job_title": "",
  "mobile": "",
  "phone": "",
  "phone_extension": "",
  "fax": "",
  "email": "",
  "country_code": "",
  "postal_code": "",
  "address": "",
  "critical_confidence": 0,
  "needs_review": true,
  "review_reason": "",
  "english_notes": "可保留英文公司、部門、職稱與英文地址；若無則留空"
}}
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
                temperature=0.0,
            ),
        )
        return _extract_json(response.text)

    @staticmethod
    def _valid_mobile(value: Any) -> bool:
        raw = str(value or "").strip()
        digits = re.sub(r"\D+", "", raw)
        if not digits:
            return False
        # 台灣本地手機或含國碼的手機，至少應有 9 碼。
        if len(digits) < 9 or len(digits) > 15:
            return False
        # 只有尾碼或異常短片段常會以破折號開頭。
        if raw.startswith("-"):
            return False
        return True

    @staticmethod
    def _clean_zh_name(value: Any) -> str:
        raw = re.sub(r"\s+", "", str(value or "")).strip()
        return raw

    @staticmethod
    def _digits(value: Any) -> str:
        return re.sub(r"\D+", "", str(value or ""))

    @staticmethod
    def _clean_extension(value: Any) -> str:
        return re.sub(r"\D+", "", str(value or ""))

    @staticmethod
    def _infer_country_code(card: dict) -> str:
        explicit = str(card.get("country_code", "") or "").strip().upper()
        if re.fullmatch(r"[A-Z]{2}", explicit):
            return explicit

        blob = " ".join(
            str(card.get(key, "") or "")
            for key in (
                "address", "postal_code", "mobile", "phone", "fax",
                "primary_organization", "card_language",
            )
        ).lower()
        digits_blob = re.sub(r"\D+", "", blob)

        if (
            any(term in blob for term in ("台灣", "臺灣", "taiwan", "zh-tw"))
            or digits_blob.startswith("886")
        ):
            return "TW"
        if (
            any(term in blob for term in ("中國", "中国", "china", "prc", "zh-cn"))
            or digits_blob.startswith("86")
        ):
            return "CN"
        if any(term in blob for term in ("日本", "japan", "ja-jp")) or digits_blob.startswith("81"):
            return "JP"
        if any(term in blob for term in ("韓國", "韩国", "korea", "ko-kr")) or digits_blob.startswith("82"):
            return "KR"
        if any(term in blob for term in ("united states", "usa", "美國", "美国")):
            return "US"
        if any(term in blob for term in ("canada", "加拿大")):
            return "CA"
        if any(term in blob for term in ("germany", "德國", "德国")) or digits_blob.startswith("49"):
            return "DE"
        if any(term in blob for term in ("united kingdom", "英國", "英国")) or digits_blob.startswith("44"):
            return "GB"
        return ""

    @staticmethod
    def _tw_area_length(local_digits: str) -> int:
        """Taiwan landline area code length, including leading zero."""
        if local_digits.startswith("02"):
            return 2
        for prefix in ("037", "049", "0826", "082", "0836", "089"):
            if local_digits.startswith(prefix):
                return len(prefix)
        return 2

    @classmethod
    def _normalize_tw_number(cls, value: Any, kind: str) -> tuple[str, str]:
        raw = str(value or "").strip()
        digits = cls._digits(raw)
        if not digits:
            return "", ""

        if digits.startswith("00886"):
            digits = digits[5:]
        elif digits.startswith("886"):
            digits = digits[3:]

        # Country-code form omits the domestic trunk 0.
        if kind == "mobile":
            if digits.startswith("9") and len(digits) == 9:
                local = "0" + digits
            elif digits.startswith("09") and len(digits) == 10:
                local = digits
            else:
                return raw, ""
            display = f"{local[:4]}-{local[4:7]}-{local[7:]}"
            normalized = "+886" + local[1:]
            return display, normalized

        if digits.startswith("0"):
            local = digits
        else:
            local = "0" + digits

        if len(local) < 8 or len(local) > 11:
            return raw, ""

        area_len = cls._tw_area_length(local)
        area = local[:area_len]
        subscriber = local[area_len:]
        if len(subscriber) == 8:
            display_subscriber = subscriber[:4] + "-" + subscriber[4:]
        elif len(subscriber) == 7:
            display_subscriber = subscriber[:3] + "-" + subscriber[3:]
        else:
            midpoint = max(3, len(subscriber) // 2)
            display_subscriber = subscriber[:midpoint] + "-" + subscriber[midpoint:]
        display = f"{area}-{display_subscriber}"
        normalized = "+886" + local[1:]
        return display, normalized

    @classmethod
    def _normalize_cn_number(cls, value: Any, kind: str) -> tuple[str, str]:
        raw = str(value or "").strip()
        digits = cls._digits(raw)
        if not digits:
            return "", ""

        if digits.startswith("0086"):
            national = digits[4:]
        elif digits.startswith("86") and len(digits) > 11:
            national = digits[2:]
        else:
            national = digits.lstrip("0")

        if kind == "mobile":
            if len(national) != 11 or not national.startswith("1"):
                return raw, ""
            display = f"+86 {national[:3]} {national[3:7]} {national[7:]}"
            return display, "+86" + national

        if len(national) < 9 or len(national) > 12:
            return raw, ""
        # Typical China area code: 2 or 3 digits after country code.
        area_len = 2 if national.startswith(("10", "20", "21", "22", "23", "24", "25", "27", "28", "29")) else 3
        area = national[:area_len]
        subscriber = national[area_len:]
        if len(subscriber) == 8:
            subscriber_display = subscriber[:4] + " " + subscriber[4:]
        else:
            subscriber_display = subscriber
        return f"+86 {area} {subscriber_display}", "+86" + national

    @classmethod
    def _normalize_international_number(
        cls,
        value: Any,
        country_code: str,
    ) -> tuple[str, str]:
        raw = str(value or "").strip()
        digits = cls._digits(raw)
        if not digits:
            return "", ""

        calling_codes = {
            "JP": "81", "KR": "82", "US": "1", "CA": "1",
            "GB": "44", "DE": "49", "FR": "33", "SG": "65",
            "MY": "60", "TH": "66", "VN": "84", "IN": "91",
            "AU": "61", "NZ": "64",
        }
        calling = calling_codes.get(country_code, "")

        if raw.startswith("+"):
            normalized = "+" + digits
        elif digits.startswith("00"):
            normalized = "+" + digits[2:]
        elif calling:
            national = digits
            if national.startswith(calling) and len(national) > len(calling) + 5:
                normalized = "+" + national
            else:
                national = national.lstrip("0")
                normalized = "+" + calling + national
        else:
            # Unknown country: preserve readable input, do not invent a country code.
            return raw, ""

        body = normalized[1:]
        if calling and body.startswith(calling):
            national = body[len(calling):]
            chunks = [national[i:i+3] for i in range(0, len(national), 3)]
            display = "+" + calling + (" " + " ".join(chunks) if chunks else "")
        else:
            chunks = [body[i:i+3] for i in range(0, len(body), 3)]
            display = "+" + " ".join(chunks)
        return display, normalized

    @classmethod
    def _normalize_contact_number(
        cls,
        value: Any,
        country_code: str,
        kind: str,
    ) -> tuple[str, str]:
        if not str(value or "").strip():
            return "", ""
        if country_code == "TW":
            return cls._normalize_tw_number(value, kind)
        if country_code == "CN":
            return cls._normalize_cn_number(value, kind)
        return cls._normalize_international_number(value, country_code)

    @staticmethod
    def _normalize_postal_code(value: Any) -> str:
        raw = str(value or "").strip()
        if raw.endswith(".0") and raw[:-2].isdigit():
            raw = raw[:-2]
        return re.sub(r"\s+", "", raw)

    @staticmethod
    def _normalize_address(
        value: Any,
        postal_code: str,
        country_code: str,
    ) -> str:
        address = re.sub(r"\s+", " ", str(value or "")).strip(" ,，")
        if not address:
            return ""

        postal = re.escape(str(postal_code or "").strip())
        if postal:
            address = re.sub(rf"^\s*{postal}\s*[-,，]?\s*", "", address)
            address = re.sub(rf"\s*[-,，]?\s*{postal}\s*$", "", address)

        if country_code == "TW":
            address = re.sub(
                r"\s*[,，]?\s*(Taiwan|TAIWAN|台灣|臺灣|R\.?O\.?C\.?)\s*$",
                "",
                address,
                flags=re.IGNORECASE,
            )
        address = re.sub(r"\s*[,，]\s*", "，" if re.search(r"[\u4e00-\u9fff]", address) else ", ", address)
        return address.strip(" ,，")

    def _normalize_card(self, card: dict, analysis: dict) -> dict:
        normalized = {key: card.get(key, "") for key in MAIN_HEADERS}

        normalized["name_zh"] = self._clean_zh_name(card.get("name_zh", ""))
        normalized["name_en"] = str(card.get("name_en", "") or "").strip()
        normalized["primary_organization"] = str(
            card.get("primary_organization", "") or ""
        ).strip()
        normalized["primary_department"] = str(
            card.get("primary_department", "") or ""
        ).strip()
        normalized["primary_job_title"] = str(
            card.get("primary_job_title", "") or ""
        ).strip()

        country_code = self._infer_country_code(card)
        normalized["country_code"] = country_code

        mobile_raw = str(card.get("mobile", "") or "").strip()
        phone_raw = str(card.get("phone", "") or "").strip()
        fax_raw = str(card.get("fax", "") or "").strip()

        mobile_display, mobile_normalized = self._normalize_contact_number(
            mobile_raw, country_code, "mobile"
        )
        phone_display, phone_normalized = self._normalize_contact_number(
            phone_raw, country_code, "phone"
        )
        fax_display, fax_normalized = self._normalize_contact_number(
            fax_raw, country_code, "fax"
        )

        normalized["mobile"] = mobile_display
        normalized["mobile_normalized"] = mobile_normalized
        normalized["phone"] = phone_display
        normalized["phone_normalized"] = phone_normalized
        normalized["phone_extension"] = self._clean_extension(
            card.get("phone_extension", "")
        )
        normalized["fax"] = fax_display
        normalized["fax_normalized"] = fax_normalized

        normalized["postal_code"] = self._normalize_postal_code(
            card.get("postal_code", "")
        )
        normalized["address"] = self._normalize_address(
            card.get("address", ""),
            normalized["postal_code"],
            country_code,
        )

        address_value = normalized.get("address", "")
        address_has_zh = bool(re.search(r"[\u4e00-\u9fff]", address_value))
        card_language = str(card.get("card_language", "") or "")
        address_needs_review = bool(
            card_language.lower().startswith("zh")
            and address_value
            and not address_has_zh
        )

        normalized["affiliations_json"] = _json_text(card.get("affiliations", []))

        raw_websites = card.get("websites", [])
        normalized["websites"] = self._websites_formula(raw_websites)

        normalized["ocr_confidence"] = card.get(
            "ocr_confidence",
            analysis.get("classification_confidence", 0),
        )
        normalized["critical_confidence"] = card.get(
            "_critical_confidence",
            0,
        )
        normalized["raw_extracted_text"] = (
            self._single_line(card.get("raw_extracted_text", ""), max_chars=1200)
            if self.store_raw_text
            else ""
        )
        notes_parts = [
            str(card.get("notes", "") or "").strip(),
            str(card.get("_english_notes", "") or "").strip(),
        ]
        notes_value = self._single_line(
            "；".join(part for part in notes_parts if part),
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

        review_reasons = []

        critical_confidence = float(card.get("_critical_confidence") or 0)
        overall_confidence = float(normalized.get("ocr_confidence") or 0)

        if bool(card.get("_needs_review", False)):
            review_reasons.append(
                str(card.get("_review_reason", "") or "第二階段要求人工確認")
            )
        if critical_confidence < 92:
            review_reasons.append(
                f"關鍵欄位信心不足（{critical_confidence:.0f}）"
            )
        if not normalized.get("name_zh") and not normalized.get("name_en"):
            review_reasons.append("姓名未完整辨識")
        if mobile_raw and not normalized.get("mobile_normalized"):
            review_reasons.append("手機號碼格式或國別無法可靠標準化")
        if address_needs_review:
            review_reasons.append("中文名片未可靠辨識出中文地址")
        if not normalized.get("email") and not normalized.get("mobile"):
            review_reasons.append("缺少可可靠識別個人的 Email 或完整手機")

        if review_reasons:
            review_text = "；".join(dict.fromkeys(review_reasons))
            notes_value = self._single_line(
                f"{notes_value}；待確認：{review_text}"
                if notes_value
                else f"待確認：{review_text}",
                max_chars=self.notes_max_chars,
            )

        normalized["notes"] = notes_value
        normalized["card_language"] = card.get("card_language", "")
        normalized["review_status"] = (
            "AUTO_SAVED"
            if overall_confidence >= 95
            and critical_confidence >= 92
            and not review_reasons
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
        mobile = str(card.get("mobile_normalized") or "").strip()
        name_zh = _compact(card.get("name_zh"))
        name_en = _compact(card.get("name_en"))

        exact = []
        possible = []
        for row in rows:
            row_email = _normalize_email(row.get("email"))
            row_mobile = str(
                row.get("mobile_normalized")
                or (
                    self._normalize_contact_number(
                        row.get("mobile", ""),
                        str(row.get("country_code", "") or ""),
                        "mobile",
                    )[1]
                )
                or ""
            ).strip()
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
        review_status = row.get("review_status") or "NEEDS_REVIEW"
        title = (
            f"📇 **名片已{action}完成**"
            if review_status == "AUTO_SAVED"
            else f"⚠️ **名片已{action}，但關鍵欄位需要確認**"
        )
        return (
            f"{title}\n"
            f"姓名：{name}\n"
            f"機構：{company}\n"
            f"職稱：{role}\n"
            f"手機：{mobile}\n"
            f"Email：{email}\n"
            f"辨識可信度：{confidence or '未提供'}\n"
            f"狀態：`{review_status}`"
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
