"""Tests for ``FormService.get_seeded_form_id`` and the new
``GET /admin/forms/seeded/{catalog_template_id}`` endpoint (Chunk 4).

The action-button toast in the planner UI relies on this lookup to
resolve a stable catalog id (``couple_intake``) to the planner's
actual seeded form_id, so it can call ``POST /admin/forms/{form_id}/send``
without scanning the planner's workspace.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from importlib import reload
from pathlib import Path

import mongomock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

import app.services.form_service as form_service_module  # noqa: E402


class _Cursor:
    def __init__(self, cursor):
        self.c = cursor

    def sort(self, *a, **kw):
        self.c.sort(*a, **kw)
        return self

    def skip(self, *a, **kw):
        self.c.skip(*a, **kw)
        return self

    def limit(self, *a, **kw):
        self.c.limit(*a, **kw)
        return self

    async def to_list(self, length=None):
        return list(self.c)


class _Collection:
    def __init__(self, c):
        self.c = c

    def find(self, *a, **kw):
        return _Cursor(self.c.find(*a, **kw))

    async def find_one(self, *a, **kw):
        return self.c.find_one(*a, **kw)

    async def insert_one(self, *a, **kw):
        return self.c.insert_one(*a, **kw)

    async def update_one(self, *a, **kw):
        return self.c.update_one(*a, **kw)

    async def update_many(self, *a, **kw):
        return self.c.update_many(*a, **kw)

    async def count_documents(self, *a, **kw):
        return self.c.count_documents(*a, **kw)


class _DB:
    def __init__(self, db):
        self._db = db
        self._wraps = {}

    def __getitem__(self, name):
        if name not in self._wraps:
            self._wraps[name] = _Collection(self._db[name])
        return self._wraps[name]


class _FakeMongo:
    def __init__(self, db):
        self.db = _DB(db)

    def get_forms_collection(self):
        return self.db["forms"]


@pytest.fixture
def configured_form_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    monkeypatch.setattr(form_service_module, "mongo", _FakeMongo(database))
    monkeypatch.setattr(
        form_service_module.rate_limiter,
        "check_rate_limit",
        lambda *a, **kw: True,
    )
    service = form_service_module.FormService()
    return service, database


def _seed_form(database, *, form_id, planner, catalog_id):
    now = datetime.utcnow()
    database["forms"].insert_one(
        {
            "_id": form_id,
            "name": catalog_id.replace("_", " ").title(),
            "settings": {},
            "fields": [],
            "created_by": planner,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "submission_count": 0,
            "planner_state": {},
            "seeded_from_catalog": True,
            "catalog_template_id": catalog_id,
        }
    )


@pytest.mark.asyncio
async def test_get_seeded_form_returns_planner_owned_form(
    configured_form_service,
):
    service, database = configured_form_service
    _seed_form(
        database,
        form_id="form-seed-couple-1",
        planner="planner@example.com",
        catalog_id="couple_intake",
    )

    result = await service.get_seeded_form_id(
        "couple_intake", created_by="planner@example.com"
    )

    assert result["form_id"] == "form-seed-couple-1"


@pytest.mark.asyncio
async def test_get_seeded_form_returns_404_when_planner_has_no_seed(
    configured_form_service,
):
    service, database = configured_form_service
    # Different planner has the seed; ours doesn't.
    _seed_form(
        database,
        form_id="other-planner-form",
        planner="other@example.com",
        catalog_id="couple_intake",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_seeded_form_id(
            "couple_intake", created_by="planner@example.com"
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_seeded_form_rejects_unknown_template_id(
    configured_form_service,
):
    service, database = configured_form_service
    with pytest.raises(HTTPException) as exc_info:
        await service.get_seeded_form_id(
            "totally_made_up_id", created_by="planner@example.com"
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_seeded_form_isolated_per_planner(configured_form_service):
    """Planner A's seed must not be visible to Planner B."""
    service, database = configured_form_service
    _seed_form(
        database,
        form_id="form-A",
        planner="planner_a@example.com",
        catalog_id="couple_intake",
    )
    _seed_form(
        database,
        form_id="form-B",
        planner="planner_b@example.com",
        catalog_id="couple_intake",
    )

    a_result = await service.get_seeded_form_id(
        "couple_intake", created_by="planner_a@example.com"
    )
    b_result = await service.get_seeded_form_id(
        "couple_intake", created_by="planner_b@example.com"
    )
    assert a_result["form_id"] == "form-A"
    assert b_result["form_id"] == "form-B"


