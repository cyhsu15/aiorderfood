"""
購物車頁面物件

封裝購物車相關的 UI 操作。
"""

from playwright.sync_api import Page, Locator
from typing import List, Dict, Optional
from .base_page import BasePage


class CartPage(BasePage):
    """購物車頁面物件"""

    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

        # 定義頁面元素選擇器
        self.cart_panel = '[data-testid="cart-panel"]'
        self.cart_items = '[data-testid="cart-item"]'
        self.cart_item_name = '[data-testid="cart-item-name"]'
        self.cart_item_price = '[data-testid="cart-item-price"]'
        self.cart_item_quantity = '[data-testid="cart-item-quantity"]'
        self.increase_quantity_btn = '[data-testid="increase-quantity-btn"]'
        self.decrease_quantity_btn = '[data-testid="decrease-quantity-btn"]'
        self.remove_item_btn = '[data-testid="remove-item-btn"]'
        self.clear_cart_btn = '[data-testid="clear-cart-btn"]'
        self.checkout_btn = '[data-testid="checkout-btn"]'
        self.total_amount = '[data-testid="total-amount"]'
        self.empty_cart_message = '[data-testid="empty-cart-message"]'
        self.cart_version = '[data-testid="cart-version"]'
        self.conflict_notification = '[data-testid="conflict-notification"]'

    def is_open(self) -> bool:
        """
        檢查購物車面板是否已開啟

        Returns:
            購物車面板是否開啟
        """
        return self.is_visible(self.cart_panel)

    def wait_for_cart_loaded(self):
        """等待購物車載入完成"""
        self.wait_for_selector(self.cart_panel, timeout=10000)

    def get_cart_items(self) -> List[Dict[str, any]]:
        """
        獲取購物車中的所有商品

        Returns:
            商品列表,每個元素包含: name, price, quantity
        """
        items = []
        item_elements = self.page.locator(self.cart_items).all()

        for item in item_elements:
            name = item.locator(self.cart_item_name).text_content()
            price = item.locator(self.cart_item_price).text_content()
            quantity = item.locator(self.cart_item_quantity).text_content()

            items.append({
                "name": name,
                "price": price,
                "quantity": int(quantity)
            })

        return items

    def get_cart_item_count(self) -> int:
        """
        獲取購物車商品種類數量

        Returns:
            購物車中的商品種類數
        """
        return self.page.locator(self.cart_items).count()

    def get_total_quantity(self) -> int:
        """
        獲取購物車商品總數量

        Returns:
            所有商品的數量總和
        """
        items = self.get_cart_items()
        return sum(item["quantity"] for item in items)

    def get_item_by_name(self, item_name: str) -> Locator:
        """
        獲取指定名稱的購物車商品元素

        Args:
            item_name: 商品名稱

        Returns:
            商品元素的 Locator
        """
        return self.page.locator(f'{self.cart_items}:has-text("{item_name}")')

    def increase_item_quantity(self, item_name: str, times: int = 1):
        """
        增加商品數量

        Args:
            item_name: 商品名稱
            times: 增加次數
        """
        item = self.get_item_by_name(item_name)
        increase_btn = item.locator(self.increase_quantity_btn)

        for _ in range(times):
            increase_btn.click()
            # 等待數量更新
            self.page.wait_for_timeout(300)

    def decrease_item_quantity(self, item_name: str, times: int = 1):
        """
        減少商品數量

        Args:
            item_name: 商品名稱
            times: 減少次數
        """
        item = self.get_item_by_name(item_name)
        decrease_btn = item.locator(self.decrease_quantity_btn)

        for _ in range(times):
            decrease_btn.click()
            # 等待數量更新
            self.page.wait_for_timeout(300)

    def remove_item(self, item_name: str):
        """
        移除購物車商品

        Args:
            item_name: 商品名稱
        """
        item = self.get_item_by_name(item_name)
        remove_btn = item.locator(self.remove_item_btn)
        remove_btn.click()
        # 等待移除動畫完成
        self.page.wait_for_timeout(500)

    def clear_cart(self):
        """清空購物車"""
        self.click(self.clear_cart_btn)
        # 等待清空動畫完成
        self.page.wait_for_timeout(500)

    def is_empty(self) -> bool:
        """
        檢查購物車是否為空

        Returns:
            購物車是否為空
        """
        return self.is_visible(self.empty_cart_message)

    def get_total_amount(self) -> float:
        """
        獲取購物車總金額

        Returns:
            總金額
        """
        amount_text = self.get_text(self.total_amount)
        # 移除 "NT$" 和 "," 符號
        amount_text = amount_text.replace("NT$", "").replace(",", "").strip()
        return float(amount_text)

    def checkout(self):
        """
        前往結帳

        會點擊結帳按鈕並等待頁面跳轉
        """
        self.click(self.checkout_btn)
        # 等待導航到結帳頁面
        self.page.wait_for_url("**/checkout", timeout=10000)

    def is_checkout_enabled(self) -> bool:
        """
        檢查結帳按鈕是否可用

        Returns:
            結帳按鈕是否可用
        """
        checkout = self.page.locator(self.checkout_btn)
        return checkout.is_enabled()

    def get_cart_version(self) -> Optional[int]:
        """
        獲取購物車版本號 (用於樂觀鎖)

        Returns:
            版本號,如果沒有則返回 None
        """
        version_element = self.page.locator(self.cart_version)
        if not version_element.is_visible():
            return None

        version_text = version_element.text_content()
        if not version_text:
            return None

        return int(version_text)

    def wait_for_sse_update(self, timeout: int = 5000):
        """
        等待 SSE 更新通知

        Args:
            timeout: 超時時間 (毫秒)
        """
        # 監聽 SSE 事件
        self.page.wait_for_function(
            "() => window._lastSSEUpdate && Date.now() - window._lastSSEUpdate < 1000",
            timeout=timeout
        )

    def has_version_conflict(self) -> bool:
        """
        檢查是否有版本衝突通知

        Returns:
            是否有版本衝突
        """
        return self.is_visible(self.conflict_notification)

    def verify_cart_synced(self, expected_items: List[Dict[str, any]]):
        """
        驗證購物車已同步

        Args:
            expected_items: 預期的商品列表
        """
        actual_items = self.get_cart_items()

        # 驗證商品數量
        assert len(actual_items) == len(expected_items), \
            f"商品數量不符: 預期 {len(expected_items)},實際 {len(actual_items)}"

        # 驗證每個商品
        for expected in expected_items:
            matching = [item for item in actual_items if item["name"] == expected["name"]]
            assert len(matching) == 1, f"找不到商品: {expected['name']}"

            actual = matching[0]
            assert actual["quantity"] == expected["quantity"], \
                f"{expected['name']} 數量不符: 預期 {expected['quantity']},實際 {actual['quantity']}"

    def get_item_quantity(self, item_name: str) -> int:
        """
        獲取指定商品的數量

        Args:
            item_name: 商品名稱

        Returns:
            商品數量,如果不存在則返回 0
        """
        items = self.get_cart_items()
        matching = [item for item in items if item["name"] == item_name]

        if not matching:
            return 0

        return matching[0]["quantity"]

    def wait_for_item_added(self, item_name: str, timeout: int = 5000):
        """
        等待商品加入購物車

        Args:
            item_name: 商品名稱
            timeout: 超時時間 (毫秒)
        """
        item = self.get_item_by_name(item_name)
        item.wait_for(state="visible", timeout=timeout)

    def wait_for_item_removed(self, item_name: str, timeout: int = 5000):
        """
        等待商品從購物車移除

        Args:
            item_name: 商品名稱
            timeout: 超時時間 (毫秒)
        """
        item = self.get_item_by_name(item_name)
        item.wait_for(state="hidden", timeout=timeout)

    def close(self):
        """關閉購物車面板"""
        # 點擊面板外的區域或關閉按鈕
        close_btn = self.page.locator('[data-testid="close-cart-btn"]')
        if close_btn.is_visible():
            close_btn.click()
        else:
            # 點擊遮罩層
            overlay = self.page.locator('[data-testid="cart-overlay"]')
            overlay.click()

        # 等待面板關閉
        self.page.wait_for_timeout(500)
