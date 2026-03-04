"""
Order 模組 API：處理前台購物車 Session 以及後台訂單 / Session 管理。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.session import ensure_session
from app.models import OrderStatus
from app.modules.sse import broadcast_to_session
from . import service


router = APIRouter()


class CartItemInput(BaseModel):
    """購物車項目輸入資料"""

    id: int = Field(..., description="菜色 ID")
    name: str = Field(..., description="菜色名稱")
    price: float = Field(..., description="單價")
    qty: int = Field(..., description="數量")
    size: Optional[str] = Field(None, description="份量/尺寸標籤")
    note: Optional[str] = Field(None, description="客製備註")
    image_url: Optional[str] = Field(None, description="圖片 URL")
    uuid: Optional[str] = Field(None, description="前端唯一識別")
    metadata: Optional[Dict[str, Any]] = Field(None, description="額外資訊")


class CartPayload(BaseModel):
    """購物車整體輸入/輸出"""

    items: List[CartItemInput] = Field(default_factory=list, description="購物車項目清單")
    note: Optional[str] = Field(None, description="全域備註")
    version: Optional[int] = Field(None, description="版本號（用於樂觀鎖定）")


class OrderCreatePayload(BaseModel):
    """建立訂單輸入"""

    contact_name: Optional[str] = Field(None, description="聯絡人姓名")
    contact_phone: Optional[str] = Field(None, description="聯絡人電話")
    note: Optional[str] = Field(None, description="訂單備註")


class OrderItemUpdatePayload(BaseModel):
    """後台更新訂單明細輸入"""

    order_item_id: Optional[int] = Field(None, description="訂單明細 ID，新增時可留空")
    dish_id: Optional[int] = Field(None, description="菜色 ID（選填）")
    name: Optional[str] = Field(None, description="品項名稱，新增時必填")
    unit_price: Optional[float] = Field(None, description="單價，新增或更新時填寫")
    quantity: Optional[int] = Field(None, ge=0, description="更新數量，0 代表刪除")
    note: Optional[str] = Field(None, description="明細備註")
    size_label: Optional[str] = Field(None, description="份量/尺寸標籤")


class OrderAdminUpdatePayload(BaseModel):
    """後台更新訂單輸入"""

    status: Optional[Literal["pending", "confirmed", "preparing", "completed", "cancelled", "preorder"]] = Field(
        None,
        description="訂單狀態（僅允許：pending, confirmed, preparing, completed, cancelled, preorder）"
    )
    note: Optional[str] = Field(None, description="訂單備註")
    contact_name: Optional[str] = Field(None, description="聯絡人姓名")
    contact_phone: Optional[str] = Field(None, description="聯絡人電話")
    items: Optional[List[OrderItemUpdatePayload]] = Field(None, description="訂單明細調整")


@router.get("/cart", response_model=CartPayload)
def read_cart(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CartPayload:
    """取得目前 Session 的購物車內容。"""
    session, _ = ensure_session(request, response, db)
    cart = service.get_cart(session)
    return CartPayload(**cart)


@router.put("/cart", response_model=CartPayload)
async def replace_cart_endpoint(
    payload: CartPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CartPayload:
    """整體更新購物車內容。

    支援樂觀鎖定：若提供 version 欄位，系統會檢查版本號是否匹配。
    若版本號不符，回傳 409 Conflict，客戶端應重新載入購物車。

    成功更新後，會透過 SSE 廣播 cart_updated 事件到同桌的其他使用者。
    """
    session, _ = ensure_session(request, response, db)
    try:
        # 取得更新前的購物車內容（用於比較變更）
        old_cart = service.get_cart(session)
        old_items = {item.get("uuid"): item for item in old_cart.get("items", [])}

        # 更新購物車
        updated = service.replace_cart(db, session, payload.model_dump())
        new_items = {item.get("uuid"): item for item in updated.get("items", [])}

        # 偵測新增或數量增加的商品
        added_or_increased = []
        for uuid, new_item in new_items.items():
            if uuid not in old_items:
                # 全新商品
                added_or_increased.append({
                    "name": new_item.get("name"),
                    "qty": new_item.get("qty"),
                    "size": new_item.get("size"),
                    "action": "added"
                })
            else:
                # 數量增加
                old_qty = old_items[uuid].get("qty", 0)
                new_qty = new_item.get("qty", 0)
                if new_qty > old_qty:
                    added_or_increased.append({
                        "name": new_item.get("name"),
                        "qty": new_qty - old_qty,
                        "size": new_item.get("size"),
                        "action": "increased"
                    })

        logger.info(f"購物車已更新 - Session: {session.session_id}, 桌號: {session.table_id}, 商品數: {len(updated.get('items', []))}")

        # 廣播購物車更新事件到同 session 的其他連線
        logger.debug(f"正在廣播 cart_updated 事件到 session {session.session_id}")
        await broadcast_to_session(
            session_id=session.session_id,
            event_type="cart_updated",
            data={
                "cart": updated,
                "updated_by": str(session.session_id),
                "table_id": session.table_id,
                "changes": added_or_increased,  # 新增的商品或數量增加的商品
            },
        )
        logger.debug(f"cart_updated 事件廣播完成")

        return CartPayload(**updated)
    except ValueError as exc:
        if str(exc) == "version_conflict":
            # 廣播版本衝突事件
            await broadcast_to_session(
                session_id=session.session_id,
                event_type="version_conflict",
                data={
                    "message": "購物車已被其他使用者更新",
                    "current_version": session.version,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="version_conflict: Cart was modified by another request. Please reload and retry.",
            ) from exc
        raise


@router.delete("/cart", response_class=Response)
def clear_cart_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """清空購物車。"""
    session, _ = ensure_session(request, response, db)
    service.clear_cart(db, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(
    payload: OrderCreatePayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """根據購物車建立訂單，並清空購物車。

    成功建立訂單後，會透過 SSE 廣播 order_status_updated 事件。
    """
    session, _ = ensure_session(request, response, db)
    try:
        result = service.create_order(
            db,
            session,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            note=payload.note,
        )

        # 廣播訂單建立事件
        await broadcast_to_session(
            session_id=session.session_id,
            event_type="order_status_updated",
            data={
                "order_id": result["order_id"],
                "status": result["status"],
                "action": "created",
                "table_id": session.table_id,
                "total_amount": result["total_amount"],
            },
        )

    except ValueError as exc:
        error_code = str(exc)
        if error_code == "cart_empty":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cart_empty") from exc
        elif error_code == "cannot_submit_empty_cart_after_order":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="cannot_submit_empty_cart_after_order"
            ) from exc
        raise

    return result


@router.get("/orders")
def list_session_orders_endpoint(
    request: Request,
    response: Response,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """列出當前 Session 的訂單歷史。"""
    session, _ = ensure_session(request, response, db)
    return service.list_session_orders(db, session.session_id, limit)


# ------------------------------
# Admin: orders
# ------------------------------


@router.get("/admin/orders")
def admin_list_orders(limit: int = 100, db: Session = Depends(get_db)):
    """列出近期訂單摘要。"""
    return service.list_orders(db, limit)


@router.get("/admin/orders/{order_id}")
def admin_get_order(order_id: int, db: Session = Depends(get_db)):
    """取得單筆訂單詳細。"""
    try:
        return service.get_order_detail(db, order_id)
    except ValueError as exc:
        if str(exc) == "order_not_found":
            raise HTTPException(status_code=404, detail="order_not_found") from exc
        raise


@router.patch("/admin/orders/{order_id}")
async def admin_update_order(order_id: int, payload: OrderAdminUpdatePayload, db: Session = Depends(get_db)):
    """更新訂單狀態或備註。

    成功更新後，會透過 SSE 廣播 order_status_updated 事件到訂單所屬的 session。
    """
    items_payload = None
    if payload.items is not None:
        items_payload = [item.model_dump(exclude_none=True) for item in payload.items]
    try:
        result = service.update_order(
            db,
            order_id,
            status=payload.status,
            note=payload.note,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            items=items_payload,
        )

        # 廣播訂單狀態更新事件（如果訂單有關聯的 session）
        if result.get("session_id"):
            await broadcast_to_session(
                session_id=result["session_id"],
                event_type="order_status_updated",
                data={
                    "order_id": result["order_id"],
                    "status": result["status"],
                    "action": "updated",
                    "table_id": result.get("table_id"),
                },
            )

        return result

    except ValueError as exc:
        error_code = str(exc)
        status_map = {
            "order_not_found": status.HTTP_404_NOT_FOUND,
            "order_item_not_found": status.HTTP_404_NOT_FOUND,
            "order_item_missing_fields": status.HTTP_400_BAD_REQUEST,
        }

        # 處理無效狀態
        if error_code.startswith("invalid_status:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status value. Allowed values: {', '.join([s.value for s in OrderStatus])}"
            ) from exc

        if error_code in status_map:
            raise HTTPException(status_code=status_map[error_code], detail=error_code) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_order_payload") from exc


# ------------------------------
# Admin: sessions
# ------------------------------


@router.get("/admin/sessions")
def admin_list_sessions(limit: int = 200, db: Session = Depends(get_db)):
    """列出使用者 Session 摘要。"""
    return service.list_sessions(db, limit)


@router.get("/admin/sessions/{session_id}")
def admin_get_session(session_id: str, db: Session = Depends(get_db)):
    """取得 Session 詳細與購物車內容。"""
    try:
        return service.get_session_detail(db, session_id)
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found") from exc
        raise


@router.post("/admin/sessions/{session_id}/clear-cart", response_class=Response)
def admin_clear_session_cart(session_id: str, db: Session = Depends(get_db)):
    """清空 Session 的購物車。"""
    try:
        service.clear_session_cart(db, session_id)
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found") from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/admin/sessions/{session_id}", response_class=Response)
def admin_delete_session(session_id: str, db: Session = Depends(get_db)):
    """刪除 Session。"""
    try:
        service.delete_session(db, session_id)
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found") from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