@pytest.mark.asyncio
async def test_get_seeded_form_team_member_inherits_owner_seed(
    configured_form_service,
):
    """A team member with manage_forms resolves the parent planner's
    seed via owner_alias_emails (the same pattern _resolve_form_owner_scope
    threads through every form lookup in the codebase)."""
    service, database = configured_form_service
    _seed_form(
        database,
        form_id="form-owner-seed",
        planner="owner@example.com",
        catalog_id="couple_intake",
    )

    # _resolve_form_owner_scope (the API caller) always includes the
    # owner email itself in owner_alias_emails plus any team members.
    # Mirror that here.
    result = await service.get_seeded_form_id(
        "couple_intake",
        created_by="owner@example.com",
        owner_alias_emails=["owner@example.com", "team_member@example.com"],
    )
    assert result["form_id"] == "form-owner-seed"


@pytest.mark.asyncio
async def test_get_seeded_form_does_not_match_non_seeded_forms(
    configured_form_service,
):
    """A planner-authored form with the same catalog_template_id but
    seeded_from_catalog missing/false must NOT match — the seed marker
    is how we distinguish auto-loaded from manually-cloned templates."""
    service, database = configured_form_service
    now = datetime.utcnow()
    database["forms"].insert_one(
        {
            "_id": "form-manual",
            "name": "Manual",
            "settings": {},
            "fields": [],
            "created_by": "planner@example.com",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "submission_count": 0,
            "planner_state": {},
            # Note: no seeded_from_catalog flag
            "catalog_template_id": "couple_intake",
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.get_seeded_form_id(
            "couple_intake", created_by="planner@example.com"
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# API-level permission-gate regression
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client(monkeypatch):
    """Build a FastAPI TestClient mounting the forms router under
    /admin and replacing the auth dependency, so we can exercise the
    permission gate on the seeded-lookup endpoint directly."""
    client = mongomock.MongoClient()
    database = client["wedding_forms"]

    import app.services.form_service as fsm

    reload(fsm)
    monkeypatch.setattr(fsm, "mongo", _FakeMongo(database))
    monkeypatch.setattr(fsm.rate_limiter, "check_rate_limit", lambda *a, **kw: True)

    import app.api.forms as forms_module

    reload(forms_module)
    monkeypatch.setattr(forms_module, "form_service", fsm.FormService())
    monkeypatch.setattr(
        forms_module.rate_limiter, "check_rate_limit", lambda *a, **kw: True
    )

    async def _noop_security_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        forms_module.security_audit, "log_security_event", _noop_security_audit
    )

    app = FastAPI()
    app.include_router(forms_module.router, prefix="/admin")
    test_client = TestClient(app)

    def override_user(user):
        async def _override():
            return user

        app.dependency_overrides[forms_module.require_team_or_planner] = _override

    yield test_client, database, forms_module, override_user

    app.dependency_overrides.clear()


def test_seeded_lookup_rejects_team_member_without_manage_forms(api_client):
    """A team member whose permission map lacks ``manage_forms`` must
    receive 403 from ``GET /admin/forms/seeded/{catalog_template_id}``,
    even though ``require_team_or_planner`` would otherwise admit them."""
    client, database, forms_module, override_user = api_client

    _seed_form(
        database,
        form_id="form-seeded-couple",
        planner="owner@example.com",
        catalog_id="couple_intake",
    )

    team_member = forms_module.ExtendedAuthUser(
        email="team@example.com",
        role="team_member",
        user_data={
            "role": "team_member",
            "team_owner_email": "owner@example.com",
        },
    )
    # Explicit empty permissions dict — no manage_forms.
    team_member.team_permissions = {"manage_forms": False}
    team_member.team_owner_email = "owner@example.com"
    override_user(team_member)

    response = client.get("/admin/forms/seeded/couple_intake")

    assert response.status_code == 403
    assert "manage forms" in response.json()["detail"].lower()
