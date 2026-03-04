# E2E 測試指南 - ✨ 完全自動化

使用 Playwright 為 AIOrderFood 專案編寫端到端 (End-to-End) 測試。

**🎉 重大更新**: E2E 測試現在**完全自動化**！無需手動啟動伺服器，只需一行命令即可執行所有測試。

---

## ⚡ 快速參考

### ✨ 新版：自動化執行（推薦）

**一行命令搞定！**

```bash
# 顯示瀏覽器執行測試（推薦）
pytest test/e2e/ --headed

# 無頭模式執行
pytest test/e2e/

# 慢動作觀察
pytest test/e2e/ --headed --slowmo 1000

# 執行特定測試
pytest test/e2e/tests/test_menu_browsing.py --headed
```

**自動化做了什麼？**
1. ✅ 自動載入 `.env` 環境變數
2. ✅ 自動構建前端 (`npm run build`)
3. ✅ 自動啟動測試伺服器（port 8088，連接測試資料庫）
4. ✅ 執行所有 E2E 測試
5. ✅ 測試完成後自動關閉伺服器

### 📜 舊版：手動啟動（僅供參考）

<details>
<summary>點擊展開舊的手動流程（不再需要）</summary>

**Windows PowerShell:**
```powershell
$env:TEST_MODE = "1"
uvicorn main:app --reload
```

**Windows CMD:**
```cmd
set TEST_MODE=1
uvicorn main:app --reload
```

**Linux/Mac:**
```bash
TEST_MODE=1 uvicorn main:app --reload
```

然後在另一個終端執行：
```bash
pytest test/e2e/ --headed
```

</details>

---

## 📋 目錄

