from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext

import os
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY")  # type: ignore
if not SECRET_KEY:
    raise ValueError("SECRET_KEY not set in environment variables. Please set it.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

from typing import Optional

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    from jose import JWTError
    try:
        if not SECRET_KEY:
            raise ValueError("SECRET_KEY not set")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("Invalid token")