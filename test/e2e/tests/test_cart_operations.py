"""
購物車操作 E2E 測試

測試購物車的完整操作流程,包括加入、修改、移除商品。
"""

import pytest
from playwright.sync_api import Page
from test.e2e.pages.menu_page import MenuPage
from test.e2e.pages.cart_page import CartPage


@pytest.mark.e2e
def test_add_dish_to_cart(page: Page, base_url: str, sample_menu_data):
    """測試加入菜品到購物車"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 加入紅燒魚到購物車
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)

    # 驗證購物車徽章顯示數量
    cart_count = menu_page.get_cart_item_count()
    assert cart_count >= 1, "購物車徽章應該顯示至少 1"

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 驗證購物車中有紅燒魚
    items = cart_page.get_cart_items()
    fish_items = [item for item in items if "紅燒魚" in item["name"]]
    assert len(fish_items) == 1, "購物車應該有紅燒魚"
    assert fish_items[0]["quantity"] == 1, "紅燒魚數量應該為 1"


@pytest.mark.e2e
def test_add_multiple_dishes_to_cart(page: Page, base_url: str, sample_menu_data):
    """測試加入多個不同菜品到購物車"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 加入多個菜品
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)
    menu_page.add_dish_to_cart("宮保雞丁", quantity=2)

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 驗證購物車內容
    items = cart_page.get_cart_items()
    assert len(items) == 2, "購物車應該有 2 種菜品"

    # 驗證總數量
    total_quantity = cart_page.get_total_quantity()
    assert total_quantity == 3, "購物車總數量應該為 3 (1+2)"


@pytest.mark.e2e
def test_increase_cart_item_quantity(page: Page, base_url: str, sample_menu_data):
    """測試增加購物車商品數量"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單並加入菜品
    menu_page.open()
    menu_page.wait_for_menu_loaded()
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 增加數量
    cart_page.increase_item_quantity("紅燒魚", times=2)

    # 驗證數量已更新
    quantity = cart_page.get_item_quantity("紅燒魚")
    assert quantity == 3, "紅燒魚數量應該為 3"


@pytest.mark.e2e
def test_decrease_cart_item_quantity(page: Page, base_url: str, sample_menu_data):
    """測試減少購物車商品數量"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單並加入菜品
    menu_page.open()
    menu_page.wait_for_menu_loaded()
    menu_page.add_dish_to_cart("紅燒魚", quantity=3)

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 減少數量
    cart_page.decrease_item_quantity("紅燒魚", times=1)

    # 驗證數量已更新
    quantity = cart_page.get_item_quantity("紅燒魚")
    assert quantity == 2, "紅燒魚數量應該為 2"


@pytest.mark.e2e
def test_remove_item_from_cart(page: Page, base_url: str, sample_menu_data):
    """測試從購物車移除商品"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單並加入菜品
    menu_page.open()
    menu_page.wait_for_menu_loaded()
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)
    menu_page.add_dish_to_cart("宮保雞丁", quantity=1)

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 移除紅燒魚
    cart_page.remove_item("紅燒魚")

    # 驗證紅燒魚已移除
    cart_page.wait_for_item_removed("紅燒魚")
    items = cart_page.get_cart_items()
    assert len(items) == 1, "購物車應該只剩 1 種菜品"
    assert items[0]["name"] == "宮保雞丁", "剩下的應該是宮保雞丁"


@pytest.mark.e2e
def test_cart_total_amount_calculation(page: Page, base_url: str, sample_menu_data):
    """測試購物車總金額計算"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單並加入菜品
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 加入已知價格的菜品
    # 紅燒魚: 280.0, 宮保雞丁: 180.0 (根據 sample_menu_data)
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)  # 280
    menu_page.add_dish_to_cart("宮保雞丁", quantity=2)  # 360

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 驗證總金額
    total = cart_page.get_total_amount()
    expected_total = 280.0 + (180.0 * 2)  # 640.0
    assert total == expected_total, f"總金額應該為 {expected_total},實際為 {total}"


@pytest.mark.e2e
@pytest.mark.slow
def test_cart_checkout_button_enabled_when_not_empty(page: Page, base_url: str, sample_menu_data):
    """測試非空購物車的結帳按鈕可用"""
    menu_page = MenuPage(page, base_url)
    cart_page = CartPage(page, base_url)

    # 開啟菜單並加入菜品
    menu_page.open()
    menu_page.wait_for_menu_loaded()
    menu_page.add_dish_to_cart("紅燒魚", quantity=1)

    # 開啟購物車
    menu_page.open_cart()
    cart_page.wait_for_cart_loaded()

    # 驗證結帳按鈕可用
    assert cart_page.is_checkout_enabled(), "非空購物車的結帳按鈕應該可用"

    # 移除商品清空購物車（因為沒有清空按鈕）
    cart_page.remove_item("紅燒魚")
    cart_page.wait_for_item_removed("紅燒魚")

    # 驗證購物車已空
    assert cart_page.is_empty(), "購物車應該為空"
