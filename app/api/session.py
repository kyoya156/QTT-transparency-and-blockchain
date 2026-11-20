"""Login/logout for the internal page: exchange a one-time token for a signed cookie."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import access
from ..auth import clear_session_cookie, current_user, set_session_cookie
from ..db import get_db

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@router.post("/session")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = access.find_user_by_token(db, body.token.strip())
    if user is None:
        raise HTTPException(401, "invalid or inactive token")
    set_session_cookie(response, request, user)
    access.audit(db, user, "login", detail={"method": "token"})
    db.commit()
    return {"id": user.id, "email": user.email, "name": user.name, "department": user.department}


@router.delete("/session")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/session")
def session_info(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "department": user.department}
