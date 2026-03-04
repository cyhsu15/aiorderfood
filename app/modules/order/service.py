"""
訂單與購物車服務：集中處理 Session 資料與訂單建立邏輯。
"""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List

from sqlalchemy.orm import Session, joinedload

from app.models import UserSession, Order, OrderItem, OrderStatus

MONEY_QUANT = Decimal("0.01")


def _quantize_money(value: Decimal) -> Decimal:
    """統一金額小數處理，避免浮點誤差。"""
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _recalculate_order_total(order: Order) -> None:
    """重新計算訂單總金額並更新 line_total。

    此函數確保：
    1. 每個 order_item 的 line_total = unit_price * quantity
    2. order.total_amount = sum(all line_totals)
    3. cart_snapshot 與實際明細同步

    應在以下情況調用：
    - 新增/刪除訂單明細
    - 更新明細數量或單價
    - 任何可能影響總金額的變更
    """
    total = Decimal("0")

    for order_item in order.items:
        # 確保單價和數量為 Decimal
        unit_price = (
            order_item.unit_price
            if isinstance(order_item.unit_price, Decimal)
            else _to_decimal(order_item.unit_price)
        )
        qty = int(order_item.quantity or 0)

        # 重新計算明細小計
        order_item.line_total = _quantize_money(unit_price * qty)
        total += order_item.line_total

    # 更新訂單總金額
    order.total_amount = _quantize_money(total)

    # 更新購物車快照
    snapshot_items = [
        {
            "id": item.dish_id,
            "name": item.name,
            "qty": int(item.quantity or 0),
            "price": float(item.unit_price),
            "note": item.note,
            "size": item.size_label,
        }
        for item in order.items
    ]
    order.cart_snapshot = {"items": snapshot_items, "note": order.note or ""}


def _get_session_data(session: UserSession) -> Dict[str, Any]:
    """取得 Session.data 的字典副本，若不存在則回傳新字典。"""
    data = session.data
    return dict(data) if isinstance(data, dict) else {}


def _get_cart_snapshot(session: UserSession) -> Dict[str, Any]:
    """擷取 Session 內的購物車快照。"""
    data = _get_session_data(session)
    cart = data.get("cart")
    if not isinstance(cart, dict):
        return {"items": [], "note": ""}
    items = cart.get("items")
    note = cart.get("note")
    return {
        "items": items if isinstance(items, list) else [],
        "note": note if isinstance(note, str) else "",
    }


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """整理單筆購物車項目，確保欄位型別正確。"""
    try:
        dish_id = int(raw.get("id"))
    except (TypeError, ValueError):
        raise ValueError("invalid_item_id") from None

    try:
        qty = int(raw.get("qty", 0))
    except (TypeError, ValueError):
        raise ValueError("invalid_item_quantity") from None
    if qty <= 0:
        raise ValueError("invalid_item_quantity")

    try:
        price = _quantize_money(Decimal(str(raw.get("price", "0"))))
    except Exception as exc:
        raise ValueError("invalid_item_price") from exc
    if price < Decimal("0"):
        raise ValueError("invalid_item_price")

    normalized: Dict[str, Any] = {
        "id": dish_id,
        "name": str(raw.get("name") or ""),
        "qty": qty,
        "price": float(price),
        "size": str(raw["size"]) if raw.get("size") is not None else None,
        "note": str(raw["note"]) if raw.get("note") is not None else None,
        "uuid": str(raw.get("uuid") or uuid.uuid4()),
        "image_url": str(raw["image_url"]) if raw.get("image_url") is not None else None,
    }

    metadata = raw.get("metadata")
    if isinstance(metadata, dict):
        normalized["metadata"] = metadata

    return normalized


def _sanitize_payload_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """整理整份購物車項目，忽略無效項目。"""
    cleaned: List[Dict[str, Any]] = []
    for raw in items:
        try:
            cleaned.append(_normalize_item(raw))
        except ValueError:
            continue
    return cleaned


def get_cart(session: UserSession) -> Dict[str, Any]:
    """讀取 Session 的購物車資料。"""
    snapshot = _get_cart_snapshot(session)
    sanitized_items: List[Dict[str, Any]] = []
    for item in snapshot["items"]:
        try:
            sanitized_items.append(_normalize_item(item))
        except ValueError:
            continue
    return {
        "items": sanitized_items,
        "note": snapshot["note"] or "",
        "version": session.version or 1,
    }


