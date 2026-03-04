"""
基礎頁面物件類別

提供所有頁面物件共用的方法和屬性。
"""

from playwright.sync_api import Page, expect
from typing import Optional
import os


class BasePage:
    """所有頁面物件的基礎類別"""

    def __init__(self, page: Page, base_url: str):
        """
        初始化頁面物件

        Args:
            page: Playwright Page 實例
            base_url: 應用程式基礎 URL
        """
        self.page = page
        self.base_url = base_url

    def navigate(self, path: str = "/"):
        """
        導航到指定路徑

        Args:
            path: URL 路徑 (預設為根路徑)
        """
        url = f"{self.base_url}{path}"
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

    def navigate_with_params(self, path: str = "/", **params):
        """
        導航到指定路徑並帶上 URL 參數

        Args:
            path: URL 路徑
            **params: URL 參數 (例如: sessionid="xxx", tableid="A1")
        """
        url = f"{self.base_url}{path}"
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{query_string}"
        self.page.goto(url)
        # 對於有 SSE 連線的頁面，使用 domcontentloaded 而非 networkidle
        # 因為 SSE 心跳會導致網路永遠不 idle
        if params and "sessionid" in params:
            self.page.wait_for_load_state("domcontentloaded")
        else:
            self.page.wait_for_load_state("networkidle")

    def wait_for_selector(self, selector: str, timeout: int = 10000):
        """
        等待元素出現

        Args:
            selector: CSS 選擇器
            timeout: 超時時間 (毫秒)
        """
        self.page.wait_for_selector(selector, timeout=timeout)

    def wait_for_text(self, text: str, timeout: int = 10000):
        """
        等待指定文字出現

        Args:
            text: 要等待的文字內容
            timeout: 超時時間 (毫秒)
        """
        self.page.get_by_text(text).wait_for(timeout=timeout)

    def click(self, selector: str):
        """
        點擊元素

        Args:
            selector: CSS 選擇器
        """
        self.page.click(selector)

    def fill(self, selector: str, value: str):
        """
        填寫表單欄位

        Args:
            selector: CSS 選擇器
            value: 要填入的值
        """
        self.page.fill(selector, value)

    def get_text(self, selector: str) -> str:
        """
        獲取元素文字內容

        Args:
            selector: CSS 選擇器

        Returns:
            元素的文字內容
        """
        return self.page.text_content(selector) or ""

    def is_visible(self, selector: str) -> bool:
        """
        檢查元素是否可見

        Args:
            selector: CSS 選擇器

        Returns:
            元素是否可見
        """
        return self.page.is_visible(selector)

    def screenshot(self, filename: Optional[str] = None) -> bytes:
        """
        截圖

        Args:
            filename: 檔案名稱 (可選,不提供則返回 bytes)

        Returns:
            截圖的 bytes 資料
        """
        if filename:
            path = os.path.join("test_results", "screenshots", filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return self.page.screenshot(path=path)
        return self.page.screenshot()

    def evaluate(self, script: str):
        """
        在頁面中執行 JavaScript

        Args:
            script: JavaScript 程式碼

        Returns:
            執行結果
        """
        return self.page.evaluate(script)

    def wait_for_api_response(self, url_pattern: str, timeout: int = 10000):
        """
        等待特定 API 請求完成

        Args:
            url_pattern: URL 匹配模式 (支援正則表達式)
            timeout: 超時時間 (毫秒)

        Returns:
            Response 物件
        """
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            return response_info.value

    def get_local_storage(self, key: str) -> Optional[str]:
        """
        獲取 localStorage 的值

        Args:
            key: localStorage 的 key

        Returns:
            對應的值,不存在則返回 None
        """
        return self.evaluate(f"() => localStorage.getItem('{key}')")

    def set_local_storage(self, key: str, value: str):
        """
        設定 localStorage 的值

        Args:
            key: localStorage 的 key
            value: 要設定的值
        """
        self.evaluate(f"() => localStorage.setItem('{key}', '{value}')")

    def clear_local_storage(self):
        """清空 localStorage"""
        self.evaluate("() => localStorage.clear()")

    def get_session_storage(self, key: str) -> Optional[str]:
        """
        獲取 sessionStorage 的值

        Args:
            key: sessionStorage 的 key

        Returns:
            對應的值,不存在則返回 None
        """
        return self.evaluate(f"() => sessionStorage.getItem('{key}')")

    def expect_element(self, selector: str):
        """
        創建元素斷言

        Args:
            selector: CSS 選擇器

        Returns:
            Playwright expect 物件
        """
        return expect(self.page.locator(selector))

    def expect_text(self, text: str):
        """
        創建文字斷言

        Args:
            text: 要斷言的文字

        Returns:
            Playwright expect 物件
        """
        return expect(self.page.get_by_text(text))
