"""
同步 SQLAlchemy 最小連線設定與 FastAPI 依賴注入。

此模組提供：
- 全域 `engine` 與 `SessionLocal`（使用 QueuePool）
- FastAPI 依賴 `get_db()`：每請求一個資料庫 Session

環境變數優先順序：
1) `DATABASE_URL`（例如：postgresql+psycopg2://user:pass@host:5432/dbname）
2) 由 `DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_NAME` 組成

可調參數（選填）：
- `DB_POOL_SIZE`（預設 5）
- `DB_MAX_OVERFLOW`（預設 5）
- `DB_POOL_RECYCLE`（秒，預設 1800）
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def _build_database_url() -> str:
    """依據環境變數取得連線字串。

    優先使用 `DATABASE_URL`；若不存在則由 `DB_*` 組合。
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "postgres")
    # 預設使用 psycopg2 同步驅動
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


DATABASE_URL: str = _build_database_url()

# 連線池設定（QueuePool）
pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))


# 全域 Engine（請勿於每請求重建）
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=pool_size,
    max_overflow=max_overflow,
    pool_recycle=pool_recycle,
    future=True,
)

# 每請求 Session 工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依賴注入：產生並釋放一個資料庫 Session。

    範例：
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.db import get_db

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            rows = db.execute(text("SELECT 1")).all()
            return rows
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

