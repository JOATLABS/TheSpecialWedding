from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, Request, Response, status

from app.core.settings import settings
from app.utils.auth_utils import (
    clear_auth_cookie,
    create_access_token,
    set_auth_cookie,
    verify_token,
)


GUEST_ACCESS_COOKIE_NAME = "guest_access_session"


@dataclass(frozen=True)
class GuestAccessSession:
    wedding_slug: str
    wedding_id: str
    guest_id: Optional[str]
    auth_method: str
    otp_verified: bool = False


def guest_access_session_max_age() -> int:
    return max(int(settings.guest_access_session_minutes), 1) * 60


def create_guest_access_session_token(
    *,
    wedding_slug: str,
    wedding_id: str,
    auth_method: str,
    guest_id: Optional[str] = None,
    otp_verified: bool = False,
) -> str:
    session_subject = guest_id or f"guest-access:{wedding_slug}"
    return create_access_token(
        {
            "sub": session_subject,
            "type": "guest_access",
            "role": "guest_access",
            "wedding_slug": wedding_slug,
            "wedding_id": wedding_id,
            "guest_id": guest_id,
            "auth_method": auth_method,
            "otp_verified": otp_verified,
        },
        expires_delta=timedelta(seconds=guest_access_session_max_age()),
    )


def set_guest_access_session(
    response: Response,
    *,
    wedding_slug: str,
    wedding_id: str,
    auth_method: str,
    guest_id: Optional[str] = None,
    otp_verified: bool = False,
) -> None:
    token = create_guest_access_session_token(
        wedding_slug=wedding_slug,
        wedding_id=wedding_id,
        auth_method=auth_method,
        guest_id=guest_id,
        otp_verified=otp_verified,
    )
    set_auth_cookie(
        response,
        GUEST_ACCESS_COOKIE_NAME,
        token,
        max_age=guest_access_session_max_age(),
    )


def clear_guest_access_session(response: Response) -> None:
    clear_auth_cookie(response, GUEST_ACCESS_COOKIE_NAME)


def get_guest_access_session(
    request: Request,
    *,
    slug: Optional[str] = None,
    required: bool = True,
    require_guest: bool = False,
    require_otp_verified: bool = False,
) -> Optional[GuestAccessSession]:
    session_token = request.cookies.get(GUEST_ACCESS_COOKIE_NAME)

    if not session_token:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Guest access session not found",
            )
        return None

    try:
        payload = verify_token(session_token)
    except ValueError as exc:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Guest access session is invalid or expired",
            ) from exc
        return None

    if payload.get("type") != "guest_access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest access session is invalid",
        )

    wedding_slug = str(payload.get("wedding_slug") or "")
    wedding_id = str(payload.get("wedding_id") or "")
    guest_id = payload.get("guest_id")
    auth_method = str(payload.get("auth_method") or "")
    otp_verified = bool(payload.get("otp_verified"))

    if not wedding_slug or not wedding_id or not auth_method:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Guest access session is incomplete",
        )

    session = GuestAccessSession(
        wedding_slug=wedding_slug,
        wedding_id=wedding_id,
        guest_id=str(guest_id) if guest_id else None,
        auth_method=auth_method,
        otp_verified=otp_verified,
    )

    if slug and session.wedding_slug != slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest access session does not match this wedding",
        )

    if require_guest and not session.guest_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest-specific access is required for this action",
        )

    if require_otp_verified and not session.otp_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OTP verification is required for this action",
        )

    return session
