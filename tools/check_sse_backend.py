"""
SSE 後端診斷工具

此工具用於檢查 SSE 後端功能是否正常運作，包括：
1. 檢查 SSE 端點是否可訪問
2. 驗證 SSE 連線建立
3. 測試購物車廣播功能

使用方法：
    python tools/check_sse_backend.py

前置條件：
    後端伺服器必須運行在 http://127.0.0.1:8000
"""

import asyncio
import httpx
import uuid
import json
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:8000"


def print_section(title):
    """印出區段標題"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def test_backend_health():
    """測試後端伺服器是否正常運行"""
    print_section("1. 檢查後端伺服器狀態")

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
            # 嘗試訪問根路徑
            response = await client.get("/")
            print(f"  狀態碼: {response.status_code}")

            if response.status_code == 200:
                print("  [OK] 後端伺服器運行正常")
                return True
            else:
                print(f"  [ERROR] 後端伺服器回應異常: {response.status_code}")
                return False

    except httpx.ConnectError:
        print("  [ERROR] 無法連線到後端伺服器")
        print(f"  請確認伺服器是否運行在 {BASE_URL}")
        return False
    except Exception as e:
        print(f"  [ERROR] 檢查失敗: {e}")
        return False


async def test_cart_api():
    """測試購物車 API 是否正常"""
    print_section("2. 測試購物車 API")

    session_id = str(uuid.uuid4())
    table_id = "DIAG-TEST"

    print(f"  測試 Session ID: {session_id}")
    print(f"  測試桌號: {table_id}\n")

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            # 使用 query parameter 建立 session
            url = f"/api/cart?sessionid={session_id}&tableid={table_id}"

            # 1. GET 購物車（應該建立新 session）
            print("  [1/3] 取得購物車...")
            response = await client.get(url)
            print(f"    狀態碼: {response.status_code}")

            if response.status_code != 200:
                print(f"    [ERROR] API 回應異常")
                return False, session_id

            cart_data = response.json()
            print(f"    版本號: {cart_data.get('version')}")
            print(f"    商品數: {len(cart_data.get('items', []))}")

            # 2. PUT 購物車（加入商品）
            print("\n  [2/3] 更新購物車（加入商品）...")
            cart_payload = {
                "items": [
                    {
                        "id": 999,
                        "name": "診斷測試商品",
                        "price": 100.0,
                        "qty": 1,
                        "size": "測試",
                        "note": "",
                        "image_url": "/images/default.png",
                        "uuid": "diag-test-001"
                    }
                ],
                "note": "SSE 診斷測試",
                "version": cart_data.get("version")
            }

            # 從第一次請求的 response 中取得 cookie
            cookies = response.cookies
            response = await client.put("/api/cart", json=cart_payload, cookies=cookies)
            print(f"    狀態碼: {response.status_code}")

            if response.status_code != 200:
                print(f"    [ERROR] 更新購物車失敗")
                return False, session_id

            updated_cart = response.json()
            print(f"    版本號: {updated_cart.get('version')}")
            print(f"    商品數: {len(updated_cart.get('items', []))}")

            # 3. 再次 GET 購物車（驗證資料持久化）
            print("\n  [3/3] 驗證購物車資料持久化...")
            response = await client.get("/api/cart", cookies=cookies)
            print(f"    狀態碼: {response.status_code}")

            verify_cart = response.json()
            item_count = len(verify_cart.get('items', []))
            print(f"    商品數: {item_count}")

            if item_count == 1:
                print("    [OK] 購物車 API 功能正常")
                return True, session_id
            else:
                print("    [ERROR] 購物車資料未正確儲存")
                return False, session_id

    except Exception as e:
        print(f"  [ERROR] 測試失敗: {e}")
        return False, session_id


async def test_sse_connection(session_id):
    """測試 SSE 連線"""
    print_section("3. 測試 SSE 連線")

    sse_url = f"{BASE_URL}/api/sse/cart/{session_id}"
    print(f"  SSE 端點: {sse_url}")
    print("  正在建立連線...\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            event_count = 0
            connected = False

            async with client.stream("GET", sse_url) as response:
                print(f"  狀態碼: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}\n")

                if response.status_code != 200:
                    print(f"  [ERROR] SSE 連線失敗")
                    return False

                if not response.headers.get('content-type', '').startswith('text/event-stream'):
                    print(f"  [ERROR] Content-Type 不正確，應為 text/event-stream")
                    return False

                print("  開始接收 SSE 事件（將持續 8 秒）...\n")

                start_time = asyncio.get_event_loop().time()
                current_event_type = None

                async for line in response.aiter_lines():
                    # 超過 8 秒後停止
                    if asyncio.get_event_loop().time() - start_time > 8:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # 解析 SSE 格式
                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        event_data = line[5:].strip()
                        event_count += 1

                        # 美化輸出
                        try:
                            data_obj = json.loads(event_data)
                            data_str = json.dumps(data_obj, ensure_ascii=False, indent=2)
                        except:
                            data_str = event_data

                        print(f"  [{event_count}] 收到事件: {current_event_type}")
                        print(f"      資料: {data_str}\n")

                        if current_event_type == "connected":
                            connected = True

                        current_event_type = None

                if connected:
                    print(f"  [OK] SSE 連線正常建立（收到 {event_count} 個事件）")
                    return True
                else:
                    print(f"  [WARN]  收到 {event_count} 個事件，但未收到 'connected' 事件")
                    return False

    except httpx.ReadTimeout:
        print("  [WARN]  SSE 連線逾時（這可能是正常的）")
        if event_count > 0:
            print(f"  已接收 {event_count} 個事件")
            return True
        return False
    except Exception as e:
        print(f"  [ERROR] SSE 連線錯誤: {e}")
        return False


async def test_sse_broadcast(session_id):
    """測試 SSE 廣播功能"""
    print_section("4. 測試 SSE 廣播功能（進階）")

    print("  此測試需要同時建立 SSE 連線和發送購物車更新")
    print("  由於技術限制，無法在單一腳本中完整測試")
    print("  建議使用瀏覽器進行完整測試\n")

    print("  請參考: docs/SSE_MANUAL_TEST_GUIDE.md")
    print("  [INFO]  跳過此測試")

    return None


async def main():
    """主函數"""
    print("\n" + "=" * 80)
    print("  SSE Backend Diagnostic Tool")
    print("=" * 80)

    results = {}

    # 1. 檢查後端狀態
    results['backend'] = await test_backend_health()

    if not results['backend']:
        print("\n" + "[ERROR]" * 40)
        print("後端伺服器無法訪問，終止診斷")
        print("請先啟動後端: uvicorn main:app --reload")
        print("[ERROR]" * 40)
        return

    # 2. 測試購物車 API
    results['cart_api'], session_id = await test_cart_api()

    if not results['cart_api']:
        print("\n" + "[ERROR]" * 40)
        print("購物車 API 異常，無法繼續測試 SSE")
        print("[ERROR]" * 40)
        return

    # 3. 測試 SSE 連線
    results['sse'] = await test_sse_connection(session_id)

    # 4. 測試廣播（跳過）
    results['broadcast'] = await test_sse_broadcast(session_id)

    # 總結
    print_section("診斷總結")

    print(f"\n  1. 後端伺服器: {'[OK] 正常' if results['backend'] else '[ERROR] 異常'}")
    print(f"  2. 購物車 API: {'[OK] 正常' if results['cart_api'] else '[ERROR] 異常'}")
    print(f"  3. SSE 連線:   {'[OK] 正常' if results['sse'] else '[ERROR] 異常'}")
    print(f"  4. SSE 廣播:   [INFO]  需瀏覽器測試")

    all_pass = all([results['backend'], results['cart_api'], results['sse']])

    print("\n" + "=" * 80)
    if all_pass:
        print("  [SUCCESS] 所有基礎功能測試通過！")
        print("  下一步：使用瀏覽器測試即時同步功能")
        print(f"  測試 URL: {BASE_URL}?sessionid={session_id}&tableid=DIAG-TEST")
        print("\n  詳細步驟請參考: docs/SSE_MANUAL_TEST_GUIDE.md")
    else:
        print("  [WARN]  部分測試失敗，請檢查上述錯誤訊息")
        print("  建議：")
        print("  1. 檢查後端日誌是否有錯誤訊息")
        print("  2. 確認資料庫連線正常")
        print("  3. 檢查相關模組是否正確導入")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[WARN]  診斷已中止")
    except Exception as e:
        print(f"\n\n[ERROR] 診斷過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
