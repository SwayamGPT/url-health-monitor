from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from database import AsyncSession, get_db
import model
import os


pwd_context = CryptContext(schemes=["bcrypt"])
secret_key = os.getenv("SECRET_KEY") or os.getenv("secret_key")
algorithm = os.getenv("ALGORITHM") or os.getenv("algorithm") or "HS256"
token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
# Set COOKIE_SECURE=true when serving over HTTPS.
cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"

COOKIE_NAME = "access_token"
cookie_scheme = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

if not secret_key:
    raise RuntimeError("SECRET_KEY is not set")

def create_access_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(minutes=token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, secret_key, algorithm=algorithm)

def set_auth_cookie(response: Response, token: str):
    # httpOnly: JS can't read the token (XSS). SameSite=Lax: not sent on cross-site POSTs (CSRF).
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure,
        max_age=token_minutes * 60,
    )

def clear_auth_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax", secure=cookie_secure)

async def get_current_user(token: str | None = Depends(cookie_scheme), db: AsyncSession = Depends(get_db)):
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    result = await db.execute(select(model.User).where(model.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return user
