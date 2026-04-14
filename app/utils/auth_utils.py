import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Response

from app.core.settings import Environment, settings

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY")  # type: ignore
if not SECRET_KEY:
    raise ValueError("SECRET_KEY not set in environment variables. Please set it.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ACCESS_TOKEN_COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60

# Pre-computed hash for timing attack mitigation
# Hash of 'dummy_password_for_timing_mitigation' with bcrypt rounds=12
DUMMY_PASSWORD_HASH = "$2b$12$IXPmQtgA9Zbt4KBnrSSHZ.iSWfs2ktpKRkP3DDSDY5W9unTu8Oxiy"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt directly"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    try:
        if not SECRET_KEY:
            raise ValueError("SECRET_KEY not set")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def _get_cookie_domain() -> str | None:
    """Return a domain value so the cookie is visible across subdomains.

    For staging/production the cookie is set on the apex domain
    (e.g. ".thespecialwedding.io") so both ``api.staging.*`` and
    ``staging.*`` can share it.  Returns ``None`` in development so
    localhost cookies work without a domain restriction.
    """
    if settings.environment in (Environment.STAGING, Environment.PRODUCTION):
        # COOKIE_DOMAIN can be overridden via env var; sensible default
        # is derived from FRONTEND_URL if available.
        explicit = getattr(settings, "cookie_domain", None)
        if explicit:
            return explicit
        frontend = getattr(settings, "frontend_url", "")
        if frontend:
            from urllib.parse import urlparse

            host = urlparse(frontend).hostname or ""
            # strip the first subdomain (e.g. "staging.thespecialwedding.io" → ".thespecialwedding.io")
            parts = host.split(".")
            if len(parts) > 2:
                return "." + ".".join(parts[-2:])
            return "." + host
    return None


def set_auth_cookie(
    response: Response,
    cookie_name: str,
    token: str,
    max_age: int = ACCESS_TOKEN_COOKIE_MAX_AGE,
) -> None:
    domain = _get_cookie_domain()
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.environment in (Environment.STAGING, Environment.PRODUCTION),
        samesite="lax",
        domain=domain,
        path="/",
    )


def clear_auth_cookie(response: Response, cookie_name: str) -> None:
    domain = _get_cookie_domain()
    response.delete_cookie(
        key=cookie_name,
        path="/",
        domain=domain,
        samesite="lax",
    )
