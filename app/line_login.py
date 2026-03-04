import os
import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Response
from jose import jwk, jwt
from jose.exceptions import JWTError
from dotenv import load_dotenv

from app.constants import LINE_LOGIN_HTTP_TIMEOUT_SECONDS

load_dotenv()

LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID", "請設定_LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "請設定_LINE_CHANNEL_SECRET")
LINE_REDIRECT_URI = os.getenv(
    "LINE_REDIRECT_URI", "http://localhost:8000/auth/line/callback"
)
LINE_SCOPE = os.getenv("LINE_SCOPE", "openid profile email")
LINE_ISS = os.getenv("LINE_ISS", "https://access.line.me")

APP_JWT_SECRET = os.getenv("APP_JWT_SECRET", "dev-only-change-me")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "app_session")
SESSION_EXPIRE_DAYS = int(os.getenv("SESSION_EXPIRE_DAYS", "30"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"

STATE_COOKIE_NAME = "line_login_state"
NONCE_COOKIE_NAME = "line_login_nonce"
STATE_COOKIE_MAX_AGE = 300  # 5 minutes

# JWKS 快取結構，減少重複向 LINE API 取公鑰的次數。
_JWKS_CACHE: Dict[str, Any] = {"keys": None, "ts": 0.0}
_JWKS_TTL_SECONDS = 600
_LINE_JWKS_ENDPOINT = "https://api.line.me/oauth2/v2.1/certs"
_LINE_AUTH_ENDPOINT = "https://access.line.me/oauth2/v2.1/authorize"
_LINE_TOKEN_ENDPOINT = "https://api.line.me/oauth2/v2.1/token"

# 伺服端記錄登入挑戰資料，避免部分行動裝置捨棄 Cookie 時造成 state 遺失。
_LOGIN_STATE_CACHE: Dict[str, Dict[str, Any]] = {}
_LOGIN_STATE_TTL_SECONDS = STATE_COOKIE_MAX_AGE


def generate_state() -> str:
    """建立 OAuth state，避免授權結果被竄改。"""
    return secrets.token_urlsafe(16)


def generate_nonce() -> str:
    """建立 ID Token nonce，配合 OpenID Connect 驗證重放攻擊。"""
    return secrets.token_urlsafe(16)


def build_authorize_url(state: str, nonce: str) -> str:
    """組合 LINE 授權頁網址並附上必要查詢參數。"""
    params = {
        "response_type": "code",
        "client_id": LINE_CHANNEL_ID,
        "redirect_uri": LINE_REDIRECT_URI,
        "state": state,
        "scope": LINE_SCOPE,
        "nonce": nonce,
    }
    return f"{_LINE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def set_temporary_login_cookies(response: Response, state: str, nonce: str) -> None:
    """在瀏覽器端保存 state 與 nonce，供 callback 驗證使用。"""
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=STATE_COOKIE_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        NONCE_COOKIE_NAME,
        nonce,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=STATE_COOKIE_MAX_AGE,
        path="/",
    )


def clear_temporary_login_cookies(response: Response) -> None:
    """授權流程結束後清除暫存的 state/nonce cookie。"""
    response.delete_cookie(STATE_COOKIE_NAME, path="/")
    response.delete_cookie(NONCE_COOKIE_NAME, path="/")


def _purge_expired_login_challenges(now: float | None = None) -> None:
    """清除已過期的登入挑戰（login challenge）。

    若未指定 now，則使用目前時間。
    掃描 _LOGIN_STATE_CACHE，移除超過 _LOGIN_STATE_TTL_SECONDS 的項目。
    """
    if now is None:
        now = time.time()
    expired_states = [
        key
        for key, info in list(_LOGIN_STATE_CACHE.items())
        if now - info["ts"] > _LOGIN_STATE_TTL_SECONDS
    ]
    for key in expired_states:
        _LOGIN_STATE_CACHE.pop(key, None)


def remember_login_challenge(state: str, nonce: str) -> None:
    """記錄登入挑戰資訊。

    將指定的 state 與對應的 nonce 儲存至快取中，
    並在儲存前自動清除過期的挑戰項目。
    """
    now = time.time()
    _purge_expired_login_challenges(now)
    _LOGIN_STATE_CACHE[state] = {"nonce": nonce, "ts": now}


def get_login_challenge(state: str) -> Optional[str]:
    """根據 state 取得對應的 nonce。

    若該 state 已過期或不存在，則回傳 None。
    """
    _purge_expired_login_challenges()
    entry = _LOGIN_STATE_CACHE.get(state)
    if not entry:
        return None
    return entry["nonce"]


def clear_login_challenge(state: Optional[str]) -> None:
    """登入流程完成或失敗時移除伺服端快取資料。"""
    if state is None:
        return
    _LOGIN_STATE_CACHE.pop(state, None)


async def _fetch_jwks(client: httpx.AsyncClient) -> Dict[str, Any]:
    response = await client.get(_LINE_JWKS_ENDPOINT)
    response.raise_for_status()
    return response.json()


async def get_line_jwks(
    http_client: Optional[httpx.AsyncClient] = None,
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """取得 LINE JWKS，必要時強制重新拉取。"""
    now = time.time()
    cached_keys = _JWKS_CACHE["keys"]
    if (
        not force_refresh
        and cached_keys
        and now - _JWKS_CACHE["ts"] < _JWKS_TTL_SECONDS
    ):
        return cached_keys

    if http_client is not None:
        jwks = await _fetch_jwks(http_client)
    else:
        async with httpx.AsyncClient(timeout=LINE_LOGIN_HTTP_TIMEOUT_SECONDS) as client:
            jwks = await _fetch_jwks(client)

    _JWKS_CACHE["keys"] = jwks
    _JWKS_CACHE["ts"] = now
    return jwks


async def exchange_code_for_tokens(
    code: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """以授權碼兌換 Access Token 與 ID Token。"""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINE_REDIRECT_URI,
        "client_id": LINE_CHANNEL_ID,
        "client_secret": LINE_CHANNEL_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    if http_client is not None:
        response = await http_client.post(_LINE_TOKEN_ENDPOINT, data=data, headers=headers)
    else:
        async with httpx.AsyncClient(timeout=LINE_LOGIN_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(_LINE_TOKEN_ENDPOINT, data=data, headers=headers)

    response.raise_for_status()
    return response.json()


def verify_id_token(id_token: str, jwks: Dict[str, Any]) -> Dict[str, Any]:
    """驗證 ID Token 的簽章與宣告內容。"""
    try:
        header = jwt.get_unverified_header(id_token)
    except Exception as exc:  # pragma: no cover - jose raises generic exceptions
        raise HTTPException(status_code=401, detail="invalid id_token header") from exc

    kid = header.get("kid")
    keys = jwks.get("keys", [])

    alg = header.get("alg") or "RS256"

    try:
        if alg.startswith("HS"):
            # 某些 LINE 環境會以 Channel Secret 產生 HS256 簽章。
            claims = jwt.decode(
                id_token,
                LINE_CHANNEL_SECRET,
                algorithms=[alg],
                audience=LINE_CHANNEL_ID,
                issuer=LINE_ISS,
                options={"verify_at_hash": False},
            )
        else:
            key = None
            if kid:
                key = next((k for k in keys if k.get("kid") == kid), None)
            elif len(keys) == 1:
                key = keys[0]

            if not key:
                header_kid = kid or "<none>"
                available_kids = [k.get("kid") for k in keys]
                print(
                    "LINE verify_id_token: kid not found",
                    {"expected": header_kid, "available": available_kids},
                )
                raise HTTPException(
                    status_code=401,
                    detail=f"kid not found in JWKS (kid={header_kid})",
                )

            jwk_key = jwk.construct(key)
            claims = jwt.decode(
                id_token,
                jwk_key,
                algorithms=[alg],
                audience=LINE_CHANNEL_ID,
                issuer=LINE_ISS,
                options={"verify_at_hash": False},
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=401, detail=f"id_token verification failed: {exc}"
        ) from exc

    return claims


def check_nonce(claims: Dict[str, Any], nonce: Optional[str]) -> None:
    """比對 ID Token 內的 nonce，防止重放攻擊。"""
    token_nonce = claims.get("nonce")
    if token_nonce is None:
        raise HTTPException(status_code=401, detail="id_token missing nonce")
    if nonce is None:
        raise HTTPException(status_code=401, detail="missing nonce")
    if token_nonce != nonce:
        raise HTTPException(status_code=401, detail="nonce mismatch")


def issue_app_session_jwt(user_id: str) -> str:
    """簽發本系統使用的 Session JWT。"""
    now = int(time.time())
    exp = now + 86400 * SESSION_EXPIRE_DAYS
    payload = {"uid": user_id, "iat": now, "exp": exp}
    return jwt.encode(payload, APP_JWT_SECRET, algorithm="HS256")


def set_session_cookie(response: Response, token: str) -> None:
    """將 Session JWT 寫入瀏覽器 Cookie，供前端後續請求使用。"""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=86400 * SESSION_EXPIRE_DAYS,
        path="/",
    )
