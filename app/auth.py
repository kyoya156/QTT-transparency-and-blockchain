"""Authentication: bearer token for API clients, signed HttpOnly cookie for the page.

The page never keeps the raw token in JavaScript. It posts the token once to
`/api/session`; the server sets a signed cookie that names the user and the
token hash already stored in the database. Deactivating the user invalidates
both the token and the cookie.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import access, models
from .config import settings
from .db import get_db

# If SESSION_SECRET is not set, cookies still work for this process but are
# invalid after a restart. Production must set SESSION_SECRET.
_PROCESS_SECRET = secrets.token_hex(32)


def _secret() -> bytes:
    return (settings.session_secret or _PROCESS_SECRET).encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_value(user: models.User, issued_at: int | None = None) -> str:
    issued = int(time.time()) if issued_at is None else int(issued_at)
    payload = f"{user.id}:{user.token_hash}:{issued}"
    raw = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{raw}.{_sign(payload)}"


def read_session_value(value: str, db: Session) -> models.User | None:
    try:
        raw, signature = value.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8")
        user_id, token_hash, issued = payload.split(":", 2)
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if time.time() - int(issued) > settings.session_max_age:
            return None
        user = db.get(models.User, int(user_id))
    except (ValueError, TypeError):
        return None
    if user is None or not user.is_active or user.token_hash != token_hash:
        return None
    return user


def set_session_cookie(response: Response, request: Request, user: models.User) -> None:
    response.set_cookie(
        settings.session_cookie,
        make_session_value(user),
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie, path="/")


def current_user(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        user = access.find_user_by_token(db, token.strip())
        if user is None:
            raise HTTPException(401, "invalid or inactive token")
        return user
    cookie = request.cookies.get(settings.session_cookie)
    if cookie:
        user = read_session_value(cookie, db)
        if user is not None:
            return user
        raise HTTPException(401, "invalid or expired session")
    raise HTTPException(401, "missing bearer token or session cookie")


def require_admin(user=Depends(current_user)):
    if user.department != "admin":
        raise HTTPException(403, "admin only")
    return user
