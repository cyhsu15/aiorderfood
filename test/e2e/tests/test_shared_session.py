"""
共享 Session E2E 測試

測試多用戶共享桌號訂餐的完整流程,包括 SSE 即時同步。
"""

import pytest
import uuid
from playwright.sync_api import Page, BrowserContext
from test.e2e.pages.menu_page import MenuPage
from test.e2e.pages.cart_page import CartPage


@pytest.mark.e2e
def test_shared_session_initialization(page: Page, base_url: str, sample_menu_data, shared_session_id: str, table_id: str):
    """測試共享 Session 初始化"""
    menu_page = MenuPage(page, base_url)

    # 使用 sessionid 和 tableid 參數開啟頁面
    menu_page.open(session_id=shared_session_id, table_id=table_id)
    menu_page.wait_for_menu_loaded()

    # 驗證共享 Session 已啟用（透過 localStorage 檢查）
    session_id = page.evaluate("() => localStorage.getItem('shared_session_id')")
    table_id_stored = page.evaluate("() => localStorage.getItem('shared_table_id')")

    assert session_id == shared_session_id, f"Session ID 應該是 {shared_session_id}"
    assert table_id_stored == table_id, f"Table ID 應該是 {table_id}"


@pytest.mark.e2e
@pytest.mark.slow
def test_cart_sync_between_two_users(context: BrowserContext, base_url: str, sample_menu_data, shared_session_id: str, table_id: str):
    """測試兩個用戶之間的購物車同步"""
    # 創建兩個用戶的頁面
    user1_page = context.new_page()
    user2_page = context.new_page()

    user1_menu = MenuPage(user1_page, base_url)
    user2_menu = MenuPage(user2_page, base_url)

    user1_cart = CartPage(user1_page, base_url)
    user2_cart = CartPage(user2_page, base_url)

    try:
        # 兩個用戶都開啟相同的共享 Session
        user1_menu.open(session_id=shared_session_id, table_id=table_id)
        user1_menu.wait_for_menu_loaded()

        user2_menu.open(session_id=shared_session_id, table_id=table_id)
        user2_menu.wait_for_menu_loaded()

        # User 1 加入菜品到購物車
        user1_menu.add_dish_to_cart("紅燒魚", quantity=1)

        # 等待 SSE 同步
        user2_page.wait_for_timeout(1000)

        # 驗證 User 2 的購物車徽章更新
        user2_cart_count = user2_menu.get_cart_item_count()
        assert user2_cart_count >= 1, "User 2 應該看到購物車更新"

        # User 2 開啟購物車驗證內容
        user2_menu.open_cart()
        user2_cart.wait_for_cart_loaded()

        items = user2_cart.get_cart_items()
        fish_items = [item for item in items if "紅燒魚" in item["name"]]
        assert len(fish_items) == 1, "User 2 的購物車應該有紅燒魚"
        assert fish_items[0]["quantity"] == 1, "紅燒魚數量應該為 1"

    finally:
        user1_page.close()
        user2_page.close()


@pytest.mark.e2e
@pytest.mark.slow
def test_cart_update_broadcasts_to_all_users(context: BrowserContext, base_url: str, sample_menu_data, shared_session_id: str, table_id: str):
    """測試購物車更新廣播到所有用戶"""
    # 創建三個用戶的頁面
    users = []
    for i in range(3):
        page = context.new_page()
        menu = MenuPage(page, base_url)
        cart = CartPage(page, base_url)
        users.append({"page": page, "menu": menu, "cart": cart})

    try:
        # 所有用戶開啟相同的共享 Session
        for user in users:
            user["menu"].open(session_id=shared_session_id, table_id=table_id)
            user["menu"].wait_for_menu_loaded()

        # User 0 加入菜品
        users[0]["menu"].add_dish_to_cart("紅燒魚", quantity=2)

        # 等待 SSE 廣播
        users[0]["page"].wait_for_timeout(1000)

        # 驗證所有用戶都收到更新
        for i, user in enumerate(users):
            cart_count = user["menu"].get_cart_item_count()
            assert cart_count >= 2, f"User {i} 應該看到購物車有 2 個商品"

        # User 1 修改數量
        users[1]["menu"].open_cart()
        users[1]["cart"].wait_for_cart_loaded()
        users[1]["cart"].increase_item_quantity("紅燒魚", times=1)

        # 等待 SSE 廣播
        users[1]["page"].wait_for_timeout(1000)

        # 驗證其他用戶看到更新
        for i in [0, 2]:
            users[i]["menu"].open_cart()
            users[i]["cart"].wait_for_cart_loaded()
            quantity = users[i]["cart"].get_item_quantity("紅燒魚")
            assert quantity == 3, f"User {i} 應該看到紅燒魚數量為 3"

    finally:
        for user in users:
            user["page"].close()


