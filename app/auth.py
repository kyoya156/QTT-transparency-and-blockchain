"""Dang nhap bang token (Authorization: Bearer ...). Danh tinh + phong ban lay tu day, khong tu request body."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import access
from .db import get_db


def current_user(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "missing bearer token")
    user = access.find_user_by_token(db, token.strip())
    if user is None:
        raise HTTPException(401, "invalid or inactive token")
    return user


def require_admin(user=Depends(current_user)):
    if user.department != "admin":
        raise HTTPException(403, "admin only")
    return user
