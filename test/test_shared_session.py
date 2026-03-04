"""
測試共享桌號點餐功能

涵蓋：
- Session 參數處理（sessionid, tableid）
- 購物車共享
- 空購物車限制
- table_id 持久化
"""

from __future__ import annotations

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

# 確保 app 可導入
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from main import app
from app.models import UserSession, Order


# ==================== Session 參數處理測試 ====================

def test_create_session_with_url_parameters(client_with_db, db_session: Session):
    """測試：使用 URL 參數創建 session"""
    # client_with_db 已通過參數注入

    # 生成測試用的 sessionid 和 tableid
    test_session_id = str(uuid.uuid4())
    test_table_id = "A1"

    # 發送請求，帶上 sessionid 和 tableid
    response = client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )

    assert response.status_code == 200

    # 驗證 Session 已在資料庫中創建
    session_record = db_session.get(UserSession, uuid.UUID(test_session_id))
    assert session_record is not None
    assert str(session_record.session_id) == test_session_id
    assert session_record.table_id == test_table_id

    # 驗證 Cookie 已設定
    cookies = response.cookies
    assert "cart_session_id" in cookies
    assert cookies["cart_session_id"] == test_session_id


def test_reuse_existing_session_with_url_parameters(client_with_db, db_session: Session):
    """測試：多個使用者使用相同 sessionid 共享 session"""
    # client_with_db 已通過參數注入

    # 第一個使用者創建 session
    test_session_id = str(uuid.uuid4())
    test_table_id = "B2"

    response1 = client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )
    assert response1.status_code == 200

    # 第二個使用者使用相同 sessionid（模擬掃描同一個 QR Code）
    response2 = client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )
    assert response2.status_code == 200

    # 驗證資料庫中只有一個 session
    session_count = db_session.execute(
        text("SELECT COUNT(*) FROM user_session WHERE session_id = :sid"),
        {"sid": uuid.UUID(test_session_id)}
    ).scalar()
    assert session_count == 1


def test_tableid_persistence(client_with_db, db_session: Session):
    """測試：table_id 正確寫入並持久化"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "C3"

    # 創建 session
    client_with_db.get("/api/cart", params={"sessionid": test_session_id, "tableid": test_table_id})

    # 從資料庫讀取
    session_record = db_session.get(UserSession, uuid.UUID(test_session_id))
    assert session_record.table_id == test_table_id


def test_update_tableid_if_different(client_with_db, db_session: Session):
    """測試：若 session 已存在但桌號不同，應更新桌號"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())

    # 第一次請求：設定桌號為 D1
    client_with_db.get("/api/cart", params={"sessionid": test_session_id, "tableid": "D1"})

    # 第二次請求：更改桌號為 D2
    client_with_db.get("/api/cart", params={"sessionid": test_session_id, "tableid": "D2"})

    # 驗證桌號已更新為 D2
    session_record = db_session.get(UserSession, uuid.UUID(test_session_id))
    assert session_record.table_id == "D2"


# ==================== 購物車共享測試 ====================

def test_cart_shared_across_users(client_with_db, db_session: Session):
    """測試：使用者 A 新增商品，使用者 B 可見"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "E5"

    # 使用者 A：新增商品到購物車
    cart_payload = {
        "items": [
            {
                "id": 1,
                "name": "Test Dish A",
                "price": 100.0,
                "qty": 2,
                "size": "Medium",
                "note": "No onions"
            }
        ],
        "note": "Table E5 order"
    }

    response_a = client_with_db.put(
        "/api/cart",
        json=cart_payload,
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )
    assert response_a.status_code == 200

    # 使用者 B：讀取購物車（使用相同 sessionid）
    response_b = client_with_db.get(
        "/api/cart",
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )
    assert response_b.status_code == 200

    cart_data = response_b.json()
    assert len(cart_data["items"]) == 1
    assert cart_data["items"][0]["name"] == "Test Dish A"
    assert cart_data["items"][0]["qty"] == 2


def test_cart_version_conflict_detection(client_with_db, db_session: Session):
    """測試：兩使用者同時修改觸發版本衝突"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())

    # 使用者 A：讀取購物車（取得版本號）
    response_a = client_with_db.get("/api/cart", params={"sessionid": test_session_id})
    assert response_a.status_code == 200
    version_a = response_a.json().get("version")

    # 使用者 B：修改購物車（版本號會遞增）
    cart_b = {
        "items": [{"id": 1, "name": "Dish B", "price": 50.0, "qty": 1}],
        "version": version_a
    }
    response_b = client_with_db.put(
        "/api/cart",
        json=cart_b,
        params={"sessionid": test_session_id}
    )
    assert response_b.status_code == 200
    version_b = response_b.json().get("version")
    assert version_b > version_a

    # 使用者 A：嘗試使用舊版本號修改購物車（應觸發衝突）
    cart_a = {
        "items": [{"id": 2, "name": "Dish A", "price": 80.0, "qty": 3}],
        "version": version_a  # 使用舊版本號
    }
    response_a_conflict = client_with_db.put(
        "/api/cart",
        json=cart_a,
        params={"sessionid": test_session_id}
    )
    assert response_a_conflict.status_code == 409  # Conflict


