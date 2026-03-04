"""
Playwright E2E 測試配置

執行測試:
    pytest test/e2e/ --headed                    # 顯示瀏覽器
    pytest test/e2e/ --browser chromium          # 指定瀏覽器
    pytest test/e2e/ --video on                  # 錄製影片
    pytest test/e2e/ --tracing on                # 啟用追蹤
"""

from playwright.sync_api import PlaywrightTestConfig

# 基礎 URL (可通過環境變數覆寫)
BASE_URL = "http://localhost:8000"

# Playwright 配置
config = PlaywrightTestConfig(
    # 基礎 URL
    base_url=BASE_URL,

    # 超時設定 (毫秒)
    timeout=30000,  # 30 秒

    # 瀏覽器配置
    browser_name="chromium",  # chromium, firefox, webkit
    headless=True,

    # 視窗大小
    viewport={"width": 1280, "height": 720},

    # 截圖設定
    screenshot="only-on-failure",  # off, on, only-on-failure

    # 影片錄製
    video="retain-on-failure",  # off, on, retain-on-failure, on-first-retry

    # 追蹤設定 (用於除錯)
    trace="retain-on-failure",  # off, on, retain-on-failure, on-first-retry

    # 重試次數
    retries=2,

    # 並行執行
    workers=4,
)

# 測試專案配置
projects = [
    {
        "name": "chromium",
        "use": {"browser_name": "chromium"},
    },
    {
        "name": "firefox",
        "use": {"browser_name": "firefox"},
    },
    {
        "name": "webkit",
        "use": {"browser_name": "webkit"},
    },
    {
        "name": "mobile-chrome",
        "use": {
            "browser_name": "chromium",
            "viewport": {"width": 375, "height": 667},
            "device_scale_factor": 2,
            "is_mobile": True,
            "has_touch": True,
        },
    },
]
