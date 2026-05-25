"""Chunk 3 — backend tests for the two-stage wedding-checklist toast.

Validates:
- ``notify_wedding_created`` writes a planner_notifications doc with
  the WEDDING_CREATED type and a couple-tab action_url.
- ``notify_couple_portal_accepted`` carries the seeded form_id /
  couple_email / couple_names in metadata so the frontend toast can
  render an action button.
- The Stage 2 dispatch helper in ``couple_auth.py`` debounces when a
  ``form_distributions`` row already exists for (form_id, couple_email).
- Planners with no seeded ``couple_intake`` form still get a Stage 2
  notification (with seeded_form_id=None), so the bell is not silent —
  the action button just won't render.

Pydantic v2 Literal-type compatibility: the new
``WEDDING_CREATED`` / ``COUPLE_PORTAL_ACCEPTED`` literals were added to
``NotificationType`` and ``PlannerNotificationCreate.type`` accepts
them per https://pydantic.dev/docs/validation/latest/concepts/types/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.models.planner_notification import (  # noqa: E402
    PlannerNotificationCreate,
    PlannerNotificationTypes,
)


# =============================================================================
# Pydantic literal compatibility — Phase 1 wave-2 added a stricter type
# union; the new triggers must round-trip through it cleanly.
# =============================================================================


def test_wedding_created_literal_is_accepted_by_pydantic_model():
    PlannerNotificationCreate(
        planner_id="planner-1",
        type="wedding_created",
        title="x",
        message="y",
    )


def test_couple_portal_accepted_literal_is_accepted_by_pydantic_model():
    PlannerNotificationCreate(
        planner_id="planner-1",
        type="couple_portal_accepted",
        title="x",
        message="y",
    )


def test_planner_notification_types_constants_match_literals():
    assert PlannerNotificationTypes.WEDDING_CREATED == "wedding_created"
    assert PlannerNotificationTypes.COUPLE_PORTAL_ACCEPTED == "couple_portal_accepted"


# =============================================================================
# Service helper shape — verify the trigger wrappers build the right
# notification document. We patch ``create_notification`` so the test
# doesn't touch SSE / web-push / Mongo.
# =============================================================================


@pytest.fixture
def patched_planner_notification_service(monkeypatch):
    from app.services import planner_notification_service as svc_module

    captured: Dict[str, Any] = {}

    async def fake_create(self, **kwargs):
        captured.update(kwargs)
        return {"id": "notif-1", "message": "ok"}

    monkeypatch.setattr(
        svc_module.PlannerNotificationService,
        "create_notification",
        fake_create,
    )

    service = svc_module.PlannerNotificationService()
    return service, captured


@pytest.mark.asyncio
async def test_notify_wedding_created_builds_couple_tab_action_url(
    patched_planner_notification_service,
):
    service, captured = patched_planner_notification_service

    await service.notify_wedding_created(
        planner_id="planner-1",
        wedding_id="wedding-1",
        couple_names="Alex & Jamie",
    )
    assert captured["notification_type"] == "wedding_created"
    assert captured["wedding_id"] == "wedding-1"
    assert "Alex & Jamie" in captured["message"]
    assert captured["action_url"] == ("/admin/planner/weddings/wedding-1?tab=couple")


@pytest.mark.asyncio
async def test_notify_wedding_created_handles_missing_couple_names(
    patched_planner_notification_service,
):
    service, captured = patched_planner_notification_service
    await service.notify_wedding_created(
        planner_id="p", wedding_id="w", couple_names=None
    )
    assert "the couple" in captured["message"]


@pytest.mark.asyncio
async def test_notify_couple_portal_accepted_carries_form_metadata(
    patched_planner_notification_service,
):
    service, captured = patched_planner_notification_service

    await service.notify_couple_portal_accepted(
        planner_id="planner-1",
        wedding_id="wedding-1",
        couple_email="couple@example.com",
        couple_names="Alex & Jamie",
        seeded_form_id="form-seed-1",
    )

    assert captured["notification_type"] == "couple_portal_accepted"
    assert captured["metadata"] == {
        "couple_email": "couple@example.com",
        "couple_names": "Alex & Jamie",
        "form_id": "form-seed-1",
    }
    # Must point at the canonical planner-side send route at
    # app/admin/forms/[id]/send/page.tsx — there is no
    # /admin/planner/forms/* route, so the older form would 404.
    assert captured["action_url"].startswith("/admin/forms/form-seed-1/send")
    assert "/admin/planner/forms" not in captured["action_url"]
    assert "prefill_email=couple%40example.com" in captured["action_url"]


@pytest.mark.asyncio
async def test_notify_couple_portal_accepted_falls_back_when_no_form_id(
    patched_planner_notification_service,
):
    """Planners with no seeded couple_intake (legacy accounts created
    before Phase D) still get a notification — the bell shouldn't be
    silent. The action button just won't render in the frontend."""
    service, captured = patched_planner_notification_service

    await service.notify_couple_portal_accepted(
        planner_id="planner-1",
        wedding_id="wedding-1",
        couple_email="couple@example.com",
        couple_names="Alex & Jamie",
        seeded_form_id=None,
    )

    assert captured["metadata"]["form_id"] is None
    assert "/forms/" not in captured["action_url"]


