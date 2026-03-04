"""
Server-Sent Events (SSE) 模組

提供即時訊息推送功能，用於多人共享桌號點餐的購物車同步。
"""

from .router import router
from .service import broadcast_to_session, sse_manager

__all__ = ["router", "broadcast_to_session", "sse_manager"]
