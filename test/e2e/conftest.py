"""
E2E 測試的共享 fixtures

提供:
- 自動化伺服器啟動與關閉
- 自動化前端構建
- 瀏覽器與頁面管理
- 測試資料準備
- 資料庫清理
- SSE 連線測試工具
"""

import pytest
import uuid
import logging
from playwright.sync_api import Page, BrowserContext, expect
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from typing import Generator
from pathlib import Path

# 從主專案導入模型
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ⚠️ 重要: 在導入任何配置模組之前加載 .env 文件
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[2]
dotenv_path = PROJECT_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)
    print(f"✓ 已加載環境變數: {dotenv_path}")
else:
    print(f"⚠️  .env 文件不存在: {dotenv_path}")

from app.models import Category, Dish, DishPrice, DishTranslation, DishDetail

# 導入自動化管理器
from .frontend_builder import FrontendBuilder
from .server_manager import ServerManager

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


# ==================== 基礎配置 ====================

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
# PROJECT_ROOT 已在上面定義


# ==================== 自動化 Fixtures ====================

@pytest.fixture(scope="session", autouse=True)
def build_frontend():
    """
    自動構建前端 (session 級別，所有測試開始前執行一次)

    此 fixture 使用 autouse=True，會在任何測試運行前自動執行。
    確保前端資源已構建並準備就緒。
    """
    builder = FrontendBuilder(PROJECT_ROOT)
    builder.build()


@pytest.fixture(scope="session")
def test_server(db_engine):
    """
    啟動測試伺服器 (session 級別，所有測試共用同一伺服器)

    依賴 db_engine fixture 確保資料庫已準備好。
    測試結束後自動關閉伺服器。

    Returns:
        ServerManager 實例
    """
    manager = ServerManager(PROJECT_ROOT)

    # 啟動伺服器
    base_url = manager.start()

    yield manager

    # 測試結束後關閉伺服器
    manager.stop()


# ==================== 資料庫 Fixtures ====================

@pytest.fixture(scope="session")
def db_engine():
    """創建測試資料庫引擎"""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_engine(TEST_DATABASE_URL, future=True)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """提供測試資料庫 session,每個測試後清理"""
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    # 清理所有表格 (測試前)
    _truncate_all_tables(session)

    yield session

    # 清理所有表格 (測試後)
    _truncate_all_tables(session)
    session.close()


def _truncate_all_tables(session: Session):
    """清空所有表格資料 (保留 alembic_version)"""
    tables = [
        "order_item", "orders", "user_session",
        "set_item", "dish_detail", "dish_price", "dish_translation",
        "dish", "category"
    ]
    for table in tables:
        session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
    session.commit()


# ==================== Playwright Fixtures ====================

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    覆寫瀏覽器啟動參數

    如需預設顯示瀏覽器,將 headless 改為 False
    """
    return {
        **browser_type_launch_args,
        # "headless": False,  # 取消註解以預設顯示瀏覽器
        # "slow_mo": 500,     # 取消註解以慢動作執行 (500ms 延遲)
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """覆寫預設的瀏覽器上下文參數"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "locale": "zh-TW",
        "timezone_id": "Asia/Taipei",
    }


@pytest.fixture
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """提供頁面實例"""
    page = context.new_page()

    # 設定預設超時
    page.set_default_timeout(10000)  # 10 秒

    # 監聽 console 訊息 (用於除錯)
    page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))

    # 監聽頁面錯誤
    page.on("pageerror", lambda err: print(f"[Page Error] {err}"))

    yield page

    # 截圖 (如果測試失敗)
    # Playwright 會自動處理,這裡只是範例
    page.close()


@pytest.fixture(scope="session")
def base_url(test_server: ServerManager) -> str:
    """
    提供基礎 URL (session scope 以兼容 pytest-base-url plugin)

    依賴 test_server fixture，確保伺服器已啟動。
    現在會自動返回測試伺服器的 URL。

    Args:
        test_server: 自動啟動的測試伺服器

    Returns:
        測試伺服器的 base URL (e.g., "http://127.0.0.1:8000")
    """
    from .config import config
    return config.get_base_url()


# ==================== 測試資料 Fixtures ====================