@pytest.mark.e2e
@pytest.mark.slow
def test_optimistic_locking_prevents_conflicts(context: BrowserContext, base_url: str, sample_menu_data, shared_session_id: str, table_id: str):
    """測試樂觀鎖防止版本衝突"""
    # 創建兩個用戶的頁面
    user1_page = context.new_page()
    user2_page = context.new_page()

    user1_menu = MenuPage(user1_page, base_url)
    user2_menu = MenuPage(user2_page, base_url)

    user1_cart = CartPage(user1_page, base_url)
    user2_cart = CartPage(user2_page, base_url)

    try:
        # 兩個用戶開啟相同的共享 Session
        user1_menu.open(session_id=shared_session_id, table_id=table_id)
        user1_menu.wait_for_menu_loaded()

        user2_menu.open(session_id=shared_session_id, table_id=table_id)
        user2_menu.wait_for_menu_loaded()

        # User 1 加入菜品
        user1_menu.add_dish_to_cart("紅燒魚", quantity=1)
        user1_page.wait_for_timeout(500)

        # 獲取當前版本號
        user1_menu.open_cart()
        user1_cart.wait_for_cart_loaded()
        version_1 = user1_cart.get_cart_version()

        # User 2 也修改購物車 (模擬同時操作)
        user2_menu.add_dish_to_cart("宮保雞丁", quantity=1)
        user2_page.wait_for_timeout(500)

        # 獲取 User 2 的版本號
        user2_menu.open_cart()
        user2_cart.wait_for_cart_loaded()
        version_2 = user2_cart.get_cart_version()

        # 驗證版本號遞增
        if version_1 is not None and version_2 is not None:
            assert version_2 > version_1, "版本號應該遞增"

        # 驗證兩個用戶最終看到相同的購物車內容
        user1_items = user1_cart.get_cart_items()
        user2_items = user2_cart.get_cart_items()

        assert len(user1_items) == len(user2_items), "兩個用戶應該看到相同數量的商品"

    finally:
        user1_page.close()
        user2_page.close()


@pytest.mark.e2e
def test_different_tables_have_separate_carts(context: BrowserContext, base_url: str, sample_menu_data):
    """測試不同桌號有獨立的購物車"""
    # 創建兩個不同桌號的 Session
    table_a_session = str(uuid.uuid4())
    table_b_session = str(uuid.uuid4())

    page_a = context.new_page()
    page_b = context.new_page()

    menu_a = MenuPage(page_a, base_url)
    menu_b = MenuPage(page_b, base_url)

    cart_a = CartPage(page_a, base_url)
    cart_b = CartPage(page_b, base_url)

    try:
        # 開啟不同桌號的頁面
        menu_a.open(session_id=table_a_session, table_id="A1")
        menu_a.wait_for_menu_loaded()

        menu_b.open(session_id=table_b_session, table_id="B1")
        menu_b.wait_for_menu_loaded()

        # Table A 加入菜品
        menu_a.add_dish_to_cart("紅燒魚", quantity=1)
        page_a.wait_for_timeout(500)

        # Table B 加入不同菜品
        menu_b.add_dish_to_cart("宮保雞丁", quantity=2)
        page_b.wait_for_timeout(500)

        # 驗證 Table A 的購物車
        menu_a.open_cart()
        cart_a.wait_for_cart_loaded()
        items_a = cart_a.get_cart_items()

        assert len(items_a) == 1, "Table A 應該只有 1 種菜品"
        assert any("紅燒魚" in item["name"] for item in items_a), "Table A 應該有紅燒魚"

        # 驗證 Table B 的購物車
        menu_b.open_cart()
        cart_b.wait_for_cart_loaded()
        items_b = cart_b.get_cart_items()

        assert len(items_b) == 1, "Table B 應該只有 1 種菜品"
        assert any("宮保雞丁" in item["name"] for item in items_b), "Table B 應該有宮保雞丁"

    finally:
        page_a.close()
        page_b.close()
