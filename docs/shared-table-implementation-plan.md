# 多人共享桌號點餐系統實作計劃

## 📋 需求摘要
- **sessionid** 作為桌號 GUID，**tableid** 為顯示標籤（如 A1、B2）
- 送出訂單後阻止空購物車再次送出
- **Server-Sent Events (SSE)** 即時同步購物車、訂單狀態、版本衝突
- 後台動態生成 QR Code（不儲存資料庫）

---

## 🗃️ 第一階段：資料庫結構調整

### 1.1 新增 UserSession.table_id 欄位
- ✅ 修改 `app/models.py` - UserSession 模型新增 `table_id: Mapped[Optional[str]]` 欄位
- ⏳ 建立 Alembic 遷移檔案

### 1.2 Order 模型調整
- ✅ 新增 `table_id` 欄位以記錄訂單所屬桌號（從 session 複製）

---

## 🔧 第二階段：後端核心功能

### 2.1 Session 管理升級 (`app/session.py`)
- 修改 `ensure_session()` 函數：
  - 支援從 query parameter 讀取 `sessionid`（若存在則使用，不存在則創建）
  - 支援從 query parameter 讀取 `tableid` 並寫入 `session.table_id`
  - 保持向後兼容（無參數時維持原行為）
  - 設定 cookie 時使用提供的或新生成的 sessionid

### 2.2 空購物車限制 (`app/modules/order/service.py`)
- 在 `create_order()` 函數新增檢查：
  - 查詢該 session 是否已有任何訂單（不論狀態）
  - 若有訂單且當前購物車為空，拋出 `ValueError("cannot_submit_empty_cart_after_order")`
  - 複製 `session.table_id` 到新訂單的 `table_id` 欄位

### 2.3 訂單 API 錯誤處理 (`app/modules/order/router.py`)
- 在 `place_order_endpoint()` 捕捉新錯誤碼，回傳 HTTP 422 和友善訊息

---

## 📡 第三階段：Server-Sent Events 實作

### 3.1 新增 SSE 模組 (`app/modules/sse/`)
- `service.py`：
  - `SSEConnectionManager` 類別管理連線（以 session_id 為 key）
  - `broadcast_to_session(session_id, event_type, data)` 廣播訊息
  - 支援事件類型：`cart_updated`、`order_status_updated`、`version_conflict`

- `router.py`：
  - `GET /api/sse/cart/{session_id}` 端點
  - 使用 `StreamingResponse` + `text/event-stream`
  - 實作心跳機制（每 30 秒發送 `:keepalive`）
  - 斷線時自動清理連線

### 3.2 整合 SSE 到現有 API
- 修改 `app/modules/order/router.py`：
  - `replace_cart_endpoint()` 成功後廣播 `cart_updated`
  - `place_order_endpoint()` 成功後廣播 `order_status_updated`

- 修改後台訂單管理（admin 相關路由）：
  - 更新訂單狀態時廣播 `order_status_updated`

---

## 📷 第四階段：QR Code 生成功能

### 4.1 新增依賴套件
- `requirements.txt` 新增：
  - `qrcode[pil]>=7.4.2`
  - `Pillow>=10.0.0`

### 4.2 QR Code API (`app/modules/admin/` 或獨立模組)
- `GET /api/admin/qrcode/generate`:
  - Query parameter: `tableid` (必填)
  - 生成新的 session UUID
  - 組合完整 URL：`{base_url}?sessionid={uuid}&tableid={tableid}`
  - 回傳 JSON：`{ "qrcode_base64": "...", "url": "...", "session_id": "..." }`

- `GET /api/admin/qrcode/image`:
  - Query parameter: `tableid` (必填)
  - 直接回傳 PNG 圖片（`Content-Type: image/png`）
  - 設定 `Content-Disposition: inline; filename="table_{tableid}.png"`

### 4.3 QR Code 後台頁面 (`static/admin/qrcode.html`)
- 輸入框：桌號（如 "A1"）
- 按鈕：「生成 QR Code」
- 顯示區：顯示 QR Code 圖片 + URL + Session ID
- 下載按鈕：觸發瀏覽器下載 PNG
- 列印按鈕：使用 `window.print()` 列印（包含桌號標籤）
- 批量生成：輸入範圍（如 "A1-A10"）批量生成

---

## 🎨 第五階段：前端整合

### 5.1 URL 參數處理 (`static/src/App.vue` 或 `main.js`)
- 應用啟動時讀取 `URLSearchParams`
- 若存在 `sessionid` 和 `tableid`：
  - 發送到後端（可透過特殊 API 或在下次請求時帶入）
  - 儲存到 Pinia store (`useSessionStore`) 和 `localStorage`
- 設定 Axios interceptor，所有請求帶上 `sessionid` query parameter

### 5.2 購物車 Store SSE 整合 (`static/src/stores/cart.js`)
- 新增狀態：
  - `sseConnection: EventSource | null`
  - `tableId: string`

- 新增方法：
  - `connectSSE(sessionId)`: 建立 SSE 連線
  - `disconnectSSE()`: 關閉連線
  - 監聽事件：
    - `cart_updated`: 調用 `fetchCartFromServer()`，顯示通知
    - `order_status_updated`: 刷新訂單列表，顯示通知
    - `version_conflict`: 觸發現有的衝突處理邏輯
  - 實作自動重連（斷線後 3 秒重試）

