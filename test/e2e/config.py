"""
E2E 測試配置模組

此模組集中管理 E2E 測試的所有配置參數，包括伺服器設定、
健康檢查參數、前端構建選項等。
"""
import os
from typing import Optional


class E2EConfig:
    """E2E 測試配置類別"""

    # 伺服器配置
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8088
    SERVER_STARTUP_TIMEOUT: int = 30  # 秒
    SERVER_SHUTDOWN_TIMEOUT: int = 5  # 秒

    # Health Check 配置
    HEALTH_CHECK_ENDPOINT: str = "/api/menu"
    HEALTH_CHECK_INTERVAL: float = 0.5  # 秒
    HEALTH_CHECK_MAX_RETRIES: int = 60  # 最多重試次數（30秒總共）

    # 前端構建配置
    FRONTEND_DIR: str = "static"
    FRONTEND_DIST_DIR: str = "static/dist"
    FRONTEND_BUILD_TIMEOUT: int = 120  # 秒
    SKIP_FRONTEND_BUILD: bool = False  # 設為 True 可跳過前端構建（加速開發）

    # 日誌配置
    LOG_LEVEL: str = "INFO"
    CAPTURE_SERVER_LOGS: bool = True
    SERVER_LOG_FILE: Optional[str] = None  # None 表示使用臨時檔案

    @staticmethod
    def get_test_database_url() -> Optional[str]:
        """動態讀取測試資料庫 URL（確保讀取最新的環境變數）"""
        return os.getenv("TEST_DATABASE_URL")

    @classmethod
    def get_base_url(cls) -> str:
        """返回測試伺服器的完整 URL"""
        return f"http://{cls.SERVER_HOST}:{cls.SERVER_PORT}"

    @classmethod
    def get_health_check_url(cls) -> str:
        """返回健康檢查的完整 URL"""
        return f"{cls.get_base_url()}{cls.HEALTH_CHECK_ENDPOINT}"


# 全域配置實例
config = E2EConfig()
