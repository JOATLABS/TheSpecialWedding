"""Leased reconciliation for storefront custom-domain evidence and recovery."""

from __future__ import annotations

import ipaddress
import json
import logging
import random
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlunsplit
from uuid import uuid4

import httpx
from pymongo import ReturnDocument

from app.constants.storefront_domain import (
    ACTION_REQUIRED,
    ACTIVE,
    AUTHORIZATION_CANCELLED,
    AUTHORIZATION_PENDING,
    CERTIFICATE_VALIDATION,
    CUTOVER_READY,
    DEPLOYING,
    DISCONNECT_FAILED,
    DISCONNECTED,
    DISCONNECTING,
    DNS_SETUP_PENDING,
    EXPIRED,
    HOSTNAME_VALIDATION,
    MIGRATION_PREVALIDATION,
    OPERATOR_REVIEW,
)
from app.core.database import mongo
from app.core.settings import settings
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError
from app.services.storefront_dns_service import (
    StorefrontDnsResolver,
    storefront_dns_resolver,
)
from app.services.storefront_domain_connect_service import (
    SystemDomainConnectAddressResolver,
)
from app.services.storefront_domain_https_probe import (
    MAX_PROBE_RESPONSE_BYTES,
    PROBE_HEADER,
    PROBE_PATH,
    build_probe_challenge,
    verify_probe_attestation,
)
from app.services.storefront_domain_operational_monitor import (
    StorefrontDomainOperationalMonitor,
)
from app.services.storefront_domain_service import (
    StorefrontDomainService,
    discover_authoritative_dns_delegation,
    normalize_authoritative_dns_snapshot,
    normalize_custom_hostname,
    storefront_domain_service,
)

logger = logging.getLogger(__name__)

_LEASE_TTL = timedelta(minutes=2)
_ROUTING_CONFIRMATION_WINDOW = timedelta(minutes=10)
_ACTIVE_POLL_INTERVAL = timedelta(minutes=5)
_MAX_BACKOFF = timedelta(hours=1)
_DUE_PHASES = (
    AUTHORIZATION_PENDING,
    DNS_SETUP_PENDING,
    MIGRATION_PREVALIDATION,
    CUTOVER_READY,
    HOSTNAME_VALIDATION,
    CERTIFICATE_VALIDATION,
    DEPLOYING,
    ACTIVE,
    ACTION_REQUIRED,
    OPERATOR_REVIEW,
    DISCONNECT_FAILED,
    DISCONNECTING,
    DISCONNECTED,
)

# Cloudflare documents these hostname states as requiring intervention rather
# than more passive polling. ``blocked`` cannot recover automatically, while a
# ``moved`` or ``deleted`` hostname must have routing corrected before the
# documented no-change PATCH can restart validation.
_PROVIDER_OPERATOR_REVIEW_STATUSES = frozenset(
    {"blocked", "pending_blocked", "test_blocked"}
)
_PROVIDER_ACTION_REQUIRED_STATUSES = frozenset(
    {"moved", "deleted", "pending_deletion", "test_failed"}
)
_SSL_ACTION_REQUIRED_STATUSES = frozenset(
    {
        "deleted",
        "expired",
        "inactive",
        "initializing_timed_out",
        "validation_timed_out",
        "issuance_timed_out",
        "deployment_timed_out",
        "deletion_timed_out",
    }
)


class StorefrontHttpsVerifier(Protocol):
    async def verify(self, record: Mapping[str, Any]) -> bool: ...


