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
from datetime import datetime, timezone
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


# =============================================================================
# HTML escaping in the confirmation email body — Copilot review.
# `_confirmation_html` interpolates recipient_name + template metadata into
# an HTML string. Both the recipient_name (public POST) and the catalog
# description (admin-authored) need to be escaped to avoid HTML injection
# in outbound emails.
# =============================================================================


def test_confirmation_html_escapes_recipient_name():
    template = FORM_TEMPLATES[0]
    body = marketing_module._confirmation_html(
        recipient_name='<script>alert("xss")</script>',
        template=template,
    )
    assert "<script>alert" not in body
    assert "&lt;script&gt;alert" in body


def test_confirmation_html_escapes_template_metadata():
    poisoned_template = {
        "id": "test",
        "name": "<b>Boutique</b>",
        "description": '<img src=x onerror="alert(1)">',
    }
    body = marketing_module._confirmation_html(
        recipient_name="Jamie",
        template=poisoned_template,
    )
    # The angle brackets must be escaped; the literal markup must NOT
    # render as HTML.
    assert "<b>Boutique</b>" not in body
    assert "&lt;b&gt;Boutique&lt;/b&gt;" in body
    assert "<img src=x" not in body
    assert "&lt;img src=x" in body


def test_confirmation_html_keeps_known_safe_chars():
    """Sanity: a vanilla name still renders cleanly without entities
    leaking into the human-readable copy."""
    template = {"id": "test", "name": "Boutique", "description": "Plain"}
    body = marketing_module._confirmation_html(
        recipient_name="Jamie",
        template=template,
    )
    assert "Hi Jamie," in body
    assert "<strong>Boutique</strong>" in body


# =============================================================================
# Starter-pack bundle (homepage lead magnet)
# =============================================================================
# The homepage band ships ALL 9 catalog PDFs in a single email when the
# caller passes ``template_id == STARTER_PACK_TEMPLATE_ID``. The lead row
# stores ``template_id="starter_pack"`` so analytics can distinguish the
# bundle from per-template downloads on /resources/templates.


@pytest.mark.asyncio
async def test_capture_starter_pack_emits_one_email_with_nine_attachments(
    configured_marketing_service, monkeypatch
):
    """One email, 9 attachments, one filename per FORM_TEMPLATES entry.

    We patch ``render_form_template_pdf`` so the test does not exercise
    WeasyPrint — we only care here that the service collects every
    catalog template into a single Resend payload."""
    service, database = configured_marketing_service

    def fake_render(template_id: str) -> bytes:
        return f"<pdf-bytes-for-{template_id}>".encode("utf-8")

    monkeypatch.setattr(marketing_module, "render_form_template_pdf", fake_render)

    result = await service.capture_template_download(
        email="visitor@example.com",
        template_id=marketing_module.STARTER_PACK_TEMPLATE_ID,
    )

    assert result["status"] == "created"
    assert result["email_dispatched"] is True

    sends = service.email_service.calls
    assert len(sends) == 1, "starter-pack ships in a single Resend email"
    call = sends[0]
    assert call["to_email"] == "visitor@example.com"
    assert call["email_type"] == "marketing_starter_pack_download"

    attachments = call["attachments"]
    assert len(attachments) == len(FORM_TEMPLATES) == 9

    expected_filenames = {f"{tpl['id']}.pdf" for tpl in FORM_TEMPLATES}
    actual_filenames = {a["filename"] for a in attachments}
    assert actual_filenames == expected_filenames

    # Each attachment is base64-encoded per the Resend contract.
    for attachment in attachments:
        decoded = base64.b64decode(attachment["content"])
        assert decoded.startswith(b"<pdf-bytes-for-")

    # Lead row records the sentinel id so analytics can distinguish
    # bundle leads from per-template ones.
    leads = list(database["marketing_leads"].find({}))
    assert len(leads) == 1
    lead = leads[0]
    assert lead["template_id"] == marketing_module.STARTER_PACK_TEMPLATE_ID
    assert lead["email"] == "visitor@example.com"
    assert lead["download_count"] == 1


