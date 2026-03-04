# 菜餚描述重新產生工具

## 📋 功能說明

使用 ChatGPT API 重新產生每個菜品的描述與標籤，整合多個來源的資訊，輸出符合 Pydantic 格式的結果。

### 輸入文件

1. **axia_dish_descriptions.json** - 原始菜品數據（來自 `tool/dish_describer/`）
2. **url_summaries.json** - URL 內容摘要（由 `summarize_url_content.py` 生成）
3. **menu_tags_simplified.json** - 簡化版標籤系統

### 輸出格式

符合以下 Pydantic 模型：

```python
class DishDescriber(BaseModel):
    dish_name: str  # 菜名
    dish_describer: str  # 菜餚描述（自然段落、無誇飾）
    tags: List[str]  # 標籤列表（僅從允許清單擇取）

class DishRawData(BaseModel):
    source: str  # 來源網站 URL
    snippet: str  # 來源網站擷取到的文字段落
    summarize: str  # 來源網站擷取到的文字段落摘要後的結果

class DishOutputFormet(BaseModel):
    disg_detil: DishDescriber  # 菜餚描述結果
    dish_raw_datas: List[DishRawData]  # 透過爬蟲取的菜色資料
```

## 🔧 前置準備

### 1. 確保已完成前置步驟

```bash
# 步驟 1: 生成 URL 摘要（如果尚未執行）
cd tool/dish_describer_clear
python summarize_url_content.py

# 這會生成 url_summaries.json
```

### 2. 設置 API Key

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY='sk-your-api-key-here'
```

## 🚀 使用方法

### 1. 測試模式（處理前 5 個菜品）

```bash
cd tool/dish_describer_clear
python regenerate_dish_descriptions.py
# 當提示時輸入: 5
```

### 2. 完整處理所有菜品

```bash
python regenerate_dish_descriptions.py
# 當提示時輸入: yes
```

### 3. 自定義數量

```bash
python regenerate_dish_descriptions.py
# 當提示時輸入任意數字，如: 50
```

## 📊 預估成本與時間

### 使用 `gpt-4o-mini` 模型

| 項目 | 數值 |
|------|------|
| 總菜品數 | 496 個 |
| 預估費用 | ~$0.99 USD |
| 預估時間 | ~25 分鐘 |
| 每個菜品 | ~3 秒 + API 延遲 |

**注意**：每個菜品的處理成本約 $0.002，比 URL 摘要略高（因為需要整合多個來源）。

## 📤 輸出格式

### 輸出文件

- **`dish_descriptions_regenerated.json`** - 最終結果
- **`dish_descriptions_temp.json`** - 臨時文件（每 5 個自動保存）

### JSON 結構

```json
{
  "metadata": {
    "total_dishes": 496,
    "processed_dishes": 496,
    "success_count": 490,
    "error_count": 6,
    "model": "gpt-4o-mini",
    "processed_at": "2025-10-26 12:00:00"
  },
  "items": [
    {
      "disg_detil": {
        "dish_name": "紅蟳米糕",
        "dish_describer": "使用新鮮紅蟳肉和蟹黃，搭配長糯米手工蒸製而成。米粒軟糯吸收蟹黃精華，層次分明，香氣濃郁。是阿霞飯店的經典招牌菜，深受饕客喜愛。",
        "tags": ["紅蟳", "米糕", "蒸", "主食", "招牌", "海鮮類", "濃郁"]
      },
      "dish_raw_datas": [
        {
          "source": "https://example.com/article1",
          "snippet": "阿霞飯店的紅蟳米糕...",
          "summarize": "使用新鮮紅蟳肉與蟹黃，配以長糯米手工製作..."
        },
        {
          "source": "https://example.com/article2",
          "snippet": "這道招牌米糕...",
          "summarize": "經典台菜，米粒軟糯，蟹黃香濃..."
        }
      ]
    }
  ]
}
```

## 🔄 處理流程

1. **讀取數據**
   - 載入 `axia_dish_descriptions.json`（496 個菜品）
   - 載入 `url_summaries.json`（771 個 URL 摘要）
   - 載入 `menu_tags_simplified.json`（55 個允許標籤）

2. **建立映射**
   - URL → 摘要的映射表
   - 提取所有允許的標籤列表

3. **逐個處理菜品**
   - 收集該菜品相關的所有 URL 摘要
   - 構建 ChatGPT prompt（包含來源資料和標籤限制）
   - 調用 API 生成描述和標籤
   - 驗證標籤是否在允許清單中

4. **自動保存**
   - 每處理 5 個菜品自動保存臨時文件
   - 支持中斷後繼續處理

5. **生成報告**
   - 統計成功/失敗數量
   - 統計標籤使用頻率

## ⚠️ 注意事項

### 1. ChatGPT Prompt 設計

Prompt 要求：
- **描述風格**：客觀、自然、不誇飾
- **描述長度**：2-4 句話
- **標籤數量**：3-7 個
- **標籤限制**：必須從允許清單中選擇
- **標籤維度**：至少包含食材 + 烹飪方式

### 2. 標籤驗證

腳本會自動：
- 驗證所有標籤是否在允許清單中
- 移除不在清單中的標籤
- 顯示警告訊息

### 3. 中斷恢復

- 每處理 5 個菜品自動保存
- 重新運行時會詢問是否繼續
- 已處理的菜品會被跳過

### 4. 錯誤處理

如果 ChatGPT 調用失敗：
- 使用預設描述："{菜名}是阿霞飯店的特色菜餚。"
- 使用預設標籤：["經典"]
- 記錄錯誤但繼續處理

## 📊 輸出示例

### 成功案例

```json
{
  "disg_detil": {
    "dish_name": "砂鍋鴨",
    "dish_describer": "選用新鮮鴨肉，以傳統砂鍋慢火燉煮，湯頭濃郁鮮美。鴨肉軟嫩入味，肉質細緻不柴。搭配多種中藥材提味，營養豐富，適合全家享用。",
    "tags": ["鴨肉", "砂鍋", "煮", "湯品", "濃郁", "經典"]
  },
  "dish_raw_datas": [
    {
      "source": "https://...",
      "snippet": "...",
      "summarize": "傳統砂鍋燉煮，鴨肉軟嫩入味..."
    }
  ]
}
```

### 資料不足案例

```json
{
  "disg_detil": {
    "dish_name": "清炒時蔬",
    "dish_describer": "選用當季新鮮青菜，以大火快炒保持脆嫩口感。調味清淡，適合搭配主菜享用。",
    "tags": ["青菜", "炒", "清爽", "熱炒"]
  },
  "dish_raw_datas": [
    {
      "source": "https://...",
      "snippet": "清炒時蔬",
      "summarize": ""
    }
  ]
}
```

## 🛠️ 自定義設置

### 修改 AI 模型

```python
# 在 regenerate_dish_descriptions.py 中
self.model = "gpt-4o-mini"  # 改為 "gpt-4o" 獲得更好品質
```

### 調整描述長度

修改 `create_prompt()` 方法中的要求：

```python
# 原本：2-4 句話
# 可改為：3-5 句話或其他長度
```

### 調整標籤數量

```python
# 原本：3-7 個標籤
# 可改為：5-10 個標籤
```

### 調整處理速度

```python
# 在 main() 函數中
time.sleep(1)  # 改為 0.5 加快速度，或 2 減慢避免限流
```

## 📈 品質控制建議

1. **先測試小批量**
   - 處理前 10-20 個菜品
   - 檢查描述品質和標籤準確性
   - 調整 prompt 直到滿意

2. **人工抽查**
   - 隨機抽查 20-30 個結果
   - 驗證描述是否客觀、準確
   - 驗證標籤是否恰當

3. **標籤統計**
   - 檢查標籤使用頻率
   - 確保沒有過度集中或遺漏

4. **資料完整性**
   - 確認所有菜品都有描述
   - 確認所有菜品至少有 3 個標籤

## 🐛 常見問題

### Q1: API Key 錯誤

**解決方法**:
```powershell
# 檢查
echo $env:OPENAI_API_KEY

