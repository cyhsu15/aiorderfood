"""
E2E 測試的 Page Object Model

提供頁面物件以封裝 UI 操作邏輯,提高測試可維護性。
"""

from .base_page import BasePage
from .menu_page import MenuPage
from .cart_page import CartPage

__all__ = ["BasePage", "MenuPage", "CartPage"]
