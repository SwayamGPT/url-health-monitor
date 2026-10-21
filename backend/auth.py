from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import select, update
from database import AsyncSession, get_db
import hashlib
import model
import os
import secrets


pwd_context = CryptContext(schemes=["bcrypt"])
secret_key = os.getenv("SECRET_KEY") or os.getenv("secret_key")
algorithm = os.getenv("ALGORITHM") or os.getenv("algorithm") or "HS256"
# Short-lived access token limits how long a stolen token is useful; the refresh token keeps users logged in.
access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
refresh_token_days = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
# Set COOKIE_SECURE=true when serving over HTTPS.
cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
access_cookie_scheme = APIKeyCookie(name=ACCESS_COOKIE, auto_error=False)
refresh_cookie_scheme = APIKeyCookie(name=REFRESH_COOKIE, auto_error=False)

if not secret_key:
    raise RuntimeError("SECRET_KEY is not set")


def create_access_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(minutes=access_token_minutes)
    return jwt.encode({"sub": str(user_id), "type": "access", "exp": expire}, secret_key, algorithm=algorithm)

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _set_cookie(response: Response, name: str, value: str, max_age: int):
    # httpOnly: JS can't read the token (XSS). SameSite=Lax: not sent on cross-site POSTs (CSRF).
    response.set_cookie(name, value, httponly=True, samesite="lax", secure=cookie_secure, max_age=max_age)

async def issue_tokens(db: AsyncSession, response: Response, user_id: int):
    """Create a new access + refresh token pair and set both cookies. Caller commits."""
    refresh = secrets.token_urlsafe(32)
    db.add(model.RefreshToken(
        user_id=user_id,
        token_hash=_hash(refresh),
        expires_at=datetime.utcnow() + timedelta(days=refresh_token_days),
    ))
    _set_cookie(response, ACCESS_COOKIE, create_access_token(user_id), access_token_minutes * 60)
    _set_cookie(response, REFRESH_COOKIE, refresh, refresh_token_days * 86400)

async def rotate_refresh_token(db: AsyncSession, response: Response, token: str | None):
    """Exchange a valid refresh token for a new pair; the old one is revoked."""
    if not token:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(model.RefreshToken).where(model.RefreshToken.token_hash == _hash(token)))
    stored = result.scalar_one_or_none()
    now = datetime.utcnow()
    if stored is None:
        raise HTTPException(401, "Invalid refresh token")
    if stored.revoked_at is not None:
        # A rotated-out token was used again: it was probably stolen. Log out every session of this user.
        await revoke_all_refresh_tokens(db, stored.user_id)
        await db.commit()
        raise HTTPException(401, "Refresh token reused; all sessions revoked")
    if stored.expires_at <= now:
        raise HTTPException(401, "Refresh token expired")
    stored.revoked_at = now
    await issue_tokens(db, response, stored.user_id)
    await db.commit()

async def revoke_refresh_token(db: AsyncSession, token: str | None):
    if token:
        await db.execute(
            update(model.RefreshToken)
            .where(model.RefreshToken.token_hash == _hash(token), model.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )

async def revoke_all_refresh_tokens(db: AsyncSession, user_id: int):
    await db.execute(
        update(model.RefreshToken)
        .where(model.RefreshToken.user_id == user_id, model.RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )

def clear_auth_cookies(response: Response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, httponly=True, samesite="lax", secure=cookie_secure)

async def get_current_user(token: str | None = Depends(access_cookie_scheme), db: AsyncSession = Depends(get_db)):
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        if payload.get("type") != "access":
            raise JWTError("wrong token type")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    result = await db.execute(select(model.User).where(model.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return user