class SystemStorefrontHttpsVerifier:
    """Perform a bounded public-network HTTPS handshake for the exact hostname."""

    def __init__(
        self,
        *,
        address_resolver: Any | None = None,
        http_transport: Any | None = None,
        timeout_seconds: float = 5.0,
        secret_key: str | None = None,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        self._addresses = address_resolver or SystemDomainConnectAddressResolver()
        self._transport = http_transport
        self._timeout_seconds = timeout_seconds
        self._secret_key = settings.secret_key if secret_key is None else secret_key
        self._nonce_factory = nonce_factory

    @staticmethod
    def _content_type_is_json(response: Any) -> bool:
        headers = getattr(response, "headers", {})
        content_type = headers.get("content-type", "") if headers else ""
        return str(content_type).split(";", 1)[0].strip().lower() == "application/json"

    def _verify_body(
        self,
        response: Any,
        record: Mapping[str, Any],
        challenge: str,
        body: bytes,
    ) -> bool:
        if (
            int(getattr(response, "status_code", 0)) != 200
            or not self._content_type_is_json(response)
            or not body
            or len(body) > MAX_PROBE_RESPONSE_BYTES
        ):
            return False
        try:
            payload = json.loads(body)
        except (TypeError, ValueError, UnicodeDecodeError):
            return False
        return verify_probe_attestation(record, challenge, payload, self._secret_key)

    async def _verify_stream(
        self,
        response: Any,
        record: Mapping[str, Any],
        challenge: str,
    ) -> bool:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_PROBE_RESPONSE_BYTES:
                return False
        return self._verify_body(response, record, challenge, bytes(body))

    async def verify(self, record: Mapping[str, Any]) -> bool:
        try:
            hostname = normalize_custom_hostname(
                record.get("hostname"), platform_domains=()
            )
            challenge = build_probe_challenge(
                record,
                self._secret_key,
                **(
                    {"nonce": self._nonce_factory()}
                    if self._nonce_factory is not None
                    else {}
                ),
            )
        except (TypeError, ValueError):
            return False
        try:
            addresses = await self._addresses.resolve(hostname)
            parsed = [ipaddress.ip_address(value) for value in addresses]
        except Exception:
            return False
        if not parsed or any(not address.is_global for address in parsed):
            return False
        url = f"https://{hostname}{PROBE_PATH}"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            PROBE_HEADER: challenge,
        }
        try:
            if self._transport is not None:
                response = await self._transport.request(
                    "GET",
                    url,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                    headers=headers,
                )
                content = getattr(response, "content", b"")
                if not isinstance(content, bytes):
                    return False
                return self._verify_body(response, record, challenge, content)
            async with httpx.AsyncClient(
                follow_redirects=False,
                trust_env=False,
                timeout=self._timeout_seconds,
            ) as client:
                for address in parsed:
                    netloc = (
                        f"[{address.compressed}]"
                        if address.version == 6
                        else address.compressed
                    )
                    pinned_url = urlunsplit(("https", netloc, PROBE_PATH, "", ""))
                    try:
                        async with client.stream(
                            "GET",
                            pinned_url,
                            headers={**headers, "Host": hostname},
                            extensions={"sni_hostname": hostname},
                        ) as response:
                            if await self._verify_stream(response, record, challenge):
                                return True
                    except httpx.RequestError:
                        continue
                return False
        except (TimeoutError, httpx.RequestError):
            return False