# 重新設置
$env:OPENAI_API_KEY='your-key'
```

### Q2: 找不到 url_summaries.json

**錯誤訊息**: `找不到 url_summaries.json`

**解決方法**:
```bash
# 先運行 URL 摘要腳本
python summarize_url_content.py
```

### Q3: 標籤不在允許清單

**現象**: 看到警告 `發現不在允許清單的標籤`

**原因**: ChatGPT 生成的標籤不在 `menu_tags_simplified.json` 中

**解決**: 腳本會自動過濾掉無效標籤，但建議：
1. 檢查是否 prompt 不夠清楚
2. 檢查 `menu_tags_simplified.json` 是否完整

### Q4: 描述品質不佳

**解決方法**:
1. 使用更強大的模型（如 `gpt-4o`）
2. 調整 prompt 的描述要求
3. 降低 temperature（目前是 0.3）

### Q5: 中途中斷怎麼辦？

**解決方法**:
1. 重新運行腳本
2. 選擇 `yes` 從中斷處繼續
3. 已處理的菜品會自動跳過

## 📝 後續處理建議

1. **匯入資料庫**
   - 將 `dish_descriptions_regenerated.json` 匯入 `dish_detail` 表
   - 更新 `description` 和 `tags` 欄位

2. **品質驗證**
   - 人工審核高頻率菜品的描述
   - 修正不準確或不自然的描述

3. **A/B 測試**
   - 對比新舊描述的用戶反應
   - 調整描述風格以提升轉換率

4. **持續優化**
   - 收集用戶反饋
   - 定期更新描述和標籤

## 🔗 相關文件

- `axia_dish_descriptions.json` - 原始數據（19.6MB）
- `url_summaries.json` - URL 摘要結果
- `menu_tags_simplified.json` - 簡化標籤系統
- `TAG_SIMPLIFICATION_REPORT.md` - 標籤簡化報告
- `URL_SUMMARIZER_README.md` - URL 摘要工具說明

---

**Created**: 2025-10-26
**Author**: Claude Code
**Version**: 1.0
