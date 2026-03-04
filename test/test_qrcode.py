"""
測試 QR Code 生成功能

涵蓋：
- JSON 格式生成（含 base64 圖片）
- PNG 圖片格式生成
- URL 格式正確性
- Session ID 自動生成與指定
- 錯誤處理
"""

from __future__ import annotations

import base64
import io
import json
import uuid
from fastapi.testclient import TestClient
from PIL import Image

# 確保 app 可導入
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from main import app


# ==================== JSON 格式 QR Code 測試 ====================

def test_generate_qrcode_json_basic():
    """測試：基本 JSON 格式 QR Code 生成"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/generate", params={"tableid": "A1"})

    assert response.status_code == 200
    data = response.json()

    # 驗證回傳欄位
    assert "qrcode_base64" in data
    assert "url" in data
    assert "session_id" in data
    assert "table_id" in data

    # 驗證數據正確性
    assert data["table_id"] == "A1"
    assert data["session_id"] is not None

    # 驗證 URL 格式
    assert "sessionid=" in data["url"]
    assert "tableid=A1" in data["url"]
    assert data["session_id"] in data["url"]

    # 驗證 base64 圖片格式
    assert len(data["qrcode_base64"]) > 0
    try:
        img_bytes = base64.b64decode(data["qrcode_base64"])
        img = Image.open(io.BytesIO(img_bytes))
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0
    except Exception as e:
        assert False, f"base64 解碼失敗: {e}"


def test_generate_qrcode_json_with_custom_session_id():
    """測試：使用自訂 session_id 生成 QR Code"""
    client = TestClient(app)

    custom_session_id = str(uuid.uuid4())

    response = client.get(
        "/api/admin/qrcode/generate",
        params={"tableid": "B2", "sessionid": custom_session_id}
    )

    assert response.status_code == 200
    data = response.json()

    # 驗證使用自訂的 session_id
    assert data["session_id"] == custom_session_id
    assert custom_session_id in data["url"]
    assert "tableid=B2" in data["url"]


def test_generate_qrcode_json_auto_session_id():
    """測試：自動生成 session_id（每次呼叫應不同）"""
    client = TestClient(app)

    response1 = client.get("/api/admin/qrcode/generate", params={"tableid": "D4"})
    response2 = client.get("/api/admin/qrcode/generate", params={"tableid": "D4"})

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # 驗證兩次生成的 session_id 不同
    assert data1["session_id"] != data2["session_id"]

    # 但 table_id 相同
    assert data1["table_id"] == data2["table_id"] == "D4"


# ==================== PNG 圖片格式 QR Code 測試 ====================

def test_generate_qrcode_png_basic():
    """測試：基本 PNG 格式 QR Code 生成"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/image", params={"tableid": "E5"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    # 驗證是否為有效的 PNG 圖片
    try:
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0
    except Exception as e:
        assert False, f"PNG 圖片解析失敗: {e}"


def test_generate_qrcode_png_with_custom_session_id():
    """測試：PNG 格式支援自訂 session_id"""
    client = TestClient(app)

    custom_session_id = str(uuid.uuid4())

    response = client.get(
        "/api/admin/qrcode/image",
        params={"tableid": "F6", "sessionid": custom_session_id}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    # 驗證圖片有效
    img = Image.open(io.BytesIO(response.content))
    assert img.format == "PNG"


def test_generate_qrcode_png_content_disposition():
    """測試：PNG 回應包含下載檔名"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/image", params={"tableid": "G7"})

    assert response.status_code == 200
    assert "content-disposition" in response.headers
    assert "table_G7_qrcode.png" in response.headers["content-disposition"]
    assert "inline" in response.headers["content-disposition"]


# ==================== 錯誤處理測試 ====================

def test_generate_qrcode_missing_table_id():
    """測試：缺少 table_id 參數"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/generate")

    # FastAPI 會回傳 422 Validation Error
    assert response.status_code == 422


def test_generate_qrcode_empty_table_id():
    """測試：空白 table_id"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/generate", params={"tableid": ""})

    # 根據實作，可能允許空字串或回傳錯誤
    # 這裡假設應該允許（業務邏輯決定）
    if response.status_code == 200:
        data = response.json()
        assert data["table_id"] == ""
    else:
        # 如果不允許，應為 400 或 422
        assert response.status_code in [400, 422]


def test_generate_qrcode_invalid_session_id_format():
    """測試：無效的 session_id 格式（非 UUID）會自動生成新的"""
    client = TestClient(app)

    invalid_session_id = "not-a-uuid"

    response = client.get(
        "/api/admin/qrcode/generate",
        params={"tableid": "H8", "sessionid": invalid_session_id}
    )

    # 服務會自動生成新的 UUID，而非回傳錯誤
    assert response.status_code == 200
    data = response.json()

    # 驗證回傳的 session_id 不是無效的那個，而是新生成的 UUID
    assert data["session_id"] != invalid_session_id

    # 驗證是有效的 UUID 格式
    try:
        uuid.UUID(data["session_id"])
    except ValueError:
        assert False, "回傳的 session_id 不是有效的 UUID"


def test_generate_qrcode_special_characters_in_table_id():
    """測試：table_id 包含特殊字元"""
    client = TestClient(app)

    # URL 編碼測試
    response = client.get("/api/admin/qrcode/generate", params={"tableid": "包廂-VIP#1"})

    assert response.status_code == 200
    data = response.json()

    # 驗證 table_id 正確處理
    assert data["table_id"] == "包廂-VIP#1"

    # 驗證 URL 中的 table_id 被正確編碼
    assert "tableid=" in data["url"]


# ==================== URL 格式測試 ====================

def test_qrcode_url_format_complete():
    """測試：生成的 URL 包含完整的參數"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/generate", params={"tableid": "I9"})

    assert response.status_code == 200
    data = response.json()

    url = data["url"]

    # 驗證 URL 結構
    assert url.startswith("http://") or url.startswith("https://")
    assert "?" in url  # 包含查詢參數

    # 驗證必要參數存在
    assert "sessionid=" in url
    assert "tableid=I9" in url

    # 驗證 session_id 是有效的 UUID
    import re
    uuid_pattern = r"sessionid=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"
    match = re.search(uuid_pattern, url)
    assert match is not None, "URL 中的 sessionid 不是有效的 UUID 格式"


