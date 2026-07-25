"""Fail-closed root-admin resolutions for storefront domain review states.

This service intentionally exposes three bounded decisions rather than a
generic phase override. Every mutation is fenced to the exact owner,
hostname, attempt, and revision that the operator reviewed, and every outcome
has an append-only operation receipt.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.constants.storefront_domain import (
    CERTIFICATE_VALIDATION,
    CUTOVER_READY,
    DISCONNECTED,
    HOSTNAME_VALIDATION,
    MIGRATION_PREVALIDATION,
    OPERATOR_REVIEW,
    PROVIDER_CREATE_REQUEST_WINDOW_SECONDS,
)
from app.core.database import mongo
from app.core.settings import settings
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError
from app.services.storefront_domain_service import (
    normalize_custom_hostname,
)
from app.utils.planner_ownership import normalize_planner_id

_RECEIPT_TTL = timedelta(days=90)
_REVIEW_REFERENCE_TTL = timedelta(minutes=15)
_SAFE_PROVIDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")
_SAFE_REVIEW_ID = re.compile(r"^sfor_[A-Za-z0-9_-]{8,220}_[a-f0-9]{36}$")
_REVIEW_KINDS = {"domain", "conflict"}


class StorefrontDomainOperatorService:
    """Resolve only the three domain states that require human judgment."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        cloudflare_service: CloudflareService | None = None,
        review_signing_key: str | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._cloudflare = cloudflare_service or CloudflareService()
        self._review_signing_key = (
            settings.secret_key if review_signing_key is None else review_signing_key
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _review_key(self) -> bytes:
        if (
            not isinstance(self._review_signing_key, str)
            or len(self._review_signing_key) < 32
        ):
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "operator_review_signing_unavailable",
                "The storefront-domain review queue is temporarily unavailable.",
                "Restore the server signing configuration before reviewing domains.",
                retryable=True,
            )
        return hmac.new(
            self._review_signing_key.encode("utf-8"),
            b"storefront-domain-operator-review-v1",
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}")

    @classmethod
    def _review_attempt_id(cls, kind: str, record: dict[str, Any]) -> str | None:
        if kind == "conflict":
            value = record.get("attempt_id")
        elif cls._domain_review_type(record) == "ambiguous_create":
            value = record.get("provider_create_attempt_id")
        else:
            value = record.get("claim_attempt_id")
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _attempt_fingerprint(attempt_id: str) -> str:
        return hashlib.sha256(attempt_id.encode("utf-8")).hexdigest()[:24]

    def _review_id(self, kind: str, record: dict[str, Any]) -> str:
        if kind not in _REVIEW_KINDS:
            raise ValueError("Unsupported storefront-domain review kind")
        record_id = record.get("_id")
        attempt_id = self._review_attempt_id(kind, record)
        revision = record.get("revision")
        if (
            not ObjectId.is_valid(record_id)
            or not attempt_id
            or isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 0
        ):
            raise ValueError("Invalid storefront-domain review target")
        expires_at = int((self._now() + _REVIEW_REFERENCE_TTL).timestamp())
        payload = self._b64encode(
            json.dumps(
                [
                    kind,
                    str(record_id),
                    self._attempt_fingerprint(attempt_id),
                    revision,
                    expires_at,
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        )
        signature = hmac.new(
            self._review_key(), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()[:36]
        return f"sfor_{payload}_{signature}"

    def _decode_review_id(
        self, review_id: str
    ) -> tuple[str, ObjectId, str, int, datetime]:
        if not isinstance(review_id, str) or not _SAFE_REVIEW_ID.fullmatch(review_id):
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "operator_review_not_found",
                "The storefront-domain review could not be found.",
                "Reload the operator review queue.",
            )
        encoded = review_id.removeprefix("sfor_")
        try:
            payload, supplied_signature = encoded.rsplit("_", 1)
            expected_signature = hmac.new(
                self._review_key(),
                payload.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()[:36]
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("invalid signature")
            decoded = json.loads(self._b64decode(payload))
            if (
                not isinstance(decoded, list)
                or len(decoded) != 5
                or decoded[0] not in _REVIEW_KINDS
                or not ObjectId.is_valid(decoded[1])
                or not isinstance(decoded[2], str)
                or not re.fullmatch(r"[a-f0-9]{24}", decoded[2])
                or isinstance(decoded[3], bool)
                or not isinstance(decoded[3], int)
                or decoded[3] < 0
                or isinstance(decoded[4], bool)
                or not isinstance(decoded[4], int)
            ):
                raise ValueError("invalid payload")
            expires_at = datetime.fromtimestamp(decoded[4], tz=UTC)
            if expires_at <= self._now():
                raise self._error(
                    status.HTTP_409_CONFLICT,
                    "operator_review_reference_expired",
                    "The storefront-domain review reference has expired.",
                    "Reload the operator review queue before taking action.",
                    retryable=True,
                )
            return (
                str(decoded[0]),
                ObjectId(str(decoded[1])),
                decoded[2],
                decoded[3],
                expires_at,
            )
        except HTTPException:
            raise
        except (binascii.Error, TypeError, ValueError, json.JSONDecodeError):
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "operator_review_not_found",
                "The storefront-domain review could not be found.",
                "Reload the operator review queue.",
            ) from None

    @staticmethod
    async def _recent_rows(
        collection: Any, query: dict[str, Any], limit: int
    ) -> list[dict]:
        cursor = collection.find(query).sort("updated_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    def _last_error(record: dict[str, Any]) -> dict[str, Any]:
        value = record.get("last_error")
        return value if isinstance(value, dict) else {}

    @classmethod
    def _domain_review_type(cls, record: dict[str, Any]) -> str:
        last_error = cls._last_error(record)
        if (
            record.get("ownership_status") == "verified"
            and record.get("intent") == "migration"
            and isinstance(record.get("authoritative_dns"), dict)
            and record["authoritative_dns"].get("provider") == "cloudflare"
            and last_error.get("code") == "cloudflare_o2o_migration_requires_assistance"
        ):
            return "o2o_cutover"
        if record.get("provider_reconciliation_required") is True:
            return "ambiguous_create"
        return "investigation"

    @staticmethod
    def _allowed_actions(review_type: str) -> list[str]:
        if review_type == "o2o_cutover":
            return ["approve_o2o_cutover"]
        if review_type == "ambiguous_create":
            return ["adopt_ambiguous_create"]
        if review_type == "hostname_conflict":
            return ["deny_hostname_conflict", "cancel_hostname_conflict"]
        return []

    @staticmethod
    def _safe_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return None

    @classmethod
    def _valid_provider_request_window(
        cls,
        started_at: object,
        ends_at: object,
        outcome_unknown_at: object | None = None,
    ) -> bool:
        started = cls._safe_datetime(started_at)
        ended = cls._safe_datetime(ends_at)
        unknown = cls._safe_datetime(outcome_unknown_at)
        if not started or not ended or ended < started:
            return False
        if ended - started > timedelta(seconds=PROVIDER_CREATE_REQUEST_WINDOW_SECONDS):
            return False
        return unknown is None or started <= unknown <= ended

    @classmethod
    def _provider_row_created_in_request_window(
        cls,
        row: dict[str, Any],
        *,
        started_at: object,
        ends_at: object,
    ) -> bool:
        started = cls._safe_datetime(started_at)
        ended = cls._safe_datetime(ends_at)
        raw_created = row.get("created_at")
        if isinstance(raw_created, str):
            try:
                created = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
            except ValueError:
                return False
            created = cls._safe_datetime(created)
        else:
            created = cls._safe_datetime(raw_created)
        if not started or not ended or not created:
            return False
        return started - timedelta(minutes=1) <= created <= ended

    def _summary(
        self,
        kind: str,
        record: dict[str, Any],
        *,
        review_id: str | None = None,
    ) -> dict[str, Any]:
        attempt_id = self._review_attempt_id(kind, record)
        revision = record.get("revision")
        hostname = record.get("hostname")
        if (
            not ObjectId.is_valid(record.get("_id"))
            or not attempt_id
            or not isinstance(hostname, str)
            or not hostname.strip()
            or isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 0
        ):
            raise ValueError("Invalid storefront-domain review queue row")
        review_type = (
            "hostname_conflict"
            if kind == "conflict"
            else self._domain_review_type(record)
        )
        last_error = self._last_error(record)
        support_id = last_error.get("support_id")
        return {
            "review_id": review_id or self._review_id(kind, record),
            "review_type": review_type,
            "hostname": hostname,
            "application_status": str(
                record.get("application_status") or OPERATOR_REVIEW
            ),
            "action": str(record.get("action") or "operator_review"),
            "revision": revision,
            "updated_at": self._safe_datetime(
                record.get("updated_at") or record.get("created_at")
            ),
            "support_id": (
                support_id
                if isinstance(support_id, str) and support_id.strip()
                else None
            ),
            "allowed_actions": self._allowed_actions(review_type),
        }

    async def list_reviews(
        self,
        actor: Any,
        *,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a bounded root-only queue; targets resolve through signed IDs."""

        self._actor_id(actor)
        bounded_limit = max(1, min(int(limit), 100))
        fetch_limit = bounded_limit + 1
        domains = await self._recent_rows(
            self._mongo.db["storefront_domains"],
            {"application_status": OPERATOR_REVIEW, "deletion_status": None},
            fetch_limit,
        )
        conflicts = await self._recent_rows(
            self._mongo.db["storefront_domain_conflict_claims"],
            {"application_status": OPERATOR_REVIEW},
            fetch_limit,
        )
        combined: list[dict[str, Any]] = []
        for kind, rows in (("domain", domains), ("conflict", conflicts)):
            for record in rows:
                try:
                    combined.append(self._summary(kind, record))
                except (TypeError, ValueError):
                    # A malformed lifecycle row must not hide healthy reviews. It
                    # remains in Mongo for operator/engineering repair, but it is
                    # not serialized into an unsafe or un-actionable queue item.
                    continue
        combined.sort(
            key=lambda item: item.get("updated_at") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return {
            "items": combined[:bounded_limit],
            "has_more": len(combined) > bounded_limit,
        }

    async def _ambiguous_candidates(
        self,
        record: dict[str, Any],
        create_operation: dict[str, Any] | None,
    ) -> tuple[list[str], dict[str, str | None]]:
        if not create_operation:
            return [], {
                "status": "invalid",
                "message": "The original provider-create receipt is unavailable or incomplete.",
                "support_id": self._error_detail(
                    "provider_create_receipt_missing",
                    "The original provider-create receipt is unavailable or incomplete.",
                    "Keep this domain in operator review for engineering investigation.",
                )["support_id"],
            }
        request_started_at = create_operation.get("provider_request_started_at")
        request_window_ends_at = create_operation.get("provider_request_window_ends_at")
        provider_outcome_unknown_at = create_operation.get(
            "provider_outcome_unknown_at"
        )
        if not self._valid_provider_request_window(
            request_started_at,
            request_window_ends_at,
            provider_outcome_unknown_at,
        ) or not self._safe_datetime(provider_outcome_unknown_at):
            return [], {
                "status": "invalid",
                "message": "The provider-create request window is missing or invalid.",
                "support_id": self._error_detail(
                    "provider_create_window_invalid",
                    "The provider-create request window is missing or invalid.",
                    "Keep this domain in operator review for engineering investigation.",
                )["support_id"],
            }
        try:
            rows = await self._cloudflare.list_custom_hostnames(record["hostname"])
        except CloudflareServiceError:
            evidence = self._error_detail(
                "provider_identity_lookup_unavailable",
                "Cloudflare could not be reached for independent identity evidence.",
                "Keep this domain in operator review and retry after Cloudflare is available.",
                retryable=True,
            )
            return [], {
                "status": "unavailable",
                "message": evidence["message"],
                "support_id": evidence["support_id"],
            }
        before = set(create_operation.get("provider_ids_before") or [])
        candidates: list[str] = []
        for row in rows:
            provider_id = row.get("id") if isinstance(row, dict) else None
            if (
                not isinstance(provider_id, str)
                or provider_id in before
                or not self._provider_row_created_in_request_window(
                    row,
                    started_at=request_started_at,
                    ends_at=request_window_ends_at,
                )
            ):
                continue
            try:
                listed_hostname = normalize_custom_hostname(
                    row.get("hostname"), platform_domains=()
                )
            except (TypeError, ValueError):
                continue
            if listed_hostname == record.get("hostname"):
                candidates.append(provider_id)
        return sorted(set(candidates)), {
            "status": "available",
            "message": "Cloudflare identity evidence was refreshed successfully.",
            "support_id": None,
        }

    async def get_review(
        self,
        actor: Any,
        *,
        review_id: str,
    ) -> dict[str, Any]:
        """Resolve one exact root-only review from an opaque signed reference."""

        self._actor_id(actor)
        (
            kind,
            record_id,
            reviewed_attempt_fingerprint,
            reviewed_revision,
            _expires_at,
        ) = self._decode_review_id(review_id)
        collection_name = (
            "storefront_domains"
            if kind == "domain"
            else "storefront_domain_conflict_claims"
        )
        record = await self._mongo.db[collection_name].find_one(
            {"_id": record_id, "application_status": OPERATOR_REVIEW}
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "operator_review_not_found",
                "The storefront-domain review is no longer pending.",
                "Reload the operator review queue.",
            )
        current_attempt_id = self._review_attempt_id(kind, record)
        if (
            not current_attempt_id
            or self._attempt_fingerprint(current_attempt_id)
            != reviewed_attempt_fingerprint
            or record.get("revision") != reviewed_revision
        ):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_review_reference_stale",
                "The storefront-domain review changed after the queue was loaded.",
                "Reload the operator review queue and inspect the current attempt and revision.",
                retryable=True,
            )
        summary = self._summary(kind, record, review_id=review_id)
        owner_id = (
            record.get("planner_id")
            if kind == "domain"
            else record.get("claimant_planner_id")
        )
        review_type = summary["review_type"]
        attempt_id = (
            record.get("provider_create_attempt_id")
            if review_type == "ambiguous_create"
            else record.get("claim_attempt_id")
            if kind == "domain"
            else record.get("attempt_id")
        )
        if not isinstance(owner_id, str) or not isinstance(attempt_id, str):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_review_target_invalid",
                "The review target is incomplete and cannot be changed safely.",
                "Escalate this review for engineering investigation.",
            )
        authority = record.get("authoritative_dns")
        authority = authority if isinstance(authority, dict) else {}
        last_error = self._last_error(record)
        create_operation = None
        provider_candidates: list[str] = []
        provider_lookup = {
            "status": "not_required",
            "message": None,
            "support_id": None,
        }
        if review_type == "ambiguous_create":
            create_operation = await self._mongo.db[
                "storefront_domain_operations"
            ].find_one(
                {
                    "operation_id": attempt_id,
                    "domain_id": str(record["_id"]),
                    "planner_id": owner_id,
                    "kind": "provider_create",
                    "state": {"$in": ["operator_review", "adoption_committing"]},
                }
            )
            provider_candidates, provider_lookup = await self._ambiguous_candidates(
                record, create_operation
            )
        return {
            **summary,
            "planner_id": owner_id,
            "attempt_id": attempt_id,
            "intent": record.get("intent"),
            "ownership_status": record.get("ownership_status"),
            "routing_dns_status": record.get("routing_dns_status"),
            "provider_hostname_status": record.get("provider_hostname_status"),
            "ssl_status": record.get("ssl_status"),
            "https_status": record.get("https_status"),
            "authoritative_dns_provider": authority.get("provider"),
            "authoritative_nameservers": [
                value
                for value in authority.get("nameservers", [])
                if isinstance(value, str)
            ],
            "provider_candidate_ids": provider_candidates,
            "provider_lookup_status": provider_lookup["status"],
            "provider_lookup_message": provider_lookup["message"],
            "provider_lookup_support_id": provider_lookup["support_id"],
            "error_code": last_error.get("code"),
            "error_message": last_error.get("message"),
            "customer_action": last_error.get("customer_action"),
        }

    @staticmethod
    def _error_detail(
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool = False,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "message": message,
            "customer_action": customer_action,
            "retryable": retryable,
            "support_id": f"sfd_{uuid4().hex[:16]}",
        }

    @classmethod
    def _error(
        cls,
        status_code: int,
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool = False,
    ) -> HTTPException:
        return HTTPException(
            status_code=status_code,
            detail=cls._error_detail(
                code,
                message,
                customer_action,
                retryable=retryable,
            ),
        )

    @classmethod
    def _actor_id(cls, actor: Any) -> str:
        if not getattr(actor, "is_root_admin", False):
            raise cls._error(
                status.HTTP_403_FORBIDDEN,
                "root_admin_required",
                "Root-admin access is required for this domain decision.",
                "Sign in with the configured root-admin account.",
            )
        email = getattr(actor, "email", None)
        if not isinstance(email, str) or not email.strip():
            raise cls._error(
                status.HTTP_403_FORBIDDEN,
                "root_admin_identity_missing",
                "The root-admin identity could not be recorded safely.",
                "Sign in again before resolving this domain.",
            )
        return email.strip().lower()

    @classmethod
    def _target(cls, planner_id: str, hostname: str) -> tuple[str, str]:
        owner_id = normalize_planner_id(planner_id)
        if not owner_id:
            raise cls._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_storefront_owner",
                "The storefront owner identifier is invalid.",
                "Reload the operator review record and try again.",
            )
        try:
            normalized_hostname = normalize_custom_hostname(
                hostname,
                platform_domains=(),
            )
        except ValueError as exc:
            raise cls._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_custom_domain",
                str(exc),
                "Reload the operator review record and use its exact hostname.",
            ) from exc
        return owner_id, normalized_hostname

    @staticmethod
    def _decision_operation_id(
        *,
        kind: str,
        domain_id: str,
        planner_id: str,
        hostname: str,
        reviewed_attempt_id: str,
        reviewed_revision: int,
        decision: str,
        provider_hostname_id: str | None = None,
    ) -> str:
        identity = json.dumps(
            [
                kind,
                domain_id,
                planner_id,
                hostname,
                reviewed_attempt_id,
                reviewed_revision,
                decision,
                provider_hostname_id,
            ],
            separators=(",", ":"),
        )
        return f"sforop_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:40]}"

    async def _find_decision_receipt(
        self,
        *,
        kind: str,
        domain_id: str,
        planner_id: str,
        hostname: str,
        reviewed_attempt_id: str,
        reviewed_revision: int,
        decision: str,
        provider_hostname_id: str | None = None,
    ) -> dict[str, Any] | None:
        operation_id = self._decision_operation_id(
            kind=kind,
            domain_id=domain_id,
            planner_id=planner_id,
            hostname=hostname,
            reviewed_attempt_id=reviewed_attempt_id,
            reviewed_revision=reviewed_revision,
            decision=decision,
            provider_hostname_id=provider_hostname_id,
        )
        return await self._mongo.db["storefront_domain_operations"].find_one(
            {"operation_id": operation_id}
        )

    async def _insert_receipt(
        self,
        *,
        kind: str,
        domain_id: str,
        planner_id: str,
        hostname: str,
        reviewed_attempt_id: str,
        reviewed_revision: int,
        actor_id: str,
        decision: str,
        reason: str,
        provider_hostname_id: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        operation_id = self._decision_operation_id(
            kind=kind,
            domain_id=domain_id,
            planner_id=planner_id,
            hostname=hostname,
            reviewed_attempt_id=reviewed_attempt_id,
            reviewed_revision=reviewed_revision,
            decision=decision,
            provider_hostname_id=provider_hostname_id,
        )
        receipt = {
            "operation_id": operation_id,
            "domain_id": domain_id,
            # Operator actions may be repeated only after another reviewed
            # revision. Keep their receipt identity independent from the
            # customer claim attempt while retaining that attempt explicitly.
            "attempt_id": operation_id,
            "reviewed_attempt_id": reviewed_attempt_id,
            "reviewed_revision": reviewed_revision,
            "kind": kind,
            "planner_id": planner_id,
            "hostname": hostname,
            "actor_id": actor_id,
            "decision": decision,
            "reason": reason.strip(),
            "state": "prepared",
            "created_at": now,
            "updated_at": now,
            "expires_at": now + _RECEIPT_TTL,
        }
        if provider_hostname_id:
            receipt["requested_provider_hostname_id"] = provider_hostname_id
        operations = self._mongo.db["storefront_domain_operations"]
        try:
            await operations.insert_one(receipt)
            return receipt
        except DuplicateKeyError:
            existing = await operations.find_one({"operation_id": operation_id})
            exact_fields = (
                "domain_id",
                "reviewed_attempt_id",
                "reviewed_revision",
                "kind",
                "planner_id",
                "hostname",
                "decision",
            )
            if not existing or any(
                existing.get(field) != receipt.get(field) for field in exact_fields
            ):
                raise self._error(
                    status.HTTP_409_CONFLICT,
                    "operator_receipt_conflict",
                    "The operator decision receipt could not be reserved safely.",
                    "Reload the review before taking any action.",
                ) from None
            if existing.get("requested_provider_hostname_id") != receipt.get(
                "requested_provider_hostname_id"
            ):
                raise self._error(
                    status.HTTP_409_CONFLICT,
                    "operator_receipt_conflict",
                    "The operator decision receipt targets different provider evidence.",
                    "Reload the review before taking any action.",
                ) from None
            return existing

    async def _finish_receipt(
        self,
        receipt: dict[str, Any],
        *,
        state: str,
        error: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "state": state,
            "updated_at": self._now(),
        }
        if error is not None:
            fields["last_error"] = error
        if extra:
            fields.update(extra)
        mutation: dict[str, Any] = {"$set": fields}
        if state == "completed" and error is None:
            mutation["$unset"] = {"last_error": ""}
        operations = self._mongo.db["storefront_domain_operations"]
        updated = await operations.update_one(
            {
                "operation_id": receipt["operation_id"],
                "state": {
                    "$in": [
                        "prepared",
                        "decision_applied",
                        "provider_operation_reconciliation",
                    ]
                },
            },
            mutation,
        )
        if getattr(updated, "matched_count", 0):
            receipt.update(fields)
            return
        current = await operations.find_one({"operation_id": receipt["operation_id"]})
        if current and current.get("state") == state:
            receipt.update(current)
            return
        raise self._error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "operator_receipt_write_failed",
            "The storefront-domain decision receipt could not be finalized.",
            "Retry the same decision so the recorded state can be reconciled.",
            retryable=True,
        )

    @staticmethod
    def _response(
        receipt: dict[str, Any],
        *,
        before_revision: int,
        application_status: str,
        provider_hostname_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "operation_id": receipt["operation_id"],
            "decision": receipt["decision"],
            "planner_id": receipt["planner_id"],
            "hostname": receipt["hostname"],
            "attempt_id": receipt["reviewed_attempt_id"],
            "before_revision": before_revision,
            "after_revision": int(receipt.get("after_revision") or before_revision + 1),
            "application_status": application_status,
            "provider_hostname_id": provider_hostname_id,
            "completed_at": receipt.get("completed_at") or datetime.now(UTC),
        }

    async def approve_o2o_cutover(
        self,
        actor: Any,
        *,
        planner_id: str,
        hostname: str,
        attempt_id: str,
        revision: int,
        reason: str,
    ) -> dict[str, Any]:
        """Approve one provider attempt; do not write customer DNS or Cloudflare."""

        actor_id = self._actor_id(actor)
        owner_id, normalized_hostname = self._target(planner_id, hostname)
        domains = self._mongo.db["storefront_domains"]
        record = await domains.find_one(
            {
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "claim_attempt_id": attempt_id,
            }
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "operator_review_not_found",
                "The exact storefront domain review could not be found.",
                "Reload the operator review queue before taking action.",
            )
        receipt_identity = {
            "kind": "operator_o2o_cutover_approval",
            "domain_id": str(record["_id"]),
            "planner_id": owner_id,
            "hostname": normalized_hostname,
            "reviewed_attempt_id": attempt_id,
            "reviewed_revision": revision,
            "decision": "approved",
        }
        expected_operation_id = self._decision_operation_id(**receipt_identity)
        approval_marker = record.get("operator_assisted_cutover_approval")
        if (
            record.get("revision") == revision + 1
            and isinstance(approval_marker, dict)
            and approval_marker.get("approval_id") == expected_operation_id
            and record.get("application_status") == MIGRATION_PREVALIDATION
        ):
            existing_receipt = await self._find_decision_receipt(**receipt_identity)
            if not existing_receipt:
                raise self._error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "operator_receipt_reconciliation_required",
                    "The cutover decision was applied but its receipt is unavailable.",
                    "Retry after the storefront-domain receipt store is repaired.",
                    retryable=True,
                )
            completed_at = existing_receipt.get("completed_at") or self._now()
            await self._finish_receipt(
                existing_receipt,
                state="completed",
                extra={
                    "completed_at": completed_at,
                    "after_revision": revision + 1,
                },
            )
            return self._response(
                existing_receipt,
                before_revision=revision,
                application_status=MIGRATION_PREVALIDATION,
            )
        if record.get("revision") != revision:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_review_revision_changed",
                "The storefront domain review changed after it was loaded.",
                "Reload the review and confirm the new revision.",
                retryable=True,
            )
        authority = record.get("authoritative_dns")
        last_error = record.get("last_error")
        assisted_o2o = bool(
            record.get("application_status") == OPERATOR_REVIEW
            and record.get("ownership_status") == "verified"
            and record.get("intent") == "migration"
            and isinstance(authority, dict)
            and authority.get("provider") == "cloudflare"
            and record.get("provider_hostname_id") is None
            and not record.get("deletion_status")
            and isinstance(last_error, dict)
            and last_error.get("code") == "cloudflare_o2o_migration_requires_assistance"
        )
        if not assisted_o2o:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "o2o_cutover_not_approvable",
                "This review is not an ownership-verified assisted O2O cutover.",
                "Reload the review and use only the decision offered for its state.",
            )

        receipt = await self._insert_receipt(
            **receipt_identity,
            actor_id=actor_id,
            reason=reason,
        )
        if receipt.get("state") not in {"prepared", "decision_applied"}:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_receipt_not_resumable",
                "This exact cutover decision already has a terminal receipt.",
                "Reload the operator review queue before taking action.",
            )
        decision_actor_id = (
            receipt.get("actor_id")
            if isinstance(receipt.get("actor_id"), str)
            else actor_id
        )
        now = self._now()
        approval = {
            "approval_id": receipt["operation_id"],
            "claim_attempt_id": attempt_id,
            "approved_revision": revision + 1,
            "approved_at": now,
            "approved_by": decision_actor_id,
            "consumed_at": None,
        }
        updated = await domains.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "claim_attempt_id": attempt_id,
                "revision": revision,
                "application_status": OPERATOR_REVIEW,
                "ownership_status": "verified",
                "provider_hostname_id": None,
                "deletion_status": None,
            },
            {
                "$set": {
                    "operator_assisted_cutover_approval": approval,
                    "application_status": MIGRATION_PREVALIDATION,
                    "action": "action_required",
                    "last_error": None,
                    "updated_at": now,
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(updated, "matched_count", 0):
            error = self._error_detail(
                "operator_review_changed",
                "The domain review changed while approval was recorded.",
                "Reload the operator review before trying again.",
                retryable=True,
            )
            await self._finish_receipt(receipt, state="cancelled", error=error)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
        completed_at = self._now()
        receipt["completed_at"] = completed_at
        await self._finish_receipt(
            receipt,
            state="completed",
            extra={"completed_at": completed_at, "after_revision": revision + 1},
        )
        return self._response(
            receipt,
            before_revision=revision,
            application_status=MIGRATION_PREVALIDATION,
        )

    async def resolve_conflict_claim(
        self,
        actor: Any,
        *,
        planner_id: str,
        hostname: str,
        attempt_id: str,
        revision: int,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        """Deny or cancel a verified claim without touching its reserved domain."""

        actor_id = self._actor_id(actor)
        owner_id, normalized_hostname = self._target(planner_id, hostname)
        if decision not in {"denied", "cancelled"}:
            raise self._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_conflict_resolution",
                "Conflict reviews may only be denied or cancelled.",
                "Choose denied or cancelled and try again.",
            )
        claims = self._mongo.db["storefront_domain_conflict_claims"]
        record = await claims.find_one(
            {
                "claimant_planner_id": owner_id,
                "hostname": normalized_hostname,
                "attempt_id": attempt_id,
            }
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "conflict_review_not_found",
                "The exact hostname conflict review could not be found.",
                "Reload the operator review queue before taking action.",
            )
        receipt_identity = {
            "kind": f"operator_conflict_{decision}",
            "domain_id": f"conflict:{record['_id']}",
            "planner_id": owner_id,
            "hostname": normalized_hostname,
            "reviewed_attempt_id": attempt_id,
            "reviewed_revision": revision,
            "decision": decision,
        }
        expected_operation_id = self._decision_operation_id(**receipt_identity)
        resolution_marker = record.get("operator_resolution")
        if (
            record.get("revision") == revision + 1
            and isinstance(resolution_marker, dict)
            and resolution_marker.get("operation_id") == expected_operation_id
            and resolution_marker.get("decision") == decision
            and record.get("application_status") == DISCONNECTED
        ):
            existing_receipt = await self._find_decision_receipt(**receipt_identity)
            if not existing_receipt:
                raise self._error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "operator_receipt_reconciliation_required",
                    "The conflict decision was applied but its receipt is unavailable.",
                    "Retry after the storefront-domain receipt store is repaired.",
                    retryable=True,
                )
            completed_at = existing_receipt.get("completed_at") or self._now()
            await self._finish_receipt(
                existing_receipt,
                state="completed",
                extra={
                    "completed_at": completed_at,
                    "after_revision": revision + 1,
                },
            )
            return self._response(
                existing_receipt,
                before_revision=revision,
                application_status=DISCONNECTED,
            )
        if record.get("revision") != revision:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_review_revision_changed",
                "The hostname conflict review changed after it was loaded.",
                "Reload the review and confirm the new revision.",
                retryable=True,
            )
        if not (
            record.get("application_status") == OPERATOR_REVIEW
            and record.get("ownership_status") == "verified"
            and record.get("current_owner_key") == owner_id
        ):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "conflict_review_not_resolvable",
                "This claim is not an active, ownership-verified conflict review.",
                "Reload the review and use only the decision offered for its state.",
            )

        receipt = await self._insert_receipt(
            **receipt_identity,
            actor_id=actor_id,
            reason=reason,
        )
        if receipt.get("state") not in {"prepared", "decision_applied"}:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_receipt_not_resumable",
                "This exact conflict decision already has a terminal receipt.",
                "Reload the operator review queue before taking action.",
            )
        decision_actor_id = (
            receipt.get("actor_id")
            if isinstance(receipt.get("actor_id"), str)
            else actor_id
        )
        now = self._now()
        customer_message = (
            "The hostname ownership review was denied without changing the existing mapping."
            if decision == "denied"
            else "The hostname ownership review was cancelled without changing the existing mapping."
        )
        customer_error = self._error_detail(
            f"hostname_conflict_claim_{decision}",
            customer_message,
            "Remove the temporary ownership TXT record. The existing hostname mapping remains unchanged.",
        )
        updated = await claims.update_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
                "hostname": normalized_hostname,
                "attempt_id": attempt_id,
                "revision": revision,
                "application_status": OPERATOR_REVIEW,
                "ownership_status": "verified",
                "current_owner_key": owner_id,
            },
            {
                "$set": {
                    "status": decision,
                    "application_status": DISCONNECTED,
                    "ownership_status": decision,
                    "action": "remove_dns_records",
                    "operator_resolution": {
                        "operation_id": receipt["operation_id"],
                        "decision": decision,
                        "resolved_at": now,
                        "resolved_by": decision_actor_id,
                    },
                    "last_error": customer_error,
                    "updated_at": now,
                },
                "$unset": {"current_owner_key": "", "retry_due_at": ""},
                "$inc": {"revision": 1},
            },
        )
        if not getattr(updated, "matched_count", 0):
            error = self._error_detail(
                "operator_review_changed",
                "The conflict review changed while the decision was recorded.",
                "Reload the operator review before trying again.",
                retryable=True,
            )
            await self._finish_receipt(receipt, state="cancelled", error=error)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
        completed_at = self._now()
        receipt["completed_at"] = completed_at
        await self._finish_receipt(
            receipt,
            state="completed",
            extra={"completed_at": completed_at, "after_revision": revision + 1},
        )
        return self._response(
            receipt,
            before_revision=revision,
            application_status=DISCONNECTED,
        )

    @staticmethod
    def _status(value: object, fallback: str = "pending") -> str:
        return (
            value.strip().lower()
            if isinstance(value, str) and value.strip()
            else fallback
        )

    @staticmethod
    def _record_dict(value: object, fields: tuple[str, ...]) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        sanitized = {
            field: value[field]
            for field in fields
            if isinstance(value.get(field), str) and value[field].strip()
        }
        return sanitized or None

    @classmethod
    def _validation_records(cls, ssl: object) -> list[dict[str, Any]]:
        if not isinstance(ssl, dict) or not isinstance(
            ssl.get("validation_records"), list
        ):
            return []
        records: list[dict[str, Any]] = []
        for item in ssl["validation_records"][:10]:
            sanitized = cls._record_dict(
                item,
                (
                    "status",
                    "txt_name",
                    "txt_value",
                    "cname_name",
                    "cname_target",
                ),
            )
            if sanitized:
                records.append(sanitized)
        return records

    @staticmethod
    def _provider_messages(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        messages: list[str] = []
        for item in value[:10]:
            message = item.get("message") if isinstance(item, dict) else item
            if not isinstance(message, str):
                continue
            normalized = " ".join(message.split())[:500]
            if normalized and normalized not in messages:
                messages.append(normalized)
        return messages

    @classmethod
    def _provider_projection(cls, provider_row: dict[str, Any]) -> dict[str, Any]:
        ssl = provider_row.get("ssl")
        ssl_status = cls._status(ssl.get("status") if isinstance(ssl, dict) else None)
        provider_status = cls._status(provider_row.get("status"))
        return {
            "provider_status": provider_status,
            "provider_hostname_status": provider_status,
            "ssl_status": ssl_status,
            "status": (
                "active"
                if provider_status == "active" and ssl_status == "active"
                else "pending"
            ),
            "ownership_verification": cls._record_dict(
                provider_row.get("ownership_verification"),
                ("type", "name", "value"),
            ),
            "ownership_verification_http": cls._record_dict(
                provider_row.get("ownership_verification_http"),
                ("http_url", "http_body"),
            ),
            "ssl_validation_records": cls._validation_records(ssl),
            "provider_verification_errors": cls._provider_messages(
                provider_row.get("verification_errors")
            ),
            "ssl_validation_errors": cls._provider_messages(
                ssl.get("validation_errors") if isinstance(ssl, dict) else None
            ),
        }

    async def adopt_ambiguous_create(
        self,
        actor: Any,
        *,
        planner_id: str,
        hostname: str,
        attempt_id: str,
        revision: int,
        provider_hostname_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Adopt only an exact, independently listed post-snapshot provider ID."""

        actor_id = self._actor_id(actor)
        owner_id, normalized_hostname = self._target(planner_id, hostname)
        if not _SAFE_PROVIDER_ID.fullmatch(provider_hostname_id):
            raise self._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_provider_hostname_id",
                "The provider hostname identifier is invalid.",
                "Copy the exact identifier from the Cloudflare review record.",
            )
        domains = self._mongo.db["storefront_domains"]
        record = await domains.find_one(
            {
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "provider_create_attempt_id": attempt_id,
            }
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "ambiguous_create_review_not_found",
                "The exact ambiguous provider-create review could not be found.",
                "Reload the operator review queue before taking action.",
            )
        receipt_identity = {
            "kind": "operator_ambiguous_create_adoption",
            "domain_id": str(record["_id"]),
            "planner_id": owner_id,
            "hostname": normalized_hostname,
            "reviewed_attempt_id": attempt_id,
            "reviewed_revision": revision,
            "decision": "adopted",
            "provider_hostname_id": provider_hostname_id,
        }
        expected_operation_id = self._decision_operation_id(**receipt_identity)
        if (
            record.get("revision") == revision + 1
            and record.get("provider_hostname_id") == provider_hostname_id
            and record.get("provider_adopted_by_operation_id") == expected_operation_id
        ):
            existing_receipt = await self._find_decision_receipt(**receipt_identity)
            if not existing_receipt:
                raise self._error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "operator_receipt_reconciliation_required",
                    "The provider adoption was applied but its receipt is unavailable.",
                    "Retry after the storefront-domain receipt store is repaired.",
                    retryable=True,
                )
            operations = self._mongo.db["storefront_domain_operations"]
            source = await operations.find_one(
                {
                    "operation_id": attempt_id,
                    "domain_id": str(record["_id"]),
                    "planner_id": owner_id,
                    "hostname": normalized_hostname,
                    "kind": "provider_create",
                }
            )
            source_completed = bool(
                source
                and source.get("state") == "completed"
                and source.get("provider_hostname_id") == provider_hostname_id
                and source.get("adopted_by_operation_id") == expected_operation_id
            )
            if (
                not source_completed
                and source
                and source.get("state") == "adoption_committing"
                and source.get("adoption_operation_id") == expected_operation_id
            ):
                source_update = await operations.update_one(
                    {
                        "_id": source["_id"],
                        "operation_id": attempt_id,
                        "state": "adoption_committing",
                        "adoption_operation_id": expected_operation_id,
                    },
                    {
                        "$set": {
                            "state": "completed",
                            "provider_hostname_id": provider_hostname_id,
                            "adopted_by_operation_id": expected_operation_id,
                            "updated_at": self._now(),
                        },
                        "$unset": {"adoption_operation_id": ""},
                    },
                )
                source_completed = bool(getattr(source_update, "matched_count", 0))
            if not source_completed:
                await self._finish_receipt(
                    existing_receipt,
                    state="provider_operation_reconciliation",
                )
                raise self._error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "provider_operation_reconciliation_required",
                    "The provider adoption is awaiting receipt reconciliation.",
                    "Retry this exact decision after the original provider operation is available.",
                    retryable=True,
                )
            completed_at = existing_receipt.get("completed_at") or self._now()
            await self._finish_receipt(
                existing_receipt,
                state="completed",
                extra={
                    "completed_at": completed_at,
                    "after_revision": revision + 1,
                    "provider_hostname_id": provider_hostname_id,
                },
            )
            return self._response(
                existing_receipt,
                before_revision=revision,
                application_status=str(record.get("application_status")),
                provider_hostname_id=provider_hostname_id,
            )
        if record.get("revision") != revision:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_review_revision_changed",
                "The ambiguous provider-create review changed after it was loaded.",
                "Reload the review and confirm the new revision.",
                retryable=True,
            )
        create_operation = await self._mongo.db[
            "storefront_domain_operations"
        ].find_one(
            {
                "operation_id": attempt_id,
                "domain_id": str(record["_id"]),
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "kind": "provider_create",
                "state": {"$in": ["operator_review", "adoption_committing"]},
            }
        )
        provider_ids_before = record.get("provider_ids_before")
        operation_ids_before = (
            create_operation.get("provider_ids_before") if create_operation else None
        )
        valid_snapshot = bool(
            isinstance(provider_ids_before, list)
            and all(
                isinstance(item, str) and item.strip() for item in provider_ids_before
            )
            and isinstance(operation_ids_before, list)
            and all(
                isinstance(item, str) and item.strip() for item in operation_ids_before
            )
            and set(provider_ids_before) == set(operation_ids_before)
            and self._valid_provider_request_window(
                create_operation.get("provider_request_started_at")
                if create_operation
                else None,
                create_operation.get("provider_request_window_ends_at")
                if create_operation
                else None,
                create_operation.get("provider_outcome_unknown_at")
                if create_operation
                else None,
            )
            and self._safe_datetime(
                create_operation.get("provider_outcome_unknown_at")
                if create_operation
                else None
            )
            is not None
        )
        reviewable = bool(
            record.get("application_status") == OPERATOR_REVIEW
            and record.get("provider_reconciliation_required") is True
            and record.get("provider_hostname_id") is None
            and not record.get("deletion_status")
            and create_operation
            and valid_snapshot
            and (
                create_operation.get("state") == "operator_review"
                or create_operation.get("adoption_operation_id")
                == expected_operation_id
            )
        )
        if not reviewable:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "ambiguous_create_not_adoptable",
                "This record is not a safely reviewable ambiguous provider create.",
                "Keep it in operator review and investigate the provider operation receipt.",
            )
        if provider_hostname_id in set(provider_ids_before):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "provider_hostname_predates_attempt",
                "The selected provider hostname existed before this create attempt.",
                "Do not adopt it; keep the domain in operator review.",
            )

        receipt = await self._insert_receipt(
            **receipt_identity,
            actor_id=actor_id,
            reason=reason,
        )
        if receipt.get("state") not in {
            "prepared",
            "decision_applied",
            "provider_operation_reconciliation",
        }:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "operator_receipt_not_resumable",
                "This exact provider adoption already has a terminal receipt.",
                "Reload the operator review queue before taking action.",
            )
        try:
            provider_rows = await self._cloudflare.list_custom_hostnames(
                normalized_hostname
            )
        except CloudflareServiceError as exc:
            error = self._error_detail(
                "provider_identity_check_failed",
                "Cloudflare could not independently confirm the selected hostname.",
                "Keep this domain in operator review and retry after Cloudflare is available.",
                retryable=True,
            )
            await self._finish_receipt(receipt, state="prepared", error=error)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error
            ) from exc

        observed_at = self._now()
        candidates: list[dict[str, Any]] = []
        for row in provider_rows:
            if not isinstance(row, dict):
                continue
            candidate_id = row.get("id")
            if (
                not isinstance(candidate_id, str)
                or candidate_id in set(provider_ids_before)
                or not self._provider_row_created_in_request_window(
                    row,
                    started_at=create_operation.get("provider_request_started_at"),
                    ends_at=create_operation.get("provider_request_window_ends_at"),
                )
            ):
                continue
            try:
                listed_hostname = normalize_custom_hostname(
                    row.get("hostname"),
                    platform_domains=(),
                )
            except (TypeError, ValueError):
                continue
            if listed_hostname == normalized_hostname:
                candidates.append(row)
        if len(candidates) != 1 or candidates[0].get("id") != provider_hostname_id:
            error = self._error_detail(
                "provider_identity_ambiguous",
                "Cloudflare did not return exactly one new hostname created during this attempt.",
                "Do not adopt any hostname; keep the domain in operator review.",
            )
            await self._finish_receipt(receipt, state="denied", error=error)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

        provider_row = candidates[0]
        projection = self._provider_projection(provider_row)
        provider_receipt = {
            "provider": "cloudflare",
            "operation": "list_custom_hostnames",
            "provider_hostname_id": provider_hostname_id,
            "hostname": normalized_hostname,
            "provider_status": projection["provider_status"],
            "ssl_status": projection["ssl_status"],
            "observed_at": observed_at,
        }
        source_fingerprint = hashlib.sha256(
            json.dumps(
                [
                    attempt_id,
                    str(create_operation["_id"]),
                    create_operation.get("domain_id"),
                    create_operation.get("provider_ids_before"),
                    self._safe_datetime(
                        create_operation.get("provider_request_started_at")
                    ).isoformat(),
                    self._safe_datetime(
                        create_operation.get("provider_request_window_ends_at")
                    ).isoformat(),
                    self._safe_datetime(
                        create_operation.get("provider_outcome_unknown_at")
                    ).isoformat(),
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        await self._finish_receipt(
            receipt,
            state="prepared",
            extra={
                "provider_hostname_id": provider_hostname_id,
                "provider_receipt": provider_receipt,
                "source_operation_fingerprint": source_fingerprint,
            },
        )
        application_status = (
            CUTOVER_READY
            if record.get("intent") == "migration"
            and projection["provider_status"] == "active"
            and projection["ssl_status"] == "active"
            else (
                CERTIFICATE_VALIDATION
                if projection["provider_status"] == "active"
                else HOSTNAME_VALIDATION
            )
        )
        operations = self._mongo.db["storefront_domain_operations"]
        source_reserved = create_operation.get("state") == "adoption_committing"
        if not source_reserved:
            source_reservation = await operations.update_one(
                {
                    "_id": create_operation["_id"],
                    "operation_id": attempt_id,
                    "domain_id": str(record["_id"]),
                    "planner_id": owner_id,
                    "hostname": normalized_hostname,
                    "kind": "provider_create",
                    "state": "operator_review",
                    "provider_ids_before": operation_ids_before,
                    "provider_request_started_at": create_operation.get(
                        "provider_request_started_at"
                    ),
                    "provider_request_window_ends_at": create_operation.get(
                        "provider_request_window_ends_at"
                    ),
                    "provider_outcome_unknown_at": create_operation.get(
                        "provider_outcome_unknown_at"
                    ),
                },
                {
                    "$set": {
                        "state": "adoption_committing",
                        "adoption_operation_id": receipt["operation_id"],
                        "adoption_source_fingerprint": source_fingerprint,
                        "adoption_reserved_at": self._now(),
                        "updated_at": self._now(),
                    }
                },
            )
            source_reserved = bool(getattr(source_reservation, "matched_count", 0))
        if not source_reserved:
            error = self._error_detail(
                "provider_operation_changed",
                "The original provider-create receipt changed before adoption.",
                "Reload the review and inspect the current provider operation.",
                retryable=True,
            )
            await self._finish_receipt(receipt, state="cancelled", error=error)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
        now = self._now()
        updated = await domains.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "provider_create_attempt_id": attempt_id,
                "revision": revision,
                "application_status": OPERATOR_REVIEW,
                "provider_reconciliation_required": True,
                "provider_hostname_id": None,
                "deletion_status": None,
            },
            {
                "$set": {
                    "provider_hostname_id": provider_hostname_id,
                    **projection,
                    "application_status": application_status,
                    "https_status": "pending",
                    "custom_route_enabled": False,
                    "action": (
                        "action_required"
                        if application_status == CUTOVER_READY
                        else "processing"
                    ),
                    "last_error": None,
                    "retry_due_at": now,
                    "provider_adopted_by_operation_id": receipt["operation_id"],
                    "updated_at": now,
                },
                "$unset": {
                    "lease_expires_at": "",
                    "provider_reconciliation_required": "",
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(updated, "matched_count", 0):
            await operations.update_one(
                {
                    "_id": create_operation["_id"],
                    "operation_id": attempt_id,
                    "state": "adoption_committing",
                    "adoption_operation_id": receipt["operation_id"],
                    "adoption_source_fingerprint": source_fingerprint,
                },
                {
                    "$set": {"state": "operator_review", "updated_at": self._now()},
                    "$unset": {
                        "adoption_operation_id": "",
                        "adoption_source_fingerprint": "",
                        "adoption_reserved_at": "",
                    },
                },
            )
            error = self._error_detail(
                "operator_review_changed",
                "The ambiguous provider-create review changed before adoption completed.",
                "Reload the operator review; do not retry against the stale revision.",
                retryable=True,
            )
            await self._finish_receipt(receipt, state="cancelled", error=error)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

        completed_at = self._now()
        receipt["completed_at"] = completed_at
        source_completed = await operations.update_one(
            {
                "_id": create_operation["_id"],
                "operation_id": attempt_id,
                "domain_id": str(record["_id"]),
                "planner_id": owner_id,
                "hostname": normalized_hostname,
                "kind": "provider_create",
                "state": "adoption_committing",
                "adoption_operation_id": receipt["operation_id"],
                "adoption_source_fingerprint": source_fingerprint,
            },
            {
                "$set": {
                    "state": "completed",
                    "provider_hostname_id": provider_hostname_id,
                    "adopted_by_operation_id": receipt["operation_id"],
                    "updated_at": completed_at,
                },
                "$unset": {"adoption_operation_id": ""},
            },
        )
        if not getattr(source_completed, "matched_count", 0):
            current_source = await operations.find_one(
                {
                    "_id": create_operation["_id"],
                    "operation_id": attempt_id,
                }
            )
            already_completed = bool(
                current_source
                and current_source.get("state") == "completed"
                and current_source.get("provider_hostname_id") == provider_hostname_id
                and current_source.get("adopted_by_operation_id")
                == receipt["operation_id"]
            )
            if not already_completed:
                error = self._error_detail(
                    "provider_operation_reconciliation_required",
                    "The provider adoption was applied but its source receipt is not finalized.",
                    "Retry this exact decision to reconcile the provider operation receipt.",
                    retryable=True,
                )
                await self._finish_receipt(
                    receipt,
                    state="provider_operation_reconciliation",
                    error=error,
                    extra={
                        "after_revision": revision + 1,
                        "provider_hostname_id": provider_hostname_id,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=error,
                )
        await self._finish_receipt(
            receipt,
            state="completed",
            extra={
                "completed_at": completed_at,
                "after_revision": revision + 1,
                "provider_hostname_id": provider_hostname_id,
                "provider_receipt": provider_receipt,
            },
        )
        return self._response(
            receipt,
            before_revision=revision,
            application_status=application_status,
            provider_hostname_id=provider_hostname_id,
        )


storefront_domain_operator_service = StorefrontDomainOperatorService()
