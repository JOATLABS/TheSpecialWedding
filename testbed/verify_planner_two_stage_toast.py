#!/usr/bin/env python3
"""
Two-Stage Planner Notification Lifecycle — Live Verification
============================================================

Exercises the two-stage wedding-checklist nudge that surfaces the
planner-side action toasts:

  Stage 1 — POST /admin/weddings → notify_wedding_created
            → bell entry + SSE ``notification-new`` (type
            ``wedding_created``); toast prompts the planner to invite
            the couple.
  Stage 2 — POST /couple/setup-password → notify_couple_portal_accepted
            → bell entry + SSE (type ``couple_portal_accepted``)
            carrying ``form_id`` (the seeded couple_intake) and
            ``couple_email`` in metadata so the toast can one-click
            send the wedding checklist.

The driver pairs each Stage with **right-logic** (positive) and
**false-positive/negative** assertions: dedup against an existing
``form_distributions`` row, team-member fan-out gated on permission
flags, and the cross-planner ownership gate on
``PUT /admin/planner/activity-notifications/{id}/actioned``.

Phases — every UX-observable transition is ENTER-gated so the human
can inspect the bell + SSE in dev tools between each stage:
  SEED        — planner + 3 team members (manage_couple_portal,
                manage_forms, neither) + couple invite, idempotent.
  CHECKPOINT 1 — Stage 1 fan-out (planner + portal team member only).
  CHECKPOINT 2 — Stage 2 fan-out (planner + forms team member only).
  CHECKPOINT 3 — Stage 2 dedup against pre-seeded form_distributions.
  CHECKPOINT 4 — mark-actioned flips actioned_at + actioned_via_action_button.
  CHECKPOINT 5 — cross-planner mark-actioned attempt → 404.
  CHECKPOINT 6 — mark-actioned idempotent (second call → 200, doc untouched).

Pair: cleanup_planner_two_stage_toast_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    TWO_STAGE_TOAST,
    banner,
    checkpoint_pause,
    count_documents,
    get_async_mongo,
    insert_one,
    now_utc,
    short_token,
)


# ---------------------------------------------------------------------------
# Plus-tagged identities — every row created by this driver is reachable
# from cleanup via one of these emails.
# ---------------------------------------------------------------------------

PLANNER_EMAIL = TWO_STAGE_TOAST.email  # test_planner+toast_lifecycle@…
PLANNER_B_EMAIL = "test_planner+toast_lifecycle_other@thespecialwedding.io"
TEAM_FORMS_EMAIL = "test_team_forms+toast_lifecycle@thespecialwedding.io"
TEAM_PORTAL_EMAIL = "test_team_portal+toast_lifecycle@thespecialwedding.io"
TEAM_NEITHER_EMAIL = "test_team_neither+toast_lifecycle@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+toast_lifecycle@thespecialwedding.io"

ALL_TAG_EMAILS: List[str] = [
    PLANNER_EMAIL,
    PLANNER_B_EMAIL,
    TEAM_FORMS_EMAIL,
    TEAM_PORTAL_EMAIL,
    TEAM_NEITHER_EMAIL,
    COUPLE_EMAIL,
]


# ---------------------------------------------------------------------------
# SEED helpers — each is idempotent: existing rows get $set instead of
# blowing up on a unique-key collision.
# ---------------------------------------------------------------------------


async def upsert_planner(email: str) -> None:
    mongo = get_async_mongo()
    await mongo.db["users"].update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "role": "planner",
                "subscription_status": "active",
                "is_email_verified": True,
                "updated_at": now_utc(),
            },
            "$setOnInsert": {
                "created_at": now_utc(),
                "name": "Two-Stage Toast Planner",
            },
        },
        upsert=True,
    )


async def upsert_team_member(
    *, owner_email: str, email: str, role: str, custom: Dict[str, bool]
) -> None:
    mongo = get_async_mongo()
    await mongo.db["team_members"].update_one(
        {"owner_email": owner_email, "email": email},
        {
            "$set": {
                "owner_email": owner_email,
                "email": email,
                "role": role,
                "custom_permissions": custom,
                "status": "active",
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"created_at": now_utc()},
        },
        upsert=True,
    )


async def upsert_seeded_couple_intake_form(planner_email: str) -> str:
    """Seed (or refresh) the planner's catalog couple_intake form.

    The Stage 2 dispatcher in ``app/api/couple_auth.py`` looks up
    ``forms`` filtered by ``created_by`` + ``seeded_from_catalog`` +
    ``catalog_template_id == couple_intake``; this matches that lookup
    so the seeded_form_id flows into the notification metadata.
    """
    mongo = get_async_mongo()
    existing = await mongo.db["forms"].find_one(
        {
            "created_by": planner_email,
            "seeded_from_catalog": True,
            "catalog_template_id": "couple_intake",
        },
        {"_id": 1},
    )
    if existing:
        return str(existing["_id"])

    form_id = f"verify_toast_intake_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Couple Intake (verifier seed)",
            "form_type": "couple_intake",
            "settings": {
                "title": "Couple Intake",
                "description": "Verifier-seeded couple_intake template.",
                "is_public": False,
                "requires_auth": True,
            },
            "fields": [
                {
                    "id": "names",
                    "label": "Couple names",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": planner_email,
            "wedding_id": None,
            "is_active": True,
            "seeded_from_catalog": True,
            "catalog_template_id": "couple_intake",
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
        },
    )
    return form_id


async def upsert_couple_invite(
    *, planner_email: str, couple_email: str, wedding_id: str
) -> str:
    """Create the couple-portal invite row that ``setup-password``
    will flip to active. We seed it in ``pending_setup`` state with an
    invite token so the verifier can either drive the public endpoint
    OR, in CHECKPOINT 3, call the dispatch helper directly.
    """
    mongo = get_async_mongo()
    invite_token = f"verify_toast_invite_{short_token()}"
    await mongo.db["couple_users"].update_one(
        {"email": couple_email},
        {
            "$set": {
                "email": couple_email,
                "planner_email": planner_email,
                "wedding_id": wedding_id,
                "couple_names": "Alex & Jordan",
                "portal_state": "pending_setup",
                "invite_token": invite_token,
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"created_at": now_utc()},
        },
        upsert=True,
    )
    return invite_token


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


async def count_notif(planner_id: str, ntype: str) -> int:
    return await count_documents(
        "planner_notifications", {"planner_id": planner_id, "type": ntype}
    )


async def fetch_latest_notif(planner_id: str, ntype: str) -> Optional[Dict[str, Any]]:
    mongo = get_async_mongo()
    cursor = (
        mongo.db["planner_notifications"]
        .find({"planner_id": planner_id, "type": ntype})
        .sort("created_at", -1)
        .limit(1)
    )
    docs = [doc async for doc in cursor]
    return docs[0] if docs else None


def assert_eq(label: str, got: Any, want: Any) -> None:
    ok = got == want
    marker = "PASS" if ok else "FAIL"
    print(f"    [{marker}] {label}: got={got!r} want={want!r}")
    if not ok:
        raise AssertionError(f"{label}: got={got!r} want={want!r}")


def assert_truthy(label: str, got: Any) -> None:
    ok = bool(got)
    marker = "PASS" if ok else "FAIL"
    print(f"    [{marker}] {label}: {got!r}")
    if not ok:
        raise AssertionError(f"{label}: falsy value {got!r}")


# ---------------------------------------------------------------------------
# Phase implementations
# ---------------------------------------------------------------------------


async def phase_seed() -> Dict[str, Any]:
    banner("SEED — planner + team members + couple invite")
    await upsert_planner(PLANNER_EMAIL)
    await upsert_planner(PLANNER_B_EMAIL)
    await upsert_team_member(
        owner_email=PLANNER_EMAIL,
        email=TEAM_PORTAL_EMAIL,
        role="viewer",
        custom={"manage_couple_portal": True, "manage_forms": False},
    )
    await upsert_team_member(
        owner_email=PLANNER_EMAIL,
        email=TEAM_FORMS_EMAIL,
        role="viewer",
        custom={"manage_couple_portal": False, "manage_forms": True},
    )
    await upsert_team_member(
        owner_email=PLANNER_EMAIL,
        email=TEAM_NEITHER_EMAIL,
        role="viewer",
        custom={
            "manage_couple_portal": False,
            "manage_forms": False,
            "view_analytics": True,
        },
    )
    seeded_form_id = await upsert_seeded_couple_intake_form(PLANNER_EMAIL)
    wedding_id = f"verify_toast_w_{short_token()}"
    invite_token = await upsert_couple_invite(
        planner_email=PLANNER_EMAIL,
        couple_email=COUPLE_EMAIL,
        wedding_id=wedding_id,
    )
    print(f"  • planner: {PLANNER_EMAIL}")
    print(f"  • planner B (cross-tenant): {PLANNER_B_EMAIL}")
    print(f"  • team [manage_couple_portal]: {TEAM_PORTAL_EMAIL}")
    print(f"  • team [manage_forms]: {TEAM_FORMS_EMAIL}")
    print(f"  • team [neither]: {TEAM_NEITHER_EMAIL}")
    print(f"  • couple: {COUPLE_EMAIL}")
    print(f"  • seeded couple_intake form_id: {seeded_form_id}")
    print(f"  • wedding_id: {wedding_id}")
    print(f"  • invite_token: {invite_token}")
    return {
        "wedding_id": wedding_id,
        "seeded_form_id": seeded_form_id,
        "invite_token": invite_token,
    }


async def phase_checkpoint_1_stage1(state: Dict[str, Any]) -> None:
    banner("CHECKPOINT 1 — Stage 1 fires on wedding create")
    print(
        "  Driver action: invoke notify_wedding_created (mirrors POST /admin/weddings)."
    )

    from app.services.planner_notification_service import (
        planner_notification_service,
    )

    before_planner = await count_notif(PLANNER_EMAIL, "wedding_created")
    before_portal = await count_notif(TEAM_PORTAL_EMAIL, "wedding_created")
    before_forms = await count_notif(TEAM_FORMS_EMAIL, "wedding_created")
    before_neither = await count_notif(TEAM_NEITHER_EMAIL, "wedding_created")

    await planner_notification_service.notify_wedding_created(
        planner_id=PLANNER_EMAIL,
        wedding_id=state["wedding_id"],
        couple_names="Alex & Jordan",
    )

    print("  CHECKPOINT — bell + SSE ``notification-new`` ``wedding_created``:")
    assert_eq(
        "planner Stage 1 row count delta",
        await count_notif(PLANNER_EMAIL, "wedding_created") - before_planner,
        1,
    )
    assert_eq(
        "team[manage_couple_portal] Stage 1 row count delta",
        await count_notif(TEAM_PORTAL_EMAIL, "wedding_created") - before_portal,
        1,
    )
    assert_eq(
        "team[manage_forms] Stage 1 row count delta (must NOT receive)",
        await count_notif(TEAM_FORMS_EMAIL, "wedding_created") - before_forms,
        0,
    )
    assert_eq(
        "team[neither] Stage 1 row count delta (must NOT receive)",
        await count_notif(TEAM_NEITHER_EMAIL, "wedding_created") - before_neither,
        0,
    )

    checkpoint_pause(
        "Stage 1 — wedding_created",
        [
            f"Sign in as {PLANNER_EMAIL} and confirm the bell shows a 'New wedding created' toast pointing at /admin/planner/weddings/{state['wedding_id']}?tab=couple.",
            f"Sign in as {TEAM_PORTAL_EMAIL} (team session) and confirm the same Stage 1 toast lands on their bell.",
            f"Sign in as {TEAM_FORMS_EMAIL} or {TEAM_NEITHER_EMAIL} and confirm NO Stage 1 toast (no manage_couple_portal permission).",
            "DevTools → EventSource: confirm a ``notification-new`` event with type=wedding_created arrived for the planner only at this stage.",
        ],
    )


async def phase_checkpoint_2_stage2(state: Dict[str, Any]) -> None:
    banner("CHECKPOINT 2 — Stage 2 fires on couple portal accept")
    print("  Driver action: dispatch the Stage 2 helper directly (mirrors")
    print("  POST /couple/setup-password completion path).")

    from app.api.couple_auth import _dispatch_couple_portal_accepted_notification

    before_planner = await count_notif(PLANNER_EMAIL, "couple_portal_accepted")
    before_forms = await count_notif(TEAM_FORMS_EMAIL, "couple_portal_accepted")
    before_portal = await count_notif(TEAM_PORTAL_EMAIL, "couple_portal_accepted")
    before_neither = await count_notif(TEAM_NEITHER_EMAIL, "couple_portal_accepted")

    couple_doc = {
        "email": COUPLE_EMAIL,
        "planner_email": PLANNER_EMAIL,
        "wedding_id": state["wedding_id"],
        "couple_names": "Alex & Jordan",
    }
    await _dispatch_couple_portal_accepted_notification(couple_doc)

    print("  CHECKPOINT — bell + SSE ``notification-new`` ``couple_portal_accepted``:")
    assert_eq(
        "planner Stage 2 row count delta",
        await count_notif(PLANNER_EMAIL, "couple_portal_accepted") - before_planner,
        1,
    )
    assert_eq(
        "team[manage_forms] Stage 2 row count delta",
        await count_notif(TEAM_FORMS_EMAIL, "couple_portal_accepted") - before_forms,
        1,
    )
    assert_eq(
        "team[manage_couple_portal] Stage 2 row count delta (must NOT receive)",
        await count_notif(TEAM_PORTAL_EMAIL, "couple_portal_accepted") - before_portal,
        0,
    )
    assert_eq(
        "team[neither] Stage 2 row count delta (must NOT receive)",
        await count_notif(TEAM_NEITHER_EMAIL, "couple_portal_accepted")
        - before_neither,
        0,
    )

    latest = await fetch_latest_notif(PLANNER_EMAIL, "couple_portal_accepted")
    assert_truthy("planner Stage 2 row exists", latest)
    metadata = (latest or {}).get("metadata") or {}
    assert_eq("metadata.form_id", metadata.get("form_id"), state["seeded_form_id"])
    assert_eq("metadata.couple_email", metadata.get("couple_email"), COUPLE_EMAIL)
    assert_eq("metadata.couple_names", metadata.get("couple_names"), "Alex & Jordan")
    state["planner_stage2_id"] = str(latest["_id"]) if latest else None

    checkpoint_pause(
        "Stage 2 — couple_portal_accepted",
        [
            f"As {PLANNER_EMAIL}, confirm the bell shows the 'Alex & Jordan accepted the portal invite' toast with a 'Send checklist' CTA.",
            f"Confirm the toast deep-link points at /admin/forms/{state['seeded_form_id']}/send?prefill_email={COUPLE_EMAIL}.",
            f"As {TEAM_FORMS_EMAIL}, confirm the same Stage 2 toast lands on the team session's bell.",
            f"As {TEAM_PORTAL_EMAIL} or {TEAM_NEITHER_EMAIL}, confirm NO Stage 2 toast.",
            "DevTools → EventSource: confirm ``notification-new`` event with metadata.form_id + metadata.couple_email present.",
        ],
    )


async def phase_checkpoint_3_dedup(state: Dict[str, Any]) -> None:
    banner("CHECKPOINT 3 — Stage 2 dedup against existing form_distributions")
    print(
        "  Pre-seed a form_distributions row, fire Stage 2 again, expect NO new bell row."
    )

    await insert_one(
        "form_distributions",
        {
            "_id": f"verify_toast_dist_{short_token()}",
            "form_id": state["seeded_form_id"],
            "recipient_email": COUPLE_EMAIL,
            "created_by": PLANNER_EMAIL,
            "created_at": now_utc(),
        },
    )

    before_planner = await count_notif(PLANNER_EMAIL, "couple_portal_accepted")
    before_forms = await count_notif(TEAM_FORMS_EMAIL, "couple_portal_accepted")

    from app.api.couple_auth import _dispatch_couple_portal_accepted_notification

    couple_doc = {
        "email": COUPLE_EMAIL,
        "planner_email": PLANNER_EMAIL,
        "wedding_id": state["wedding_id"],
        "couple_names": "Alex & Jordan",
    }
    await _dispatch_couple_portal_accepted_notification(couple_doc)

    assert_eq(
        "planner Stage 2 dedup (must NOT increment)",
        await count_notif(PLANNER_EMAIL, "couple_portal_accepted") - before_planner,
        0,
    )
    assert_eq(
        "team[manage_forms] Stage 2 dedup (must NOT increment)",
        await count_notif(TEAM_FORMS_EMAIL, "couple_portal_accepted") - before_forms,
        0,
    )

    checkpoint_pause(
        "Stage 2 dedup",
        [
            "Confirm in the planner bell that NO new 'accepted the portal invite' entry was added by the second dispatch.",
            "Confirm DevTools shows NO new ``notification-new`` SSE for the planner.",
            "form_distributions table inspection: row exists for the seeded form_id + couple email — that's the dedup signal.",
        ],
    )


async def phase_checkpoint_4_actioned(state: Dict[str, Any]) -> None:
    banner(
        "CHECKPOINT 4 — mark-actioned flips actioned_at + actioned_via_action_button"
    )
    print(
        "  Driver action: mirror PUT /admin/planner/activity-notifications/{id}/actioned."
    )

    if not state.get("planner_stage2_id"):
        raise RuntimeError(
            "Stage 2 notification id missing; cannot exercise mark-actioned."
        )

    from app.services.planner_notification_service import (
        planner_notification_service,
    )

    notif_id = state["planner_stage2_id"]
    res = await planner_notification_service.mark_action_completed(
        notification_id=notif_id, planner_id=PLANNER_EMAIL
    )
    assert_truthy("mark_action_completed (success path)", res)

    mongo = get_async_mongo()
    from bson import ObjectId

    doc = await mongo.db["planner_notifications"].find_one({"_id": ObjectId(notif_id)})
    assert_truthy("planner Stage 2 doc still present", doc)
    assert_eq(
        "actioned_via_action_button",
        (doc or {}).get("actioned_via_action_button"),
        True,
    )
    assert_eq("is_read", (doc or {}).get("is_read"), True)
    assert_truthy("actioned_at populated", (doc or {}).get("actioned_at"))
    state["actioned_at_first"] = (doc or {}).get("actioned_at")

    checkpoint_pause(
        "mark-actioned (positive path)",
        [
            "Confirm the 'Send checklist' toast disappears from the bell unread badge after the CTA fires.",
            "DevTools → EventSource: confirm a ``notification-count`` SSE event arrives with the new unread total.",
        ],
    )


async def phase_checkpoint_5_ownership_gate(state: Dict[str, Any]) -> None:
    banner("CHECKPOINT 5 — cross-planner mark-actioned gate (ownership)")
    print("  Driver action: planner B attempts to action planner A's notification id.")

    from fastapi import HTTPException

    from app.services.planner_notification_service import (
        planner_notification_service,
    )

    notif_id = state.get("planner_stage2_id")
    if not notif_id:
        raise RuntimeError(
            "Stage 2 notification id missing; cross-planner gate cannot run."
        )

    raised = False
    status = None
    try:
        await planner_notification_service.mark_action_completed(
            notification_id=notif_id, planner_id=PLANNER_B_EMAIL
        )
    except HTTPException as exc:
        raised = True
        status = exc.status_code

    assert_eq("HTTPException raised on cross-planner mark-actioned", raised, True)
    assert_eq("ownership-gate status code", status, 404)

    checkpoint_pause(
        "cross-planner ownership gate",
        [
            f"Sign in as {PLANNER_B_EMAIL}; confirm the bell shows none of planner A's rows.",
            "Attempt the same PUT via DevTools → confirm the API responds 404 (Notification not found).",
        ],
    )


async def phase_checkpoint_6_idempotent(state: Dict[str, Any]) -> None:
    banner("CHECKPOINT 6 — mark-actioned idempotent (second call → 200)")
    print("  Driver action: call mark-actioned a second time on the same id.")

    from app.services.planner_notification_service import (
        planner_notification_service,
    )

    notif_id = state.get("planner_stage2_id")
    if not notif_id:
        raise RuntimeError(
            "Stage 2 notification id missing; idempotency check cannot run."
        )

    res = await planner_notification_service.mark_action_completed(
        notification_id=notif_id, planner_id=PLANNER_EMAIL
    )
    assert_truthy("second mark_action_completed (idempotent success)", res)

    mongo = get_async_mongo()
    from bson import ObjectId

    doc = await mongo.db["planner_notifications"].find_one({"_id": ObjectId(notif_id)})
    assert_eq(
        "actioned_via_action_button still True",
        (doc or {}).get("actioned_via_action_button"),
        True,
    )
    assert_eq("is_read still True", (doc or {}).get("is_read"), True)
    assert_truthy("actioned_at still populated", (doc or {}).get("actioned_at"))
    # Document is allowed to either retain the original timestamp or
    # refresh it; we only assert the field stays populated and the
    # actioned-state flags are sticky. Spec note: monotonic update OK.

    checkpoint_pause(
        "mark-actioned idempotency",
        [
            "Re-fire the toast handler twice in DevTools — both calls return 200.",
            "Confirm the bell row stays read + actioned across both calls (no flicker, no error toast).",
        ],
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


async def main() -> None:
    banner("verify_planner_two_stage_toast — VERIFY")
    print(f"Driver tag: {TWO_STAGE_TOAST.tag}")
    print(f"Planner: {PLANNER_EMAIL}")

    state = await phase_seed()
    await phase_checkpoint_1_stage1(state)
    await phase_checkpoint_2_stage2(state)
    await phase_checkpoint_3_dedup(state)
    await phase_checkpoint_4_actioned(state)
    await phase_checkpoint_5_ownership_gate(state)
    await phase_checkpoint_6_idempotent(state)

    banner("VERIFY complete")
    final_planner = await count_notif(PLANNER_EMAIL, "wedding_created")
    final_planner_stage2 = await count_notif(PLANNER_EMAIL, "couple_portal_accepted")
    print(f"  ↳ planner wedding_created rows: {final_planner}")
    print(f"  ↳ planner couple_portal_accepted rows: {final_planner_stage2}")
    print("  ↳ run cleanup: python testbed/cleanup_planner_two_stage_toast_state.py")


if __name__ == "__main__":
    asyncio.run(main())
