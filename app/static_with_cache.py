"""
自訂 StaticFiles 中介軟體，加入快取控制標頭
"""
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope, Receive, Send
import os


class CachedStaticFiles(StaticFiles):
    """
    擴充 StaticFiles，為靜態檔案加入快取控制標頭

    快取策略：
    - 圖片檔案 (.jpg, .jpeg, .png, .webp, .gif, .svg): 30 天
    - 字型檔案 (.woff, .woff2, .ttf, .otf): 365 天
    - 其他靜態檔案: 7 天
    """

    def __init__(self, *args, max_age: int = 604800, **kwargs):
        """
        Args:
            max_age: 預設快取時間（秒），預設 7 天
        """
        super().__init__(*args, **kwargs)
        self.default_max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 取得請求路徑
        path = scope.get("path", "")

        # 根據副檔名設定不同的快取時間
        max_age = self._get_cache_max_age(path)

        # 包裝 send 來注入快取標頭
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))

                # 加入快取控制標頭
                headers[b"cache-control"] = f"public, max-age={max_age}".encode()

                # 如果是圖片，加入額外的優化標頭
                if self._is_image(path):
                    # 告訴瀏覽器可以使用過期的快取（stale-while-revalidate）
                    headers[b"cache-control"] = (
                        f"public, max-age={max_age}, stale-while-revalidate=86400".encode()
                    )

                message["headers"] = [(k, v) for k, v in headers.items()]

            await send(message)

        await super().__call__(scope, receive, send_wrapper)

    def _get_cache_max_age(self, path: str) -> int:
        """
        根據檔案類型決定快取時間

        Returns:
            快取時間（秒）
        """
        ext = os.path.splitext(path)[1].lower()

        # 圖片檔案：30 天
        if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico", ".avif"):
            return 2592000  # 30 天

        # 字型檔案：365 天（字型通常不會變更）
        if ext in (".woff", ".woff2", ".ttf", ".otf", ".eot"):
            return 31536000  # 365 天

        # JS/CSS 檔案：如果有 hash，使用長快取；否則短快取
        if ext in (".js", ".css"):
            # 檢查是否有 hash（例如 main.abc123.js）
            filename = os.path.basename(path)
            parts = filename.split(".")
            if len(parts) >= 3:  # name.hash.ext
                return 31536000  # 365 天（有 hash 的檔案可以長時間快取）
            else:
                return 3600  # 1 小時（無 hash 的檔案使用短快取）

        # 其他檔案：使用預設值
        return self.default_max_age

    @staticmethod
    def _is_image(path: str) -> bool:
        """檢查是否為圖片檔案"""
        ext = os.path.splitext(path)[1].lower()
        return ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif")
