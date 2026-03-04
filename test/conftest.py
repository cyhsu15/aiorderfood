"""Pytest shared fixtures for Postgres test DB using Alembic migrations.
Ensures schema is up-to-date and cleans data between tests.
"""

from __future__ import annotations

import os
from typing import List

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

# Ensure project root on sys.path before importing app.*
import sys, pathlib, os as _os
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db import DATABASE_URL
from app.models import Base


load_dotenv()


def _ensure_test_db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or str(DATABASE_URL)
    lowered = url.lower()
    if "ai_order_food_test" not in lowered:
        raise RuntimeError(
            "Refusing to run tests: TEST_DATABASE_URL/DATABASE_URL must point to ai_order_food_test"
        )
    return url


def _alembic_upgrade_head(url: str) -> None:
    # Ensure Alembic env.py picks the test DB URL
    os.environ["DATABASE_URL"] = url
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(cfg, "head")

    # Safety: verify required tables exist; if not, force rebuild (downgrade base -> upgrade head)
    eng = create_engine(url, future=True)
    required = {
        "category",
        "dish",
        "dish_price",
        "dish_translation",
        "set_item",
        "dish_detail",
        "user_session",
        "orders",
        "order_item",
    }
    with eng.connect() as conn:
        existing = set(
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).all()
        )
    missing = required - existing
    if missing:
        # Reset migration history then upgrade again
        alembic_command.downgrade(cfg, "base")
        alembic_command.upgrade(cfg, "head")
    # Ensure any newly added ORM tables are present (belt-and-suspenders for tests)
    eng2 = create_engine(url, future=True)
    with eng2.begin() as conn:
        Base.metadata.create_all(bind=conn)


@pytest.fixture(scope="session")
def pg_engine() -> Engine:
    """Create a session-scoped engine and migrate schema to head via Alembic."""
    url = _ensure_test_db_url()
    _alembic_upgrade_head(url)
    engine = create_engine(url, future=True)
    return engine


def _truncate_all(engine: Engine) -> None:
    """Truncate all user tables and reset identity, keeping alembic_version."""
    with engine.begin() as conn:
        tables: List[str] = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
                    """
                )
            ).all()
        ]
        if not tables:
            return
        joined = ", ".join(f'"{t}"' for t in tables)
        conn.exec_driver_sql(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE;")


@pytest.fixture()
def db_session(pg_engine: Engine) -> Session:
    """Clean data before each test and yield a fresh Session."""
    _truncate_all(pg_engine)
    SessionLocal = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client_with_db(db_session):
    """
    創建使用測試 database session 的 TestClient

    此 fixture 會覆寫 FastAPI 的 get_db 依賴,
    讓 TestClient 使用測試的 db_session 而不是創建新連線。
    這解決了 TestClient 內部創建獨立資料庫連線時缺少密碼的問題。
    """
    from fastapi.testclient import TestClient
    from main import app
    from app.db import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
