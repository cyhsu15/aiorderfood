"""
SSE (Server-Sent Events) API 路由
"""

from __future__ import annotations

import asyncio
import time
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.constants import SSE_KEEPALIVE_TIMEOUT_SECONDS
from .service import sse_manager


router = APIRouter()


@router.get("/sse/cart/{session_id}")
async def cart_sse_endpoint(session_id: str, request: Request):
    """
    建立 SSE 連線以接收購物車和訂單相關的即時更新。

    事件類型：
    - cart_updated: 購物車內容變更
    - order_status_updated: 訂單狀態更新
    - version_conflict: 版本衝突通知

    參數:
        session_id: Session UUID 字串

    回傳:
        StreamingResponse: SSE 串流
    """
    # 驗證 session_id 格式
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        return {"error": "Invalid session_id format"}

    # 建立連線
    queue = sse_manager.connect(session_uuid)

    async def event_stream():
        """
        事件串流生成器。

        生成 SSE 格式的訊息串流，並在客戶端斷線時清理資源。
        """
        try:
            # 發送初始連線成功訊息
            logger.info(f"[SSE] 🔌 Client connected: session {session_id}")
            yield "event: connected\ndata: {\"status\": \"ok\"}\n\n"

            # 持續發送事件
            message_count = 0
            keepalive_count = 0

            while True:
                try:
                    # 等待訊息（timeout 用於定期發送心跳）
                    message = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_TIMEOUT_SECONDS)
                    message_count += 1

                    logger.info(f"[SSE] 📤 Message #{message_count} to session {session_id}")
                    logger.debug(f"[SSE] 📋 Content: {message[:150]}...")

                    # 立即 yield 訊息
                    yield message

                    logger.info(f"[SSE] ✅ Message #{message_count} sent successfully")

                except asyncio.TimeoutError:
                    # 每 10 秒發送心跳訊號（保持連線活躍）
                    keepalive_count += 1
                    keepalive_msg = f"event: keepalive\ndata: {{\"timestamp\": {time.time()}}}\n\n"

                    # 只在前 3 次心跳時記錄
                    if keepalive_count <= 3:
                        logger.debug(f"[SSE] 💓 Keepalive #{keepalive_count} to session {session_id}")

                    yield keepalive_msg

        except GeneratorExit:
            # 客戶端主動斷線（正常情況）
            logger.info(f"[SSE] 👋 Client disconnected (GeneratorExit): session {session_id}, sent {message_count} messages")
        except asyncio.CancelledError:
            logger.info(f"[SSE] ⚠️ Stream cancelled: session {session_id}")
        except Exception as e:
            logger.error(f"[SSE] ❌ Error in stream: session {session_id}, error: {e}", exc_info=True)
        finally:
            # 清理連線
            sse_manager.disconnect(queue)
            logger.info(f"[SSE] 🧹 Cleanup completed: session {session_id}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 緩衝
        },
    )


@router.get("/sse/debug/connections")
async def debug_connections():
    """
    除錯端點：查看當前所有活躍的 SSE 連線。

    回傳:
        Dict: 包含活躍 session 列表和總連線數
    """
    active_sessions = sse_manager.get_active_sessions()
    session_details = {
        str(session_id): sse_manager.get_connection_count(session_id)
        for session_id in active_sessions
    }

    return {
        "total_connections": sse_manager.get_connection_count(),
        "active_sessions": len(active_sessions),
        "session_details": session_details,
    }


@router.post("/sse/debug/broadcast/{session_id}")
async def debug_broadcast(session_id: str):
    """
    除錯端點：手動向指定 session 發送測試廣播。

    用途：測試 SSE 廣播機制是否正常工作。
    """
    from .service import broadcast_to_session
    import uuid

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        return {"error": "Invalid session_id format"}

    # 檢查連線數
    conn_count = sse_manager.get_connection_count(session_uuid)
    if conn_count == 0:
        return {
            "error": "No active connections for this session",
            "session_id": session_id,
            "connections": 0
        }

    # 發送測試廣播
    logger.debug(f"[DEBUG Broadcast] Manually triggering test broadcast to session {session_id}")

    await broadcast_to_session(
        session_id=session_uuid,
        event_type="cart_updated",
        data={
            "cart": {
                "items": [
                    {
                        "id": 999,
                        "name": "🧪 測試商品 (手動廣播)",
                        "qty": 1,
                        "price": 99.0,
                        "size": None,
                        "note": "",
                        "uuid": "test-manual-broadcast",
                        "image_url": ""
                    }
                ],
                "note": "這是一個測試廣播",
                "version": 999
            },
            "updated_by": session_id,
            "table_id": "DEBUG",
            "changes": [
                {
                    "name": "🧪 測試商品",
                    "qty": 1,
                    "size": None,
                    "action": "added"
                }
            ]
        }
    )

    logger.debug(f"[DEBUG Broadcast] Test broadcast sent to session {session_id}")

    return {
        "success": True,
        "session_id": session_id,
        "connections": conn_count,
        "message": f"Test broadcast sent to {conn_count} connection(s)"
    }
