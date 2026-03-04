"""
測試 SSE 版本號去重功能

驗證：
1. 單人模式下，更新購物車後不會收到自己的 SSE 廣播
2. 多人模式下，其他使用者仍能收到 SSE 更新
"""

from __future__ import annotations

import asyncio
import uuid
import json
from typing import List, Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from main import app
from app.modules.sse.service import sse_manager


def test_sse_sender_receives_own_update_with_version(client_with_db, db_session: Session):
    """
    測試：發送者會收到自己的 SSE 更新（含版本號）

    前端應該根據版本號判斷是否跳過重新載入。
    此測試驗證後端確實廣播給所有連線（包括發送者）。
    """
    # 1. 創建 session
    test_session_id = str(uuid.uuid4())
    test_table_id = "TEST-A1"

    client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )

    # 2. 模擬建立 SSE 連線
    sender_queue = sse_manager.connect(uuid.UUID(test_session_id))

    # 3. 更新購物車
    cart_payload = {
        "items": [
            {
                "id": 1,
                "name": "測試菜品",
                "qty": 1,
                "price": 100.0,
                "size": "小",
                "note": "",
                "uuid": str(uuid.uuid4())
            }
        ],
        "note": "",
        "version": 1
    }

    response = client_with_db.put("/api/cart", json=cart_payload)
    assert response.status_code == 200

    response_data = response.json()
    assert "version" in response_data
    assert response_data["version"] == 2  # 版本號應該遞增

    # 4. 等待 SSE 訊息（使用同步方式）
    import time
    timeout = 2.0
    elapsed = 0
    while sender_queue.empty() and elapsed < timeout:
        time.sleep(0.1)
        elapsed += 0.1

    # 5. 檢查 SSE 訊息
    assert not sender_queue.empty(), "發送者應該收到 SSE 訊息"

    message = sender_queue.get_nowait()
    assert "event: cart_updated" in message

    # 解析 SSE 訊息
    data_line = [line for line in message.split("\n") if line.startswith("data: ")][0]
    data_json = data_line.replace("data: ", "")
    data = json.loads(data_json)

    # 6. 驗證訊息包含版本號
    assert "cart" in data
    assert "version" in data["cart"]
    assert data["cart"]["version"] == 2  # 🎯 關鍵：版本號應該是更新後的值

    # 清理
    sse_manager.disconnect(sender_queue)


def test_sse_other_users_receive_update(client_with_db, db_session: Session):
    """
    測試：其他使用者能收到 SSE 更新

    驗證多人共享桌號時，一個人更新購物車，其他人能收到通知。
    """
    # 1. 創建共享 session
    test_session_id = str(uuid.uuid4())
    test_table_id = "TEST-B2"

    client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )

    # 2. 模擬兩個使用者的 SSE 連線
    user_a_queue = sse_manager.connect(uuid.UUID(test_session_id))
    user_b_queue = sse_manager.connect(uuid.UUID(test_session_id))

    # 3. User A 更新購物車
    cart_payload = {
        "items": [
            {
                "id": 2,
                "name": "紅燒魚",
                "qty": 1,
                "price": 280.0,
                "size": "小",
                "note": "",
                "uuid": str(uuid.uuid4())
            }
        ],
        "note": "",
        "version": 1
    }

    response = client_with_db.put("/api/cart", json=cart_payload)
    assert response.status_code == 200

    # 4. 等待 SSE 訊息（使用同步方式）
    import time
    timeout = 2.0
    elapsed = 0
    while user_b_queue.empty() and elapsed < timeout:
        time.sleep(0.1)
        elapsed += 0.1

    # 5. 驗證 User B 收到更新
    assert not user_b_queue.empty(), "User B 應該收到 SSE 訊息"

    message = user_b_queue.get_nowait()
    assert "event: cart_updated" in message

    # 解析訊息
    data_line = [line for line in message.split("\n") if line.startswith("data: ")][0]
    data_json = data_line.replace("data: ", "")
    data = json.loads(data_json)

    # 6. 驗證訊息內容
    assert data["cart"]["version"] == 2
    assert len(data["cart"]["items"]) == 1
    assert data["cart"]["items"][0]["name"] == "紅燒魚"
    assert data["table_id"] == test_table_id

    # 清理
    sse_manager.disconnect(user_a_queue)
    sse_manager.disconnect(user_b_queue)


def test_sse_version_mismatch_in_broadcast(client_with_db, db_session: Session):
    """
    測試：SSE 廣播的版本號與 HTTP 回應一致

    確保前端能正確比較版本號。
    """
    # 1. 創建 session
    test_session_id = str(uuid.uuid4())

    client_with_db.get("/api/cart", params={"sessionid": test_session_id})

    # 2. 建立 SSE 連線
    queue = sse_manager.connect(uuid.UUID(test_session_id))

    # 3. 更新購物車
    cart_payload = {
        "items": [{"id": 3, "name": "測試", "qty": 2, "price": 50.0, "size": "大", "note": "", "uuid": str(uuid.uuid4())}],
        "note": "",
        "version": 1
    }

    response = client_with_db.put("/api/cart", json=cart_payload)
    http_version = response.json()["version"]

    # 4. 等待 SSE 訊息（使用同步方式）
    import time
    timeout = 2.0
    elapsed = 0
    while queue.empty() and elapsed < timeout:
        time.sleep(0.1)
        elapsed += 0.1

    message = queue.get_nowait()
    data_line = [line for line in message.split("\n") if line.startswith("data: ")][0]
    data = json.loads(data_line.replace("data: ", ""))

    sse_version = data["cart"]["version"]

    # 5. 驗證版本號一致
    assert http_version == sse_version, f"HTTP 版本號 ({http_version}) 與 SSE 版本號 ({sse_version}) 不一致"

    # 清理
    sse_manager.disconnect(queue)
