from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from bson import ObjectId
import mongomock
import pytest

from app.services.storefront_domain_operational_monitor import (
    StorefrontDomainOperationalMonitor,
)


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, value):
        self._cursor = self._cursor.limit(value)
        return self

    async def to_list(self, length=None):
        rows = list(self._cursor)
        return rows if length is None else rows[:length]


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._collection.count_documents(*args, **kwargs)


class AsyncDatabase:
    def __init__(self, raw):
        self.raw = raw
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = AsyncCollection(self.raw[name])
        return self._collections[name]


class FakeMongo:
    def __init__(self):
        self.raw = mongomock.MongoClient()["storefront_domain_ops_test"]
        self.db = AsyncDatabase(self.raw)


class MetricSink:
    def __init__(self):
        self.counters: list[tuple[str, dict]] = []
        self.gauges: list[tuple[str, float, dict]] = []

    def counter(self, name: str, **tags):
        self.counters.append((name, tags))

    def gauge(self, name: str, value: float, **tags):
        self.gauges.append((name, value, tags))


def _domain(now: datetime, **overrides) -> dict:
    value = {
        "_id": ObjectId(),
        "planner_id": "planner-customer-identity",
        "hostname": "weddings.customer-secret.example",
        "revision": 3,
        "application_status": "operator_review",
        "last_error": {
            "code": "provider_hostname_missing",
            "support_id": "sfd_support_one",
        },
        "retry_due_at": now,
        "updated_at": now,
    }
    value.update(overrides)
    return value


def _monitor(now: datetime):
    mongo = FakeMongo()
    metrics = MetricSink()
    monitor = StorefrontDomainOperationalMonitor(
        mongo_client=mongo,
        now=lambda: now,
        counter=metrics.counter,
        gauge=metrics.gauge,
    )
    return monitor, mongo, metrics


@pytest.mark.asyncio
async def test_same_unresolved_phase_does_not_alert_storm_when_support_id_rotates():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    domain = _domain(now)
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))

    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"last_error.support_id": "sfd_support_rotated_by_poll"}},
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )

    alerts = list(mongo.raw.notifications.find({}))
    assert len(alerts) == 1
    assert alerts[0]["target_audience"] == "root_admin"
    assert alerts[0]["metadata"]["phase"] == "operator_review"
    assert alerts[0]["metadata"]["support_id"] == "sfd_support_one"
    assert alerts[0]["action_url"] == "/admin/platform?tab=storefront"
    assert metrics.counters == [
        (
            "storefront.domain.operational_alert",
            {"category": "operator_review", "phase": "operator_review"},
        )
    ]
    persisted = mongo.raw.storefront_domain_operational_metrics.find_one(
        {"name": "storefront.domain.operational_alert"}
    )
    assert persisted["value"] == 1
    assert persisted["tags"] == {
        "category": "operator_review",
        "phase": "operator_review",
    }


@pytest.mark.asyncio
async def test_stale_failure_snapshot_cannot_alert_after_domain_state_recovers():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    domain = _domain(now)
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))
    stale_snapshot = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"application_status": "active", "last_error": None}},
    )

    await monitor.observe_domain(stale_snapshot)

    assert mongo.raw.notifications.count_documents({}) == 0
    assert metrics.counters == []


@pytest.mark.asyncio
async def test_resolved_then_recurrent_incident_gets_one_new_durable_alert():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, _ = _monitor(now)
    domain = _domain(now)
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))

    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {
            "$set": {
                "application_status": "active",
                "last_error": None,
            }
        },
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {
            "$set": {
                "application_status": "operator_review",
                "last_error": {
                    "code": "provider_hostname_identity_mismatch",
                    "support_id": "sfd_support_recurrence",
                },
            }
        },
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )

    assert mongo.raw.notifications.count_documents({}) == 2
    supports = {
        row["metadata"]["support_id"] for row in mongo.raw.notifications.find({})
    }
    assert supports == {"sfd_support_one", "sfd_support_recurrence"}


@pytest.mark.asyncio
async def test_resolved_incident_also_resolves_root_admin_notification():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, _ = _monitor(now)
    domain = _domain(now)
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))

    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )
    alert = mongo.raw.notifications.find_one({})
    assert alert["status"] == "active"

    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"application_status": "active", "last_error": None}},
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )

    resolved = mongo.raw.notifications.find_one({"_id": alert["_id"]})
    assert resolved["status"] == "resolved"
    assert resolved["metadata"]["resolved_at"].replace(tzinfo=timezone.utc) == now


