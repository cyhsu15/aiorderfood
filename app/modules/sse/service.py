"""
Server-Sent Events (SSE) 服務：管理即時連線和訊息廣播。

用於多人共享桌號點餐功能，即時同步購物車更新、訂單狀態變更等事件。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict, Set, Any
from collections import defaultdict
from loguru import logger

from app.constants import SSE_BROADCAST_TIMEOUT_SECONDS


class SSEConnectionManager:
    """
    SSE 連線管理器（單例模式）

    管理所有活躍的 SSE 連線，並提供訊息廣播功能。
    連線以 session_id 分組，方便向同一桌的所有使用者廣播訊息。
    """

    def __init__(self):
        # session_id -> Set[asyncio.Queue]
        self._connections: Dict[uuid.UUID, Set[asyncio.Queue]] = defaultdict(set)
        # Queue -> session_id（反向索引，用於快速查找）
        self._queue_to_session: Dict[asyncio.Queue, uuid.UUID] = {}

    def connect(self, session_id: uuid.UUID) -> asyncio.Queue:
        """
        建立新的 SSE 連線。

        參數:
            session_id: Session UUID

        回傳:
            asyncio.Queue: 訊息佇列，用於向客戶端發送事件
        """
        queue = asyncio.Queue()
        self._connections[session_id].add(queue)
        self._queue_to_session[queue] = session_id
        logger.debug(f"SSE connection established for session {session_id}. Total connections: {len(self._queue_to_session)}")
        return queue

    def disconnect(self, queue: asyncio.Queue):
        """
        斷開 SSE 連線並清理資源。

        參數:
            queue: 要移除的訊息佇列
        """
        if queue not in self._queue_to_session:
            return

        session_id = self._queue_to_session[queue]
        self._connections[session_id].discard(queue)
        del self._queue_to_session[queue]

        # 如果該 session 沒有任何連線，清理該 session 的記錄
        if not self._connections[session_id]:
            del self._connections[session_id]

        logger.debug(f"SSE connection closed for session {session_id}. Total connections: {len(self._queue_to_session)}")

    async def broadcast_to_session(
        self,
        session_id: uuid.UUID,
        event_type: str,
        data: Any,
        exclude_queue: asyncio.Queue | None = None,
    ):
        """
        向指定 session 的所有連線廣播訊息。

        參數:
            session_id: Session UUID
            event_type: 事件類型（cart_updated, order_status_updated, version_conflict 等）
            data: 事件資料（將被序列化為 JSON）
            exclude_queue: 要排除的佇列（例如發起變更的客戶端）
        """
        if session_id not in self._connections:
            logger.debug(f"No active connections for session {session_id}")
            return

        message = self._format_sse_message(event_type, data)
        dead_queues = set()

        queues_list = list(self._connections[session_id])
        logger.debug(f"[SSE Broadcast] 📢 Event: {event_type}, Session: {session_id}, Queues: {len(queues_list)}")
        logger.debug(f"[SSE Broadcast] 📋 Message preview: {message[:150]}...")

        sent_count = 0
        excluded_count = 0

        for idx, queue in enumerate(queues_list):
            # 排除指定的佇列（避免發送者收到自己的更新）
            if queue == exclude_queue:
                logger.debug(f"[SSE Broadcast] ⏭️ Queue #{idx} excluded (is sender)")
                excluded_count += 1
                continue

            try:
                # 非阻塞式放入訊息，設置超時避免永久阻塞
                await asyncio.wait_for(queue.put(message), timeout=SSE_BROADCAST_TIMEOUT_SECONDS)
                sent_count += 1
                logger.debug(f"[SSE Broadcast] ✅ Queue #{idx} received message (qsize: {queue.qsize()})")
            except asyncio.TimeoutError:
                logger.warning(f"[SSE Broadcast] ⚠️ Queue #{idx} timeout (client may be slow/disconnected), marking as dead")
                dead_queues.add(queue)
            except Exception as e:
                logger.error(f"[SSE Broadcast] ❌ Queue #{idx} error: {e}")
                dead_queues.add(queue)

        # 清理無法送達的佇列
        for queue in dead_queues:
            self.disconnect(queue)

        logger.debug(f"[SSE Broadcast] 🎯 Summary: {sent_count} sent, {excluded_count} excluded, {len(dead_queues)} failed")

    def _format_sse_message(self, event_type: str, data: Any) -> str:
        """
        格式化為 SSE 協定訊息。

        SSE 格式:
            event: <event_type>
            data: <json_data>
            \n\n

        參數:
            event_type: 事件類型
            data: 事件資料

        回傳:
            格式化的 SSE 訊息字串
        """
        json_data = json.dumps(data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {json_data}\n\n"

    def get_active_sessions(self) -> set[uuid.UUID]:
        """取得所有有活躍連線的 session ID 列表"""
        return set(self._connections.keys())

    def get_connection_count(self, session_id: uuid.UUID | None = None) -> int:
        """
        取得連線數量。

        參數:
            session_id: 若指定，回傳該 session 的連線數；否則回傳總連線數

        回傳:
            連線數量
        """
        if session_id is not None:
            return len(self._connections.get(session_id, set()))
        return len(self._queue_to_session)


# 全域單例實例
sse_manager = SSEConnectionManager()


# 便捷函數，直接使用全域實例
async def broadcast_to_session(
    session_id: uuid.UUID | str,
    event_type: str,
    data: Any,
):
    """
    向指定 session 的所有連線廣播訊息（全域便捷函數）。

    參數:
        session_id: Session UUID（字串或 UUID 物件）
        event_type: 事件類型
        data: 事件資料
    """
    if isinstance(session_id, str):
        session_id = uuid.UUID(session_id)

    await sse_manager.broadcast_to_session(session_id, event_type, data)
