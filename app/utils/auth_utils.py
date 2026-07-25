import logging
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Response

from app.core.settings import Environment, settings

load_dotenv()

logger = logging.getLogger(__name__)

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


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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


def _extract_cookie_host(value: str | None) -> str | None:
    if not value:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if "://" in candidate:
        return (urlparse(candidate).hostname or "").strip().lower() or None

    return candidate.lstrip(".").strip().lower() or None


def _cookie_domain_matches_host(domain: str, host: str | None) -> bool:
    if not host:
        return True

    normalized_domain = domain.lstrip(".").lower()
    normalized_host = host.lower()
    return normalized_host == normalized_domain or normalized_host.endswith(
        f".{normalized_domain}"
    )


def _derive_cookie_domain_from_host(host: str | None) -> str | None:
    if not host:
        return None

    labels = host.split(".")
    if len(labels) < 2:
        return None

    return f".{host}"


def _derive_cookie_domain_from_api_host(host: str | None) -> str | None:
    if not host:
        return None

    labels = host.split(".")
    if len(labels) < 2:
        return None

    if len(labels) == 2:
        return f".{host}"

    return "." + ".".join(labels[1:])


def _derive_shared_cookie_domain(frontend_host: str, api_host: str) -> str | None:
    frontend_labels = frontend_host.split(".")
    api_labels = api_host.split(".")
    shared_labels: list[str] = []

    while frontend_labels and api_labels and frontend_labels[-1] == api_labels[-1]:
        shared_labels.insert(0, frontend_labels.pop())
        api_labels.pop()

    if len(shared_labels) < 2:
        return None

    return "." + ".".join(shared_labels)


def legacy_cookie_cleanup_domains(
    environment: Environment,
    explicit_cookie_domain: str | None = None,
    frontend_url: str | None = None,
    api_base_url: str | None = None,
) -> list[str | None]:
    """Return cookie-domain variants worth clearing during auth transitions."""
    if environment not in (Environment.STAGING, Environment.PRODUCTION):
        return [None]

    cleanup_domains: list[str | None] = [None]
    seen = {None}

    def add(domain: str | None) -> None:
        if domain in seen:
            return
        seen.add(domain)
        cleanup_domains.append(domain)

    resolved_domain = resolve_cookie_domain(
        environment=environment,
        explicit_cookie_domain=explicit_cookie_domain,
        frontend_url=frontend_url,
        api_base_url=api_base_url,
    )
    add(resolved_domain)

    frontend_host = _extract_cookie_host(frontend_url)
    api_host = _extract_cookie_host(api_base_url)

    if frontend_host and "." in frontend_host:
        add(frontend_host)
    if api_host and "." in api_host:
        add(api_host)

    return cleanup_domains


def resolve_cookie_domain(
    environment: Environment,
    explicit_cookie_domain: str | None = None,
    frontend_url: str | None = None,
    api_base_url: str | None = None,
) -> str | None:
    """Return the shared auth-cookie domain for production-like environments.

    Staging/production need a domain visible to both the API host and the
    frontend host so login, silent refresh, the notification stream, and the
    Next.js proxy all share the same `admin_token` cookie contract.
    """
    if environment not in (Environment.STAGING, Environment.PRODUCTION):
        return None

    frontend_host = _extract_cookie_host(frontend_url)
    api_host = _extract_cookie_host(api_base_url)

    if explicit_cookie_domain:
        if _cookie_domain_matches_host(
            explicit_cookie_domain, frontend_host
        ) and _cookie_domain_matches_host(explicit_cookie_domain, api_host):
            return explicit_cookie_domain

        logger.critical(
            "COOKIE_DOMAIN=%s is not shared by FRONTEND_URL=%s and NEXT_PUBLIC_API_BASE_URL=%s",
            explicit_cookie_domain,
            frontend_url,
            api_base_url,
        )

    if frontend_host and api_host:
        shared_domain = _derive_shared_cookie_domain(frontend_host, api_host)
        if shared_domain:
            return shared_domain

    if frontend_host:
        frontend_domain = _derive_cookie_domain_from_host(frontend_host)
        if frontend_domain and _cookie_domain_matches_host(frontend_domain, api_host):
            return frontend_domain

    if api_host:
        api_domain = _derive_cookie_domain_from_api_host(api_host)
        if api_domain and _cookie_domain_matches_host(api_domain, frontend_host):
            return api_domain

    logger.critical(
        "No shared auth cookie domain could be derived from COOKIE_DOMAIN=%s FRONTEND_URL=%s NEXT_PUBLIC_API_BASE_URL=%s; falling back to a host-only cookie.",
        explicit_cookie_domain,
        frontend_url,
        api_base_url,
    )
    return None


def _get_cookie_domain() -> str | None:
    return resolve_cookie_domain(
        environment=settings.environment,
        explicit_cookie_domain=settings.cookie_domain,
        frontend_url=settings.frontend_url,
        api_base_url=settings.api_base_url,
    )


def _clear_auth_cookie_variants(response: Response, cookie_name: str) -> None:
    for domain in legacy_cookie_cleanup_domains(
        environment=settings.environment,
        explicit_cookie_domain=settings.cookie_domain,
        frontend_url=settings.frontend_url,
        api_base_url=settings.api_base_url,
    ):
        response.delete_cookie(
            key=cookie_name,
            path="/",
            domain=domain,
            samesite="lax",
        )


def set_auth_cookie(
    response: Response,
    cookie_name: str,
    token: str,
    max_age: int = ACCESS_TOKEN_COOKIE_MAX_AGE,
) -> None:
    # Flush older host-only or narrowly-scoped variants before issuing the
    # canonical shared-domain cookie so existing staging sessions do not keep
    # sending a stale `admin_token` alongside the new one.
    _clear_auth_cookie_variants(response, cookie_name)
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
    _clear_auth_cookie_variants(response, cookie_name)