@pytest.fixture
def sample_menu_data(db_session: Session):
    """創建測試用的菜單資料"""
    # 創建分類
    category = Category(category_id=1, name_zh="測試分類", name_en="Test Category", sort_order=1)
    db_session.add(category)
    db_session.commit()  # 先提交分類,確保外鍵約束滿足

    # 創建菜品 1: 紅燒魚
    dish1 = Dish(dish_id=1, category_id=1, name_zh="紅燒魚", is_set=False, sort_order=1)
    db_session.add(dish1)
    db_session.commit()  # 提交菜品,確保後續翻譯、價格能引用

    translation1 = DishTranslation(
        dish_id=1, lang="zh-TW", name="紅燒魚"
    )
    db_session.add(translation1)

    price1 = DishPrice(dish_id=1, price_label="小", price=280.0)
    db_session.add(price1)

    detail1 = DishDetail(
        dish_id=1,
        image_url="/images/dish/1.webp",
        description="經典紅燒魚"
    )
    db_session.add(detail1)

    # 創建菜品 2: 宮保雞丁
    dish2 = Dish(dish_id=2, category_id=1, name_zh="宮保雞丁", is_set=False, sort_order=2)
    db_session.add(dish2)
    db_session.commit()  # 提交第二個菜品

    translation2 = DishTranslation(
        dish_id=2, lang="zh-TW", name="宮保雞丁"
    )
    db_session.add(translation2)

    price2 = DishPrice(dish_id=2, price_label="小", price=180.0)
    db_session.add(price2)

    detail2 = DishDetail(
        dish_id=2,
        image_url="/images/dish/2.webp",
        description="經典川菜"
    )
    db_session.add(detail2)

    db_session.commit()  # 最終提交所有關聯資料

    return {
        "category_id": 1,
        "dishes": [
            {"id": 1, "name": "紅燒魚", "price": 280.0},
            {"id": 2, "name": "宮保雞丁", "price": 180.0},
        ]
    }


@pytest.fixture
def shared_session_id() -> str:
    """生成測試用的共享 session ID"""
    return str(uuid.uuid4())


@pytest.fixture
def table_id() -> str:
    """生成測試用的桌號"""
    return "E2E_TEST_TABLE"


# ==================== 頁面操作 Helper ====================

@pytest.fixture
def goto_menu_page(page: Page, base_url: str):
    """導航到菜單頁面"""
    def _goto(session_id: str = None, table_id: str = None):
        url = f"{base_url}/"
        if session_id and table_id:
            url += f"?sessionid={session_id}&tableid={table_id}"
        page.goto(url)
        # 等待頁面載入
        page.wait_for_load_state("networkidle")
        return page
    return _goto


@pytest.fixture
def wait_for_sse_message(page: Page):
    """等待 SSE 訊息"""
    def _wait(event_type: str, timeout: int = 5000):
        """
        等待特定類型的 SSE 事件

        Args:
            event_type: 事件類型 (connected, cart_updated, order_status_updated)
            timeout: 超時時間 (毫秒)
        """
        # 在頁面中注入監聽器
        page.evaluate(f"""
            window._sseEvents = window._sseEvents || [];
            const eventSource = window.eventSource;
            if (eventSource) {{
                eventSource.addEventListener('{event_type}', (e) => {{
                    window._sseEvents.push({{
                        type: '{event_type}',
                        data: JSON.parse(e.data),
                        timestamp: Date.now()
                    }});
                }});
            }}
        """)

        # 等待事件出現
        page.wait_for_function(
            f"() => window._sseEvents && window._sseEvents.some(e => e.type === '{event_type}')",
            timeout=timeout
        )

        # 返回事件資料
        return page.evaluate(
            f"() => window._sseEvents.find(e => e.type === '{event_type}')"
        )

    return _wait


# ==================== 斷言 Helpers ====================

@pytest.fixture
def expect_page():
    """提供 Playwright expect API"""
    return expect


# ==================== 測試標記 ====================

def pytest_configure(config):
    """註冊自訂標記"""
    config.addinivalue_line(
        "markers", "e2e: E2E 測試 (需要運行的應用程式)"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速 E2E 測試"
    )
