"""
QR Code 生成 API 路由
"""

from __future__ import annotations

import os
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from .service import generate_table_qrcode, generate_table_qrcode_image


router = APIRouter()


class QRCodeResponse(BaseModel):
    """QR Code 生成回應"""

    qrcode_base64: str
    url: str
    session_id: str
    table_id: str


@router.get("/admin/qrcode/generate", response_model=QRCodeResponse)
def generate_qrcode_json(
    request: Request,
    tableid: str = Query(..., description="桌號標籤（如 A1, B2）"),
    sessionid: str | None = Query(None, description="Session UUID（可選，未提供則自動生成）"),
):
    """
    生成餐桌 QR Code（JSON 格式）。

    回傳包含 Base64 編碼的 QR Code 圖片、完整 URL、Session ID 和桌號。

    參數:
        tableid: 桌號標籤（如 "A1", "B2"）
        sessionid: Session UUID（可選，未提供則自動生成）

    回傳:
        QRCodeResponse: 包含 QR Code 圖片和相關資訊
    """
    # 從 request 取得 base URL（支援開發和生產環境）
    # 優先使用環境變數 FRONTEND_BASE_URL，否則使用請求的 host
    base_url = os.getenv("FRONTEND_BASE_URL")
    if not base_url:
        # 使用請求的 scheme 和 host
        scheme = request.url.scheme
        host = request.headers.get("host", "localhost:3000")
        base_url = f"{scheme}://{host}"

    result = generate_table_qrcode(
        table_id=tableid,
        base_url=base_url,
        session_id=sessionid,
    )

    return QRCodeResponse(**result)


@router.get("/admin/qrcode/image")
def generate_qrcode_image(
    request: Request,
    tableid: str = Query(..., description="桌號標籤（如 A1, B2）"),
    sessionid: str | None = Query(None, description="Session UUID（可選，未提供則自動生成）"),
):
    """
    生成餐桌 QR Code（PNG 圖片）。

    直接回傳 PNG 圖片，可用於下載或在瀏覽器中直接顯示。

    參數:
        tableid: 桌號標籤
        sessionid: Session UUID（可選）

    回傳:
        PNG 圖片
    """
    # 從 request 取得 base URL
    base_url = os.getenv("FRONTEND_BASE_URL")
    if not base_url:
        scheme = request.url.scheme
        host = request.headers.get("host", "localhost:3000")
        base_url = f"{scheme}://{host}"

    image_data = generate_table_qrcode_image(
        table_id=tableid,
        base_url=base_url,
        session_id=sessionid,
    )

    return Response(
        content=image_data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="table_{tableid}_qrcode.png"',
            "Cache-Control": "no-cache",  # 不快取，因為每次生成的 session_id 可能不同
        },
    )
