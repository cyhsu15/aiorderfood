# 菜餚描述匯入資料庫指南

## 📋 功能說明

`import_dish_details.py` 用於將菜餚描述和標籤匯入到資料庫的 `dish_detail` 表。

### 支援的數據格式

1. **dish_descriptions_regenerated.json** - ChatGPT 重新產生的描述（推薦）
2. **axia_dish_descriptions.json** - 原始爬蟲數據

## 🔧 前置準備

### 1. 準備必要文件

```bash
cd tool/dish_describer_clear

# 確保以下文件存在：
# - dish_descriptions_regenerated.json (由 regenerate_dish_descriptions.py 生成)
# - dish.csv (菜品 ID 對應表)
```

### 2. 準備 dish.csv

`dish.csv` 必須包含以下欄位：

```csv
dish_id,dish_name,category_name
1,紅蟳米糕,主食
2,砂鍋鴨,熱炒
...
```

**生成方法**：

```bash
# 從資料庫導出 dish.csv
# 使用 psql 或 pgAdmin 執行：
SELECT dish_id, name_zh as dish_name,
       (SELECT name_zh FROM category WHERE category_id = dish.category_id) as category_name
FROM dish
ORDER BY dish_id;

# 或使用 Python 腳本導出（如果有的話）
```

### 3. 設置資料庫連線

```powershell
# Windows PowerShell
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:PORT/DB"
```

## 🚀 使用方法

### 1. 試運行模式（推薦先執行）

```bash
# 試運行，不實際提交到資料庫
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --dry-run

# 如果要看標籤統計
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --dry-run \
    --show-tags
```

**輸出示例**：
```
讀取 JSON: dish_descriptions_regenerated.json

資料來源資訊：
  模型: gpt-4o-mini
  處理時間: 2025-10-26 12:00:00
  總菜品數: 496
  成功處理: 490

讀取 CSV: dish.csv

開始處理...

============================================================
DRY-RUN：未提交變更
============================================================
輸入菜色總數：496
成功更新 dish_detail：450
略過（CSV 無對應 dish_id）：10
略過（DB 無此 dish_id）：36
```

### 2. 正式匯入

確認試運行結果無誤後，執行正式匯入：

```bash
# 實際提交到資料庫
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --show-tags

# 或明確指定資料庫（如果環境變數未設置）
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --database-url "postgresql+psycopg2://USER:PASS@HOST:PORT/DB" \
    --show-tags
```

### 3. 只匯入部分數據

如果想先測試少量數據：

```bash
# 手動編輯 JSON 文件，只保留前 10 個 items
# 或使用 jq 工具過濾
jq '.items |= .[0:10]' dish_descriptions_regenerated.json > test_data.json

python import_dish_details.py test_data.json \
    --csv-path dish.csv \
    --dry-run
```

## 📊 命令列參數

| 參數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `json_path` | ✅ | - | JSON 文件路徑 |
| `--csv-path` | ❌ | `dish.csv` | dish.csv 路徑 |
| `--database-url` | ❌ | 環境變數 | 資料庫連線字串 |
| `--dry-run` | ❌ | `False` | 試運行模式，不提交變更 |
| `--show-tags` | ❌ | `False` | 顯示標籤統計 |

## 🔍 輸出說明

### 成功案例

```
============================================================
已提交變更
============================================================
輸入菜色總數：496
成功更新 dish_detail：450
略過（CSV 無對應 dish_id）：10
略過（DB 無此 dish_id）：36

============================================================
標籤統計（共 45 個不同標籤，總使用 2250 次）
============================================================
  蒸: 120 次
  炒: 95 次
  海鮮類: 85 次
  主食: 78 次
  濃郁: 65 次
  招牌: 60 次
  ...
```

### 統計說明

- **輸入菜色總數**：JSON 文件中的總菜品數
- **成功更新 dish_detail**：成功寫入資料庫的數量
- **略過（CSV 無對應 dish_id）**：菜名在 CSV 中找不到對應的 dish_id
- **略過（DB 無此 dish_id）**：dish_id 在資料庫中不存在

## ⚠️ 常見問題

### Q1: "CSV 無對應 dish_id" 數量很多

**原因**：
1. `dish.csv` 的菜名與 JSON 中的菜名不匹配
2. CSV 文件不完整

**解決方法**：
```bash
# 檢查 CSV 中的菜名
cat dish.csv | grep "紅蟳米糕"

# 檢查 JSON 中的菜名
jq '.items[].disg_detil.dish_name' dish_descriptions_regenerated.json | head -20

# 手動對比差異，更新 dish.csv 或 JSON
```

