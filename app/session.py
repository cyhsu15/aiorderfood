"""
Session 管理協助函式：負責為未登入使用者建立伺服端 Session
並在回應中寫入對應的 Cookie，後端以資料庫維護 Session 狀態。
"""

from __future__ import annotations

import os
import uuid
from typing import Tuple

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.models import UserSession

CART_SESSION_COOKIE_NAME = os.getenv("CART_SESSION_COOKIE_NAME", "cart_session_id")
CART_SESSION_COOKIE_MAX_AGE = int(os.getenv("CART_SESSION_COOKIE_MAX_AGE", str(21600))) # 3Hr
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"


def ensure_session(request: Request, response: Response, db: Session) -> Tuple[UserSession, bool]:
    """
    取得或建立使用者 Session。

    支援多人共享桌號點餐：
    - 若 URL 包含 ?sessionid={GUID} 參數，則使用該 session（若不存在則創建）
    - 若 URL 包含 ?tableid={桌號} 參數，則設定到 session.table_id

    參數:
        request: 當前 FastAPI Request
        response: 當前 Response，用於寫入 Cookie
        db: SQLAlchemy Session

    回傳:
        (session, created) -> created 為 True 代表新建 Session
    """
    session: UserSession | None = None
    created = False
    need_cookie = False

    # 優先從 query parameter 取得 sessionid（用於 QR Code 掃描場景）
    query_session_id = request.query_params.get("sessionid")
    query_table_id = request.query_params.get("tableid")

    if query_session_id:
        # 使用 URL 提供的 sessionid
        try:
            session_uuid = uuid.UUID(query_session_id)
            session = db.get(UserSession, session_uuid)

            if session is None:
                # Session 不存在，創建新的（使用 URL 提供的 UUID）
                session = UserSession(
                    session_id=session_uuid,
                    table_id=query_table_id,  # 同時設定桌號
                    data={},
                    version=1
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                created = True
            elif query_table_id and session.table_id != query_table_id:
                # Session 已存在但桌號不同，更新桌號
                session.table_id = query_table_id
                db.commit()
                db.refresh(session)

            # 使用 query parameter 時，需要設定 cookie 讓後續請求可以使用
            need_cookie = True

        except ValueError:
            # 無效的 UUID 格式，忽略並使用原有邏輯
            pass

    # 若未從 query parameter 取得，則從 cookie 取得
    if session is None:
        cookie_session_id = request.cookies.get(CART_SESSION_COOKIE_NAME)
        if cookie_session_id:
            session = db.get(UserSession, cookie_session_id)

    # 若仍未取得 session，創建新的
    if session is None:
        session = UserSession(
            session_id=str(uuid.uuid4()),
            table_id=query_table_id,  # 若有提供桌號則設定
            data={},
            version=1
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        created = True
        need_cookie = True

    # 設定 cookie（新建 session 或從 query parameter 取得時）
    if need_cookie or created:
        secure_flag = COOKIE_SECURE and request.url.scheme == "https"
        samesite = COOKIE_SAMESITE if secure_flag else "lax"
        response.set_cookie(
            key=CART_SESSION_COOKIE_NAME,
            value=str(session.session_id), # UUID
            httponly=True,
            secure=secure_flag,
            samesite=samesite,
            max_age=CART_SESSION_COOKIE_MAX_AGE,
            path="/",
        )

    return session, created