@pytest.mark.asyncio
async def test_notify_guest_message_points_to_unified_inbox(
    patched_planner_notification_service,
):
    service, captured = patched_planner_notification_service

    await service.notify_guest_message(
        planner_id="planner-1",
        wedding_id="wedding/needs encoding",
        guest_name="Ayo Guest",
        message_preview="Can you help me?",
        guest_id="guest-1",
    )

    assert captured["notification_type"] == "guest_message"
    assert captured["action_url"] == (
        "/admin/communications/inbox?wedding_id=wedding%2Fneeds%20encoding"
    )


# =============================================================================
# Debounce: the Stage 2 dispatcher in couple_auth must skip when a
# form_distributions row already exists for (form_id, couple_email).
# =============================================================================


class _FakeMongoDB:
    def __init__(self, by_collection: Dict[str, Any]) -> None:
        self._by = by_collection

    def __getitem__(self, name: str):
        return self._by[name]


def _make_couple_auth_module(monkeypatch, *, seeded_doc, distribution_doc):
    """Build a couple_auth-like environment by monkey-patching only the
    bits ``_dispatch_couple_portal_accepted_notification`` touches."""
    from app.api import couple_auth as ca_module

    forms_coll = MagicMock()
    forms_coll.find_one = AsyncMock(return_value=seeded_doc)

    dist_coll = MagicMock()
    dist_coll.find_one = AsyncMock(return_value=distribution_doc)

    fake_db = _FakeMongoDB({"forms": forms_coll, "form_distributions": dist_coll})
    fake_mongo = MagicMock()
    fake_mongo.db = fake_db
    monkeypatch.setattr(ca_module, "mongo", fake_mongo)

    captured: Dict[str, Any] = {}

    class _FakePlannerSvc:
        async def notify_couple_portal_accepted(self, **kwargs):
            captured.update(kwargs)
            return {"id": "notif-1"}

    fake_svc = _FakePlannerSvc()

    import app.services.planner_notification_service as pns_module

    monkeypatch.setattr(pns_module, "planner_notification_service", fake_svc)

    return ca_module, captured, dist_coll, forms_coll


@pytest.mark.asyncio
async def test_dispatch_skips_when_form_already_sent_to_couple(monkeypatch):
    seeded_doc = {"_id": "form-seed-1"}
    distribution_doc = {"_id": "d1", "form_id": "form-seed-1"}
    ca, captured, dist_coll, forms_coll = _make_couple_auth_module(
        monkeypatch,
        seeded_doc=seeded_doc,
        distribution_doc=distribution_doc,
    )

    couple = {
        "planner_id": "planner-1",
        "planner_email": "planner@example.com",
        "email": "couple@example.com",
        "couple_names": "Alex & Jamie",
        "wedding_id": "w-1",
    }

    await ca._dispatch_couple_portal_accepted_notification(couple)

    # Debounce: the notification helper must NOT have been invoked.
    assert captured == {}
    # Distribution lookup happened with the correct scope.
    dist_coll.find_one.assert_awaited_once_with(
        {"form_id": "form-seed-1", "recipient_email": "couple@example.com"}
    )


