"""
Repair planner Stripe billing and trial records.

This is a production maintenance script for cases where planner accounts were
created while Stripe checkout or webhooks were misconfigured. It is deliberately
dry-run by default.

Examples:
  python -m app.scripts.repair_planner_stripe_trials
  python -m app.scripts.repair_planner_stripe_trials --email planner@example.com
  python -m app.scripts.repair_planner_stripe_trials --apply --email planner@example.com
  python -m app.scripts.repair_planner_stripe_trials --apply --default-plan-id plan_signature
  python -m app.scripts.repair_planner_stripe_trials --apply --archive-orphan-subscriptions

Safety rules:
  - ROOT_ADMIN, team members, vendors, and other non-planner roles are skipped.
  - Existing Stripe subscriptions are treated as the source of truth.
  - Missing plan_id is not guessed unless --default-plan-id is supplied.
  - Active/past-due/cancelled local accounts without Stripe subscriptions are
    not silently converted into new free trials.
  - Orphan user_subscriptions rows are archived only when explicitly requested.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import stripe
from bson import ObjectId
from stripe import InvalidRequestError, StripeError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.constants.registration_sources import (  # noqa: E402
    REGISTRATION_SOURCE_LEGACY,
    is_public_signup_registration,
)
from app.core.database import close_database, init_database, mongo  # noqa: E402
from app.core.settings import settings  # noqa: E402
from app.models.subscription import (  # noqa: E402
    SubscriptionStatus,
    normalize_subscription_status,
)
from app.services.stripe_service import StripeService  # noqa: E402
from app.services.subscription_service import SubscriptionService  # noqa: E402
from app.utils.planner_billing_scope import is_planner_billing_role  # noqa: E402


TRIAL_REPAIR_STATUSES = {
    None,
    "",
    "inactive",
    "pending",
    SubscriptionStatus.PENDING_CHECKOUT.value,
    SubscriptionStatus.PENDING_PAYMENT.value,
    SubscriptionStatus.TRIAL.value,
    SubscriptionStatus.TRIAL_EXPIRING.value,
}

TRIAL_STATUSES = {
    SubscriptionStatus.TRIAL.value,
    SubscriptionStatus.TRIAL_EXPIRING.value,
}

NON_TRIAL_REPAIR_STATUSES = {
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.PAST_DUE.value,
    SubscriptionStatus.CANCELLED.value,
    SubscriptionStatus.SUSPENDED.value,
}


@dataclass
class RepairResult:
    email: str
    user_id: str
    status: str
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RepairStats:
    scanned: int = 0
    repaired: int = 0
    would_repair: int = 0
    skipped: int = 0
    errors: int = 0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stringify_id(value: Any) -> str:
    return str(value) if value is not None else ""


def coerce_utc_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def is_root_admin_user(user: dict[str, Any], root_admin_email: str | None) -> bool:
    role = str(user.get("role") or "")
    email = str(user.get("email") or "").strip().lower()
    root_email = (root_admin_email or "").strip().lower()
    return role.upper() == "ROOT_ADMIN" or bool(root_email and email == root_email)


def is_repair_candidate(user: dict[str, Any], root_admin_email: str | None) -> bool:
    if is_root_admin_user(user, root_admin_email):
        return False
    return is_planner_billing_role(user.get("role"))


def choose_local_subscription(
    subscriptions: Iterable[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    status_rank = {
        SubscriptionStatus.ACTIVE.value: 70,
        SubscriptionStatus.TRIAL.value: 65,
        SubscriptionStatus.TRIAL_EXPIRING.value: 60,
        SubscriptionStatus.PAST_DUE.value: 55,
        SubscriptionStatus.PENDING_CHECKOUT.value: 45,
        SubscriptionStatus.PENDING_PAYMENT.value: 40,
        SubscriptionStatus.SUSPENDED.value: 25,
        SubscriptionStatus.EXPIRED.value: 20,
        SubscriptionStatus.CANCELLED.value: 10,
    }

    candidates = list(subscriptions)
    if not candidates:
        return None

    def score(sub: dict[str, Any]) -> tuple[int, int, float]:
        has_stripe_sub = 1 if sub.get("stripe_subscription_id") else 0
        normalized_status = normalize_subscription_status(sub.get("status")) or ""
        status_score = status_rank.get(normalized_status, 0)
        updated = (
            coerce_utc_datetime(sub.get("updated_at"))
            or coerce_utc_datetime(sub.get("created_at"))
            or coerce_utc_datetime(sub.get("start_date"))
            or datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
        return has_stripe_sub, status_score, updated.timestamp()

    return max(candidates, key=score)


def determine_billing_interval(
    user: dict[str, Any], sub: Optional[dict[str, Any]]
) -> str:
    raw = (
        (sub or {}).get("billing_interval") or user.get("billing_interval") or "monthly"
    )
    return "yearly" if str(raw).lower() == "yearly" else "monthly"


def determine_trial_days(
    user: dict[str, Any],
    plan: dict[str, Any],
    now: datetime,
    override_trial_days: Optional[int] = None,
) -> int:
    if override_trial_days is not None:
        return max(0, override_trial_days)

    local_status = normalize_subscription_status(user.get("subscription_status"))
    local_trial_end = coerce_utc_datetime(user.get("trial_end_date"))
    if (
        local_status
        in {
            SubscriptionStatus.TRIAL.value,
            SubscriptionStatus.TRIAL_EXPIRING.value,
        }
        and local_trial_end
        and local_trial_end > now
    ):
        seconds_remaining = (local_trial_end - now).total_seconds()
        return max(1, math.ceil(seconds_remaining / 86400))

    plan_trial_days = plan.get("trial_days")
    if isinstance(plan_trial_days, int) and plan_trial_days > 0:
        return plan_trial_days
    return 0


def derive_legacy_trial_status(
    user: dict[str, Any], sub: Optional[dict[str, Any]]
) -> Optional[str]:
    user_status = normalize_subscription_status(user.get("subscription_status"))
    sub_status = normalize_subscription_status((sub or {}).get("status"))

    if user_status in TRIAL_STATUSES:
        return user_status
    if sub_status in TRIAL_STATUSES and user_status in TRIAL_REPAIR_STATUSES:
        return sub_status
    return None


def derive_legacy_trial_end(
    user: dict[str, Any],
    sub: Optional[dict[str, Any]],
    plan: dict[str, Any],
) -> Optional[datetime]:
    for value in (
        user.get("trial_end_date"),
        (sub or {}).get("trial_end_date"),
        (sub or {}).get("current_period_end"),
        (sub or {}).get("end_date"),
    ):
        trial_end = coerce_utc_datetime(value)
        if trial_end:
            return trial_end

    plan_trial_days = plan.get("trial_days")
    created_at = coerce_utc_datetime(user.get("created_at")) or coerce_utc_datetime(
        (sub or {}).get("created_at")
    )
    if isinstance(plan_trial_days, int) and plan_trial_days > 0 and created_at:
        return created_at + timedelta(days=plan_trial_days)

    return None


def can_create_missing_trial_subscription(
    user: dict[str, Any],
    *,
    include_expired: bool = False,
) -> bool:
    status = normalize_subscription_status(user.get("subscription_status"))
    if status == SubscriptionStatus.EXPIRED.value:
        return include_expired
    if status in NON_TRIAL_REPAIR_STATUSES:
        return False
    return status in TRIAL_REPAIR_STATUSES


def local_trial_already_expired(
    user: dict[str, Any],
    sub: Optional[dict[str, Any]],
    plan: dict[str, Any],
    now: datetime,
) -> bool:
    if derive_legacy_trial_status(user, sub) not in TRIAL_STATUSES:
        return False

    trial_end = derive_legacy_trial_end(user, sub, plan)
    return bool(trial_end and trial_end <= now)


def build_plan_snapshot(plan: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "plan_name": plan.get("name"),
        "max_weddings": plan.get("max_weddings", 1),
        "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
        "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
        "storage_gb": plan.get("storage_gb", 1),
        "staff_seats": plan.get("staff_seats", 0),
        "features": plan.get("features", {}),
        "price_monthly": plan.get("price_monthly", 0),
        "price_yearly": plan.get("price_yearly"),
        "stripe_price_id_monthly": plan.get("stripe_price_id_monthly"),
        "stripe_price_id_yearly": plan.get("stripe_price_id_yearly"),
        "snapshot_date": now,
    }


def stripe_object_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


def extract_subscription_item(subscription: dict[str, Any]) -> dict[str, Any]:
    items = subscription.get("items", {})
    data = items.get("data", []) if isinstance(items, dict) else []
    if not data:
        return {}
    item = data[0]
    return stripe_object_to_dict(item)


def extract_period_dates(
    subscription: dict[str, Any],
) -> tuple[Optional[datetime], Optional[datetime]]:
    item = extract_subscription_item(subscription)
    period_start = (
        coerce_utc_datetime(item.get("current_period_start"))
        or coerce_utc_datetime(subscription.get("current_period_start"))
        or coerce_utc_datetime(subscription.get("start_date"))
    )
    period_end = (
        coerce_utc_datetime(item.get("current_period_end"))
        or coerce_utc_datetime(subscription.get("current_period_end"))
        or coerce_utc_datetime(subscription.get("trial_end"))
    )
    return period_start, period_end


def is_missing(value: Any) -> bool:
    return value is None or value == ""


async def ensure_plan_prices(
    service: StripeService,
    plans_col,
    plan: dict[str, Any],
    *,
    apply: bool,
    actions: list[str],
) -> dict[str, Any]:
    needs_monthly = not plan.get("stripe_price_id_monthly")
    needs_yearly = plan.get("price_yearly") is not None and not plan.get(
        "stripe_price_id_yearly"
    )
    if not needs_monthly and not needs_yearly:
        return plan

    actions.append("sync missing Stripe product/price IDs for plan")
    if not apply:
        return plan

    stripe_ids = service.sync_plan_to_stripe(plan)
    await plans_col.update_one({"_id": plan["_id"]}, {"$set": stripe_ids})
    repaired_plan = dict(plan)
    repaired_plan.update(stripe_ids)
    return repaired_plan


async def ensure_customer(
    db,
    user: dict[str, Any],
    sub: Optional[dict[str, Any]],
    *,
    apply: bool,
    actions: list[str],
    warnings: list[str],
) -> Optional[str]:
    user_id = stringify_id(user.get("_id"))
    customer_record = await db["stripe_customers"].find_one({"user_id": user_id})
    if not customer_record and user.get("stripe_customer_id"):
        customer_record = await db["stripe_customers"].find_one(
            {"stripe_customer_id": user["stripe_customer_id"]}
        )
    if not customer_record and user.get("email"):
        customer_record = await db["stripe_customers"].find_one(
            {"email": user["email"]}
        )
    customer_id = (
        user.get("stripe_customer_id")
        or (sub or {}).get("stripe_customer_id")
        or (customer_record or {}).get("stripe_customer_id")
    )

    if customer_id:
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if bool(getattr(customer, "deleted", False)):
                warnings.append(
                    f"Stripe customer {customer_id} is deleted; a replacement is needed"
                )
                customer_id = None
        except InvalidRequestError as exc:
            warnings.append(
                f"Stripe customer {customer_id} could not be retrieved: {exc}"
            )
            customer_id = None

    if not customer_id:
        actions.append("create missing Stripe customer")
        if apply:
            customer = stripe.Customer.create(
                email=user["email"],
                name=user.get("company_name")
                or " ".join(
                    part
                    for part in [user.get("first_name"), user.get("last_name")]
                    if part
                )
                or user["email"],
                metadata={"user_id": user_id},
            )
            customer_id = customer.id
        else:
            customer_id = "cus_dry_run_new_customer"

    now = utc_now()
    user_updates: dict[str, Any] = {}
    if user.get("stripe_customer_id") != customer_id:
        user_updates["stripe_customer_id"] = customer_id
    if "trial_warning_sent" not in user:
        user_updates["trial_warning_sent"] = False
    if "registration_source" not in user:
        user_updates["registration_source"] = REGISTRATION_SOURCE_LEGACY

    if user_updates:
        user_updates["updated_at"] = now
        actions.append("patch user Stripe/customer schema fields")
        if apply:
            await db["users"].update_one({"_id": user["_id"]}, {"$set": user_updates})

    mapping_needs_patch = (
        not customer_record
        or customer_record.get("stripe_customer_id") != customer_id
        or customer_record.get("email") != user["email"]
        or customer_record.get("user_id") != user_id
    )
    if mapping_needs_patch:
        actions.append("upsert stripe_customers mapping")
    if apply and mapping_needs_patch:
        mapping_query = (
            {"_id": customer_record["_id"]} if customer_record else {"user_id": user_id}
        )
        await db["stripe_customers"].update_one(
            mapping_query,
            {
                "$set": {
                    "user_id": user_id,
                    "stripe_customer_id": customer_id,
                    "email": user["email"],
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    return customer_id


async def patch_local_subscription_fields(
    db,
    user: dict[str, Any],
    plan: dict[str, Any],
    *,
    stripe_subscription: Optional[dict[str, Any]],
    customer_id: Optional[str],
    apply: bool,
    actions: list[str],
) -> None:
    user_id = stringify_id(user["_id"])
    query: dict[str, Any] = {"user_id": user_id}
    if stripe_subscription and stripe_subscription.get("id"):
        query = {"stripe_subscription_id": stripe_subscription["id"]}

    local_sub = await db["user_subscriptions"].find_one(query)
    if not local_sub and query != {"user_id": user_id}:
        local_sub = await db["user_subscriptions"].find_one({"user_id": user_id})
    if not local_sub:
        return

    now = utc_now()
    updates: dict[str, Any] = {}
    stripe_sub_id = stripe_subscription.get("id") if stripe_subscription else None
    period_start, period_end = (
        extract_period_dates(stripe_subscription)
        if stripe_subscription
        else (None, None)
    )

    if is_missing(local_sub.get("user_email")):
        updates["user_email"] = user["email"]
    if is_missing(local_sub.get("start_date")):
        updates["start_date"] = local_sub.get("created_at") or period_start or now
    if is_missing(local_sub.get("created_by")):
        updates["created_by"] = "system:stripe_trial_repair"
    if customer_id and local_sub.get("stripe_customer_id") != customer_id:
        updates["stripe_customer_id"] = customer_id
    if stripe_sub_id and local_sub.get("stripe_subscription_id") != stripe_sub_id:
        updates["stripe_subscription_id"] = stripe_sub_id
    if is_missing(local_sub.get("plan_snapshot")):
        updates["plan_snapshot"] = build_plan_snapshot(plan, now)
    if is_missing(local_sub.get("usage")):
        updates["usage"] = {
            "weddings_count": 0,
            "ai_credits_used_month": 0,
            "storage_used_gb": 0,
            "staff_seats_used": 0,
        }
    if period_start and is_missing(local_sub.get("current_period_start")):
        updates["current_period_start"] = period_start
    if period_end and is_missing(local_sub.get("current_period_end")):
        updates["current_period_end"] = period_end

    if updates:
        updates["updated_at"] = now
        actions.append("patch required user_subscriptions fields")
        if apply:
            await db["user_subscriptions"].update_one(
                {"_id": local_sub["_id"]}, {"$set": updates}
            )


async def patch_legacy_user_trial_fields(
    db,
    user: dict[str, Any],
    sub: Optional[dict[str, Any]],
    plan: dict[str, Any],
    *,
    apply: bool,
    actions: list[str],
    warnings: list[str],
) -> None:
    legacy_trial_status = derive_legacy_trial_status(user, sub)
    if legacy_trial_status not in TRIAL_STATUSES:
        return

    trial_end = derive_legacy_trial_end(user, sub, plan)
    updates: dict[str, Any] = {}
    current_status = normalize_subscription_status(user.get("subscription_status"))

    if current_status not in TRIAL_STATUSES:
        updates["subscription_status"] = legacy_trial_status
    if trial_end and coerce_utc_datetime(user.get("trial_end_date")) != trial_end:
        updates["trial_end_date"] = trial_end
    if "trial_warning_sent" not in user:
        updates["trial_warning_sent"] = False
    if "is_active" not in user:
        # Current auth treats missing is_active as active; make that explicit so
        # Mongo trial-maintenance queries that require is_active=True can see it.
        updates["is_active"] = True

    if (
        is_public_signup_registration(user.get("registration_source"))
        and user.get("email_verified") is not True
    ):
        warnings.append(
            "public signup email_verified is not true; warning emails require verification, "
            "but expired-trial processing can still run"
        )
    if not trial_end:
        warnings.append(
            "legacy trial status found but no trial_end_date/current_period_end/created_at+plan trial could be derived"
        )

    if updates:
        updates["updated_at"] = utc_now()
        actions.append("patch legacy users trial fields for trial maintenance")
        user.update(updates)
        if apply:
            await db["users"].update_one({"_id": user["_id"]}, {"$set": updates})


async def initialize_usage_if_needed(
    subscription_service: SubscriptionService,
    db,
    user_id: str,
    *,
    apply: bool,
    actions: list[str],
) -> None:
    current_month = utc_now().strftime("%Y-%m")
    existing = await db["usage_tracking"].find_one(
        {"user_id": user_id, "current_month": current_month}
    )
    if existing:
        return

    local_sub = await db["user_subscriptions"].find_one({"user_id": user_id})
    if not local_sub:
        return

    actions.append("initialize usage tracking")
    if apply:
        await subscription_service.initialize_usage_tracking(user_id, local_sub["_id"])


async def find_user_for_subscription(db, user_id: Any) -> Optional[dict[str, Any]]:
    user_id_text = stringify_id(user_id)
    if ObjectId.is_valid(user_id_text):
        user = await db["users"].find_one({"_id": ObjectId(user_id_text)})
        if user:
            return user
    if user_id_text:
        return await db["users"].find_one({"_id": user_id_text})
    return None


async def archive_orphan_subscriptions(
    db,
    *,
    apply: bool,
    limit: int = 0,
) -> list[RepairResult]:
    query = {"archived_at": {"$exists": False}}
    max_scan = limit if limit and limit > 0 else 50000
    cursor = db["user_subscriptions"].find(query).sort("created_at", 1)
    if limit and limit > 0:
        cursor = cursor.limit(limit)
    subscriptions = await cursor.to_list(length=max_scan)

    results: list[RepairResult] = []
    now = utc_now()
    for sub in subscriptions:
        user_id = stringify_id(sub.get("user_id"))
        user = await find_user_for_subscription(db, user_id)
        if user:
            continue

        result = RepairResult(
            email=sub.get("user_email") or "<missing-user>",
            user_id=user_id,
            status="repaired" if apply else "would_repair",
            actions=["archive orphan user_subscriptions record"],
            warnings=[
                "subscription has no matching user document; hiding it from live billing metrics"
            ],
        )
        results.append(result)

        if apply:
            await db["user_subscriptions"].update_one(
                {"_id": sub["_id"]},
                {
                    "$set": {
                        "archived_at": now,
                        "archived_reason": "orphan_user_subscription",
                        "archived_by": "system:stripe_trial_repair",
                        "updated_at": now,
                    }
                },
            )

    return results


async def sync_existing_stripe_subscription(
    service: StripeService,
    db,
    user: dict[str, Any],
    plan_id: Optional[str],
    stripe_subscription_id: str,
    *,
    apply: bool,
    actions: list[str],
) -> Optional[dict[str, Any]]:
    actions.append(
        f"sync local billing state from Stripe subscription {stripe_subscription_id}"
    )
    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
    stripe_sub_dict = stripe_object_to_dict(stripe_sub)
    user_id = stringify_id(user["_id"])
    stripe_customer_id = stripe_sub_dict.get("customer")

    existing_sub = await db["user_subscriptions"].find_one(
        {"stripe_subscription_id": stripe_subscription_id}, {"user_id": 1}
    )
    if existing_sub and existing_sub.get("user_id") not in (None, user_id):
        raise ValueError(
            f"Stripe subscription {stripe_subscription_id} is mapped to "
            f"user {existing_sub['user_id']}, not {user_id}"
        )

    if stripe_customer_id:
        customer_owner = await db["stripe_customers"].find_one(
            {"stripe_customer_id": stripe_customer_id}, {"user_id": 1}
        )
        if customer_owner and customer_owner.get("user_id") not in (None, user_id):
            raise ValueError(
                f"Stripe customer {stripe_customer_id} is mapped to "
                f"user {customer_owner['user_id']}, not {user_id}"
            )

    metadata_user_id = (stripe_sub_dict.get("metadata") or {}).get("user_id")
    if metadata_user_id and metadata_user_id != user_id:
        raise ValueError(
            f"Stripe subscription {stripe_subscription_id} metadata user_id "
            f"{metadata_user_id} does not match {user_id}"
        )

    if apply:
        await service._sync_subscription_state(
            user_id=user_id,
            subscription=stripe_sub_dict,
            customer_id=stripe_customer_id or user.get("stripe_customer_id"),
            plan_id=plan_id,
        )

    return stripe_sub_dict


async def create_trial_subscription(
    service: StripeService,
    db,
    user: dict[str, Any],
    plan: dict[str, Any],
    customer_id: str,
    billing_interval: str,
    trial_days: int,
    trial_end_behavior: str,
    *,
    apply: bool,
    actions: list[str],
) -> Optional[dict[str, Any]]:
    price_field = f"stripe_price_id_{billing_interval}"
    stripe_price_id = plan.get(price_field)
    if not stripe_price_id:
        actions.append(f"missing {price_field}; cannot create trial subscription")
        return None

    actions.append(
        f"create {trial_days}-day Stripe trial subscription on {plan['_id']} ({billing_interval})"
    )
    if not apply:
        return None

    user_id = stringify_id(user["_id"])
    stripe_sub = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": stripe_price_id}],
        trial_period_days=trial_days,
        trial_settings={"end_behavior": {"missing_payment_method": trial_end_behavior}},
        metadata={
            "user_id": user_id,
            "plan_id": plan["_id"],
            "billing_interval": billing_interval,
            "trial_days": str(trial_days),
            "repaired_by": "repair_planner_stripe_trials",
        },
    )
    stripe_sub_dict = stripe_object_to_dict(stripe_sub)

    await service._sync_subscription_state(
        user_id=user_id,
        subscription=stripe_sub_dict,
        customer_id=customer_id,
        plan_id=plan["_id"],
        extra_updates={"created_by": "system:stripe_trial_repair"},
    )
    return stripe_sub_dict


async def repair_user(
    db,
    service: StripeService,
    subscription_service: SubscriptionService,
    user: dict[str, Any],
    *,
    apply: bool,
    default_plan_id: Optional[str],
    override_trial_days: Optional[int],
    include_expired: bool,
    sync_plan_prices: bool,
    create_missing_subscriptions: bool,
    trial_end_behavior: str,
) -> RepairResult:
    email = user.get("email", "<missing-email>")
    user_id = stringify_id(user.get("_id"))
    result = RepairResult(email=email, user_id=user_id, status="scanned")

    root_admin_email = settings.root_admin_email
    if not is_repair_candidate(user, root_admin_email):
        result.status = "skipped"
        result.warnings.append("not a planner billing user")
        return result

    if not ObjectId.is_valid(user_id):
        result.status = "skipped"
        result.warnings.append(
            "planner has non-ObjectId _id; Stripe sync path expects ObjectId"
        )
        return result

    local_subs = (
        await db["user_subscriptions"].find({"user_id": user_id}).to_list(length=20)
    )
    local_sub = choose_local_subscription(local_subs)

    plan_id = user.get("plan_id") or (local_sub or {}).get("plan_id")
    if not plan_id and default_plan_id:
        plan_id = default_plan_id
        result.actions.append(f"use explicit --default-plan-id {default_plan_id}")

    if not plan_id:
        result.status = "skipped"
        result.warnings.append(
            "missing plan_id; pass --default-plan-id to repair explicitly"
        )
        return result

    plan = await db["subscription_plans"].find_one({"_id": plan_id})
    if not plan:
        result.status = "skipped"
        result.warnings.append(f"plan {plan_id} not found")
        return result

    if sync_plan_prices:
        plan = await ensure_plan_prices(
            service,
            db["subscription_plans"],
            plan,
            apply=apply,
            actions=result.actions,
        )

    await patch_legacy_user_trial_fields(
        db,
        user,
        local_sub,
        plan,
        apply=apply,
        actions=result.actions,
        warnings=result.warnings,
    )

    billing_interval = determine_billing_interval(user, local_sub)
    customer_id = await ensure_customer(
        db,
        user,
        local_sub,
        apply=apply,
        actions=result.actions,
        warnings=result.warnings,
    )

    stripe_subscription_id = user.get("stripe_subscription_id") or (
        local_sub or {}
    ).get("stripe_subscription_id")
    stripe_subscription: Optional[dict[str, Any]] = None

    if stripe_subscription_id:
        stripe_subscription = await sync_existing_stripe_subscription(
            service,
            db,
            user,
            plan_id,
            stripe_subscription_id,
            apply=apply,
            actions=result.actions,
        )
        customer_id = stripe_subscription.get("customer") or customer_id
    else:
        if not create_missing_subscriptions:
            result.warnings.append("missing Stripe subscription; creation disabled")
        elif local_trial_already_expired(user, local_sub, plan, utc_now()):
            result.warnings.append(
                "legacy local trial is already expired; patched users fields so trial maintenance can expire/notify instead of creating a new Stripe trial"
            )
        elif not can_create_missing_trial_subscription(
            user, include_expired=include_expired
        ):
            status = normalize_subscription_status(user.get("subscription_status"))
            result.warnings.append(
                f"missing Stripe subscription but local status {status!r} is not trial-repair eligible"
            )
        else:
            trial_days = determine_trial_days(
                user,
                plan,
                utc_now(),
                override_trial_days=override_trial_days,
            )
            if trial_days <= 0:
                result.warnings.append(
                    f"missing Stripe subscription but plan {plan_id} has no trial_days"
                )
            elif customer_id:
                stripe_subscription = await create_trial_subscription(
                    service,
                    db,
                    user,
                    plan,
                    customer_id,
                    billing_interval,
                    trial_days,
                    trial_end_behavior,
                    apply=apply,
                    actions=result.actions,
                )
            else:
                result.warnings.append(
                    "missing Stripe customer; cannot create subscription in dry-run"
                )

    await patch_local_subscription_fields(
        db,
        user,
        plan,
        stripe_subscription=stripe_subscription,
        customer_id=customer_id,
        apply=apply,
        actions=result.actions,
    )

    await initialize_usage_if_needed(
        subscription_service,
        db,
        user_id,
        apply=apply,
        actions=result.actions,
    )

    if result.actions:
        result.status = "repaired" if apply else "would_repair"
    else:
        result.status = "ok"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair planner Stripe customers, subscriptions, and trial records."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Write repairs. Default is dry-run."
    )
    parser.add_argument("--email", help="Repair a single planner email.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum users to scan.")
    parser.add_argument(
        "--default-plan-id",
        help="Explicit plan to use only when a planner is missing plan_id.",
    )
    parser.add_argument(
        "--trial-days",
        type=int,
        default=None,
        help="Override trial days for newly-created missing Stripe subscriptions.",
    )
    parser.add_argument(
        "--include-expired",
        action="store_true",
        help="Allow expired local planners without Stripe subscriptions to receive a repaired trial.",
    )
    parser.add_argument(
        "--no-create-missing-subscriptions",
        action="store_true",
        help="Only patch customers/local fields; do not create missing Stripe subscriptions.",
    )
    parser.add_argument(
        "--sync-plan-prices",
        action="store_true",
        help="Create/update missing Stripe product and price IDs for plans before repair.",
    )
    parser.add_argument(
        "--trial-end-behavior",
        choices=("cancel", "pause"),
        default="cancel",
        help="Stripe behavior if a repaired trial ends without a payment method.",
    )
    parser.add_argument(
        "--archive-orphan-subscriptions",
        action="store_true",
        help="Archive user_subscriptions rows whose user_id no longer maps to a user.",
    )
    parser.add_argument(
        "--orphan-limit",
        type=int,
        default=0,
        help="Maximum orphan subscription rows to scan when archiving orphans.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    if not settings.stripe_enabled:
        print("[ERROR] STRIPE_ENABLED is false; refusing to run Stripe repair.")
        return 2
    if not settings.stripe_secret_key:
        print("[ERROR] STRIPE_SECRET_KEY is not configured.")
        return 2

    stripe.api_key = settings.stripe_secret_key

    await init_database()
    db = mongo.db
    service = StripeService()
    subscription_service = SubscriptionService()
    stats = RepairStats()

    query: dict[str, Any] = {"role": "wedding_planner"}
    if args.email:
        query = {"email": args.email}

    print("=" * 72)
    print("Planner Stripe trial repair")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Query: {query}")
    print("=" * 72)

    try:
        cursor = db["users"].find(query).sort("created_at", 1)
        if args.limit and args.limit > 0:
            cursor = cursor.limit(args.limit)

        async for user in cursor:
            stats.scanned += 1
            try:
                result = await repair_user(
                    db,
                    service,
                    subscription_service,
                    user,
                    apply=args.apply,
                    default_plan_id=args.default_plan_id,
                    override_trial_days=args.trial_days,
                    include_expired=args.include_expired,
                    sync_plan_prices=args.sync_plan_prices,
                    create_missing_subscriptions=not args.no_create_missing_subscriptions,
                    trial_end_behavior=args.trial_end_behavior,
                )
            except (StripeError, Exception) as exc:
                result = RepairResult(
                    email=user.get("email", "<missing-email>"),
                    user_id=stringify_id(user.get("_id")),
                    status="error",
                    error=str(exc),
                )

            if result.status == "repaired":
                stats.repaired += 1
            elif result.status == "would_repair":
                stats.would_repair += 1
            elif result.status == "skipped":
                stats.skipped += 1
            elif result.status == "error":
                stats.errors += 1

            print(f"\n[{result.status.upper()}] {result.email} ({result.user_id})")
            for action in result.actions:
                prefix = "did" if args.apply else "would"
                print(f"  - {prefix} {action}")
            for warning in result.warnings:
                print(f"  ! {warning}")
            if result.error:
                print(f"  x {result.error}")

        if args.archive_orphan_subscriptions:
            print("\n" + "=" * 72)
            print("Orphan subscription archive")
            orphan_results = await archive_orphan_subscriptions(
                db,
                apply=args.apply,
                limit=args.orphan_limit,
            )
            for result in orphan_results:
                if result.status == "repaired":
                    stats.repaired += 1
                elif result.status == "would_repair":
                    stats.would_repair += 1

                print(f"\n[{result.status.upper()}] {result.email} ({result.user_id})")
                for action in result.actions:
                    prefix = "did" if args.apply else "would"
                    print(f"  - {prefix} {action}")
                for warning in result.warnings:
                    print(f"  ! {warning}")
            print(f"\n  orphan rows found: {len(orphan_results)}")

        print("\n" + "=" * 72)
        print("Summary")
        print(f"  scanned      : {stats.scanned}")
        print(f"  repaired     : {stats.repaired}")
        print(f"  would repair : {stats.would_repair}")
        print(f"  skipped      : {stats.skipped}")
        print(f"  errors       : {stats.errors}")
        print("=" * 72)
        return 1 if stats.errors else 0
    finally:
        await close_database()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