# ==================== 空購物車限制測試 ====================

def test_prevent_empty_cart_after_order(client_with_db, db_session: Session):
    """測試：送出訂單後無法送出空購物車"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "F6"

    # 1. 新增商品到購物車
    cart_payload = {
        "items": [
            {"id": 1, "name": "Test Dish", "price": 120.0, "qty": 1}
        ]
    }
    client_with_db.put(
        "/api/cart",
        json=cart_payload,
        params={"sessionid": test_session_id, "tableid": test_table_id}
    )

    # 2. 送出訂單（購物車會被清空）
    order_response = client_with_db.post(
        "/api/orders",
        json={"note": "First order"},
        params={"sessionid": test_session_id}
    )
    assert order_response.status_code == 201

    # 3. 驗證購物車已被清空
    cart_response = client_with_db.get("/api/cart", params={"sessionid": test_session_id})
    assert len(cart_response.json()["items"]) == 0

    # 4. 嘗試送出空購物車（應被拒絕）
    empty_order_response = client_with_db.post(
        "/api/orders",
        json={"note": "Empty order"},
        params={"sessionid": test_session_id}
    )
    assert empty_order_response.status_code == 422
    assert empty_order_response.json()["detail"] == "cannot_submit_empty_cart_after_order"


def test_allow_non_empty_cart_after_order(client_with_db, db_session: Session):
    """測試：送出訂單後仍可送出有商品的購物車（追加訂單）"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "G7"

    # 1. 第一次下單
    cart1 = {"items": [{"id": 1, "name": "Dish 1", "price": 100.0, "qty": 1}]}
    client_with_db.put("/api/cart", json=cart1, params={"sessionid": test_session_id, "tableid": test_table_id})

    order1 = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    assert order1.status_code == 201

    # 2. 新增第二批商品
    cart2 = {"items": [{"id": 2, "name": "Dish 2", "price": 150.0, "qty": 2}]}
    client_with_db.put("/api/cart", json=cart2, params={"sessionid": test_session_id})

    # 3. 第二次下單（應該成功）
    order2 = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    assert order2.status_code == 201

    # 驗證有兩筆訂單
    session_record = db_session.get(UserSession, uuid.UUID(test_session_id))
    assert len(session_record.orders) == 2


def test_first_order_allows_empty_cart(client_with_db, db_session: Session):
    """測試：首次訂單如果購物車為空，應回傳 cart_empty（而非 cannot_submit_empty_cart_after_order）"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())

    # 確保購物車為空
    cart_response = client_with_db.get("/api/cart", params={"sessionid": test_session_id})
    assert len(cart_response.json()["items"]) == 0

    # 嘗試送出空購物車（首次訂單）
    order_response = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    assert order_response.status_code == 400
    assert order_response.json()["detail"] == "cart_empty"


# ==================== 訂單桌號測試 ====================

def test_order_inherits_table_id_from_session(client_with_db, db_session: Session):
    """測試：訂單建立時會複製 session 的 table_id"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "H8"

    # 新增商品並下單
    cart = {"items": [{"id": 1, "name": "Dish", "price": 200.0, "qty": 1}]}
    client_with_db.put("/api/cart", json=cart, params={"sessionid": test_session_id, "tableid": test_table_id})

    order_response = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    assert order_response.status_code == 201

    order_id = order_response.json()["order_id"]

    # 驗證訂單的 table_id
    order_record = db_session.query(Order).filter(Order.order_id == order_id).first()
    assert order_record is not None
    assert order_record.table_id == test_table_id


def test_multiple_orders_same_table_id(client_with_db, db_session: Session):
    """測試：同一桌的多筆訂單都有相同的 table_id"""
    # client_with_db 已通過參數注入

    test_session_id = str(uuid.uuid4())
    test_table_id = "I9"

    # 第一筆訂單
    cart1 = {"items": [{"id": 1, "name": "Dish 1", "price": 100.0, "qty": 1}]}
    client_with_db.put("/api/cart", json=cart1, params={"sessionid": test_session_id, "tableid": test_table_id})
    order1 = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    order1_id = order1.json()["order_id"]

    # 第二筆訂單
    cart2 = {"items": [{"id": 2, "name": "Dish 2", "price": 150.0, "qty": 2}]}
    client_with_db.put("/api/cart", json=cart2, params={"sessionid": test_session_id})
    order2 = client_with_db.post("/api/orders", json={}, params={"sessionid": test_session_id})
    order2_id = order2.json()["order_id"]

    # 驗證兩筆訂單的 table_id 都是 I9
    order1_record = db_session.query(Order).filter(Order.order_id == order1_id).first()
    order2_record = db_session.query(Order).filter(Order.order_id == order2_id).first()

    assert order1_record.table_id == test_table_id
    assert order2_record.table_id == test_table_id
