# AIOrderFood 🍽️

基於 FastAPI 的餐廳點餐系統，整合 LINE Login 認證、菜單管理、購物車與訂單處理功能。

## 📋 目錄

- [專案特色](#專案特色)
- [技術棧](#技術棧)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [開發環境設定](#開發環境設定)
- [資料庫管理](#資料庫管理)
- [前端開發](#前端開發)
- [測試](#測試)
- [API 文檔](#api-文檔)
- [常見問題](#常見問題)

---

## 🌟 專案特色

- **LINE Login 整合**：完整的 OAuth 2.0 認證流程，支援 JWT token 驗證
- **菜單管理系統**：支援分類、多語言、多規格定價、套餐組合
- **購物車功能**：基於 Session 的購物車，支援匿名用戶
- **共享桌號點餐**：QR Code 掃描，多用戶即時同步，SSE 推播技術
- **訂單處理**：訂單建立、狀態管理、快照保存
- **前後端分離**：Vue 3 SPA + FastAPI REST API
- **資料庫遷移**：Alembic 自動化 schema 管理
- **完整測試**：92 個單元測試 + 17 個 E2E 測試，完整覆蓋核心功能
- **✨ 全自動 E2E 測試**：一行命令執行，自動構建前端、啟動伺服器、運行測試、清理資源

---

## 🛠 技術棧

### 後端
- **框架**: FastAPI 0.119.0
- **資料庫**: PostgreSQL + SQLAlchemy 2.0.43
- **遷移工具**: Alembic 1.16.5
- **認證**: python-jose (JWT)
- **測試**: pytest 8.4.2
- **E2E 測試**: Playwright 1.40.0
- **HTTP 客戶端**: httpx 0.28.1

### 前端
- **框架**: Vue 3 + Vite
- **狀態管理**: Pinia
- **路由**: Vue Router
- **UI**: 自定義組件

### 基礎設施
- **容器化**: Docker (PostgreSQL, pgAdmin)
- **Python 版本**: 3.11.13+

---

## 📁 專案結構

```
AIOrderFood/
├── app/                          # 後端應用程式
│   ├── modules/                  # 功能模組
│   │   ├── line_login/          # LINE 登入模組
│   │   │   ├── __init__.py
│   │   │   └── router.py        # 登入路由
│   │   ├── menu/                # 菜單管理模組
│   │   │   ├── __init__.py
│   │   │   ├── menu.py          # 菜單業務邏輯
│   │   │   └── router.py        # 菜單 API 路由
│   │   └── order/               # 訂單模組
│   │       ├── __init__.py
│   │       ├── router.py        # 訂單 API 路由
│   │       └── service.py       # 訂單業務邏輯
│   ├── db.py                    # 資料庫連線設定
│   ├── models.py                # SQLAlchemy 資料模型
│   ├── session.py               # Session 管理
│   └── line_login.py            # LINE Login 工具函數
│
├── alembic/                     # 資料庫遷移
│   ├── versions/                # 遷移版本腳本
│   │   ├── e691d383068d_create_menu_tables.py
│   │   ├── 20251017_01_add_dish_detail_table.py
│   │   ├── 20251018_01_add_category_sort_order.py
│   │   ├── 20251021_02_add_session_and_order_tables.py
│   │   └── ...
│   ├── env.py                   # Alembic 環境設定
│   └── alembic.ini              # Alembic 配置檔
│
├── static/                      # 前端資源
│   ├── admin/                   # 管理後台 (Vanilla JS)
│   │   ├── admin.js
│   │   ├── orders.js
│   │   ├── sessions.js
│   │   └── set_editor.js
│   ├── src/                     # Vue 3 源碼
│   │   ├── components/          # Vue 組件
│   │   │   ├── BottomBar.vue
│   │   │   ├── DishModal.vue
│   │   │   └── ...
│   │   ├── views/               # 頁面視圖
│   │   │   ├── AdminMenuView.vue
│   │   │   ├── CartView.vue
│   │   │   └── ...
│   │   ├── stores/              # Pinia stores
│   │   │   ├── cart.js
│   │   │   └── chat.js
│   │   ├── router/              # 路由配置
│   │   │   └── index.js
│   │   └── main.js              # Vue 入口
│   ├── dist/                    # 打包後的前端資源
│   ├── package.json
│   └── vite.config.js
│
├── test/                        # 測試套件
│   ├── conftest.py              # pytest 配置與 fixtures
│   ├── test_menu.py             # 菜單功能測試
│   ├── test_order.py            # 訂單功能測試
│   ├── test_sse.py              # SSE 即時同步測試
│   └── e2e/                     # E2E 端到端測試（完全自動化）
│       ├── __init__.py          # Package 初始化
│       ├── config.py            # 測試配置（Port、超時、構建選項）
│       ├── frontend_builder.py  # 自動前端構建管理器
│       ├── server_manager.py    # 自動伺服器生命週期管理
│       ├── conftest.py          # E2E fixtures（自動啟動/關閉）
│       ├── playwright.config.py # Playwright 配置
│       ├── requirements.txt     # E2E 測試依賴
│       ├── E2E_README.md        # E2E 測試完整指南
│       ├── RUNNING_TESTS.md     # E2E 測試快速開始
│       ├── pages/               # Page Object Model
│       │   ├── base_page.py     # 基礎頁面類別
│       │   ├── menu_page.py     # 菜單頁面物件
│       │   └── cart_page.py     # 購物車頁面物件
│       └── tests/               # E2E 測試案例
│           ├── test_menu_browsing.py      # 菜單瀏覽測試
│           ├── test_cart_operations.py    # 購物車操作測試
│           └── test_shared_session.py     # 共享 Session 測試
│
├── tool/                        # 工具腳本
│   ├── dish_describer/          # 菜品描述爬蟲工具
│   │   ├── axia_selenium_describer.py
│   │   └── import_dish_details.py
│   └── menu_db.py               # 菜單資料匯入工具
│
├── docs/                        # 文檔
│   ├── CART_CONFLICT_RESOLUTION.md
│   └── RAG_implementation_plan.md
│
├── main.py                      # FastAPI 應用程式入口
├── requirements.txt             # Python 依賴套件
├── .env.example                 # 環境變數範例
├── CLAUDE.md                    # AI 開發指南
└── README.md                    # 本文件
```

---

## 🚀 快速開始

### 前置需求

- Python 3.11.13 或更高版本
- PostgreSQL 資料庫
- Node.js 16+ (用於前端開發)
- Docker (可選，用於快速建立資料庫)

### 首次安裝完整流程

#### 1. 克隆專案

```bash
git clone <repository-url>
cd AIOrderFood
```

#### 2. 建立 Python 虛擬環境（建議）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安裝後端依賴

```bash
pip install -r requirements.txt
```

#### 4. 設定環境變數

複製 `.env.example` 並填入實際值：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：

```env
# LINE Login 設定
LINE_CHANNEL_ID=your_channel_id
LINE_CHANNEL_SECRET=your_channel_secret
LINE_REDIRECT_URI=http://localhost:8000/auth/line/callback
LIFF_ID=your_liff_id

# 資料庫連線（二擇一）
# 方式 1: 使用完整連線字串（建議）
DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:PORT/DBNAME

# 方式 2: 使用個別參數
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_order_food

# 測試資料庫（必須包含 "test" 字樣以確保安全）
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:PORT/ai_order_food_test

# Session Cookie 設定
CART_SESSION_COOKIE_NAME=cart_session_id
CART_SESSION_COOKIE_MAX_AGE=21600
COOKIE_SECURE=false
```

#### 5. 建立資料庫

**選項 A: 使用 Docker（推薦）**

```bash
# 啟動 PostgreSQL
docker run --name postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  -d postgres

# 啟動 pgAdmin（可選）
docker run -d --name pgadmin \
  -p 11111:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@example.com \
  -e PGADMIN_DEFAULT_PASSWORD=your_password \
  -v pgadmin_data:/var/lib/pgadmin \
  dpage/pgadmin4
```

**選項 B: 使用本地 PostgreSQL**

```bash
# 使用 psql 創建資料庫
psql -U postgres
CREATE DATABASE ai_order_food;
CREATE DATABASE ai_order_food_test;
\q
```

#### 6. 執行資料庫遷移

```bash
# 升級到最新版本
alembic upgrade head

# Windows PowerShell 若需要設定環境變數
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:PORT/DB"
alembic upgrade head
```

#### 7. 匯入初始菜單資料（可選）

```bash
python tool/menu_db.py
```

#### 8. 啟動後端服務

```bash
uvicorn main:app --reload --port 8080

# 或使用更詳細的日誌級別
uvicorn main:app --reload --port 8080 --log-level debug
```

後端將在 http://127.0.0.1:8080 運行

#### 9. 安裝與啟動前端（可選）

```bash
# 進入前端目錄
cd static

# 安裝依賴
npm ci

# 開發模式（使用 Vite dev server）
npm run dev
# 前端將在 http://localhost:5173 運行

# 或建置為生產版本（由 FastAPI 提供）
npm run build
# 建置後訪問 http://127.0.0.1:8000
```

#### 10. 驗證安裝

```bash
# 執行測試
pytest -v

# 訪問 API 文檔
# 瀏覽器開啟: http://127.0.0.1:8000/docs
```
#### 可選

```bash
# 優化圖片 轉為WEBP 減少載入壓力
python tool/optimize_images.py
```

---

## 🔧 開發環境設定

### 後端開發

```bash
# 啟動開發伺服器（自動重載）
uvicorn main:app --reload

# 指定端口
uvicorn main:app --reload --port 3000

# 指定主機（允許外部訪問）
uvicorn main:app --reload --host 0.0.0.0
```

### API 文檔

FastAPI 自動生成互動式 API 文檔：

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### 編輯器設定

建議使用 VSCode 並安裝以下擴充：

- Python
- Pylance
- Vue - Official
- ESLint
- Prettier

---

## 💾 資料庫管理

### Alembic 遷移工作流程

```bash
# 1. 修改 app/models.py 中的資料模型

# 2. 自動生成遷移腳本
alembic revision --autogenerate -m "描述變更內容"

# 3. 檢查生成的遷移檔案
# 查看 alembic/versions/ 目錄下的最新檔案

# 4. 執行遷移
alembic upgrade head

# 5. 如需回滾
alembic downgrade -1

# 查看當前版本
alembic current

# 查看遷移歷史
alembic history
```

### 資料庫架構

#### 菜單相關表

- `category`: 菜單分類（含排序）
- `dish`: 菜品主表（支援套餐標記）
- `dish_price`: 菜品多規格定價（如大中小杯）
- `dish_translation`: 多語言名稱與描述
- `dish_detail`: 菜品詳細資訊（圖片、標籤等）
- `set_item`: 套餐組成（多對多關聯）

#### 訂單相關表

- `user_session`: 用戶會話（購物車存儲）
- `orders`: 訂單主表（含狀態、快照）
- `order_item`: 訂單明細項目

### 資料庫工具

```bash
# 使用 pgAdmin Web UI
# 訪問 http://localhost:11111

# 使用 psql 命令列
psql $DATABASE_URL

# 查看所有表
\dt

# 查看表結構
\d+ category

# 執行 SQL 查詢
SELECT * FROM category ORDER BY sort_order;
```

---

## 🎨 前端開發

### 開發模式設定

前端提供兩種運行方式：

#### 方式 1: Vite 開發伺服器（推薦開發使用）

```bash
cd static
npm run dev
```

- 前端運行於: http://localhost:5173
- 支援熱重載（Hot Module Replacement）
- API 請求自動代理到後端（配置於 `vite.config.js`）

#### 方式 2: FastAPI 提供靜態資源（模擬生產環境）

```bash
cd static
npm run build
cd ..
uvicorn main:app --reload
```

- 訪問: http://127.0.0.1:8000
- 提供打包後的生產版本
- 測試 SPA 路由與靜態資源

### 前端結構說明

```
static/
├── src/
│   ├── App.vue              # 根組件
│   ├── main.js              # 應用程式入口
│   ├── components/          # 可重用組件
│   │   ├── BottomBar.vue   # 底部導航列
│   │   ├── DishModal.vue   # 菜品詳情彈窗
│   │   └── ...
│   ├── views/               # 頁面組件
│   │   ├── CartView.vue    # 購物車頁面
│   │   ├── AdminMenuView.vue  # 管理後台
│   │   └── ...
│   ├── stores/              # Pinia 狀態管理
│   │   ├── cart.js         # 購物車狀態
│   │   └── chat.js         # 聊天功能狀態
│   └── router/
│       └── index.js         # 路由配置
├── admin/                   # 獨立的管理後台（Vanilla JS）
│   └── ...
├── vite.config.js          # Vite 配置
└── package.json            # 前端依賴
```

### API 代理配置

`static/vite.config.js`:

```javascript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // 後端地址
        changeOrigin: true
      }
    }
  }
})
```

---

## 🧪 測試

### 測試環境設定

確保 `.env` 中設定了測試資料庫：

```env
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:PORT/ai_order_food_test
E2E_BASE_URL=http://127.0.0.1:8000  # E2E 測試用
```

**安全機制**: 測試資料庫名稱必須包含 "test" 字樣，防止意外覆蓋生產資料。

### 單元測試 (Unit Tests)

測試後端 API 和業務邏輯。

```bash
# 執行所有單元測試
pytest

# 執行並顯示詳細輸出
pytest -v

# 執行並顯示 print 輸出
pytest -s

# 執行特定測試檔案
pytest test/test_menu.py

# 執行特定測試函數
pytest test/test_menu.py::test_category_crud

# 使用模式匹配執行測試
pytest -k "cart" -v

# 顯示測試覆蓋率（需要 pytest-cov）
pytest --cov=app --cov-report=html
```

### E2E 測試 (End-to-End Tests) - ✨ 完全自動化

使用 Playwright 進行前端介面的端到端測試。**無需手動啟動伺服器** - 測試框架會自動處理一切！

#### 🚀 一鍵執行測試

**首次安裝 E2E 測試依賴：**

```bash
# 安裝 Python 依賴
pip install -r test/e2e/requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium

# 安裝前端依賴（如果尚未安裝）
cd static && npm ci && cd ..
```

**執行測試（完全自動化）：**

```bash
# 顯示瀏覽器執行測試（推薦，可以看到測試過程）
pytest test/e2e/ --headed

# 無頭模式執行（CI/CD 適用）
pytest test/e2e/

# 慢動作觀察測試過程
pytest test/e2e/ --headed --slowmo 1000

# 執行特定測試
pytest test/e2e/tests/test_menu_browsing.py::test_menu_page_loads_successfully --headed

# 指定瀏覽器
pytest test/e2e/ --headed --browser chromium
pytest test/e2e/ --headed --browser firefox

# 錄製影片和追蹤（用於除錯）
pytest test/e2e/ --headed --video on --tracing on
```

**就這麼簡單！** 🎉 測試框架會自動：

1. ✅ 載入 `.env` 環境變數
2. ✅ 構建前端（`npm run build`）
3. ✅ 啟動測試伺服器（連接測試資料庫，port 8088）
4. ✅ 執行所有 E2E 測試
5. ✅ 測試完成後自動關閉伺服器

**自動化技術細節：**

- **自動前端構建**: 測試前自動執行 `npm run build`，確保前端資源最新
- **自動伺服器啟動**: 使用 subprocess 在背景啟動 uvicorn，自動設定 `TEST_MODE=1`
- **健康檢查**: 自動等待伺服器就緒（最多 30 秒，60 次重試）
- **日誌捕獲**: 伺服器日誌自動保存到臨時檔案，測試失敗時顯示
- **優雅關閉**: 測試完成後自動終止伺服器進程

**配置選項** (修改 `test/e2e/config.py`)：

```python
# 跳過前端構建（如果剛構建過）
SKIP_FRONTEND_BUILD = True

# 修改伺服器 Port（預設 8088）
SERVER_PORT = 8088

# 增加啟動超時（如果伺服器啟動較慢）
SERVER_STARTUP_TIMEOUT = 60
```

#### E2E 測試類型

**菜單瀏覽測試** (`test_menu_browsing.py`):
- ✅ 菜單頁面載入
- ✅ 瀏覽分類中的菜品
- ✅ 搜尋菜品功能
- ✅ 查看菜品詳情
- ✅ 切換分類
- ✅ 響應式設計（手機版）

**購物車操作測試** (`test_cart_operations.py`):
- ✅ 加入菜品到購物車
- ✅ 加入多個菜品
- ✅ 增加/減少數量
- ✅ 移除商品
- ✅ 清空購物車
- ✅ 總金額計算
- ✅ 購物車持久化
- ✅ 結帳按鈕狀態

**共享 Session 測試** (`test_shared_session.py`):
- ✅ 共享 Session 初始化
- ✅ URL 參數清理
- ✅ 多用戶購物車同步
- ✅ SSE 即時更新廣播
- ✅ 樂觀鎖版本衝突處理
- ✅ 不同桌號獨立購物車
- ✅ SSE 連線重連機制

詳細的 E2E 測試說明請參考:
- 📖 **完整指南**: [test/e2e/E2E_README.md](./test/e2e/E2E_README.md)
- 🚀 **快速開始**: [test/e2e/RUNNING_TESTS.md](./test/e2e/RUNNING_TESTS.md)

### 測試結構

```
test/
├── conftest.py              # pytest 配置與共用 fixtures
│                           # - 提供 db fixture (資料庫 session)
│                           # - 自動運行 Alembic 遷移
│                           # - 每個測試後清理資料
│
├── test_menu.py            # 菜單管理測試
│                           # - CRUD 操作
│                           # - 多語言支援
│                           # - 套餐組合
│
├── test_order.py           # 訂單系統測試
│                           # - 購物車操作
│                           # - 訂單建立
│                           # - 併發處理
│
├── test_sse.py             # SSE 即時同步測試
│                           # - 連線管理
│                           # - 訊息格式化
│                           # - 廣播機制
│
└── e2e/                    # E2E 端到端測試（完全自動化 🚀）
    ├── __init__.py         # Package 初始化
    │
    ├── config.py           # 測試配置管理
    │                       # - 伺服器 Port、超時設定
    │                       # - 健康檢查參數
    │                       # - 前端構建選項
    │
    ├── frontend_builder.py # 自動前端構建管理器
    │                       # - 檢查 node_modules
    │                       # - 執行 npm ci / npm run build
    │                       # - 驗證構建輸出
    │
    ├── server_manager.py   # 自動伺服器生命週期管理
    │                       # - Subprocess 啟動 uvicorn
    │                       # - Port 可用性檢查
    │                       # - 健康檢查（重試機制）
    │                       # - 日誌捕獲與優雅關閉
    │
    ├── conftest.py         # E2E fixtures（自動啟動/關閉）
    │                       # - build_frontend: 自動構建前端
    │                       # - test_server: 自動啟動/關閉伺服器
    │                       # - base_url: 動態伺服器 URL
    │                       # - db_session: 資料庫清理
    │
    ├── playwright.config.py # Playwright 配置
    ├── requirements.txt    # E2E 測試依賴
    ├── E2E_README.md       # E2E 測試完整指南（1000+ 行）
    ├── RUNNING_TESTS.md    # E2E 測試快速開始
    │
    ├── pages/              # Page Object Model
    │   ├── base_page.py
    │   ├── menu_page.py
    │   └── cart_page.py
    │
    └── tests/              # E2E 測試案例
        ├── test_menu_browsing.py      # 菜單瀏覽測試
        ├── test_cart_operations.py    # 購物車操作測試
        └── test_shared_session.py     # 共享 Session 測試
```

### 測試最佳實踐

**單元測試範例**:

```python
# 使用 TestClient 測試 API 端點
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_menu():
    response = client.get("/api/menu")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

# 使用 db fixture 進行資料庫操作
def test_create_category(db):
    from app.models import Category

    category = Category(name_zh="測試分類", sort_order=1)
    db.add(category)
    db.commit()
    db.refresh(category)

    assert category.category_id is not None
```

**E2E 測試範例** (使用 Page Object Model):

```python
def test_add_dish_to_cart(page: Page, base_url: str, sample_menu_data):
    """測試加入菜品到購物車"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 加入菜品到購物車
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)

    # 驗證購物車徽章更新
    cart_count = menu_page.get_cart_item_count()
    assert cart_count >= 1, "購物車徽章應該顯示至少 1"
```

---

## 📡 API 文檔

### 公開 API

#### 菜單 API

```bash
# 獲取完整菜單
GET /api/menu
# 回傳: [{ category_id, category_name, dishes: [...] }]

# 獲取購物車
GET /api/cart
# 回傳: { items: [...], total: 0 }

# 更新購物車
PUT /api/cart
# Body: { items: [{ dish_id, price_id, quantity }] }

# 清空購物車
DELETE /api/cart
```

#### 訂單 API

```bash
# 建立訂單
POST /api/orders
# Body: {
#   contact_name: "顧客名稱",
#   contact_phone: "0912345678",
#   contact_email: "email@example.com",
#   notes: "備註"
# }

# 查詢訂單
GET /api/orders/{order_id}
```

### 管理 API

```bash
# 分類管理
GET    /api/admin/categories
POST   /api/admin/categories
PATCH  /api/admin/categories/{id}
DELETE /api/admin/categories/{id}

# 菜品管理
GET    /api/admin/dishes
POST   /api/admin/dishes
PATCH  /api/admin/dishes/{id}
DELETE /api/admin/dishes/{id}

# 訂單管理
GET    /api/admin/orders
GET    /api/admin/orders/{id}
PATCH  /api/admin/orders/{id}

# Session 管理
GET    /api/admin/sessions
GET    /api/admin/sessions/{id}
DELETE /api/admin/sessions/{id}
```

### 認證 API

```bash
# 發起 LINE Login
GET /auth/line/login

# LINE OAuth 回調
GET /auth/line/callback?code=xxx&state=xxx
```

---

## ❓ 常見問題

### 後端問題

**Q: Alembic 無法連接資料庫**

```bash
# 檢查環境變數
echo $DATABASE_URL  # Linux/Mac
echo $env:DATABASE_URL  # Windows PowerShell

# 測試資料庫連線
psql $DATABASE_URL

# Windows PowerShell 設定環境變數
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:PORT/DB"
```

**Q: 測試失敗並顯示連線錯誤**

- 確認 `TEST_DATABASE_URL` 已設定
- 資料庫名稱必須包含 "test" 字樣
- 確認測試資料庫已建立：`CREATE DATABASE ai_order_food_test;`

**Q: 安裝 psycopg2-binary 失敗**

```bash
# Windows: 確保已安裝 Visual C++ Build Tools
# 或使用預編譯的 wheel
pip install psycopg2-binary --only-binary :all:
```

### 前端問題

**Q: 訪問 http://127.0.0.1:8000 出現 404 錯誤於 `/src/main.js`**

原因：直接訪問開發版 `index.html`，但 Vite dev server 未運行。

解決方案：
```bash
# 方案 1: 啟動 Vite dev server
cd static && npm run dev
# 訪問 http://localhost:5173

# 方案 2: 建置生產版本
cd static && npm run build
# 訪問 http://127.0.0.1:8000
```

**Q: API 請求返回 CORS 錯誤**

- 檢查 Vite 的 proxy 配置（`vite.config.js`）
- 確認後端已啟動並運行於正確端口

**Q: `/api/menu` 返回空資料**

```bash
# 檢查資料庫表
psql $DATABASE_URL -c "\dt"

# 執行遷移
alembic upgrade head

# 匯入測試資料
python tool/menu_db.py
```

### E2E 測試問題

**Q: E2E 測試失敗，提示 Port 已被佔用**

```bash
# 錯誤: ServerStartupError: Port 8088 已被佔用

# 解決方法 1: 終止佔用 port 的進程
# Windows
netstat -ano | findstr :8088
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8088 | xargs kill -9

# 解決方法 2: 修改測試 Port
# 編輯 test/e2e/config.py
SERVER_PORT = 8089  # 改為其他可用 port
```

**Q: E2E 測試失敗，提示資料庫連接錯誤**

```bash
# 錯誤: connection to server at "xxx" failed

# 檢查 TEST_DATABASE_URL 是否正確設定
grep TEST_DATABASE_URL .env

# 測試資料庫連接
python -c "import psycopg2; psycopg2.connect('YOUR_TEST_DATABASE_URL'); print('✓ 連接成功')"

# 確保資料庫存在
psql -U postgres -c "CREATE DATABASE ai_order_food_test;"
```

**Q: E2E 測試失敗，提示前端構建失敗**

```bash
# 錯誤: FrontendBuildError: npm run build 執行失敗

# 解決方法 1: 手動測試前端構建
cd static
npm ci
npm run build

# 解決方法 2: 跳過前端構建（如果剛構建過）
# 編輯 test/e2e/config.py
SKIP_FRONTEND_BUILD = True
```

**Q: E2E 測試啟動很慢或超時**

```bash
# 原因: 前端構建或伺服器啟動需要更多時間

# 解決方法: 增加超時設定
# 編輯 test/e2e/config.py
SERVER_STARTUP_TIMEOUT = 60  # 從 30 秒增加到 60 秒
FRONTEND_BUILD_TIMEOUT = 180  # 從 120 秒增加到 180 秒
```

**Q: 想查看 E2E 測試的伺服器日誌**

```bash
# E2E 測試失敗時會自動顯示最後 50 行日誌
# 日誌檔案位置會在錯誤訊息中顯示，例如：
# C:\Users\xxx\AppData\Local\Temp\e2e_server_xxxxx.log

# 啟用詳細日誌
# 編輯 test/e2e/config.py
LOG_LEVEL = "DEBUG"
```

**Q: E2E 測試執行時想跳過特定測試**

```bash
# 跳過慢速測試
pytest test/e2e/ -m "not slow" --headed

# 只執行特定測試
pytest test/e2e/tests/test_menu_browsing.py --headed

# 使用關鍵字過濾
pytest test/e2e/ -k "cart" --headed
```

### 開發環境問題

**Q: Docker PostgreSQL 容器無法啟動**

```bash
# 檢查容器狀態
docker ps -a

# 查看日誌
docker logs postgres

# 移除並重建
docker rm -f postgres
docker run --name postgres -e POSTGRES_PASSWORD=pwd -p 5432:5432 -d postgres
```

**Q: Python 虛擬環境激活失敗**

```bash
# Windows
# 如遇執行策略錯誤，以管理員權限執行：
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# Linux/Mac
# 確認使用 source 而非 sh
source venv/bin/activate
```

---

## 📚 更多資源

- **技術文檔**: [CLAUDE.md](./CLAUDE.md) - AI 開發指南
- **API 互動文檔**: http://127.0.0.1:8000/docs
- **購物車衝突解決**: [docs/CART_CONFLICT_RESOLUTION.md](./docs/CART_CONFLICT_RESOLUTION.md)
- **E2E 測試指南**: [test/e2e/E2E_README.md](./test/e2e/E2E_README.md) - 完整的 Playwright 測試文檔
- **E2E 快速開始**: [test/e2e/RUNNING_TESTS.md](./test/e2e/RUNNING_TESTS.md) - 快速執行測試

---

## 📝 開發注意事項

- **資料庫變更**: 修改 `app/models.py` 後必須執行 `alembic revision --autogenerate`
- **環境變數**: 生產環境記得將 `COOKIE_SECURE` 設為 `true`
- **psycopg2-binary**: 僅用於開發/測試，生產環境建議使用 `psycopg2`
- **測試資料庫**: 始終使用獨立的測試資料庫，避免污染開發資料

---

## 🤝 貢獻指南

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

提交前請確保：
- ✅ 所有測試通過 (`pytest`)
- ✅ 代碼符合 PEP 8 規範
- ✅ 新功能包含相應測試
- ✅ 更新相關文檔

---