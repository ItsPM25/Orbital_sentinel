from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_session_token, get_current_user, verify_password
from app.core.settings import settings
from app.models import User, UserContactEmail
from app.schemas.auth import LoginRequest, LoginResponse, UserOut

router = APIRouter(tags=["auth"])


def _user_out(user: User, email: str | None = None) -> UserOut:
    return UserOut(
        user_id=user.user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        email=email or (user.contact_emails[0].contact_email if user.contact_emails else ""),
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    contact = db.get(UserContactEmail, body.email.strip().lower())
    if contact is None or not verify_password(body.password, contact.user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    response.set_cookie(
        settings.session_cookie,
        create_session_token(contact.user_id),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return LoginResponse(user=_user_out(contact.user, contact.contact_email))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
