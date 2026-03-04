"""
QR Code 生成服務

用於產生餐桌 QR Code，讓多位使用者可以掃描加入同一桌點餐。
"""

from __future__ import annotations

import uuid
import io
import base64
from typing import Dict, Any

import qrcode
from qrcode.image.pil import PilImage

from app.constants import QR_CODE_BOX_SIZE, QR_CODE_BORDER


def generate_table_qrcode(
    table_id: str,
    base_url: str,
    session_id: str | None = None,
) -> Dict[str, Any]:
    """
    生成餐桌 QR Code（JSON 格式）。

    參數:
        table_id: 桌號標籤（如 "A1", "B2"）
        base_url: 前端 base URL（如 "https://example.com" 或 "http://localhost:3000"）
        session_id: Session UUID（若未提供則自動生成）

    回傳:
        Dict 包含：
        - qrcode_base64: Base64 編碼的 PNG 圖片
        - url: 完整的 URL（包含 sessionid 和 tableid 參數）
        - session_id: Session UUID 字串
        - table_id: 桌號標籤
    """
    # 生成或使用提供的 session_id
    if session_id is None:
        session_uuid = uuid.uuid4()
        session_id = str(session_uuid)
    else:
        # 驗證 UUID 格式
        try:
            session_uuid = uuid.UUID(session_id)
            session_id = str(session_uuid)
        except ValueError:
            # 無效的 UUID，生成新的
            session_uuid = uuid.uuid4()
            session_id = str(session_uuid)

    # 移除 base_url 末尾的斜線
    base_url = base_url.rstrip("/")

    # 組合完整 URL
    full_url = f"{base_url}?sessionid={session_id}&tableid={table_id}"

    # 生成 QR Code
    qr = qrcode.QRCode(
        version=1,  # 自動調整大小
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # 中等錯誤修正
        box_size=QR_CODE_BOX_SIZE,
        border=QR_CODE_BORDER,
    )
    qr.add_data(full_url)
    qr.make(fit=True)

    # 生成圖片
    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    # 轉換為 Base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    qrcode_base64 = base64.b64encode(buffer.read()).decode("utf-8")

    return {
        "qrcode_base64": qrcode_base64,
        "url": full_url,
        "session_id": session_id,
        "table_id": table_id,
    }


def generate_table_qrcode_image(
    table_id: str,
    base_url: str,
    session_id: str | None = None,
) -> bytes:
    """
    生成餐桌 QR Code（PNG 圖片二進位資料）。

    參數:
        table_id: 桌號標籤
        base_url: 前端 base URL
        session_id: Session UUID（若未提供則自動生成）

    回傳:
        PNG 圖片的二進位資料
    """
    # 生成或使用提供的 session_id
    if session_id is None:
        session_uuid = uuid.uuid4()
        session_id = str(session_uuid)
    else:
        try:
            session_uuid = uuid.UUID(session_id)
            session_id = str(session_uuid)
        except ValueError:
            session_uuid = uuid.uuid4()
            session_id = str(session_uuid)

    base_url = base_url.rstrip("/")
    full_url = f"{base_url}?sessionid={session_id}&tableid={table_id}"

    # 生成 QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=QR_CODE_BOX_SIZE,
        border=QR_CODE_BORDER,
    )
    qr.add_data(full_url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    # 轉換為二進位
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()
