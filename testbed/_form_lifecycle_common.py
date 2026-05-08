"""Shared helpers for the form-lifecycle testbed verifiers.

The 10 ``verify_form_*.py`` drivers all need the same handful of
ingredients — a seeded planner with their catalog, a freshly-created
form, a way to generate distributions / responses / uploads, and a
predictable cleanup hook. Putting these here keeps each driver under
200 lines while preserving the testbed/README.md house rules:

  - Plus-suffixed test accounts so QA base accounts are untouched.
  - Idempotent SEED.
  - ENTER-gated checkpoints for browser inspection.
  - Cleanup script targets the plus-suffixed rows.

Leading underscore on the module name keeps driver-discovery in the
project's release tooling from picking this file up as a runnable
verifier — it's a library, not a driver.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Test account constants — one per scenario so a single cleanup script can
# target a specific verifier's rows without disturbing the others.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormVerifierAccount:
    """One planner identity per verifier scenario."""

    tag: str
    password: str

    @property
    def email(self) -> str:
        # Plus-tag pattern: test_planner+<scenario>@thespecialwedding.io.
        return f"test_planner+{self.tag}@thespecialwedding.io"


# Each verifier picks its own scenario tag. Centralised so a stray
# verifier can't collide with another's seed.
ANON_SUBMIT = FormVerifierAccount("formlife_anon", "FormAnon2026!")
TOKENIZED_SUBMIT = FormVerifierAccount("formlife_tok", "FormTok2026!")
CONDITIONAL = FormVerifierAccount("formlife_cond", "FormCond2026!")
FILE_UPLOAD = FormVerifierAccount("formlife_upload", "FormUp2026!")
REMINDER = FormVerifierAccount("formlife_reminder", "FormRem2026!")
PHASE_D_SEED = FormVerifierAccount("formlife_seed", "FormSeed2026!")
PUBLIC_PDF = FormVerifierAccount("formlife_pdf", "FormPdf2026!")
MARKETING = FormVerifierAccount("formlife_market", "FormMarket2026!")
PAGINATION = FormVerifierAccount("formlife_page", "FormPage2026!")
CSV_TRUNCATION = FormVerifierAccount("formlife_csv", "FormCsv2026!")


ALL_FORM_VERIFIER_ACCOUNTS: List[FormVerifierAccount] = [
    ANON_SUBMIT,
    TOKENIZED_SUBMIT,
    CONDITIONAL,
    FILE_UPLOAD,
    REMINDER,
    PHASE_D_SEED,
    PUBLIC_PDF,
    MARKETING,
    PAGINATION,
    CSV_TRUNCATION,
]


# ---------------------------------------------------------------------------
# Mongo + HTTP helpers
# ---------------------------------------------------------------------------


def get_async_mongo():
    """Return the project's MongoConnector (Motor under the hood).

    Drivers run against the real configured ``MONGODB_URL`` — that's
    the point. We import lazily so the harness preflight check has a
    chance to fail loud before we touch the DB.
    """
    from app.core.database import mongo

    return mongo


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def insert_one(collection_name: str, doc: Dict[str, Any]) -> Any:
    mongo = get_async_mongo()
    coll = mongo.db[collection_name]
    return await coll.insert_one(doc)


async def delete_many(collection_name: str, query: Dict[str, Any]) -> int:
    mongo = get_async_mongo()
    coll = mongo.db[collection_name]
    result = await coll.delete_many(query)
    return int(getattr(result, "deleted_count", 0) or 0)


async def count_documents(collection_name: str, query: Dict[str, Any]) -> int:
    mongo = get_async_mongo()
    coll = mongo.db[collection_name]
    return int(await coll.count_documents(query))


def short_token() -> str:
    """Stable-ish per-run identifier — used to suffix per-driver
    distribution / form ids so reruns don't collide."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Cleanup primitive: remove every form-related row owned by a planner email.
# Cleanup scripts under ``cleanup_form_*_state.py`` import this so the
# scenario-specific scripts only have to call one function.
# ---------------------------------------------------------------------------


async def purge_form_rows_for_planner(planner_email: str) -> Dict[str, int]:
    """Remove forms / responses / distributions / uploads owned by a planner.

    The ``forms`` collection joins everything else: every form row
    carries ``created_by``; ``form_responses`` and ``form_distributions``
    join via ``form_id``; ``form_uploads`` join the same way; and
    ``marketing_leads`` are keyed on ``email``, so we sweep them too.

    Idempotent — re-running on already-cleaned state returns zeros.
    """
    mongo = get_async_mongo()
    forms_coll = mongo.db["forms"]
    cursor = forms_coll.find(
        {"created_by": planner_email}, {"_id": 1}
    )
    form_ids: List[Any] = []
    async for doc in cursor:
        form_ids.append(doc["_id"])

    deleted: Dict[str, int] = {
        "forms": 0,
        "form_responses": 0,
        "form_distributions": 0,
        "form_uploads": 0,
        "marketing_leads": 0,
        "planner_notifications": 0,
    }

    if form_ids:
        deleted["form_responses"] = await delete_many(
            "form_responses", {"form_id": {"$in": form_ids}}
        )
        deleted["form_distributions"] = await delete_many(
            "form_distributions", {"form_id": {"$in": form_ids}}
        )
        deleted["form_uploads"] = await delete_many(
            "form_uploads", {"form_id": {"$in": form_ids}}
        )

    deleted["forms"] = await delete_many("forms", {"created_by": planner_email})
    deleted["marketing_leads"] = await delete_many(
        "marketing_leads", {"email": planner_email}
    )
    deleted["planner_notifications"] = await delete_many(
        "planner_notifications", {"planner_id": planner_email}
    )
    return deleted


async def purge_marketing_leads_for_email(email: str) -> int:
    return await delete_many("marketing_leads", {"email": email.lower().strip()})


# ---------------------------------------------------------------------------
# Phase-gating: every driver pauses at a checkpoint so the user can
# eyeball Chrome before SEED turns into VERIFY. Mirrors
# verify_form_data_apply_isolation.py exactly.
# ---------------------------------------------------------------------------


def checkpoint_pause(label: str, expectations: List[str]) -> None:
    """Pause the driver and print a checklist for the human to verify
    in the browser before pressing ENTER."""
    print()
    print(f"  📋 CHECKPOINT — {label}")
    for line in expectations:
        print(f"    • {line}")
    print()
    if os.environ.get("FORMLIFE_NO_INPUT"):
        # CI / smoke-import path — don't block.
        return
    input("  Press ENTER once verified in Chrome…")


def banner(label: str) -> None:
    print()
    print("=" * 72)
    print(f"  {label}")
    print("=" * 72)
    print()


def run(coro):
    """Execute an async coroutine inside the driver's __main__ block."""
    asyncio.run(coro)


__all__ = [
    "ALL_FORM_VERIFIER_ACCOUNTS",
    "ANON_SUBMIT",
    "CONDITIONAL",
    "CSV_TRUNCATION",
    "FILE_UPLOAD",
    "FormVerifierAccount",
    "MARKETING",
    "PAGINATION",
    "PHASE_D_SEED",
    "PUBLIC_PDF",
    "REMINDER",
    "TOKENIZED_SUBMIT",
    "banner",
    "checkpoint_pause",
    "count_documents",
    "delete_many",
    "get_async_mongo",
    "insert_one",
    "now_utc",
    "purge_form_rows_for_planner",
    "purge_marketing_leads_for_email",
    "run",
    "short_token",
]
