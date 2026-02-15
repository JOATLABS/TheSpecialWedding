"""Service for compiling SaaS platform metrics.

The logic previously lived inside the FastAPI route and mixed direct Motor
calls with synchronous mongomock fallbacks.  This module centralises the
queries, makes the database access patterns explicit, and batches I/O so the
route handler stays lean while remaining testable.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Sequence, Tuple

try:  # pragma: no cover - optional Motor runtime
    from motor.motor_asyncio import AsyncIOMotorCollection
except ImportError:  # pragma: no cover - Motor not installed in tests
    AsyncIOMotorCollection = None  # type: ignore[assignment,misc]
from app.core.database import mongo

logger = logging.getLogger(__name__)

CancelledStatuses = {"cancelled", "deleted", "inactive"}


class PlatformMetricsService:
    """Aggregate platform metrics for the admin analytics dashboard."""

    def __init__(self, mongo_connector: Any) -> None:
        self._mongo = mongo_connector
        self._index_lock = asyncio.Lock()
        self._indexes_ready = False

    async def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return the most recent metrics snapshot or ``None`` when empty."""

        await self._ensure_indexes()

        collection = self._mongo.get_platform_metrics_collection()
        document = await self._find_one(
            collection,
            {},
            sort=[("snapshot_time", -1), ("_id", -1)],
        )

        if not document:
            return None

        return self._prepare_snapshot_document(document)

    async def save_snapshot(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Persist a metrics snapshot payload and return the stored document."""

        await self._ensure_indexes()

        collection = self._mongo.get_platform_metrics_collection()

        document: Dict[str, Any] = {
            key: value for key, value in payload.items() if key != "id"
        }

        snapshot_time_candidate = document.get("snapshot_time") or document.get(
            "timestamp"
        )
        snapshot_time = self._parse_datetime(snapshot_time_candidate)
        if snapshot_time is None:
            snapshot_time = datetime.now(timezone.utc)
        snapshot_time = self._normalize_to_utc(snapshot_time)

        document["snapshot_time"] = snapshot_time

        ingested_at = datetime.now(timezone.utc)
        document["ingested_at"] = ingested_at

        document.setdefault(
            "timestamp",
            snapshot_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        document.setdefault("metrics", {})

        insert_result = await self._call_collection_method(
            collection, "insert_one", document
        )
        inserted_id = getattr(insert_result, "inserted_id", None)
        if inserted_id is not None:
            document["_id"] = inserted_id

        return self._prepare_snapshot_document(document)

    async def get_history(
        self, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Return ordered snapshots, optionally filtered by ``since``."""

        await self._ensure_indexes()

        collection = self._mongo.get_platform_metrics_collection()

        query: Dict[str, Any] = {}
        if since is not None:
            query["snapshot_time"] = {"$gte": self._normalize_to_utc(since)}

        cursor = collection.find(query).sort(
            [("snapshot_time", -1), ("_id", -1)]
        )
        documents = await self._collect_cursor(cursor)

        return [self._prepare_snapshot_document(doc) for doc in documents]

    async def compile_metrics(self, timeframe: str) -> Dict[str, Any]:
        """Return the payload consumed by `/admin/saas/analytics/platform`."""

        await self._ensure_indexes()

        period_days = self._resolve_timeframe(timeframe)
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        users_task = asyncio.create_task(self._compile_user_metrics(period_start))
        subscriptions_task = asyncio.create_task(
            self._compile_subscription_metrics(period_start)
        )
        operations_task = asyncio.create_task(
            self._compile_operations_metrics(period_start, now)
        )

        users, subscriptions, operations = await asyncio.gather(
            users_task, subscriptions_task, operations_task
        )

        return {
            "generated_at": now.isoformat() + "Z",
            "timeframe": timeframe,
            "users": users,
            "subscriptions": subscriptions,
            "operations": operations,
        }

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return

        async with self._index_lock:
            if self._indexes_ready:
                return

            collection = self._mongo.get_platform_metrics_collection()
            if not hasattr(collection, "create_index"):
                logger.warning(
                    "Platform metrics collection lacks create_index; skipping index setup"
                )
            else:
                try:
                    await self._call_collection_method(
                        collection, "create_index", "snapshot_time"
                    )
                except Exception as exc:
                    logger.warning(
                        "Unable to create snapshot_time index: %s", exc, exc_info=True
                    )

            self._indexes_ready = True

    async def _compile_user_metrics(self, period_start: datetime) -> Dict[str, Any]:
        users_collection = self._mongo.get_users_collection()

        total_task = asyncio.create_task(
            self._count_documents(users_collection, {})
        )
        active_task = asyncio.create_task(
            self._count_documents(users_collection, {"is_active": True})
        )
        new_task = asyncio.create_task(
            self._count_documents(
                users_collection, {"created_at": {"$gte": period_start}}
            )
        )

        try:
            role_breakdown_docs = await self._aggregate(
                users_collection,
                [
                    {"$group": {"_id": "$role", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                ],
            )
        except Exception as exc:  # pragma: no cover - mongomock fallback path
            logger.debug("Role breakdown pipeline failed: %s", exc)
            role_breakdown_docs = []

        total_users, active_users, new_users = await asyncio.gather(
            total_task, active_task, new_task
        )

        role_breakdown = {
            (doc.get("_id") or "unassigned"): int(doc.get("count", 0))
            for doc in role_breakdown_docs
        }

        growth_rate = (new_users / total_users * 100) if total_users else 0.0

        return {
            "total": total_users,
            "active": active_users,
            "new_in_period": new_users,
            "growth_rate": growth_rate,
            "role_breakdown": role_breakdown,
        }

    async def _compile_subscription_metrics(self, period_start: datetime) -> Dict[str, Any]:
        subscriptions_collection = self._mongo.db.get_collection("user_subscriptions")
        plans_collection = self._mongo.get_subscription_plans_collection()

        # Filter out null/missing statuses and group by actual status values
        status_docs = await self._safe_aggregate(
            subscriptions_collection,
            [
                {"$match": {"status": {"$ne": None, "$exists": True}}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ],
        )

        status_breakdown: Dict[str, int] = {
            str(doc.get("_id")): int(doc.get("count", 0)) for doc in status_docs
        }

        # Ensure all expected status keys exist with default 0 to prevent NaN in frontend
        expected_statuses = ["active", "trial", "cancelled", "expired", "suspended", "pending_payment"]
        for status in expected_statuses:
            if status not in status_breakdown:
                status_breakdown[status] = 0

        total_subscriptions = sum(status_breakdown.values())

        active_plans_task = asyncio.create_task(
            self._count_documents(plans_collection, {"is_active": True})
        )

        revenue_summary = await self._calculate_revenue_summary(
            subscriptions_collection, plans_collection
        )

        monthly_revenue = revenue_summary["monthly"]
        annual_revenue = revenue_summary["annual"]
        plan_breakdown = revenue_summary["plans"]

        projected_annual = monthly_revenue * 12 if monthly_revenue else annual_revenue

        active_plans = await active_plans_task

        return {
            "total": total_subscriptions,
            "status_breakdown": status_breakdown,
            "active_plans": active_plans,
            "monthly_recurring_revenue": monthly_revenue,
            "yearly_recurring_revenue": annual_revenue,
            "projected_annual_revenue": projected_annual,
            "plan_breakdown": plan_breakdown,
        }

    async def _compile_operations_metrics(
        self, period_start: datetime, now: datetime
    ) -> Dict[str, Any]:
        weddings_task = asyncio.create_task(
            self._compile_wedding_metrics(period_start, now)
        )
        forms_task = asyncio.create_task(self._compile_form_metrics(period_start))
        comms_task = asyncio.create_task(
            self._compile_communications_metrics(period_start)
        )

        weddings, forms, communications = await asyncio.gather(
            weddings_task, forms_task, comms_task
        )

        return {
            "weddings": weddings,
            "forms": forms,
            "communications": communications,
        }

    async def _compile_wedding_metrics(
        self, period_start: datetime, now: datetime
    ) -> Dict[str, Any]:
        weddings_collection = self._mongo.get_weddings_collection()

        pipeline: List[Dict[str, Any]] = [
            {
                "$addFields": {
                    "event_date": {
                        "$cond": [
                            {"$eq": [{"$type": "$date"}, "date"]},
                            "$date",
                            {
                                "$cond": [
                                    {"$eq": [{"$type": "$date"}, "string"]},
                                    {
                                        "$dateFromString": {
                                            "dateString": "$date",
                                            "onError": None,
                                            "onNull": None,
                                        }
                                    },
                                    None,
                                ]
                            },
                        ]
                    },
                    "created_normalized": {
                        "$cond": [
                            {"$eq": [{"$type": "$created_at"}, "date"]},
                            "$created_at",
                            {
                                "$cond": [
                                    {"$eq": [{"$type": "$created_at"}, "string"]},
                                    {
                                        "$dateFromString": {
                                            "dateString": "$created_at",
                                            "onError": None,
                                            "onNull": None,
                                        }
                                    },
                                    None,
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "active": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", list(CancelledStatuses)]},
                                0,
                                1,
                            ]
                        }
                    },
                    "upcoming": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$event_date", None]},
                                        {"$gte": ["$event_date", now]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "created_in_period": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$created_normalized", None]},
                                        {"$gte": ["$created_normalized", period_start]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]

        try:
            aggregates = await self._aggregate(weddings_collection, pipeline)
        except Exception as exc:  # pragma: no cover - mongomock fallback path
            logger.debug("Wedding pipeline fallback engaged: %s", exc)
            return await self._wedding_fallback(period_start, now, weddings_collection)

        summary = aggregates[0] if aggregates else {}

        return {
            "total": int(summary.get("total", 0)),
            "active": int(summary.get("active", 0)),
            "upcoming": int(summary.get("upcoming", 0)),
            "created_in_period": int(summary.get("created_in_period", 0)),
            "guest_total": await self._count_documents(
                self._mongo.get_guest_collection(), {}
            ),
            "rsvp_total": await self._count_documents(
                self._mongo.get_rsvps_collection(), {}
            ),
        }

    async def _wedding_fallback(
        self,
        period_start: datetime,
        now: datetime,
        weddings_collection: Any,
    ) -> Dict[str, Any]:
        total = active = upcoming = created = 0

        async for wedding in self._iterate_documents(
            weddings_collection, {}, {"status": 1, "date": 1, "created_at": 1}
        ):
            total += 1

            status = str(wedding.get("status")) if wedding.get("status") else ""
            if status.lower() not in CancelledStatuses:
                active += 1

            event_date = self._parse_datetime(wedding.get("date"))
            if event_date and event_date.date() >= now.date():
                upcoming += 1

            created_at = self._parse_datetime(wedding.get("created_at"))
            if created_at and created_at >= period_start:
                created += 1

        guest_total = await self._count_documents(
            self._mongo.get_guest_collection(), {}
        )
        rsvp_total = await self._count_documents(
            self._mongo.get_rsvps_collection(), {}
        )

        return {
            "total": total,
            "active": active,
            "upcoming": upcoming,
            "created_in_period": created,
            "guest_total": guest_total,
            "rsvp_total": rsvp_total,
        }

    async def _compile_form_metrics(self, period_start: datetime) -> Dict[str, Any]:
        forms_collection = self._mongo.get_forms_collection()
        responses_collection = self._mongo.get_form_responses_collection()

        total_task = asyncio.create_task(
            self._count_documents(forms_collection, {"is_active": True})
        )
        new_task = asyncio.create_task(
            self._count_documents(
                forms_collection,
                {"is_active": True, "created_at": {"$gte": period_start}},
            )
        )
        responses_total_task = asyncio.create_task(
            self._count_documents(responses_collection, {})
        )
        responses_period_task = asyncio.create_task(
            self._count_documents(
                responses_collection, {"submitted_at": {"$gte": period_start}}
            )
        )

        (
            total_forms,
            new_forms,
            responses_total,
            responses_period,
        ) = await asyncio.gather(
            total_task, new_task, responses_total_task, responses_period_task
        )

        return {
            "total": total_forms,
            "new_in_period": new_forms,
            "responses_total": responses_total,
            "responses_in_period": responses_period,
        }

    async def _compile_communications_metrics(
        self, period_start: datetime
    ) -> Dict[str, Any]:
        notifications_collection = self._mongo.db.get_collection("notifications")
        email_logs_collection = self._mongo.db.get_collection("email_logs")
        ai_usage_collection = self._mongo.get_ai_usage_collection()

        notifications_total_task = asyncio.create_task(
            self._count_documents(notifications_collection, {"status": "sent"})
        )
        notifications_period_task = asyncio.create_task(
            self._count_documents(
                notifications_collection,
                {"status": "sent", "sent_at": {"$gte": period_start}},
            )
        )
        emails_total_task = asyncio.create_task(
            self._count_documents(email_logs_collection, {})
        )
        emails_period_task = asyncio.create_task(
            self._count_documents(
                email_logs_collection,
                {"status": "success", "sent_at": {"$gte": period_start}},
            )
        )
        ai_total_task = asyncio.create_task(
            self._count_documents(ai_usage_collection, {})
        )
        ai_period_task = asyncio.create_task(
            self._count_documents(
                ai_usage_collection, {"created_at": {"$gte": period_start}}
            )
        )

        (
            notifications_total,
            notifications_period,
            emails_total,
            emails_period,
            ai_total,
            ai_period,
        ) = await asyncio.gather(
            notifications_total_task,
            notifications_period_task,
            emails_total_task,
            emails_period_task,
            ai_total_task,
            ai_period_task,
        )

        return {
            "notifications_sent": notifications_total,
            "notifications_in_period": notifications_period,
            "email_logs_total": emails_total,
            "emails_sent_in_period": emails_period,
            "ai_events_total": ai_total,
            "ai_events_in_period": ai_period,
        }

    async def _calculate_revenue_summary(
        self, subscriptions_collection: Any, plans_collection: Any
    ) -> Dict[str, Any]:
        pipeline: List[Dict[str, Any]] = [
            # Include both active and trial subscriptions in plan breakdown
            {"$match": {"status": {"$in": ["active", "trial"]}}},
            {
                "$lookup": {
                    "from": plans_collection.name
                    if hasattr(plans_collection, "name")
                    else "subscription_plans",
                    "localField": "plan_id",
                    "foreignField": "_id",
                    "as": "plan_doc",
                }
            },
            {"$unwind": {"path": "$plan_doc", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "plan_id": "$plan_doc._id",
                    "plan_name": "$plan_doc.name",
                    "billing_interval": "$billing_interval",
                    "price_monthly": {
                        "$ifNull": ["$plan_doc.price_monthly", 0]
                    },
                    "price_yearly": {
                        "$ifNull": ["$plan_doc.price_yearly", 0]
                    },
                }
            },
            {
                "$project": {
                    "plan_id": 1,
                    "plan_name": 1,
                    "monthly_revenue": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {
                                        "$eq": ["$billing_interval", "yearly"]
                                    },
                                    "then": {
                                        "$cond": [
                                            {"$gt": ["$price_yearly", 0]},
                                            {"$divide": ["$price_yearly", 12]},
                                            "$price_monthly",
                                        ]
                                    },
                                },
                                {
                                    "case": {
                                        "$eq": ["$billing_interval", "monthly"]
                                    },
                                    "then": {
                                        "$cond": [
                                            {"$gt": ["$price_monthly", 0]},
                                            "$price_monthly",
                                            {"$divide": ["$price_yearly", 12]},
                                        ]
                                    },
                                },
                            ],
                            "default": {
                                "$cond": [
                                    {"$gt": ["$price_monthly", 0]},
                                    "$price_monthly",
                                    {"$divide": ["$price_yearly", 12]},
                                ]
                            },
                        }
                    },
                    "annual_revenue": {
                        "$cond": [
                            {"$gt": ["$price_yearly", 0]},
                            "$price_yearly",
                            {"$multiply": ["$price_monthly", 12]},
                        ]
                    },
                }
            },
            {
                "$group": {
                    "_id": "$plan_id",
                    "plan_name": {"$first": "$plan_name"},
                    "monthly": {"$sum": "$monthly_revenue"},
                    "annual": {"$sum": "$annual_revenue"},
                }
            },
        ]

        try:
            revenue_docs = await self._aggregate(subscriptions_collection, pipeline)
        except Exception as exc:  # pragma: no cover - mongomock fallback path
            logger.debug("Revenue pipeline fallback engaged: %s", exc)
            return await self._revenue_fallback(
                subscriptions_collection, plans_collection
            )

        monthly_total = 0.0
        annual_total = 0.0
        plan_breakdown: Dict[str, Dict[str, Any]] = {}

        for doc in revenue_docs:
            plan_id = doc.get("_id")
            plan_name = doc.get("plan_name") or "Unassigned"
            monthly = float(doc.get("monthly", 0))
            annual = float(doc.get("annual", 0))

            if plan_id is None:
                logger.warning(
                    "Subscription with missing plan_id found during revenue calculation; "
                    "monthly=%.2f, annual=%.2f",
                    monthly,
                    annual,
                )
            key = str(plan_id) if plan_id is not None else "unknown"
            plan_breakdown[key] = {
                "name": plan_name,
                "monthly_revenue": monthly,
                "annual_revenue": annual,
            }

            monthly_total += monthly
            annual_total += annual

        return {"monthly": monthly_total, "annual": annual_total, "plans": plan_breakdown}

    async def _revenue_fallback(
        self, subscriptions_collection: Any, plans_collection: Any
    ) -> Dict[str, Any]:
        plans_lookup: Dict[Any, Mapping[str, Any]] = {}
        async for plan in self._iterate_documents(
            plans_collection,
            {},
            {"price_monthly": 1, "price_yearly": 1, "name": 1},
        ):
            plans_lookup[plan.get("_id")] = plan

        monthly_total = 0.0
        annual_total = 0.0
        plan_breakdown: Dict[str, Dict[str, Any]] = {}

        async for subscription in self._iterate_documents(
            subscriptions_collection,
            {"status": {"$in": ["active", "trial"]}},
            {"plan_id": 1, "billing_interval": 1},
        ):
            plan = plans_lookup.get(subscription.get("plan_id"), {})
            plan_id = subscription.get("plan_id")
            plan_name = plan.get("name", "Unassigned")
            price_monthly = float(plan.get("price_monthly") or 0)
            price_yearly = float(plan.get("price_yearly") or 0)
            interval = subscription.get("billing_interval")

            monthly_value = self._calculate_monthly_value(
                price_monthly, price_yearly, interval
            )
            annual_value = price_yearly if price_yearly else monthly_value * 12

            if plan_id is None:
                logger.warning(
                    "Subscription with missing plan_id found in revenue fallback; "
                    "monthly=%.2f, annual=%.2f",
                    monthly_value,
                    annual_value,
                )
            key = str(plan_id) if plan_id is not None else "unknown"
            plan_entry = plan_breakdown.setdefault(
                key,
                {"name": plan_name, "monthly_revenue": 0.0, "annual_revenue": 0.0},
            )

            plan_entry["monthly_revenue"] += monthly_value
            plan_entry["annual_revenue"] += annual_value

            monthly_total += monthly_value
            annual_total += annual_value

        return {"monthly": monthly_total, "annual": annual_total, "plans": plan_breakdown}

    async def _iterate_documents(
        self,
        collection: Any,
        filter_query: Mapping[str, Any],
        projection: Optional[Mapping[str, int]] = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        cursor = collection.find(filter_query, projection)

        if hasattr(cursor, "__aiter__"):
            async for document in cursor:
                yield document
            return

        def sync_iter() -> List[Mapping[str, Any]]:
            return list(cursor)

        for document in await asyncio.to_thread(sync_iter):
            yield document

    async def _aggregate(
        self, collection: Any, pipeline: Sequence[Mapping[str, Any]]
    ) -> List[Mapping[str, Any]]:
        cursor = collection.aggregate(pipeline)

        if hasattr(cursor, "__aiter__"):
            return [document async for document in cursor]

        def sync_aggregate() -> List[Mapping[str, Any]]:
            return list(cursor)

        return await asyncio.to_thread(sync_aggregate)

    async def _safe_aggregate(
        self, collection: Any, pipeline: Sequence[Mapping[str, Any]]
    ) -> List[Mapping[str, Any]]:
        try:
            return await self._aggregate(collection, pipeline)
        except Exception as exc:  # pragma: no cover - mongomock fallback path
            logger.debug("Aggregate pipeline failed: %s", exc)
            return []

    async def _call_collection_method(
        self, collection: Any, method_name: str, *args: Any, **kwargs: Any
    ) -> Any:
        method = getattr(collection, method_name)

        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)

        if AsyncIOMotorCollection is not None and isinstance(
            collection, AsyncIOMotorCollection
        ):
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        def sync_call() -> Any:
            return method(*args, **kwargs)

        result = await asyncio.to_thread(sync_call)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _find_one(
        self,
        collection: Any,
        filter_query: Mapping[str, Any],
        *,
        sort: Optional[Sequence[Tuple[str, int]]] = None,
    ) -> Optional[Mapping[str, Any]]:
        if sort is None:
            return await self._call_collection_method(
                collection, "find_one", filter_query
            )
        return await self._call_collection_method(
            collection, "find_one", filter_query, sort=list(sort)
        )

    async def _collect_cursor(self, cursor: Any) -> List[Mapping[str, Any]]:
        if hasattr(cursor, "__aiter__"):
            return [document async for document in cursor]

        def sync_collect() -> List[Mapping[str, Any]]:
            return list(cursor)

        return await asyncio.to_thread(sync_collect)

    async def _count_documents(
        self, collection: Any, filter_query: Mapping[str, Any]
    ) -> int:
        result = await self._call_collection_method(
            collection, "count_documents", filter_query
        )
        return int(result)

    def _prepare_snapshot_document(
        self, document: Mapping[str, Any]
    ) -> Dict[str, Any]:
        prepared = dict(document)
        identifier = prepared.get("_id")
        if identifier is not None:
            prepared["id"] = str(identifier)
        return prepared

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            normalized = value.strip()
            try:
                iso_normalized = normalized.replace("Z", "+00:00")
                return datetime.fromisoformat(iso_normalized)
            except ValueError:
                try:
                    return datetime.strptime(normalized, "%Y-%m-%d")
                except ValueError:
                    return None
        return None

    @staticmethod
    def _normalize_to_utc(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @staticmethod
    def _calculate_monthly_value(
        monthly_price: float, yearly_price: float, interval: Optional[str]
    ) -> float:
        interval_normalized = (interval or "").lower()
        if interval_normalized == "yearly":
            return yearly_price / 12 if yearly_price else monthly_price
        if interval_normalized == "monthly":
            return monthly_price if monthly_price else yearly_price / 12
        return monthly_price if monthly_price else yearly_price / 12

    @staticmethod
    def _resolve_timeframe(timeframe: str) -> int:
        normalized = timeframe.lower()
        mapping = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
        if normalized not in mapping:
            raise ValueError(
                "Invalid timeframe. Use one of: 7d, 30d, 90d, 1y."
            )
        return mapping[normalized]


service = PlatformMetricsService(mongo)