def test_qrcode_url_uses_request_base():
    """測試：未指定 base_url 時使用請求的 base URL"""
    client = TestClient(app)

    # TestClient 預設的 base_url 是 http://testserver
    response = client.get("/api/admin/qrcode/generate", params={"tableid": "J10"})

    assert response.status_code == 200
    data = response.json()

    # 應該使用 testserver 或預設值
    url = data["url"]
    assert url.startswith("http://testserver") or url.startswith("http://")


# ==================== Base64 圖片解碼測試 ====================

def test_qrcode_base64_decodes_to_valid_image():
    """測試：base64 字串可正確解碼為圖片"""
    client = TestClient(app)

    response = client.get("/api/admin/qrcode/generate", params={"tableid": "K11"})

    assert response.status_code == 200
    data = response.json()

    base64_str = data["qrcode_base64"]

    # 解碼 base64
    img_bytes = base64.b64decode(base64_str)
    img = Image.open(io.BytesIO(img_bytes))

    # 驗證圖片屬性
    assert img.format == "PNG"
    assert img.mode in ["RGB", "RGBA", "L", "1"]  # 常見的 QR Code 模式
    assert img.size[0] > 100  # 合理的尺寸（至少 100x100）
    assert img.size[1] > 100


def test_qrcode_json_and_png_consistency():
    """測試：JSON 和 PNG 格式生成的 QR Code 內容一致"""
    client = TestClient(app)

    # 使用相同的參數生成兩種格式
    session_id = str(uuid.uuid4())
    params = {"tableid": "L12", "sessionid": session_id}

    response_json = client.get("/api/admin/qrcode/generate", params=params)
    response_png = client.get("/api/admin/qrcode/image", params=params)

    assert response_json.status_code == 200
    assert response_png.status_code == 200

    # 解碼 JSON 中的 base64 圖片
    json_data = response_json.json()
    json_img_bytes = base64.b64decode(json_data["qrcode_base64"])
    json_img = Image.open(io.BytesIO(json_img_bytes))

    # 解碼 PNG 回應
    png_img = Image.open(io.BytesIO(response_png.content))

    # 驗證兩張圖片尺寸相同（內容應該也相同，但像素比對較複雜）
    assert json_img.size == png_img.size
    assert json_img.format == png_img.format == "PNG"


# ==================== 整合測試 ====================

def test_qrcode_generated_url_works_with_session_api(client_with_db, db_session):
    """測試：生成的 QR Code URL 可正確用於建立 session"""
    from sqlalchemy.orm import Session

    # 1. 生成 QR Code
    qr_response = client_with_db.get("/api/admin/qrcode/generate", params={"tableid": "M13"})
    assert qr_response.status_code == 200
    qr_data = qr_response.json()

    # 2. 解析 URL 參數
    from urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(qr_data["url"])
    query_params = parse_qs(parsed_url.query)

    sessionid = query_params["sessionid"][0]
    tableid = query_params["tableid"][0]

    # 3. 使用這些參數呼叫購物車 API（應自動建立 session）
    cart_response = client_with_db.get(
        "/api/cart",
        params={"sessionid": sessionid, "tableid": tableid}
    )

    assert cart_response.status_code == 200

    # 4. 驗證回應設定了正確的 Cookie
    cookies = cart_response.cookies
    assert "cart_session_id" in cookies
    assert cookies["cart_session_id"] == sessionid