@pytest.mark.asyncio
async def test_verified_conflict_review_emits_and_resolves_sanitized_alert():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    conflict = {
        "_id": ObjectId(),
        "claimant_planner_id": "planner-secret-claimant",
        "hostname": "weddings.customer-secret.example",
        "attempt_id": "sdc_secret_attempt",
        "revision": 4,
        "application_status": "operator_review",
        "ownership_status": "verified",
        "last_error": {
            "code": "hostname_conflict_requires_review",
            "support_id": "sfd_conflict_review",
        },
        "updated_at": now,
    }
    mongo.raw.storefront_domain_conflict_claims.insert_one(deepcopy(conflict))

    observed = await monitor.observe_conflict_reviews()

    assert observed == 1
    alert = mongo.raw.notifications.find_one({})
    assert alert["target_audience"] == "root_admin"
    assert alert["action_url"] == "/admin/platform?tab=storefront"
    assert alert["metadata"]["category"] == "operator_review"
    serialized = repr(alert)
    assert conflict["hostname"] not in serialized
    assert conflict["claimant_planner_id"] not in serialized
    assert conflict["attempt_id"] not in serialized
    assert (
        "storefront.domain.operational_alert",
        {"category": "operator_review", "phase": "operator_review"},
    ) in metrics.counters

    mongo.raw.storefront_domain_conflict_claims.update_one(
        {"_id": conflict["_id"]},
        {
            "$set": {
                "application_status": "disconnected",
                "last_error": None,
                "updated_at": now,
            }
        },
    )
    assert await monitor.observe_conflict_reviews() == 1
    assert mongo.raw.notifications.find_one({"_id": alert["_id"]})["status"] == (
        "resolved"
    )


@pytest.mark.asyncio
async def test_provider_outcome_is_counted_once_until_it_resolves_and_recurs():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    domain = _domain(
        now,
        application_status="certificate_validation",
        last_error={
            "code": "domain_reconciliation_failed",
            "support_id": "sfd_provider_first",
        },
        provider_last_error={
            "operation": "get_custom_hostname",
            "provider_status_code": 503,
        },
    )
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))

    for support_id, status_code in (
        ("sfd_provider_first", 503),
        ("sfd_provider_poll_rotated", 502),
    ):
        mongo.raw.storefront_domains.update_one(
            {"_id": domain["_id"]},
            {
                "$set": {
                    "last_error.support_id": support_id,
                    "provider_last_error.provider_status_code": status_code,
                }
            },
        )
        await monitor.observe_domain(
            mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
        )

    assert mongo.raw.notifications.count_documents({}) == 1
    provider_metric = mongo.raw.storefront_domain_operational_metrics.find_one(
        {"name": "storefront.domain.provider_outcome"}
    )
    assert provider_metric["value"] == 1

    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$unset": {"provider_last_error": ""}, "$set": {"last_error": None}},
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {
            "$set": {
                "last_error": {
                    "code": "domain_reconciliation_failed",
                    "support_id": "sfd_provider_recurrence",
                },
                "provider_last_error": {
                    "operation": "get_custom_hostname",
                    "provider_status_code": 503,
                },
            }
        },
    )
    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )

    assert mongo.raw.notifications.count_documents({}) == 2
    provider_metric = mongo.raw.storefront_domain_operational_metrics.find_one(
        {"name": "storefront.domain.provider_outcome"}
    )
    assert provider_metric["value"] == 2
    assert (
        len(
            [
                row
                for row in metrics.counters
                if row[0] == "storefront.domain.provider_outcome"
            ]
        )
        == 2
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("phase", "provider_status", "expected_category"),
    [
        ("disconnect_failed", 503, "disconnect_failed"),
        ("action_required", None, "action_required"),
        ("certificate_validation", 429, "provider_rate_limited"),
        ("hostname_validation", 502, "provider_server_error"),
    ],
)
async def test_alerts_cover_required_worker_failures_without_customer_identity(
    phase, provider_status, expected_category
):
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    domain = _domain(
        now,
        application_status=phase,
        last_error={
            "code": "domain_reconciliation_failed",
            "support_id": f"sfd_{expected_category}",
        },
        **(
            {
                "provider_last_error": {
                    "operation": "get_custom_hostname",
                    "kind": "provider",
                    "provider_status_code": provider_status,
                    "errors": [{"code": "bounded", "message": "not copied"}],
                }
            }
            if provider_status is not None
            else {}
        ),
    )
    mongo.raw.storefront_domains.insert_one(deepcopy(domain))

    await monitor.observe_domain(
        mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    )

    alert = mongo.raw.notifications.find_one({})
    assert alert["metadata"]["category"] == expected_category
    serialized = repr(alert)
    assert domain["hostname"] not in serialized
    assert domain["planner_id"] not in serialized
    assert "not copied" not in serialized
    assert alert["metadata"]["domain_reference"].startswith("sfdomain_")
    if provider_status in {429, 502, 503}:
        assert (
            "storefront.domain.provider_outcome",
            {
                "outcome": (
                    "rate_limited" if provider_status == 429 else "server_error"
                ),
                "phase": phase,
            },
        ) in metrics.counters


