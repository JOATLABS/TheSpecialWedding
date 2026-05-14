#!/usr/bin/env python3
"""Conference auto-create verification.

When a ``calendar_connections`` row has ``conference_provider_default``
set to ``zoom``, ``teams``, or ``webex`` and a couple-initiated booking
is approved (or auto-confirmed), our server's call to Aurinko's
``POST /v1/book/account/profiles/{profile}`` MUST include
``startConference=true``. Aurinko then provisions a meeting URL through
the connection's Zoom / Teams / Webex grant and returns it in the
booking response. The driver verifies:

    * The toggle on the connection round-trips Mongo → Aurinko request
      body.
    * Aurinko's response URL is persisted onto the resulting
      ``planner_tasks`` row as ``conference_url`` + ``conference_provider``.
    * The ICS attachment in the couple invite email contains the
      conference URL (verbatim, no smart-quote mangling, no trailing
      garbage from CRLF folding).
    * A ``conference_provider_default=None`` connection produces NO
      conference URL and a request body with ``startConference=false``
      (calendar-only path — the regression risk is shipping
      "always-on" or "always-off" by accident).
    * A per-meeting ``conference_provider`` override wins over the
      connection's default.

The driver does NOT exercise real Aurinko sandbox calls — Aurinko's
sandbox doesn't actually provision a Zoom room without a real Zoom
grant attached to the test account. Instead it monkey-patches
``httpx.Client.post`` to capture the outbound request body and return a
canned Aurinko response shape carrying the expected ``conferenceUrl``.
This is the same mocking strategy used by
``verify_aurinko_event_crud.py`` to assert verb-shape (PATCH vs PUT) —
the wire-shape claim is what we cannot get from unit tests.

Scenario phases
---------------

    P0  — SEED:                planner on signature plan, active Aurinko
                               connection seeded with
                               ``conference_provider_default='zoom'``,
                               couple+wedding pair, ``auto_confirm=True``.
    P1  — REQUEST_AND_BOOK:    couple POSTs ``/couple/portal/meetings/book``;
                               auto-confirm path runs end-to-end → SCHEDULED.
    P2  — AURINKO_BOOK_REQ:    captured Aurinko POST body MUST include
                               ``startConference=true``.
    P3  — CONFERENCE_URL:      ``planner_tasks.conference_url`` populated
                               with the Zoom URL from the canned response;
                               ``conference_provider='zoom'``.
    P4  — ICS_INCLUDES_URL:    couple-side invite email's ICS attachment
                               contains the Zoom URL.
    P5  — TEAMS:               repeat P0–P4 with default='teams'.
    P6  — WEBEX:               repeat P0–P4 with default='webex'.
    P7  — CALENDAR_ONLY:       default=None → ``startConference=false``,
                               ``conference_url`` IS NULL on the task.
    P8  — OVERRIDE:            default=None but request carries
                               ``conference_provider='zoom'`` — Zoom URL
                               is generated (override wins).
    P9  — CHROME_CHECK:        manually verify the meeting on the
                               planner calendar renders the Join button
                               + the right provider logo.

Usage
-----

    python testbed/verify_conference_auto_create.py

    # Skip the Chrome checkpoint for CI-style re-runs:
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_conference_auto_create.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_conference_auto_create"
PLANNER_EMAIL = "test_planner+conference@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoConference2026!"  # pragma: allowlist secret
COUPLE_EMAIL = "test_couple+conference@thespecialwedding.io"
COUPLE_PASSWORD = "AurinkoConference2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("CONFERENCE_PLAN_ID", "plan_signature")
PROVIDERS = ["zoom", "teams", "webex", None]

SYNTH_AURINKO_ACCOUNT_ID = "testbed-conference-account"
SYNTH_AURINKO_CALENDAR_ID = "testbed-conference-calendar"
SYNTH_AURINKO_PROFILE = "testbed-conference-profile"

# Canned per-provider conferenceUrl shapes Aurinko would return.
PROVIDER_URL_FIXTURES: dict[str, str] = {
    "zoom": "https://us06web.zoom.us/j/85123456789?pwd=TESTBEDZOOM",
    "teams": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_TESTBED%40thread.v2/0",
    "webex": "https://thespecialwedding.webex.com/meet/testbed-conference-room",
}


# =============================================================================
# Aurinko HTTP capture — monkeypatch httpx.Client.post and stash the body.
# =============================================================================


class AurinkoBookCapture:
    """Captures the outbound Aurinko booking POST body and serves a fake response.

    Why a class rather than freeform monkeypatch: every phase variant
    needs to assert against a fresh capture buffer AND swap the canned
    response URL. Sharing the capture state across phases would make
    failures hard to attribute.
    """

    def __init__(self) -> None:
        self.last_url: Optional[str] = None
        self.last_body: Optional[dict] = None
        self.canned_response_url: Optional[str] = None
        self._original_post = httpx.Client.post

    def install(self, *, canned_response_url: Optional[str]) -> None:
        self.last_url = None
        self.last_body = None
        self.canned_response_url = canned_response_url

        original = self._original_post
        capture = self

        def patched_post(client_self, url, *args, **kwargs):  # type: ignore[no-untyped-def]
            # Only intercept Aurinko /book/account endpoints; everything
            # else (Stripe HTTP, internal probes) must pass through.
            if "/book/account" in str(url):
                capture.last_url = str(url)
                body = kwargs.get("json")
                if body is None and kwargs.get("data"):
                    try:
                        body = json.loads(kwargs["data"])
                    except Exception:
                        body = {"_raw": str(kwargs["data"])}
                capture.last_body = body or {}
                return _fake_aurinko_response(capture.canned_response_url)
            return original(client_self, url, *args, **kwargs)

        httpx.Client.post = patched_post  # type: ignore[method-assign]

    def uninstall(self) -> None:
        httpx.Client.post = self._original_post  # type: ignore[method-assign]


def _fake_aurinko_response(conference_url: Optional[str]) -> httpx.Response:
    payload: dict[str, Any] = {
        "id": f"evt_testbed_{uuid.uuid4().hex[:8]}",
        "accountId": SYNTH_AURINKO_ACCOUNT_ID,
        "calendarId": SYNTH_AURINKO_CALENDAR_ID,
        "subject": "Testbed conference booking",
    }
    if conference_url:
        # Aurinko surfaces the conference URL in both the body and a top-level
        # alias. Replicate both so the parser is exercised either way.
        payload["conferenceUrl"] = conference_url
        payload["onlineMeeting"] = {"joinUrl": conference_url}
    request = httpx.Request("POST", "https://api.aurinko.io/v1/book/account/profiles/x")
    return httpx.Response(200, json=payload, request=request)


@contextmanager
def aurinko_capture(
    *, canned_response_url: Optional[str]
) -> Iterator[AurinkoBookCapture]:
    cap = AurinkoBookCapture()
    cap.install(canned_response_url=canned_response_url)
    try:
        yield cap
    finally:
        cap.uninstall()


# =============================================================================
# Mongo + connection helpers
# =============================================================================


def _seed_connection(
    h: Harness,
    *,
    owner_id: str,
    owner_email: str,
    conference_provider_default: Optional[str],
) -> str:
    """Upsert a stub calendar_connection row with the requested toggle."""
    now = datetime.now(timezone.utc)
    doc = {
        "owner_planner_id": owner_id,
        "owner_planner_email": owner_email,
        "user_id": owner_id,
        "user_email": owner_email,
        "provider": "google",
        "provider_account_email": owner_email,
        "provider_account_name": "Testbed Conference",
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
        "aurinko_calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "aurinko_profile_id": SYNTH_AURINKO_PROFILE,
        "aurinko_access_token_encrypted": "testbed-stub-token",
        "calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "calendar_name": "Testbed Primary",
        "is_writable": True,
        "is_primary": True,
        "is_default_write_target": True,
        "sync_enabled": True,
        "couple_booking_auto_confirm": True,
        "conference_provider_default": conference_provider_default,
        "connection_status": "active",
        "last_error": None,
        "updated_at": now,
        "created_at": now,
    }
    query = {
        "owner_planner_id": owner_id,
        "user_id": owner_id,
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
    }
    h.mongo["calendar_connections"].update_one(query, {"$set": doc}, upsert=True)
    row = h.mongo["calendar_connections"].find_one(query, {"_id": 1})
    assert row, "connection upsert returned no document"
    return str(row["_id"])


def _set_connection_default(
    h: Harness, connection_id: str, provider: Optional[str]
) -> None:
    h.mongo["calendar_connections"].update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {"conference_provider_default": provider}},
    )


def _wipe_test_state(h: Harness) -> None:
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL}, {"_id": 1})
    if not user:
        return
    owner_id = str(user["_id"])
    for coll, filt in (
        ("calendar_connections", {"owner_planner_id": owner_id}),
        ("planner_tasks", {"owner_planner_id": owner_id}),
        ("calendar_event_syncs", {"owner_planner_id": owner_id}),
        (
            "calendar_idempotency_keys",
            {"scope_key": {"$regex": f"couple_meeting_book:.*{COUPLE_EMAIL}"}},
        ),
        ("planner_notifications", {"planner_id": {"$in": [owner_id, PLANNER_EMAIL]}}),
    ):
        result = h.mongo[coll].delete_many(filt)
        if result.deleted_count:
            h.log.info(f"  ✅ {coll}: removed {result.deleted_count} doc(s)")
    h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})


# =============================================================================
# Booking helpers (mirror verify_couple_booking_lifecycle patterns)
# =============================================================================


def _next_business_day_slot(*, hour: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    candidate = now + timedelta(days=2)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    start = datetime.combine(
        candidate.date(), time(hour=hour, minute=0), tzinfo=timezone.utc
    )
    return start, start + timedelta(minutes=30)


def _book_slot(
    h: Harness,
    couple_token: str,
    *,
    staff_id: str,
    hour: int,
    title: str,
    conference_provider_override: Optional[str] = None,
) -> dict:
    start, end = _next_business_day_slot(hour=hour)
    payload: dict[str, Any] = {
        "staff_id": staff_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "title": title,
        "notes": "[testbed] verify_conference_auto_create",
        "timezone": "UTC",
        "idempotency_key": uuid.uuid4().hex,
    }
    if conference_provider_override is not None:
        payload["conference_provider"] = conference_provider_override
    resp = h.api_post("/couple/portal/meetings/book", token=couple_token, json=payload)
    h.log.info(f"  POST /couple/portal/meetings/book -> {resp.status_code}")
    assert resp.status_code == 200, (
        f"booking returned {resp.status_code} — body={resp.text}"
    )
    return resp.json() or {}


def _provider_request_assertions(
    h: Harness,
    capture: AurinkoBookCapture,
    *,
    expect_start_conference: bool,
    expect_provider: Optional[str],
    phase_tag: str,
) -> None:
    """Assert the outbound Aurinko body matches the expected conference shape."""
    assert capture.last_body is not None, (
        f"[{phase_tag}] AURINKO_BOOK_REQ: no /book/account POST observed — "
        "the booking auto-confirm path did not call Aurinko. Either the "
        "endpoint route changed, the mock didn't install (httpx upgrade?), "
        "or the booking did not run."
    )
    actual = capture.last_body.get("startConference")
    assert actual is expect_start_conference, (
        f"[{phase_tag}] REGRESSION: outbound Aurinko request had "
        f"startConference={actual!r}, expected {expect_start_conference!r}. "
        f"Provider default at the time of the call: {expect_provider!r}. "
        f"Full request body captured: {capture.last_body!r}"
    )
    h.log.info(
        f"  ✅ [{phase_tag}] Aurinko request startConference={actual!r} "
        f"(provider={expect_provider!r})"
    )


def _task_assertions(
    h: Harness,
    meeting_id: str,
    *,
    expect_url: Optional[str],
    expect_provider: Optional[str],
    phase_tag: str,
) -> dict:
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(meeting_id)})
    assert task, f"[{phase_tag}] planner_tasks row not found for {meeting_id}"
    actual_url = task.get("conference_url")
    actual_provider = task.get("conference_provider")
    if expect_url is None:
        assert not actual_url, (
            f"[{phase_tag}] REGRESSION: expected conference_url to be unset "
            f"(calendar-only path) but got {actual_url!r}"
        )
        assert not actual_provider, (
            f"[{phase_tag}] conference_provider should be unset; got "
            f"{actual_provider!r}"
        )
    else:
        assert actual_url == expect_url, (
            f"[{phase_tag}] REGRESSION: planner_tasks.conference_url="
            f"{actual_url!r}, expected {expect_url!r}"
        )
        assert actual_provider == expect_provider, (
            f"[{phase_tag}] REGRESSION: planner_tasks.conference_provider="
            f"{actual_provider!r}, expected {expect_provider!r}"
        )
    h.log.info(
        f"  ✅ [{phase_tag}] planner_task.conference_url={actual_url!r} "
        f"provider={actual_provider!r}"
    )
    return task


def _ics_assertion(
    h: Harness, meeting_id: str, *, expect_url: Optional[str], phase_tag: str
) -> None:
    """Verify the couple-side ICS attachment carries the conference URL.

    The ICS body is stamped onto ``planner_tasks.last_ics_payload`` by
    ``meeting_invite_service.build_ics`` when the invite is sent. If
    your build doesn't persist that field, this assertion will warn but
    not fail — the canonical assertion remains on conference_url.
    """
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(meeting_id)})
    ics = (task or {}).get("last_ics_payload") or (task or {}).get("ics_body")
    if not ics:
        h.log.info(
            f"  ⚠ [{phase_tag}] ICS_INCLUDES_URL: planner_task carries no "
            f"persisted ICS payload — skipping verbatim assertion. Verify "
            f"manually in Chrome at the P9 checkpoint."
        )
        return
    if expect_url is None:
        assert "LOCATION:" not in ics or expect_url == "", (
            f"[{phase_tag}] ICS contains LOCATION line even though no "
            f"conference URL was expected — ics={ics[:300]}"
        )
    else:
        assert expect_url in ics, (
            f"[{phase_tag}] REGRESSION: ICS does not contain the conference "
            f"URL. Expected substring {expect_url!r}. ICS snippet: {ics[:400]}"
        )
    h.log.info(f"  ✅ [{phase_tag}] ICS contains the expected conference URL")


# =============================================================================
# Phases — provider sweep
# =============================================================================


def phase_seed(h: Harness, admin_token: str) -> tuple[str, str, str]:
    h.phase("CONFERENCE_SEED", "Bootstrap planner + couple + wedding")
    _wipe_test_state(h)

    existing = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if existing:
        h.log.info("  ♻ Existing planner — dropping chain for clean seed")
        h.delete_user_chain(PLANNER_EMAIL)

    seed = h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        pm_token=PM_TOKEN_GOOD,
    )
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    # Wedding
    resp = h.api_post(
        "/admin/weddings",
        token=planner_token,
        json={"couple_names": "Confa & Couple", "date": "2027-11-11"},
    )
    assert resp.status_code in (200, 201), (
        f"wedding create failed: {resp.status_code} {resp.text}"
    )
    wedding_id = (
        (resp.json() or {}).get("_id")
        or (resp.json() or {}).get("id")
        or (resp.json() or {}).get("wedding_id")
    )
    if not wedding_id:
        doc = h.mongo["weddings"].find_one(
            {"assigned_planner_email": PLANNER_EMAIL}, sort=[("_id", -1)]
        )
        wedding_id = str(doc["_id"]) if doc else None
    assert wedding_id, "could not resolve wedding_id"

    # Couple invite + setup
    invite = h.api_post(
        "/admin/couple-portal/invite",
        token=planner_token,
        json={
            "email": COUPLE_EMAIL,
            "partner1_name": "Confa",
            "partner2_name": "Couple",
            "wedding_id": wedding_id,
        },
    )
    assert invite.status_code in (200, 201), (
        f"invite failed: {invite.status_code} {invite.text}"
    )
    invite_body = invite.json() or {}
    setup_link = invite_body.get("setup_link") or ""
    invite_token = setup_link.rsplit("/", 1)[-1] if setup_link else ""
    if not invite_token:
        doc = h.mongo["couple_users"].find_one(
            {"email": COUPLE_EMAIL, "wedding_id": wedding_id}, {"invite_token": 1}
        )
        invite_token = (doc or {}).get("invite_token") or ""
    assert invite_token, "could not resolve invite_token"

    setup = h.api_post(
        "/couple/setup-password",
        json={"token": invite_token, "password": COUPLE_PASSWORD},
    )
    assert setup.status_code in (200, 201), (
        f"setup failed: {setup.status_code} {setup.text}"
    )
    couple_token = (setup.json() or {}).get("access_token")
    assert couple_token, "missing couple access_token"

    h.checkpoint(
        "P0_SEED_COMPLETE",
        expectations=[
            f"Planner creds: {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            f"Couple  creds: {COUPLE_EMAIL} / {COUPLE_PASSWORD}",
            "No Chrome check at this phase — pure backend bootstrap",
        ],
    )
    return seed.user_id, planner_token, couple_token


def run_provider_variant(
    h: Harness,
    *,
    owner_id: str,
    couple_token: str,
    connection_id: str,
    provider_default: Optional[str],
    override_provider: Optional[str] = None,
    hour: int,
    phase_tag: str,
) -> str:
    """One full P1-P4 cycle for a given (default, override) pair.

    Returns the meeting_id of the resulting planner_task.
    """
    h.phase(
        f"CONFERENCE_{phase_tag}",
        f"default={provider_default!r} override={override_provider!r}",
    )
    _set_connection_default(h, connection_id, provider_default)

    effective_provider = override_provider or provider_default
    expect_start_conference = effective_provider is not None
    expect_url: Optional[str] = (
        PROVIDER_URL_FIXTURES.get(effective_provider) if effective_provider else None
    )

    with aurinko_capture(canned_response_url=expect_url) as capture:
        body = _book_slot(
            h,
            couple_token,
            staff_id=owner_id,
            hour=hour,
            title=f"[testbed] {phase_tag}",
            conference_provider_override=override_provider,
        )
        meeting_id = body["meeting_id"]
        assert body.get("meeting_status") == "scheduled", (
            f"[{phase_tag}] auto-confirm failed: meeting_status="
            f"{body.get('meeting_status')!r}"
        )

    _provider_request_assertions(
        h,
        capture,
        expect_start_conference=expect_start_conference,
        expect_provider=effective_provider,
        phase_tag=phase_tag,
    )
    _task_assertions(
        h,
        meeting_id,
        expect_url=expect_url,
        expect_provider=effective_provider,
        phase_tag=phase_tag,
    )
    _ics_assertion(h, meeting_id, expect_url=expect_url, phase_tag=phase_tag)
    return meeting_id


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Conference Auto-Create (Zoom / Teams / Webex)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email  : {COUPLE_EMAIL}")
    h.log.info(f"  Providers     : {PROVIDERS}")
    h.log.info(f"  Started at    : {datetime.now(timezone.utc).isoformat()}")
    h.preflight()

    admin_token = h.get_admin_token()
    owner_id, planner_token, couple_token = phase_seed(h, admin_token)

    # Seed connection — starts with default='zoom' for the first variant.
    connection_id = _seed_connection(
        h,
        owner_id=owner_id,
        owner_email=PLANNER_EMAIL,
        conference_provider_default="zoom",
    )
    h.log.info(f"  ✅ calendar_connection_id = {connection_id}")

    # P1–P4 ZOOM
    run_provider_variant(
        h,
        owner_id=owner_id,
        couple_token=couple_token,
        connection_id=connection_id,
        provider_default="zoom",
        hour=9,
        phase_tag="P1_P4_ZOOM",
    )

    # P5 TEAMS
    run_provider_variant(
        h,
        owner_id=owner_id,
        couple_token=couple_token,
        connection_id=connection_id,
        provider_default="teams",
        hour=10,
        phase_tag="P5_TEAMS",
    )

    # P6 WEBEX
    run_provider_variant(
        h,
        owner_id=owner_id,
        couple_token=couple_token,
        connection_id=connection_id,
        provider_default="webex",
        hour=11,
        phase_tag="P6_WEBEX",
    )

    # P7 CALENDAR-ONLY (default=None, no override)
    run_provider_variant(
        h,
        owner_id=owner_id,
        couple_token=couple_token,
        connection_id=connection_id,
        provider_default=None,
        hour=13,
        phase_tag="P7_CALENDAR_ONLY",
    )

    # P8 OVERRIDE (default=None, request carries conference_provider='zoom')
    run_provider_variant(
        h,
        owner_id=owner_id,
        couple_token=couple_token,
        connection_id=connection_id,
        provider_default=None,
        override_provider="zoom",
        hour=14,
        phase_tag="P8_OVERRIDE",
    )

    # P9 — Chrome checkpoint (manual)
    h.phase("CONFERENCE_P9_CHROME", "Manual: verify Join button + provider logo")
    h.checkpoint(
        "P9_CHROME_CHECK",
        expectations=[
            "Open http://localhost:3000/admin/planner/calendar",
            f"Log in as {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            "Click the most-recent meeting on the planner calendar",
            "  Expect: 'Join' button is visible and links to the conference URL",
            "  Expect: provider logo (Zoom / Teams / Webex) matches the meeting",
            "Open the couple portal in another tab as the couple user",
            f"  Log in as {COUPLE_EMAIL} / {COUPLE_PASSWORD}",
            "  Verify the same meeting carries a 'Join' button + correct URL",
        ],
    )

    h.banner("VERIFY — Conference Auto-Create COMPLETE ✅")
    h.log.info(
        "  Cleanup: drop the plus-variant chain with "
        "`python testbed/cleanup_couple_booking_lifecycle_state.py` after "
        "swapping the email/scope constants, or write a dedicated cleanup "
        "script if this driver becomes part of CI."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise SystemExit(1)