- [快速開始](#快速開始)
- [命令參考](#命令參考)
- [架構概覽](#架構概覽)
- [Page Object Model](#page-object-model)
- [測試案例](#測試案例)
- [執行測試](#執行測試)
- [最佳實踐](#最佳實踐)
- [故障排除](#故障排除)

---

## 🚀 快速開始（全自動化版）

### 1. 安裝依賴（一次性設定）

```bash
# 安裝 Python 依賴
pip install -r requirements.txt
pip install -r test/e2e/requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium

# 安裝前端依賴（如果尚未安裝）
cd static && npm ci && cd ..
```

### 2. 設定環境變數

在 `.env` 檔案中設定測試資料庫：

```bash
# 測試資料庫 URL（必須包含 "test" 字樣）
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ai_order_food_test
```

**注意**：不再需要手動設定 `E2E_BASE_URL`，測試框架會自動使用 `http://127.0.0.1:8088`。

### 3. 執行測試（一行命令）

```bash
# 顯示瀏覽器執行測試（推薦）
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
pytest test/e2e/ --headed --browser webkit

# 錄製影片和追蹤
pytest test/e2e/ --headed --video on --tracing on
```

**就這麼簡單！** 🎉 無需手動啟動伺服器或構建前端。

---

### 🔧 自動化流程說明

當您執行 `pytest test/e2e/` 時，背後發生的事情：

```
┌─────────────────────────────────────────────────┐
│ 步驟 1: 載入環境變數                             │
│   • 從 .env 讀取 TEST_DATABASE_URL              │
│   • 驗證配置完整性                               │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 步驟 2: 自動構建前端                             │
│   • 檢查 node_modules 是否存在                   │
│   • 執行 npm ci（如需要）                        │
│   • 執行 npm run build                          │
│   • 驗證 static/dist/ 構建成功                   │
│   • 耗時: 約 10-30 秒                           │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 步驟 3: 啟動測試伺服器                           │
│   • 檢查 port 8088 可用性                        │
│   • 使用 subprocess 啟動 uvicorn                 │
│   • 自動設定 TEST_MODE=1                         │
│   • 自動設定 DATABASE_URL=TEST_DATABASE_URL      │
│   • 耗時: 約 2-5 秒                             │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 步驟 4: 健康檢查                                 │
│   • 重複請求 http://127.0.0.1:8088/api/menu     │
│   • 最多重試 60 次（每次間隔 0.5 秒）            │
│   • 確保伺服器完全啟動                           │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 步驟 5: 執行測試                                 │
│   • 啟動 Playwright 瀏覽器                       │
│   • 運行所有測試案例                             │
│   • 截圖/錄影（如有失敗）                        │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 步驟 6: 清理資源                                 │
│   • 發送 SIGTERM 給伺服器進程                    │
│   • 等待 5 秒優雅關閉                            │
│   • 如仍運行則 SIGKILL 強制終止                  │
│   • 清理臨時檔案                                 │
└─────────────────────────────────────────────────┘
```

---

### 📁 自動化架構

新增的自動化組件：

```
test/e2e/
├── config.py               # 測試配置（port、超時、構建選項）
├── frontend_builder.py     # 自動前端構建管理器
├── server_manager.py       # 自動伺服器生命週期管理
└── conftest.py            # 整合所有自動化 fixtures
```

**核心 Fixtures：**

1. **`build_frontend`** (session, autouse)
   - 自動執行前端構建
   - 只在測試開始前執行一次
   - 可通過 `config.SKIP_FRONTEND_BUILD = True` 跳過

2. **`test_server`** (session)
   - 啟動測試伺服器
   - 所有測試共用同一伺服器實例
   - 測試結束後自動關閉

3. **`base_url`** (session)
   - 動態返回測試伺服器 URL
   - 自動依賴 `test_server`

---

### ⚙️ 配置選項

編輯 `test/e2e/config.py` 自定義行為：

```python
class E2EConfig:
    # 修改測試伺服器 Port
    SERVER_PORT = 8088  # 預設 8088

    # 跳過前端構建（如果剛構建過）
    SKIP_FRONTEND_BUILD = False  # 改為 True 可跳過

    # 增加啟動超時（如果伺服器啟動較慢）
    SERVER_STARTUP_TIMEOUT = 30  # 秒

    # 前端構建超時
    FRONTEND_BUILD_TIMEOUT = 120  # 秒

    # 啟用詳細日誌
    LOG_LEVEL = "INFO"  # 改為 "DEBUG" 看更多資訊
```

# 啟用追蹤 (用於除錯)
pytest test/e2e/ --tracing on
```

---

## 📝 命令參考

### 啟動測試模式

**Windows PowerShell:**
```powershell
$env:TEST_MODE = "1"
uvicorn main:app --reload
```

**Windows CMD:**
```cmd
# 方法 1: 分兩行執行 (推薦)
set TEST_MODE=1
uvicorn main:app --reload

# 方法 2: 單行執行
cmd /c "set TEST_MODE=1 && uvicorn main:app --reload"
```

**Linux/Mac:**
```bash
TEST_MODE=1 uvicorn main:app --reload
```

### 基本執行

```bash
# 執行所有 E2E 測試
pytest test/e2e/ -v

# 執行特定測試檔案
pytest test/e2e/tests/test_menu_browsing.py -v

# 執行特定測試案例
pytest test/e2e/tests/test_cart_operations.py::test_add_dish_to_cart -v

# 執行帶有特定標記的測試
pytest test/e2e/ -m e2e -v
pytest test/e2e/ -m slow -v
```

### 瀏覽器選項

```bash
# 顯示瀏覽器視窗 (預設是無頭模式)
pytest test/e2e/ --headed

# 指定瀏覽器
pytest test/e2e/ --browser chromium    # Chrome/Edge
pytest test/e2e/ --browser firefox     # Firefox
pytest test/e2e/ --browser webkit      # Safari

# 多瀏覽器同時測試
pytest test/e2e/ --browser chromium --browser firefox
```

### 除錯選項

```bash
# 錄製影片 (失敗時保留)
pytest test/e2e/ --video retain-on-failure

# 錄製所有測試的影片
pytest test/e2e/ --video on

# 啟用追蹤 (可在 Playwright Inspector 中查看)
pytest test/e2e/ --tracing on

# 截圖 (失敗時)
pytest test/e2e/ --screenshot only-on-failure

# 減速執行 (方便觀察,單位為毫秒)
pytest test/e2e/ --slowmo 1000
```

### 常見組合

```bash
# 開發除錯 (顯示瀏覽器 + 慢速)
pytest test/e2e/ --headed --slowmo 500

# 完整記錄 (影片 + 追蹤 + 截圖)
pytest test/e2e/ --video on --tracing on --screenshot on

# 並行執行 (需先安裝 pytest-xdist)
pytest test/e2e/ -n 4    # 4 個並行執行緒
pytest test/e2e/ -n auto # 自動偵測 CPU 核心數
```

### 生成報告

```bash
# 生成 HTML 報告 (需先安裝 pytest-html)
pytest test/e2e/ --html=test_results/e2e_report.html --self-contained-html

# 生成 JUnit XML 報告 (用於 CI/CD)
pytest test/e2e/ --junitxml=test_results/e2e_results.xml
```

---

## 🏗️ 架構概覽

### 目錄結構

```
test/e2e/
├── conftest.py              # 共享 fixtures (資料庫、瀏覽器、測試資料)
├── requirements.txt         # E2E 測試依賴
├── E2E_README.md           # 本文件
├── pages/                   # Page Object Model
│   ├── __init__.py
│   ├── base_page.py        # 基礎頁面類別
│   ├── menu_page.py        # 菜單頁面物件
│   └── cart_page.py        # 購物車頁面物件
└── tests/                   # 測試案例
    ├── __init__.py
    ├── test_menu_browsing.py      # 菜單瀏覽測試
    ├── test_cart_operations.py    # 購物車操作測試
    └── test_shared_session.py     # 共享 Session 測試
```

### Fixtures 說明

#### 資料庫 Fixtures

- **`db_engine`** (scope=session): 測試資料庫引擎
- **`db_session`** (scope=function): 測試資料庫 session,每個測試前後清理所有表格

#### Playwright Fixtures

- **`browser_context_args`**: 覆寫瀏覽器上下文參數 (視窗大小、語言、時區)
- **`page`**: 提供頁面實例,監聽 console 訊息和錯誤
- **`base_url`**: 應用程式基礎 URL

#### 測試資料 Fixtures

- **`sample_menu_data`**: 創建測試用的菜單資料 (2 個菜品: 紅燒魚、宮保雞丁)
- **`shared_session_id`**: 生成共享 session ID (UUID)
- **`table_id`**: 生成測試用的桌號

#### Helper Fixtures

- **`goto_menu_page`**: 導航到菜單頁面的 helper 函數
- **`wait_for_sse_message`**: 等待 SSE 訊息的 helper 函數
- **`expect_page`**: Playwright expect API

---

## 📦 Page Object Model

### 設計理念

Page Object Model (POM) 將頁面操作封裝成可重用的方法,提供:

- **可維護性**: UI 改變時只需更新頁面物件
- **可讀性**: 測試案例更接近自然語言
- **可重用性**: 同一個操作可在多個測試中使用

### BasePage (基礎頁面類別)

所有頁面物件的父類別,提供共用功能:

**核心方法**:

- `navigate(path)`: 導航到指定路徑
- `navigate_with_params(path, **params)`: 導航並帶上 URL 參數
- `wait_for_selector(selector)`: 等待元素出現
- `wait_for_text(text)`: 等待文字出現
- `click(selector)`: 點擊元素
- `fill(selector, value)`: 填寫表單
- `get_text(selector)`: 獲取元素文字
- `is_visible(selector)`: 檢查元素可見性
- `screenshot(filename)`: 截圖

**進階方法**:

- `wait_for_api_response(url_pattern)`: 等待 API 請求完成
- `get_local_storage(key)`: 獲取 localStorage
- `set_local_storage(key, value)`: 設定 localStorage
- `evaluate(script)`: 執行 JavaScript

### MenuPage (菜單頁面物件)

封裝菜單瀏覽相關的 UI 操作。

**關鍵方法**:

```python
# 頁面操作
menu_page.open()                                    # 開啟菜單頁面
menu_page.open(session_id="uuid", table_id="A1")   # 使用共享 Session 開啟
menu_page.wait_for_menu_loaded()                   # 等待菜單載入

# 分類操作
categories = menu_page.get_categories()            # 獲取所有分類
menu_page.select_category("熱炒")                   # 選擇分類

# 菜品操作
dishes = menu_page.get_dishes_in_category()        # 獲取當前分類菜品
menu_page.search_dish("紅燒魚")                     # 搜尋菜品
menu_page.add_dish_to_cart("紅燒魚", quantity=2)   # 加入購物車

# 購物車操作
count = menu_page.get_cart_item_count()            # 獲取購物車數量
menu_page.open_cart()                              # 開啟購物車

# 驗證
menu_page.verify_menu_loaded()                     # 驗證菜單已載入
menu_page.verify_shared_session_active("A1")       # 驗證共享 Session 啟用
```

**元素選擇器**:

- `[data-testid="category-tab"]`: 分類標籤
- `[data-testid="dish-card"]`: 菜品卡片
- `[data-testid="add-to-cart-btn"]`: 加入購物車按鈕
- `[data-testid="cart-badge"]`: 購物車徽章

### CartPage (購物車頁面物件)

封裝購物車相關的 UI 操作。

**關鍵方法**:

```python
# 購物車狀態
cart_page.is_open()                                # 檢查購物車是否開啟
cart_page.wait_for_cart_loaded()                   # 等待購物車載入
cart_page.is_empty()                               # 檢查購物車是否為空

# 獲取資訊
items = cart_page.get_cart_items()                 # 獲取所有商品
count = cart_page.get_cart_item_count()            # 獲取商品種類數
total = cart_page.get_total_quantity()             # 獲取商品總數量
amount = cart_page.get_total_amount()              # 獲取總金額

# 修改商品
cart_page.increase_item_quantity("紅燒魚", times=2) # 增加數量
cart_page.decrease_item_quantity("紅燒魚", times=1) # 減少數量
cart_page.remove_item("紅燒魚")                     # 移除商品
cart_page.clear_cart()                             # 清空購物車

# 結帳
cart_page.is_checkout_enabled()                    # 檢查結帳按鈕可用性
cart_page.checkout()                               # 前往結帳

# 同步相關
version = cart_page.get_cart_version()             # 獲取版本號
cart_page.wait_for_sse_update()                    # 等待 SSE 更新
cart_page.has_version_conflict()                   # 檢查版本衝突
cart_page.verify_cart_synced(expected_items)       # 驗證購物車已同步
```

**元素選擇器**:

- `[data-testid="cart-panel"]`: 購物車面板
- `[data-testid="cart-item"]`: 購物車商品
- `[data-testid="increase-quantity-btn"]`: 增加數量按鈕
- `[data-testid="checkout-btn"]`: 結帳按鈕

---

## 🧪 測試案例

### test_menu_browsing.py (菜單瀏覽測試)

測試用戶瀏覽菜單的完整流程。

**測試案例** (6 個):

1. `test_menu_page_loads_successfully`: 測試菜單頁面成功載入
2. `test_browse_dishes_in_category`: 測試瀏覽分類中的菜品
3. `test_search_dish_by_name`: 測試搜尋菜品
4. `test_view_dish_details`: 測試查看菜品詳情
5. `test_switch_between_categories`: 測試切換分類
6. `test_menu_responsive_design`: 測試菜單響應式設計 (手機版)

**範例**:

```python
def test_menu_page_loads_successfully(page: Page, base_url: str, sample_menu_data):
    """測試菜單頁面成功載入"""
    menu_page = MenuPage(page, base_url)

    menu_page.open()
    menu_page.verify_menu_loaded()

    categories = menu_page.get_categories()
    assert len(categories) > 0, "應該至少有一個分類"
```

### test_cart_operations.py (購物車操作測試)

測試購物車的完整操作流程。

**測試案例** (10 個):

1. `test_add_dish_to_cart`: 測試加入菜品到購物車
2. `test_add_multiple_dishes_to_cart`: 測試加入多個不同菜品
3. `test_increase_cart_item_quantity`: 測試增加商品數量
4. `test_decrease_cart_item_quantity`: 測試減少商品數量
5. `test_remove_item_from_cart`: 測試移除商品
6. `test_clear_cart`: 測試清空購物車
7. `test_cart_total_amount_calculation`: 測試總金額計算
8. `test_cart_persists_across_page_reload`: 測試購物車持久化
9. `test_cart_checkout_button_enabled_when_not_empty`: 測試結帳按鈕狀態

**範例**:

```python
def test_add_dish_to_cart(page: Page, base_url: str, sample_menu_data):
    """測試加入菜品到購物車"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    menu_page.open()
    menu_page.wait_for_menu_loaded()
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)

    cart_count = menu_page.get_cart_item_count()
    assert cart_count >= 1, "購物車徽章應該顯示至少 1"
```

### test_shared_session.py (共享 Session 測試)

測試多用戶共享桌號訂餐的完整流程。

**測試案例** (8 個):

1. `test_shared_session_initialization`: 測試共享 Session 初始化
2. `test_shared_session_url_parameters_cleaned`: 測試 URL 參數清理
3. `test_cart_sync_between_two_users`: 測試兩個用戶之間的購物車同步
4. `test_cart_update_broadcasts_to_all_users`: 測試購物車更新廣播到所有用戶
5. `test_optimistic_locking_prevents_conflicts`: 測試樂觀鎖防止版本衝突
6. `test_different_tables_have_separate_carts`: 測試不同桌號有獨立購物車
7. `test_sse_connection_reconnects_on_disconnect`: 測試 SSE 重新連線

**範例**:

```python
def test_cart_sync_between_two_users(context: BrowserContext, base_url: str,
                                     sample_menu_data, shared_session_id: str, table_id: str):
    """測試兩個用戶之間的購物車同步"""
    user1_page = context.new_page()
    user2_page = context.new_page()

    user1_menu = MenuPage(user1_page, base_url)
    user2_menu = MenuPage(user2_page, base_url)

    # 兩個用戶開啟相同的共享 Session
    user1_menu.open(session_id=shared_session_id, table_id=table_id)
    user2_menu.open(session_id=shared_session_id, table_id=table_id)

    # User 1 加入菜品
    user1_menu.add_dish_to_cart("紅燒魚", quantity=1)

    # 等待 SSE 同步
    user2_page.wait_for_timeout(1000)

    # 驗證 User 2 看到更新
    user2_cart_count = user2_menu.get_cart_item_count()
    assert user2_cart_count >= 1, "User 2 應該看到購物車更新"
```

---

## ▶️ 執行測試

### 基本執行

```bash
# 執行所有 E2E 測試
pytest test/e2e/ -v

# 執行特定測試檔案
pytest test/e2e/tests/test_menu_browsing.py -v

# 執行特定測試案例
pytest test/e2e/tests/test_cart_operations.py::test_add_dish_to_cart -v

# 執行帶有特定標記的測試
pytest test/e2e/ -m e2e -v
pytest test/e2e/ -m slow -v
```

### 瀏覽器選項

```bash
# 顯示瀏覽器視窗 (預設是無頭模式)
pytest test/e2e/ --headed

# 指定瀏覽器
pytest test/e2e/ --browser chromium    # Chrome/Edge
pytest test/e2e/ --browser firefox     # Firefox
pytest test/e2e/ --browser webkit      # Safari

# 多瀏覽器同時測試
pytest test/e2e/ --browser chromium --browser firefox
```

### 除錯選項

```bash
# 錄製影片 (失敗時保留)
pytest test/e2e/ --video retain-on-failure

# 錄製所有測試的影片
pytest test/e2e/ --video on

# 啟用追蹤 (可在 Playwright Inspector 中查看)
pytest test/e2e/ --tracing on

# 截圖 (失敗時)
pytest test/e2e/ --screenshot only-on-failure

# 減速執行 (方便觀察,單位為毫秒)
pytest test/e2e/ --slowmo 1000
```

### 並行執行

```bash
# 使用 pytest-xdist 並行執行 (需先安裝: pip install pytest-xdist)
pytest test/e2e/ -n 4    # 4 個並行執行緒
pytest test/e2e/ -n auto # 自動偵測 CPU 核心數
```

### 生成報告

```bash
# 生成 HTML 報告 (需先安裝: pip install pytest-html)
pytest test/e2e/ --html=test_results/e2e_report.html --self-contained-html

# 生成 JUnit XML 報告 (用於 CI/CD)
pytest test/e2e/ --junitxml=test_results/e2e_results.xml
```

---

## 💡 最佳實踐

### 1. Page Object Model 設計原則

**✅ 好的做法**:

```python
# 在頁面物件中封裝 UI 操作
menu_page.add_dish_to_cart("紅燒魚", quantity=2)
cart_page.verify_cart_synced(expected_items)
```

**❌ 不好的做法**:

```python
# 直接在測試中操作 DOM
page.click('[data-testid="add-to-cart-btn"]')
page.fill('[data-testid="quantity-input"]', "2")
```

### 2. 使用 data-testid 選擇器

**✅ 好的做法**:

```python
# 使用專為測試設計的選擇器
self.add_to_cart_btn = '[data-testid="add-to-cart-btn"]'
```

**❌ 不好的做法**:

```python
# 依賴 CSS 類別或 XPath (容易因 UI 改版而損壞)
self.add_to_cart_btn = '.btn.btn-primary.add-cart'
self.add_to_cart_btn = '//div[@class="menu"]//button[1]'
```

### 3. 等待策略

**✅ 好的做法**:

```python
# 使用 Playwright 的自動等待
menu_page.wait_for_selector('[data-testid="dish-card"]')
cart_page.wait_for_item_added("紅燒魚")

# 等待特定條件
page.wait_for_function("() => window.cartLoaded === true")
```

**❌ 不好的做法**:

```python
# 使用固定時間的 sleep
import time
time.sleep(5)  # 太長浪費時間,太短可能不穩定
```

### 4. 測試獨立性

**✅ 好的做法**:

```python
# 每個測試都重新初始化狀態
def test_cart_operations(page, sample_menu_data):
    menu_page = MenuPage(page, base_url)
    menu_page.open()
    # ... 測試邏輯
```

**❌ 不好的做法**:

```python
# 測試之間有依賴關係
def test_add_to_cart():  # 測試 1
    # 加入商品
    pass

def test_checkout():  # 測試 2 依賴測試 1 的結果
    # 直接結帳 (假設購物車有商品)
    pass
```

### 5. 斷言清晰性

**✅ 好的做法**:

```python
# 清晰的斷言訊息
assert cart_count >= 1, f"購物車徽章應該顯示至少 1,實際為 {cart_count}"
assert fish_items[0]["quantity"] == 2, "紅燒魚數量應該為 2"
```

**❌ 不好的做法**:

```python
# 無意義的斷言訊息
assert cart_count >= 1  # 沒有訊息,失敗時不知道原因
```

### 6. 測試資料管理

**✅ 好的做法**:

```python
# 使用 fixture 提供測試資料
@pytest.fixture
def sample_menu_data(db_session):
    # 在資料庫中創建測試資料
    category = Category(name_zh_tw="測試分類")
    db_session.add(category)
    db_session.commit()
    return category
```

**❌ 不好的做法**:

```python
# 硬編碼測試資料或依賴生產資料
def test_menu():
    # 假設資料庫中已經有特定的菜品
    menu_page.select_category("熱炒")  # 如果不存在就會失敗
```

### 7. 共享 Session 測試

**測試多用戶同步時的注意事項**:

```python
# 使用 BrowserContext 創建多個頁面
def test_multi_user(context: BrowserContext, shared_session_id):
    user1_page = context.new_page()
    user2_page = context.new_page()

    try:
        # 測試邏輯
        pass
    finally:
        # 確保關閉頁面
        user1_page.close()
        user2_page.close()
```

**等待 SSE 同步**:

```python
# 操作後等待 SSE 廣播
user1_menu.add_dish_to_cart("紅燒魚")
user2_page.wait_for_timeout(1000)  # 等待 SSE 同步

# 或使用更精確的等待
cart_page.wait_for_sse_update(timeout=5000)
```

---

## 🔧 故障排除

### ✨ 自動化模式常見問題

#### 問題 A: Port 8088 已被佔用

**錯誤訊息**:
```
ServerStartupError: Port 8088 已被佔用
```

**解決方法**:

```bash
# 方法 1: 終止佔用 port 的進程
# Windows
netstat -ano | findstr :8088
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8088 | xargs kill -9

# 方法 2: 修改測試 Port
# 編輯 test/e2e/config.py
SERVER_PORT = 8089  # 改為其他可用 port
```

---

#### 問題 B: 測試資料庫連接失敗

**錯誤訊息**:
```
ServerStartupError: 伺服器未在 30 秒內就緒
最後 50 行日誌:
  sqlalchemy.exc.OperationalError: connection to server at "xxx" failed
```

**解決方法**:

```bash
# 1. 檢查 TEST_DATABASE_URL 是否正確設定
grep TEST_DATABASE_URL .env

# 2. 測試資料庫連接
python -c "import psycopg2; psycopg2.connect('YOUR_TEST_DATABASE_URL'); print('✓ 連接成功')"

# 3. 確保資料庫存在
psql -U postgres -c "CREATE DATABASE ai_order_food_test;"

# 4. 檢查 PostgreSQL 服務是否運行
# Windows: 服務管理器
# Linux: sudo systemctl status postgresql
```

---

#### 問題 C: 前端構建失敗

**錯誤訊息**:
```
FrontendBuildError: npm run build 執行失敗
```

**解決方法**:

```bash
# 1. 手動測試前端構建
cd static
npm ci
npm run build

# 2. 如果成功，可以跳過構建加速測試
# 編輯 test/e2e/config.py
SKIP_FRONTEND_BUILD = True

# 3. 如果失敗，檢查 Node.js 版本
node --version  # 建議 v16+

# 4. 清理並重新安裝依賴
cd static
rm -rf node_modules package-lock.json
npm install
```

---

#### 問題 D: 伺服器啟動超時

**錯誤訊息**:
```
ServerStartupError: 伺服器未在 30 秒內就緒
```

**解決方法**:

```python
# 編輯 test/e2e/config.py，增加超時時間
SERVER_STARTUP_TIMEOUT = 60  # 從 30 秒增加到 60 秒
FRONTEND_BUILD_TIMEOUT = 180  # 從 120 秒增加到 180 秒
```

---

#### 問題 E: 想查看伺服器詳細日誌

**解決方法**:

1. **測試失敗時自動顯示日誌** - 錯誤訊息會包含最後 50 行日誌和日誌檔案位置

2. **啟用 DEBUG 日誌**:
```python
# 編輯 test/e2e/config.py
LOG_LEVEL = "DEBUG"
```

3. **手動查看日誌檔案** - 日誌檔案位置會在測試輸出中顯示:
```
✓ 日誌檔案: C:\Users\xxx\AppData\Local\Temp\e2e_server_xxxxx.log
```

---

#### 問題 F: .env 檔案未正確載入

**症狀**: TEST_DATABASE_URL 明明在 .env 中設定了，但伺服器仍連接不到

**解決方法**:

```bash
# 1. 確認 .env 檔案在專案根目錄
ls .env

# 2. 驗證環境變數讀取
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TEST_DATABASE_URL'))"

# 3. 確保 python-dotenv 已安裝
pip install python-dotenv
```

---

### 📜 手動模式常見問題（舊版）

<details>
<summary>點擊展開手動啟動模式的故障排除（不再需要）</summary>

#### ⚠️ 問題 0: 應用程式連接到開發資料庫而非測試資料庫 (最常見!)

**症狀**:
- E2E 測試執行後,開發資料庫的資料被清空
- 測試資料與實際資料混在一起
- 測試失敗,因為預期的測試資料不存在

**原因**:

直接執行 `uvicorn main:app --reload` 會讀取 `.env` 的 `DATABASE_URL` (開發資料庫),而不是 `TEST_DATABASE_URL` (測試資料庫)。

**解決方法**:

```bash
# ✅ 正確: 使用 TEST_MODE 環境變數
TEST_MODE=1 uvicorn main:app --reload              # Linux/Mac
$env:TEST_MODE = "1"; uvicorn main:app --reload    # Windows PowerShell

# Windows CMD (分兩行執行)
set TEST_MODE=1
uvicorn main:app --reload

# ❌ 錯誤: 直接啟動 (會連接到開發資料庫!)
uvicorn main:app --reload
```

**⚠️ Windows CMD 注意事項**:
在 Windows CMD 中,`set TEST_MODE=1 && uvicorn main:app --reload` **無法正常工作**,因為環境變數不會傳遞到第二個命令。請使用分兩行的方式執行。

**驗證是否連接到測試資料庫**:

啟動時應該看到明顯的警告:

```
================================================================================
⚠️  TEST MODE ENABLED ⚠️
📊 Database: postgresql+psycopg2://...ai_order_food_test
⚠️  Application is connected to TEST database
================================================================================
```

如果**沒有**看到這個警告,代表應用程式正在使用開發資料庫!

---

### 問題 1: Playwright 瀏覽器未安裝

**錯誤訊息**:
```
playwright._impl._api_types.Error: Executable doesn't exist at ...
```

**解決方法**:
```bash
playwright install
```

### 問題 2: 測試超時

**錯誤訊息**:
```
TimeoutError: Timeout 30000ms exceeded
```

**可能原因**:

1. 應用程式未運行
2. 網路問題
3. 元素選擇器錯誤
4. SSE 連線問題

**解決方法**:

```bash
# 增加超時時間
pytest test/e2e/ --timeout=60

# 或在 conftest.py 中設定
page.set_default_timeout(60000)  # 60 秒
```

### 問題 3: 資料庫連線失敗

**錯誤訊息**:
```
psycopg2.OperationalError: could not connect to server
```

**解決方法**:

```bash
# 檢查 TEST_DATABASE_URL 是否設定
echo $env:TEST_DATABASE_URL

# 確保測試資料庫存在
psql -U postgres -c "CREATE DATABASE ai_order_food_test;"

# 執行 migration
$env:DATABASE_URL=$env:TEST_DATABASE_URL
alembic upgrade head
```

### 問題 4: 測試不穩定 (Flaky Tests)

**可能原因**:

1. 過度使用 `wait_for_timeout()` 而非條件等待
2. 競態條件 (Race Conditions)
3. 測試之間有依賴

**解決方法**:

```python
# 使用條件等待替代固定延遲
page.wait_for_function("() => window.dataLoaded === true")

# 等待 API 請求完成
page.wait_for_response("**/api/cart")

# 等待元素狀態
element.wait_for(state="visible")
```

### 問題 5: SSE 測試失敗

**可能原因**:

1. SSE 連線未建立
2. 廣播延遲
3. 事件監聽器未正確注入

**解決方法**:

```python
# 驗證 SSE 連線狀態
sse_status = page.evaluate("() => window.eventSource?.readyState")
assert sse_status == 1, "SSE 應該已連線"

# 增加同步等待時間
page.wait_for_timeout(2000)  # 給 SSE 廣播足夠時間

# 使用 wait_for_sse_message fixture
wait_for_sse_message("cart_updated", timeout=5000)
```

### 問題 6: 截圖和影片未生成

**解決方法**:

```bash
# 確保輸出目錄存在
mkdir -p test_results/screenshots
mkdir -p test_results/videos

# 明確指定輸出選項
pytest test/e2e/ --screenshot on --video on --output test_results/
```

---

## 📊 測試標記 (Markers)

使用 pytest 標記來分類和過濾測試:

```python
@pytest.mark.e2e           # 標記為 E2E 測試
@pytest.mark.slow          # 標記為慢速測試
@pytest.mark.skip          # 跳過測試
@pytest.mark.skipif(condition, reason="...")  # 條件跳過
```

**執行特定標記的測試**:

```bash
# 只執行 E2E 測試
pytest -m e2e

# 排除慢速測試
pytest -m "not slow"

# 執行 E2E 且非慢速的測試
pytest -m "e2e and not slow"
```

---

## 🎯 持續整合 (CI/CD)

### GitHub Actions 範例

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r test/e2e/requirements.txt
          playwright install --with-deps

      - name: Run migrations
        env:
          TEST_DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost/test_db
        run: |
          alembic upgrade head

      - name: Run E2E tests
        env:
          E2E_BASE_URL: http://localhost:8000
          TEST_DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost/test_db
        run: |
          pytest test/e2e/ -v --html=report.html --self-contained-html

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-results
          path: |
            report.html
            test_results/
```

---

## 📚 參考資源

- [Playwright 官方文件](https://playwright.dev/python/)
- [Playwright Python API](https://playwright.dev/python/docs/api/class-playwright)
- [pytest-playwright](https://github.com/microsoft/playwright-pytest)
- [Page Object Model 模式](https://playwright.dev/python/docs/pom)

---

## ✅ 檢查清單

建立新的 E2E 測試時,確保:

- [ ] 測試案例有清晰的名稱和文件字串
- [ ] 使用 Page Object Model 封裝 UI 操作
- [ ] 使用 `data-testid` 選擇器
- [ ] 使用條件等待而非固定延遲
- [ ] 測試是獨立的,不依賴其他測試
- [ ] 有清晰的斷言訊息
- [ ] 添加適當的測試標記 (`@pytest.mark.e2e`, `@pytest.mark.slow`)
- [ ] 測試後清理資源 (關閉頁面、清理資料庫)
- [ ] 在本地和 CI 環境都能通過

---

</details>

## 🎉 總結

這份指南提供了完整的 Playwright E2E 測試結構,包括:

- ✅ **✨ 全自動化執行** - 一行命令搞定所有流程
- ✅ **自動前端構建** - 無需手動 `npm run build`
- ✅ **自動伺服器管理** - 無需手動啟動/關閉伺服器
- ✅ **智能健康檢查** - 確保伺服器完全就緒
- ✅ **Page Object Model 設計** - 可維護的測試架構
- ✅ **完整的測試案例範例** - 菜單、購物車、共享 Session
- ✅ **SSE 即時同步測試** - 多用戶場景覆蓋
- ✅ **詳細故障排除指南** - 涵蓋所有常見問題
- ✅ **靈活配置選項** - 可自定義 port、超時、構建選項

### 🚀 從手動到自動化的演進

**以前（手動模式）**:
1. 手動設定 `TEST_MODE=1`
2. 手動啟動伺服器
3. 手動構建前端（如需要）
4. 另開終端執行測試
5. 測試完成後手動關閉伺服器

**現在（自動化模式）**:
```bash
pytest test/e2e/ --headed  # 一行命令，完成所有步驟！
```

遵循這些指南,您可以編寫穩定、可維護的 E2E 測試,確保 AIOrderFood 專案的品質！

---

## 📚 相關文檔

- **快速開始**: [RUNNING_TESTS.md](./RUNNING_TESTS.md) - 簡化的執行指南
- **專案文檔**: [../../README.md](../../README.md) - 專案總覽
- **開發指南**: [../../CLAUDE.md](../../CLAUDE.md) - AI 開發指南

**需要幫助？** 查看本文檔的「故障排除」章節，涵蓋所有常見問題！
