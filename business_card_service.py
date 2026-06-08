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
            f"/values/{range_name}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
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
            f"/values/{range_name}?valueInputOption=RAW"
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

    @property
    def ready(self) -> bool:
        return not self.config_errors and self.gemini is not None and self.google is not None

    def status_text(self) -> str:
        if self.ready:
            return (
                f"ready | channel={self.architect_channel_id} | "
                f"sheet={self.main_sheet}/{self.history_sheet} | model={self.vision_model}"
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
            return False

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
        normalized["websites"] = _json_text(card.get("websites", []))
        normalized["ocr_confidence"] = card.get(
            "ocr_confidence",
            analysis.get("classification_confidence", 0),
        )
        normalized["raw_extracted_text"] = (
            self._single_line(card.get("raw_extracted_text", ""), max_chars=1200)
            if self.store_raw_text
            else ""
        )
        normalized["notes"] = self._single_line(
            card.get("notes", ""),
            max_chars=self.notes_max_chars,
        )
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
