"""OIDC authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse

from src.core.logging import get_logger
from src.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

SESSION_COOKIE = "undata_session"
STATE_COOKIE = "undata_state"


@router.get("/login")
async def login(provider_hint: str | None = None):
    """Initiate OIDC login flow — redirect to Keycloak authorization URL."""
    url, state = await AuthService.get_authorization_url(provider_hint)
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=False,  # set True in production
        max_age=600,
    )
    return response


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    undata_state: str | None = Cookie(default=None),
    response: Response = None,
):
    """Handle Keycloak OIDC callback.

    Validates state cookie (CSRF), exchanges code for tokens, upserts UserProfile,
    sets signed session cookie, redirects to frontend.
    """
    if state is None or undata_state is None:
        raise HTTPException(status_code=401, detail={"error": "missing_state"})

    if code is None:
        raise HTTPException(status_code=400, detail={"error": "missing_code"})

    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                user = await AuthService.handle_callback(session, code, state, undata_state)
            except ValueError as exc:
                logger.warning("auth.callback.failed", extra={"error": str(exc)})
                raise HTTPException(status_code=401, detail={"error": "invalid_callback"})

    signed_session = AuthService.sign_session(str(user.id))
    redirect_url = "/"  # Frontend root — configure per deployment

    resp = RedirectResponse(url=redirect_url, status_code=302)
    resp.set_cookie(
        SESSION_COOKIE,
        signed_session,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )
    resp.delete_cookie(STATE_COOKIE)
    return resp


@router.post("/logout")
async def logout():
    """Clear the session cookie and return confirmation."""
    content = {"status": "logged_out"}
    from fastapi.responses import JSONResponse

    resp = JSONResponse(content=content)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