@pytest.mark.asyncio
async def test_backlog_metrics_report_exact_count_and_bounded_oldest_age():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, metrics = _monitor(now)
    mongo.raw.storefront_domains.insert_many(
        [
            _domain(
                now,
                application_status="certificate_validation",
                retry_due_at=now - timedelta(minutes=10),
                updated_at=now - timedelta(minutes=12),
            ),
            _domain(
                now,
                application_status="disconnect_failed",
                retry_due_at=now - timedelta(minutes=2),
            ),
            _domain(
                now,
                application_status="certificate_validation",
                retry_due_at=now + timedelta(minutes=5),
            ),
            _domain(now, application_status="expired", retry_due_at=now),
        ]
    )

    await monitor.observe_backlog(
        ("certificate_validation", "disconnect_failed", "active")
    )

    assert (
        "storefront.domain.reconciliation.backlog_count",
        2.0,
        {},
    ) in metrics.gauges
    assert (
        "storefront.domain.reconciliation.backlog_oldest_age_seconds",
        600.0,
        {},
    ) in metrics.gauges
    persisted = {
        row["name"]: row["value"]
        for row in mongo.raw.storefront_domain_operational_metrics.find(
            {"kind": "gauge"}
        )
    }
    assert persisted == {
        "storefront.domain.reconciliation.backlog_count": 2.0,
        "storefront.domain.reconciliation.backlog_oldest_age_seconds": 600.0,
    }
    assert (
        mongo.raw.notifications.count_documents({"metadata.category": "worker_backlog"})
        == 0
    )


@pytest.mark.asyncio
async def test_stale_backlog_uses_one_resumable_root_admin_alert():
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    monitor, mongo, _ = _monitor(now)
    domain = _domain(
        now,
        application_status="certificate_validation",
        retry_due_at=now - timedelta(minutes=20),
    )
    mongo.raw.storefront_domains.insert_one(domain)
    phases = ("certificate_validation",)

    await monitor.observe_backlog(phases)
    await monitor.observe_backlog(phases)

    alert = mongo.raw.notifications.find_one({"metadata.category": "worker_backlog"})
    assert alert["status"] == "active"
    assert alert["target_audience"] == "root_admin"
    assert alert["metadata"]["phase"] == "backlog"
    assert alert["metadata"]["support_id"] == "sfd_storefront_domain_backlog"
    assert (
        mongo.raw.notifications.count_documents({"metadata.category": "worker_backlog"})
        == 1
    )
    assert (
        mongo.raw.storefront_domain_operational_metrics.find_one(
            {"name": "storefront.domain.worker_backlog_alert"}
        )["value"]
        == 1
    )

    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"retry_due_at": now + timedelta(minutes=1)}},
    )
    await monitor.observe_backlog(phases)
    assert mongo.raw.notifications.find_one({"_id": alert["_id"]})["status"] == (
        "resolved"
    )

    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"retry_due_at": now - timedelta(minutes=20)}},
    )
    await monitor.observe_backlog(phases)
    recurrent = mongo.raw.notifications.find_one({"_id": alert["_id"]})
    assert recurrent["status"] == "active"
    assert recurrent["read_by"] == []
    assert recurrent["dismissed_by"] == []
    assert (
        mongo.raw.storefront_domain_operational_metrics.find_one(
            {"name": "storefront.domain.worker_backlog_alert"}
        )["value"]
        == 2
    )