@pytest.mark.asyncio
async def test_dispatch_fires_when_no_distribution_exists(monkeypatch):
    seeded_doc = {"_id": "form-seed-1"}
    ca, captured, dist_coll, forms_coll = _make_couple_auth_module(
        monkeypatch,
        seeded_doc=seeded_doc,
        distribution_doc=None,
    )

    await ca._dispatch_couple_portal_accepted_notification(
        {
            "planner_id": "planner-1",
            "planner_email": "planner@example.com",
            "email": "couple@example.com",
            "couple_names": "Alex & Jamie",
            "wedding_id": "w-1",
        }
    )

    assert captured["seeded_form_id"] == "form-seed-1"
    assert captured["couple_email"] == "couple@example.com"


@pytest.mark.asyncio
async def test_dispatch_still_notifies_when_planner_has_no_seeded_form(
    monkeypatch,
):
    """No seeded couple_intake → seeded_form_id=None reaches the notify
    helper, so the bell still rings (just no action button)."""
    ca, captured, _, forms_coll = _make_couple_auth_module(
        monkeypatch, seeded_doc=None, distribution_doc=None
    )

    await ca._dispatch_couple_portal_accepted_notification(
        {
            "planner_id": "planner-1",
            "planner_email": "planner@example.com",
            "email": "couple@example.com",
            "couple_names": "Alex & Jamie",
            "wedding_id": "w-1",
        }
    )

    assert captured["seeded_form_id"] is None
    assert captured["couple_email"] == "couple@example.com"


@pytest.mark.asyncio
async def test_dispatch_no_ops_when_planner_id_missing(monkeypatch):
    """Defensive: a malformed couple doc without any planner identifier
    must not raise — the user-facing setup_password flow continues."""
    ca, captured, _, _ = _make_couple_auth_module(
        monkeypatch, seeded_doc=None, distribution_doc=None
    )

    await ca._dispatch_couple_portal_accepted_notification(
        {"email": "couple@example.com"}
    )

    assert captured == {}


@pytest.mark.asyncio
async def test_dispatch_prefers_planner_email_over_objectid_planner_id(monkeypatch):
    """Notification fan-out queries by email — passing an ObjectId-style
    planner_id silently drops the toast. The dispatcher must prefer
    planner_email even when both fields are present."""
    ca, captured, _, _ = _make_couple_auth_module(
        monkeypatch, seeded_doc=None, distribution_doc=None
    )

    await ca._dispatch_couple_portal_accepted_notification(
        {
            "email": "couple@example.com",
            "planner_id": "507f1f77bcf86cd799439011",  # ObjectId-style
            "planner_email": "real-planner@example.com",
        }
    )

    assert captured.get("planner_id") == "real-planner@example.com", (
        "Dispatcher must use planner_email as the notification key, "
        "even when the legacy planner_id field is also set"
    )


@pytest.mark.asyncio
async def test_dispatch_falls_back_to_legacy_id_when_no_email(monkeypatch):
    """Strictly-legacy rows without planner_email still get a best-
    effort delivery via the legacy id (the team-fanout helper degrades
    gracefully on a non-email key)."""
    ca, captured, _, _ = _make_couple_auth_module(
        monkeypatch, seeded_doc=None, distribution_doc=None
    )

    await ca._dispatch_couple_portal_accepted_notification(
        {
            "email": "couple@example.com",
            "planner_id": "507f1f77bcf86cd799439011",
        }
    )

    assert captured.get("planner_id") == "507f1f77bcf86cd799439011"
