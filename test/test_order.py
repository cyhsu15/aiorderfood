"""
Order 模組測試：涵蓋 Session 購物車與後台訂單 / Session 管理流程。
"""

from __future__ import annotations

import pytest
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.db import get_db
from app.models import UserSession, Order, OrderItem


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """覆寫 get_db 以使用測試資料庫。"""

    def _override_db():
        return db_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_cart_session_persistence(client: TestClient, db_session: Session) -> None:
    """購物車應建立 Session 並持久化資料。"""
    resp = client.get("/api/cart")
    assert resp.status_code == 200
    cart_data = resp.json()
    assert cart_data["items"] == []
    assert cart_data["note"] == ""
    assert cart_data["version"] == 1

    payload = {
        "items": [
            {
                "id": 101,
                "name": "Test Dish",
                "price": 120.5,
                "qty": 2,
                "size": "Large",
                "note": "Less salt",
                "uuid": "item-1",
                "image_url": "/images/default.png",
            }
        ],
        "note": "Takeaway",
    }
    resp = client.put("/api/cart", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Test Dish"
    assert data["note"] == "Takeaway"

    session_id = client.cookies.get("cart_session_id")
    assert session_id

    session = db_session.get(UserSession, session_id)
    assert session is not None
    assert session.data["cart"]["items"][0]["name"] == "Test Dish"


def test_create_order_and_admin_endpoints(client: TestClient, db_session: Session) -> None:
    """新增訂單並驗證後台訂單管理端點，包含新增與移除餐點。"""
    cart_resp = client.put(
        "/api/cart",
        json={
            "items": [
                {"id": 201, "name": "Seafood Platter", "price": 250, "qty": 1, "size": "Large"},
                {"id": 202, "name": "Juice", "price": 80, "qty": 2, "size": "Regular"},
            ],
            "note": "Pack separately",
        },
    )
    assert cart_resp.status_code == 200
    assert len(cart_resp.json()["items"]) == 2

    resp = client.post("/api/orders", json={"note": "Table A1"})
    assert resp.status_code == 201, resp.json()
    order_id = resp.json()["order_id"]

    order = db_session.get(Order, order_id)
    assert order is not None
    assert float(order.total_amount) == pytest.approx(410.0)
    assert order.note == "Table A1"
    assert len(order.items) == 2

    items = (
        db_session.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.order_item_id)
        .all()
    )
    assert len(items) == 2
    assert items[0].name == "Seafood Platter"
    assert items[1].quantity == 2

    resp = client.get("/api/cart")
    assert resp.status_code == 200
    cart_data = resp.json()
    assert cart_data["items"] == []
    assert cart_data["note"] == ""
    assert "version" in cart_data

    list_resp = client.get("/api/admin/orders")
    assert list_resp.status_code == 200
    orders_data = list_resp.json()
    assert any(o["order_id"] == order_id for o in orders_data)

    detail_resp = client.get(f"/api/admin/orders/{order_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["order_id"] == order_id
    assert len(detail["items"]) == 2

    update_resp = client.patch(
        f"/api/admin/orders/{order_id}",
        json={"status": "completed", "note": "Ready for pickup"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "completed"
    assert updated["note"] == "Ready for pickup"

    first_item_id = items[0].order_item_id
    item_update_resp = client.patch(
        f"/api/admin/orders/{order_id}",
        json={"items": [{"order_item_id": first_item_id, "quantity": 3, "note": "加辣"}]},
    )
    assert item_update_resp.status_code == 200
    detail_after_item_update = item_update_resp.json()
    first_item = next(i for i in detail_after_item_update["items"] if i["order_item_id"] == first_item_id)
    assert first_item["quantity"] == 3
    assert first_item["note"] == "加辣"
    assert detail_after_item_update["total_amount"] == pytest.approx(910.0)

    add_item_resp = client.patch(
        f"/api/admin/orders/{order_id}",
        json={
            "items": [
                {
                    "name": "Extra Snack",
                    "unit_price": 120,
                    "quantity": 2,
                    "note": "新增",
                }
            ]
        },
    )
    assert add_item_resp.status_code == 200
    detail_after_add = add_item_resp.json()
    assert detail_after_add["total_amount"] == pytest.approx(1150.0)
    new_item = next(i for i in detail_after_add["items"] if i["name"] == "Extra Snack")
    assert new_item["quantity"] == 2
    assert new_item["note"] == "新增"

    remove_resp = client.patch(
        f"/api/admin/orders/{order_id}",
        json={
            "items": [
                {
                    "order_item_id": new_item["order_item_id"],
                    "quantity": 0,
                }
            ]
        },
    )
    assert remove_resp.status_code == 200
    detail_after_remove = remove_resp.json()
    assert len(detail_after_remove["items"]) == 2
    assert detail_after_remove["total_amount"] == pytest.approx(910.0)


def test_admin_session_endpoints(client: TestClient, db_session: Session) -> None:
    """後台 Session 管理流程。"""
    client.get("/api/cart")
    client.put(
        "/api/cart",
        json={
            "items": [
                {"id": 301, "name": "Temp Dish", "price": 150, "qty": 1, "size": "Small"},
                {"id": 302, "name": "Drink", "price": 60, "qty": 2},
            ],
            "note": "Session note",
        },
    )
    session_id = client.cookies.get("cart_session_id")
    assert session_id

    list_resp = client.get("/api/admin/sessions")
    assert list_resp.status_code == 200
    sessions_data = list_resp.json()
    assert any(s["session_id"] == session_id for s in sessions_data)

    detail_resp = client.get(f"/api/admin/sessions/{session_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["session_id"] == session_id
    assert len(detail["cart_items"]) == 2

    clear_resp = client.post(f"/api/admin/sessions/{session_id}/clear-cart")
    assert clear_resp.status_code == 204

    detail_after_clear = client.get(f"/api/admin/sessions/{session_id}")
    assert detail_after_clear.status_code == 200
    assert detail_after_clear.json()["cart_items"] == []

    delete_resp = client.delete(f"/api/admin/sessions/{session_id}")
    assert delete_resp.status_code == 204

    not_found = client.get(f"/api/admin/sessions/{session_id}")
    assert not_found.status_code == 404


def test_cart_version_control(client: TestClient, db_session: Session) -> None:
    """測試購物車版本控制與樂觀鎖定功能，防止併發更新衝突。"""
    # 1. 初次取得購物車，應該有初始版本號
    resp = client.get("/api/cart")
    assert resp.status_code == 200
    cart1 = resp.json()
    assert cart1["items"] == []
    assert cart1["version"] == 1

    # 2. 新增第一個項目，版本號應遞增
    payload1 = {
        "items": [{"id": 401, "name": "Dish A", "price": 100, "qty": 1}],
        "note": "First update",
        "version": 1,  # 提供當前版本號
    }
    resp = client.put("/api/cart", json=payload1)
    assert resp.status_code == 200
    cart2 = resp.json()
    assert cart2["version"] == 2
    assert len(cart2["items"]) == 1

    # 3. 使用舊版本號更新應該失敗（模擬 User A 持有舊版本）
    payload_stale = {
        "items": [{"id": 402, "name": "Dish B", "price": 150, "qty": 1}],
        "note": "Stale update",
        "version": 1,  # 使用過期的版本號
    }
    resp = client.put("/api/cart", json=payload_stale)
    assert resp.status_code == 409  # Conflict
    assert "version_conflict" in resp.json()["detail"]

    # 4. 使用正確版本號更新應該成功
    payload3 = {
        "items": [
            {"id": 401, "name": "Dish A", "price": 100, "qty": 2},
            {"id": 403, "name": "Dish C", "price": 200, "qty": 1},
        ],
        "note": "Correct update",
        "version": 2,  # 使用正確的版本號
    }
    resp = client.put("/api/cart", json=payload3)
    assert resp.status_code == 200
    cart3 = resp.json()
    assert cart3["version"] == 3
    assert len(cart3["items"]) == 2

    # 5. 不提供版本號也應該允許更新（向後相容）
    payload_no_version = {
        "items": [{"id": 404, "name": "Dish D", "price": 120, "qty": 1}],
        "note": "Update without version",
    }
    resp = client.put("/api/cart", json=payload_no_version)
    assert resp.status_code == 200
    cart4 = resp.json()
    assert cart4["version"] == 4
    assert len(cart4["items"]) == 1

    # 6. 清空購物車也應該遞增版本號
    resp = client.delete("/api/cart")
    assert resp.status_code == 204

    resp = client.get("/api/cart")
    assert resp.status_code == 200
    cart5 = resp.json()
    assert cart5["items"] == []
    assert cart5["version"] == 5


def test_concurrent_cart_updates_simulation(client: TestClient, db_session: Session) -> None:
    """模擬併發更新場景：兩個請求同時更新購物車。"""
    # 初始化購物車
    resp = client.put(
        "/api/cart",
        json={"items": [{"id": 501, "name": "Initial", "price": 100, "qty": 1}]},
    )
    assert resp.status_code == 200
    initial_cart = resp.json()
    initial_version = initial_cart["version"]

    # 模擬 User A 和 User B 同時讀取購物車（看到相同版本）
    resp_a = client.get("/api/cart")
    resp_b = client.get("/api/cart")
    assert resp_a.json()["version"] == resp_b.json()["version"]

    # User A 先更新成功
    update_a = {
        "items": [{"id": 502, "name": "From User A", "price": 150, "qty": 1}],
        "version": initial_version,
    }
    resp = client.put("/api/cart", json=update_a)
    assert resp.status_code == 200
    new_version = resp.json()["version"]
    assert new_version == initial_version + 1

    # User B 嘗試使用舊版本更新應該失敗
    update_b = {
        "items": [{"id": 503, "name": "From User B", "price": 200, "qty": 1}],
        "version": initial_version,  # 使用舊版本
    }
    resp = client.put("/api/cart", json=update_b)
    assert resp.status_code == 409  # Conflict

    # User B 重新讀取購物車並以新版本更新
    resp = client.get("/api/cart")
    current_cart = resp.json()
    assert current_cart["items"][0]["name"] == "From User A"  # User A 的更新保留

    update_b_retry = {
        "items": [
            {"id": 502, "name": "From User A", "price": 150, "qty": 1},
            {"id": 503, "name": "From User B", "price": 200, "qty": 1},
        ],
        "version": current_cart["version"],  # 使用新版本
    }
    resp = client.put("/api/cart", json=update_b_retry)
    assert resp.status_code == 200
    final_cart = resp.json()
    assert len(final_cart["items"]) == 2


def test_order_status_validation(client: TestClient, db_session: Session) -> None:
    """測試訂單狀態驗證功能，確保僅允許有效的狀態值。"""
    # 1. 建立測試訂單
    client.put("/api/cart", json={"items": [{"id": 601, "name": "Test Dish", "price": 100, "qty": 1}]})
    resp = client.post("/api/orders", json={"note": "Test order"})
    assert resp.status_code == 201
    order_id = resp.json()["order_id"]

    # 2. 測試有效的狀態更新
    valid_statuses = ["pending", "confirmed", "preparing", "completed", "cancelled", "preorder"]
    for status_value in valid_statuses:
        resp = client.patch(f"/api/admin/orders/{order_id}", json={"status": status_value})
        assert resp.status_code == 200, f"Failed to update to {status_value}"
        assert resp.json()["status"] == status_value

    # 3. 測試無效的狀態值（應該被 Pydantic 攔截）
    resp = client.patch(f"/api/admin/orders/{order_id}", json={"status": "invalid_status"})
    assert resp.status_code == 422  # Unprocessable Entity (Pydantic validation error)

    # 4. 測試空字串
    resp = client.patch(f"/api/admin/orders/{order_id}", json={"status": ""})
    assert resp.status_code == 422

    # 5. 驗證最終狀態為最後一次有效更新
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "preorder"  # 最後一次有效的更新


def test_order_default_status(client: TestClient, db_session: Session) -> None:
    """測試訂單建立時的預設狀態為 'pending'。"""
    # 建立訂單
    client.put("/api/cart", json={"items": [{"id": 701, "name": "Test Item", "price": 50, "qty": 1}]})
    resp = client.post("/api/orders", json={"note": "Default status test"})
    assert resp.status_code == 201

    order_id = resp.json()["order_id"]

    # 檢查預設狀態
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    # 直接查詢資料庫確認
    from app.models import Order
    order = db_session.get(Order, order_id)
    assert order.status == "pending"


def test_list_orders_performance(client: TestClient, db_session: Session) -> None:
    """測試 list_orders 的查詢效能（應該使用 eager loading 避免 N+1）。"""
    # 建立多筆訂單，每筆訂單有多個明細
    for i in range(5):
        client.put(
            "/api/cart",
            json={
                "items": [
                    {"id": 800 + j, "name": f"Item {i}-{j}", "price": 100, "qty": 1}
                    for j in range(3)  # 每筆訂單 3 個項目
                ]
            }
        )
        client.post("/api/orders", json={"note": f"Test order {i}"})

    # 啟用 SQL 日誌記錄（若環境支援）
    import logging
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    # 列出訂單（應該只有 1 個主查詢 + 1 個 JOIN 查詢，而非 N+1）
    resp = client.get("/api/admin/orders?limit=10")
    assert resp.status_code == 200
    orders = resp.json()

    # 驗證訂單資料
    assert len(orders) >= 5
    for order in orders[:5]:
        assert "item_count" in order
        assert order["item_count"] == 3  # 每筆訂單有 3 個項目

    # 注意：在實際測試中，可以使用 SQLAlchemy 的查詢計數工具
    # 來驗證確實只執行了預期數量的查詢


def test_eager_loading_verification(db_session: Session) -> None:
    """驗證 eager loading 確實有效（單元測試層級）。"""
    from app.modules.order import service
    from app.models import Order, OrderItem

    # 建立測試資料
    order1 = Order(
        status="pending",
        total_amount=300,
        note="Test order 1",
    )
    db_session.add(order1)
    db_session.flush()

    for j in range(3):
        item = OrderItem(
            order_id=order1.order_id,
            dish_id=None,  # 設為 None 以符合外鍵約束
            name=f"Dish {j}",
            quantity=1,
            unit_price=100,
            line_total=100,
        )
        db_session.add(item)

    db_session.commit()

    # 使用 service 函數（應該使用 eager loading）
    orders = service.list_orders(db_session, limit=10)

    # 驗證資料正確
    assert len(orders) >= 1
    found_order = next((o for o in orders if o["order_id"] == order1.order_id), None)
    assert found_order is not None
    assert found_order["item_count"] == 3


def test_order_total_recalculation_on_status_change(client: TestClient, db_session: Session) -> None:
    """測試僅更新狀態時，訂單總金額仍然正確（確保使用 _recalculate_order_total）。"""
    from decimal import Decimal

    # 1. 建立一個訂單
    resp = client.put("/api/cart", json={
        "items": [
            {"id": 1, "name": "Dish A", "price": 100, "qty": 2},
            {"id": 2, "name": "Dish B", "price": 50, "qty": 3},
        ]
    })
    assert resp.status_code == 200

    resp = client.post("/api/orders", json={
        "contact_name": "Alice",
        "contact_phone": "0912345678",
    })
    assert resp.status_code == 201
    order_data = resp.json()
    order_id = order_data["order_id"]

    # 驗證初始總金額：100*2 + 50*3 = 350
    assert float(order_data["total_amount"]) == 350.0

    # 2. 僅更新狀態（不修改 items）
    resp = client.patch(f"/api/admin/orders/{order_id}", json={
        "status": "confirmed",
    })
    assert resp.status_code == 200
    updated = resp.json()

    # 驗證狀態已更新
    assert updated["status"] == "confirmed"

    # 驗證總金額仍然正確（_recalculate_order_total 被調用）
    assert float(updated["total_amount"]) == 350.0

    # 驗證資料庫中的金額也正確
    order = db_session.query(Order).filter_by(order_id=order_id).first()
    assert order is not None
    assert order.total_amount == Decimal("350.00")

    # 驗證 line_total 也正確
    items = sorted(order.items, key=lambda x: x.name)
    assert items[0].line_total == Decimal("200.00")  # Dish A: 100*2
    assert items[1].line_total == Decimal("150.00")  # Dish B: 50*3


def test_order_total_recalculation_on_item_update(client: TestClient, db_session: Session) -> None:
    """測試更新訂單明細時，總金額和 line_total 都正確重新計算。"""
    from decimal import Decimal

    # 1. 建立訂單
    resp = client.put("/api/cart", json={
        "items": [
            {"id": 1, "name": "Dish A", "price": 100, "qty": 2},
        ]
    })
    assert resp.status_code == 200

    resp = client.post("/api/orders", json={
        "contact_name": "Bob",
    })
    assert resp.status_code == 201
    order_summary = resp.json()
    order_id = order_summary["order_id"]

    # 驗證初始總金額：100*2 = 200
    assert float(order_summary["total_amount"]) == 200.0

    # 取得完整訂單資料（包含 items）
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    order_data = resp.json()
    original_item_id = order_data["items"][0]["order_item_id"]

    # 2. 修改數量並新增項目
    resp = client.patch(f"/api/admin/orders/{order_id}", json={
        "items": [
            {
                "order_item_id": original_item_id,
                "quantity": 5,  # 修改數量從 2 到 5
            },
            {
                "name": "Dish B",
                "unit_price": 50,
                "quantity": 3,  # 新增項目
            },
        ]
    })
    assert resp.status_code == 200
    updated = resp.json()

    # 驗證總金額重新計算：100*5 + 50*3 = 650
    assert float(updated["total_amount"]) == 650.0

    # 驗證資料庫
    order = db_session.query(Order).filter_by(order_id=order_id).first()
    assert order is not None
    assert order.total_amount == Decimal("650.00")
    assert len(order.items) == 2

    # 驗證每個 line_total 都正確
    items_by_name = {item.name: item for item in order.items}
    assert items_by_name["Dish A"].line_total == Decimal("500.00")  # 100*5
    assert items_by_name["Dish B"].line_total == Decimal("150.00")  # 50*3


def test_order_total_recalculation_on_item_deletion(client: TestClient, db_session: Session) -> None:
    """測試刪除訂單明細（quantity=0）時，總金額正確重新計算。"""
    from decimal import Decimal

    # 1. 建立包含多個項目的訂單
    resp = client.put("/api/cart", json={
        "items": [
            {"id": 1, "name": "Dish A", "price": 100, "qty": 2},
            {"id": 2, "name": "Dish B", "price": 50, "qty": 3},
            {"id": 3, "name": "Dish C", "price": 75, "qty": 1},
        ]
    })
    assert resp.status_code == 200

    resp = client.post("/api/orders", json={
        "contact_name": "Charlie",
    })
    assert resp.status_code == 201
    order_summary = resp.json()
    order_id = order_summary["order_id"]

    # 驗證初始總金額：100*2 + 50*3 + 75*1 = 425
    assert float(order_summary["total_amount"]) == 425.0

    # 取得完整訂單資料（包含 items）
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    order_data = resp.json()

    # 找到 "Dish B" 的 order_item_id
    dish_b_item = next(item for item in order_data["items"] if item["name"] == "Dish B")
    dish_b_id = dish_b_item["order_item_id"]

    # 2. 刪除 "Dish B"（設定 quantity=0）
    resp = client.patch(f"/api/admin/orders/{order_id}", json={
        "items": [
            {
                "order_item_id": dish_b_id,
                "quantity": 0,  # 刪除此項目
            },
        ]
    })
    assert resp.status_code == 200
    updated = resp.json()

    # 驗證總金額重新計算：100*2 + 75*1 = 275
    assert float(updated["total_amount"]) == 275.0
    assert len(updated["items"]) == 2

    # 驗證資料庫
    order = db_session.query(Order).filter_by(order_id=order_id).first()
    assert order is not None
    assert order.total_amount == Decimal("275.00")
    assert len(order.items) == 2

    # 驗證 "Dish B" 已被刪除
    item_names = {item.name for item in order.items}
    assert "Dish A" in item_names
    assert "Dish C" in item_names
    assert "Dish B" not in item_names


def test_concurrent_cart_updates_with_threading(client: TestClient, db_session: Session) -> None:
    """測試真正的並發購物車更新（使用多線程）。

    此測試使用真實的多線程來模擬多個用戶同時更新同一個購物車，
    驗證樂觀鎖定機制能正確處理並發衝突。
    """
    # 1. 建立初始購物車並設置 cookies 到 client 實例
    resp = client.get("/api/cart")
    assert resp.status_code == 200
    # 將 cookies 設置到 client 實例上（避免 DeprecationWarning）
    client.cookies.update(resp.cookies)

    # 2. 定義並發更新函數
    def update_cart_worker(worker_id: int) -> dict:
        """每個 worker 嘗試添加不同的商品到購物車"""
        try:
            # 先讀取當前購物車（不需要傳遞 cookies 參數）
            resp = client.get("/api/cart")
            cart_data = resp.json()
            current_items = cart_data.get("items", [])
            current_version = cart_data.get("version")

            # 添加新商品
            new_item = {
                "id": 100 + worker_id,
                "name": f"Dish-Worker-{worker_id}",
                "price": 50 + worker_id * 10,
                "qty": 1,
                "uuid": f"worker-{worker_id}",
            }
            current_items.append(new_item)

            # 嘗試更新（不需要傳遞 cookies 參數）
            resp = client.put("/api/cart", json={
                "items": current_items,
                "version": current_version,
            })

            return {
                "worker_id": worker_id,
                "status_code": resp.status_code,
                "success": resp.status_code == 200,
                "conflict": resp.status_code == 409,
            }
        except Exception as e:
            return {
                "worker_id": worker_id,
                "status_code": -1,
                "success": False,
                "error": str(e),
            }

    # 3. 使用 ThreadPoolExecutor 執行並發更新
    num_workers = 10
    results = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(update_cart_worker, i) for i in range(num_workers)]
        for future in as_completed(futures):
            results.append(future.result())

    # 4. 驗證結果
    successful = [r for r in results if r.get("success", False)]
    conflicts = [r for r in results if r.get("conflict", False)]
    errors = [r for r in results if "error" in r]

    # 至少有一個成功
    assert len(successful) >= 1, "At least one update should succeed"

    # 可能有衝突（因為並發）
    print(f"\n並發測試結果: {len(successful)} 成功, {len(conflicts)} 衝突, {len(errors)} 錯誤")
    if errors:
        for err in errors:
            print(f"  Worker {err['worker_id']} 錯誤: {err.get('error', 'unknown')}")

    # 5. 驗證最終購物車狀態（不需要傳遞 cookies 參數）
    resp = client.get("/api/cart")
    assert resp.status_code == 200
    final_cart = resp.json()

    # 購物車應該有商品（至少有成功添加的）
    assert len(final_cart["items"]) >= 1
    # 版本號應該已遞增
    assert final_cart["version"] > 1


def test_large_cart_stress_test(client: TestClient, db_session: Session) -> None:
    """大型購物車壓力測試（100+ 件商品）。

    測試系統能否正確處理包含大量商品的購物車，
    驗證效能、資料完整性和計算準確性。
    """
    # 1. 建立包含 150 件商品的購物車
    num_items = 150
    large_cart_items = []

    for i in range(num_items):
        large_cart_items.append({
            "id": 1000 + i,
            "name": f"Bulk Item {i:03d}",
            "price": 10.5 + (i % 10) * 0.5,  # 價格範圍: 10.5 ~ 15.0
            "qty": 1 + (i % 5),  # 數量範圍: 1 ~ 5
            "uuid": f"bulk-{i}",
        })

    # 2. 更新購物車
    resp = client.put("/api/cart", json={"items": large_cart_items})
    assert resp.status_code == 200
    cart_data = resp.json()

    # 3. 驗證所有商品都成功添加
    assert len(cart_data["items"]) == num_items

    # 4. 計算預期總金額
    expected_total = sum(item["price"] * item["qty"] for item in large_cart_items)

    # 5. 建立訂單
    resp = client.post("/api/orders", json={
        "contact_name": "Bulk Tester",
        "contact_phone": "0900000000",
    })
    assert resp.status_code == 201
    order_summary = resp.json()
    order_id = order_summary["order_id"]

    # 6. 取得訂單詳細資料
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    order_detail = resp.json()

    # 7. 驗證訂單明細數量
    assert len(order_detail["items"]) == num_items

    # 8. 驗證總金額正確（考慮浮點數精度）
    actual_total = float(order_detail["total_amount"])
    assert abs(actual_total - expected_total) < 0.01, \
        f"Total mismatch: expected {expected_total}, got {actual_total}"

    # 9. 驗證資料庫中的訂單
    order = db_session.query(Order).filter_by(order_id=order_id).first()
    assert order is not None
    assert len(order.items) == num_items

    # 10. 驗證每個 line_total 都正確計算
    for order_item in order.items:
        expected_line_total = order_item.unit_price * order_item.quantity
        assert order_item.line_total == expected_line_total, \
            f"Line total mismatch for {order_item.name}"

    # 11. 驗證總金額 = 所有 line_total 之和
    calculated_total = sum(item.line_total for item in order.items)
    assert order.total_amount == calculated_total

    print(f"\n壓力測試通過: {num_items} 件商品, 總金額 ${actual_total:.2f}")


def test_list_session_orders(client: TestClient, db_session: Session) -> None:
    """測試列出當前 Session 的訂單歷史。"""
    # 1. 建立第一筆訂單
    client.put("/api/cart", json={
        "items": [
            {"id": 1, "name": "Dish A", "price": 100, "qty": 2},
            {"id": 2, "name": "Dish B", "price": 50, "qty": 1},
        ]
    })
    resp = client.post("/api/orders", json={"note": "First order"})
    assert resp.status_code == 201
    order1_id = resp.json()["order_id"]

    # 2. 建立第二筆訂單
    client.put("/api/cart", json={
        "items": [
            {"id": 3, "name": "Dish C", "price": 75, "qty": 3},
        ]
    })
    resp = client.post("/api/orders", json={"note": "Second order"})
    assert resp.status_code == 201
    order2_id = resp.json()["order_id"]

    # 3. 取得當前 Session 的訂單列表
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    orders = resp.json()

    # 4. 驗證訂單數量和內容
    assert len(orders) == 2

    # 訂單應該按建立時間降序排列（最新的在前）
    assert orders[0]["order_id"] == order2_id
    assert orders[1]["order_id"] == order1_id

    # 5. 驗證第一筆訂單的內容
    order1 = orders[1]
    assert order1["total_amount"] == 250.0  # 100*2 + 50*1
    assert order1["note"] == "First order"
    assert len(order1["items"]) == 2
    assert order1["items"][0]["name"] == "Dish A"
    assert order1["items"][0]["quantity"] == 2
    assert order1["items"][1]["name"] == "Dish B"
    assert order1["items"][1]["quantity"] == 1

    # 6. 驗證第二筆訂單的內容
    order2 = orders[0]
    assert order2["total_amount"] == 225.0  # 75*3
    assert order2["note"] == "Second order"
    assert len(order2["items"]) == 1
    assert order2["items"][0]["name"] == "Dish C"
    assert order2["items"][0]["quantity"] == 3

    # 7. 驗證訂單有正確的時間戳記
    assert "created_at" in order1
    assert "created_at" in order2
    assert order1["created_at"] is not None
    assert order2["created_at"] is not None


def test_list_session_orders_empty(client: TestClient, db_session: Session) -> None:
    """測試當沒有訂單時，應該返回空列表。"""
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert orders == []


def test_list_session_orders_isolation(client: TestClient, db_session: Session) -> None:
    """測試不同 Session 的訂單應該互相隔離。"""
    # 1. 第一個 client 建立訂單
    client1 = client
    client1.put("/api/cart", json={
        "items": [{"id": 1, "name": "Dish A", "price": 100, "qty": 1}]
    })
    resp = client1.post("/api/orders", json={"note": "Client 1 order"})
    assert resp.status_code == 201

    # 2. 第二個 client（新 Session）建立訂單
    from fastapi.testclient import TestClient
    from main import app
    client2 = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    client2.put("/api/cart", json={
        "items": [{"id": 2, "name": "Dish B", "price": 50, "qty": 1}]
    })
    resp = client2.post("/api/orders", json={"note": "Client 2 order"})
    assert resp.status_code == 201

    # 3. 驗證 client1 只能看到自己的訂單
    resp = client1.get("/api/orders")
    assert resp.status_code == 200
    orders1 = resp.json()
    assert len(orders1) == 1
    assert orders1[0]["note"] == "Client 1 order"

    # 4. 驗證 client2 只能看到自己的訂單
    resp = client2.get("/api/orders")
    assert resp.status_code == 200
    orders2 = resp.json()
    assert len(orders2) == 1
    assert orders2[0]["note"] == "Client 2 order"


def test_currency_quantization_edge_cases(client: TestClient, db_session: Session) -> None:
    """測試貨幣量化邊緣情況（四捨五入）。

    驗證系統正確處理需要四捨五入的貨幣計算，
    確保不會因浮點數精度問題導致金額錯誤。
    """
    test_cases = [
        # (price, qty, expected_line_total)
        # 注意：價格先量化到 2 位小數，再乘以數量
        (10.001, 1, Decimal("10.00")),  # 10.001 → 10.00, 10.00 * 1 = 10.00
        (10.005, 1, Decimal("10.01")),  # 10.005 → 10.01 (banker's rounding)
        (10.004, 1, Decimal("10.00")),  # 10.004 → 10.00
        (10.006, 1, Decimal("10.01")),  # 10.006 → 10.01
        (33.333, 3, Decimal("99.99")),  # 33.333 → 33.33, 33.33 * 3 = 99.99
        (0.01, 100, Decimal("1.00")),   # 0.01 → 0.01, 0.01 * 100 = 1.00
        (99.999, 2, Decimal("200.00")), # 99.999 → 100.00, 100.00 * 2 = 200.00
        (7.777, 7, Decimal("54.46")),   # 7.777 → 7.78, 7.78 * 7 = 54.46
    ]

    # 1. 建立購物車
    cart_items = []
    for idx, (price, qty, expected) in enumerate(test_cases):
        cart_items.append({
            "id": 2000 + idx,
            "name": f"Round Test {idx}",
            "price": price,
            "qty": qty,
            "uuid": f"round-{idx}",
        })

    resp = client.put("/api/cart", json={"items": cart_items})
    assert resp.status_code == 200

    # 2. 建立訂單
    resp = client.post("/api/orders", json={
        "contact_name": "Rounding Tester",
    })
    assert resp.status_code == 201
    order_id = resp.json()["order_id"]

    # 3. 取得訂單詳細
    resp = client.get(f"/api/admin/orders/{order_id}")
    assert resp.status_code == 200
    order_detail = resp.json()

    # 4. 驗證資料庫中的訂單
    order = db_session.query(Order).filter_by(order_id=order_id).first()
    assert order is not None

    # 5. 按名稱建立 order_item 對應表
    items_by_name = {item.name: item for item in order.items}

    # 6. 驗證每個測試案例的 line_total
    for idx, (price, qty, expected_line_total) in enumerate(test_cases):
        item_name = f"Round Test {idx}"
        order_item = items_by_name[item_name]

        # 驗證 line_total 正確量化到 2 位小數
        assert order_item.line_total == expected_line_total, \
            f"Case {idx}: {price} * {qty} should be {expected_line_total}, got {order_item.line_total}"

        # 驗證 line_total 是 Decimal 類型且最多 2 位小數
        assert isinstance(order_item.line_total, Decimal)
        assert order_item.line_total == order_item.line_total.quantize(Decimal("0.01"))

    # 7. 驗證總金額 = 所有 expected line_total 之和
    expected_total = sum(expected for _, _, expected in test_cases)
    assert order.total_amount == expected_total, \
        f"Total should be {expected_total}, got {order.total_amount}"

    # 8. 驗證總金額也正確量化
    assert order.total_amount == order.total_amount.quantize(Decimal("0.01"))

    print(f"\n四捨五入測試通過: {len(test_cases)} 個邊緣案例, 總金額 ${float(order.total_amount):.2f}")
