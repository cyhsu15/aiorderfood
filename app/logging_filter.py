"""
自訂日誌過濾器
過濾特定路徑的 404 錯誤日誌（如圖片載入失敗）
"""
import logging
import re


class ImageNotFoundFilter(logging.Filter):
    """
    過濾圖片路徑的 404 錯誤日誌

    會過濾以下路徑的 404 錯誤：
    - /images/
    - /static/images/
    - 圖片副檔名：.jpg, .jpeg, .png, .webp, .gif, .svg
    """

    def __init__(self, name: str = ""):
        super().__init__(name)
        # 圖片路徑模式
        self.image_patterns = [
            r'/images/',
            r'/static/images/',
            r'\.(jpg|jpeg|png|webp|gif|svg|ico|avif)',
        ]
        # 編譯正則表達式以提高效能
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.image_patterns]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        判斷是否應該記錄此日誌

        Returns:
            True: 記錄此日誌
            False: 過濾掉此日誌（不記錄）
        """
        # 取得日誌訊息
        message = record.getMessage()

        # 檢查是否為 404 錯誤
        if '404' not in message:
            return True  # 不是 404，正常記錄

        # 檢查是否為圖片路徑
        for pattern in self.compiled_patterns:
            if pattern.search(message):
                # 是圖片的 404 錯誤，過濾掉
                return False

        # 其他 404 錯誤，正常記錄
        return True


class StaticFileFilter(logging.Filter):
    """
    過濾所有靜態檔案的存取日誌（包含成功的請求）

    適用於生產環境，減少日誌量
    """

    def __init__(self, name: str = "", include_404: bool = True):
        """
        Args:
            include_404: 是否記錄 404 錯誤（預設 True）
        """
        super().__init__(name)
        self.include_404 = include_404
        # 靜態檔案路徑模式
        self.static_patterns = [
            r'/images/',
            r'/static/',
            r'/assets/',
            r'/favicon\.ico',
            r'\.(js|css|jpg|jpeg|png|webp|gif|svg|ico|avif|woff|woff2|ttf|otf)(\s|$)',
        ]
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.static_patterns]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        # 檢查是否為靜態檔案請求
        is_static = any(pattern.search(message) for pattern in self.compiled_patterns)

        if not is_static:
            return True  # 不是靜態檔案，正常記錄

        # 如果是靜態檔案
        if self.include_404 and '404' in message:
            return True  # 記錄 404 錯誤

        # 過濾掉成功的靜態檔案請求
        return False
