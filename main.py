from dotenv import load_dotenv
import os
import sys
import logging

# 載入 .env (必須在所有其他 import 之前)
load_dotenv()

# 檢查是否為測試模式 (必須在 import app.* 之前設定 DATABASE_URL)
# 使用方式: 設定環境變數 TEST_MODE=1
# Windows PowerShell: $env:TEST_MODE="1"; uvicorn main:app --reload
# Windows CMD:
#   方法1: set TEST_MODE=1
#          uvicorn main:app --reload
#   方法2 (單行): cmd /c "set TEST_MODE=1 && uvicorn main:app --reload"
# Linux/Mac: TEST_MODE=1 uvicorn main:app --reload
if os.getenv("TEST_MODE") == "1":
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if test_db_url:
        os.environ["DATABASE_URL"] = test_db_url
        print("=" * 80)
        print("WARNING: TEST MODE ENABLED")
        print(f"Database: {test_db_url}")
        print("WARNING: Application is connected to TEST database")
        print("=" * 80)
    else:
        print("ERROR: TEST_DATABASE_URL not set in .env")
        sys.exit(1)

# 在設定好 DATABASE_URL 之後才 import 需要資料庫連線的模組
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from starlette.types import Scope

from app.modules.line_login import router as line_login_router
from app.modules.menu import router as menu_router
from app.modules.order import router as order_router
from app.modules.chat import router as chat_router
from app.modules.sse import router as sse_router
from app.modules.qrcode import router as qrcode_router
from app.static_with_cache import CachedStaticFiles
from app.logging_filter import ImageNotFoundFilter

# 設定日誌過濾器（過濾圖片 404 錯誤）
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(ImageNotFoundFilter())

app = FastAPI()

# ---- 掛載應用路由（確保 /api* 保留給後端 API） ----
app.include_router(line_login_router)
app.include_router(menu_router, prefix="/api")
app.include_router(order_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(qrcode_router, prefix="/api")

# ---- 靜態與前端設定 ----
dist_root = os.path.join("static", "dist")
dev_index = os.path.join("static", "index.html")
admin_root = os.path.join("static", "admin")

if os.path.isdir(dist_root):
    # Mount independent admin static at /admin (non-Vue admin UI)
    if os.path.isdir(admin_root):
        app.mount("/admin", StaticFiles(directory=admin_root, html=True), name="admin")

    # Explicit assets mount to ensure correct MIME for JS/CSS
    assets_root = os.path.join(dist_root, "assets")
    if os.path.isdir(assets_root):
        app.mount("/assets", StaticFiles(directory=assets_root), name="assets")

    # Mount static files (images, etc.) if they exist
    static_root = os.path.join(dist_root, "static")
    if os.path.isdir(static_root):
        app.mount("/static", StaticFiles(directory=static_root), name="static")

    # Serve public images directory (for dish images) with caching
    # 優先使用 public 目錄，如果不存在則使用 dist 目錄
    public_images_root = os.path.join("static", "public", "images")
    dist_images_root = os.path.join(dist_root, "images")

    if os.path.isdir(public_images_root):
        app.mount("/images", CachedStaticFiles(directory=public_images_root), name="images")
    elif os.path.isdir(dist_images_root):
        app.mount("/images", CachedStaticFiles(directory=dist_images_root), name="images")

    # SPA fallback for Vue Router: serve index.html for all non-API, non-static routes
    @app.get("/{full_path:path}", response_class=FileResponse)
    async def spa_fallback(request: Request, full_path: str):
        """
        Fallback route for Vue Router history mode.
        Returns index.html for all routes that don't match API or static files.
        """
        # Check if the requested file exists in dist_root
        file_path = os.path.join(dist_root, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Otherwise, return index.html for SPA routing
        return FileResponse(os.path.join(dist_root, "index.html"))

else:
    # Dev mode: serve raw static and SPA fallback to static/index.html
    # Serve public images with caching first
    public_images_root = os.path.join("static", "public", "images")
    if os.path.isdir(public_images_root):
        app.mount("/images", CachedStaticFiles(directory=public_images_root), name="images")

    app.mount("/static", StaticFiles(directory="static"), name="static")
    if os.path.isdir(admin_root):
        app.mount("/admin", StaticFiles(directory=admin_root, html=True), name="admin")

    @app.get("/", response_class=FileResponse)
    async def dev_index_page():
        return FileResponse(dev_index)

    @app.get("/{_path:path}", response_class=FileResponse)
    async def dev_spa_fallback(_path: str):
        return FileResponse(dev_index)