### 5.3 衝突通知 UI 強化 (`static/src/views/CartView.vue`)
- 更新通知樣式：
  - 版本衝突：紅色邊框 + 警告圖示
  - 其他使用者更新：藍色邊框 + 資訊圖示
  - 訂單狀態更新：綠色邊框 + 成功圖示
- 新增「查看詳情」按鈕（展開顯示變更內容）
- 可選：使用 `Audio` API 播放提示音

### 5.4 空購物車錯誤處理
- 在 `placeOrder()` 函數：
  - 本地檢查：若 `cart.length === 0` 提示「購物車是空的」
  - 捕捉 HTTP 422 錯誤碼 `cannot_submit_empty_cart_after_order`
  - 顯示友善訊息：「此桌已送出訂單，無法送出空白訂單。請先新增商品。」

### 5.5 桌號顯示
- 在導航欄或頁首顯示：「🍽️ A1 桌」
- 購物車頁面顯示：「您正在為 A1 桌點餐」

---

## 🧪 第六階段：測試案例

### 6.1 後端測試 (`test/test_shared_session.py` - 新檔案)

**測試場景：**

1. **Session 參數處理**
   - `test_create_session_with_parameters` - 提供 sessionid 和 tableid 創建 session
   - `test_reuse_existing_session` - 多個使用者使用相同 sessionid
   - `test_tableid_persistence` - table_id 正確寫入資料庫

2. **購物車共享**
   - `test_cart_shared_across_users` - 使用者 A 新增商品，使用者 B 可見
   - `test_cart_version_conflict` - 兩使用者同時修改觸發版本衝突

3. **空購物車限制**
   - `test_prevent_empty_cart_after_order` - 送出訂單後無法送出空購物車
   - `test_allow_non_empty_cart_after_order` - 送出訂單後仍可送出有商品的購物車
   - `test_first_order_allows_empty` - 首次送出可為空（若業務邏輯允許）

4. **SSE 功能**
   - `test_sse_connection_established` - 成功建立 SSE 連線
   - `test_sse_cart_updated_broadcast` - 購物車更新時廣播事件
   - `test_sse_order_status_broadcast` - 訂單狀態更新時廣播事件
   - `test_sse_multiple_clients` - 多個客戶端同時連線
   - `test_sse_reconnect_after_disconnect` - 斷線重連機制

5. **QR Code 生成**
   - `test_qrcode_generate_json` - 生成 QR Code JSON 回應
   - `test_qrcode_generate_image` - 生成 PNG 圖片
   - `test_qrcode_url_format` - URL 格式正確包含 sessionid 和 tableid

### 6.2 整合測試 (`test/test_integration_shared_table.py`)
- `test_full_workflow_multiple_users` - 完整流程：掃描 QR Code → 多人加入 → 共同點餐 → 送出訂單

---

## 📝 第七階段：文件更新

### 7.1 更新 `CLAUDE.md`
- 新增「共享桌號點餐」章節
- SSE API 使用說明
- QR Code 生成 API 文件
- URL 參數說明

### 7.2 更新 API 文件（若有 OpenAPI/Swagger）
- 標記新增的端點
- 更新 schema 定義

---

## 🚀 實作順序建議

1. ✅ **資料庫模型更新**（已完成）
2. ⏳ **資料庫遷移**（進行中）
3. **Session 參數處理**
4. **空購物車限制**
5. **SSE 模組基礎**
6. **SSE 整合到現有 API**
7. **QR Code API**
8. **QR Code 後台頁面**
9. **前端 URL 參數處理**
10. **前端 SSE 整合**
11. **UI 優化**
12. **測試撰寫**
13. **文件更新**

**預估總時長：約 8 小時**

---

## ⚠️ 技術注意事項

1. **SSE 連線管理**：使用 in-memory dict 儲存連線，重啟服務會斷線（生產環境可考慮 Redis Pub/Sub）
2. **Session ID 安全性**：UUID v4 已足夠隨機，但 URL 中的 sessionid 可被他人使用（若需更高安全性可加入驗證機制）
3. **並發控制**：現有樂觀鎖機制已足夠，SSE 只負責通知不處理衝突
4. **QR Code 尺寸**：建議使用 `box_size=10`, `border=4` 確保可掃描性
5. **Base URL 設定**：QR Code URL 需要正確的 base URL（從環境變數或 request 取得）

---

## 📊 進度追蹤

- ✅ 已完成
- ⏳ 進行中
- ⏸️ 待處理

### 資料庫層
- ✅ UserSession.table_id 欄位
- ✅ Order.table_id 欄位
- ⏳ Alembic 遷移

### 後端 API
- ⏸️ Session 管理升級
- ⏸️ 空購物車限制
- ⏸️ SSE 模組
- ⏸️ QR Code API

### 前端
- ⏸️ URL 參數處理
- ⏸️ SSE 整合
- ⏸️ UI 優化

### 測試
- ⏸️ 單元測試
- ⏸️ 整合測試

### 文件
- ✅ 實作計劃文件
- ⏸️ CLAUDE.md 更新

---

**最後更新：** 2025-11-11
**版本：** 1.0
