"""Tests for Phase C: marketing template-download lead capture.

Validates:
- ``MarketingLeadService.capture_template_download`` writes one
  ``marketing_leads`` row, dispatches the PDF email, normalizes
  email casing, and is idempotent on (email, template_id).
- UTM provenance is persisted on the lead row.
- Repeat downloads bump ``download_count`` + record subsequent UTM as
  history without overwriting the original attribution.
- Unknown ``template_id`` raises ``KeyError`` (which the API maps to 404).
- Resend attachment payload matches the documented shape
  (https://resend.com/docs/api-reference/emails/send-email):
  ``{"filename": str, "content": base64-string}``.

Pydantic v2 patterns confirmed in earlier validations
(https://pydantic.dev/docs/validation/latest/concepts/validators/).
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import mongomock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

import app.services.marketing_lead_service as marketing_module  # noqa: E402
from app.services.form_template_catalog import FORM_TEMPLATES  # noqa: E402


class _AsyncMockCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args, **kwargs):
        self.cursor.sort(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        return list(self.cursor)


class _AsyncMockCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, *args, **kwargs):
        return _AsyncMockCursor(self.collection.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self.collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self.collection.count_documents(*args, **kwargs)


class _AsyncMockDatabase:
    def __init__(self, database):
        self.db = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = _AsyncMockCollection(self.db[name])
        return self.collections[name]


class _FakeMongo:
    def __init__(self, database):
        self.db = _AsyncMockDatabase(database)


class _StubResend:
    """Minimal Resend stand-in. Records every send_email call so the
    tests can inspect attachment shape, recipient, etc."""

    def __init__(self) -> None:
        self.configured = True
        self.calls: List[Dict[str, Any]] = []
        self.return_success: bool = True

    async def send_email(self, **kwargs):  # noqa: D401 - matches real signature
        self.calls.append(kwargs)
        if self.return_success:
            return {"success": True, "email_id": f"em_{len(self.calls)}"}
        return {"success": False, "error": "stubbed failure"}


@pytest.fixture
def configured_marketing_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_marketing"]
    monkeypatch.setattr(marketing_module, "mongo", _FakeMongo(database))
    service = marketing_module.MarketingLeadService()
    service.email_service = _StubResend()
    return service, database


# =============================================================================
# Happy path
# =============================================================================


@pytest.mark.asyncio
async def test_capture_records_a_single_lead_with_utm(configured_marketing_service):
    service, database = configured_marketing_service

    template_id = FORM_TEMPLATES[0]["id"]
    result = await service.capture_template_download(
        email="Visitor@Example.COM ",
        template_id=template_id,
        recipient_name="Jamie Planner",
        utm_source="instagram",
        utm_medium="story",
        utm_campaign="autumn_launch",
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 (...)",
    )

    assert result["status"] == "created"
    assert result["email_dispatched"] is True

    leads = list(database["marketing_leads"].find({}))
    assert len(leads) == 1
    lead = leads[0]
    assert lead["email"] == "visitor@example.com"
    assert lead["template_id"] == template_id
    assert lead["recipient_name"] == "Jamie Planner"
    assert lead["utm_source"] == "instagram"
    assert lead["utm_medium"] == "story"
    assert lead["utm_campaign"] == "autumn_launch"
    assert lead["download_count"] == 1
    assert lead["email_sends"] == 1
    assert lead["first_downloaded_at"] is not None


@pytest.mark.asyncio
async def test_capture_dispatches_email_with_pdf_attachment(
    configured_marketing_service,
):
    """Resend payload must match the documented shape — base64 string in
    ``content`` and a ``filename`` ending in ``.pdf``."""
    service, database = configured_marketing_service
    template_id = FORM_TEMPLATES[0]["id"]

    await service.capture_template_download(
        email="visitor@example.com",
        template_id=template_id,
    )

    sends = service.email_service.calls
    assert len(sends) == 1
    call = sends[0]
    assert call["to_email"] == "visitor@example.com"
    assert call["from_name"] == "The Special Wedding"
    assert call["email_type"] == "marketing_template_download"

    attachments = call["attachments"]
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment["filename"] == f"{template_id}.pdf"
    # ``content`` is base64-encoded per the existing ICS-attachment
    # convention and per Resend docs.
    decoded = base64.b64decode(attachment["content"])
    assert decoded.startswith(b"%PDF")


# =============================================================================
# Idempotence + repeat downloads
# =============================================================================


@pytest.mark.asyncio
async def test_repeat_download_resends_email_without_creating_duplicate_lead(
    configured_marketing_service,
):
    service, database = configured_marketing_service
    template_id = FORM_TEMPLATES[0]["id"]

    await service.capture_template_download(
        email="visitor@example.com", template_id=template_id, utm_source="ig"
    )
    second = await service.capture_template_download(
        email="visitor@example.com", template_id=template_id, utm_source="newsletter"
    )

    assert second["status"] == "resent"
    assert second["email_dispatched"] is True

    leads = list(database["marketing_leads"].find({}))
    assert len(leads) == 1, "no duplicate lead row on resubmit"
    lead = leads[0]
    assert lead["download_count"] == 2
    # Original attribution preserved
    assert lead["utm_source"] == "ig"
    # Subsequent attribution recorded as history
    assert isinstance(lead.get("subsequent_utm"), list)
    assert lead["subsequent_utm"][0]["utm_source"] == "newsletter"


@pytest.mark.asyncio
async def test_different_email_or_template_creates_separate_lead(
    configured_marketing_service,
):
    service, database = configured_marketing_service
    template_a = FORM_TEMPLATES[0]["id"]
    template_b = FORM_TEMPLATES[1]["id"]

    await service.capture_template_download(
        email="alice@example.com", template_id=template_a
    )
    await service.capture_template_download(
        email="bob@example.com", template_id=template_a
    )
    await service.capture_template_download(
        email="alice@example.com", template_id=template_b
    )

    assert database["marketing_leads"].count_documents({}) == 3


# =============================================================================
# Edge cases / resilience
# =============================================================================


@pytest.mark.asyncio
async def test_unknown_template_id_raises_key_error(configured_marketing_service):
    service, _ = configured_marketing_service
    with pytest.raises(KeyError):
        await service.capture_template_download(
            email="visitor@example.com", template_id="does-not-exist"
        )


@pytest.mark.asyncio
async def test_blank_email_raises_value_error(configured_marketing_service):
    service, _ = configured_marketing_service
    template_id = FORM_TEMPLATES[0]["id"]
    for bad in ("", "   ", None):
        with pytest.raises(ValueError):
            await service.capture_template_download(
                email=bad, template_id=template_id
            )


@pytest.mark.asyncio
async def test_email_send_failure_records_failure_count_but_keeps_lead(
    configured_marketing_service,
):
    """A delivery blip should not cost us the lead — we still want the
    email + UTM in marketing_leads for follow-up."""
    service, database = configured_marketing_service
    service.email_service.return_success = False

    template_id = FORM_TEMPLATES[0]["id"]
    result = await service.capture_template_download(
        email="visitor@example.com", template_id=template_id
    )

    assert result["status"] == "created"
    assert result["email_dispatched"] is False

    lead = database["marketing_leads"].find_one({"email": "visitor@example.com"})
    assert lead is not None
    assert lead["email_send_failures"] == 1
    assert lead["email_sends"] == 0


@pytest.mark.asyncio
async def test_truncates_oversized_utm_strings(configured_marketing_service):
    """A 1 MB attribution blob shouldn't bloat the lead doc — truncate to
    documented caps."""
    service, database = configured_marketing_service
    template_id = FORM_TEMPLATES[0]["id"]

    huge = "x" * 5000
    await service.capture_template_download(
        email="visitor@example.com",
        template_id=template_id,
        utm_source=huge,
        utm_medium=huge,
        utm_campaign=huge,
        recipient_name=huge,
        user_agent=huge,
    )

    lead = database["marketing_leads"].find_one({"email": "visitor@example.com"})
    assert lead["utm_source"] is not None and len(lead["utm_source"]) <= 60
    assert lead["utm_medium"] is not None and len(lead["utm_medium"]) <= 60
    assert lead["utm_campaign"] is not None and len(lead["utm_campaign"]) <= 120
    assert lead["recipient_name"] is not None and len(lead["recipient_name"]) <= 120
    assert lead["user_agent"] is not None and len(lead["user_agent"]) <= 300