### Q2: "DB 無此 dish_id" 數量很多

**原因**：
1. CSV 中的 dish_id 在資料庫中不存在
2. 資料庫中的 dish 表尚未建立

**解決方法**：
```sql
-- 檢查資料庫中的 dish_id
SELECT COUNT(*) FROM dish;

-- 檢查特定 dish_id 是否存在
SELECT * FROM dish WHERE dish_id = 123;
```

### Q3: 標籤格式錯誤

**現象**：資料庫中的 tags 欄位格式不正確

**原因**：標籤以 `", "` 分隔（逗號+空格）

**確認**：
```sql
-- 檢查 tags 欄位
SELECT dish_id, tags FROM dish_detail LIMIT 10;
```

應該顯示為：`"蒸, 海鮮類, 主食, 濃郁"`

### Q4: 資料庫連線失敗

**錯誤訊息**：`請提供 --database-url 或設定環境變數 DATABASE_URL`

**解決方法**：
```powershell
# 設置環境變數
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:PORT/DB"

# 或直接在命令列指定
python import_dish_details.py dish_descriptions_regenerated.json \
    --database-url "postgresql+psycopg2://USER:PASS@HOST:PORT/DB"
```

### Q5: 想要重新匯入

**情況**：已經匯入過，想用新數據重新匯入

**說明**：
- 腳本使用 `upsert` 邏輯（有則更新，無則新增）
- 可以直接重新執行，會自動更新已存在的記錄
- 如果想清空後重新匯入：

```sql
-- 清空所有 dish_detail
TRUNCATE dish_detail CASCADE;

-- 或只刪除特定範圍
DELETE FROM dish_detail WHERE dish_id IN (SELECT dish_id FROM dish);
```

## 📝 資料庫結構

### dish_detail 表

```sql
CREATE TABLE dish_detail (
    dish_id INTEGER PRIMARY KEY REFERENCES dish(dish_id),
    description TEXT,
    tags TEXT,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**欄位說明**：
- `dish_id`: 外鍵，關聯到 `dish` 表
- `description`: 菜餚描述（來自 `dish_describer` 欄位）
- `tags`: 標籤，以逗號+空格分隔（例如："蒸, 海鮮類, 主食"）
- `image_url`: 圖片 URL（此腳本不處理）

## 🔄 完整流程示例

```bash
# 1. 生成菜餚描述
cd tool/dish_describer_clear
python regenerate_dish_descriptions.py
# 輸入: yes

# 2. 準備 dish.csv（如果還沒有）
# ... 從資料庫導出 ...

# 3. 試運行匯入
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --dry-run \
    --show-tags

# 4. 檢查輸出，確認無誤

# 5. 正式匯入
python import_dish_details.py dish_descriptions_regenerated.json \
    --csv-path dish.csv \
    --show-tags

# 6. 驗證資料庫
```

## 🔍 驗證匯入結果

### SQL 查詢

```sql
-- 檢查匯入的總數
SELECT COUNT(*) FROM dish_detail;

-- 查看前 10 筆
SELECT d.dish_id, d.name_zh, dd.description, dd.tags
FROM dish d
LEFT JOIN dish_detail dd ON d.dish_id = dd.dish_id
LIMIT 10;

-- 檢查缺少描述的菜品
SELECT d.dish_id, d.name_zh
FROM dish d
LEFT JOIN dish_detail dd ON d.dish_id = dd.dish_id
WHERE dd.dish_id IS NULL;

-- 統計標籤使用
SELECT
    TRIM(unnest(string_to_array(tags, ','))) as tag,
    COUNT(*) as count
FROM dish_detail
WHERE tags IS NOT NULL
GROUP BY tag
ORDER BY count DESC
LIMIT 20;
```

### Python 驗證腳本

```python
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    # 總數
    result = conn.execute(text("SELECT COUNT(*) FROM dish_detail"))
    print(f"總菜品數: {result.scalar()}")

    # 有描述的數量
    result = conn.execute(text("SELECT COUNT(*) FROM dish_detail WHERE description IS NOT NULL"))
    print(f"有描述: {result.scalar()}")

    # 有標籤的數量
    result = conn.execute(text("SELECT COUNT(*) FROM dish_detail WHERE tags IS NOT NULL"))
    print(f"有標籤: {result.scalar()}")
```

## 📚 相關文件

- `regenerate_dish_descriptions.py` - 生成菜餚描述
- `REGENERATE_README.md` - 菜餚描述生成工具說明
- `menu_tags_simplified.json` - 標籤系統定義

---

**Created**: 2025-10-26
**Author**: Claude Code
**Version**: 1.0