def replace_cart(db: Session, session: UserSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """整體替換購物車內容並寫回 Session。

    使用樂觀鎖定（Optimistic Locking）防止併發更新衝突。
    若提供 expected_version 且與當前版本不符，則拋出 ValueError。
    """
    sanitized_items = _sanitize_payload_items(payload.get("items") or [])
    note_value = payload.get("note")
    note_text = str(note_value) if note_value is not None else ""
    expected_version = payload.get("version")

    # 樂觀鎖定：檢查版本號
    if expected_version is not None:
        current_version = session.version or 1
        if int(expected_version) != current_version:
            raise ValueError("version_conflict")

    data = _get_session_data(session)
    data["cart"] = {"items": sanitized_items, "note": note_text}
    session.data = data

    # 遞增版本號
    session.version = (session.version or 1) + 1

    try:
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise

    return {
        "items": sanitized_items,
        "note": note_text,
        "version": session.version,
    }


def clear_cart(db: Session, session: UserSession) -> None:
    """清空購物車內容。"""
    data = _get_session_data(session)
    data["cart"] = {"items": [], "note": ""}
    session.data = data

    # 遞增版本號
    session.version = (session.version or 1) + 1

    try:
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise


def create_order(
    db: Session,
    session: UserSession,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    note: str | None = None,
) -> Dict[str, Any]:
    """根據購物車建立訂單，並於建立後清空購物車。

    限制：若該 session 已有訂單，則不允許提交空購物車（防止誤操作）。
    """
    cart_snapshot = get_cart(session)
    items = cart_snapshot.get("items", [])

    # 檢查該 session 是否已有訂單
    existing_order_count = db.query(Order).filter(Order.session_id == session.session_id).count()

    if not items:
        # 若購物車為空
        if existing_order_count > 0:
            # 該桌已有訂單，不允許提交空購物車
            raise ValueError("cannot_submit_empty_cart_after_order")
        else:
            # 首次訂單，購物車為空
            raise ValueError("cart_empty")

    # 收集所有 dish_id 並驗證其存在性
    dish_ids = [item.get("id") for item in items if item.get("id") is not None]
    valid_dish_ids = set()
    if dish_ids:
        from sqlalchemy import text
        result = db.execute(
            text("SELECT dish_id FROM dish WHERE dish_id = ANY(:ids)"),
            {"ids": dish_ids}
        )
        valid_dish_ids = {row[0] for row in result}

    total = Decimal("0")
    order_items: List[OrderItem] = []

    for item in items:
        unit_price = _quantize_money(Decimal(str(item["price"])))
        quantity = int(item["qty"])
        line_total = _quantize_money(unit_price * quantity)
        total += line_total

        extra_data = {}
        if item.get("image_url"):
            extra_data["image_url"] = item["image_url"]
        if item.get("metadata"):
            extra_data["extra"] = item["metadata"]
        if item.get("uuid"):
            extra_data["uuid"] = item["uuid"]

        # 只有當 dish_id 存在於資料庫中時才設定，否則設為 None
        dish_id = item.get("id")
        if dish_id is not None and dish_id not in valid_dish_ids:
            dish_id = None

        order_items.append(
            OrderItem(
                dish_id=dish_id,
                name=item.get("name") or "",
                size_label=item.get("size"),
                note=item.get("note"),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                extra_data=extra_data or None,
            )
        )

    total = _quantize_money(total)

    order = Order(
        session_id=session.session_id,
        table_id=session.table_id,  # 複製桌號到訂單
        status=OrderStatus.PENDING.value,  # 明確設定初始狀態
        total_amount=total,
        note=note or cart_snapshot.get("note") or "",
        contact_name=contact_name,
        contact_phone=contact_phone,
        cart_snapshot=cart_snapshot,
    )

    try:
        db.add(order)
        for item in order_items:
            order.items.append(item)

        db.commit()
        db.refresh(order)

        clear_cart(db, session)
    except Exception:
        db.rollback()
        raise

    return {
        "order_id": order.order_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def list_orders(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """列出近期訂單摘要。

    使用 joinedload 預先載入 order.items 以避免 N+1 查詢問題。
    """
    limit = max(1, min(limit, 500))
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))  # 預先載入訂單明細
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )
    results: List[Dict[str, Any]] = []
    for order in orders:
        item_count = sum(item.quantity or 0 for item in order.items)
        results.append(
            {
                "order_id": order.order_id,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "note": order.note,
                "contact_name": order.contact_name,
                "contact_phone": order.contact_phone,
                "session_id": order.session_id,
                "item_count": item_count,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
        )
    return results


def list_session_orders(db: Session, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出當前 Session 的訂單歷史。

    使用 joinedload 預先載入 order.items 以避免 N+1 查詢問題。
    返回訂單摘要及詳細項目列表。
    """
    limit = max(1, min(limit, 200))
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))  # 預先載入訂單明細
        .filter(Order.session_id == session_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )
    results: List[Dict[str, Any]] = []
    for order in orders:
        items = [
            {
                "name": item.name,
                "quantity": item.quantity,
                "size_label": item.size_label,
                "note": item.note,
                "unit_price": float(item.unit_price),
                "line_total": float(item.line_total),
            }
            for item in order.items
        ]
        results.append(
            {
                "order_id": order.order_id,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "note": order.note,
                "items": items,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
        )
    return results


def get_order_detail(db: Session, order_id: int) -> Dict[str, Any]:
    """取得單筆訂單含明細。

    使用 joinedload 預先載入 order.items 以避免 N+1 查詢問題。
    """
    order = (
        db.query(Order)
        .options(joinedload(Order.items))  # 預先載入訂單明細
        .filter(Order.order_id == order_id)
        .first()
    )
    if not order:
        raise ValueError("order_not_found")

    items = [
        {
            "order_item_id": item.order_item_id,
            "dish_id": item.dish_id,
            "name": item.name,
            "size_label": item.size_label,
            "note": item.note,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
            "extra_data": item.extra_data,
        }
        for item in order.items
    ]
    return {
        "order_id": order.order_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "note": order.note,
        "contact_name": order.contact_name,
        "contact_phone": order.contact_phone,
        "session_id": order.session_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "items": items,
    }


def update_order(
    db: Session,
    order_id: int,
    *,
    status: str | None = None,
    note: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    items: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """更新訂單狀態或備註。"""
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("order_not_found")

    if status is not None:
        # 驗證狀態值是否有效
        valid_statuses = {s.value for s in OrderStatus}
        if status not in valid_statuses:
            raise ValueError(f"invalid_status: {status}")
        order.status = status
    if note is not None:
        order.note = note
    if contact_name is not None:
        order.contact_name = contact_name
    if contact_phone is not None:
        order.contact_phone = contact_phone

    if items is not None:
        item_map = {item.order_item_id: item for item in order.items}
        new_payloads: List[Dict[str, Any]] = []

        for payload in items:
            item_id = payload.get("order_item_id")
            if item_id is None:
                new_payloads.append(payload)
                continue

            order_item = item_map.get(item_id)
            if not order_item:
                raise ValueError("order_item_not_found")

            if payload.get("dish_id") is not None:
                order_item.dish_id = payload.get("dish_id")

            if payload.get("name") is not None:
                order_item.name = payload.get("name") or order_item.name

            if payload.get("unit_price") is not None:
                new_price = _quantize_money(_to_decimal(payload.get("unit_price")))
                order_item.unit_price = new_price

            if payload.get("size_label") is not None:
                order_item.size_label = payload.get("size_label")

            if payload.get("note") is not None:
                order_item.note = payload.get("note")

            if payload.get("extra_data") is not None:
                order_item.extra_data = payload.get("extra_data")

            if payload.get("quantity") is not None:
                qty = int(payload.get("quantity") or 0)
                if qty <= 0:
                    order.items.remove(order_item)
                    db.delete(order_item)
                    item_map.pop(item_id, None)
                    continue
                order_item.quantity = qty

        for payload in new_payloads:
            qty = int(payload.get("quantity") or 0)
            if qty <= 0:
                continue
            name = payload.get("name")
            unit_price_val = payload.get("unit_price")
            if name is None or unit_price_val is None:
                raise ValueError("order_item_missing_fields")
            unit_price = _quantize_money(_to_decimal(unit_price_val))
            line_total = _quantize_money(unit_price * qty)
            new_item = OrderItem(
                dish_id=payload.get("dish_id"),
                name=name,
                size_label=payload.get("size_label"),
                note=payload.get("note"),
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                extra_data=payload.get("extra_data"),
            )
            order.items.append(new_item)

        # 重新計算總金額並維護快照
        _recalculate_order_total(order)

    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return get_order_detail(db, order_id)


def list_sessions(db: Session, limit: int = 200) -> List[Dict[str, Any]]:
    """列出 Session 與購物車摘要。

    注意：雖然此函數不涉及關聯表的 N+1 問題，但我們內聯處理購物車資料
    以避免重複調用 get_cart()，提升效能。
    """
    limit = max(1, min(limit, 500))
    rows = (
        db.query(UserSession)
        .order_by(UserSession.updated_at.desc())
        .limit(limit)
        .all()
    )
    results: List[Dict[str, Any]] = []
    for session in rows:
        # 內聯處理購物車資料，避免函數調用開銷
        cart_snapshot = _get_cart_snapshot(session)
        cart_size = sum(int(item.get("qty") or 0) for item in cart_snapshot.get("items", []))

        results.append(
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "cart_size": cart_size,
                "note": cart_snapshot.get("note") or "",
            }
        )
    return results


def get_session_detail(db: Session, session_id: str) -> Dict[str, Any]:
    """取得 Session 詳細與購物車內容。"""
    session = db.get(UserSession, session_id)
    if not session:
        raise ValueError("session_not_found")
    cart = get_cart(session)
    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "cart_items": cart.get("items", []),
        "note": cart.get("note") or "",
    }


def clear_session_cart(db: Session, session_id: str) -> None:
    """清空指定 Session 的購物車。"""
    session = db.get(UserSession, session_id)
    if not session:
        raise ValueError("session_not_found")
    clear_cart(db, session)


def delete_session(db: Session, session_id: str) -> None:
    """刪除 Session。"""
    session = db.get(UserSession, session_id)
    if not session:
        raise ValueError("session_not_found")

    try:
        db.delete(session)
        db.commit()
    except Exception:
        db.rollback()
        raise
