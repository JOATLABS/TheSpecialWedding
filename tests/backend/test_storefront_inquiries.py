from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from bson import ObjectId
from fastapi import HTTPException
import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.models.storefront import StorefrontInquiryRequest
from app.services.storefront_inquiry_service import StorefrontInquiryService
from app.utils.rate_limiter import get_client_ip


OWNER_ID = "507f1f77bcf86cd799439011"


class FakeCollection:
    def __init__(self, documents: list[dict] | None = None) -> None:
        self.documents = list(documents or [])
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict]] = []

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None

    async def insert_one(self, document: dict) -> SimpleNamespace:
        stored = dict(document)
        stored.setdefault("_id", ObjectId("65f000000000000000000099"))
        self.documents.append(stored)
        self.inserted.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        self.updated.append((query, update))
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                document.update(update.get("$set", {}))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {
            "users": FakeCollection(
                [
                    {
                        "_id": ObjectId(OWNER_ID),
                        "email": "private-planner@example.test",
                        "company_name": "Luxe & Light",
                    }
                ]
            ),
            "storefront_inquiries": FakeCollection(),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())


class FakeMongo:
    def __init__(self) -> None:
        self.db = FakeDatabase()

    def get_users_collection(self) -> FakeCollection:
        return self.db["users"]


class FakeStorefrontService:
    def __init__(self, failure: HTTPException | None = None) -> None:
        self.failure = failure
        self.identifiers: list[str] = []

    async def resolve_public_context(self, identifier: str) -> dict:
        self.identifiers.append(identifier)
        if self.failure:
            raise self.failure
        return {
            "owner_id": OWNER_ID,
            "slug": "luxe-light",
            "settings": {"title": "Luxe weddings"},
        }


class FakeRateLimiter:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.keys: list[str] = []

    async def is_allowed(self, key: str, requests_per_minute: int | None = None):
        self.keys.append(key)
        return self.allowed, 4 if self.allowed else 0, 1234567890


class FakeEmailService:
    def __init__(
        self,
        *,
        result: dict | None = None,
        error: Exception | None = None,
        inquiries: FakeCollection | None = None,
    ) -> None:
        self.result = result or {"success": True, "id": "email-1"}
        self.error = error
        self.inquiries = inquiries
        self.calls: list[dict] = []

    async def send_email(self, **kwargs):
        if self.inquiries is not None:
            assert len(self.inquiries.inserted) == 1, (
                "the inquiry must be durable before notification is attempted"
            )
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def inquiry_payload(**overrides) -> StorefrontInquiryRequest:
    values = {
        "name": "Ayo <script>alert(1)</script>",
        "email": "ayo@example.com",
        "phone": "+1 555 555 0199",
        "wedding_date": date(2027, 6, 12),
        "message": "Please help with <b>planning</b> & logistics.",
    }
    values.update(overrides)
    return StorefrontInquiryRequest.model_validate(values)


def make_service(
    *,
    storefront_failure: HTTPException | None = None,
    rate_allowed: bool = True,
    email_result: dict | None = None,
    email_error: Exception | None = None,
):
    mongo = FakeMongo()
    storefront = FakeStorefrontService(storefront_failure)
    limiter = FakeRateLimiter(rate_allowed)
    email = FakeEmailService(
        result=email_result,
        error=email_error,
        inquiries=mongo.db["storefront_inquiries"],
    )
    service = StorefrontInquiryService(
        mongo_client=mongo,
        storefront_service=storefront,
        rate_limiter=limiter,
        email_service=email,
    )
    return service, mongo, storefront, limiter, email


def test_inquiry_request_forbids_owner_metadata_and_validates_contact_fields():
    with pytest.raises(ValidationError):
        StorefrontInquiryRequest.model_validate(
            {
                "name": "Ayo",
                "email": "ayo@example.com",
                "message": "Hello",
                "planner_id": "attacker-controlled",
            }
        )

    for invalid in (
        {"name": "", "email": "ayo@example.com", "message": "Hello"},
        {"name": "Ayo", "email": "not-email", "message": "Hello"},
        {"name": "Ayo", "email": "ayo@example.com", "message": ""},
    ):
        with pytest.raises(ValidationError):
            StorefrontInquiryRequest.model_validate(invalid)


