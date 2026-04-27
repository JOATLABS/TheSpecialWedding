"""
testbed/harness.py — shared infrastructure for subscription-lifecycle drivers.

Every driver under testbed/ instantiates a single Harness. The harness owns:

- config (env loading, guard rails for missing required keys)
- HTTP primitives (api_get / api_post / login / get_admin_token)
- Mongo primitives (find user, link stripe customer, read invite token,
  force email_verified, delete user chain)
- Stripe + test-clock primitives (get_or_create_clock, advance_clock_days
  that anchors on frozen_time — never wall-now, attach_payment_method,
  swap_subscription_pm, fetch_plan_monthly_price with sync fallback)
- Planner bootstrap (register → activate → email_verified → link customer
  → attach PM → subscribe, with optional trial)
- Console helpers (banner, structured checkpoint with ENTER gate,
  wait_for_webhooks)

Design decisions (agreed 2026-04-21):

1. Class form, not a free-function module — every driver carries the same
   dependency tree (config, mongo handle, logger, stripe-keyed session) and
   passing `harness` around beats passing five handles separately.
2. `.env` overlay. Repo-root `.env` is the source of real secrets; optional
   `testbed/.env` overrides testbed-only tunables (which clock, which plan,
   non-interactive mode). No secret duplication.
3. `checkpoint(name, expectations)` replaces freeform `pause_for_user`. Prints
   a standard block so grep against run logs stays legible, and has a clean
   skip point for non-interactive mode.
4. HTTP helpers return a `requests.Response`, they do NOT auto-raise. Callers
   inspect status codes (200/201/402/etc.) explicitly — that's the whole
   point of gate verification.
5. `advance_clock_days` anchors on the clock's current `frozen_time`, NOT
   `datetime.now()`. Reused clocks drift forward every run; advancing
   relative to wall-now explodes with "Test clocks can only be advanced
   forward in time." on the second run.

Not in the harness:

- Driver-specific plus-variant emails, clock ids, plan ids — those stay in
  the driver module header so they're grep-visible and reruns are
  deterministic.
- UX assertions (banners, toasts, console noise) — those live only in
  `checkpoint` expectation strings that the user verifies in Chrome.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
import stripe
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTBED_DIR = Path(__file__).resolve().parent

DEFAULT_WEBHOOK_SETTLE_SECONDS = 10
DEFAULT_CLOCK_POLL_ATTEMPTS = 20
DEFAULT_CLOCK_POLL_INTERVAL_SEC = 5

# Pre-built Stripe test PaymentMethod tokens. We use tokens rather than raw
# card dicts because the wedding Stripe account (correctly) does not have
# raw-card-data API access enabled. See https://docs.stripe.com/testing#cards
PM_TOKEN_GOOD = "pm_card_visa"  # 4242, always succeeds
PM_TOKEN_WILL_FAIL_ON_RENEWAL = (
    "pm_card_chargeCustomerFail"  # 4000 0000 0000 0341, succeeds once, fails renewals
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestbedConfig:
    """Resolved configuration for a testbed run.

    Constructed by Harness via `_load_config()`. Immutable so drivers can't
    clobber it mid-run by accident.
    """

    # Secrets (required)
    stripe_secret_key: str
    mongo_uri: str
    mongo_db: str
    admin_email: str
    admin_password: str

    # URLs (required)
    backend_url: str
    frontend_url: str

    # Testbed-only tunables (optional, sensible defaults)
    webhook_settle_seconds: int = DEFAULT_WEBHOOK_SETTLE_SECONDS
    non_interactive: bool = False
    default_plan_id: str = "plan_signature"
    default_pm_token_good: str = PM_TOKEN_GOOD
    default_pm_token_will_fail: str = PM_TOKEN_WILL_FAIL_ON_RENEWAL


# ---------------------------------------------------------------------------
# Seed result types
# ---------------------------------------------------------------------------


@dataclass
class PlannerSeed:
    """Return value of `Harness.seed_planner` and `Harness.seed_planner_on_clock`.

    Carries everything a driver needs to drive subsequent phases — the
    Stripe customer + subscription ids, the Mongo user_id, and the clock id
    the customer is pinned to (or None when the customer was created
    clockless via `seed_planner`).
    """

    customer_id: str
    subscription_id: str
    user_id: str
    email: str
    plan_id: str
    clock_id: Optional[str] = None
    has_trial: bool = False


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class Harness:
    """Shared infrastructure for subscription-lifecycle drivers.

    Construct once per driver run:

        harness = Harness(driver_name="verify_planner_trial_lifecycle")
        harness.preflight()            # backend health, admin login, stripe key
        seed = harness.seed_planner_on_clock(...)
        ...
        harness.checkpoint("A0", ["...", "..."])
    """

    def __init__(self, driver_name: str) -> None:
        self.driver_name = driver_name
        self.config = self._load_config()
        self._configure_logging()
        self.log = logging.getLogger(driver_name)

        # Bind module-level Stripe. The Stripe SDK is module-stateful, which
        # means only one API key at a time. That's fine for this repo — we
        # only ever run one driver at a time.
        stripe.api_key = self.config.stripe_secret_key
        self.stripe = stripe

        self.mongo_client: MongoClient = MongoClient(self.config.mongo_uri)
        self.mongo: Database = self.mongo_client[self.config.mongo_db]

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config() -> TestbedConfig:
        """Load repo-root .env, then overlay testbed/.env.

        Overlay semantics: repo-root .env provides real secrets. testbed/.env
        is optional and overrides with testbed-only tunables. No secret
        duplication. Missing testbed/.env is fine — defaults take over.
        """
        load_dotenv(REPO_ROOT / ".env")
        testbed_env = TESTBED_DIR / ".env"
        if testbed_env.exists():
            load_dotenv(testbed_env, override=True)

        required = {
            "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
            "ROOT_ADMIN_PASSWORD": os.getenv("ROOT_ADMIN_PASSWORD"),
        }
        mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
        required["MONGO_URI"] = mongo_uri

        missing = [k for k, v in required.items() if not v]
        if missing:
            sys.stderr.write(
                f"testbed/harness: missing required env keys: {', '.join(missing)}\n"
            )
            sys.exit(1)

        non_interactive = os.getenv("TESTBED_NON_INTERACTIVE", "0") in (
            "1",
            "true",
            "True",
        )
        try:
            webhook_settle = int(
                os.getenv(
                    "TESTBED_WEBHOOK_SETTLE_SECONDS", DEFAULT_WEBHOOK_SETTLE_SECONDS
                )
            )
        except ValueError:
            webhook_settle = DEFAULT_WEBHOOK_SETTLE_SECONDS

        return TestbedConfig(
            stripe_secret_key=required["STRIPE_SECRET_KEY"],  # type: ignore[arg-type]
            mongo_uri=required["MONGO_URI"],  # type: ignore[arg-type]
            mongo_db=os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding"),
            admin_email=os.getenv(
                "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
            ),
            admin_password=required["ROOT_ADMIN_PASSWORD"],  # type: ignore[arg-type]
            backend_url=os.getenv("BACKEND_URL", "http://localhost:8000"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            webhook_settle_seconds=webhook_settle,
            non_interactive=non_interactive,
            default_plan_id=os.getenv("TESTBED_DEFAULT_PLAN", "plan_signature"),
        )

    def _configure_logging(self) -> None:
        # Only configure root once; repeated calls no-op.
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s",
            )

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    def preflight(self) -> None:
        """Fail fast if the environment isn't ready to run a driver.

        Called once at the top of a driver's `main()`. Verifies:
          - Backend /health responds 200
          - ROOT admin can log in
          - Stripe key is live (we can list test_clocks)

        Raises RuntimeError on any failure so the driver can report context
        before exit.
        """
        self.banner(f"PREFLIGHT — {self.driver_name}")
        self.log.info(f"  Backend   : {self.config.backend_url}")
        self.log.info(f"  Frontend  : {self.config.frontend_url}")
        self.log.info(f"  Mongo DB  : {self.config.mongo_db}")
        self.log.info(f"  Non-interactive: {self.config.non_interactive}")

        try:
            health = requests.get(f"{self.config.backend_url}/health", timeout=5)
        except requests.RequestException as exc:
            raise RuntimeError(f"Backend unreachable: {exc}") from exc
        if health.status_code != 200:
            raise RuntimeError(
                f"Backend /health returned {health.status_code}: {health.text[:200]}"
            )
        self.log.info("  ✅ Backend healthy")

        # Admin login — any 4xx/5xx means the driver will fail later anyway,
        # so surface it now.
        try:
            self.get_admin_token()
            self.log.info("  ✅ Admin token acquired")
        except Exception as exc:
            raise RuntimeError(f"Admin login failed: {exc}") from exc

        # Stripe key smoke — cheapest possible call that touches the key.
        try:
            stripe.Account.retrieve()
            self.log.info("  ✅ Stripe key live")
        except stripe.error.StripeError as exc:
            raise RuntimeError(f"Stripe key invalid: {exc}") from exc

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def api_get(
        self, path: str, *, token: Optional[str] = None, timeout: int = 30
    ) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.get(
            f"{self.config.backend_url}{path}", headers=headers, timeout=timeout
        )

    def api_post(
        self,
        path: str,
        *,
        token: Optional[str] = None,
        json: Optional[dict] = None,
        timeout: int = 30,
    ) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.post(
            f"{self.config.backend_url}{path}",
            headers=headers,
            json=json or {},
            timeout=timeout,
        )

    def get_admin_token(self) -> str:
        resp = self.api_post(
            "/admin/token",
            json={
                "email": self.config.admin_email,
                "password": self.config.admin_password,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def login(self, email: str, password: str) -> str:
        """Log in as any user. Returns the access_token.

        For anything other than the happy path (e.g. 402 verification), call
        `api_post("/admin/token", json={...})` directly and inspect the
        response yourself — this helper raises on non-2xx.
        """
        resp = self.api_post(
            "/admin/token", json={"email": email, "password": password}
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    # ------------------------------------------------------------------
    # Mongo helpers
    # ------------------------------------------------------------------

    def find_user_id_by_email(self, admin_token: str, email: str) -> str:
        """Resolve a Mongo user_id from an email via the admin /users endpoint.

        Handles the `{users: [...]}` envelope shape as well as a bare list.
        """
        resp = self.api_get("/users", token=admin_token)
        resp.raise_for_status()
        payload = resp.json()
        users = payload.get("users") if isinstance(payload, dict) else payload
        for u in users or []:
            if u.get("email", "").lower() == email.lower():
                return u["_id"]
        raise RuntimeError(f"User {email} not found via /users")

    def get_user_doc(self, user_id: str) -> Optional[dict]:
        """Raw user document from Mongo. Returns None if not found."""
        return self.mongo["users"].find_one({"_id": ObjectId(user_id)})

    def get_user_subscription_doc(self, user_id: str) -> Optional[dict]:
        """Raw user_subscriptions document from Mongo. Returns None if not found."""
        return self.mongo["user_subscriptions"].find_one({"user_id": user_id})

    def link_stripe_customer(self, user_id: str, email: str, customer_id: str) -> None:
        """Upsert the users + stripe_customers mapping so webhooks resolve.

        Webhooks arrive keyed on stripe_customer_id. If the stripe_customers
        row is missing or unlinked, the webhook handler silently drops the
        event and the user's subscription state never updates. Every driver
        that seeds a customer MUST call this before the first webhook.
        """
        self.mongo["stripe_customers"].update_one(
            {"stripe_customer_id": customer_id},
            {
                "$set": {
                    "stripe_customer_id": customer_id,
                    "user_id": user_id,
                    "email": email,
                    "source": f"testbed:{self.driver_name}",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        self.mongo["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    def read_invite_token(self, owner_id: str, member_email: str) -> str:
        """Read the plaintext invite_token for a pending team member.

        Used by team-related drivers to accept an invite programmatically
        without waiting on email delivery. Raises if no pending invite
        exists for the (owner, email) pair.
        """
        doc = self.mongo["team_members"].find_one(
            {
                "owner_id": owner_id,
                "email": member_email.lower(),
                "status": "pending",
            }
        )
        if not doc or not doc.get("invite_token"):
            raise RuntimeError(
                f"No pending invite_token for {member_email} under owner {owner_id} — doc={doc!r}"
            )
        return doc["invite_token"]

    def force_email_verified(self, user_id: str) -> None:
        """Flip email_verified=True directly in Mongo.

        /users/{id}/activate only sets is_active. Because /public/register
        sets registration_source="public_signup", authenticate_user will
        reject login with 401 "Please verify your email address" until
        email_verified is True. This bypass avoids a real email round-trip.
        """
        self.mongo["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"email_verified": True}},
        )

    def delete_user_chain(self, email: str) -> int:
        """Delete a user and every document that references them.

        Removes: `users`, `user_subscriptions`, `stripe_customers`,
        `team_members` (both by `user_id` and by invitee `email`),
        `usage_tracking` (by `user_id`), and `weddings` (by
        `assigned_planner_email` — the stable key that survives user_id
        regeneration).

        **Why weddings by email and not just user_id:** when a driver
        re-seeds, the new `users` record gets a brand-new ObjectId. Weddings
        created under the PREVIOUS user_id were orphaned but still carried
        `assigned_planner_email`, which the /admin/money dashboard counts —
        so the planner's "Weddings X/3" counter silently drifted above the
        cap while `usage_tracking.weddings_count` (the counter the cap check
        reads) stayed at 0 for the freshly-seeded user. That's how
        trial-driver A1/A2 can "pass" (402 still fires because the *per-run*
        counter reaches 3) while the tenancy's true wedding count exceeds
        the plan limit. Email-keyed cleanup closes that drift.

        Returns the count of collections that had at least one document
        removed — useful for cleanup scripts that want to report progress.
        """
        user = self.mongo["users"].find_one({"email": email})

        collections_affected = 0

        # Weddings are keyed by email (assigned_planner_email / created_by),
        # which persists across user_id regeneration — delete BEFORE we lose
        # the user record, but use email (stable) rather than user_id (per-run).
        wedding_filter = {
            "$or": [
                {"assigned_planner_email": email},
                {"created_by": email},
            ]
        }
        result = self.mongo["weddings"].delete_many(wedding_filter)
        if result.deleted_count:
            collections_affected += 1
            self.log.info(
                f"  ✅ weddings (by email): removed {result.deleted_count} doc(s)"
            )

        if not user:
            return collections_affected

        user_id = str(user["_id"])

        for coll_name in (
            "user_subscriptions",
            "stripe_customers",
            "team_members",
            "usage_tracking",
        ):
            result = self.mongo[coll_name].delete_many({"user_id": user_id})
            if result.deleted_count:
                collections_affected += 1
                self.log.info(
                    f"  ✅ {coll_name}: removed {result.deleted_count} doc(s)"
                )

        # team_members also keys by invitee email for incoming invites.
        result = self.mongo["team_members"].delete_many({"email": email})
        if result.deleted_count:
            collections_affected += 1
            self.log.info(
                f"  ✅ team_members (by invitee email): removed {result.deleted_count} doc(s)"
            )

        # Also sweep any weddings that had assigned_planner_id pointing at the
        # user we're about to delete — covers the edge case where a wedding
        # was created without assigned_planner_email set.
        result = self.mongo["weddings"].delete_many({"assigned_planner_id": user_id})
        if result.deleted_count:
            collections_affected += 1
            self.log.info(
                f"  ✅ weddings (by planner_id): removed {result.deleted_count} doc(s)"
            )

        result = self.mongo["users"].delete_one({"_id": user["_id"]})
        if result.deleted_count:
            collections_affected += 1
            self.log.info(f"  ✅ users: removed {email}")

        return collections_affected

    # ------------------------------------------------------------------
    # Stripe test-clock helpers
    # ------------------------------------------------------------------

    def get_or_create_clock(
        self, clock_id: Optional[str], *, name: str
    ) -> stripe.test_helpers.TestClock:
        """Return an existing test clock if clock_id is set, else create one.

        Drivers that pin a clock in their module header for cross-run reuse
        call this with clock_id=TEST_CLOCK_ID. Drivers that want a fresh
        clock per run call this with clock_id=None — they're responsible
        for deleting it themselves at cleanup.
        """
        if clock_id:
            clock = stripe.test_helpers.TestClock.retrieve(clock_id)
            self.log.info(
                f"  ✅ Using existing clock {clock.id} "
                f"(status={clock.status}, frozen_at="
                f"{datetime.fromtimestamp(clock.frozen_time, tz=timezone.utc).isoformat()})"
            )
            return clock

        frozen_time = int(datetime.now(timezone.utc).timestamp())
        clock = stripe.test_helpers.TestClock.create(frozen_time=frozen_time, name=name)
        self.log.info(
            f"  ✅ Fresh clock created: {clock.id} "
            f"(frozen_at={datetime.fromtimestamp(frozen_time, tz=timezone.utc).isoformat()})"
        )
        return clock

    def wait_for_clock_ready(
        self,
        clock_id: str,
        max_polls: int = DEFAULT_CLOCK_POLL_ATTEMPTS,
        poll_interval: int = DEFAULT_CLOCK_POLL_INTERVAL_SEC,
    ) -> None:
        for attempt in range(1, max_polls + 1):
            clock = stripe.test_helpers.TestClock.retrieve(clock_id)
            if clock.status == "ready":
                self.log.info(f"  ✅ Clock ready (poll {attempt}/{max_polls})")
                return
            self.log.info(
                f"  ⏳ Clock status={clock.status} (poll {attempt}/{max_polls})"
            )
            time.sleep(poll_interval)
        raise RuntimeError(f"Clock {clock_id} never reached ready state")

    def advance_clock_days(self, clock_id: str, days: int) -> int:
        """Advance a test clock by N days relative to its CURRENT frozen_time.

        This is the critical bit: reused clocks drift forward each run. If we
        advance relative to `datetime.now()`, the second run on the same
        clock explodes with "Test clocks can only be advanced forward in
        time." Always anchor to the clock's own frozen_time.

        Returns the new target frozen_time (unix ts).
        """
        current = stripe.test_helpers.TestClock.retrieve(clock_id).frozen_time
        if not current:
            raise RuntimeError(
                f"Test clock {clock_id} has no frozen_time; cannot compute advance target."
            )
        target_ts = int(current) + days * 86400
        self.log.info(
            f"Advancing clock from "
            f"{datetime.fromtimestamp(int(current), tz=timezone.utc).isoformat()} "
            f"to {datetime.fromtimestamp(target_ts, tz=timezone.utc).isoformat()} "
            f"(+{days}d)…"
        )
        stripe.test_helpers.TestClock.advance(clock_id, frozen_time=target_ts)
        self.wait_for_clock_ready(clock_id)
        return target_ts

    def attach_payment_method(self, customer_id: str, pm_token: str) -> str:
        """Attach a pre-built Stripe test PM token and set as default.

        Returns the new PaymentMethod id so callers can pin it on the
        subscription too (see `swap_subscription_pm`).
        """
        pm = stripe.PaymentMethod.attach(pm_token, customer=customer_id)
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": pm.id},
        )
        return pm.id

    def swap_subscription_pm(
        self, customer_id: str, subscription_id: str, pm_token: str
    ) -> str:
        """Swap the default PM on BOTH the customer and the subscription.

        `Subscription.create(save_default_payment_method=on_subscription)`
        pins the first successful PM onto the subscription after its first
        charge. For renewals, subscription.default_payment_method wins over
        customer.invoice_settings.default_payment_method. If you only swap
        the customer default, renewal still bills the OLD card.

        This is the footgun that masked PR1's first FAIL run as a
        false-negative.
        """
        pm_id = self.attach_payment_method(customer_id, pm_token)
        stripe.Subscription.modify(subscription_id, default_payment_method=pm_id)
        return pm_id

    def fetch_plan_monthly_price(self, admin_token: str, plan_id: str) -> str:
        """Resolve the monthly Stripe price_id for a plan.

        Reads from the ROOT_ADMIN endpoint (NOT /public/subscription-plans,
        which deliberately sanitizes stripe_*_id fields). If the plan exists
        in Mongo but has no stripe_price_id_monthly yet, calls the admin
        sync endpoint once — it's idempotent — and retries.
        """
        price = self._read_plan_price_monthly(admin_token, plan_id)
        if price:
            return price

        self.log.info(
            f"  ⚠️ plan {plan_id} has no stripe_price_id_monthly — "
            f"syncing all plans to Stripe and retrying…"
        )
        sync_resp = self.api_post("/system/sync-plans-to-stripe", token=admin_token)
        if sync_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"/system/sync-plans-to-stripe failed: "
                f"{sync_resp.status_code} {sync_resp.text}"
            )
        sync_payload = sync_resp.json()
        self.log.info(f"  ✅ sync response: {sync_payload.get('message')}")
        if sync_payload.get("errors"):
            self.log.warning(f"  ⚠️ sync reported errors: {sync_payload['errors']}")

        price = self._read_plan_price_monthly(admin_token, plan_id)
        if price:
            return price

        raise RuntimeError(
            f"No Stripe monthly price_id for plan {plan_id} even after sync — "
            f"check that the plan exists in Mongo and STRIPE_SECRET_KEY is correct."
        )

    def _read_plan_price_monthly(self, admin_token: str, plan_id: str) -> Optional[str]:
        resp = self.api_get(
            "/subscription-plans?include_inactive=true", token=admin_token
        )
        resp.raise_for_status()
        payload = resp.json()
        plans = payload if isinstance(payload, list) else payload.get("plans") or []
        for p in plans:
            if p.get("_id") == plan_id or p.get("id") == plan_id:
                return p.get("stripe_price_id_monthly") or None
        return None

    def create_customer_on_clock(
        self,
        clock_id: str,
        email: str,
        name: str,
        **metadata: Any,
    ) -> stripe.Customer:
        """Create a fresh Stripe customer pinned to a test clock.

        The clock binding is what lets `advance_clock_days` drive this
        customer's subscription through its lifecycle.
        """
        meta = {"driver": self.driver_name, **metadata}
        customer = stripe.Customer.create(
            email=email,
            name=name,
            test_clock=clock_id,
            metadata=meta,
        )
        self.log.info(f"  ✅ Stripe customer: {customer.id} on clock {clock_id}")
        return customer

    def cleanup_clock_customers(self, clock_id: str) -> int:
        """Delete every Stripe customer pinned to the given clock.

        Uses Stripe's native `test_clock` list filter rather than scanning
        every customer client-side — the `test_clock` field on Customer
        objects returned by an un-filtered list is not always populated,
        only the filtered list guarantees correct membership.

        Returns the count of customers deleted.
        """
        deleted = 0
        for customer in stripe.Customer.list(
            test_clock=clock_id, limit=100
        ).auto_paging_iter():
            try:
                stripe.Customer.delete(customer.id)
                self.log.info(
                    f"  ✅ Deleted Stripe customer {customer.id} "
                    f"({customer.email or '—'})"
                )
                deleted += 1
            except stripe.error.StripeError as exc:
                self.log.warning(f"  ⚠️ Could not delete {customer.id}: {exc}")
        return deleted

    # ------------------------------------------------------------------
    # Planner bootstrap flow
    # ------------------------------------------------------------------

    def register_planner(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        company_name: str,
        plan_id: str,
    ) -> None:
        """POST /public/register for a new wedding_planner account.

        Raises RuntimeError on non-2xx.
        """
        resp = self.api_post(
            "/public/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "selected_plan_id": plan_id,
                "role": "wedding_planner",
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Planner register failed: {resp.status_code} {resp.text}"
            )
        self.log.info(f"  ✅ Planner registered: {email}")

    def activate_planner(self, admin_token: str, user_id: str) -> None:
        """Flip is_active + email_verified so the planner can log in.

        Two-step: /users/{id}/activate flips is_active. force_email_verified
        flips email_verified (which /activate does not touch — see
        force_email_verified docstring for why).
        """
        resp = self.api_post(f"/users/{user_id}/activate", token=admin_token)
        resp.raise_for_status()
        self.log.info(f"  ✅ Planner activated (user_id={user_id})")
        self.force_email_verified(user_id)
        self.log.info("  ✅ Planner email_verified=True (harness bypass)")

    def subscribe_planner(
        self,
        *,
        admin_token: str,
        customer_id: str,
        user_id: str,
        plan_id: str,
        trial_days: Optional[int] = None,
    ) -> stripe.Subscription:
        """Create the Stripe subscription for a customer.

        If trial_days is set, subscription enters `trialing` and fires the
        `customer.subscription.created` webhook with status=trialing. Plan
        snapshot limits still apply — that's how trial A1/A2/A3 tests work.
        """
        price_id = self.fetch_plan_monthly_price(admin_token, plan_id)

        kwargs: dict = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": {
                "user_id": user_id,
                "plan_id": plan_id,
                "billing_interval": "monthly",
                "driver": self.driver_name,
            },
            "payment_settings": {
                "save_default_payment_method": "on_subscription",
            },
        }
        if trial_days is not None:
            # Use trial_period_days (not trial_end): Stripe anchors this
            # to the subscription's start timestamp on the test clock, so
            # the trial end lands in the clock's future regardless of how
            # far the clock has drifted from wall-now. trial_end with a
            # wall-now timestamp breaks for drifted/reused clocks.
            kwargs["trial_period_days"] = trial_days
            kwargs["metadata"]["trial_days"] = str(trial_days)

        subscription = stripe.Subscription.create(**kwargs)
        self.log.info(
            f"  ✅ Subscription: {subscription.id} (status={subscription.status}"
            + (
                f", trial_end="
                f"{datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc).isoformat()})"
                if trial_days is not None and subscription.trial_end
                else ")"
            )
        )
        return subscription

    def seed_planner(
        self,
        *,
        admin_token: str,
        email: str,
        password: str,
        plan_id: str,
        first_name: str = "Testbed",
        last_name: str = "Planner",
        company_name: str = "Testbed QA Co",
        pm_token: Optional[str] = PM_TOKEN_GOOD,
        trial_days: Optional[int] = None,
        customer_metadata: Optional[dict] = None,
        clock_id: Optional[str] = None,
    ) -> PlannerSeed:
        """End-to-end planner bootstrap. **No clock by default.**

        Use this for tests that don't need to advance Stripe time —
        contract / package / vendor flows, anything verified at the moment
        of the action. For tests that need to drive subscription state
        through time (renewals, trial expiry, past_due transitions, the
        autopilot installment cron), use `seed_planner_on_clock` which
        delegates here with `clock_id` set.

        The 6-step arc every planner-lifecycle driver shares:

          1. Create Stripe customer (clock-pinned if `clock_id`, else plain)
          2. POST /public/register
          3. Activate (is_active + email_verified harness bypass)
          4. Link Stripe customer ↔ user_id (so webhooks resolve)
          5. Attach payment method (unless pm_token=None, e.g. trial-only)
          6. Create real Stripe subscription → webhook flips
             users.subscription_status=active

        Returns a PlannerSeed with every id the driver needs.

        pm_token=None is allowed for scenarios that want to exercise the
        "no PM on file" path — e.g. test that a trial without PM expires to
        `expired` rather than trying to charge. Default is PM_TOKEN_GOOD.

        Adding a clock just for the customer when no time advancement is
        required is overhead with no benefit — use the clockless default.
        """
        self.log.info(
            f"Seeding planner {email}"
            + (f" on clock {clock_id}" if clock_id else " (clockless)")
            + "…"
        )

        # 1. Stripe customer.
        if clock_id:
            customer = self.create_customer_on_clock(
                clock_id,
                email=email,
                name=f"{first_name} {last_name}",
                plan_id=plan_id,
                **(customer_metadata or {}),
            )
        else:
            meta = {
                "driver": self.driver_name,
                "plan_id": plan_id,
                **(customer_metadata or {}),
            }
            customer = stripe.Customer.create(
                email=email,
                name=f"{first_name} {last_name}",
                metadata=meta,
            )
            self.log.info(f"  ✅ Stripe customer: {customer.id}")

        # 2. Register.
        self.register_planner(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            plan_id=plan_id,
        )

        # 3. Resolve user_id, activate, verify email.
        user_id = self.find_user_id_by_email(admin_token, email)
        self.activate_planner(admin_token, user_id)

        # 4. Link customer ↔ user.
        self.link_stripe_customer(user_id, email, customer.id)
        self.log.info("  ✅ stripe_customers link upserted")

        # 5. Attach PM (optional — trial-only fixtures can skip).
        if pm_token is not None:
            self.attach_payment_method(customer.id, pm_token)
            self.log.info(f"  ✅ Payment method attached ({pm_token})")

        # 6. Subscribe (real Stripe Subscription; webhook flips Mongo state).
        subscription = self.subscribe_planner(
            admin_token=admin_token,
            customer_id=customer.id,
            user_id=user_id,
            plan_id=plan_id,
            trial_days=trial_days,
        )
        self.wait_for_webhooks()

        return PlannerSeed(
            customer_id=customer.id,
            subscription_id=subscription.id,
            user_id=user_id,
            email=email,
            plan_id=plan_id,
            clock_id=clock_id,
            has_trial=trial_days is not None,
        )

    def seed_planner_on_clock(
        self,
        *,
        admin_token: str,
        clock_id: str,
        email: str,
        password: str,
        plan_id: str,
        first_name: str = "Testbed",
        last_name: str = "Planner",
        company_name: str = "Testbed QA Co",
        pm_token: Optional[str] = PM_TOKEN_GOOD,
        trial_days: Optional[int] = None,
        customer_metadata: Optional[dict] = None,
    ) -> PlannerSeed:
        """Same as `seed_planner` but pins the Stripe customer to a test clock.

        Use when the test needs to advance time (subscription renewals,
        trial expiry, past_due transitions, autopilot installment cron).
        For one-shot tests that don't drive subscription state through
        time, use `seed_planner` directly — adding a clock costs you a
        cleanup obligation for no gain.

        Thin delegating wrapper — all logic lives in `seed_planner`.
        """
        return self.seed_planner(
            admin_token=admin_token,
            email=email,
            password=password,
            plan_id=plan_id,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            pm_token=pm_token,
            trial_days=trial_days,
            customer_metadata=customer_metadata,
            clock_id=clock_id,
        )

    # ------------------------------------------------------------------
    # Console helpers
    # ------------------------------------------------------------------

    def banner(self, title: str) -> None:
        """Emit a heavy-ruled title bar.

        Used at the top of the driver and at each phase boundary. Log-grep
        trick: every phase banner uses `=` * 72, every checkpoint uses `─`.
        """
        line = "=" * 72
        self.log.info("")
        self.log.info(line)
        self.log.info(f"  {title}")
        self.log.info(line)

    def phase(self, name: str, description: str = "") -> None:
        """Start a new phase. Sub-heading of banner."""
        self.banner(f"PHASE — {name}" + (f"  ({description})" if description else ""))

    def checkpoint(self, name: str, expectations: list[str]) -> None:
        """Emit a structured checkpoint and pause on ENTER.

        Replaces freeform `pause_for_user`. Enforces a standard shape:

            ── CHECKPOINT <name> ──
              1. <expectation>
              2. <expectation>
              ...
            → Press ENTER once verified…

        Skips the pause when TESTBED_NON_INTERACTIVE=1 (for CI reruns that
        only care about backend-observable state, not UX). Logs the skip so
        the checkpoint is still grep-visible.
        """
        rule = "─" * 72
        self.log.info("")
        self.log.info(rule)
        self.log.info(f"  CHECKPOINT {name}")
        self.log.info(rule)
        for i, exp in enumerate(expectations, 1):
            for line in exp.splitlines():
                self.log.info(
                    f"  {i}. {line}" if line == exp.splitlines()[0] else f"     {line}"
                )
        self.log.info(rule)
        if self.config.non_interactive:
            self.log.info("  (non-interactive mode — skipping ENTER gate)")
            return
        input("→ Press ENTER once you've verified this checkpoint in Chrome… ")

    def wait_for_webhooks(self, seconds: Optional[int] = None) -> None:
        secs = seconds if seconds is not None else self.config.webhook_settle_seconds
        self.log.info(f"  ⏳ Waiting {secs}s for Stripe webhooks to settle…")
        time.sleep(secs)

    # ------------------------------------------------------------------
    # Stripe Connect (Express) helpers
    # ------------------------------------------------------------------

    def ensure_connect_account(
        self,
        *,
        user_id: str,
        email: str,
        country: str = "US",
    ) -> str:
        """Ensure the planner has a Stripe Connect Express account, idempotent.

        Returns the connect account id. If the user already has
        `stripe_connect_id` on their Mongo doc, returns it as-is. Otherwise
        creates a fresh Express account via Stripe and persists the id on
        the user document. Does NOT complete onboarding —
        `charges_enabled=False` is the expected post-create state until the
        planner walks the hosted onboarding flow.

        Use `wait_for_connect_charges_enabled` after onboarding to poll the
        ready state.

        Raises SystemExit with a clear message if the platform Stripe
        account hasn't signed up for Connect at all (one-time setup at
        https://dashboard.stripe.com/test/connect).
        """
        user = self.get_user_doc(user_id)
        if user and user.get("stripe_connect_id"):
            self.log.info(
                f"  ✅ Stripe Connect account already attached: {user['stripe_connect_id']}"
            )
            return user["stripe_connect_id"]

        try:
            account = stripe.Account.create(
                type="express",
                country=country,
                email=email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                business_type="individual",
                business_profile={
                    "url": "https://thespecialwedding.io",
                    "mcc": "7299",
                    "product_description": "Wedding planning services (test)",
                },
            )
        except stripe.error.InvalidRequestError as exc:
            if "signed up for Connect" in str(exc):
                raise SystemExit(
                    "Stripe Connect is not enabled for this test account.\n"
                    "Visit https://dashboard.stripe.com/test/connect and click "
                    "'Get started' (one-time, free)."
                )
            raise

        self.mongo["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"stripe_connect_id": account.id}},
        )
        self.log.info(
            f"  ✅ Stripe Connect account: {account.id} (charges_enabled=False until onboarding)"
        )
        return account.id

    def create_account_link(self, account_id: str, return_url: str) -> str:
        """Generate a Stripe AccountLink URL for hosted onboarding.

        Use the returned URL with checkpoint() — the planner clicks through
        Stripe's hosted form (using "Use test data" buttons) and gets
        redirected back to return_url.
        """
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=return_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return link.url

    def wait_for_connect_charges_enabled(
        self,
        account_id: str,
        max_polls: int = 24,
        poll_interval: int = 5,
    ) -> None:
        """Poll Stripe until the connected account flips charges_enabled=True.

        Raises RuntimeError if it never flips (typically means onboarding
        wasn't completed or capability requirements remain).
        """
        for attempt in range(1, max_polls + 1):
            account = stripe.Account.retrieve(account_id)
            if account.charges_enabled:
                self.log.info(f"  ✅ charges_enabled=True (poll {attempt}/{max_polls})")
                return
            self.log.info(f"  ⏳ charges_enabled=False (poll {attempt}/{max_polls})")
            time.sleep(poll_interval)
        raise RuntimeError(
            f"Stripe Connect account {account_id} never flipped charges_enabled=True"
        )

    def delete_connect_account(self, account_id: str) -> None:
        """Delete a Stripe Express account. Cleanup helper — swallows
        already-deleted errors with a warning so cleanup scripts stay
        idempotent."""
        try:
            stripe.Account.delete(account_id)
            self.log.info(f"  ✅ Deleted Stripe Express account {account_id}")
        except stripe.error.StripeError as exc:
            self.log.warning(f"  ⚠️ Could not delete Stripe account {account_id}: {exc}")

    # ------------------------------------------------------------------
    # Wedding + Couple helpers (planner-side)
    # ------------------------------------------------------------------

    def create_wedding(
        self,
        *,
        planner_token: str,
        couple_names: str,
        date_iso: str,
        guest_count: Optional[int] = None,
        venue: Optional[str] = None,
        status: str = "active",
    ) -> str:
        """POST /admin/weddings — create a real wedding row through the
        production code path.

        `couple_names` is a string only (e.g. "Alex & Jamie"). It is NOT a
        link to a couple user — that link is established later via
        `invite_couple_to_wedding`. Until invited, the couple has no portal
        account.

        Returns the wedding id (typically `wedding_<hex>`).
        """
        payload: dict = {
            "couple_names": couple_names,
            "date": date_iso,
            "status": status,
        }
        if guest_count is not None:
            payload["guest_count"] = guest_count
        if venue is not None:
            payload["venue"] = venue

        resp = self.api_post("/admin/weddings", token=planner_token, json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"wedding create failed: {resp.status_code} {resp.text}")
        body = resp.json()
        wedding_id = (
            body.get("id")
            or body.get("_id")
            or (body.get("wedding") or {}).get("id")
            or (body.get("wedding") or {}).get("_id")
        )
        if not wedding_id:
            raise RuntimeError(f"wedding create: no id in response {body!r}")
        self.log.info(
            f"  ✅ Created wedding: {wedding_id} ({couple_names}, {date_iso})"
        )
        return str(wedding_id)

    def invite_couple_to_wedding(
        self,
        *,
        planner_token: str,
        wedding_id: str,
        email: str,
        partner1_name: str,
        partner2_name: Optional[str] = None,
    ) -> dict:
        """POST /admin/couple-portal/invite — invite a couple to the wedding's
        couple portal.

        Returns the response payload, which includes `setup_link` — the
        couple-side URL where the couple sets up their own credentials.
        Production planners share this link via email; tests can either
        complete the setup programmatically (TODO: add helper) or pause
        for manual setup at a checkpoint.

        Without this step, the couple is just a `couple_names` string on
        the wedding — they have no portal account, no login, no
        `/couple/dashboard` access.
        """
        payload: dict = {
            "email": email,
            "partner1_name": partner1_name,
            "wedding_id": wedding_id,
        }
        if partner2_name:
            payload["partner2_name"] = partner2_name
        resp = self.api_post(
            "/admin/couple-portal/invite", token=planner_token, json=payload
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"couple invite failed: {resp.status_code} {resp.text}")
        body = resp.json()
        self.log.info(
            f"  ✅ Couple invited: {email} → setup_link={body.get('setup_link', '(not in response)')[:60]}…"
        )
        return body

    # ------------------------------------------------------------------
    # Package helpers (planner-side)
    # ------------------------------------------------------------------

    def create_package(
        self,
        *,
        planner_token: str,
        name: str,
        total_amount: float,
        services: Optional[list[dict]] = None,
        payment_schedule: Optional[list[dict]] = None,
        description: str = "",
        currency: str = "usd",
        cancellation_policy: str = "",
        status: str = "active",
    ) -> str:
        """POST /admin/packages — create a real package through the
        production code path.

        `payment_schedule` items shape (validated by ScheduleItemRequest):
          - name: str (required)
          - trigger: "on_signing" | "days_after_signing" | "days_before_wedding" | "fixed_date"
          - days_after / days_before / fixed_date as appropriate
          - amount XOR percentage (production UI uses percentage; backend
            accepts either)

        Status defaults to "active" so the package is immediately
        sendable. "draft" status blocks send_to_couple.

        Returns the package id (24-char hex ObjectId stringified).
        """
        payload: dict = {
            "name": name,
            "description": description,
            "services": services or [],
            "total_amount": total_amount,
            "currency": currency,
            "payment_schedule": payment_schedule or [],
            "cancellation_policy": cancellation_policy,
            "status": status,
        }
        resp = self.api_post("/admin/packages", token=planner_token, json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"package create failed: {resp.status_code} {resp.text}")
        body = resp.json()
        package = body.get("package") or body
        package_id = package.get("id") or package.get("_id")
        if not package_id:
            raise RuntimeError(f"package create: no id in response {body!r}")
        self.log.info(
            f"  ✅ Created package: {package_id} "
            f"(${total_amount:.2f} {currency.upper()}, status={status})"
        )
        return str(package_id)

    def send_package_to_couple(
        self,
        *,
        planner_token: str,
        package_id: str,
        wedding_id: str,
        couple_email: str,
        partner1_name: str,
        partner2_name: Optional[str] = None,
    ) -> str:
        """POST /admin/packages/{id}/send — send a package to a couple,
        producing a public-token contract row through `package_service.send_to_couple`.

        IMPORTANT: This requires `RESEND_API_KEY` in .env. The send_to_couple
        service unconditionally emails the couple after creating the
        contract row, and ROLLS BACK the row if the email fails. So drivers
        must validate RESEND_API_KEY at startup.

        Returns the public contract token. The couple uses the token to
        open `/contracts/{token}` (no auth required) and sign +
        capture-card via SetupIntent.
        """
        payload: dict = {
            "couple": {
                "partner1_name": partner1_name,
                "email": couple_email,
            },
            "wedding_id": wedding_id,
        }
        if partner2_name:
            payload["couple"]["partner2_name"] = partner2_name
        resp = self.api_post(
            f"/admin/packages/{package_id}/send",
            token=planner_token,
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"package send failed: {resp.status_code} {resp.text}")
        body = resp.json()
        contract = body.get("contract") or body
        token = contract.get("token") or contract.get("public_token")
        if not token:
            raise RuntimeError(f"package send: no token in response {body!r}")
        self.log.info(f"  ✅ Sent package — contract token: {token}")
        return token

    # ------------------------------------------------------------------
    # Contract sign helpers (couple-side, public-token)
    # ------------------------------------------------------------------

    def init_contract_setup_intent(self, contract_token: str) -> dict:
        """POST /public/contracts/{token}/setup-intent — initialize the
        SetupIntent for capturing the couple's payment method.

        No auth required; the contract token is the gate. Returns
        {customer_id, client_secret, setup_intent_id} — `setup_intent_id`
        is parsed from the client_secret since Stripe's secret format is
        always `<si_id>_secret_<random>`.
        """
        resp = requests.post(
            f"{self.config.backend_url}/public/contracts/{contract_token}/setup-intent",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        client_secret = data["client_secret"]
        setup_intent_id = client_secret.split("_secret_")[0]
        self.log.info(
            f"  ✅ SetupIntent initialized: customer={data['customer_id']} "
            f"setup_intent={setup_intent_id}"
        )
        return {
            "customer_id": data["customer_id"],
            "client_secret": client_secret,
            "setup_intent_id": setup_intent_id,
        }

    def confirm_setup_intent_with_test_pm(
        self, setup_intent_id: str, pm_token: str = PM_TOKEN_GOOD
    ) -> dict:
        """Confirm a Stripe SetupIntent server-side using a pre-built test
        PaymentMethod token (default: pm_card_visa).

        In test mode this completes without 3DS step-up. Returns
        {payment_method_id, last4, brand} for use with sign_contract.
        Raises if the SetupIntent doesn't reach `succeeded`.
        """
        intent = stripe.SetupIntent.confirm(setup_intent_id, payment_method=pm_token)
        if intent.status != "succeeded":
            raise RuntimeError(
                f"SetupIntent confirm did not succeed: status={intent.status}"
            )
        pm = stripe.PaymentMethod.retrieve(intent.payment_method)
        last4 = pm.card.last4 if pm.card else None
        brand = pm.card.brand if pm.card else None
        self.log.info(
            f"  ✅ SetupIntent confirmed: pm={intent.payment_method} ({brand} •••• {last4})"
        )
        return {
            "payment_method_id": intent.payment_method,
            "last4": last4,
            "brand": brand,
        }

    def sign_contract(
        self,
        *,
        contract_token: str,
        signature_name: str,
        customer_id: str,
        payment_method_id: str,
        setup_intent_id: str,
        last4: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> dict:
        """POST /public/contracts/{token}/sign — sign the contract.

        Triggers `contract_service.sign_contract` server-side which:
          1. Marks the contract `signed`
          2. Creates `scheduled_payments` rows from the package schedule
          3. Auto-charges the on_signing deposit through Stripe with
             transfer_data.destination = the planner's stripe_connect_id

        Returns the response body (includes `contract` with
        `scheduled_payments`, `deposit_processed`, etc.).
        """
        resp = requests.post(
            f"{self.config.backend_url}/public/contracts/{contract_token}/sign",
            json={
                "signature_name": signature_name,
                "accept_terms": True,
                "stripe_customer_id": customer_id,
                "stripe_payment_method_id": payment_method_id,
                "setup_intent_id": setup_intent_id,
                "payment_method_last4": last4,
                "payment_method_brand": brand,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"sign failed: {resp.status_code} {resp.text}")
        body = resp.json()
        contract = body.get("contract") or {}
        self.log.info(
            f"  ✅ Contract signed. deposit_processed={contract.get('deposit_processed')} "
            f"scheduled_payments={len(contract.get('scheduled_payments') or [])}"
        )
        return body
