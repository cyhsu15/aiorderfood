"""
測試 SSE 即時同步功能

此腳本模擬兩個使用者同時操作購物車的情境：
1. 使用者 A 和使用者 B 使用相同的 sessionid 和 tableid
2. 使用者 A 加入商品到購物車
3. 檢查使用者 B 是否透過 SSE 收到更新通知
"""

import httpx
import json
import time
import asyncio
import uuid
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:8000"

def test_sse_cart_sync():
    """測試購物車 SSE 即時同步"""

    print("=" * 80)
    print("測試 SSE 購物車即時同步功能")
    print("=" * 80)

    # 1. 建立共享 session（模擬掃描 QR Code）
    print("\n[步驟 1] 建立共享 session...")
    session_id = str(uuid.uuid4())  # 使用有效的 UUID 格式
    table_id = "A1"
    print(f"  Session ID: {session_id}")
    print(f"  桌號: {table_id}")

    # 建立兩個 HTTP 客戶端（模擬兩個使用者）
    cookies_a = {"cart_session_id": session_id}
    cookies_b = {"cart_session_id": session_id}

    with httpx.Client(base_url=BASE_URL, cookies=cookies_a) as client_a:
        # 2. 使用者 A 取得購物車
        print(f"\n[步驟 2] 使用者 A 取得購物車...")
        response = client_a.get("/api/cart")
        print(f"  狀態碼: {response.status_code}")
        cart_data = response.json()
        print(f"  購物車內容: {json.dumps(cart_data, ensure_ascii=False, indent=2)}")

        # 3. 使用者 A 加入商品到購物車
        print(f"\n[步驟 3] 使用者 A 加入商品到購物車...")
        cart_payload = {
            "items": [
                {
                    "id": 1,
                    "name": "測試菜品",
                    "price": 100.0,
                    "qty": 2,
                    "size": "中",
                    "note": "",
                    "image_url": "/images/default.png",
                    "uuid": "test-uuid-001"
                }
            ],
            "note": "測試訂單",
            "version": cart_data.get("version")
        }

        response = client_a.put("/api/cart", json=cart_payload)
        print(f"  狀態碼: {response.status_code}")
        updated_cart = response.json()
        print(f"  更新後購物車: {json.dumps(updated_cart, ensure_ascii=False, indent=2)}")

    # 4. 使用者 B 取得購物車（檢查是否已同步）
    print(f"\n[步驟 4] 使用者 B 取得購物車（檢查同步結果）...")
    with httpx.Client(base_url=BASE_URL, cookies=cookies_b) as client_b:
        response = client_b.get("/api/cart")
        print(f"  狀態碼: {response.status_code}")
        cart_b = response.json()
        print(f"  購物車內容: {json.dumps(cart_b, ensure_ascii=False, indent=2)}")

        # 驗證同步
        if len(cart_b.get("items", [])) > 0:
            print("\n✅ 購物車資料已同步到資料庫！")
        else:
            print("\n❌ 購物車資料未同步")

    print("\n" + "=" * 80)
    print("注意：此測試僅驗證資料庫同步，不包含 SSE 即時推送")
    print("要測試 SSE 即時推送，需要：")
    print("1. 使用瀏覽器開啟兩個分頁")
    print("2. 在網址列輸入: http://127.0.0.1:8000?sessionid=test-session&tableid=A1")
    print("3. 觀察頂部是否顯示紫色 Banner 和「同步中」綠色指示器")
    print("4. 在分頁 A 加入商品，檢查分頁 B 是否收到通知")
    print("5. 開啟瀏覽器開發者工具 (F12) 查看 Console 日誌")
    print("=" * 80)

    return session_id  # 返回 session_id 供後續測試使用


async def test_sse_connection(session_id=None):
    """測試 SSE 連線是否正常建立"""

    print("\n" + "=" * 80)
    print("測試 SSE 連線")
    print("=" * 80)

    if session_id is None:
        session_id = str(uuid.uuid4())

    print(f"\n使用 Session ID: {session_id}")
    sse_url = f"{BASE_URL}/api/sse/cart/{session_id}"

    print(f"\n[測試] 連線到 SSE 端點: {sse_url}")
    print("（此測試會持續 5 秒接收事件）")

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", sse_url) as response:
                print(f"  狀態碼: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type')}")

                if response.status_code == 200:
                    print("\n✅ SSE 連線建立成功！正在監聽事件...")

                    start_time = time.time()
                    async for line in response.aiter_lines():
                        if time.time() - start_time > 5:
                            print("\n⏱️  測試時間結束 (5秒)")
                            break

                        if line:
                            print(f"  收到: {line}")
                else:
                    print(f"\n❌ SSE 連線失敗: {response.status_code}")

    except Exception as e:
        print(f"\n❌ 連線錯誤: {e}")

    print("=" * 80)


if __name__ == "__main__":
    # 執行同步測試
    session_id = test_sse_cart_sync()

    # 執行 SSE 連線測試（使用相同的 session_id）
    print("\n")
    asyncio.run(test_sse_connection(session_id))