def _request(peer: str, headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/storefront/luxe-light/inquiries",
            "raw_path": b"/api/storefront/luxe-light/inquiries",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 443),
            "server": ("api.example.com", 443),
        }
    )


def test_client_ip_ignores_spoofed_forwarding_headers_from_public_peer():
    direct = _request(
        "8.8.8.8",
        [(b"x-forwarded-for", b"1.1.1.1"), (b"cf-connecting-ip", b"9.9.9.9")],
    )
    proxied = _request(
        "10.0.0.10",
        [(b"cf-connecting-ip", b"1.1.1.1"), (b"x-forwarded-for", b"9.9.9.9")],
    )

    assert get_client_ip(direct) == "8.8.8.8"
    assert get_client_ip(proxied) == "1.1.1.1"


@pytest.mark.asyncio
async def test_inquiry_persists_owner_scoped_allowlist_before_escaped_notification():
    service, mongo, storefront, limiter, email = make_service()

    result = await service.capture(
        "LUXE-LIGHT",
        inquiry_payload(),
        client_ip="203.0.113.10",
        user_agent="Example Browser/1.0",
    )

    assert result["success"] is True
    assert result["inquiry_id"] == "65f000000000000000000099"
    assert storefront.identifiers == ["LUXE-LIGHT"]
    assert limiter.keys == ["203.0.113.10:luxe-light"]

    stored = mongo.db["storefront_inquiries"].inserted[0]
    assert stored["planner_id"] == OWNER_ID
    assert stored["storefront_slug"] == "luxe-light"
    assert stored["name"] == "Ayo <script>alert(1)</script>"
    assert stored["email"] == "ayo@example.com"
    assert stored["wedding_date"] == "2027-06-12"
    assert stored["notification"]["status"] == "pending"
    assert "settings" not in stored
    assert "planner_email" not in stored

    sent = email.calls[0]
    assert sent["to_email"] == "private-planner@example.test"
    assert sent["subject"] == "New storefront inquiry"
    assert "<script>" not in sent["html_content"]
    assert "&lt;script&gt;" in sent["html_content"]
    assert "<b>planning</b>" not in sent["html_content"]
    assert "&lt;b&gt;planning&lt;/b&gt;" in sent["html_content"]
    assert (
        mongo.db["storefront_inquiries"].updated[-1][1]["$set"]["notification.status"]
        == "sent"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "notification_result,notification_error",
    [
        ({"success": False, "error": "not configured"}, None),
        (None, RuntimeError("provider unavailable")),
    ],
)
async def test_notification_failure_never_loses_persisted_inquiry(
    notification_result, notification_error
):
    service, mongo, _storefront, _limiter, _email = make_service(
        email_result=notification_result,
        email_error=notification_error,
    )

    result = await service.capture(
        "luxe-light",
        inquiry_payload(),
        client_ip="203.0.113.10",
        user_agent=None,
    )

    assert result["success"] is True
    assert len(mongo.db["storefront_inquiries"].inserted) == 1
    assert (
        mongo.db["storefront_inquiries"].updated[-1][1]["$set"]["notification.status"]
        == "failed"
    )


@pytest.mark.asyncio
async def test_private_or_ineligible_storefront_is_404_without_side_effects():
    service, mongo, _storefront, limiter, email = make_service(
        storefront_failure=HTTPException(status_code=404, detail="Storefront not found")
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.capture(
            "private-storefront",
            inquiry_payload(),
            client_ip="203.0.113.10",
            user_agent=None,
        )

    assert exc_info.value.status_code == 404
    assert mongo.db["storefront_inquiries"].inserted == []
    assert limiter.keys == []
    assert email.calls == []


@pytest.mark.asyncio
async def test_rate_limit_is_keyed_by_canonical_storefront_and_ip_before_insert():
    service, mongo, _storefront, limiter, email = make_service(rate_allowed=False)

    with pytest.raises(HTTPException) as exc_info:
        await service.capture(
            "luxe-light",
            inquiry_payload(),
            client_ip="203.0.113.10",
            user_agent=None,
        )

    assert exc_info.value.status_code == 429
    assert limiter.keys == ["203.0.113.10:luxe-light"]
    assert mongo.db["storefront_inquiries"].inserted == []
    assert email.calls == []
