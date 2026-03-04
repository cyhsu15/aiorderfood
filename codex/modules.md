# jin-xia-api-flask 後端模組與資料庫結構比對

## 後端必要套件（requirements.txt）
- Flask — Web 應用框架
- flask-cors — 跨來源請求處理（CORS）
- python-dotenv — 載入 .env 環境變數
- psycopg2-binary — PostgreSQL 驅動（含連線池 SimpleConnectionPool 使用）
- openai — OpenAI API SDK（程式同時相容新/舊版）
- pydantic — 回應模型驗證（LLM 回傳 JSON 驗證）


## 主要內部模組一覽
- app.py — 建立 Flask 應用、註冊藍圖、初始化 DB 連線池、服務前端靜態檔
- config.py — 載入與驗證環境變數（DB_*、OPENAI_API_KEY 等）
- db_pool.py / db.py — PostgreSQL 連線池與查詢 helper（`execute_query`）
- routes/
  - menu.py — `/api/menu`：查詢菜單並整理成前端 JSON 結構
  - chat.py — `/api/chat/`：整理 system prompt、呼叫 OpenAI、以 Pydantic 驗證回傳
- models.py — Pydantic 模型（`ChatResponse`, `Recommendation`）
- openai_client.py — OpenAI 用戶端封裝（同時支援新舊 SDK）

## 環境變數（.env）
- DB_USER, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT
- OPENAI_API_KEY
- DB_POOL_MIN, DB_POOL_MAX（選填）
- PORT（預設 3000）

---

## 資料庫結構比對

本專案（FastAPI + Alembic）現有資料表（依 `alembic/versions/e691d383068d_create_menu_tables.py` 與 `app/models.py`）：
- category(category_id PK, name_zh, name_en)
- dish(dish_id PK, category_id FK→category.category_id, name_zh, is_set, sort_order)
- dish_price(price_id PK, dish_id FK→dish.dish_id, price_label, price numeric(12,2))
- dish_translation((dish_id, lang) PK, name, description)
- set_item((set_id, item_id) PK, quantity, sort_order) —（jin-xia-api-flask 目前未用於查詢）

jin-xia-api-flask 的 `/api/menu` 查詢（`routes/menu.py`）邏輯假設：
- 需要上述四張主表與欄位：category、dish、dish_price、dish_translation
- 欄位包含：category_id、name_zh、dish_id、is_set、sort_order、price_label、price、lang、description

結論：
- 欄位與關聯皆相容；你目前的資料模型能滿足 Flask 後端查詢需求。
- 唯一需要注意「資料表命名」：jin-xia-api-flask 原始 SQL 使用未加引號的 CamelCase 名稱（如 `DishPrice`）。在 PostgreSQL 未加引號時會自動轉為小寫且不會自動補底線，導致 `DishPrice` 變成 `dishprice`，而你實際資料表是 `dish_price`（含底線），可能查不到資料。

### 修正建議（SQL 表名對齊）
請將查詢改為使用實際表名（全小寫且含底線），例如：

```sql
SELECT
  c.category_id,
  c.name_zh AS category_name,
  d.dish_id,
  d.name_zh AS dish_name,
  d.is_set,
  dt.description,
  dp.price_label,
  dp.price
FROM category c
LEFT JOIN dish d ON d.category_id = c.category_id
LEFT JOIN dish_price dp ON dp.dish_id = d.dish_id
LEFT JOIN dish_translation dt ON dt.dish_id = d.dish_id AND dt.lang = 'zh'
ORDER BY c.category_id, d.sort_order, d.dish_id, dp.price_id;
```

或保留 CamelCase 但一律加雙引號對應實際表名（若真的以帶引號 CamelCase 建表，通常不建議）：

```sql
FROM "category" c
LEFT JOIN "dish" d ON d.category_id = c.category_id
LEFT JOIN "dish_price" dp ON dp.dish_id = d.dish_id
LEFT JOIN "dish_translation" dt ON dt.dish_id = d.dish_id AND dt.lang = 'zh'
```

---

## 快速檢核清單
- 套件已安裝：Flask、flask-cors、python-dotenv、psycopg2-binary、openai、pydantic
- .env 已設定 DB_* 與（如需）OPENAI_API_KEY
- PostgreSQL 中實際表名為全小寫底線（category、dish、dish_price、dish_translation）
- `/api/menu` SQL 已改為使用正確表名與欄位

以上內容若需我直接套用到 `jin-xia-api-flask/routes/menu.py`，告訴我即可協助修改。
