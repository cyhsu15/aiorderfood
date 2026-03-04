# URL 內容摘要整理工具

## 📋 功能說明

這個工具使用 **ChatGPT API** 自動整理阿霞飯店相關的網頁內容，從 771 個唯一 URL 中提取：

1. **阿霞飯店簡介** - 歷史、特色、榮譽認證
2. **餐點描述** - 菜名、特色、口味、做法、價格
3. **用餐資訊** - 營業時間、訂位方式、地址

## 🔧 安裝依賴

```bash
pip install openai
```

## 🔑 設置 API Key

### 獲取 OpenAI API Key

1. 前往 [OpenAI Platform](https://platform.openai.com/)
2. 登入並前往 **API Keys** 頁面
3. 創建新的 API Key
4. 複製 Key（只會顯示一次）

### 設置環境變量

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY='sk-your-api-key-here'
```

**Windows CMD:**
```cmd
set OPENAI_API_KEY=sk-your-api-key-here
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY=sk-your-api-key-here
```

或者創建 `.env` 文件：
```
OPENAI_API_KEY=sk-your-api-key-here
```

## 🚀 使用方法

### 1. 完整處理所有 URL

```bash
cd tool/dish_describer_clear
python summarize_url_content.py
```

當提示時輸入 `yes` 處理所有 771 個 URL。

### 2. 測試模式（處理前 5 個）

```bash
python summarize_url_content.py
```

當提示時輸入 `5` 只處理前 5 個 URL。

### 3. 自定義數量

當提示時輸入任意數字（如 `50`）處理前 50 個 URL。

## 📊 預估成本與時間

### 使用 `gpt-4o-mini` 模型

| 項目 | 數值 |
|------|------|
| 總 URL 數 | 771 個 |
| 預估費用 | ~$0.77 USD |
| 預估時間 | ~40 分鐘 |
| 每個 URL | ~3 秒 + API 延遲 |

### 成本計算

- 模型：`gpt-4o-mini`
- Input: $0.150 / 1M tokens
- Output: $0.600 / 1M tokens
- 每個 URL 平均: ~$0.001

**注意**：實際費用取決於 content 長度和 API 回應長度。

## 📤 輸出格式

### 輸出文件

- **`url_summaries.json`** - 最終結果
- **`url_summaries_temp.json`** - 臨時文件（每 10 個自動保存）

### JSON 結構

```json
{
  "metadata": {
    "total_urls": 771,
    "processed_urls": 771,
    "model": "gpt-4o-mini",
    "processed_at": "2025-10-25 23:30:00"
  },
  "summaries": [
    {
      "url": "https://example.com/...",
      "title": "網頁標題",
      "content_length": 15234,
      "original_content": "原始網頁內容...",
      "related_dishes": ["紅蟳米糕", "砂鍋鴨"],
      "summary": {
        "restaurant_intro": "阿霞飯店創立於1940年...",
        "dishes": [
          {
            "dish_name": "紅蟳米糕",
            "description": "以新鮮紅蟳肉和蟹黃...",
            "price": "時價",
            "tags": ["招牌", "米其林推薦", "海鮮"]
          }
        ],
        "dining_info": {
          "hours": "11:00-14:00, 17:00-21:00",
          "reservation": "需提前訂位",
          "location": "台南市中西區忠義路二段84巷7號"
        }
      },
      "processed_at": "2025-10-25 23:15:30"
    }
  ]
}
```

## 🔄 處理流程

1. **讀取數據** - 載入 `axia_dish_descriptions.json`（19.6MB）
2. **去重** - 從 4960 個 snippets 中提取 771 個唯一 URL
3. **批量處理** - 逐個調用 ChatGPT API
4. **自動保存** - 每 10 個自動保存，防止中斷丟失
5. **生成報告** - 統計處理結果

## ⚠️ 注意事項

### 1. API 限流

- 腳本已內建每個請求間隔 1 秒
- 如遇到限流錯誤，會自動記錄並繼續
- 可手動調整 `time.sleep(1)` 的延遲時間

### 2. 中斷恢復

- 每處理 10 個 URL 會自動保存臨時文件
- 如果中斷，可手動從臨時文件繼續
- 或修改腳本跳過已處理的 URL

### 3. Token 限制

- 每個 URL 的 content 限制為前 8000 字符
- 避免超過 ChatGPT 的 token 限制
- 如需完整內容，可調整 `content[:8000]`

### 4. 費用控制

- 建議先測試少量 URL（如 5-10 個）
- 確認結果滿意後再處理全部
- 可設置 OpenAI 賬戶的月度限額

## 🛠️ 自定義設置

### 修改 AI 模型

```python
# 在 summarize_url_content.py 中
self.model = "gpt-4o-mini"  # 改為 "gpt-4o" 或其他模型
```

### 調整提示詞

修改 `create_prompt()` 方法中的提示詞來改變輸出格式或重點。

### 調整處理速度

```python
# 在 main() 函數中
time.sleep(1)  # 改為 0.5 加快速度，或 2 減慢避免限流
```

## 📊 示例輸出

```json
{
  "restaurant_intro": "阿霞飯店創立於1940年，是台南知名的台菜老店，獲得米其林必比登推薦。以傳統手路菜聞名，招牌菜包括紅蟳米糕、砂鍋鴨等。",
  "dishes": [
    {
      "dish_name": "紅蟳米糕",
      "description": "採用新鮮紅蟳肉與蟹黃，配以長糯米手工製作，米粒軟糯，蟹黃香濃，層次分明。",
      "price": "時價",
      "tags": ["招牌", "米糕", "海鮮", "紅蟳"]
    },
    {
      "dish_name": "砂鍋鴨",
      "description": "傳統砂鍋燉煮，鴨肉軟嫩入味，湯頭濃郁鮮美。",
      "price": null,
      "tags": ["經典", "砂鍋", "鴨肉"]
    }
  ],
  "dining_info": {
    "hours": "午餐 11:00-14:00，晚餐 17:00-21:00",
    "reservation": "建議提前電話訂位",
    "location": "台南市中西區忠義路二段84巷7號"
  }
}
```

## 🐛 常見問題

### Q1: API Key 錯誤

**錯誤訊息**: `請設置 OPENAI_API_KEY 環境變量`

**解決方法**:
```bash
# 檢查是否已設置
echo $env:OPENAI_API_KEY  # PowerShell
echo %OPENAI_API_KEY%     # CMD

# 重新設置
$env:OPENAI_API_KEY='your-key'
```

### Q2: 處理太慢

**原因**: API 延遲 + 限流保護

**解決方法**:
- 調整 `time.sleep(1)` 為 `time.sleep(0.5)`
- 或使用更快的模型（但費用較高）

### Q3: 中途中斷怎麼辦？

**解決方法**:
1. 查看 `url_summaries_temp.json`
2. 記錄已處理的數量
3. 修改腳本從該位置繼續

### Q4: 輸出結果不理想

**解決方法**:
1. 調整 `create_prompt()` 中的提示詞
2. 提高 temperature（但會增加不確定性）
3. 使用更強大的模型如 `gpt-4o`

## 📝 後續處理建議

1. **合併菜色資訊** - 將多個 URL 的同一道菜合併
2. **去除重複** - 清理重複的餐點描述
3. **驗證準確性** - 人工檢查部分結果
4. **更新資料庫** - 將整理好的資訊匯入資料庫

## 🔗 相關文件

- `axia_dish_descriptions.json` - 原始數據（19.6MB）
- `menu_tags_simplified.json` - 簡化標籤系統
- `TAG_SIMPLIFICATION_REPORT.md` - 標籤簡化報告

---

**Created**: 2025-10-25
**Author**: Claude Code
**Version**: 1.0
