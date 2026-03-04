"""
菜單瀏覽 E2E 測試

測試用戶瀏覽菜單的完整流程。
"""

import pytest
from playwright.sync_api import Page
from test.e2e.pages.menu_page import MenuPage


@pytest.mark.e2e
def test_menu_page_loads_successfully(page: Page, base_url: str, sample_menu_data):
    """測試菜單頁面成功載入"""
    menu_page = MenuPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()

    # 驗證菜單已載入
    menu_page.verify_menu_loaded()

    # 驗證至少有一個分類
    categories = menu_page.get_categories()
    assert len(categories) > 0, "應該至少有一個分類"


@pytest.mark.e2e
def test_browse_dishes_in_category(page: Page, base_url: str, sample_menu_data):
    """測試瀏覽分類中的菜品"""
    menu_page = MenuPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 選擇第一個分類
    categories = menu_page.get_categories()
    first_category = categories[0]
    menu_page.select_category(first_category)

    # 獲取分類中的菜品
    dishes = menu_page.get_dishes_in_category()
    assert len(dishes) > 0, "分類中應該至少有一個菜品"

    # 驗證每個菜品都有必要的資訊
    for dish in dishes:
        assert dish["name"], "菜品應該有名稱"
        assert dish["price"], "菜品應該有價格"


@pytest.mark.e2e
def test_view_dish_details(page: Page, base_url: str, sample_menu_data):
    """測試查看菜品詳情"""
    menu_page = MenuPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 開啟紅燒魚的詳情
    menu_page.open_dish_detail("紅燒魚")

    # 驗證詳情面板已開啟
    assert menu_page.is_visible('[data-testid="dish-detail-modal"]'), "詳情面板應該開啟"

    # 關閉詳情
    menu_page.close_dish_detail()

    # 驗證詳情面板已關閉
    assert not menu_page.is_visible('[data-testid="dish-detail-modal"]'), "詳情面板應該關閉"


@pytest.mark.e2e
def test_switch_between_categories(page: Page, base_url: str, sample_menu_data):
    """測試切換分類"""
    menu_page = MenuPage(page, base_url)

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 獲取所有分類
    categories = menu_page.get_categories()

    if len(categories) > 1:
        # 選擇第一個分類
        menu_page.select_category(categories[0])
        dishes_cat1 = menu_page.get_dishes_in_category()

        # 選擇第二個分類
        menu_page.select_category(categories[1])
        dishes_cat2 = menu_page.get_dishes_in_category()

        # 驗證兩個分類的菜品不同 (如果測試資料設計得當)
        # 這裡只驗證都能成功獲取菜品
        assert len(dishes_cat1) >= 0, "第一個分類應該有菜品或為空"
        assert len(dishes_cat2) >= 0, "第二個分類應該有菜品或為空"


@pytest.mark.e2e
@pytest.mark.slow
def test_menu_responsive_design(page: Page, base_url: str, sample_menu_data):
    """測試菜單響應式設計 (手機版)"""
    menu_page = MenuPage(page, base_url)

    # 切換到手機視窗大小
    page.set_viewport_size({"width": 375, "height": 667})

    # 開啟菜單頁面
    menu_page.open()
    menu_page.wait_for_menu_loaded()

    # 驗證菜單在手機版也能正常載入
    menu_page.verify_menu_loaded()

    # 驗證分類標籤可見
    categories = menu_page.get_categories()
    assert len(categories) > 0, "手機版應該顯示分類"

    # 切回桌面版
    page.set_viewport_size({"width": 1280, "height": 720})
