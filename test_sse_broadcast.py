"""
測試 SSE 廣播功能的腳本

使用方法：
python test_sse_broadcast.py <session_id>
"""

import asyncio
import sys
import httpx


async def test_broadcast(session_id: str):
    """測試向指定 session 發送測試廣播"""
    base_url = "http://127.0.0.1:8080"

    print(f"\n🔍 檢查 SSE 連線狀態...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. 檢查連線數
        resp = await client.get(f"{base_url}/api/sse/debug/connections")
        conn_data = resp.json()
        print(f"📊 連線統計:")
        print(f"   總連線數: {conn_data['total_connections']}")
        print(f"   活躍 sessions: {conn_data['active_sessions']}")
        print(f"   詳細資訊: {conn_data['session_details']}")

        if session_id not in conn_data['session_details']:
            print(f"\n❌ Session {session_id} 沒有活躍連線！")
            return

        conn_count = conn_data['session_details'][session_id]
        print(f"\n✅ Session {session_id} 有 {conn_count} 個活躍連線")

        # 2. 獲取當前購物車
        print(f"\n🛒 獲取當前購物車...")
        resp = await client.get(f"{base_url}/api/cart", params={
            "sessionid": session_id,
            "tableid": "TEST"
        })
        cart_data = resp.json()
        print(f"   商品數: {len(cart_data.get('items', []))}")
        print(f"   版本號: {cart_data.get('version')}")

        # 3. 發送一個測試更新（加入一個測試商品）
        print(f"\n📤 發送測試廣播（模擬加入商品）...")
        test_item = {
            "id": 999,
            "name": "🧪 測試商品",
            "qty": 1,
            "price": 99.0,
            "size": None,
            "note": "SSE 測試",
            "uuid": "test-broadcast-item",
            "image_url": ""
        }

        new_cart = {
            "items": cart_data.get("items", []) + [test_item],
            "note": cart_data.get("note", ""),
            "version": cart_data.get("version")
        }

        resp = await client.put(f"{base_url}/api/cart",
                                json=new_cart,
                                params={
                                    "sessionid": session_id,
                                    "tableid": "TEST"
                                })

        if resp.status_code == 200:
            print(f"✅ 購物車更新成功！")
            print(f"   新版本號: {resp.json().get('version')}")
            print(f"\n💡 請檢查所有連線的前端 Console，應該都會收到 cart_updated 事件")
        else:
            print(f"❌ 購物車更新失敗: {resp.status_code}")
            print(f"   {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python test_sse_broadcast.py <session_id>")
        print("範例: python test_sse_broadcast.py 284747f1-69a4-4f85-9cc5-ba6d2b9e644b")
        sys.exit(1)

    session_id = sys.argv[1]
    asyncio.run(test_broadcast(session_id))
