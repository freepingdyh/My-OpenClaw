# Release Notes

## v1.5.38_R1

目前主要部署檔：`lobster_discord.py`

### 本版重點

- 交換日記先完成文字，再由 Photo Selector 決定當天最想留下的一個畫面。
- `selected_memory` 僅用於當次流程與既有 trace，不另建資料庫。
- `why_this_photo` 以小俠第一人稱自然融入日記收尾。
- 照片生成後，以 Vision 檢查場景、主要動作、關鍵物件與穿著意圖。
- Discord 顯示簡短結果：
  - 🟢 已反映
  - 🟡 部分反映
  - 🔴 未反映
- 檢查結果僅供判讀，不自動重拍，避免額外生圖費用。

### 部署提醒

- Zeabur 由 `main` 分支自動部署。
- 本文件目前建立於測試分支，不會影響正式服務。
