"""
SSE (Server-Sent Events) 功能測試

測試範圍:
1. SSE 連線管理 (SSEConnectionManager)
2. SSE 訊息格式化
3. SSE 廣播功能
4. SSE API 端點
5. 多客戶端同步場景
"""

from __future__ import annotations

import asyncio
import uuid
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

# 測試 SSE 連線管理器
from app.modules.sse.service import SSEConnectionManager, broadcast_to_session


# ==================== 單元測試: SSEConnectionManager ====================

class TestSSEConnectionManager:
    """測試 SSE 連線管理器的核心功能"""

    @pytest.fixture
    def manager(self):
        """提供乾淨的 SSEConnectionManager 實例"""
        mgr = SSEConnectionManager()
        yield mgr
        # 清理所有連線
        mgr._connections.clear()
        mgr._queue_to_session.clear()

    @pytest.fixture
    def session_id(self):
        """提供測試用的 session UUID"""
        return uuid.uuid4()

    def test_connect_creates_queue(self, manager, session_id):
        """測試 connect() 方法創建新的訊息佇列"""
        queue = manager.connect(session_id)

        assert isinstance(queue, asyncio.Queue)
        assert session_id in manager._connections
        assert queue in manager._connections[session_id]
        assert manager._queue_to_session[queue] == session_id
        assert manager.get_connection_count(session_id) == 1

    def test_connect_multiple_clients_same_session(self, manager, session_id):
        """測試同一 session 的多個客戶端連線"""
        queue1 = manager.connect(session_id)
        queue2 = manager.connect(session_id)
        queue3 = manager.connect(session_id)

        assert manager.get_connection_count(session_id) == 3
        assert len(manager._connections[session_id]) == 3
        assert queue1 != queue2 != queue3

    def test_disconnect_removes_queue(self, manager, session_id):
        """測試 disconnect() 方法正確移除連線"""
        queue = manager.connect(session_id)
        assert manager.get_connection_count(session_id) == 1

        manager.disconnect(queue)

        assert manager.get_connection_count(session_id) == 0
        assert session_id not in manager._connections
        assert queue not in manager._queue_to_session

    def test_disconnect_one_of_multiple(self, manager, session_id):
        """測試在多個連線中斷開其中一個"""
        queue1 = manager.connect(session_id)
        queue2 = manager.connect(session_id)

        manager.disconnect(queue1)

        assert manager.get_connection_count(session_id) == 1
        assert queue2 in manager._connections[session_id]
        assert queue1 not in manager._connections[session_id]

    def test_disconnect_nonexistent_queue(self, manager):
        """測試斷開不存在的連線不會拋出錯誤"""
        fake_queue = asyncio.Queue()
        manager.disconnect(fake_queue)  # 應該不會拋出異常

    def test_get_active_sessions(self, manager):
        """測試取得所有活躍 session 列表"""
        session1 = uuid.uuid4()
        session2 = uuid.uuid4()
        session3 = uuid.uuid4()

        manager.connect(session1)
        manager.connect(session2)
        manager.connect(session3)

        active_sessions = manager.get_active_sessions()

        assert len(active_sessions) == 3
        assert session1 in active_sessions
        assert session2 in active_sessions
        assert session3 in active_sessions

    def test_get_connection_count_total(self, manager):
        """測試取得總連線數"""
        session1 = uuid.uuid4()
        session2 = uuid.uuid4()

        manager.connect(session1)
        manager.connect(session1)
        manager.connect(session2)

        assert manager.get_connection_count() == 3

    def test_format_sse_message(self, manager):
        """測試 SSE 訊息格式化"""
        event_type = "cart_updated"
        data = {"test": "data", "number": 123}

        message = manager._format_sse_message(event_type, data)

        # 驗證格式: event: {type}\ndata: {json}\n\n
        assert message.startswith(f"event: {event_type}\n")
        assert "data: " in message
        assert message.endswith("\n\n")

        # 驗證 JSON 可以解析
        lines = message.strip().split("\n")
        data_line = lines[1]
        json_str = data_line.replace("data: ", "")
        parsed_data = json.loads(json_str)

        assert parsed_data == data
