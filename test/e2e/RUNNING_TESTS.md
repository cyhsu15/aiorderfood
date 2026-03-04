# 🎭 E2E 測試執行指南

## ✨ 全自動化測試 - 一鍵啟動！

E2E 測試現在**完全自動化**！無需手動啟動伺服器或構建前端，只需執行一條命令。

## 🚀 快速開始

### 一行命令執行所有測試

```bash
# 運行所有 E2E 測試 (headless 模式)
pytest test/e2e/ -v

# 顯示瀏覽器運行測試 (推薦，可以看到測試過程)
pytest test/e2e/ --headed

# 慢動作觀察測試過程
pytest test/e2e/ --headed --slowmo 800
```

**就這麼簡單！** 🎉

測試框架會自動：
- ✅ 構建前端 (npm run build)
- ✅ 啟動測試伺服器 (連接測試資料庫)
- ✅ 執行所有 E2E 測試
- ✅ 測試完成後關閉伺服器

### 必要條件

在運行測試前，請確保：

1. **已安裝 Python 依賴**
   ```bash
   pip install -r requirements.txt
   pip install -r test/e2e/requirements.txt
   ```

2. **已安裝 Playwright 瀏覽器** (首次運行)
   ```bash
   playwright install chromium
   ```

3. **已設定測試資料庫** (在 `.env` 檔案中)
   ```env
   TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ai_order_food_test
   ```

4. **前端依賴已安裝** (只需執行一次)
   ```bash
   cd static && npm ci && cd ..
   ```

### 執行流程說明

當您執行 `pytest test/e2e/` 時，會發生以下流程：

```
┌─────────────────────────────────────────┐
│ 1. 構建前端                              │
│    • 執行 npm run build                  │
│    • 生成 static/dist/                   │
│    • 約需 10-30 秒                       │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│ 2. 啟動測試伺服器                        │
│    • 在後台啟動 uvicorn                  │
│    • 自動連接測試資料庫                  │
│    • Health check 確保伺服器就緒         │
│    • 約需 2-5 秒                         │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│ 3. 執行 E2E 測試                         │
│    • 啟動瀏覽器 (Chromium)               │
│    • 執行所有測試案例                    │
│    • 自動截圖/錄影 (失敗時)              │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│ 4. 清理資源                              │
│    • 關閉測試伺服器                      │
│    • 清理臨時檔案                        │
└─────────────────────────────────────────┘
```

---

## 🖥️ 顯示瀏覽器的方法

### 方法 1: 使用 `--headed` 參數 (推薦)

```bash
# 顯示瀏覽器執行所有測試
pytest test/e2e/ --headed

# 只執行一個測試並顯示瀏覽器
pytest test/e2e/tests/test_menu_browsing.py::test_menu_page_loads_successfully --headed

# 顯示瀏覽器 + 慢動作 (每個操作延遲 1 秒)
pytest test/e2e/ --headed --slowmo 1000

# 顯示瀏覽器 + 慢動作 (500ms)
pytest test/e2e/ --headed --slowmo 500
```

### 方法 2: 使用 `page.pause()` 互動式除錯

在測試中添加 `page.pause()`:

```python
def test_my_feature(page: Page, base_url: str):
    page.goto(base_url)
    
    # 進入互動式除錯模式
    page.pause()  # ← 這裡會暫停並開啟 Playwright Inspector
    
    # 後續操作...
```

運行:
```bash
pytest test/e2e/tests/test_example_debug.py::test_debug_menu_interaction --headed
```

### 方法 3: 修改配置預設顯示瀏覽器

**選項 A: 修改 `pytest.ini`**

編輯 `pytest.ini`,取消註解:
```ini
addopts =
    --headed              # 預設顯示瀏覽器
    --slowmo 500          # 預設慢動作
```

**選項 B: 修改 `test/e2e/conftest.py`**

編輯 `conftest.py` 中的 `browser_type_launch_args` fixture:
```python
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "headless": False,  # 預設顯示瀏覽器
        "slow_mo": 500,     # 預設慢動作 (500ms)
    }
```

---

## 📝 常用命令

### 運行特定測試

