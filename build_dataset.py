import os
import json

# 設定資料夾與檔案名稱
DATASET_DIR = "dataset"
TXT_FILE = "dataset.txt"
OUTPUT_JSON = "dataset.json"

def build():
    # 1. 檢查資料夾是否存在
    if not os.path.exists(DATASET_DIR):
        os.makedirs(DATASET_DIR)
        print(f"📁 已建立 '{DATASET_DIR}' 資料夾，請將照片放進去！")

    # 2. 檢查文字檔是否存在
    if not os.path.exists(TXT_FILE):
        with open(TXT_FILE, "w", encoding="utf-8") as f:
            f.write("01.jpg | 大俠，這是我第一次穿上這件洋裝，你說很好看對吧？\n")
        print(f"📄 找不到 '{TXT_FILE}'，已幫你建立範例檔，請依照格式修改！")
        return

    result = []
    
    # 3. 讀取文字檔並轉換為 JSON 格式
    with open(TXT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            # 略過空行或沒有分隔符號的行
            if not line or "|" not in line:
                continue
                
            filename, text = line.split("|", 1)
            filename = filename.strip()
            text = text.strip()
            
            # 檢查圖片實體檔案是否存在
            img_path = os.path.join(DATASET_DIR, filename)
            if os.path.exists(img_path):
                # 寫入專供網頁讀取的 JSON 格式
                result.append({
                    "url": f"/dataset/{filename}",
                    "text": text
                })
            else:
                print(f"⚠️ 警告: 找不到圖片實體檔案 '{filename}'，已略過此筆。")

    # 4. 輸出 dataset.json
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 成功轉換！共處理了 {len(result)} 筆資料，已儲存至 '{OUTPUT_JSON}'。")

if __name__ == "__main__":
    build()