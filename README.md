# My-OpenClaw

My-OpenClaw 是小俠 Discord Bot 的主要程式庫，包含 Discord 互動、交換日記、小俠自主活動、衣櫃、Cosplay、照片生成與相關服務。

## 正式部署入口

- 主要程式：`lobster_discord.py`
- 正式分支：`main`
- 部署平台：Zeabur
- 部署方式：由 GitHub `main` 自動部署

> `lobster_discord.py` 位於儲存庫根目錄，是日常最常修改的正式部署檔。除非另有明確指示，不應改名、搬移或以其他版本檔取代。

## 目前版本

請查看 [`VERSION`](VERSION)。

## 版本紀錄

- [`CHANGELOG.md`](CHANGELOG.md)：各版本主要修改
- [`RELEASE_NOTES.md`](RELEASE_NOTES.md)：目前版本說明
- Git commit：完整歷史與差異

## 建議開發流程

1. 從 `main` 建立功能或測試分支。
2. 在分支修改並檢查差異。
3. 測試通過後合併回 `main`。
4. 穩定版本建立 Git Tag。
5. 若新版本異常，以新的 rollback commit 回復上一個穩定版本。

## 重要安全事項

- 不提交 Discord Token、API Key、密碼或 `.env` 機密資料。
- `main` 的更新可能立即觸發 Zeabur 正式部署。
- 修改大型主程式前，先確認基底 commit、版本號與目標函式。