```bash
# 運行單個測試文件
pytest test/e2e/tests/test_menu_browsing.py --headed

# 運行單個測試
pytest test/e2e/tests/test_cart_operations.py::test_add_dish_to_cart --headed

# 運行包含關鍵字的測試
pytest test/e2e/ -k "cart" --headed

# 排除慢速測試
pytest test/e2e/ -m "not slow" --headed
```

### 瀏覽器選擇

```bash
# 使用 Chromium (預設)
pytest test/e2e/ --headed --browser chromium

# 使用 Firefox
pytest test/e2e/ --headed --browser firefox

# 使用 Webkit (Safari)
pytest test/e2e/ --headed --browser webkit
```

### 除錯選項

```bash
# 啟用詳細輸出
pytest test/e2e/ --headed -vv

# 顯示 print 輸出
pytest test/e2e/ --headed -s

# 失敗時進入 pdb
pytest test/e2e/ --headed --pdb

# 顯示瀏覽器 console 訊息 (已在 conftest 中配置)
pytest test/e2e/ --headed -s
```

### 截圖與影片

```bash
# 總是截圖
pytest test/e2e/ --screenshot on

# 僅失敗時截圖 (預設)
pytest test/e2e/ --screenshot only-on-failure

# 錄製影片 (保留失敗的)
pytest test/e2e/ --video retain-on-failure

# 總是錄製影片
pytest test/e2e/ --video on

# 啟用追蹤 (可用 Playwright Trace Viewer 查看)
pytest test/e2e/ --tracing on
```

---

## 🎯 測試分類

### 菜單瀏覽測試

```bash
pytest test/e2e/tests/test_menu_browsing.py --headed
```

測試項目:
- ✅ 菜單頁面載入
- ✅ 瀏覽分類中的菜品
- ✅ 搜尋菜品
- ✅ 查看菜品詳情
- ✅ 切換分類
- ✅ 響應式設計 (手機版)

### 購物車操作測試

```bash
pytest test/e2e/tests/test_cart_operations.py --headed --slowmo 500
```

測試項目:
- ✅ 加入菜品到購物車
- ✅ 加入多個菜品
- ✅ 增加/減少數量
- ✅ 移除商品
- ✅ 清空購物車
- ✅ 總金額計算
- ✅ 購物車持久化
- ✅ 結帳按鈕狀態

### 共享 Session 測試 (多用戶同步)

```bash
pytest test/e2e/tests/test_shared_session.py --headed --slowmo 800
```

測試項目:
- ✅ 共享 Session 初始化
- ✅ URL 參數清理
- ✅ 兩個用戶之間的購物車同步
- ✅ 購物車更新廣播到所有用戶
- ✅ 樂觀鎖防止版本衝突
- ✅ 不同桌號有獨立購物車
- ✅ SSE 連線重連

---

## 🐛 互動式除錯範例

```bash
# 執行除錯範例測試
pytest test/e2e/tests/test_example_debug.py --headed
```

這個測試會:
1. 開啟瀏覽器
2. 載入菜單頁面
3. 暫停並開啟 **Playwright Inspector**
4. 讓您可以手動操作瀏覽器並觀察狀態

在 Inspector 中您可以:
- 🎮 手動操作瀏覽器
- ▶️ 單步執行測試
- 🔍 查看和測試選擇器
- 📋 查看控制台輸出
- 📸 截圖

---

## 📊 測試報告

```bash
# 生成 HTML 報告
pytest test/e2e/ --headed --html=test-report.html --self-contained-html

# 查看覆蓋率
pytest test/e2e/ --cov=app --cov-report=html
```

---

## ⚠️ 注意事項與故障排除

### 必要條件檢查清單

執行測試前請確認：

✅ **Python 依賴已安裝**
```bash
pip install -r requirements.txt
pip install -r test/e2e/requirements.txt
```

✅ **Playwright 瀏覽器已安裝**
```bash
playwright install chromium
```

✅ **測試資料庫已設定** (`.env` 檔案)
```env
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ai_order_food_test
```

✅ **前端依賴已安裝**
```bash
cd static && npm ci
```

