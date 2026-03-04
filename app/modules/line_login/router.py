from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import line_login

router = APIRouter(prefix="/auth/line", tags=["LINE Login"])


@router.get("/login")
async def start_line_login() -> RedirectResponse:
    """啟動 LINE Login，導向官方授權頁。"""
    # 產生 state 與 nonce，並同步寫入 Cookie 與伺服端快取以供回呼驗證。
    state = line_login.generate_state()
    nonce = line_login.generate_nonce()
    redirect_url = line_login.build_authorize_url(state, nonce)

    response = RedirectResponse(url=redirect_url, status_code=302)
    line_login.set_temporary_login_cookies(response, state, nonce)
    line_login.remember_login_challenge(state, nonce)
    return response


def _redirect_with_error(message: str, *, state: str | None = None) -> RedirectResponse:
    """帶著錯誤資訊重新導回首頁並清除暫存資料。"""
    params = {"error": message}
    target = f"/?{urlencode(params)}"
    response = RedirectResponse(url=target, status_code=302)
    line_login.clear_temporary_login_cookies(response)
    line_login.clear_login_challenge(state)
    return response


@router.get("/callback")
async def complete_line_login(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """處理 LINE 回呼：驗證授權結果並建立應用程式 Session。"""
    if error:
        message = error_description or error
        return _redirect_with_error(message, state=state)
    if not code or not state:
        return _redirect_with_error("missing_code_or_state", state=state)

    stored_state = request.cookies.get(line_login.STATE_COOKIE_NAME)
    stored_nonce = request.cookies.get(line_login.NONCE_COOKIE_NAME)
    cached_nonce = line_login.get_login_challenge(state)

    if stored_state and stored_state != state:
        return _redirect_with_error("state_mismatch", state=state)

    # 以瀏覽器 Cookie 為優先，其次採用伺服端快取的 nonce，確保行動裝置也能完成驗證。
    expected_nonce = None
    if stored_state == state and stored_nonce:
        expected_nonce = stored_nonce
    elif cached_nonce:
        expected_nonce = cached_nonce

    if expected_nonce is None:
        return _redirect_with_error("state_mismatch", state=state)

    token_payload = await line_login.exchange_code_for_tokens(code)
    id_token = token_payload.get("id_token")
    if not id_token:
        return _redirect_with_error("missing_id_token", state=state)

    jwks = await line_login.get_line_jwks()
    try:
        claims = line_login.verify_id_token(id_token, jwks)
        line_login.check_nonce(claims, expected_nonce)
    except HTTPException as exc:
        if exc.detail.startswith("kid not found in JWKS"):
            jwks = await line_login.get_line_jwks(force_refresh=True)
            try:
                claims = line_login.verify_id_token(id_token, jwks)
                line_login.check_nonce(claims, expected_nonce)
            except HTTPException as retry_exc:
                return _redirect_with_error(retry_exc.detail, state=state)
        else:
            return _redirect_with_error(exc.detail, state=state)

    user_id = claims.get("sub")
    if not user_id:
        return _redirect_with_error("missing_subject", state=state)

    session_jwt = line_login.issue_app_session_jwt(user_id)

    # 整理要回傳給前端的使用者資訊，僅帶有值的欄位才會加入查詢參數。
    redirect_params = {"login": "success", "userId": user_id}
    display_name = claims.get("name") or claims.get("given_name") or ""
    picture = claims.get("picture") or ""
    if display_name:
        redirect_params["displayName"] = display_name
    if picture:
        redirect_params["avatar"] = picture
    email = claims.get("email")
    if email:
        redirect_params["email"] = email

    redirect_target = f"/?{urlencode(redirect_params)}"
    response = RedirectResponse(url=redirect_target, status_code=302)
    line_login.set_session_cookie(response, session_jwt)
    line_login.clear_temporary_login_cookies(response)
    line_login.clear_login_challenge(state)
    return response