@pytest.mark.asyncio
async def test_starter_pack_lead_is_idempotent_per_email(
    configured_marketing_service, monkeypatch
):
    """Repeat starter-pack downloads from the same email must not create
    a second lead row but DO dispatch a second email — same idempotence
    contract as per-template downloads."""
    service, database = configured_marketing_service

    monkeypatch.setattr(
        marketing_module,
        "render_form_template_pdf",
        lambda template_id: f"<pdf-bytes-for-{template_id}>".encode("utf-8"),
    )

    first = await service.capture_template_download(
        email="visitor@example.com",
        template_id=marketing_module.STARTER_PACK_TEMPLATE_ID,
    )
    second = await service.capture_template_download(
        email="visitor@example.com",
        template_id=marketing_module.STARTER_PACK_TEMPLATE_ID,
    )

    assert first["status"] == "created"
    assert second["status"] == "resent"

    leads = list(database["marketing_leads"].find({}))
    assert len(leads) == 1, "no duplicate lead row on starter-pack resubmit"
    assert leads[0]["download_count"] == 2

    # Both calls dispatched a real email.
    assert len(service.email_service.calls) == 2
    for call in service.email_service.calls:
        assert call["email_type"] == "marketing_starter_pack_download"
        assert len(call["attachments"]) == 9


# =============================================================================
# Concurrent-insert race — Codex review P2 follow-up
# Two requests for the same (email, template_id) can both see
# existing=None and race to insert. The unique compound index on
# marketing_leads (created in scripts/create_indexes_p1_forms_and_ai.py)
# makes Mongo raise on the loser; the service must treat that as an
# idempotent re-send rather than 500.
# =============================================================================


@pytest.mark.asyncio
async def test_capture_handles_duplicate_key_race(monkeypatch, configured_marketing_service):
    """Simulate the race where existing=None at find_one time but a
    concurrent insert lands a duplicate-key error. The service must
    fall back to the resent path without surfacing the exception."""
    service, database = configured_marketing_service
    template_id = FORM_TEMPLATES[0]["id"]

    # Pre-seed a lead so the post-error find_one resolves it. Without
    # this the recovery path can't recover and re-raises (the service's
    # contract — defensible if Mongo says the row was inserted but then
    # vanishes between calls).
    pre_existing = {
        "email": "racer@example.com",
        "template_id": template_id,
        "template_name": FORM_TEMPLATES[0].get("name"),
        "first_downloaded_at": datetime.now(timezone.utc),
        "last_downloaded_at": datetime.now(timezone.utc),
        "download_count": 1,
        "email_sends": 0,
        "email_send_failures": 0,
    }
    database["marketing_leads"].insert_one(pre_existing)

    real_find_one = service.leads.find_one
    real_insert_one = service.leads.insert_one
    call_log: List[str] = []

    async def first_find_returns_none(*args, **kwargs):
        # First find_one returns None to simulate the race; subsequent
        # find_ones (recovery path) hit the real collection so the
        # update branch resolves the pre-seeded row.
        if not call_log:
            call_log.append("miss")
            return None
        return await real_find_one(*args, **kwargs)

    async def insert_raises_dup_key(*args, **kwargs):
        # Simulate a Mongo unique-index violation. Match by class name
        # to avoid coupling the test to PyMongo's exception import path.
        class _DuplicateKeyError(Exception):
            pass

        _DuplicateKeyError.__name__ = "DuplicateKeyError"
        raise _DuplicateKeyError(
            "E11000 duplicate key error collection: marketing_leads"
        )

    service.leads.find_one = first_find_returns_none  # type: ignore[assignment]
    service.leads.insert_one = insert_raises_dup_key  # type: ignore[assignment]

    try:
        result = await service.capture_template_download(
            email="racer@example.com",
            template_id=template_id,
        )
    finally:
        service.leads.find_one = real_find_one  # type: ignore[assignment]
        service.leads.insert_one = real_insert_one  # type: ignore[assignment]

    # Race resolved as a re-send, not a 500.
    assert result["status"] == "resent"
    assert result["email_dispatched"] is True

    # Pre-seed download_count was 1; the recovery path bumps it.
    leads = list(database["marketing_leads"].find({}))
    assert len(leads) == 1, "race recovery must NOT create a duplicate lead row"
    assert leads[0]["download_count"] == 2