class StorefrontDomainReconciliationService:
    """Lease bounded rows and advance them only from independent evidence."""

    def __init__(
        self,
        *,
        mongo_client: Any | None = None,
        cloudflare_service: CloudflareService | None = None,
        dns_resolver: StorefrontDnsResolver | None = None,
        https_verifier: StorefrontHttpsVerifier | None = None,
        domain_service: Any | None = None,
        operational_monitor: Any | None = None,
        cname_target: str | None = None,
        now: Callable[[], datetime] | None = None,
        jitter: Callable[[float, float], float] | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._cloudflare = cloudflare_service or CloudflareService()
        self._dns = dns_resolver or storefront_dns_resolver
        self._https = https_verifier or SystemStorefrontHttpsVerifier()
        self._domains = domain_service or storefront_domain_service
        self._operations = operational_monitor or StorefrontDomainOperationalMonitor(
            mongo_client=self._mongo,
            now=now,
        )
        configured_target = (
            settings.storefront_cname_target if cname_target is None else cname_target
        )
        try:
            self._cname_target = normalize_custom_hostname(
                configured_target, platform_domains=()
            )
        except (TypeError, ValueError):
            self._cname_target = None
        self._now = now or (lambda: datetime.now(UTC))
        self._jitter = jitter or random.uniform

    @staticmethod
    def _aware(value: object) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @staticmethod
    def _safe_error(exc: Exception) -> dict[str, object]:
        support_id = f"sfd_{uuid4().hex[:16]}"
        provider = (
            {
                "name": "cloudflare",
                "operation": exc.operation,
                "kind": exc.kind,
                "status_code": exc.provider_status_code,
            }
            if isinstance(exc, CloudflareServiceError)
            else None
        )
        return {
            "code": "domain_reconciliation_failed",
            "message": "Custom-domain activation could not be checked right now.",
            "customer_action": "Keep using the platform URL and retry later.",
            "retryable": True,
            "support_id": support_id,
            **({"provider": provider} if provider else {}),
        }

    @staticmethod
    def _customer_error(
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool,
        provider: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Build a stable public error shape without exposing raw responses."""

        return {
            "code": code,
            "message": message,
            "customer_action": customer_action,
            "retryable": retryable,
            "support_id": f"sfd_{uuid4().hex[:16]}",
            **({"provider": provider} if provider else {}),
        }

    @staticmethod
    def _provider_error_metadata(exc: CloudflareServiceError) -> dict[str, object]:
        return {
            "name": "cloudflare",
            "operation": exc.operation,
            "kind": exc.kind,
            "status_code": exc.provider_status_code,
        }

    async def _fail_closed(
        self,
        record: dict,
        *,
        application_status: str,
        action: str,
        error: dict[str, object],
        provider_hostname_status: str | None = None,
        provider_status: str | None = None,
        provider_projection: dict[str, Any] | None = None,
        provider_observation: dict[str, Any] | None = None,
        provider_error: dict[str, Any] | None = None,
    ) -> None:
        """Revoke only custom-host routing after authoritative provider loss.

        The lease, lifecycle revision, and deletion intent are all part of the
        compare-and-set. A concurrent disconnect therefore always wins, and
        publication or the platform slug is never touched.
        """

        now = self._now()
        fields: dict[str, Any] = {
            **(provider_projection or {}),
            "application_status": application_status,
            "status": "pending",
            "custom_route_enabled": False,
            # A previous route attestation is no longer current once the
            # provider identity or lifecycle becomes unsafe. Preserve it in
            # historical observations, but require a fresh HTTPS proof before
            # routing can ever be restored.
            "https_status": "pending",
            "action": action,
            "last_error": error,
            "last_checked_at": now,
            "retry_due_at": now + _ACTIVE_POLL_INTERVAL,
            "updated_at": now,
        }
        if provider_hostname_status is not None:
            fields["provider_hostname_status"] = provider_hostname_status
        if provider_status is not None:
            fields["provider_status"] = provider_status
        if provider_observation is not None:
            fields["provider_last_observation"] = provider_observation
            fields["provider_last_observed_at"] = now
        if provider_error is not None:
            fields["provider_last_error"] = provider_error
            fields["provider_last_observed_at"] = now
        unset_fields = {
            "lease_token": "",
            "lease_expires_at": "",
            "reconciliation_started_at": "",
        }
        if provider_observation is not None and provider_error is None:
            unset_fields["provider_last_error"] = ""
        await self._mongo.db["storefront_domains"].update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
                "revision": record.get("revision"),
                "deletion_status": record.get("deletion_status"),
            },
            {
                "$set": fields,
                "$unset": unset_fields,
            },
        )

    async def _delegation_is_current(self, record: dict) -> bool:
        """Fence routing evidence to the delegation captured for this claim."""

        authority = record.get("authoritative_dns")
        stored = normalize_authoritative_dns_snapshot(authority)
        current: dict[str, object] | None = None
        if stored:
            current = await discover_authoritative_dns_delegation(
                self._dns, record["hostname"]
            )
            if normalize_authoritative_dns_snapshot(current) == stored:
                return True

        now = self._now()
        changed = current is not None
        error = self._customer_error(
            (
                "authoritative_dns_delegation_changed"
                if changed
                else "authoritative_dns_missing"
            ),
            (
                "The domain's authoritative DNS provider changed after setup."
                if changed
                else "The authoritative DNS snapshot for this domain is unavailable."
            ),
            "Restart domain setup to generate a fresh ownership record for the current DNS provider.",
            retryable=False,
        )
        query: dict[str, object] = {
            "_id": record["_id"],
            "lease_token": record.get("lease_token"),
            "revision": record.get("revision"),
            "deletion_status": record.get("deletion_status"),
            # Preserve the complete preflight evidence as a CAS fence. A
            # concurrent claim refresh or disconnect must always win.
            "authoritative_dns": authority,
        }
        fields: dict[str, object] = {
            "application_status": ACTION_REQUIRED,
            "status": "pending",
            "ownership_status": "expired",
            "routing_dns_status": "mismatch",
            "https_status": "pending",
            "custom_route_enabled": False,
            "action": "action_required",
            "claim_expires_at": now,
            "last_checked_at": now,
            "last_error": error,
            "retry_due_at": now + _ACTIVE_POLL_INTERVAL,
            "updated_at": now,
        }
        if current is not None:
            fields["current_authoritative_dns"] = {
                **current,
                "observed_at": now,
            }
        await self._mongo.db["storefront_domains"].update_one(
            query,
            {
                "$set": fields,
                "$unset": {
                    "lease_token": "",
                    "lease_expires_at": "",
                    "reconciliation_started_at": "",
                },
                "$inc": {"revision": 1},
            },
        )
        return False

    def _backoff(self, attempts: int) -> timedelta:
        seconds = min(3600.0, 30.0 * (2 ** max(0, min(attempts - 1, 7))))
        return timedelta(seconds=seconds + self._jitter(0.0, seconds * 0.2))

    async def _lease_one(self) -> dict | None:
        now = self._now()
        token = f"sdl_{uuid4().hex}"
        return await self._mongo.db["storefront_domains"].find_one_and_update(
            {
                "application_status": {"$in": list(_DUE_PHASES)},
                "$and": [
                    {
                        "$or": [
                            {"retry_due_at": {"$lte": now}},
                            {
                                "retry_due_at": {"$exists": False},
                                "provider_hostname_id": {"$type": "string"},
                            },
                            {
                                "retry_due_at": None,
                                "provider_hostname_id": {"$type": "string"},
                            },
                        ]
                    },
                    {
                        "$or": [
                            {"lease_expires_at": {"$exists": False}},
                            {"lease_expires_at": None},
                            {"lease_expires_at": {"$lte": now}},
                        ]
                    },
                ],
            },
            {
                "$set": {
                    "lease_token": token,
                    "lease_expires_at": now + _LEASE_TTL,
                    "reconciliation_started_at": now,
                    "updated_at": now,
                },
                "$inc": {"reconciliation_attempts": 1},
            },
            sort=[("retry_due_at", 1), ("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )

    async def sweep_due(self, *, batch_size: int = 25) -> int:
        bounded = max(1, min(int(batch_size), 100))
        processed = 0
        seen: set[object] = set()
        for _ in range(bounded):
            record = await self._lease_one()
            if not record or record.get("_id") in seen:
                break
            seen.add(record.get("_id"))
            processed += 1
            try:
                await self._process_leased(record)
            except Exception as exc:
                await self._defer_failure(record, exc)
            finally:
                await self._observe_domain_operations_safely(record.get("_id"))
        await self._observe_conflict_reviews_safely()
        await self._observe_backlog_safely()
        return processed

    async def _observe_domain_operations_safely(self, domain_id: object) -> None:
        """Keep alerting failures from interrupting reconciliation recovery."""

        try:
            current = await self._mongo.db["storefront_domains"].find_one(
                {"_id": domain_id}
            )
            await self._operations.observe_domain(current)
        except Exception:
            logger.exception(
                "Failed to publish storefront-domain operational incident",
                extra={"domain_id": str(domain_id)},
            )

    async def _observe_backlog_safely(self) -> None:
        """Keep queue telemetry best effort and independent from state writes."""

        try:
            await self._operations.observe_backlog(_DUE_PHASES)
        except Exception:
            logger.exception("Failed to publish storefront-domain backlog metrics")

    async def _observe_conflict_reviews_safely(self) -> None:
        """Alert on verified hostname claims that bypass the domain lease queue."""

        observe = getattr(self._operations, "observe_conflict_reviews", None)
        if not callable(observe):
            return
        try:
            await observe(limit=100)
        except Exception:
            logger.exception(
                "Failed to publish storefront conflict-claim operational incidents"
            )

    async def _defer_failure(self, record: dict, exc: Exception) -> None:
        attempts = int(record.get("reconciliation_attempts") or 1)
        error = self._safe_error(exc)
        provider_fields = (
            {
                "provider_last_error": exc.as_dict(),
                "provider_last_observed_at": self._now(),
            }
            if isinstance(exc, CloudflareServiceError)
            else {}
        )
        await self._mongo.db["storefront_domains"].update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
                "revision": record.get("revision"),
                "deletion_status": record.get("deletion_status"),
            },
            {
                "$set": {
                    "last_error": error,
                    **provider_fields,
                    "retry_due_at": self._now() + self._backoff(attempts),
                    "updated_at": self._now(),
                },
                "$unset": {
                    "lease_token": "",
                    "lease_expires_at": "",
                    "reconciliation_started_at": "",
                },
            },
        )
        logger.warning(
            "Storefront domain reconciliation deferred support_id=%s",
            error["support_id"],
        )

    async def _process_leased(self, record: dict) -> None:
        collection = self._mongo.db["storefront_domains"]
        owner_id = str(record.get("planner_id") or "")
        if record.get("deletion_status") == "operator_review":
            # A conflicting provider delete response requires the existing
            # root-admin review path. Never turn that support hold into an
            # automatic second DELETE request.
            await self._release_if_still_leased(record, timedelta(days=1))
            return
        if record.get("deletion_status") in {
            "provider_delete_pending",
            "retry_pending",
            "local_cleanup_pending",
        }:
            await self._domains._disconnect_claim_record(collection, record, owner_id)
            await self._release_if_still_leased(record, timedelta(minutes=5))
            return

        if record.get("application_status") == AUTHORIZATION_PENDING:
            await self._reconcile_authorization_flow(record)
            return

        if not record.get("provider_hostname_id"):
            if record.get("application_status") in {
                DNS_SETUP_PENDING,
                MIGRATION_PREVALIDATION,
            }:
                if (
                    record.get("application_status") == DNS_SETUP_PENDING
                    and record.get("setup_method") == "automatic"
                    and record.get("domain_connect_authorized_at") is not None
                ):
                    # A provider-approved automatic flow must be able to finish
                    # without asking a nontechnical planner to perform the
                    # manual "I've added these records" activation step. The
                    # domain service re-resolves current plan capabilities and
                    # independently proves authoritative DNS before it permits
                    # any Cloudflare mutation.
                    await self._domains.verify_authorized_automatic_for_owner_id(
                        owner_id, record.get("claim_attempt_id")
                    )
                else:
                    await self._domains.observe_pending_for_owner_id(owner_id)
                await self._release_if_still_leased(record, timedelta(seconds=30))
                return
            if record.get("application_status") == OPERATOR_REVIEW:
                # An unknown provider-create outcome is an ownership decision,
                # not a polling decision.  Only the root-admin operator API may
                # bind a Cloudflare row, using its revision-fenced review
                # receipt.  Background reconciliation must never auto-adopt a
                # candidate even when one row appears demonstrably new.
                await self._release_if_still_leased(record, timedelta(minutes=5))
                return
            else:
                await self._release_if_still_leased(record, timedelta(minutes=5))
                return

        provider_id = record.get("provider_hostname_id")
        if not await self._delegation_is_current(record):
            return
        try:
            provider_result = await self._cloudflare.get_custom_hostname(provider_id)
        except CloudflareServiceError as exc:
            if not (exc.kind == "provider" and exc.provider_status_code == 404):
                raise
            await self._fail_closed(
                record,
                application_status=OPERATOR_REVIEW,
                action="operator_review",
                provider_hostname_status="not_found",
                provider_status="not_found",
                provider_error=exc.as_dict(),
                error=self._customer_error(
                    "provider_hostname_missing",
                    "The custom-domain provider no longer has this hostname mapping.",
                    "Keep using the platform URL and contact support before changing DNS or reconnecting the hostname.",
                    retryable=False,
                    provider=self._provider_error_metadata(exc),
                ),
            )
            return

        try:
            observed_hostname = normalize_custom_hostname(
                provider_result.get("hostname"), platform_domains=()
            )
        except (TypeError, ValueError):
            observed_hostname = None
        if provider_result.get("id") != provider_id or observed_hostname != record.get(
            "hostname"
        ):
            await self._fail_closed(
                record,
                application_status=OPERATOR_REVIEW,
                action="operator_review",
                provider_hostname_status="identity_mismatch",
                provider_observation=provider_result,
                error=self._customer_error(
                    "provider_hostname_identity_mismatch",
                    "The provider returned a hostname mapping that does not match this storefront.",
                    "Keep using the platform URL and contact support; do not change DNS or retry the connection.",
                    retryable=False,
                    provider={
                        "name": "cloudflare",
                        "operation": "get_custom_hostname",
                        "kind": "identity_mismatch",
                    },
                ),
            )
            return
        projection = StorefrontDomainService._provider_projection(provider_result)
        provider_status = projection["provider_status"]
        ssl_status = projection["ssl_status"]

        if provider_status in _PROVIDER_OPERATOR_REVIEW_STATUSES:
            await self._fail_closed(
                record,
                application_status=OPERATOR_REVIEW,
                action="operator_review",
                provider_hostname_status=provider_status,
                provider_status=provider_status,
                provider_projection=projection,
                provider_observation=provider_result,
                error=self._customer_error(
                    "provider_hostname_blocked",
                    "The custom-domain provider has blocked this hostname from activation.",
                    "Keep using the platform URL and contact support; do not change DNS until the provider hold is reviewed.",
                    retryable=False,
                    provider={
                        "name": "cloudflare",
                        "operation": "hostname_validation",
                        "status": provider_status,
                    },
                ),
            )
            return
        if provider_status in _PROVIDER_ACTION_REQUIRED_STATUSES:
            await self._fail_closed(
                record,
                application_status=ACTION_REQUIRED,
                action="action_required",
                provider_hostname_status=provider_status,
                provider_status=provider_status,
                provider_projection=projection,
                provider_observation=provider_result,
                error=self._customer_error(
                    "provider_hostname_inactive",
                    "The provider hostname is no longer active for storefront traffic.",
                    "Confirm the displayed CNAME record, then use Retry verification to restart provider validation.",
                    retryable=True,
                    provider={
                        "name": "cloudflare",
                        "operation": "hostname_validation",
                        "status": provider_status,
                    },
                ),
            )
            return
        if ssl_status in _SSL_ACTION_REQUIRED_STATUSES:
            await self._fail_closed(
                record,
                application_status=ACTION_REQUIRED,
                action="action_required",
                provider_hostname_status=provider_status,
                provider_status=provider_status,
                provider_projection=projection,
                provider_observation=provider_result,
                error=self._customer_error(
                    "provider_certificate_inactive",
                    "The provider certificate could not become active.",
                    "Confirm the displayed certificate-validation DNS records, then use Retry verification.",
                    retryable=True,
                    provider={
                        "name": "cloudflare",
                        "operation": "certificate_validation",
                        "status": ssl_status,
                    },
                ),
            )
            return

        authoritative = record.get("authoritative_dns")
        nameservers = (
            list(authoritative.get("nameservers") or [])
            if isinstance(authoritative, dict)
            else []
        )
        if not nameservers:
            raise RuntimeError("authoritative DNS evidence is unavailable")
        cname_values = await self._dns.query_authoritative(
            record["hostname"], "CNAME", nameservers
        )
        if not await self._delegation_is_current(record):
            return
        normalized_cnames = sorted(
            {
                str(value).rstrip(".").lower()
                for value in cname_values
                if isinstance(value, str) and value.strip()
            }
        )
        observed_routing = (
            "verified"
            if self._cname_target and self._cname_target in normalized_cnames
            else ("mismatch" if normalized_cnames else "pending")
        )
        now = self._now()
        mismatch_update: dict[str, object] = {}
        mismatch_unset: dict[str, str] = {}
        confirmed_drift = False
        routing_status = observed_routing
        first_at: datetime | None = None
        pre_cutover_migration = bool(
            record.get("intent") == "migration"
            and not record.get("migration_cutover_completed_at")
            and not record.get("custom_route_enabled")
        )
        if observed_routing == "verified":
            mismatch_unset.update(
                {
                    "routing_mismatch_count": "",
                    "routing_mismatch_first_at": "",
                }
            )
        elif pre_cutover_migration:
            # The customer's live route is intentionally unchanged until the
            # SaaS hostname and certificate are ready. This is not drift.
            routing_status = observed_routing
        else:
            previous_count = int(record.get("routing_mismatch_count") or 0)
            first_at = self._aware(record.get("routing_mismatch_first_at"))
            if previous_count < 1 or not first_at:
                mismatch_count = 1
                first_at = now
            elif now - first_at >= _ROUTING_CONFIRMATION_WINDOW:
                mismatch_count = previous_count + 1
                confirmed_drift = mismatch_count >= 2
            else:
                mismatch_count = previous_count
            mismatch_update.update(
                {
                    "routing_mismatch_count": mismatch_count,
                    "routing_mismatch_first_at": first_at,
                }
            )
            if record.get("custom_route_enabled") and not confirmed_drift:
                routing_status = str(record.get("routing_dns_status") or "verified")

        https_status = "pending"
        if (
            observed_routing == "verified"
            and provider_status == "active"
            and ssl_status == "active"
        ):
            https_status = "verified" if await self._https.verify(record) else "failed"
        elif record.get("custom_route_enabled") and not confirmed_drift:
            https_status = str(record.get("https_status") or "pending")

        five_proofs = (
            record.get("ownership_status") == "verified"
            and routing_status == "verified"
            and provider_status == "active"
            and ssl_status == "active"
            and https_status == "verified"
            and not confirmed_drift
        )
        state_error: dict[str, object] | None = None
        if https_status == "failed":
            application_status = ACTION_REQUIRED
            action = "action_required"
            route_enabled = False
            state_error = self._customer_error(
                "custom_domain_https_unreachable",
                "The hostname and certificate are active, but the storefront did not answer the secure route check.",
                "Keep using the platform URL, confirm the routing record, then select Check again; contact support if the check continues to fail.",
                retryable=True,
            )
        elif confirmed_drift:
            application_status = ACTION_REQUIRED
            action = "action_required"
            route_enabled = False
            state_error = self._customer_error(
                "custom_domain_routing_drift",
                "The custom hostname no longer points to the storefront service.",
                "Restore the displayed CNAME record, then select Check again.",
                retryable=True,
            )
        elif five_proofs:
            application_status = ACTIVE
            action = "none"
            route_enabled = True
        elif (
            pre_cutover_migration
            and provider_status == "active"
            and ssl_status == "active"
            and observed_routing != "verified"
        ):
            application_status = CUTOVER_READY
            action = "action_required"
            route_enabled = False
        elif provider_status != "active":
            application_status = HOSTNAME_VALIDATION
            action = "processing"
            route_enabled = False
        elif ssl_status != "active":
            application_status = CERTIFICATE_VALIDATION
            action = "processing"
            route_enabled = False
        else:
            application_status = DEPLOYING
            action = "processing"
            route_enabled = False

        retry_delay = (
            _ACTIVE_POLL_INTERVAL
            if five_proofs
            else (
                max(timedelta(), first_at + _ROUTING_CONFIRMATION_WINDOW - now)
                if observed_routing != "verified" and not confirmed_drift and first_at
                else self._backoff(int(record.get("reconciliation_attempts") or 1))
            )
        )
        migration_update: dict[str, Any] = {}
        if application_status == CUTOVER_READY:
            migration_update["migration_cutover_ready_at"] = (
                record.get("migration_cutover_ready_at") or now
            )
        if five_proofs and record.get("intent") == "migration":
            migration_update["migration_cutover_completed_at"] = now

        update: dict[str, Any] = {
            "$set": {
                **projection,
                **mismatch_update,
                **migration_update,
                "provider_last_observation": provider_result,
                "provider_last_observed_at": now,
                "provider_hostname_status": provider_status,
                "routing_dns_status": routing_status,
                "routing_dns_observation": {
                    "status": observed_routing,
                    "values": normalized_cnames,
                    "observed_at": now,
                },
                "https_status": https_status,
                "https_last_observed_at": now,
                "application_status": application_status,
                "status": "active" if five_proofs else "pending",
                "custom_route_enabled": route_enabled,
                "action": action,
                "last_error": state_error,
                "last_checked_at": now,
                "retry_due_at": now + retry_delay,
                "updated_at": now,
            },
            "$unset": {
                **mismatch_unset,
                "provider_last_error": "",
                "lease_token": "",
                "lease_expires_at": "",
                "reconciliation_started_at": "",
            },
        }
        persisted = await collection.update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
                "revision": record.get("revision"),
                "deletion_status": None,
                "authoritative_dns": record.get("authoritative_dns"),
            },
            update,
        )
        if not getattr(persisted, "matched_count", 0):
            await self._discard_stale_lease(record)

    async def _reconcile_authorization_flow(self, record: dict) -> None:
        collection = self._mongo.db["storefront_domains"]
        now = self._now()
        flow = await self._mongo.db["storefront_domain_flows"].find_one(
            {
                "domain_id": str(record["_id"]),
                "attempt_id": record.get("claim_attempt_id"),
                "planner_id": record.get("planner_id"),
            }
        )
        flow_state = flow.get("state") if flow else None
        flow_expiry = self._aware(flow.get("expires_at")) if flow else None
        completion_outcome = flow.get("completion_outcome") if flow else None
        if flow_state == "consumed" and completion_outcome == "authorized":
            application_status = DNS_SETUP_PENDING
            action = "processing"
            retry_due_at = now
            last_error = None
        elif flow_state == "consumed" and completion_outcome == "cancelled":
            application_status = AUTHORIZATION_CANCELLED
            action = "action_required"
            retry_due_at = None
            last_error = flow.get("last_error") or self._customer_error(
                "domain_connect_authorization_cancelled",
                "Automatic DNS authorization was cancelled.",
                "Start automatic setup again or use manual DNS setup.",
                retryable=True,
            )
        elif flow_state == "consumed" and completion_outcome == "failed":
            application_status = ACTION_REQUIRED
            action = "action_required"
            retry_due_at = None
            last_error = flow.get("last_error") or self._customer_error(
                "domain_connect_authorization_failed",
                "The DNS provider did not authorize automatic setup.",
                "Retry automatic setup or use manual DNS setup.",
                retryable=True,
            )
        elif flow_state == "consumed":
            application_status = ACTION_REQUIRED
            action = "action_required"
            retry_due_at = None
            last_error = self._customer_error(
                "domain_connect_completion_outcome_missing",
                "Automatic DNS completion could not be verified safely.",
                "Restart automatic setup or use manual DNS setup.",
                retryable=False,
            )
        elif flow_expiry and flow_expiry > now:
            # Provider callback GET records only the one-time flow result. It
            # has no authenticated actor or CSRF proof, so authorized,
            # cancelled, failed, and completing callbacks all remain inert
            # until the owner-scoped completion POST consumes the flow.
            await self._release_if_still_leased(record, flow_expiry - now)
            return
        else:
            application_status = EXPIRED
            action = "action_required"
            retry_due_at = None
            last_error = {
                "code": "domain_connect_flow_expired",
                "message": "Automatic DNS authorization expired before completion.",
                "customer_action": "Start automatic setup again or use manual DNS setup.",
                "retryable": True,
                "support_id": f"sfd_{uuid4().hex[:16]}",
            }
        update: dict[str, Any] = {
            "$set": {
                "application_status": application_status,
                "action": action,
                "last_error": last_error,
                "updated_at": now,
            },
            "$unset": {
                "lease_token": "",
                "lease_expires_at": "",
                "reconciliation_started_at": "",
            },
        }
        if retry_due_at is None:
            update["$unset"]["retry_due_at"] = ""
        else:
            update["$set"]["retry_due_at"] = retry_due_at
        await collection.update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
                "revision": record.get("revision"),
                "deletion_status": record.get("deletion_status"),
            },
            update,
        )

    async def _release_if_still_leased(self, record: dict, delay: timedelta) -> None:
        await self._mongo.db["storefront_domains"].update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
                "revision": record.get("revision"),
                "deletion_status": record.get("deletion_status"),
            },
            {
                "$set": {
                    "retry_due_at": self._now() + delay,
                    "updated_at": self._now(),
                },
                "$unset": {
                    "lease_token": "",
                    "lease_expires_at": "",
                    "reconciliation_started_at": "",
                },
            },
        )

    async def _discard_stale_lease(self, record: dict) -> None:
        """Release only this worker's lease after a lifecycle CAS loses.

        A concurrent observe, retry, or disconnect owns the newer state and
        retry schedule. The stale worker must not persist its provider result,
        but it also must not strand its unique lease until TTL expiry.
        """

        released = await self._mongo.db["storefront_domains"].update_one(
            {
                "_id": record["_id"],
                "lease_token": record.get("lease_token"),
            },
            {
                "$unset": {
                    "lease_token": "",
                    "lease_expires_at": "",
                    "reconciliation_started_at": "",
                }
            },
        )
        if getattr(released, "matched_count", 0):
            logger.info(
                "Discarded stale storefront-domain reconciliation lease domain_id=%s",
                str(record.get("_id")),
            )


system_storefront_https_verifier = SystemStorefrontHttpsVerifier()
storefront_domain_reconciliation_service = StorefrontDomainReconciliationService(
    https_verifier=system_storefront_https_verifier
)
