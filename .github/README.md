# GitHub 專案維護說明

此目錄用於保存 My-OpenClaw 的 GitHub 專案維護規範。

## 主要程式

- Repository：`freepingdyh/My-OpenClaw`
- 正式分支：`main`
- 主要部署檔：`/lobster_discord.py`
- Zeabur：由 `main` 自動部署

## 建議流程

1. 新功能先建立獨立分支。
2. 修改後檢查差異與版本號。
3. 測試通過後再合併到 `main`。
4. 穩定版本建立 Git Tag，例如 `v1.5.38_R1`。
5. 發生問題時，以新的 rollback commit 回復，不改寫 Git 歷史。

## 安全原則

- 未經明確指示，不直接修改 `main`。
- 不任意改名或移動 `lobster_discord.py`。
- 不提交 Token、API Key、密碼或其他機密資訊。