✅ **Port 8000 可用** (沒有其他服務佔用)

---

### 常見問題

#### Q1: Port 8000 已被佔用

**錯誤訊息:**
```
ServerStartupError: Port 8000 已被佔用
```

**解決方法:**
```bash
# Windows: 查看佔用 port 的進程
netstat -ano | findstr :8000

# 終止進程 (PID 從上面獲取)
taskkill /PID <PID> /F

# 或者修改測試配置使用其他 port
# 編輯 test/e2e/config.py:
# SERVER_PORT = 8001
```

---

#### Q2: 前端構建失敗

**錯誤訊息:**
```
FrontendBuildError: npm run build 執行失敗
```

**解決方法:**
```bash
# 手動測試前端構建
cd static
npm ci
npm run build

# 如果失敗，檢查 Node.js 版本
node --version  # 建議 v16+

# 清理並重新安裝
rm -rf node_modules package-lock.json
npm install
```

---

#### Q3: 測試伺服器啟動超時

**錯誤訊息:**
```
ServerStartupError: 伺服器未在 30 秒內就緒
```

**可能原因與解決:**

1. **資料庫連線問題**
   ```bash
   # 測試資料庫連線
   psql $TEST_DATABASE_URL
   ```

2. **Python 依賴缺失**
   ```bash
   pip install -r requirements.txt
   ```

3. **查看伺服器日誌**
   - 錯誤訊息會顯示日誌檔案路徑
   - 檢查日誌內容找出啟動失敗原因

---

#### Q4: 測試資料庫未設定

**錯誤訊息:**
```
pytest.skip: TEST_DATABASE_URL not set
```

**解決方法:**
```bash
# 在 .env 檔案中添加
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ai_order_food_test

# 確認資料庫存在
psql -U user -h localhost -p 5432 -l | grep ai_order_food_test
```

---

#### Q5: 測試失敗 "Locator expected to be visible"

**可能原因:**
- 前端資源未正確構建
- 伺服器返回 404
- 測試資料未正確建立

**偵錯方法:**
```bash
# 使用慢動作和顯示瀏覽器觀察
pytest test/e2e/ --headed --slowmo 1000 -s

# 或在測試中添加 page.pause() 進入互動式偵錯
```

---

#### Q6: 想跳過前端構建加速測試

如果您剛構建過前端，想跳過構建步驟：

**編輯 `test/e2e/config.py`:**
```python
SKIP_FRONTEND_BUILD = True  # 改為 True
```

**注意:** 跳過構建後，請確保 `static/dist/` 目錄存在且為最新版本。

---

#### Q7: 想看伺服器詳細日誌

**方法 1: 查看伺服器日誌檔案**
```bash
# 執行測試
pytest test/e2e/ -v

# 測試完成後，日誌檔案路徑會顯示在輸出中
# 類似: /tmp/e2e_server_xxxxx.log
```

**方法 2: 啟用 DEBUG 日誌級別**

編輯 `test/e2e/config.py`:
```python
LOG_LEVEL = "DEBUG"  # 改為 DEBUG
```

---

#### Q8: 測試一直超時

```bash
# 增加 pytest 超時時間
pytest test/e2e/ --headed --timeout=120

# 增加伺服器啟動超時時間
# 編輯 test/e2e/config.py:
# SERVER_STARTUP_TIMEOUT = 60  # 改為 60 秒
```

---

#### Q9: 想看瀏覽器 console 訊息

```bash
# 使用 -s 參數顯示所有輸出
pytest test/e2e/ --headed -s
```

conftest.py 已配置自動輸出瀏覽器 console 訊息。

---

## 🎬 影片與追蹤查看

失敗的測試會自動保存影片和追蹤:

```bash
# 查看影片
test-results/test_name/video.webm

# 查看追蹤 (使用 Playwright Trace Viewer)
playwright show-trace test-results/test_name/trace.zip
```

---

## 📚 更多資源

- [Playwright Python 文件](https://playwright.dev/python/docs/intro)
- [pytest-playwright 文件](https://github.com/microsoft/playwright-pytest)
- [Playwright Inspector](https://playwright.dev/python/docs/debug)
