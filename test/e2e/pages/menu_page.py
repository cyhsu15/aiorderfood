"""
菜單頁面物件

封裝菜單瀏覽相關的 UI 操作。
"""

from playwright.sync_api import Page, Locator, expect
from typing import List, Dict, Optional
from .base_page import BasePage


class MenuPage(BasePage):
    """菜單頁面物件"""

    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

        # 定義頁面元素選擇器
        self.category_tabs = page.locator('[data-testid="category-tab"]')
        self.dish_cards = page.locator('[data-testid="dish-card"]')
        self.dish_name = '[data-testid="dish-name"]'
        self.dish_price = '[data-testid="dish-price"]'
        self.dish_image = '[data-testid="dish-image"]'
        self.add_to_cart_btn = '[data-testid="add-to-cart-btn"]'
        self.cart_badge = '[data-testid="cart-badge"]'
        self.cart_icon = '[data-testid="cart-icon"]'
        self.search_input = '[data-testid="search-input"]'
        self.table_label = '[data-testid="table-label"]'

    def open(self, session_id: Optional[str] = None, table_id: Optional[str] = None):
        """
        開啟菜單頁面

        Args:
            session_id: 共享 session ID (可選)
            table_id: 桌號 (可選)
        """
        params = {}
        if session_id:
            params["sessionid"] = session_id
        if table_id:
            params["tableid"] = table_id

        if params:
            self.navigate_with_params("/", **params)
        else:
            self.navigate("/")

    def wait_for_menu_loaded(self):
        """等待菜單載入完成"""
        # 等待至少一個分類標籤出現
        self.category_tabs.first.wait_for(state="visible", timeout=10000)

    def get_categories(self) -> List[str]:
        """
        獲取所有分類名稱

        Returns:
            分類名稱列表
        """
        return [tab.text_content() for tab in self.category_tabs.all()]

    def select_category(self, category_name: str):
        """
        選擇分類

        Args:
            category_name: 分類名稱
        """
        # 使用 data-testid 精確定位分類按鈕，避免與標題衝突
        category_btn = self.page.locator(f'[data-testid="category-tab"]').filter(has_text=category_name)
        category_btn.click()
        # 等待分類切換動畫完成
        self.page.wait_for_timeout(500)

    def get_dishes_in_category(self) -> List[Dict[str, str]]:
        """
        獲取當前分類的所有菜品

        Returns:
            菜品資訊列表,每個元素包含: name, price, image_url
        """
        dishes = []
        for card in self.dish_cards.all():
            name = card.locator(self.dish_name).text_content()
            price = card.locator(self.dish_price).text_content()
            image = card.locator(self.dish_image).get_attribute("src")
            dishes.append({
                "name": name,
                "price": price,
                "image_url": image
            })
        return dishes

    def search_dish(self, keyword: str):
        """
        搜尋菜品

        Args:
            keyword: 搜尋關鍵字
        """
        self.fill(self.search_input, keyword)
        # 等待搜尋結果更新
        self.page.wait_for_timeout(500)

    def get_dish_card(self, dish_name: str) -> Locator:
        """
        獲取指定菜品的卡片元素

        Args:
            dish_name: 菜品名稱

        Returns:
            菜品卡片的 Locator
        """
        return self.page.locator(f'[data-testid="dish-card"]:has-text("{dish_name}")')

    def add_dish_to_cart(self, dish_name: str, quantity: int = 1):
        """
        將菜品加入購物車

        Args:
            dish_name: 菜品名稱
            quantity: 數量
        """
        # 點擊菜品卡片打開 Modal
        dish_card = self.get_dish_card(dish_name)
        dish_card.click()

        # 等待 Modal 出現
        modal = self.page.locator('[data-testid="dish-detail-modal"]')
        modal.wait_for(state="visible", timeout=5000)

        # 調整數量（如果需要）
        if quantity > 1:
            increase_btn = modal.locator('[data-testid="modal-increase-quantity"]')
            quantity_display = modal.locator('[data-testid="modal-quantity"]')

            for i in range(quantity - 1):
                increase_btn.click()
                # 等待數量顯示更新
                expected_qty = str(i + 2)  # 初始是 1，每次點擊 +1
                self.page.wait_for_function(
                    f"() => document.querySelector('[data-testid=\"modal-quantity\"]')?.textContent?.trim() === '{expected_qty}'",
                    timeout=3000
                )

        # 點擊加入購物車按鈕
        add_btn = modal.locator(self.add_to_cart_btn)
        add_btn.click()

        # 等待 Modal 關閉
        modal.wait_for(state="hidden", timeout=5000)

    def get_cart_item_count(self) -> int:
        """
        獲取購物車商品數量

        Returns:
            購物車中的商品總數
        """
        badge = self.page.locator(self.cart_badge)
        if not badge.is_visible():
            return 0

        count_text = badge.text_content()
        if not count_text:
            return 0

        # 移除可能的 "+" 符號 (例如 "99+")
        count_text = count_text.replace("+", "")
        return int(count_text)

    def open_cart(self):
        """開啟購物車"""
        self.click(self.cart_icon)
        # 等待購物車面板展開
        self.page.wait_for_timeout(500)

    def get_table_label(self) -> Optional[str]:
        """
        獲取桌號標籤

        Returns:
            桌號,如果沒有則返回 None
        """
        label = self.page.locator(self.table_label)
        if not label.is_visible():
            return None
        return label.text_content()

    def wait_for_notification(self, message: str, timeout: int = 5000):
        """
        等待通知訊息出現

        Args:
            message: 通知訊息內容
            timeout: 超時時間 (毫秒)
        """
        notification = self.page.get_by_text(message)
        notification.wait_for(state="visible", timeout=timeout)

    def is_dish_available(self, dish_name: str) -> bool:
        """
        檢查菜品是否可用 (未售罄)

        Args:
            dish_name: 菜品名稱

        Returns:
            菜品是否可用
        """
        dish_card = self.get_dish_card(dish_name)
        sold_out_tag = dish_card.locator('[data-testid="sold-out-tag"]')
        return not sold_out_tag.is_visible()

    def get_dish_details(self, dish_name: str) -> Dict[str, str]:
        """
        獲取菜品詳細資訊

        Args:
            dish_name: 菜品名稱

        Returns:
            包含 name, price, description, image_url 的字典
        """
        dish_card = self.get_dish_card(dish_name)

        return {
            "name": dish_card.locator(self.dish_name).text_content(),
            "price": dish_card.locator(self.dish_price).text_content(),
            "description": dish_card.locator('[data-testid="dish-description"]').text_content(),
            "image_url": dish_card.locator(self.dish_image).get_attribute("src")
        }

    def open_dish_detail(self, dish_name: str):
        """
        開啟菜品詳情

        Args:
            dish_name: 菜品名稱
        """
        dish_card = self.get_dish_card(dish_name)
        dish_card.click()
        # 等待詳情面板展開
        self.page.wait_for_selector('[data-testid="dish-detail-modal"]', timeout=5000)

    def close_dish_detail(self):
        """關閉菜品詳情"""
        close_btn = self.page.locator('[data-testid="close-detail-btn"]')
        close_btn.click()
        # 等待面板關閉
        self.page.wait_for_timeout(500)

    def verify_menu_loaded(self):
        """驗證菜單已正確載入"""
        # 驗證至少有一個分類
        categories = self.page.locator('[data-testid="category-tab"]')
        expect(categories.first).to_be_visible()

        # 驗證至少有一個菜品
        dishes = self.page.locator('[data-testid="dish-card"]')
        expect(dishes.first).to_be_visible()

    def verify_shared_session_active(self, table_id: str):
        """
        驗證共享 Session 已啟用

        Args:
            table_id: 預期的桌號
        """
        # 驗證桌號標籤顯示
        label = self.get_table_label()
        assert label == table_id, f"預期桌號為 {table_id},實際為 {label}"

        # 驗證 localStorage 中有 sessionid
        session_id = self.get_local_storage("cart_session_id")
        assert session_id is not None, "localStorage 中沒有 cart_session_id"
