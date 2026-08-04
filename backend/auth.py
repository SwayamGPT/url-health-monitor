from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from database import AsyncSession, get_db
from fastapi import Depends, HTTPException
from sqlalchemy import Select
import model
import os


pwd_context = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
secret_key = os.getenv("secret_key")
algorithm = os.getenv("algorithm")

def create_access_token(user_id: int):
    expire = datetime.utcnow() + timedelta(minutes=60)
    return jwt.encode({"sub": str(user_id), "exp": expire}, secret_key, algorithm)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, secret_key, algorithm)
        user_id = int(payload["sub"])
    except (JWTError, KeyError):
        raise HTTPException(401, "Invalid or expired token")
    result = db.execute(Select(model.User).where(model.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return user
