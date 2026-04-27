#!/usr/bin/env python3
"""ONE-OFF seed for the planner-onboarding-modal Chrome verification.

Question being verified: does the planner onboarding tour show on every
sign-in, or only the first time?

This script seeds an isolated planner so we can drive the answer in Chrome:
two consecutive sign-ins, observe whether the modal opens both times.

What it does (idempotent — safe to re-run):
  1. POST /public/register for test_planner+onboarding@thespecialwedding.io
     (skipped if user already exists).
  2. POST /admin/token to get a root admin token.
  3. POST /users/{id}/activate to flip is_active=True.
  4. Mongo direct writes to:
       - email_verified=True (no real email round-trip)
       - subscription_status=active + a user_subscriptions row, so the
         planner dashboard isn't 402-gated. Onboarding is unrelated to
         billing — we just need a clean dashboard load.
       - onboarding_completed=False (force fresh onboarding state every
         re-run, so the verification can be repeated without manual reset).

After running, sign in at http://localhost:3000/admin/login with the
credentials printed at the end.

Cleanup: delete the user document and the user_subscriptions row by email
when finished. Or just leave it — plus-variant emails are sandboxed.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMAIL = "test_planner+onboarding@thespecialwedding.io"
PASSWORD = "OnboardingVerify2026!"  # pragma: allowlist secret
FIRST_NAME = "Onboarding"
LAST_NAME = "Verify"
COMPANY_NAME = "Onboarding Verify Studio"
PLAN_ID = "plan_signature"

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")
ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD")

if not MONGO_URI:
    sys.exit("MONGO_URI not set in .env")
if not ADMIN_PASSWORD:
    sys.exit("ROOT_ADMIN_PASSWORD not set in .env")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_post(path: str, *, json: dict, token: str | None = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{BACKEND_URL}{path}", json=json, headers=headers, timeout=30)


def admin_token() -> str:
    resp = api_post(
        "/admin/token", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

mongo = MongoClient(MONGO_URI)[MONGO_DB]

print(f"→ Backend  : {BACKEND_URL}")
print(f"→ Frontend : {FRONTEND_URL}")
print(f"→ Planner  : {EMAIL}")
print()

# 1. Register (skip if already exists).
existing = mongo["users"].find_one({"email": EMAIL})
if existing:
    print("✅ Planner already registered — reusing")
else:
    resp = api_post(
        "/public/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "first_name": FIRST_NAME,
            "last_name": LAST_NAME,
            "company_name": COMPANY_NAME,
            "selected_plan_id": PLAN_ID,
            "role": "wedding_planner",
        },
    )
    if resp.status_code not in (200, 201):
        sys.exit(f"register failed: {resp.status_code} {resp.text}")
    print(f"✅ Registered new planner ({resp.status_code})")

# 2. Admin token.
token = admin_token()
print("✅ Admin token acquired")

# 3. Activate (is_active=True).
user = mongo["users"].find_one({"email": EMAIL})
if not user:
    sys.exit(f"user not found in mongo after register: {EMAIL}")
user_id = str(user["_id"])

activate = api_post(f"/users/{user_id}/activate", json={}, token=token)
# /activate is idempotent — if it errors because already-active, that's fine.
if activate.status_code not in (200, 201, 204):
    print(f"  ⚠️ activate returned {activate.status_code}: {activate.text[:200]}")
else:
    print("✅ Activated (is_active=True)")

# 4. Mongo flips: email_verified, subscription bypass, onboarding reset.
now = datetime.now(timezone.utc)

mongo["users"].update_one(
    {"_id": user["_id"]},
    {
        "$set": {
            "email_verified": True,
            "is_active": True,
            "subscription_status": "active",
            "user_data.plan_id": PLAN_ID,
            # Force fresh onboarding state every re-run.
            "onboarding_completed": False,
            "onboarding_completed_at": None,
            "onboarding_steps_completed": [],
        }
    },
)
print("✅ email_verified=True, subscription_status=active, onboarding_completed=False")

mongo["user_subscriptions"].update_one(
    {"user_id": user_id},
    {
        "$set": {
            "user_id": user_id,
            "plan_id": PLAN_ID,
            "status": "active",
            "billing_interval": "monthly",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "payment_status": "paid",
            "created_at": now.isoformat(),
            "source": "_seed_planner_for_onboarding_verify",
        }
    },
    upsert=True,
)
print("✅ user_subscriptions row upserted (dashboard 402-gate bypass)")

# Quick verification readback.
after = mongo["users"].find_one({"_id": user["_id"]})
print()
print("─── Final state ────────────────────────────────────────────────")
print(f"  user_id              : {user_id}")
print(f"  email_verified       : {after.get('email_verified')}")
print(f"  is_active            : {after.get('is_active')}")
print(f"  subscription_status  : {after.get('subscription_status')}")
print(f"  onboarding_completed : {after.get('onboarding_completed')}")
print()
print("─── Sign-in credentials ────────────────────────────────────────")
print(f"  URL      : {FRONTEND_URL}/admin/login")
print(f"  Email    : {EMAIL}")
print(f"  Password : {PASSWORD}")
print()
