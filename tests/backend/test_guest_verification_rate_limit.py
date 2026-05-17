import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import guest_verification_service as guest_verification_module  # noqa: E402
from app.services.guest_verification_service import GuestVerificationService  # noqa: E402


@pytest.fixture(autouse=True)
def reset_guest_verification_state(monkeypatch):
    GuestVerificationService._failed_attempts = {}
    GuestVerificationService._attempt_locks = {}
    monkeypatch.setattr(guest_verification_module.cache, "enabled", False)
    monkeypatch.setattr(guest_verification_module.cache, "redis_client", None)


def _build_service() -> GuestVerificationService:
    return GuestVerificationService.__new__(GuestVerificationService)


def test_password_attempts_share_the_same_lock_scope_as_the_failure_counter():
    service = _build_service()

    rate_identifier_a, lock_identifier_a = service._build_verification_identifiers(
        slug="demo-wedding",
        verification_data={"password": "first"},
    )
    rate_identifier_b, lock_identifier_b = service._build_verification_identifiers(
        slug="demo-wedding",
        verification_data={"password": "second"},
    )

    assert rate_identifier_a == "demo-wedding:password_attempt"
    assert rate_identifier_b == "demo-wedding:password_attempt"
    assert lock_identifier_a == "demo-wedding:password_attempt"
    assert lock_identifier_b == "demo-wedding:password_attempt"


@pytest.mark.asyncio
async def test_attempt_lock_serializes_same_identifier_until_release():
    service = _build_service()

    first_token = await service._acquire_attempt_lock(
        "demo-wedding:guest@example.com",
        namespace="guest_page_access",
    )
    second_token = await service._acquire_attempt_lock(
        "demo-wedding:guest@example.com",
        namespace="guest_page_access",
    )

    assert first_token is not None
    assert second_token is None

    await service._release_attempt_lock(
        "demo-wedding:guest@example.com",
        first_token,
        namespace="guest_page_access",
    )

    third_token = await service._acquire_attempt_lock(
        "demo-wedding:guest@example.com",
        namespace="guest_page_access",
    )

    assert third_token is not None
