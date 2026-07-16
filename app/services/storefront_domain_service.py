"""Owner-scoped storefront custom-domain lifecycle.

Custom domains are child records, separate from storefront settings. The
service reserves a normalized hostname locally before provisioning it at the
provider, persists validation state, compensates partial creates, and never
deletes or rewrites a mapping merely because its entitlement is later lost.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import html
import ipaddress
import logging
import re
import secrets
from typing import Any, Callable, Iterable
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException, status
from cryptography.fernet import Fernet, InvalidToken
import idna
from pymongo.errors import DuplicateKeyError

from app.constants.roles import is_wedding_planner_role
from app.constants.storefront_domain import (
    ACTIVE,
    CERTIFICATE_VALIDATION,
    CLAIM_PENDING,
    CUTOVER_READY,
    DEPLOYING,
    DISCONNECTED,
    DISCONNECT_FAILED,
    DISCONNECTING,
    DNS_SETUP_PENDING,
    EXPIRED,
    HOSTNAME_VALIDATION,
    MIGRATION_PREVALIDATION,
    OPERATOR_REVIEW,
    PROVIDER_PROVISIONING,
    PROVIDER_CREATE_REQUEST_WINDOW_SECONDS,
    STOREFRONT_DOMAIN_INSTRUCTIONS_EMAIL_TYPE,
    STOREFRONT_DOMAIN_APPLICATION_STATUSES,
)
from app.core.database import mongo
from app.core.settings import settings
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError
from app.services.config_validator import get_storefront_domain_readiness
from app.services.storefront_dns_service import (
    StorefrontDnsResolutionError,
    StorefrontDnsResolver,
    storefront_dns_resolver,
)
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
    storefront_entitlement_service,
)
from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy
from app.utils.planner_ownership import normalize_planner_id


logger = logging.getLogger(__name__)

_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_DEFAULT_PLATFORM_DOMAINS = frozenset({"thespecialwedding.io", "thespecialwedding.com"})
_PROVIDER_DELETE_PENDING = "provider_delete_pending"
_PROVIDER_DELETE_RETRY_PENDING = "retry_pending"
_LOCAL_CLEANUP_PENDING = "local_cleanup_pending"
_PROVISIONING = "provisioning"
_PROVISIONING_UNKNOWN = "provisioning_unknown"
_PROVISIONING_ABSENCE_CONFIRMATIONS = 2
_PROVISIONING_RECONCILIATION_GRACE_SECONDS = 60
_PROVISIONING_LEASE_SECONDS = 10 * 60
_CLAIM_TTL = timedelta(days=7)
_INSTRUCTION_LINK_TTL = timedelta(days=7)
_INSTRUCTION_DELIVERY_LEASE = timedelta(minutes=2)
_INSTRUCTION_QUOTA_WINDOW = timedelta(hours=1)
_INSTRUCTION_OWNER_SEND_LIMIT = 20
_INSTRUCTION_ATTEMPT_SEND_LIMIT = 10
_INSTRUCTION_RECIPIENT_SEND_LIMIT = 3
_INSTRUCTION_ACTIVE_LINK_LIMIT = 5
_INSTRUCTION_LINK_LIST_LIMIT = 20
_LIFECYCLE_RECEIPT_TTL = timedelta(days=90)
_PROVIDER_RETRY_THROTTLE = timedelta(minutes=5)
_DNS_RECORD_TYPES = ("NS", "A", "AAAA", "CNAME", "CAA", "TXT")
_NON_ROUTABLE_DOMAIN_STATUSES = frozenset(
    {"deleting", "delete_failed", "provider_deleted"}
)
_DNS_PROVIDER_DETAILS = {
    "google_or_squarespace_dns": (
        "Google Cloud DNS or Squarespace DNS",
        None,
    ),
    "squarespace_dns": (
        "Squarespace DNS",
        "https://account.squarespace.com/domains",
    ),
    "cloudflare": ("Cloudflare", "https://dash.cloudflare.com/"),
    "amazon_route53": (
        "Amazon Route 53",
        "https://console.aws.amazon.com/route53/v2/hostedzones",
    ),
    "godaddy": ("GoDaddy", "https://dcc.godaddy.com/manage/dns"),
    "namecheap": (
        "Namecheap",
        "https://ap.www.namecheap.com/domains/domaincontrolpanel/",
    ),
    "namesilo": ("NameSilo", "https://www.namesilo.com/account_domains.php"),
}


def _mask_instruction_recipient(email: str) -> str:
    """Return a useful receipt hint without persisting a recoverable address."""

    local, separator, domain = email.strip().casefold().rpartition("@")
    if not separator or not local or not domain:
        return "masked recipient"
    domain_labels = domain.split(".")
    domain_name = domain_labels[0]
    domain_suffix = ".".join(domain_labels[1:])
    local_hint = f"{local[0]}***"
    domain_hint = f"{domain_name[0]}***" if domain_name else "***"
    return f"{local_hint}@{domain_hint}{'.' + domain_suffix if domain_suffix else ''}"


def _ascii_hostname(value: str) -> str:
    try:
        ascii_hostname = (
            idna.encode(
                value,
                uts46=True,
                std3_rules=True,
                transitional=False,
            )
            .decode("ascii")
            .lower()
        )
    except idna.IDNAError as exc:
        raise ValueError("Custom domain contains an invalid IDNA label") from exc

    labels = ascii_hostname.split(".")
    for ascii_label in labels:
        if len(ascii_label) > 63 or not _HOST_LABEL.fullmatch(ascii_label):
            raise ValueError("Custom domain contains an invalid hostname label")
    return ".".join(labels)


def normalize_custom_hostname(
    value: str,
    *,
    platform_domains: Iterable[str] | None = None,
) -> str:
    """Normalize a hostname-only custom domain or reject unsafe input."""

    if not isinstance(value, str) or not value:
        raise ValueError("Custom domain must be a hostname")
    if value != value.strip() or any(character.isspace() for character in value):
        raise ValueError("Custom domain cannot contain whitespace")
    if any(marker in value for marker in ("://", "@", ":", "/", "?", "#", "*")):
        raise ValueError(
            "Enter a hostname only, without a URL, port, path, or wildcard"
        )
    if value.endswith("."):
        raise ValueError("Custom domain must not end with a dot")

    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses cannot be used as custom domains")

    hostname = _ascii_hostname(value)
    if len(hostname) > 253 or "." not in hostname:
        raise ValueError("Custom domain must be a fully qualified hostname")
    if hostname.rsplit(".", 1)[-1].isdigit():
        raise ValueError("Custom domain must not use a numeric top-level label")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Localhost cannot be used as a custom domain")

    blocked_domains: set[str] = set()
    blocked_source = (
        _DEFAULT_PLATFORM_DOMAINS if platform_domains is None else platform_domains
    )
    for platform_domain in blocked_source:
        if not isinstance(platform_domain, str):
            continue
        candidate = platform_domain.strip().lower().rstrip(".")
        if not candidate:
            continue
        try:
            blocked_domains.add(_ascii_hostname(candidate))
        except ValueError:
            continue
    if any(
        hostname == platform_domain or hostname.endswith(f".{platform_domain}")
        for platform_domain in blocked_domains
    ):
        raise ValueError("Platform-owned hostnames cannot be mapped as custom domains")
    return hostname


def normalize_authoritative_dns_snapshot(
    authority: object,
) -> tuple[str, tuple[str, ...]] | None:
    """Return the security-relevant delegation snapshot in canonical form."""

    if not isinstance(authority, dict):
        return None
    zone = authority.get("zone")
    nameservers = authority.get("nameservers")
    if not isinstance(zone, str) or not isinstance(nameservers, list):
        return None
    normalized_zone = zone.strip().lower().rstrip(".")
    normalized_nameservers = tuple(
        sorted(
            {
                value.strip().lower().rstrip(".")
                for value in nameservers
                if isinstance(value, str) and value.strip()
            }
        )
    )
    if not normalized_zone or not normalized_nameservers:
        return None
    return normalized_zone, normalized_nameservers


async def discover_authoritative_dns_delegation(
    resolver: StorefrontDnsResolver, hostname: str
) -> dict[str, object]:
    """Rediscover the currently delegated zone and NS set via recursive DNS.

    Ownership and routing proofs must never bootstrap from the nameservers saved
    during preflight. That snapshot is only a compare-and-swap fence; recursive
    DNS is consulted again immediately before each authoritative proof.
    """

    normalized_hostname = normalize_custom_hostname(hostname, platform_domains=())
    labels = normalized_hostname.split(".")
    for offset in range(0, len(labels) - 1):
        candidate = ".".join(labels[offset:])
        nameservers = await resolver.query(candidate, "NS")
        normalized = normalize_authoritative_dns_snapshot(
            {"zone": candidate, "nameservers": list(nameservers)}
        )
        if normalized:
            zone, normalized_nameservers = normalized
            return {"zone": zone, "nameservers": list(normalized_nameservers)}
    raise StorefrontDnsResolutionError(
        f"Authoritative DNS delegation is unavailable for {normalized_hostname}"
    )


class StorefrontDomainService:
    """Provision and resolve planner-owned custom storefront hostnames."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        cloudflare_service: CloudflareService | None = None,
        entitlement_service: StorefrontEntitlementService | None = None,
        dns_resolver: StorefrontDnsResolver | None = None,
        *,
        claim_encryption_key: str | None = None,
        cname_target: str | None = None,
        platform_domains: Iterable[str] | None = None,
        readiness_resolver: Callable[[], dict[str, object]] | None = None,
        instruction_email_service: Any | None = None,
        instruction_public_base_url: str | None = None,
        domain_connect_discovery: Any | None = None,
        rollout_policy: StorefrontDomainRolloutPolicy | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._cloudflare = cloudflare_service or CloudflareService()
        self._entitlements = entitlement_service or storefront_entitlement_service
        self._dns_resolver = dns_resolver or storefront_dns_resolver
        self._readiness = readiness_resolver or get_storefront_domain_readiness
        self._instruction_email_service = instruction_email_service
        self._instruction_public_base_url = (
            instruction_public_base_url
            if instruction_public_base_url is not None
            else settings.frontend_url
        )
        self._domain_connect_discovery = domain_connect_discovery
        self._rollout_policy = (
            rollout_policy or StorefrontDomainRolloutPolicy.from_settings()
        )
        encryption_secret = claim_encryption_key or settings.secret_key
        self._claim_cipher_key = base64.urlsafe_b64encode(
            hashlib.sha256(
                f"storefront-domain-claim-v1:{encryption_secret}".encode()
            ).digest()
        )
        self._claim_cipher = Fernet(self._claim_cipher_key)
        configured_cname = (
            settings.storefront_cname_target if cname_target is None else cname_target
        )
        try:
            self._cname_target = (
                normalize_custom_hostname(configured_cname, platform_domains=())
                if configured_cname
                else None
            )
        except (TypeError, ValueError):
            self._cname_target = None
        configured_platform_domains = (
            settings.storefront_platform_domains
            if platform_domains is None
            else platform_domains
        )
        self._platform_domains = set(
            configured_platform_domains or _DEFAULT_PLATFORM_DOMAINS
        )
        frontend_hostname = urlparse(settings.frontend_url or "").hostname
        if frontend_hostname:
            self._platform_domains.add(frontend_hostname)
        if self._cname_target:
            self._platform_domains.add(self._cname_target)

    @property
    def provider_configuration_present(self) -> bool:
        """Whether a connect request could reach the custom-hostname provider."""

        readiness = self._readiness()
        return bool(
            readiness.get("ready") is True
            and self._cname_target
            and self._cloudflare.is_configured
        )

    def _require_rollout(self, owner_id: str, hostname: str) -> None:
        if self._rollout_policy.allows(owner_id, hostname):
            return
        raise self._domain_http_error(
            status.HTTP_403_FORBIDDEN,
            "custom_domain_rollout_unavailable",
            "New custom-domain setup is not available for this storefront yet.",
            "Keep using the platform storefront URL while the production pilot is restricted.",
            retryable=False,
            field="domain",
        )

    def _require_provider_mutations(self, owner_id: str, hostname: str) -> None:
        """Fail closed before any Cloudflare mutation or provider snapshot."""

        if self._readiness().get("ready") is True:
            self._require_rollout(owner_id, hostname)
            return
        raise self._domain_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "custom_domain_provider_unavailable",
            "Custom-domain provider operations are temporarily unavailable.",
            "Keep using the platform storefront URL and retry later.",
            retryable=True,
        )

    @staticmethod
    def _owner_data(owner: Any) -> dict:
        if isinstance(owner, dict):
            return owner
        user_data = dict(getattr(owner, "user_data", None) or {})
        role = getattr(owner, "role", None)
        if role:
            user_data["role"] = role
        return user_data

    @classmethod
    def _owner_id(cls, owner: Any) -> str:
        user_data = cls._owner_data(owner)
        owner_id = normalize_planner_id(user_data.get("_id"))
        if not owner_id or not is_wedding_planner_role(user_data.get("role")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Planner-owner access required",
            )
        return owner_id

    async def _require_custom_domain(self, owner: Any):
        user_data = self._owner_data(owner)
        self._owner_id(user_data)
        try:
            entitlements = await self._entitlements.resolve_for_owner(user_data)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain eligibility is temporarily unavailable",
            ) from exc
        if not (entitlements.storefront_enabled and entitlements.custom_domain_enabled):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": "Custom Domain is not included in the current plan",
                    "feature": "custom_domain",
                    "upgrade_required": True,
                },
            )
        return entitlements

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _aware(value: object) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _error_detail(
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool,
        field: str | None = None,
        provider: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": code,
            "message": message,
            "customer_action": customer_action,
            "retryable": retryable,
            "support_id": f"sfd_{uuid4().hex[:16]}",
        }
        if field:
            result["field"] = field
        if provider:
            result["provider"] = provider
        return result

    @classmethod
    def _domain_http_error(
        cls,
        status_code: int,
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool = False,
        field: str | None = None,
        provider: dict[str, Any] | None = None,
    ) -> HTTPException:
        return HTTPException(
            status_code=status_code,
            detail=cls._error_detail(
                code,
                message,
                customer_action,
                retryable=retryable,
                field=field,
                provider=provider,
            ),
        )

    @staticmethod
    def _dns_provider(nameservers: list[str]) -> str:
        authority = " ".join(nameservers).lower()
        providers = (
            # Squarespace documents that its default nameservers may use the
            # googledomains.com suffix and that other companies share these
            # nameserver families. Do not send a customer to a single provider
            # console when the delegation itself cannot distinguish the host.
            ("squarespacedns.com", "squarespace_dns"),
            ("googledomains.com", "google_or_squarespace_dns"),
            ("cloudflare.com", "cloudflare"),
            ("awsdns-", "amazon_route53"),
            ("domaincontrol.com", "godaddy"),
            ("registrar-servers.com", "namecheap"),
            ("dnsowl.com", "namesilo"),
        )
        return next(
            (provider for marker, provider in providers if marker in authority),
            "unknown",
        )

    @staticmethod
    def _dns_provider_details(provider: str) -> tuple[str, str | None]:
        return _DNS_PROVIDER_DETAILS.get(
            provider,
            ("DNS provider not detected", None),
        )

    async def _query_dns(
        self,
        hostname: str,
        record_type: str,
        *,
        authoritative_nameservers: list[str] | None = None,
    ) -> list[str]:
        try:
            if authoritative_nameservers:
                return await self._dns_resolver.query_authoritative(
                    hostname, record_type, authoritative_nameservers
                )
            return await self._dns_resolver.query(hostname, record_type)
        except StorefrontDnsResolutionError as exc:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "dns_lookup_unavailable",
                "Authoritative DNS could not be checked right now.",
                "Wait a moment, then retry the DNS check.",
                retryable=True,
                provider={"name": "dns", "operation": record_type.lower()},
            ) from exc

    async def _authoritative_dns(
        self, hostname: str, exact_nameservers: list[str]
    ) -> tuple[str, list[str]]:
        if exact_nameservers:
            return hostname, sorted(set(exact_nameservers))
        labels = hostname.split(".")
        for offset in range(1, len(labels) - 1):
            candidate = ".".join(labels[offset:])
            nameservers = await self._query_dns(candidate, "NS")
            if nameservers:
                return candidate, sorted(set(nameservers))
        raise self._domain_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "authoritative_dns_not_found",
            "The authoritative DNS provider could not be identified.",
            "Confirm that the domain is registered and delegates to active nameservers.",
            retryable=True,
            field="domain",
        )

    async def _current_authoritative_dns(self, record: dict) -> dict[str, object]:
        """Read current public delegation independently from stored proof data."""

        try:
            return await discover_authoritative_dns_delegation(
                self._dns_resolver, record["hostname"]
            )
        except StorefrontDnsResolutionError as exc:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "dns_lookup_unavailable",
                "The current authoritative DNS delegation could not be checked.",
                "Wait a moment, then retry the DNS check.",
                retryable=True,
                provider={"name": "dns", "operation": "delegation"},
            ) from exc

    @staticmethod
    def _delegation_changed_error() -> dict[str, object]:
        return StorefrontDomainService._error_detail(
            "authoritative_dns_delegation_changed",
            "The domain's authoritative DNS provider changed during setup.",
            "Restart domain setup to generate a fresh ownership record for the current DNS provider.",
            retryable=False,
            field="domain",
        )

    async def _expire_domain_after_delegation_change(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
        current_authority: dict[str, object],
    ) -> dict:
        """Expire one exact claim without overwriting a refreshed snapshot."""

        stored_authority = record.get("authoritative_dns")
        now = self._now()
        result = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "claim_attempt_id": record.get("claim_attempt_id"),
                "revision": record.get("revision"),
                "authoritative_dns.zone": (
                    stored_authority.get("zone")
                    if isinstance(stored_authority, dict)
                    else None
                ),
                "authoritative_dns.nameservers": (
                    stored_authority.get("nameservers")
                    if isinstance(stored_authority, dict)
                    else None
                ),
                "provider_hostname_id": record.get("provider_hostname_id"),
                "deletion_status": record.get("deletion_status"),
            },
            {
                "$set": {
                    "application_status": EXPIRED,
                    "status": "pending",
                    "ownership_status": "expired",
                    "routing_dns_status": "mismatch",
                    "https_status": "pending",
                    "custom_route_enabled": False,
                    "action": "action_required",
                    "claim_expires_at": now,
                    "current_authoritative_dns": {
                        **current_authority,
                        "observed_at": now,
                    },
                    "last_checked_at": now,
                    "last_error": self._delegation_changed_error(),
                    "updated_at": now,
                },
                "$unset": {
                    "retry_due_at": "",
                    "lease_token": "",
                    "lease_expires_at": "",
                    "reconciliation_started_at": "",
                    "ownership_verification": "",
                    "ownership_verification_http": "",
                },
                "$inc": {"revision": 1},
            },
        )
        current = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if current:
            return current
        if not getattr(result, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "claim_changed",
                "The domain claim changed while DNS delegation was being checked.",
                "Reload custom-domain status before retrying.",
                retryable=True,
            )
        return record

    async def _expire_conflict_after_delegation_change(
        self,
        record: dict,
        owner_id: str,
        current_authority: dict[str, object],
    ) -> dict:
        """Expire only the claimant's exact conflict proof attempt."""

        stored_authority = record.get("authoritative_dns")
        now = self._now()
        claims = self._mongo.db["storefront_domain_conflict_claims"]
        result = await claims.update_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
                "attempt_id": record.get("attempt_id"),
                "revision": record.get("revision"),
                "current_owner_key": owner_id,
                "authoritative_dns.zone": (
                    stored_authority.get("zone")
                    if isinstance(stored_authority, dict)
                    else None
                ),
                "authoritative_dns.nameservers": (
                    stored_authority.get("nameservers")
                    if isinstance(stored_authority, dict)
                    else None
                ),
            },
            {
                "$set": {
                    "status": "expired",
                    "application_status": EXPIRED,
                    "ownership_status": "expired",
                    "action": "action_required",
                    "claim_expires_at": now,
                    "current_authoritative_dns": {
                        **current_authority,
                        "observed_at": now,
                    },
                    "last_checked_at": now,
                    "last_error": self._delegation_changed_error(),
                    "updated_at": now,
                },
                "$unset": {"current_owner_key": "", "retry_due_at": ""},
                "$inc": {"revision": 1},
            },
        )
        current = await claims.find_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
            }
        )
        if current:
            return current
        if not getattr(result, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "conflict_claim_changed",
                "The hostname ownership review changed while DNS delegation was checked.",
                "Reload custom-domain status before retrying.",
                retryable=True,
            )
        return record

    def _expected_records(
        self,
        hostname: str,
        token: str | None,
        *,
        include_routing: bool = True,
    ) -> list[dict]:
        records = [
            {
                "type": "TXT",
                "name": f"_tsw-storefront.{hostname}",
                "value": f"tsw-verification={token}" if token else None,
                "ttl": 300,
                "purpose": "application_ownership",
            }
        ]
        if include_routing:
            records.append(
                {
                    "type": "CNAME",
                    "name": hostname,
                    "value": self._cname_target,
                    "ttl": 300,
                    "purpose": "storefront_routing",
                }
            )
        return records

    def _decrypt_claim_token(self, record: dict) -> str | None:
        encrypted = record.get("claim_token_encrypted")
        expected_digest = record.get("claim_token_digest")
        if (
            not isinstance(encrypted, str)
            or not encrypted
            or not isinstance(expected_digest, str)
            or len(expected_digest) != 64
        ):
            return None
        try:
            token = self._claim_cipher.decrypt(encrypted.encode()).decode()
        except (InvalidToken, UnicodeDecodeError):
            return None
        actual_digest = hashlib.sha256(token.encode()).hexdigest()
        return token if secrets.compare_digest(actual_digest, expected_digest) else None

    async def preflight(
        self, owner: Any, raw_hostname: str, *, intent: str = "new"
    ) -> dict:
        """Inspect customer DNS without making any SaaS-provider mutation."""

        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        if intent not in {"new", "migration"}:
            raise self._domain_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_domain_intent",
                "Domain intent must be new or migration.",
                "Choose whether this is a new hostname or a live-site migration.",
                field="intent",
            )
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except ValueError as exc:
            raise self._domain_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_custom_domain",
                str(exc),
                "Enter a fully qualified customer hostname without a URL or path.",
                field="domain",
            ) from exc
        rollout_allowed = self._rollout_policy.allows(owner_id, hostname)
        if not self._cname_target:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "custom_domain_not_configured",
                "Custom-domain setup is temporarily unavailable.",
                "Keep using the platform storefront URL and contact support if this persists.",
                retryable=True,
            )

        exact_nameservers = await self._query_dns(hostname, "NS")
        zone, nameservers = await self._authoritative_dns(hostname, exact_nameservers)
        if zone == hostname:
            raise self._domain_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "apex_self_service_not_supported",
                "Apex domains are not supported by self-service setup.",
                "Use a subdomain such as www or contact support for an assisted apex migration.",
                field="domain",
            )

        observed: dict[str, list[str]] = {}
        for record_type in _DNS_RECORD_TYPES:
            observed_name = zone if record_type == "NS" else hostname
            observed[record_type] = await self._query_dns(
                observed_name,
                record_type,
                authoritative_nameservers=nameservers,
            )

        conflicts: list[dict] = []
        for record_type in ("A", "AAAA", "CNAME"):
            values = observed[record_type]
            if (
                record_type == "CNAME"
                and values
                and all(
                    value.rstrip(".").lower() == self._cname_target for value in values
                )
            ):
                continue
            if values:
                conflicts.append(
                    {
                        "code": "existing_routing_record",
                        "record_type": record_type,
                        "values": values,
                    }
                )

        dns_provider = self._dns_provider(nameservers)
        requires_assisted_o2o = intent == "migration" and dns_provider == "cloudflare"
        if requires_assisted_o2o:
            # Cloudflare explicitly does not support TXT/HTTP hostname
            # pre-validation for Orange-to-Orange custom hostnames. Treating
            # this as the normal zero-downtime migration flow could move live
            # traffic as soon as the SaaS hostname activates, before the
            # customer has approved a cutover. Return non-mutating discovery
            # evidence instead of an HTTP error so the customer can see the
            # detected provider, the exact risk, and the assisted next step.
            conflicts.append(
                {
                    "code": "cloudflare_o2o_migration_requires_assistance",
                    "record_type": "NS",
                    "values": nameservers,
                    "message": (
                        "Cloudflare-to-Cloudflare migration cannot be "
                        "prevalidated automatically. Keep the current routing "
                        "unchanged until support confirms a safe cutover."
                    ),
                }
            )

        discovery_service = self._domain_connect_discovery
        if discovery_service is None:
            from app.services.storefront_domain_connect_service import (
                domain_connect_discovery,
            )

            discovery_service = domain_connect_discovery
        try:
            domain_connect = await discovery_service.discover(zone)
        except Exception:
            domain_connect = {
                "supported": False,
                "reason_code": "discovery_unavailable",
            }
        automatic_setup_available = bool(
            rollout_allowed
            and not requires_assisted_o2o
            and domain_connect.get("supported") is True
            and intent == "new"
            and not conflicts
        )

        provider_name, control_panel_url = self._dns_provider_details(dns_provider)
        if automatic_setup_available and isinstance(
            domain_connect.get("control_panel_url"), str
        ):
            control_panel_url = domain_connect["control_panel_url"]

        return {
            "hostname": hostname,
            "host_type": "subdomain",
            "intent": intent,
            "authoritative_dns": {
                "zone": zone,
                "provider": dns_provider,
                "provider_name": provider_name,
                "control_panel_url": control_panel_url,
                "nameservers": nameservers,
            },
            "observed_records": [
                {
                    "type": record_type,
                    "name": zone if record_type == "NS" else hostname,
                    "values": values,
                }
                for record_type, values in observed.items()
            ],
            "conflicts": conflicts,
            "expected_records": self._expected_records(
                hostname,
                None,
                include_routing=intent != "migration",
            ),
            "domain_connect_supported": automatic_setup_available,
            "domain_connect_provider": domain_connect.get("provider_name"),
            # DNS delegation does not prove the registrar of record. Until a
            # bounded RDAP lookup is implemented, preserve this as explicitly
            # unknown rather than conflating DNS host and registrar.
            "registrar": "unknown",
            "platform_provider": "Cloudflare for The Special Wedding",
            "recommended_flow": (
                "manual"
                if not rollout_allowed
                else (
                    "automatic"
                    if automatic_setup_available
                    else (
                        "assisted_migration"
                        if intent == "migration" or conflicts
                        else "manual"
                    )
                )
            ),
            "self_service_allowed": rollout_allowed and not requires_assisted_o2o,
            "customer_action": (
                "Keep the current DNS record unchanged and request an assisted "
                "Cloudflare-to-Cloudflare cutover."
                if requires_assisted_o2o
                else (
                    "Keep using the platform storefront URL while custom-domain "
                    "onboarding is restricted to the production pilot."
                    if not rollout_allowed
                    else None
                )
            ),
        }

    def _new_claim_fields(
        self, hostname: str, *, revision: int, intent: str
    ) -> tuple[dict, str]:
        token = secrets.token_urlsafe(32)
        now = self._now()
        attempt_id = uuid4().hex
        return (
            {
                "status": "pending",
                "application_status": (
                    MIGRATION_PREVALIDATION
                    if intent == "migration"
                    else DNS_SETUP_PENDING
                ),
                "ownership_status": "pending",
                "provider_status": "not_created",
                "provider_hostname_status": "not_created",
                "ssl_status": "not_started",
                "routing_dns_status": "pending",
                "https_status": "pending",
                "action": "action_required",
                "provider_hostname_id": None,
                "ownership_verification": None,
                "ownership_verification_http": None,
                "ssl_validation_records": [],
                "claim_attempt_id": attempt_id,
                "claim_token_encrypted": self._claim_cipher.encrypt(
                    token.encode()
                ).decode(),
                "claim_token_digest": hashlib.sha256(token.encode()).hexdigest(),
                "claim_expires_at": now + _CLAIM_TTL,
                "revision": revision,
                "deletion_status": None,
                "last_error": None,
                "retry_due_at": None,
                "lease_expires_at": None,
                "updated_at": now,
            },
            token,
        )

    def _new_conflict_claim_record(
        self,
        *,
        owner_id: str,
        hostname: str,
        intent: str,
        preflight: dict,
    ) -> dict:
        """Create one independent proof attempt without copying reserved-owner data."""

        token = secrets.token_urlsafe(32)
        now = self._now()
        expires_at = now + _CLAIM_TTL
        return {
            "attempt_id": uuid4().hex,
            "claimant_planner_id": owner_id,
            # This unique, partial-indexed key permits one resumable conflict
            # journey per claimant while retaining previous attempts as
            # append-only evidence after expiry or cancellation.
            "current_owner_key": owner_id,
            "hostname": hostname,
            "intent": intent,
            "status": "pending",
            "application_status": DNS_SETUP_PENDING,
            "ownership_status": "pending",
            "provider_status": "not_created",
            "provider_hostname_status": "not_created",
            "ssl_status": "not_started",
            "routing_dns_status": "pending",
            "https_status": "pending",
            "action": "action_required",
            "conflict_code": "hostname_reserved",
            "authoritative_dns": preflight["authoritative_dns"],
            # Do not persist the reserved row, its owner, provider mapping, or
            # routing observations into a claimant-visible journey.
            "observed_records": [],
            "claim_token_encrypted": self._claim_cipher.encrypt(
                token.encode()
            ).decode(),
            "claim_token_digest": hashlib.sha256(token.encode()).hexdigest(),
            "claim_expires_at": expires_at,
            "purge_at": expires_at + _LIFECYCLE_RECEIPT_TTL,
            "revision": 1,
            "registrar": preflight.get("registrar") or "unknown",
            "platform_provider": "Cloudflare for The Special Wedding",
            "last_error": self._error_detail(
                "hostname_reserved",
                "This hostname is already reserved in the storefront platform.",
                "Publish the ownership TXT record to request a manual review without changing current traffic.",
                retryable=False,
                field="domain",
            ),
            "created_at": now,
            "updated_at": now,
        }

    def _conflict_expected_records(self, record: dict) -> list[dict]:
        token = self._decrypt_claim_token(record)
        if not token or record.get("application_status") in {EXPIRED, DISCONNECTED}:
            return []
        return [
            {
                "type": "TXT",
                "name": f"_tsw-storefront.{record['hostname']}",
                "value": f"tsw-conflict-verification={token}",
                "ttl": 300,
                "purpose": "conflict_ownership_review",
            }
        ]

    def _serialize_conflict_claim(self, record: dict) -> dict:
        expected_records = self._conflict_expected_records(record)
        observed_records = (
            [
                {
                    "type": "TXT",
                    "name": expected_records[0]["name"],
                    "values": [expected_records[0]["value"]],
                    "purpose": "conflict_ownership_review",
                }
            ]
            if expected_records and record.get("ownership_verified_at")
            else []
        )
        ownership_verification = None
        if expected_records:
            ownership_verification = {
                "type": "txt",
                "name": expected_records[0]["name"],
                "value": expected_records[0]["value"],
            }
        authority = record.get("authoritative_dns")
        if not (
            isinstance(authority, dict)
            and isinstance(authority.get("zone"), str)
            and isinstance(authority.get("provider"), str)
            and isinstance(authority.get("nameservers"), list)
        ):
            authority = None
        return {
            "hostname": record["hostname"],
            "status": self._status(record.get("status"), "pending"),
            "provider_status": "not_created",
            "ssl_status": "not_started",
            "application_status": record.get("application_status") or DNS_SETUP_PENDING,
            "ownership_status": self._status(record.get("ownership_status"), "pending"),
            "provider_hostname_status": "not_created",
            "routing_dns_status": "pending",
            "https_status": "pending",
            "action": self._status(record.get("action"), "action_required"),
            "provider_hostname_id": None,
            "attempt_id": record.get("attempt_id"),
            "revision": max(int(record.get("revision") or 0), 0),
            "claim_expires_at": record.get("claim_expires_at"),
            "intent": record.get("intent") or "new",
            "authoritative_dns": authority,
            "observed_records": observed_records,
            "conflicts": [],
            "cleanup_records": [],
            "domain_connect_supported": False,
            "domain_connect_provider": None,
            "registrar": record.get("registrar") or "unknown",
            "platform_provider": record.get("platform_provider")
            or "Cloudflare for The Special Wedding",
            "conflict_code": "hostname_reserved",
            "last_checked_at": record.get("last_checked_at"),
            "next_check_at": record.get("retry_due_at"),
            "expected_records": expected_records,
            "ownership_verification": ownership_verification,
            "ownership_verification_http": None,
            "ssl_validation_records": [],
            "cname_target": None,
            "deletion_status": None,
            "last_error": record.get("last_error"),
        }

    async def _expire_conflict_claim(self, record: dict, owner_id: str) -> None:
        now = self._now()
        await self._mongo.db["storefront_domain_conflict_claims"].update_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
                "attempt_id": record.get("attempt_id"),
                "revision": record.get("revision"),
                "current_owner_key": owner_id,
            },
            {
                "$set": {
                    "status": "expired",
                    "application_status": EXPIRED,
                    "ownership_status": "expired",
                    "action": "action_required",
                    "last_error": self._error_detail(
                        "domain_claim_expired",
                        "The hostname ownership challenge has expired.",
                        "Start the claim again to generate a fresh TXT value.",
                        retryable=False,
                    ),
                    "updated_at": now,
                },
                "$unset": {"current_owner_key": "", "retry_due_at": ""},
                "$inc": {"revision": 1},
            },
        )

    async def _claim_reserved_hostname(
        self,
        *,
        owner_id: str,
        hostname: str,
        intent: str,
        preflight: dict,
    ) -> dict:
        claims = self._mongo.db["storefront_domain_conflict_claims"]
        current = await claims.find_one({"current_owner_key": owner_id})
        if current:
            expires_at = self._aware(current.get("claim_expires_at"))
            already_verified = (
                current.get("application_status") == OPERATOR_REVIEW
                and current.get("ownership_status") == "verified"
            )
            if already_verified or (expires_at and expires_at > self._now()):
                if current.get("hostname") != hostname:
                    raise self._domain_http_error(
                        status.HTTP_409_CONFLICT,
                        "conflict_claim_already_active",
                        "Another hostname ownership review is already active for this storefront.",
                        "Cancel the current review before claiming a different hostname.",
                        field="domain",
                    )
                return self._serialize_conflict_claim(current)
            await self._expire_conflict_claim(current, owner_id)

        for _ in range(2):
            attempt = self._new_conflict_claim_record(
                owner_id=owner_id,
                hostname=hostname,
                intent=intent,
                preflight=preflight,
            )
            try:
                inserted = await claims.insert_one(attempt)
            except DuplicateKeyError:
                current = await claims.find_one({"current_owner_key": owner_id})
                if current and current.get("hostname") == hostname:
                    return self._serialize_conflict_claim(current)
                continue
            saved = await claims.find_one(
                {"_id": inserted.inserted_id, "claimant_planner_id": owner_id}
            )
            return self._serialize_conflict_claim(saved)

        raise self._domain_http_error(
            status.HTTP_409_CONFLICT,
            "conflict_claim_changed",
            "The hostname ownership review changed while it was being created.",
            "Reload custom-domain status before retrying.",
            retryable=True,
        )

    async def _conflict_claim_preflight(self, hostname: str) -> dict:
        """Collect only delegation data needed for a non-mutating conflict proof."""

        exact_nameservers = await self._query_dns(hostname, "NS")
        zone, nameservers = await self._authoritative_dns(hostname, exact_nameservers)
        dns_provider = self._dns_provider(nameservers)
        provider_name, control_panel_url = self._dns_provider_details(dns_provider)
        return {
            "authoritative_dns": {
                "zone": zone,
                "provider": dns_provider,
                "provider_name": provider_name,
                "control_panel_url": control_panel_url,
                "nameservers": nameservers,
            },
            "registrar": "unknown",
        }

    async def claim(
        self, owner: Any, raw_hostname: str, *, intent: str = "new"
    ) -> dict:
        """Create or resume an expiring manual ownership claim."""

        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        if intent not in {"new", "migration"}:
            raise self._domain_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_domain_intent",
                "Domain intent must be new or migration.",
                "Choose whether this is a new hostname or a live-site migration.",
                field="intent",
            )
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except ValueError as exc:
            raise self._domain_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_custom_domain",
                str(exc),
                "Enter a fully qualified customer hostname without a URL or path.",
                field="domain",
            ) from exc
        self._require_rollout(owner_id, hostname)
        collection = self._mongo.db["storefront_domains"]
        owned = await collection.find_one({"planner_id": owner_id})
        if owned and owned.get("hostname") != hostname:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "existing_custom_domain_must_be_disconnected",
                "This storefront already has a different custom-domain journey.",
                "Disconnect the current custom domain before claiming another hostname.",
                field="domain",
            )
        current_conflict = await self._mongo.db[
            "storefront_domain_conflict_claims"
        ].find_one({"current_owner_key": owner_id})
        if current_conflict:
            expires_at = self._aware(current_conflict.get("claim_expires_at"))
            already_verified = (
                current_conflict.get("application_status") == OPERATOR_REVIEW
                and current_conflict.get("ownership_status") == "verified"
            )
            if already_verified or (expires_at and expires_at > self._now()):
                if current_conflict.get("hostname") != hostname:
                    raise self._domain_http_error(
                        status.HTTP_409_CONFLICT,
                        "conflict_claim_already_active",
                        "Another hostname ownership review is already active for this storefront.",
                        "Cancel the current review before claiming a different hostname.",
                        field="domain",
                    )
                return self._serialize_conflict_claim(current_conflict)
            await self._expire_conflict_claim(current_conflict, owner_id)
        reserved = await collection.find_one({"hostname": hostname})
        if reserved and reserved.get("planner_id") != owner_id:
            conflict_preflight = await self._conflict_claim_preflight(hostname)
            return await self._claim_reserved_hostname(
                owner_id=owner_id,
                hostname=hostname,
                intent=intent,
                preflight=conflict_preflight,
            )

        preflight = await self.preflight(owner, raw_hostname, intent=intent)
        fields, _token = self._new_claim_fields(hostname, revision=1, intent=intent)
        now = self._now()
        record = {
            "planner_id": owner_id,
            "hostname": hostname,
            "provider": "cloudflare",
            "cname_target": self._cname_target,
            "intent": intent,
            "authoritative_dns": preflight["authoritative_dns"],
            "observed_records": preflight["observed_records"],
            "dns_conflicts": preflight["conflicts"],
            "domain_connect_supported": preflight["domain_connect_supported"],
            "domain_connect_provider": preflight.get("domain_connect_provider"),
            "registrar": preflight["registrar"],
            "platform_provider": preflight["platform_provider"],
            "created_at": now,
            **fields,
        }
        try:
            inserted = await collection.insert_one(record)
            saved = await collection.find_one(
                {"_id": inserted.inserted_id, "planner_id": owner_id}
            )
            return self._serialize(saved)
        except DuplicateKeyError as exc:
            reserved = await collection.find_one({"hostname": hostname})
            if reserved and reserved.get("planner_id") != owner_id:
                return await self._claim_reserved_hostname(
                    owner_id=owner_id,
                    hostname=hostname,
                    intent=intent,
                    preflight=preflight,
                )
            existing = reserved or await collection.find_one({"planner_id": owner_id})
            if not existing:
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "claim_changed",
                    "The custom-domain reservation changed while the claim was being created.",
                    "Reload custom-domain status before retrying.",
                    retryable=True,
                ) from exc
            if existing.get("hostname") != hostname:
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "existing_custom_domain_must_be_disconnected",
                    "This storefront already has a different custom-domain journey.",
                    "Disconnect the current custom domain before claiming another hostname.",
                    field="domain",
                ) from exc
            expires_at = self._aware(existing.get("claim_expires_at"))
            active_claim = expires_at and expires_at > self._now()
            if existing.get("provider_hostname_id") or active_claim:
                return self._serialize(existing)
            revision = int(existing.get("revision") or 0) + 1
            rotated, _token = self._new_claim_fields(
                hostname, revision=revision, intent=intent
            )
            result = await collection.update_one(
                {
                    "_id": existing["_id"],
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "revision": existing.get("revision"),
                    "provider_hostname_id": existing.get("provider_hostname_id"),
                },
                {
                    "$set": {
                        **rotated,
                        "intent": intent,
                        "authoritative_dns": preflight["authoritative_dns"],
                        "observed_records": preflight["observed_records"],
                        "dns_conflicts": preflight["conflicts"],
                        "domain_connect_supported": preflight[
                            "domain_connect_supported"
                        ],
                        "domain_connect_provider": preflight.get(
                            "domain_connect_provider"
                        ),
                        "registrar": preflight["registrar"],
                        "platform_provider": preflight["platform_provider"],
                    },
                    "$unset": {
                        "provider_create_attempt_id": "",
                        "provider_ids_before": "",
                        "provider_reconciliation_required": "",
                        "provisioning_unknown_at": "",
                    },
                },
            )
            if not getattr(result, "matched_count", 0):
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "claim_changed",
                    "The domain claim changed while it was being renewed.",
                    "Reload the domain status and retry.",
                    retryable=True,
                )
            saved = await collection.find_one(
                {"_id": existing["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

    @staticmethod
    def _provider_identity_rows(
        provider_rows: list[dict], hostname: str
    ) -> tuple[dict[str, dict], bool]:
        exact: dict[str, dict] = {}
        invalid = False
        for row in provider_rows:
            provider_id = row.get("id")
            try:
                provider_hostname = normalize_custom_hostname(
                    row.get("hostname"), platform_domains=()
                )
            except (TypeError, ValueError):
                provider_hostname = None
            if (
                provider_hostname != hostname
                or not isinstance(provider_id, str)
                or not provider_id.strip()
                or provider_id in exact
            ):
                invalid = True
                continue
            exact[provider_id] = row
        return exact, invalid

    @classmethod
    def _provider_row_created_within(
        cls,
        row: dict,
        *,
        started_at: object,
        observed_at: object,
    ) -> bool:
        started = cls._aware(started_at)
        observed = cls._aware(observed_at)
        raw_created = row.get("created_at")
        if isinstance(raw_created, str):
            try:
                created = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
            except ValueError:
                return False
            created = cls._aware(created)
        else:
            created = cls._aware(raw_created)
        if not started or not observed or not created:
            return False
        return (
            started - timedelta(minutes=1) <= created <= observed + timedelta(minutes=5)
        )

    async def _mark_operator_review(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
        attempt_id: str,
        error: dict,
    ) -> dict:
        now = self._now()
        await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "provider_create_attempt_id": attempt_id,
                "provider_hostname_id": None,
            },
            {
                "$set": {
                    "application_status": OPERATOR_REVIEW,
                    "status": "pending",
                    "provider_status": "unknown",
                    "provider_hostname_status": "unknown",
                    "provider_reconciliation_required": True,
                    "action": "operator_review",
                    "last_error": error,
                    "retry_due_at": now + timedelta(minutes=1),
                    "updated_at": now,
                },
                "$unset": {"lease_expires_at": ""},
            },
        )
        await self._mongo.db["storefront_domain_operations"].update_one(
            {"operation_id": attempt_id, "planner_id": owner_id},
            {
                "$set": {
                    "state": "operator_review",
                    "last_error": error,
                    "updated_at": now,
                }
            },
        )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved)

    async def _verify_conflict_claim(self, record: dict, owner_id: str) -> dict:
        """Observe only the claimant's TXT proof; never touch provider or routing."""

        claims = self._mongo.db["storefront_domain_conflict_claims"]
        if record.get("application_status") == DISCONNECTED:
            return self._serialize_conflict_claim(record)
        if (
            record.get("application_status") == OPERATOR_REVIEW
            and record.get("ownership_status") == "verified"
        ):
            return self._serialize_conflict_claim(record)

        expires_at = self._aware(record.get("claim_expires_at"))
        if not expires_at or expires_at <= self._now():
            await self._expire_conflict_claim(record, owner_id)
            saved = await claims.find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": record.get("attempt_id"),
                }
            )
            return self._serialize_conflict_claim(saved or record)

        token = self._decrypt_claim_token(record)
        if not token:
            error = self._error_detail(
                "claim_material_unavailable",
                "The hostname ownership challenge cannot be verified safely.",
                "Contact support with the displayed support ID.",
                retryable=False,
            )
            await claims.update_one(
                {
                    "_id": record["_id"],
                    "claimant_planner_id": owner_id,
                    "attempt_id": record.get("attempt_id"),
                    "revision": record.get("revision"),
                },
                {
                    "$set": {
                        "application_status": OPERATOR_REVIEW,
                        "action": "operator_review",
                        "last_error": error,
                        "updated_at": self._now(),
                    },
                    "$inc": {"revision": 1},
                },
            )
            saved = await claims.find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": record.get("attempt_id"),
                }
            )
            return self._serialize_conflict_claim(saved or record)

        authority = record.get("authoritative_dns")
        stored_delegation = normalize_authoritative_dns_snapshot(authority)
        if not stored_delegation:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "authoritative_dns_missing",
                "The authoritative DNS source for this ownership review is unavailable.",
                "Cancel this review and start a fresh hostname claim.",
                field="domain",
            )
        current_authority = await self._current_authoritative_dns(record)
        current_delegation = normalize_authoritative_dns_snapshot(current_authority)
        if current_delegation != stored_delegation:
            expired = await self._expire_conflict_after_delegation_change(
                record,
                owner_id,
                current_authority,
            )
            return self._serialize_conflict_claim(expired)
        nameservers = list(current_authority["nameservers"])

        txt_name = f"_tsw-storefront.{record['hostname']}"
        expected_txt = f"tsw-conflict-verification={token}"
        txt_values = await self._query_dns(
            txt_name,
            "TXT",
            authoritative_nameservers=nameservers,
        )
        confirmed_authority = await self._current_authoritative_dns(record)
        if (
            normalize_authoritative_dns_snapshot(confirmed_authority)
            != stored_delegation
        ):
            expired = await self._expire_conflict_after_delegation_change(
                record,
                owner_id,
                confirmed_authority,
            )
            return self._serialize_conflict_claim(expired)
        now = self._now()
        matched = expected_txt in txt_values
        if matched:
            application_status = OPERATOR_REVIEW
            ownership_status = "verified"
            action = "operator_review"
            error = self._error_detail(
                "hostname_conflict_requires_review",
                "Ownership proof was found, but this hostname remains reserved.",
                "Keep current DNS and traffic unchanged while support reviews the claim.",
                retryable=False,
            )
        else:
            application_status = DNS_SETUP_PENDING
            ownership_status = "pending"
            action = "action_required"
            error = self._error_detail(
                "conflict_dns_ownership_not_verified",
                "The current ownership TXT value was not found.",
                "Publish the exact current TXT value, then check again.",
                retryable=True,
                field="domain",
            )
        updated = await claims.update_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
                "attempt_id": record.get("attempt_id"),
                "revision": record.get("revision"),
                "current_owner_key": owner_id,
                "authoritative_dns.zone": authority.get("zone"),
                "authoritative_dns.nameservers": authority.get("nameservers"),
            },
            {
                "$set": {
                    "status": "pending",
                    "application_status": application_status,
                    "ownership_status": ownership_status,
                    "action": action,
                    "last_checked_at": now,
                    "last_error": error,
                    "updated_at": now,
                    **({"ownership_verified_at": now} if matched else {}),
                },
                "$unset": {"retry_due_at": ""},
                "$inc": {"revision": 1},
            },
        )
        if not getattr(updated, "matched_count", 0):
            current = await claims.find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": record.get("attempt_id"),
                }
            )
            if current:
                return self._serialize_conflict_claim(current)
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "conflict_claim_changed",
                "The hostname ownership review changed during verification.",
                "Reload custom-domain status before retrying.",
                retryable=True,
            )
        saved = await claims.find_one(
            {
                "claimant_planner_id": owner_id,
                "attempt_id": record.get("attempt_id"),
            }
        )
        return self._serialize_conflict_claim(saved)

    async def verify(
        self,
        owner: Any,
        attempt_id: str | None = None,
        *,
        _require_entitlement: bool = True,
        _allow_provider_mutations: bool = True,
    ) -> dict:
        """Independently verify the current TXT challenge before provider creation."""

        owner_id = self._owner_id(owner)
        if _require_entitlement:
            await self._require_custom_domain(owner)
        collection = self._mongo.db["storefront_domains"]
        if attempt_id:
            conflict = await self._mongo.db[
                "storefront_domain_conflict_claims"
            ].find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": attempt_id,
                }
            )
            if conflict:
                return await self._verify_conflict_claim(conflict, owner_id)
            record = await collection.find_one(
                {"planner_id": owner_id, "claim_attempt_id": attempt_id}
            )
        else:
            record = await collection.find_one({"planner_id": owner_id})
            if not record:
                conflict = await self._mongo.db[
                    "storefront_domain_conflict_claims"
                ].find_one({"current_owner_key": owner_id})
                if conflict:
                    return await self._verify_conflict_claim(conflict, owner_id)
        if not record:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found" if attempt_id else "domain_claim_not_found",
                (
                    "The custom-domain attempt could not be found."
                    if attempt_id
                    else "No custom-domain claim exists for this storefront."
                ),
                "Reload custom-domain status before verifying DNS."
                if attempt_id
                else "Start custom-domain setup before verifying DNS.",
            )
        if record.get("provider_hostname_id"):
            return self._serialize(record)

        expires_at = self._aware(record.get("claim_expires_at"))
        if not expires_at or expires_at <= self._now():
            error = self._error_detail(
                "domain_claim_expired",
                "The DNS ownership challenge has expired.",
                "Start the claim again to generate a fresh TXT value.",
                retryable=False,
            )
            await collection.update_one(
                {"_id": record["_id"], "planner_id": owner_id},
                {
                    "$set": {
                        "application_status": (
                            MIGRATION_PREVALIDATION
                            if record.get("intent") == "migration"
                            else DNS_SETUP_PENDING
                        ),
                        "ownership_status": "expired",
                        "action": "action_required",
                        "last_error": error,
                        "updated_at": self._now(),
                    }
                },
            )
            saved = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

        token = self._decrypt_claim_token(record)
        if not token:
            error = self._error_detail(
                "claim_material_unavailable",
                "The current DNS challenge cannot be verified safely.",
                "Restart the domain claim or contact support.",
                retryable=False,
            )
            attempt_id = record.get("provider_create_attempt_id") or uuid4().hex
            await collection.update_one(
                {"_id": record["_id"], "planner_id": owner_id},
                {
                    "$set": {
                        "provider_create_attempt_id": attempt_id,
                        "application_status": OPERATOR_REVIEW,
                        "action": "operator_review",
                        "last_error": error,
                        "updated_at": self._now(),
                    }
                },
            )
            saved = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

        expected_txt = f"tsw-verification={token}"
        txt_name = f"_tsw-storefront.{record['hostname']}"
        authority = record.get("authoritative_dns")
        stored_delegation = normalize_authoritative_dns_snapshot(authority)
        if not stored_delegation:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "authoritative_dns_missing",
                "The authoritative DNS source for this claim is unavailable.",
                "Restart domain setup before verifying DNS.",
                retryable=False,
            )
        current_authority = await self._current_authoritative_dns(record)
        current_delegation = normalize_authoritative_dns_snapshot(current_authority)
        if current_delegation != stored_delegation:
            expired = await self._expire_domain_after_delegation_change(
                collection,
                record,
                owner_id,
                current_authority,
            )
            return self._serialize(expired)
        nameservers = list(current_authority["nameservers"])
        txt_values = await self._query_dns(
            txt_name,
            "TXT",
            authoritative_nameservers=nameservers,
        )
        cname_values = await self._query_dns(
            record["hostname"],
            "CNAME",
            authoritative_nameservers=nameservers,
        )
        confirmed_authority = await self._current_authoritative_dns(record)
        if (
            normalize_authoritative_dns_snapshot(confirmed_authority)
            != stored_delegation
        ):
            expired = await self._expire_domain_after_delegation_change(
                collection,
                record,
                owner_id,
                confirmed_authority,
            )
            return self._serialize(expired)
        routing_status = (
            "verified"
            if any(
                value.rstrip(".").lower() == self._cname_target
                for value in cname_values
            )
            else ("conflict" if cname_values else "pending")
        )
        ownership_matched = expected_txt in txt_values
        observed_at = self._now()
        # Persist public DNS evidence, but never duplicate the current secret
        # ownership token in plaintext. `_serialize` adds that already-known
        # value back only for the authenticated owner after a successful proof.
        observed_records = [
            {
                "type": "TXT",
                "name": txt_name,
                "values": [value for value in txt_values if value != expected_txt],
                "purpose": "application_ownership",
            },
            {
                "type": "CNAME",
                "name": record["hostname"],
                "values": list(cname_values),
                "purpose": "storefront_routing",
            },
        ]
        observation_fields: dict[str, Any] = {
            "observed_records": observed_records,
            "last_checked_at": observed_at,
            "routing_dns_status": routing_status,
            "updated_at": observed_at,
        }
        if ownership_matched:
            observation_fields.update(
                {
                    "ownership_status": "verified",
                    "ownership_verified_at": observed_at,
                }
            )
        observation = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "revision": record.get("revision"),
                "claim_attempt_id": record.get("claim_attempt_id"),
                "authoritative_dns.zone": authority.get("zone"),
                "authoritative_dns.nameservers": authority.get("nameservers"),
                "deletion_status": None,
            },
            {"$set": observation_fields},
        )
        if not getattr(observation, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if current:
                return self._serialize(current)
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "claim_changed",
                "The domain claim changed while DNS was being observed.",
                "Reload custom-domain status before retrying.",
                retryable=True,
            )
        record = {**record, **observation_fields}
        if not ownership_matched:
            error = self._error_detail(
                "dns_ownership_not_verified",
                "The current ownership TXT value was not found.",
                "Publish the exact current TXT value, then retry verification.",
                retryable=True,
                field="domain",
            )
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "revision": record.get("revision"),
                    "claim_attempt_id": record.get("claim_attempt_id"),
                },
                {
                    "$set": {
                        "application_status": (
                            MIGRATION_PREVALIDATION
                            if record.get("intent") == "migration"
                            else DNS_SETUP_PENDING
                        ),
                        "ownership_status": "pending",
                        "action": "action_required",
                        "last_error": error,
                        "updated_at": observed_at,
                    }
                },
            )
            saved = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

        authority = record.get("authoritative_dns")
        assisted_o2o = bool(
            record.get("intent") == "migration"
            and isinstance(authority, dict)
            and authority.get("provider") == "cloudflare"
        )
        operator_approval = record.get("operator_assisted_cutover_approval")
        approved_assisted_o2o = bool(
            assisted_o2o
            and isinstance(operator_approval, dict)
            and isinstance(operator_approval.get("approval_id"), str)
            and operator_approval.get("claim_attempt_id")
            == record.get("claim_attempt_id")
            and operator_approval.get("approved_revision") == record.get("revision")
            and operator_approval.get("consumed_at") is None
        )
        requires_assisted_o2o = assisted_o2o and not approved_assisted_o2o
        if requires_assisted_o2o:
            # Creating an O2O custom hostname can affect existing proxied
            # traffic before a customer-controlled CNAME cutover exists.
            # Ownership proof is safe and useful; provider creation is not.
            # Pause with durable evidence for an operator-assisted cutover.
            error = self._error_detail(
                "cloudflare_o2o_migration_requires_assistance",
                "Ownership is verified and the existing Cloudflare route remains unchanged.",
                "Request an assisted cutover before changing DNS routing.",
                retryable=False,
                field="domain",
            )
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "revision": record.get("revision"),
                    "claim_attempt_id": record.get("claim_attempt_id"),
                    "provider_hostname_id": None,
                },
                {
                    "$set": {
                        "application_status": OPERATOR_REVIEW,
                        "action": "operator_review",
                        "provider_status": "not_created",
                        "provider_hostname_status": "not_created",
                        "last_error": error,
                        "updated_at": self._now(),
                    },
                    "$unset": {
                        "provider_create_attempt_id": "",
                        "provider_ids_before": "",
                        "lease_expires_at": "",
                    },
                },
            )
            saved = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

        if not _allow_provider_mutations:
            # Reconciliation may refresh owner-visible DNS diagnostics after an
            # entitlement is lost, but a background observation must never
            # create or retry a provider hostname. Activation remains an
            # explicit, currently-entitled owner action.
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "revision": record.get("revision"),
                    "claim_attempt_id": record.get("claim_attempt_id"),
                    "provider_hostname_id": None,
                    "deletion_status": None,
                },
                {
                    "$set": {
                        "application_status": (
                            MIGRATION_PREVALIDATION
                            if record.get("intent") == "migration"
                            else DNS_SETUP_PENDING
                        ),
                        "action": "action_required",
                        "last_error": None,
                        "updated_at": self._now(),
                    }
                },
            )
            saved = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize(saved)

        try:
            self._require_provider_mutations(owner_id, record["hostname"])
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else None
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "revision": record.get("revision"),
                    "claim_attempt_id": record.get("claim_attempt_id"),
                    "deletion_status": None,
                },
                {
                    "$set": {
                        "application_status": PROVIDER_PROVISIONING,
                        "action": "action_required",
                        "last_error": detail,
                        "updated_at": self._now(),
                    }
                },
            )
            raise
        try:
            provider_rows_before = await self._cloudflare.list_custom_hostnames(
                record["hostname"]
            )
        except CloudflareServiceError as exc:
            raise self._provider_http_error(exc) from exc
        rows_before, invalid_before = self._provider_identity_rows(
            provider_rows_before, record["hostname"]
        )
        if invalid_before:
            raise self._domain_http_error(
                status.HTTP_502_BAD_GATEWAY,
                "invalid_provider_snapshot",
                "The existing provider state could not be verified safely.",
                "Contact support before retrying this domain.",
                retryable=False,
                provider={"name": "cloudflare", "operation": "list_custom_hostnames"},
            )

        attempt_id = uuid4().hex
        now = self._now()
        request_window_ends_at = now + timedelta(
            seconds=PROVIDER_CREATE_REQUEST_WINDOW_SECONDS
        )
        operation = {
            "operation_id": attempt_id,
            "domain_id": str(record["_id"]),
            "attempt_id": attempt_id,
            "kind": "provider_create",
            "planner_id": owner_id,
            "hostname": record["hostname"],
            "state": "prepared",
            "provider_ids_before": sorted(rows_before),
            "provider_request_started_at": now,
            "provider_request_window_ends_at": request_window_ends_at,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + _LIFECYCLE_RECEIPT_TTL,
        }
        operations = self._mongo.db["storefront_domain_operations"]
        await operations.insert_one(operation)
        claimed = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "revision": record.get("revision"),
                "claim_attempt_id": record.get("claim_attempt_id"),
                "provider_hostname_id": None,
                "ownership_status": "verified",
                **(
                    {
                        "operator_assisted_cutover_approval.approval_id": operator_approval[
                            "approval_id"
                        ],
                        "operator_assisted_cutover_approval.consumed_at": None,
                    }
                    if approved_assisted_o2o
                    else {}
                ),
            },
            {
                "$set": {
                    "ownership_status": "verified",
                    "routing_dns_status": routing_status,
                    "application_status": PROVIDER_PROVISIONING,
                    "provider_status": "provisioning",
                    "provider_hostname_status": "provisioning",
                    "action": "processing",
                    "provider_create_attempt_id": attempt_id,
                    "provider_ids_before": sorted(rows_before),
                    "last_error": None,
                    "lease_expires_at": now + timedelta(minutes=10),
                    "updated_at": now,
                    **(
                        {
                            "operator_assisted_cutover_approval.consumed_at": now,
                            "operator_assisted_cutover_approval.consumed_by_provider_attempt_id": attempt_id,
                        }
                        if approved_assisted_o2o
                        else {}
                    ),
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(claimed, "matched_count", 0):
            await operations.update_one(
                {"operation_id": attempt_id},
                {"$set": {"state": "cancelled", "updated_at": self._now()}},
            )
            current = await collection.find_one({"planner_id": owner_id})
            if current:
                return self._serialize(current)
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "claim_changed",
                "The domain claim changed during verification.",
                "Reload status before retrying.",
                retryable=True,
            )
        await operations.update_one(
            {"operation_id": attempt_id},
            {"$set": {"state": "creating", "updated_at": self._now()}},
        )

        provider_result: dict | None = None
        try:
            provider_result = await self._cloudflare.create_custom_hostname(
                record["hostname"]
            )
        except CloudflareServiceError as exc:
            if self._create_failure_is_definitive(exc):
                error = self._error_detail(
                    "provider_create_rejected",
                    "The custom-domain provider rejected this hostname.",
                    "Review the DNS records and retry, or contact support.",
                    retryable=False,
                    provider={
                        "name": "cloudflare",
                        "operation": "create_custom_hostname",
                        "status_code": exc.provider_status_code,
                    },
                )
                await collection.update_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "provider_create_attempt_id": attempt_id,
                    },
                    {
                        "$set": {
                            "application_status": DNS_SETUP_PENDING,
                            "provider_status": "rejected",
                            "provider_hostname_status": "rejected",
                            "action": "action_required",
                            "last_error": error,
                            "updated_at": self._now(),
                        },
                        "$unset": {"lease_expires_at": ""},
                    },
                )
                await operations.update_one(
                    {"operation_id": attempt_id},
                    {"$set": {"state": "failed", "last_error": error}},
                )
                saved = await collection.find_one({"planner_id": owner_id})
                return self._serialize(saved)
            provider_outcome_unknown_at = min(self._now(), request_window_ends_at)
            await operations.update_one(
                {
                    "operation_id": attempt_id,
                    "planner_id": owner_id,
                    "state": "creating",
                },
                {
                    "$set": {
                        "provider_outcome_unknown_at": provider_outcome_unknown_at,
                        "updated_at": self._now(),
                    }
                },
            )
            try:
                provider_rows_after = await self._cloudflare.list_custom_hostnames(
                    record["hostname"]
                )
            except CloudflareServiceError:
                provider_rows_after = []
            rows_after, invalid_after = self._provider_identity_rows(
                provider_rows_after, record["hostname"]
            )
            new_ids = set(rows_after) - set(rows_before)
            if not invalid_after and len(new_ids) == 1:
                candidate = rows_after[new_ids.pop()]
                if self._provider_row_created_within(
                    candidate,
                    started_at=now,
                    observed_at=self._now(),
                ):
                    provider_result = candidate
            else:
                error = self._error_detail(
                    "ambiguous_provider_create",
                    "The provider create outcome cannot be proven automatically.",
                    "Do not retry or remove DNS; support must reconcile this attempt.",
                    retryable=False,
                    provider={
                        "name": "cloudflare",
                        "operation": "create_custom_hostname",
                    },
                )
                current = await collection.find_one(
                    {"_id": record["_id"], "planner_id": owner_id}
                )
                return await self._mark_operator_review(
                    collection, current, owner_id, attempt_id, error
                )

        provider_id = provider_result.get("id") if provider_result else None
        try:
            provider_hostname = normalize_custom_hostname(
                provider_result.get("hostname") if provider_result else None,
                platform_domains=self._platform_domains,
            )
        except (TypeError, ValueError):
            provider_hostname = None
        if (
            not isinstance(provider_id, str)
            or not provider_id.strip()
            or provider_hostname != record["hostname"]
            or provider_id in rows_before
        ):
            error = self._error_detail(
                "invalid_provider_create_result",
                "The provider returned a mapping that cannot be bound safely.",
                "Do not retry; contact support with the displayed support ID.",
                retryable=False,
                provider={"name": "cloudflare", "operation": "create_custom_hostname"},
            )
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return await self._mark_operator_review(
                collection, current, owner_id, attempt_id, error
            )

        projection = self._provider_projection(provider_result)
        if (
            record.get("intent") == "migration"
            and projection["provider_status"] == "active"
            and projection["ssl_status"] == "active"
        ):
            application_status = CUTOVER_READY
        else:
            application_status = (
                CERTIFICATE_VALIDATION
                if projection["provider_status"] == "active"
                else HOSTNAME_VALIDATION
            )
        persisted_at = self._now()
        persisted = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "provider_create_attempt_id": attempt_id,
                "provider_hostname_id": None,
            },
            {
                "$set": {
                    "provider_hostname_id": provider_id,
                    "provider_ssl_method": "txt",
                    "provider_ssl_type": "dv",
                    **projection,
                    "application_status": application_status,
                    "provider_hostname_status": projection["provider_status"],
                    "https_status": "pending",
                    "action": (
                        "action_required"
                        if application_status == CUTOVER_READY
                        else "processing"
                    ),
                    **(
                        {"migration_cutover_ready_at": persisted_at}
                        if application_status == CUTOVER_READY
                        else {}
                    ),
                    "last_error": None,
                    "retry_due_at": persisted_at,
                    "updated_at": persisted_at,
                },
                "$unset": {
                    "lease_expires_at": "",
                    "provider_reconciliation_required": "",
                },
            },
        )
        if not getattr(persisted, "matched_count", 0):
            await self._compensate_failed_create(
                collection,
                reservation_id=record["_id"],
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The verified provider mapping could not be persisted",
            )
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_mapping_not_persisted",
                "The provider mapping could not be saved safely.",
                "Contact support before retrying.",
                retryable=True,
            )
        await operations.update_one(
            {"operation_id": attempt_id, "planner_id": owner_id},
            {
                "$set": {
                    "state": "completed",
                    "provider_hostname_id": provider_id,
                    "updated_at": self._now(),
                }
            },
        )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved)

    async def observe_pending_for_owner_id(
        self, planner_id: str, attempt_id: str | None = None
    ) -> dict:
        """Refresh pending DNS evidence without entitlement or provider mutation.

        This is an internal worker entry point. It accepts only a canonical
        planner owner ID, retains owner-scoped queries, and deliberately cannot
        create a Cloudflare hostname even when DNS proof has propagated.
        """

        owner_id = normalize_planner_id(planner_id)
        if not owner_id:
            raise self._domain_http_error(
                status.HTTP_400_BAD_REQUEST,
                "invalid_storefront_owner",
                "The custom-domain owner could not be identified.",
                "Contact support with the current domain support ID.",
                retryable=False,
            )
        return await self.verify(
            {"_id": owner_id, "role": "wedding_planner"},
            attempt_id,
            _require_entitlement=False,
            _allow_provider_mutations=False,
        )

    async def get_status(
        self, owner: Any, attempt_id: str | None = None
    ) -> dict | None:
        """Return durable owner state without DNS or provider I/O."""

        owner_id = self._owner_id(owner)
        domain_query: dict[str, Any] = {"planner_id": owner_id}
        if attempt_id:
            domain_query["claim_attempt_id"] = attempt_id
        record = await self._mongo.db["storefront_domains"].find_one(domain_query)
        if record:
            return self._serialize(record)
        conflict_query = (
            {"claimant_planner_id": owner_id, "attempt_id": attempt_id}
            if attempt_id
            else {"current_owner_key": owner_id}
        )
        conflict = await self._mongo.db["storefront_domain_conflict_claims"].find_one(
            conflict_query
        )
        if conflict:
            expires_at = self._aware(conflict.get("claim_expires_at"))
            challenge_active = conflict.get("application_status") not in {
                OPERATOR_REVIEW,
                DISCONNECTED,
                EXPIRED,
            }
            if (
                challenge_active
                and expires_at
                and expires_at <= self._now()
                and conflict.get("current_owner_key") == owner_id
            ):
                await self._expire_conflict_claim(conflict, owner_id)
                conflict = await self._mongo.db[
                    "storefront_domain_conflict_claims"
                ].find_one({"_id": conflict["_id"]})
            return self._serialize_conflict_claim(conflict)
        if attempt_id:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found",
                "The custom-domain attempt could not be found.",
                "Reload custom-domain status before trying again.",
            )
        tombstone = await self._mongo.db["storefront_domain_tombstones"].find_one(
            {"planner_id": owner_id},
            sort=[("deleted_at", -1)],
        )
        if not tombstone:
            return None
        return {
            "hostname": tombstone["hostname"],
            "status": "provider_deleted",
            "provider_status": "deleted",
            "ssl_status": "inactive",
            "application_status": DISCONNECTED,
            "ownership_status": "disconnected",
            "provider_hostname_status": "deleted",
            "routing_dns_status": "disconnected",
            "https_status": "disconnected",
            "action": "remove_dns_records",
            "provider_hostname_id": tombstone.get("provider_hostname_id"),
            "attempt_id": None,
            "revision": 0,
            "claim_expires_at": None,
            "intent": "new",
            "authoritative_dns": None,
            "observed_records": [],
            "conflicts": [],
            "cleanup_records": list(tombstone.get("cleanup_records") or []),
            "domain_connect_supported": False,
            "domain_connect_provider": None,
            "registrar": tombstone.get("registrar") or "unknown",
            "platform_provider": "Cloudflare for The Special Wedding",
            "conflict_code": None,
            "last_checked_at": tombstone.get("deleted_at"),
            "next_check_at": None,
            "expected_records": [],
            "ownership_verification": None,
            "ownership_verification_http": None,
            "ssl_validation_records": [],
            "cname_target": tombstone.get("cname_target") or self._cname_target,
            "deletion_status": "completed",
            "last_error": None,
        }

    async def observe(self, owner: Any, attempt_id: str) -> dict | None:
        """Enqueue an owner-scoped read-only evidence refresh.

        This is intentionally distinct from ``retry_provider``: it does not
        PATCH Cloudflare or restart validation. It only makes the existing row
        due for the leased reconciler, which performs DNS and provider reads.
        """

        owner_id = self._owner_id(owner)
        collection = self._mongo.db["storefront_domains"]
        record = await collection.find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            conflict = await self._mongo.db[
                "storefront_domain_conflict_claims"
            ].find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": attempt_id,
                }
            )
            if conflict:
                return await self._verify_conflict_claim(conflict, owner_id)
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found",
                "The current custom-domain attempt could not be found.",
                "Reload domain status before checking again.",
            )
        if self._has_deletion_intent(record):
            return self._serialize(record)

        now = self._now()
        last_requested = self._aware(record.get("observation_requested_at"))
        if last_requested and now - last_requested < timedelta(seconds=15):
            return self._serialize(record)
        queued = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "claim_attempt_id": attempt_id,
                "revision": record.get("revision"),
                "deletion_status": record.get("deletion_status"),
            },
            {
                "$set": {
                    "observation_requested_at": now,
                    "retry_due_at": now,
                    "updated_at": now,
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(queued, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_observation_changed",
                "The custom-domain state changed while scheduling a check.",
                "Reload domain status before checking again.",
                retryable=True,
            )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved) if saved else None

    async def retry_provider(self, owner: Any, attempt_id: str) -> dict:
        """Request Cloudflare's documented no-change validation retry."""

        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        collection = self._mongo.db["storefront_domains"]
        record = await collection.find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found",
                "The current custom-domain attempt could not be found.",
                "Reload domain status before retrying.",
            )
        self._require_provider_mutations(owner_id, record["hostname"])

        provider_id = record.get("provider_hostname_id")
        ssl_method = record.get("provider_ssl_method")
        ssl_type = record.get("provider_ssl_type")
        if (
            not isinstance(provider_id, str)
            or not provider_id.strip()
            or ssl_method not in {"txt", "http", "email"}
            or ssl_type != "dv"
        ):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "custom_domain_retry_unavailable",
                "The provider mapping has no safe retry configuration.",
                "Reload status or contact support before retrying.",
            )

        now = self._now()
        last_retry = self._aware(record.get("provider_retry_requested_at"))
        if last_retry and now - last_retry < _PROVIDER_RETRY_THROTTLE:
            raise self._domain_http_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "custom_domain_retry_throttled",
                "A provider validation retry was requested recently.",
                "Wait five minutes before requesting another retry.",
                retryable=True,
            )

        operation_id = f"cfr_{uuid4().hex}"
        operation = {
            "operation_id": operation_id,
            "domain_id": str(record["_id"]),
            "attempt_id": operation_id,
            "kind": "provider_retry",
            "planner_id": owner_id,
            "provider_hostname_id": provider_id,
            "ssl_method": ssl_method,
            "ssl_type": ssl_type,
            "state": "prepared",
            "created_at": now,
            "updated_at": now,
            "expires_at": now + _LIFECYCLE_RECEIPT_TTL,
        }
        operations = self._mongo.db["storefront_domain_operations"]
        await operations.insert_one(operation)

        was_routable = bool(
            record.get("application_status") == ACTIVE
            and record.get("ownership_status") == "verified"
            and record.get("routing_dns_status") == "verified"
            and record.get("provider_hostname_status") == "active"
            and record.get("ssl_status") == "active"
            and record.get("https_status") == "verified"
        )
        phase = (
            DEPLOYING
            if was_routable
            else (
                CERTIFICATE_VALIDATION
                if record.get("provider_hostname_status") == "active"
                else HOSTNAME_VALIDATION
            )
        )
        reserved = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "claim_attempt_id": attempt_id,
                "revision": record.get("revision"),
                "provider_hostname_id": provider_id,
                "provider_retry_requested_at": record.get(
                    "provider_retry_requested_at"
                ),
            },
            {
                "$set": {
                    "application_status": phase,
                    "action": "processing",
                    "provider_retry_requested_at": now,
                    "provider_retry_operation_id": operation_id,
                    "retry_due_at": now,
                    "last_error": None,
                    "updated_at": now,
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(reserved, "matched_count", 0):
            await operations.update_one(
                {"operation_id": operation_id, "state": "prepared"},
                {"$set": {"state": "cancelled", "updated_at": self._now()}},
            )
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "custom_domain_retry_changed",
                "The custom-domain state changed while retrying.",
                "Reload status before retrying again.",
                retryable=True,
            )

        await operations.update_one(
            {"operation_id": operation_id, "state": "prepared"},
            {"$set": {"state": "requesting", "updated_at": self._now()}},
        )
        try:
            provider_result = await self._cloudflare.retry_custom_hostname(
                provider_id,
                ssl_method=ssl_method,
                ssl_type=ssl_type,
            )
        except CloudflareServiceError as exc:
            error = self._error_detail(
                "provider_retry_failed",
                "The custom-domain provider could not start validation again.",
                "Wait five minutes and retry, or contact support.",
                retryable=True,
                provider={
                    "name": "cloudflare",
                    "operation": "retry_custom_hostname",
                    "status_code": exc.provider_status_code,
                },
            )
            await operations.update_one(
                {"operation_id": operation_id},
                {
                    "$set": {
                        "state": "failed",
                        "last_error": error,
                        "updated_at": self._now(),
                    }
                },
            )
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "provider_retry_operation_id": operation_id,
                },
                {
                    "$set": {
                        "action": "action_required",
                        "last_error": error,
                        "retry_due_at": now + _PROVIDER_RETRY_THROTTLE,
                        "updated_at": self._now(),
                    }
                },
            )
            raise self._provider_http_error(exc) from exc

        await operations.update_one(
            {"operation_id": operation_id},
            {
                "$set": {
                    "state": "completed",
                    "provider_observation": provider_result,
                    "updated_at": self._now(),
                }
            },
        )
        await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "provider_retry_operation_id": operation_id,
            },
            {
                "$set": {
                    "provider_last_observation": provider_result,
                    "provider_last_observed_at": self._now(),
                    "last_error": None,
                    "updated_at": self._now(),
                }
            },
        )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved)

    def _instruction_link_url(self, token: str) -> str:
        parsed = urlparse(str(self._instruction_public_base_url or ""))
        try:
            port = parsed.port
        except ValueError as exc:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_instruction_link_unavailable",
                "Secure DNS instruction links are not configured.",
                "Copy the records manually and contact support.",
                retryable=True,
            ) from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_instruction_link_unavailable",
                "Secure DNS instruction links are not configured.",
                "Copy the records manually and contact support.",
                retryable=True,
            )
        origin = f"https://{parsed.hostname}"
        return f"{origin}/domain-instructions/{token}"

    def _instruction_link_summary(self, link: dict[str, Any]) -> dict[str, Any]:
        created_at = self._aware(link.get("created_at"))
        expires_at = self._aware(link.get("expires_at"))
        delivery_state = link.get("delivery_state")
        receipt_state = (
            "delivery_failed"
            if delivery_state == "failed"
            else (
                "delivery_pending"
                if delivery_state in {"pending", "sending"}
                else "active"
            )
        )
        return {
            "link_id": link.get("link_id"),
            "state": receipt_state,
            "created_at": created_at,
            "expires_at": expires_at,
            "recipient_hint": link.get("recipient_hint") or "masked recipient",
        }

    async def _acquire_instruction_quotas(
        self,
        quota_specs: list[tuple[str, int, datetime]],
    ) -> list[str]:
        """Atomically acquire bounded counters, rolling back partial acquisition."""

        quotas = self._mongo.db["storefront_domain_instruction_quotas"]
        acquired: list[str] = []
        for quota_key, limit, expires_at in quota_specs:
            try:
                result = await quotas.update_one(
                    {"quota_key": quota_key, "count": {"$lt": limit}},
                    {
                        "$inc": {"count": 1},
                        "$setOnInsert": {
                            "quota_key": quota_key,
                            "created_at": self._now(),
                            "expires_at": expires_at,
                        },
                    },
                    upsert=True,
                )
            except DuplicateKeyError:
                result = None
            if result is None or not (
                getattr(result, "matched_count", 0)
                or getattr(result, "upserted_id", None) is not None
            ):
                await self._release_instruction_quotas(acquired)
                raise self._domain_http_error(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "domain_instruction_send_rate_limited",
                    "DNS instruction delivery is temporarily limited.",
                    "Wait until the next delivery window or copy the records manually.",
                    retryable=True,
                )
            acquired.append(quota_key)
        return acquired

    async def _release_instruction_quotas(self, quota_keys: Iterable[str]) -> None:
        quotas = self._mongo.db["storefront_domain_instruction_quotas"]
        for quota_key in quota_keys:
            await quotas.update_one(
                {"quota_key": quota_key, "count": {"$gt": 0}},
                {"$inc": {"count": -1}},
            )

    async def list_instruction_links(
        self,
        owner: Any,
        attempt_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """List bounded active receipts for one exact owner-scoped attempt."""

        owner_id = self._owner_id(owner)
        record = await self._mongo.db["storefront_domains"].find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found",
                "The current custom-domain attempt could not be found.",
                "Reload domain status before managing instruction links.",
            )
        # Public instruction reads fail closed from the moment disconnect intent
        # is reserved. The authenticated receipt list must never keep calling the
        # same link active while the public reader correctly rejects it, including
        # when provider cleanup later enters a retryable failure state.
        if self._has_deletion_intent(record):
            return {"links": []}
        now = self._now()
        cursor = self._mongo.db["storefront_domain_instruction_links"].find(
            {
                "planner_id": owner_id,
                "domain_id": str(record["_id"]),
                "claim_attempt_id": attempt_id,
                "state": "active",
                "expires_at": {"$gt": now},
            }
        )
        cursor = cursor.sort("created_at", -1).limit(_INSTRUCTION_LINK_LIST_LIMIT)
        links = await cursor.to_list(length=_INSTRUCTION_LINK_LIST_LIMIT)
        return {
            "links": [
                self._instruction_link_summary(link)
                for link in links
                if isinstance(link.get("link_id"), str)
                and self._aware(link.get("created_at")) is not None
                and self._aware(link.get("expires_at")) is not None
            ]
        }

    async def send_instructions(
        self,
        owner: Any,
        attempt_id: str,
        *,
        email: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Send the exact current owner-scoped DNS records to a DNS contact."""

        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        record = await self._mongo.db["storefront_domains"].find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_attempt_not_found",
                "The current custom-domain attempt could not be found.",
                "Reload domain status before sending instructions.",
            )
        serialized = self._serialize(record)
        expected_records = [
            item
            for item in serialized.get("expected_records", [])
            if isinstance(item, dict)
            and isinstance(item.get("type"), str)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("value"), str)
            and item.get("value")
        ]
        if not expected_records:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_instructions_unavailable",
                "The current DNS instructions are not available.",
                "Restart domain setup or contact support.",
            )
        # Fail before reserving a token, quota, or delivery lease when the
        # first-party read-only link origin is not configured safely.
        self._instruction_link_url("x" * 43)

        normalized_email = email.strip().casefold()
        recipient_hash = hashlib.sha256(normalized_email.encode()).hexdigest()
        recipient_hint = _mask_instruction_recipient(normalized_email)
        operations = self._mongo.db["storefront_domain_operations"]
        links = self._mongo.db["storefront_domain_instruction_links"]
        link_filter = {
            "domain_id": str(record["_id"]),
            "claim_attempt_id": attempt_id,
            "recipient_hash": recipient_hash,
        }
        existing_link = await links.find_one(link_filter)
        now = self._now()
        existing_expiry = (
            self._aware(existing_link.get("expires_at")) if existing_link else None
        )
        if (
            existing_link
            and existing_link.get("state") == "active"
            and existing_expiry
            and existing_expiry > now
            and existing_link.get("delivery_state") == "completed"
        ):
            return {"status": "sent", **self._instruction_link_summary(existing_link)}
        existing_lease_expiry = (
            self._aware(existing_link.get("delivery_lease_expires_at"))
            if existing_link
            else None
        )
        if (
            existing_link
            and existing_link.get("state") == "active"
            and existing_expiry
            and existing_expiry > now
            and existing_link.get("delivery_state") == "sending"
            and existing_lease_expiry
            and existing_lease_expiry > now
        ):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_instructions_delivery_in_progress",
                "DNS instructions are already being delivered to this recipient.",
                "Wait a moment, then reload the active instruction links.",
                retryable=True,
            )

        quota_bucket = int(now.timestamp()) // int(
            _INSTRUCTION_QUOTA_WINDOW.total_seconds()
        )
        quota_expiry = datetime.fromtimestamp(
            (quota_bucket + 2) * int(_INSTRUCTION_QUOTA_WINDOW.total_seconds()),
            tz=timezone.utc,
        )
        hourly_quota_keys = await self._acquire_instruction_quotas(
            [
                (
                    f"instruction:owner:{owner_id}:{quota_bucket}",
                    _INSTRUCTION_OWNER_SEND_LIMIT,
                    quota_expiry,
                ),
                (
                    f"instruction:attempt:{owner_id}:{record['_id']}:{attempt_id}:{quota_bucket}",
                    _INSTRUCTION_ATTEMPT_SEND_LIMIT,
                    quota_expiry,
                ),
                (
                    f"instruction:recipient:{owner_id}:{recipient_hash}:{quota_bucket}",
                    _INSTRUCTION_RECIPIENT_SEND_LIMIT,
                    quota_expiry,
                ),
            ]
        )

        # Close the find/reserve race before deciding whether a new link token is
        # required. Concurrent calls must converge on one link and one provider
        # idempotency key.
        existing_link = await links.find_one(link_filter)
        existing_expiry = (
            self._aware(existing_link.get("expires_at")) if existing_link else None
        )
        if (
            existing_link
            and existing_link.get("state") == "active"
            and existing_expiry
            and existing_expiry > now
            and existing_link.get("delivery_state") == "completed"
        ):
            await self._release_instruction_quotas(hourly_quota_keys)
            return {"status": "sent", **self._instruction_link_summary(existing_link)}
        existing_lease_expiry = (
            self._aware(existing_link.get("delivery_lease_expires_at"))
            if existing_link
            else None
        )
        if (
            existing_link
            and existing_link.get("state") == "active"
            and existing_expiry
            and existing_expiry > now
            and existing_link.get("delivery_state") == "sending"
            and existing_lease_expiry
            and existing_lease_expiry > now
        ):
            await self._release_instruction_quotas(hourly_quota_keys)
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_instructions_delivery_in_progress",
                "DNS instructions are already being delivered to this recipient.",
                "Wait a moment, then reload the active instruction links.",
                retryable=True,
            )

        claim_expiry = self._aware(record.get("claim_expires_at"))
        link_expiry = min(
            now + _INSTRUCTION_LINK_TTL,
            claim_expiry or now + _INSTRUCTION_LINK_TTL,
        )
        if link_expiry <= now:
            await self._release_instruction_quotas(hourly_quota_keys)
            raise self._domain_http_error(
                status.HTTP_410_GONE,
                "domain_claim_expired",
                "The current DNS ownership challenge has expired.",
                "Restart domain setup before sending instructions.",
            )
        new_link_generation = not (
            existing_link
            and existing_link.get("state") == "active"
            and existing_expiry
            and existing_expiry > now
        )
        active_quota_keys: list[str] = []
        if new_link_generation:
            active_quota_key = (
                f"instruction:active:{owner_id}:{record['_id']}:{attempt_id}"
            )
            try:
                active_quota_keys = await self._acquire_instruction_quotas(
                    [
                        (
                            active_quota_key,
                            _INSTRUCTION_ACTIVE_LINK_LIMIT,
                            claim_expiry or link_expiry,
                        )
                    ]
                )
            except HTTPException:
                await self._release_instruction_quotas(hourly_quota_keys)
                raise

            link_id = f"sfil_{uuid4().hex}"
            link_token = secrets.token_urlsafe(32)
            token_digest = hashlib.sha256(link_token.encode()).hexdigest()
            token_ciphertext = self._claim_cipher.encrypt(link_token.encode()).decode()
            link_document = {
                **link_filter,
                "link_id": link_id,
                "planner_id": owner_id,
                "hostname": record["hostname"],
                "recipient_hint": recipient_hint,
                "token_digest": token_digest,
                "token_ciphertext": token_ciphertext,
                "state": "active",
                "delivery_state": "pending",
                "active_quota_key": active_quota_key,
                "expires_at": link_expiry,
                "created_at": now,
                "updated_at": now,
            }
            if existing_link:
                reservation = await links.update_one(
                    {
                        "_id": existing_link["_id"],
                        "$or": [
                            {"state": {"$ne": "active"}},
                            {"expires_at": {"$lte": now}},
                        ],
                    },
                    {
                        "$set": link_document,
                        "$unset": {
                            "revoked_at": "",
                            "revoked_token_digest": "",
                            "delivered_at": "",
                            "last_delivery_error": "",
                            "delivery_lease_id": "",
                            "delivery_lease_expires_at": "",
                        },
                    },
                )
                if not getattr(reservation, "matched_count", 0):
                    await self._release_instruction_quotas(
                        [*hourly_quota_keys, *active_quota_keys]
                    )
                    raise self._domain_http_error(
                        status.HTTP_409_CONFLICT,
                        "domain_instructions_delivery_in_progress",
                        "DNS instructions are already being prepared for this recipient.",
                        "Wait a moment, then reload the active instruction links.",
                        retryable=True,
                    )
            else:
                try:
                    await links.insert_one(link_document)
                except DuplicateKeyError:
                    await self._release_instruction_quotas(
                        [*hourly_quota_keys, *active_quota_keys]
                    )
                    raise self._domain_http_error(
                        status.HTTP_409_CONFLICT,
                        "domain_instructions_delivery_in_progress",
                        "DNS instructions are already being prepared for this recipient.",
                        "Wait a moment, then reload the active instruction links.",
                        retryable=True,
                    )
            existing_link = await links.find_one(link_filter)
        else:
            token_ciphertext = existing_link.get("token_ciphertext")
            if not isinstance(token_ciphertext, str):
                await self._release_instruction_quotas(hourly_quota_keys)
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "domain_instruction_retry_unavailable",
                    "This existing instruction link cannot be retried safely.",
                    "Revoke the existing link, then send a new one.",
                )
            try:
                link_token = self._claim_cipher.decrypt(
                    token_ciphertext.encode()
                ).decode()
            except (InvalidToken, UnicodeDecodeError):
                await self._release_instruction_quotas(hourly_quota_keys)
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "domain_instruction_retry_unavailable",
                    "This existing instruction link cannot be retried safely.",
                    "Revoke the existing link, then send a new one.",
                )
            link_id = str(existing_link["link_id"])
            token_digest = hashlib.sha256(link_token.encode()).hexdigest()

        if not existing_link:
            await self._release_instruction_quotas(
                [*hourly_quota_keys, *active_quota_keys]
            )
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_instruction_link_unavailable",
                "The secure instruction link could not be prepared.",
                "Copy the records manually and retry later.",
                retryable=True,
            )

        lease_id = f"sfil_lease_{uuid4().hex}"
        lease_result = await links.update_one(
            {
                "_id": existing_link["_id"],
                "state": "active",
                "$or": [
                    {"delivery_state": {"$in": ["pending", "failed"]}},
                    {
                        "delivery_state": "sending",
                        "delivery_lease_expires_at": {"$lte": now},
                    },
                ],
            },
            {
                "$set": {
                    "delivery_state": "sending",
                    "delivery_lease_id": lease_id,
                    "delivery_lease_expires_at": now + _INSTRUCTION_DELIVERY_LEASE,
                    "updated_at": now,
                }
            },
        )
        if not getattr(lease_result, "matched_count", 0):
            await self._release_instruction_quotas(
                [*hourly_quota_keys, *active_quota_keys]
            )
            latest_link = await links.find_one(link_filter)
            if latest_link and latest_link.get("delivery_state") == "completed":
                return {"status": "sent", **self._instruction_link_summary(latest_link)}
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_instructions_delivery_in_progress",
                "DNS instructions are already being delivered to this recipient.",
                "Wait a moment, then reload the active instruction links.",
                retryable=True,
            )

        link_url = self._instruction_link_url(link_token)
        safe_note = (
            note.strip()[:1000] if isinstance(note, str) and note.strip() else None
        )
        await links.update_one(
            {"_id": existing_link["_id"], "delivery_lease_id": lease_id},
            {
                "$set": {
                    "note": safe_note,
                    "updated_at": now,
                },
                "$unset": {
                    "records": "",
                    "revoked_at": "",
                    "revoked_token_digest": "",
                },
            },
        )
        operation_id = (
            "sfi_"
            + hashlib.sha256(
                f"{record['_id']}:{attempt_id}:{recipient_hash}".encode()
            ).hexdigest()[:32]
        )
        await operations.update_one(
            {"operation_id": operation_id},
            {
                "$set": {
                    "state": "sending",
                    "instruction_link_id": link_id,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "operation_id": operation_id,
                    "domain_id": str(record["_id"]),
                    "attempt_id": f"{attempt_id}:{recipient_hash[:20]}",
                    "kind": "instruction_email",
                    "planner_id": owner_id,
                    "claim_attempt_id": attempt_id,
                    "recipient_hash": recipient_hash,
                    "request_fingerprint": hashlib.sha256(
                        f"{record['_id']}:{attempt_id}:{recipient_hash}".encode()
                    ).hexdigest(),
                    "created_at": now,
                    "expires_at": now + _LIFECYCLE_RECEIPT_TTL,
                },
                "$inc": {"delivery_attempts": 1},
            },
            upsert=True,
        )

        note_html = (
            f"<p><strong>Planner note:</strong> {html.escape(safe_note)}</p>"
            if safe_note
            else ""
        )
        hostname = html.escape(str(record["hostname"]))
        content = (
            f"<h1>DNS setup for {hostname}</h1>"
            "<p>Add the exact records below at the authoritative DNS provider. "
            "Do not remove existing production records unless your migration plan "
            "explicitly calls for cutover.</p>"
            f"{note_html}"
            f'<p><a href="{html.escape(link_url, quote=True)}">'
            "View secure read-only DNS instructions</a>. This link expires in "
            "seven days or when the current claim expires, and cannot change DNS "
            "or activate the storefront.</p>"
            "<p>The planner can return to The Special Wedding after DNS has "
            "propagated and choose I've added these records. Later pending states "
            "use Check again. Provider authorization alone does not prove "
            "activation.</p>"
        )
        email_service = self._instruction_email_service
        if email_service is None:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()
        try:
            result = await email_service.send_email(
                to_email=normalized_email,
                subject=f"DNS setup instructions for {record['hostname']}",
                html_content=content,
                from_name=settings.resend_from_name,
                email_type=STOREFRONT_DOMAIN_INSTRUCTIONS_EMAIL_TYPE,
                idempotency_key=f"storefront-domain-instructions:{link_id}",
            )
        except Exception:
            result = None
        if not isinstance(result, dict) or result.get("success") is not True:
            error = self._error_detail(
                "domain_instructions_delivery_failed",
                "The DNS instructions could not be delivered.",
                "Confirm the email address and retry later.",
                retryable=True,
            )
            await operations.update_one(
                {"operation_id": operation_id},
                {
                    "$set": {
                        "state": "failed",
                        "last_error": error,
                        "updated_at": self._now(),
                    }
                },
            )
            await links.update_one(
                {"_id": existing_link["_id"], "delivery_lease_id": lease_id},
                {
                    "$set": {
                        "delivery_state": "failed",
                        "last_delivery_error": error,
                        "updated_at": self._now(),
                    },
                    "$unset": {
                        "delivery_lease_id": "",
                        "delivery_lease_expires_at": "",
                    },
                },
            )
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                error["code"],
                error["message"],
                error["customer_action"],
                retryable=True,
            )
        provider_message_id = (
            result.get("message_id") or result.get("resend_id") or result.get("id")
        )
        if not isinstance(provider_message_id, str) or not provider_message_id.strip():
            provider_message_id = None
        else:
            provider_message_id = provider_message_id.strip()
        await operations.update_one(
            {"operation_id": operation_id},
            {
                "$set": {
                    "state": "completed",
                    "provider_message_id": provider_message_id,
                    "completed_at": self._now(),
                    "updated_at": self._now(),
                },
                "$unset": {"last_error": ""},
            },
        )
        await links.update_one(
            {"_id": existing_link["_id"], "delivery_lease_id": lease_id},
            {
                "$set": {
                    "delivery_state": "completed",
                    "delivered_at": self._now(),
                    "updated_at": self._now(),
                },
                "$unset": {
                    "delivery_lease_id": "",
                    "delivery_lease_expires_at": "",
                    "last_delivery_error": "",
                },
            },
        )
        saved_link = await links.find_one({"_id": existing_link["_id"]})
        return {
            "status": "sent",
            **self._instruction_link_summary(saved_link or existing_link),
        }

    async def read_instruction_link(self, token: str) -> dict[str, Any]:
        """Read a current instruction snapshot without exposing any mutation."""

        if not isinstance(token, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{43,128}", token
        ):
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_instruction_link_not_found",
                "This DNS instruction link is unavailable.",
                "Ask the planner to send a new instruction link.",
            )
        digest = hashlib.sha256(token.encode()).hexdigest()
        link = await self._mongo.db["storefront_domain_instruction_links"].find_one(
            {"token_digest": digest, "state": "active"}
        )
        expires_at = self._aware(link.get("expires_at")) if link else None
        if not link or not expires_at or expires_at <= self._now():
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_instruction_link_not_found",
                "This DNS instruction link is unavailable.",
                "Ask the planner to send a new instruction link.",
            )
        current = await self._mongo.db["storefront_domains"].find_one(
            {
                "planner_id": link.get("planner_id"),
                "claim_attempt_id": link.get("claim_attempt_id"),
                "hostname": link.get("hostname"),
                "deletion_status": None,
            }
        )
        if not current:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_instruction_link_not_found",
                "This DNS instruction link is unavailable.",
                "Ask the planner to send a new instruction link.",
            )
        authoritative_dns = current.get("authoritative_dns")
        provider: dict[str, Any] | None = None
        zone: str | None = None
        provider_key: str | None = None
        if isinstance(authoritative_dns, dict):
            candidate_zone = authoritative_dns.get("zone")
            candidate_provider = authoritative_dns.get("provider")
            if (
                isinstance(candidate_zone, str)
                and candidate_zone
                and (
                    link["hostname"] == candidate_zone
                    or link["hostname"].endswith(f".{candidate_zone}")
                )
                and isinstance(candidate_provider, str)
            ):
                zone = candidate_zone
                provider_key = candidate_provider
                provider_name, canonical_panel_url = self._dns_provider_details(
                    provider_key
                )
                provider = {
                    "name": provider_name,
                    "zone": zone,
                    "control_panel_url": canonical_panel_url,
                }

        public_records: list[dict[str, Any]] = []
        for item in self._serialize(current).get("expected_records") or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            relative_host: str | None = None
            if isinstance(name, str) and zone:
                if name == zone:
                    relative_host = "@"
                elif name.endswith(f".{zone}"):
                    relative_host = name[: -(len(zone) + 1)]
            public_records.append(
                {
                    **item,
                    "relative_host": relative_host,
                    "proxy": (
                        "dns_only"
                        if provider_key == "cloudflare" and item.get("type") == "CNAME"
                        else None
                    ),
                }
            )

        return {
            "hostname": link["hostname"],
            "records": public_records,
            "provider": provider,
            "note": link.get("note"),
            "expires_at": expires_at,
        }

    async def revoke_instruction_link(self, owner: Any, link_id: str) -> dict[str, str]:
        """Revoke an owner-scoped public link even after entitlement loss."""

        owner_id = self._owner_id(owner)
        links = self._mongo.db["storefront_domain_instruction_links"]
        link = await links.find_one({"planner_id": owner_id, "link_id": link_id})
        if not link:
            raise self._domain_http_error(
                status.HTTP_404_NOT_FOUND,
                "domain_instruction_link_not_found",
                "This DNS instruction link could not be found.",
                "Reload domain status before trying again.",
            )
        if link.get("state") == "revoked":
            return {"status": "revoked"}
        result = await links.update_one(
            {"_id": link["_id"], "planner_id": owner_id, "state": "active"},
            {
                "$set": {
                    "state": "revoked",
                    "revoked_at": self._now(),
                    "revoked_token_digest": link.get("token_digest"),
                    "updated_at": self._now(),
                },
                "$unset": {"token_digest": "", "token_ciphertext": ""},
            },
        )
        active_quota_key = link.get("active_quota_key")
        if getattr(result, "matched_count", 0) and isinstance(active_quota_key, str):
            await self._release_instruction_quotas([active_quota_key])
        return {"status": "revoked"}

    @staticmethod
    def _record_dict(value: object, allowed_fields: tuple[str, ...]) -> dict | None:
        if not isinstance(value, dict):
            return None
        result = {
            field: value[field]
            for field in allowed_fields
            if isinstance(value.get(field), (str, int, bool))
        }
        return result or None

    @classmethod
    def _validation_records(cls, ssl: object) -> list[dict]:
        if not isinstance(ssl, dict) or not isinstance(
            ssl.get("validation_records"), list
        ):
            return []
        records: list[dict] = []
        for record in ssl["validation_records"]:
            sanitized = cls._record_dict(
                record,
                (
                    "status",
                    "txt_name",
                    "txt_value",
                    "cname_name",
                    "cname_target",
                    "emails",
                ),
            )
            if sanitized:
                records.append(sanitized)
        return records

    @staticmethod
    def _status(value: object, fallback: str = "pending") -> str:
        if not isinstance(value, str) or not value.strip():
            return fallback
        return value.strip().lower()

    @classmethod
    def _provider_projection(cls, provider_result: dict) -> dict:
        ssl = provider_result.get("ssl")
        ssl_status = cls._status(ssl.get("status") if isinstance(ssl, dict) else None)
        provider_status = cls._status(provider_result.get("status"))

        def sanitized_messages(value: object) -> list[str]:
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

        return {
            "provider_status": provider_status,
            "ssl_status": ssl_status,
            "status": (
                "active"
                if provider_status == "active" and ssl_status == "active"
                else "pending"
            ),
            "ownership_verification": cls._record_dict(
                provider_result.get("ownership_verification"),
                ("type", "name", "value"),
            ),
            "ownership_verification_http": cls._record_dict(
                provider_result.get("ownership_verification_http"),
                ("http_url", "http_body"),
            ),
            "ssl_validation_records": cls._validation_records(ssl),
            "provider_verification_errors": sanitized_messages(
                provider_result.get("verification_errors")
            ),
            "ssl_validation_errors": sanitized_messages(
                ssl.get("validation_errors") if isinstance(ssl, dict) else None
            ),
        }

    @classmethod
    def _provider_expected_records(cls, record: dict) -> list[dict[str, Any]]:
        """Expose provider-issued TXT/CNAME work while it is still required."""

        expected: list[dict[str, Any]] = []
        if cls._status(record.get("provider_status")) != "active":
            ownership = record.get("ownership_verification")
            if isinstance(ownership, dict):
                record_type = cls._status(ownership.get("type"), "").upper()
                name = ownership.get("name")
                value = ownership.get("value")
                if record_type in {"TXT", "CNAME"} and all(
                    isinstance(item, str) and item for item in (name, value)
                ):
                    expected.append(
                        {
                            "type": record_type,
                            "name": name,
                            "value": value,
                            "ttl": 300,
                            "purpose": "provider_hostname_validation",
                        }
                    )
        if cls._status(record.get("ssl_status")) != "active":
            for validation in record.get("ssl_validation_records") or []:
                if not isinstance(validation, dict):
                    continue
                if isinstance(validation.get("txt_name"), str) and isinstance(
                    validation.get("txt_value"), str
                ):
                    expected.append(
                        {
                            "type": "TXT",
                            "name": validation["txt_name"],
                            "value": validation["txt_value"],
                            "ttl": 300,
                            "purpose": "certificate_validation",
                        }
                    )
                elif isinstance(validation.get("cname_name"), str) and isinstance(
                    validation.get("cname_target"), str
                ):
                    expected.append(
                        {
                            "type": "CNAME",
                            "name": validation["cname_name"],
                            "value": validation["cname_target"],
                            "ttl": 300,
                            "purpose": "certificate_validation",
                        }
                    )
        return expected

    def _serialize(self, record: dict) -> dict:
        raw_application_status = self._status(record.get("application_status"), "")
        include_routing = bool(
            record.get("intent") != "migration"
            or raw_application_status
            in {
                CUTOVER_READY,
                DEPLOYING,
                ACTIVE,
                DISCONNECTING,
                DISCONNECT_FAILED,
                DISCONNECTED,
            }
            or record.get("migration_cutover_ready_at")
            or record.get("migration_cutover_completed_at")
        )
        token = (
            None
            if raw_application_status == EXPIRED
            or self._status(record.get("ownership_status")) == "expired"
            else self._decrypt_claim_token(record)
        )
        observed_records = [
            {
                **item,
                **(
                    {"values": list(item.get("values") or [])}
                    if isinstance(item, dict)
                    else {}
                ),
            }
            for item in list(record.get("observed_records") or [])
            if isinstance(item, dict)
        ]
        if token and self._status(record.get("ownership_status")) == "verified":
            ownership_name = f"_tsw-storefront.{record['hostname']}"
            ownership_observation = next(
                (
                    item
                    for item in observed_records
                    if item.get("type") == "TXT" and item.get("name") == ownership_name
                ),
                None,
            )
            if ownership_observation is None:
                ownership_observation = {
                    "type": "TXT",
                    "name": ownership_name,
                    "values": [],
                    "purpose": "application_ownership",
                }
                observed_records.append(ownership_observation)
            current_proof = f"tsw-verification={token}"
            ownership_values = list(ownership_observation.get("values") or [])
            if current_proof not in ownership_values:
                ownership_values.append(current_proof)
            ownership_observation["values"] = ownership_values
        expected_records = (
            self._expected_records(
                record["hostname"], token, include_routing=include_routing
            )
            if token
            else []
        )
        seen_expected = {
            (item.get("type"), item.get("name"), item.get("value"))
            for item in expected_records
        }
        for provider_record in self._provider_expected_records(record):
            identity = (
                provider_record.get("type"),
                provider_record.get("name"),
                provider_record.get("value"),
            )
            if identity not in seen_expected:
                expected_records.append(provider_record)
                seen_expected.add(identity)
        ownership_verification = record.get("ownership_verification")
        if ownership_verification is None and expected_records:
            txt_record = expected_records[0]
            ownership_verification = {
                "type": "txt",
                "name": txt_record["name"],
                "value": txt_record["value"],
            }
        provider_status = self._status(record.get("provider_status"))
        authoritative_dns = record.get("authoritative_dns")
        if not (
            isinstance(authoritative_dns, dict)
            and isinstance(authoritative_dns.get("zone"), str)
            and isinstance(authoritative_dns.get("provider"), str)
            and isinstance(authoritative_dns.get("nameservers"), list)
        ):
            authoritative_dns = None
        if raw_application_status in STOREFRONT_DOMAIN_APPLICATION_STATUSES:
            application_status = raw_application_status
        else:
            legacy_status = self._status(record.get("status"))
            application_status = {
                "active": DEPLOYING,
                "deleting": DISCONNECTING,
                "delete_failed": DISCONNECT_FAILED,
                "provider_deleted": DISCONNECTED,
                _PROVISIONING: PROVIDER_PROVISIONING,
                _PROVISIONING_UNKNOWN: OPERATOR_REVIEW,
            }.get(
                legacy_status,
                (
                    HOSTNAME_VALIDATION
                    if record.get("provider_hostname_id")
                    else (
                        DNS_SETUP_PENDING
                        if record.get("claim_attempt_id")
                        else CLAIM_PENDING
                    )
                ),
            )
        return {
            "hostname": record["hostname"],
            "status": self._status(record.get("status")),
            "provider_status": provider_status,
            "ssl_status": self._status(record.get("ssl_status")),
            "application_status": application_status,
            "ownership_status": self._status(record.get("ownership_status"), "pending"),
            "provider_hostname_status": self._status(
                record.get("provider_hostname_status"), provider_status
            ),
            "routing_dns_status": self._status(
                record.get("routing_dns_status"), "pending"
            ),
            "https_status": self._status(record.get("https_status"), "pending"),
            "action": self._status(record.get("action"), "action_required"),
            "provider_hostname_id": record.get("provider_hostname_id"),
            "attempt_id": record.get("claim_attempt_id"),
            "revision": max(int(record.get("revision") or 0), 0),
            "claim_expires_at": record.get("claim_expires_at"),
            "intent": record.get("intent") or "new",
            "authoritative_dns": authoritative_dns,
            "observed_records": observed_records,
            "conflicts": list(record.get("dns_conflicts") or []),
            "cleanup_records": list(record.get("cleanup_records") or []),
            "domain_connect_supported": bool(record.get("domain_connect_supported")),
            "domain_connect_provider": record.get("domain_connect_provider"),
            "registrar": record.get("registrar"),
            "platform_provider": record.get("platform_provider")
            or "Cloudflare for The Special Wedding",
            "conflict_code": record.get("conflict_code"),
            "last_checked_at": record.get("last_checked_at"),
            "next_check_at": record.get("retry_due_at"),
            "expected_records": expected_records,
            "ownership_verification": ownership_verification,
            "ownership_verification_http": record.get("ownership_verification_http"),
            "ssl_validation_records": list(record.get("ssl_validation_records") or []),
            "provider_verification_errors": list(
                record.get("provider_verification_errors") or []
            ),
            "ssl_validation_errors": list(record.get("ssl_validation_errors") or []),
            "cname_target": record.get("cname_target") or self._cname_target,
            "deletion_status": record.get("deletion_status"),
            "last_error": record.get("last_error"),
        }

    @staticmethod
    def _has_deletion_intent(record: dict) -> bool:
        deletion_status = record.get("deletion_status")
        return (
            isinstance(deletion_status, str) and bool(deletion_status.strip())
        ) or StorefrontDomainService._status(record.get("status")) in (
            _NON_ROUTABLE_DOMAIN_STATUSES
        )

    @staticmethod
    def _refresh_write_filter(record: dict, owner_id: str) -> dict:
        """Fence a provider observation to the exact lifecycle row it read.

        A provider GET is an unbounded network await. Disconnect may claim the
        row while that request is in flight, so every later refresh write must
        compare the lifecycle identity it observed before the await.
        """

        return {
            "_id": record["_id"],
            "planner_id": owner_id,
            "hostname": record.get("hostname"),
            "provider_hostname_id": record.get("provider_hostname_id"),
            "status": record.get("status"),
            "provider_status": record.get("provider_status"),
            "ssl_status": record.get("ssl_status"),
            "deletion_status": record.get("deletion_status"),
            "deletion_attempt_id": record.get("deletion_attempt_id"),
            "updated_at": record.get("updated_at"),
        }

    async def _write_refresh_observation(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
        update: dict,
    ) -> tuple[bool, dict | None]:
        """Persist a refresh result or return a newer deletion projection.

        A lost compare-and-set is only safely absorbable when the row vanished
        or moved into deletion. Other concurrent edits remain an explicit 409.
        """

        result = await collection.update_one(
            self._refresh_write_filter(record, owner_id), update
        )
        if getattr(result, "matched_count", 0):
            return True, None

        current = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not current:
            return False, None
        if self._has_deletion_intent(current):
            return False, self._serialize(current)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom-domain mapping changed during refresh",
        )

    @staticmethod
    def _provider_not_found(exc: CloudflareServiceError) -> bool:
        """Return true only for an authoritative provider-level HTTP 404."""

        return exc.kind == "provider" and exc.provider_status_code == 404

    @staticmethod
    def _bounded_provider_value(value: object, *, limit: int = 256) -> str | None:
        """Return a bounded, printable provider value suitable for a receipt."""

        if not isinstance(value, str):
            return None
        normalized = " ".join(value.split()).strip()
        if not normalized:
            return None
        return normalized[:limit]

    @classmethod
    def _provider_delete_receipt(
        cls,
        *,
        outcome: str,
        provider_id: str | None,
        provider_result: object = None,
        provider_status_code: int | None = None,
    ) -> dict[str, object]:
        """Build a small allowlisted receipt without retaining provider payloads."""

        receipt: dict[str, object] = {
            "outcome": outcome,
            "provider": "cloudflare",
        }
        if isinstance(provider_status_code, int):
            receipt["provider_status_code"] = provider_status_code
        if isinstance(provider_result, dict):
            response_id = cls._bounded_provider_value(provider_result.get("id"))
            response_status = cls._bounded_provider_value(
                provider_result.get("status"), limit=64
            )
            response_hostname = cls._bounded_provider_value(
                provider_result.get("hostname"), limit=253
            )
            if response_id:
                receipt["response_provider_hostname_id"] = response_id
                receipt["response_id_matches_request"] = response_id == provider_id
            if response_status:
                receipt["provider_status"] = response_status
            if response_hostname:
                receipt["response_hostname"] = response_hostname
        return receipt

    @staticmethod
    def _provider_delete_operation_id(deletion_attempt_id: str) -> str:
        return f"cfd_{deletion_attempt_id}"

    @staticmethod
    def _provider_delete_request_fingerprint(
        *,
        owner_id: str,
        domain_id: object,
        hostname: object,
        provider_id: object,
        deletion_attempt_id: str,
    ) -> str:
        request_identity = "\n".join(
            (
                "storefront-provider-delete-v1",
                owner_id,
                str(domain_id),
                str(hostname or "")[:253],
                str(provider_id or "")[:256],
                deletion_attempt_id,
            )
        )
        return hashlib.sha256(request_identity.encode("utf-8")).hexdigest()

    async def _prepare_provider_delete_operation(
        self,
        *,
        record: dict,
        owner_id: str,
        deletion_attempt_id: str,
    ) -> tuple[str, dict]:
        """Reserve one durable provider-delete row for one deletion attempt."""

        operation_id = self._provider_delete_operation_id(deletion_attempt_id)
        fingerprint = self._provider_delete_request_fingerprint(
            owner_id=owner_id,
            domain_id=record["_id"],
            hostname=record.get("hostname"),
            provider_id=record.get("provider_hostname_id"),
            deletion_attempt_id=deletion_attempt_id,
        )
        now = self._now()
        operation = {
            "operation_id": operation_id,
            "domain_id": str(record["_id"]),
            "attempt_id": deletion_attempt_id,
            "deletion_attempt_id": deletion_attempt_id,
            "kind": "provider_delete",
            "planner_id": owner_id,
            "hostname": str(record.get("hostname") or "")[:253],
            "provider": "cloudflare",
            "provider_hostname_id": self._bounded_provider_value(
                record.get("provider_hostname_id")
            ),
            "request_fingerprint": fingerprint,
            "state": "prepared",
            "created_at": now,
            "updated_at": now,
            "expires_at": now + _LIFECYCLE_RECEIPT_TTL,
        }
        operations = self._mongo.db["storefront_domain_operations"]
        try:
            await operations.insert_one(operation)
            return operation_id, operation
        except DuplicateKeyError:
            existing = await operations.find_one({"operation_id": operation_id})
            immutable_identity = (
                existing
                and existing.get("domain_id") == operation["domain_id"]
                and existing.get("attempt_id") == deletion_attempt_id
                and existing.get("kind") == "provider_delete"
                and existing.get("planner_id") == owner_id
                and existing.get("hostname") == operation["hostname"]
                and existing.get("provider_hostname_id")
                == operation["provider_hostname_id"]
                and existing.get("request_fingerprint") == fingerprint
            )
            if immutable_identity:
                return operation_id, existing
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_delete_operation_conflict",
                "The provider deletion receipt conflicts with another operation.",
                "Contact support before retrying this disconnect.",
                retryable=False,
            )

    async def _delete_provider_with_receipt(
        self,
        *,
        record: dict,
        owner_id: str,
        deletion_attempt_id: str,
    ) -> tuple[str, dict[str, object]]:
        """Delete one provider mapping and durably record its bounded outcome."""

        operation_id, operation = await self._prepare_provider_delete_operation(
            record=record,
            owner_id=owner_id,
            deletion_attempt_id=deletion_attempt_id,
        )
        operations = self._mongo.db["storefront_domain_operations"]
        if operation.get("state") == "completed" and isinstance(
            operation.get("provider_receipt"), dict
        ):
            return operation_id, dict(operation["provider_receipt"])

        operation_state = operation.get("state")
        operation_updated_at = self._aware(operation.get("updated_at"))
        requesting_filter: dict[str, object] = {"state": "prepared"}
        if operation_state == "requesting":
            if operation_updated_at and operation_updated_at > self._now() - timedelta(
                minutes=10
            ):
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "provider_delete_in_progress",
                    "The provider deletion request is already in progress.",
                    "Wait for the current disconnect attempt to finish.",
                    retryable=True,
                )
            requesting_filter = {
                "state": "requesting",
                "updated_at": operation.get("updated_at"),
            }
        elif operation_state != "prepared":
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_delete_attempt_closed",
                "The previous provider deletion attempt is closed.",
                "Retry the disconnect to create a new deletion attempt.",
                retryable=True,
            )

        requesting_at = self._now()
        requesting = await operations.update_one(
            {
                "operation_id": operation_id,
                "planner_id": owner_id,
                "domain_id": str(record["_id"]),
                "kind": "provider_delete",
                "request_fingerprint": operation["request_fingerprint"],
                **requesting_filter,
            },
            {
                "$set": {
                    "state": "requesting",
                    "request_started_at": requesting_at,
                    "updated_at": requesting_at,
                },
                "$inc": {"request_count": 1},
            },
        )
        if not getattr(requesting, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_delete_receipt_unavailable",
                "The provider deletion receipt could not be advanced safely.",
                "Retry the disconnect later or contact support.",
                retryable=True,
            )

        provider_id = record.get("provider_hostname_id")
        if not isinstance(provider_id, str) or not provider_id:
            receipt = self._provider_delete_receipt(
                outcome="not_created",
                provider_id=None,
            )
        else:
            try:
                provider_result = await self._cloudflare.delete_custom_hostname(
                    provider_id
                )
            except CloudflareServiceError as exc:
                if self._provider_not_found(exc):
                    receipt = self._provider_delete_receipt(
                        outcome="not_found",
                        provider_id=provider_id,
                        provider_status_code=exc.provider_status_code,
                    )
                else:
                    retry_error = self._error_detail(
                        "provider_delete_failed",
                        "The provider mapping could not be removed.",
                        "Retry the disconnect later; the hostname is no longer routable in the application.",
                        retryable=True,
                        provider={
                            "name": "cloudflare",
                            "operation": "delete_custom_hostname",
                            "status_code": exc.provider_status_code,
                        },
                    )
                    await operations.update_one(
                        {
                            "operation_id": operation_id,
                            "planner_id": owner_id,
                            "kind": "provider_delete",
                        },
                        {
                            "$set": {
                                "state": "failed",
                                "retry_error": retry_error,
                                "last_error": retry_error,
                                "provider_status_code": exc.provider_status_code,
                                "failed_at": self._now(),
                                "updated_at": self._now(),
                            }
                        },
                    )
                    raise
            else:
                receipt = self._provider_delete_receipt(
                    outcome="deleted",
                    provider_id=provider_id,
                    provider_result=provider_result,
                )

        completed_at = self._now()
        completed = await operations.update_one(
            {
                "operation_id": operation_id,
                "planner_id": owner_id,
                "domain_id": str(record["_id"]),
                "kind": "provider_delete",
            },
            {
                "$set": {
                    "state": "completed",
                    "provider_receipt": receipt,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
                "$unset": {"retry_error": "", "last_error": ""},
            },
        )
        if not getattr(completed, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_delete_receipt_not_persisted",
                "The provider mapping was removed but its receipt could not be saved.",
                "Contact support before reconnecting this hostname.",
                retryable=True,
            )
        return operation_id, receipt

    @staticmethod
    def _provider_http_error(exc: CloudflareServiceError) -> HTTPException:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.kind == "configuration"
            else status.HTTP_502_BAD_GATEWAY
        )
        return StorefrontDomainService._domain_http_error(
            status_code,
            (
                "custom_domain_not_configured"
                if exc.kind == "configuration"
                else "custom_domain_provider_error"
            ),
            (
                "Custom-domain setup is temporarily unavailable."
                if exc.kind == "configuration"
                else "The custom-domain provider could not complete the request."
            ),
            "Keep using the platform storefront URL and retry later.",
            retryable=exc.kind != "provider"
            or not isinstance(exc.provider_status_code, int)
            or exc.provider_status_code >= 500
            or exc.provider_status_code == 429,
            provider={
                "name": "cloudflare",
                "operation": exc.operation,
                "kind": exc.kind,
                "status_code": exc.provider_status_code,
            },
        )

    @staticmethod
    def _create_failure_is_definitive(exc: CloudflareServiceError) -> bool:
        if exc.kind == "configuration":
            return True
        provider_status = exc.provider_status_code
        return bool(
            exc.kind == "provider"
            and isinstance(provider_status, int)
            and 400 <= provider_status < 500
            and provider_status not in {408, 409, 425, 429}
        )

    @staticmethod
    def _timestamp_is_older_than(value: object, seconds: int) -> bool:
        if not isinstance(value, datetime):
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc) - timedelta(seconds=seconds)

    async def _recover_stale_provisioning(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
    ) -> dict:
        if self._status(record.get("status")) != _PROVISIONING:
            return record
        started_at = record.get("provisioning_started_at") or record.get("updated_at")
        if not self._timestamp_is_older_than(started_at, _PROVISIONING_LEASE_SECONDS):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning is still in progress",
            )
        now = datetime.now(timezone.utc)
        recovered = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "hostname": record.get("hostname"),
                "provider_hostname_id": None,
                "status": _PROVISIONING,
                "provisioning_attempt_id": record.get("provisioning_attempt_id"),
                "updated_at": record.get("updated_at"),
            },
            {
                "$set": {
                    "status": _PROVISIONING_UNKNOWN,
                    "provider_status": "unknown",
                    "last_error": "Interrupted provisioning requires reconciliation",
                    "provisioning_unknown_at": now,
                    "updated_at": now,
                },
                "$unset": {
                    "provisioning_attempt_id": "",
                    "provisioning_started_at": "",
                },
            },
        )
        if not getattr(recovered, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if current and self._status(current.get("status")) in {
                _PROVISIONING_UNKNOWN,
                "pending",
            }:
                return current
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning changed during recovery",
            )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain provisioning recovery could not be read",
            )
        return saved

    async def _mark_provisioning_unknown(
        self,
        collection: Any,
        *,
        record_id: Any,
        owner_id: str,
        attempt_id: str,
        error: CloudflareServiceError,
    ) -> None:
        now = datetime.now(timezone.utc)
        result = await collection.update_one(
            {
                "_id": record_id,
                "planner_id": owner_id,
                "provider_hostname_id": None,
                "status": _PROVISIONING,
                "provisioning_attempt_id": attempt_id,
            },
            {
                "$set": {
                    "status": _PROVISIONING_UNKNOWN,
                    "provider_status": "unknown",
                    "last_error": error.message,
                    "provisioning_unknown_at": now,
                    "updated_at": now,
                },
                "$unset": {
                    "provisioning_attempt_id": "",
                    "provisioning_started_at": "",
                },
            },
        )
        if getattr(result, "matched_count", 0):
            return
        current = await collection.find_one({"_id": record_id, "planner_id": owner_id})
        if current and (
            current.get("provider_hostname_id")
            or self._status(current.get("status")) == _PROVISIONING_UNKNOWN
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom-domain provisioning changed while recording its outcome",
        )

    async def _reconcile_unknown_provisioning(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
    ) -> dict:
        hostname = record.get("hostname")
        if not isinstance(hostname, str):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning receipt is invalid",
            )
        try:
            provider_rows = await self._cloudflare.list_custom_hostnames(hostname)
        except CloudflareServiceError as exc:
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "provider_hostname_id": None,
                    "status": _PROVISIONING_UNKNOWN,
                    "updated_at": record.get("updated_at"),
                },
                {
                    "$set": {
                        "last_error": exc.message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise self._provider_http_error(exc) from exc

        exact_rows: dict[str, dict] = {}
        invalid_result = False
        for provider_row in provider_rows:
            try:
                provider_hostname = normalize_custom_hostname(
                    provider_row.get("hostname"),
                    platform_domains=self._platform_domains,
                )
            except (TypeError, ValueError):
                provider_hostname = None
            provider_id = provider_row.get("id")
            if (
                provider_hostname != hostname
                or not isinstance(provider_id, str)
                or not provider_id.strip()
            ):
                invalid_result = True
                continue
            if provider_id in exact_rows:
                invalid_result = True
                continue
            exact_rows[provider_id] = provider_row

        if invalid_result:
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "provider_hostname_id": None,
                    "status": _PROVISIONING_UNKNOWN,
                },
                {
                    "$set": {
                        "last_error": (
                            "Cloudflare returned ambiguous hostname reconciliation"
                        ),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned ambiguous custom-hostname matches",
            )

        now = datetime.now(timezone.utc)
        reconciliation_error: dict[str, Any] | None = None
        if not exact_rows:
            previous_absences = record.get("provisioning_absent_observations", 0)
            if isinstance(previous_absences, bool) or not isinstance(
                previous_absences, int
            ):
                previous_absences = 0
            absence_count = previous_absences + 1
            absence_confirmed = (
                absence_count >= _PROVISIONING_ABSENCE_CONFIRMATIONS
                and self._timestamp_is_older_than(
                    record.get("provisioning_unknown_at"),
                    _PROVISIONING_RECONCILIATION_GRACE_SECONDS,
                )
            )
            result = await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "provider_hostname_id": None,
                    "status": _PROVISIONING_UNKNOWN,
                    "updated_at": record.get("updated_at"),
                },
                {
                    "$set": {
                        "status": (
                            "pending" if absence_confirmed else _PROVISIONING_UNKNOWN
                        ),
                        "provider_status": (
                            "pending" if absence_confirmed else "unknown"
                        ),
                        "provisioning_absent_observations": absence_count,
                        "last_error": (
                            None
                            if absence_confirmed
                            else "Cloudflare mapping absence is awaiting confirmation"
                        ),
                        "provisioning_reconciled_at": (
                            now if absence_confirmed else None
                        ),
                        "updated_at": now,
                    }
                },
            )
        else:
            provider_ids_before = record.get("provider_ids_before")
            snapshot_valid = isinstance(provider_ids_before, list) and all(
                isinstance(provider_id, str) and bool(provider_id.strip())
                for provider_id in provider_ids_before
            )
            snapshot_ids = set(provider_ids_before) if snapshot_valid else set()
            demonstrably_new_ids = set(exact_rows) - snapshot_ids
            if not snapshot_valid or len(demonstrably_new_ids) != 1:
                error = self._error_detail(
                    "ambiguous_provider_create",
                    "The provider create outcome cannot be proven automatically.",
                    "Do not retry or remove DNS; support must reconcile this attempt.",
                    retryable=False,
                    provider={
                        "name": "cloudflare",
                        "operation": "list_custom_hostnames",
                    },
                )
                reconciliation_error = error
                result = await collection.update_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "hostname": hostname,
                        "provider_hostname_id": None,
                        "status": _PROVISIONING_UNKNOWN,
                        "updated_at": record.get("updated_at"),
                    },
                    {
                        "$set": {
                            "status": "pending",
                            "application_status": OPERATOR_REVIEW,
                            "provider_status": "unknown",
                            "provider_hostname_status": "unknown",
                            "provider_reconciliation_required": True,
                            "action": "operator_review",
                            "last_error": error,
                            "retry_due_at": now + timedelta(minutes=1),
                            "updated_at": now,
                        },
                        "$unset": {"provisioning_absent_observations": ""},
                    },
                )
            else:
                provider_row = exact_rows[demonstrably_new_ids.pop()]
                result = await collection.update_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "hostname": hostname,
                        "provider_hostname_id": None,
                        "status": _PROVISIONING_UNKNOWN,
                        "updated_at": record.get("updated_at"),
                    },
                    {
                        "$set": {
                            "provider_hostname_id": provider_row["id"],
                            **self._provider_projection(provider_row),
                            "last_error": None,
                            "provider_reconciliation_required": False,
                            "provisioning_reconciled_at": now,
                            "updated_at": now,
                        },
                        "$unset": {"provisioning_absent_observations": ""},
                    },
                )
        if not getattr(result, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if current and (
                current.get("provider_hostname_id")
                or current.get("application_status") == OPERATOR_REVIEW
            ):
                return current
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning changed during reconciliation",
            )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain reconciliation could not be read",
            )
        if reconciliation_error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=reconciliation_error,
            )
        return saved

    async def get_for_owner(self, owner: Any) -> dict | None:
        return await self.get_status(owner)

    async def connect(self, owner: Any, raw_hostname: str) -> dict:
        """Source-compatible legacy entry point that now creates a DNS claim."""

        return await self.claim(owner, raw_hostname, intent="new")

    async def _legacy_unverified_provider_connect(
        self, owner: Any, raw_hostname: str
    ) -> dict:
        """Retained only for migration reference; no route or service calls it."""

        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        if not self._cname_target:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront custom-domain CNAME target is not configured",
            )
        self._require_provider_mutations(owner_id, hostname)

        try:
            provider_rows_before = await self._cloudflare.list_custom_hostnames(
                hostname
            )
        except CloudflareServiceError as exc:
            raise self._provider_http_error(exc) from exc
        rows_before, invalid_before = self._provider_identity_rows(
            provider_rows_before, hostname
        )
        if invalid_before:
            raise self._domain_http_error(
                status.HTTP_502_BAD_GATEWAY,
                "invalid_provider_snapshot",
                "The existing provider state could not be verified safely.",
                "Contact support before retrying this domain.",
                retryable=False,
                provider={"name": "cloudflare", "operation": "list_custom_hostnames"},
            )

        collection = self._mongo.db["storefront_domains"]
        now = datetime.now(timezone.utc)
        provisioning_attempt_id = uuid4().hex
        reservation = {
            "planner_id": owner_id,
            "hostname": hostname,
            "provider": "cloudflare",
            "provider_hostname_id": None,
            "status": _PROVISIONING,
            "provider_status": "pending",
            "ssl_status": "pending",
            "ownership_verification": None,
            "ownership_verification_http": None,
            "ssl_validation_records": [],
            "cname_target": self._cname_target,
            "deletion_status": None,
            "delete_attempts": 0,
            "last_error": None,
            "provisioning_attempt_id": provisioning_attempt_id,
            "provider_ids_before": sorted(rows_before),
            "provisioning_started_at": now,
            "created_at": now,
            "updated_at": now,
        }
        try:
            inserted = await collection.insert_one(reservation)
        except DuplicateKeyError as exc:
            existing = await collection.find_one(
                {
                    "$or": [
                        {"planner_id": owner_id},
                        {"hostname": hostname},
                    ]
                }
            )
            if (
                not existing
                or existing.get("planner_id") != owner_id
                or existing.get("hostname") != hostname
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This planner or hostname already has a custom-domain mapping"
                    ),
                ) from exc
            if existing.get("provider_hostname_id"):
                return self._serialize(existing)
            if self._status(existing.get("status")) == _PROVISIONING:
                existing = await self._recover_stale_provisioning(
                    collection, existing, owner_id
                )
            if self._status(existing.get("status")) == _PROVISIONING_UNKNOWN:
                existing = await self._reconcile_unknown_provisioning(
                    collection, existing, owner_id
                )
                if existing.get("provider_hostname_id"):
                    return self._serialize(existing)
            if self._status(existing.get("status")) != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Custom-domain provisioning is still being reconciled",
                ) from exc
            provisioning_attempt_id = uuid4().hex
            claimed = await collection.update_one(
                {
                    "_id": existing["_id"],
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "provider_hostname_id": None,
                    "status": "pending",
                    "updated_at": existing.get("updated_at"),
                },
                {
                    "$set": {
                        "status": _PROVISIONING,
                        "provisioning_attempt_id": provisioning_attempt_id,
                        "provisioning_started_at": datetime.now(timezone.utc),
                        "provider_ids_before": sorted(rows_before),
                        "last_error": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if not getattr(claimed, "matched_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Custom-domain provisioning changed during reconnect",
                ) from exc
            reservation_id = existing["_id"]
        else:
            reservation_id = inserted.inserted_id

        try:
            provider_result = await self._cloudflare.create_custom_hostname(hostname)
        except CloudflareServiceError as exc:
            if self._create_failure_is_definitive(exc):
                try:
                    await collection.delete_one(
                        {
                            "_id": reservation_id,
                            "planner_id": owner_id,
                            "provider_hostname_id": None,
                            "status": _PROVISIONING,
                            "provisioning_attempt_id": provisioning_attempt_id,
                        }
                    )
                except Exception:
                    logger.exception(
                        "Failed to release custom-domain reservation for owner %s",
                        owner_id,
                    )
            else:
                await self._mark_provisioning_unknown(
                    collection,
                    record_id=reservation_id,
                    owner_id=owner_id,
                    attempt_id=provisioning_attempt_id,
                    error=exc,
                )
            raise self._provider_http_error(exc) from exc

        provider_id = provider_result.get("id")
        provider_hostname = provider_result.get("hostname")
        try:
            normalized_provider_hostname = normalize_custom_hostname(
                provider_hostname, platform_domains=self._platform_domains
            )
        except (TypeError, ValueError):
            normalized_provider_hostname = None
        if not isinstance(provider_id, str) or not provider_id.strip():
            invalid_response = CloudflareServiceError(
                "Cloudflare returned an unreadable hostname mapping",
                operation="create_custom_hostname",
                kind="response",
            )
            await self._mark_provisioning_unknown(
                collection,
                record_id=reservation_id,
                owner_id=owner_id,
                attempt_id=provisioning_attempt_id,
                error=invalid_response,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned an invalid custom-hostname result",
            )
        if normalized_provider_hostname != hostname:
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="Cloudflare returned an invalid hostname mapping",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned an invalid custom-hostname result",
            )

        projection = self._provider_projection(provider_result)
        try:
            update_result = await collection.update_one(
                {
                    "_id": reservation_id,
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "provider_hostname_id": None,
                    "status": _PROVISIONING,
                    "provisioning_attempt_id": provisioning_attempt_id,
                },
                {
                    "$set": {
                        "provider_hostname_id": provider_id,
                        **projection,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "provisioning_attempt_id": "",
                        "provisioning_started_at": "",
                        "provisioning_absent_observations": "",
                        "provisioning_unknown_at": "",
                        "provider_missing_at": "",
                    },
                },
            )
        except Exception as exc:
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The provider mapping could not be persisted",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain mapping could not be persisted",
            ) from exc

        if not getattr(update_result, "matched_count", 0):
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The local reservation no longer exists",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain reservation changed during provisioning",
            )

        saved = await collection.find_one(
            {"_id": reservation_id, "planner_id": owner_id}
        )
        if not saved:
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The saved mapping could not be read",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain mapping could not be read after provisioning",
            )
        return self._serialize(saved)

    async def _compensate_failed_create(
        self,
        collection: Any,
        *,
        reservation_id: Any,
        owner_id: str,
        provider_id: str | None,
        failure_message: str,
    ) -> None:
        provider_deleted = not provider_id
        provider_error: str | None = None
        if provider_id:
            try:
                await self._cloudflare.delete_custom_hostname(provider_id)
                provider_deleted = True
            except CloudflareServiceError as exc:
                provider_error = exc.message
                logger.exception(
                    "Failed to compensate custom-domain create for owner %s", owner_id
                )

        if provider_deleted:
            await collection.delete_one({"_id": reservation_id, "planner_id": owner_id})
            return

        # If compensation itself failed, preserve enough identity to retry the
        # provider deletion rather than orphaning an external hostname.
        await collection.update_one(
            {"_id": reservation_id, "planner_id": owner_id},
            {
                "$set": {
                    "provider_hostname_id": provider_id,
                    "status": "delete_failed",
                    "application_status": DISCONNECT_FAILED,
                    "custom_route_enabled": False,
                    "action": "action_required",
                    "deletion_status": _PROVIDER_DELETE_RETRY_PENDING,
                    "last_error": provider_error or failure_message,
                    "retry_due_at": self._now() + timedelta(minutes=5),
                    "updated_at": self._now(),
                },
                "$inc": {"delete_attempts": 1},
            },
        )

    async def refresh(self, owner: Any) -> dict | None:
        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        collection = self._mongo.db["storefront_domains"]
        record = await collection.find_one({"planner_id": owner_id})
        if not record:
            return None
        # Disconnect intent is monotonic. A status poll must never ask the
        # provider for an activation projection and thereby resurrect a
        # hostname whose owner already requested removal.
        if self._has_deletion_intent(record):
            return self._serialize(record)
        provider_id = record.get("provider_hostname_id")
        if not isinstance(provider_id, str) or not provider_id:
            if self._status(record.get("status")) == _PROVISIONING:
                record = await self._recover_stale_provisioning(
                    collection, record, owner_id
                )
            if self._status(record.get("status")) == _PROVISIONING_UNKNOWN:
                reconciled = await self._reconcile_unknown_provisioning(
                    collection, record, owner_id
                )
                return self._serialize(reconciled)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning is still in progress",
            )

        try:
            provider_result = await self._cloudflare.get_custom_hostname(provider_id)
        except CloudflareServiceError as exc:
            if self._provider_not_found(exc):
                now = datetime.now(timezone.utc)
                applied, superseding_result = await self._write_refresh_observation(
                    collection,
                    record,
                    owner_id,
                    {
                        "$set": {
                            "status": "pending",
                            "provider_status": "not_found",
                            "ssl_status": "pending",
                            "ownership_verification": None,
                            "ownership_verification_http": None,
                            "ssl_validation_records": [],
                            "provider_missing_at": now,
                            "last_error": exc.message,
                            "updated_at": now,
                        },
                        "$unset": {
                            "provider_hostname_id": "",
                            "provisioning_absent_observations": "",
                            "provisioning_reconciled_at": "",
                            "provisioning_unknown_at": "",
                        },
                    },
                )
                if not applied:
                    return superseding_result
                missing = await collection.find_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "hostname": record.get("hostname"),
                        "provider_hostname_id": {"$exists": False},
                    }
                )
                return self._serialize(missing) if missing else None
            applied, superseding_result = await self._write_refresh_observation(
                collection,
                record,
                owner_id,
                {
                    "$set": {
                        "last_error": exc.message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if not applied:
                return superseding_result
            raise self._provider_http_error(exc) from exc

        provider_result_id = provider_result.get("id")
        try:
            provider_result_hostname = normalize_custom_hostname(
                provider_result.get("hostname"),
                platform_domains=self._platform_domains,
            )
        except (TypeError, ValueError):
            provider_result_hostname = None
        if provider_result_id != provider_id or provider_result_hostname != record.get(
            "hostname"
        ):
            applied, superseding_result = await self._write_refresh_observation(
                collection,
                record,
                owner_id,
                {
                    "$set": {
                        "last_error": (
                            "Cloudflare returned a mismatched hostname mapping"
                        ),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if not applied:
                return superseding_result
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned a mismatched custom-hostname result",
            )

        projection = self._provider_projection(provider_result)
        applied, superseding_result = await self._write_refresh_observation(
            collection,
            record,
            owner_id,
            {
                "$set": {
                    **projection,
                    "last_error": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not applied:
            return superseding_result
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved) if saved else None

    async def _disconnect_claim_record(
        self, collection: Any, record: dict, owner_id: str
    ) -> None:
        if (
            record.get("application_status") == PROVIDER_PROVISIONING
            and record.get("provider_create_attempt_id")
            and not record.get("provider_hostname_id")
        ):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_operation_in_progress",
                "This domain is still being provisioned at the provider.",
                "Wait for the current operation to finish, then retry disconnect.",
                retryable=True,
            )
        if record.get("provider_reconciliation_required") is True and not record.get(
            "provider_hostname_id"
        ):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_reconciliation_required",
                "This domain has an unresolved provider-create attempt.",
                "Support must reconcile the provider attempt before deletion.",
                retryable=False,
            )

        receipt_id = record.get("deletion_receipt_id") or uuid4().hex
        if record.get("deletion_status") == _LOCAL_CLEANUP_PENDING:
            await self._finish_local_cleanup(collection, record, owner_id)
            return

        if record.get("deletion_status") != _PROVIDER_DELETE_PENDING:
            deletion_attempt_id = uuid4().hex
            provider_delete_operation_id = self._provider_delete_operation_id(
                deletion_attempt_id
            )
            claimed = await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "revision": record.get("revision"),
                    "deletion_status": record.get("deletion_status"),
                    "provider_delete_operation_id": record.get(
                        "provider_delete_operation_id"
                    ),
                },
                {
                    "$set": {
                        "status": "deleting",
                        "application_status": DISCONNECTING,
                        "custom_route_enabled": False,
                        "action": "processing",
                        "deletion_status": _PROVIDER_DELETE_PENDING,
                        "deletion_attempt_id": deletion_attempt_id,
                        "deletion_receipt_id": receipt_id,
                        "provider_delete_operation_id": (provider_delete_operation_id),
                        "deletion_requested_at": record.get("deletion_requested_at")
                        or self._now(),
                        "last_error": None,
                        "retry_due_at": self._now(),
                        "updated_at": self._now(),
                    },
                    "$inc": {"revision": 1, "delete_attempts": 1},
                },
            )
            if not getattr(claimed, "matched_count", 0):
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "domain_changed_during_deletion",
                    "The custom-domain state changed during deletion.",
                    "Reload status before retrying.",
                    retryable=True,
                )
            record = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
        if not record:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_delete_state_unavailable",
                "The provider deletion state could not be read.",
                "Reload domain status before retrying.",
                retryable=True,
            )

        deletion_attempt_id = record.get("deletion_attempt_id")
        if not isinstance(deletion_attempt_id, str) or not deletion_attempt_id:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_delete_attempt_missing",
                "The provider deletion attempt is missing its receipt identity.",
                "Contact support before retrying this disconnect.",
                retryable=False,
            )
        expected_operation_id = self._provider_delete_operation_id(deletion_attempt_id)
        if record.get("provider_delete_operation_id") != expected_operation_id:
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "provider_delete_operation_mismatch",
                "The provider deletion attempt does not match its operation receipt.",
                "Contact support before retrying this disconnect.",
                retryable=False,
            )
        try:
            operation_id, provider_receipt = await self._delete_provider_with_receipt(
                record=record,
                owner_id=owner_id,
                deletion_attempt_id=deletion_attempt_id,
            )
        except CloudflareServiceError as exc:
            retry_error = self._error_detail(
                "provider_delete_failed",
                "The provider mapping could not be removed.",
                "Retry the disconnect later; the hostname is no longer routable in the application.",
                retryable=True,
                provider={
                    "name": "cloudflare",
                    "operation": "delete_custom_hostname",
                    "status_code": exc.provider_status_code,
                },
            )
            await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "deletion_status": _PROVIDER_DELETE_PENDING,
                    "deletion_attempt_id": deletion_attempt_id,
                    "provider_delete_operation_id": expected_operation_id,
                },
                {
                    "$set": {
                        "status": "delete_failed",
                        "application_status": DISCONNECT_FAILED,
                        "custom_route_enabled": False,
                        "action": "action_required",
                        "deletion_status": _PROVIDER_DELETE_RETRY_PENDING,
                        "last_error": retry_error,
                        "retry_due_at": self._now() + timedelta(minutes=5),
                        "updated_at": self._now(),
                    }
                },
            )
            raise self._provider_http_error(exc) from exc

        provider_deleted_at = self._now()
        advanced = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "deletion_status": _PROVIDER_DELETE_PENDING,
                "deletion_attempt_id": deletion_attempt_id,
                "provider_delete_operation_id": operation_id,
            },
            {
                "$set": {
                    "status": "provider_deleted",
                    "application_status": DISCONNECTED,
                    "provider_status": "deleted",
                    "provider_hostname_status": "deleted",
                    "ssl_status": "inactive",
                    "action": "processing",
                    "deletion_status": _LOCAL_CLEANUP_PENDING,
                    "provider_deleted_at": provider_deleted_at,
                    "provider_delete_operation_id": operation_id,
                    "provider_delete_receipt": provider_receipt,
                    "last_error": None,
                    "updated_at": provider_deleted_at,
                },
                "$unset": {
                    "deletion_attempt_id": "",
                    "retry_due_at": "",
                    "lease_expires_at": "",
                },
            },
        )
        if not getattr(advanced, "matched_count", 0):
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "domain_changed_after_provider_delete",
                "Provider deletion completed but local state changed.",
                "Contact support before reconnecting this hostname.",
                retryable=False,
            )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not saved:
            tombstone = await self._mongo.db["storefront_domain_tombstones"].find_one(
                {
                    "deletion_receipt_id": receipt_id,
                    "planner_id": owner_id,
                    "provider_delete_operation_id": operation_id,
                }
            )
            if tombstone:
                return
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_delete_cleanup_state_unavailable",
                "Provider deletion completed but local cleanup state could not be read.",
                "Contact support before reconnecting this hostname.",
                retryable=True,
            )
        await self._finish_local_cleanup(collection, saved, owner_id)

    async def _cancel_conflict_claim(self, record: dict, owner_id: str) -> None:
        if record.get("application_status") == DISCONNECTED:
            return
        now = self._now()
        cancelled = await self._mongo.db[
            "storefront_domain_conflict_claims"
        ].update_one(
            {
                "_id": record["_id"],
                "claimant_planner_id": owner_id,
                "attempt_id": record.get("attempt_id"),
                "revision": record.get("revision"),
            },
            {
                "$set": {
                    "status": "cancelled",
                    "application_status": DISCONNECTED,
                    "ownership_status": "cancelled",
                    "action": "none",
                    "last_error": None,
                    "cancelled_at": now,
                    "purge_at": now + _LIFECYCLE_RECEIPT_TTL,
                    "updated_at": now,
                },
                "$unset": {"current_owner_key": "", "retry_due_at": ""},
                "$inc": {"revision": 1},
            },
        )
        if not getattr(cancelled, "matched_count", 0):
            current = await self._mongo.db[
                "storefront_domain_conflict_claims"
            ].find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": record.get("attempt_id"),
                }
            )
            if current and current.get("application_status") == DISCONNECTED:
                return
            raise self._domain_http_error(
                status.HTTP_409_CONFLICT,
                "conflict_claim_changed",
                "The hostname ownership review changed during cancellation.",
                "Reload custom-domain status before retrying.",
                retryable=True,
            )

    async def disconnect(self, owner: Any, attempt_id: str | None = None) -> None:
        owner_id = self._owner_id(owner)
        collection = self._mongo.db["storefront_domains"]
        if attempt_id:
            conflict = await self._mongo.db[
                "storefront_domain_conflict_claims"
            ].find_one(
                {
                    "claimant_planner_id": owner_id,
                    "attempt_id": attempt_id,
                }
            )
            if conflict:
                await self._cancel_conflict_claim(conflict, owner_id)
                return None
            record = await collection.find_one(
                {"planner_id": owner_id, "claim_attempt_id": attempt_id}
            )
            if not record:
                raise self._domain_http_error(
                    status.HTTP_404_NOT_FOUND,
                    "domain_attempt_not_found",
                    "The custom-domain attempt could not be found.",
                    "Reload custom-domain status before trying again.",
                )
        else:
            record = await collection.find_one({"planner_id": owner_id})
            if not record:
                conflict = await self._mongo.db[
                    "storefront_domain_conflict_claims"
                ].find_one({"current_owner_key": owner_id})
                if conflict:
                    await self._cancel_conflict_claim(conflict, owner_id)
                return None
        if not record:
            return None

        if record.get("application_status"):
            await self._disconnect_claim_record(collection, record, owner_id)
            return None

        if (
            not record.get("provider_hostname_id")
            and self._status(record.get("status")) == _PROVISIONING
        ):
            record = await self._recover_stale_provisioning(
                collection, record, owner_id
            )
        if (
            not record.get("provider_hostname_id")
            and self._status(record.get("status")) == _PROVISIONING_UNKNOWN
        ):
            record = await self._reconcile_unknown_provisioning(
                collection, record, owner_id
            )
            if not record.get("provider_hostname_id"):
                if self._status(record.get("status")) == _PROVISIONING_UNKNOWN:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Custom-domain provisioning outcome is still being "
                            "reconciled"
                        ),
                    )
                deleted = await collection.delete_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "hostname": record.get("hostname"),
                        "provider_hostname_id": None,
                        "status": "pending",
                        "updated_at": record.get("updated_at"),
                    }
                )
                if getattr(deleted, "deleted_count", 0):
                    return None
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Custom-domain provisioning changed during disconnect",
                )

        if (
            record.get("deletion_status") == _LOCAL_CLEANUP_PENDING
            or self._status(record.get("status")) == "provider_deleted"
        ):
            await self._finish_local_cleanup(collection, record, owner_id)
            return None

        # Claim deletion intent locally before making an irreversible provider
        # call. The compare-and-set prevents two requests that read the same
        # state from both acting on the provider mapping.
        deletion_attempt_id = uuid4().hex
        provider_delete_operation_id = self._provider_delete_operation_id(
            deletion_attempt_id
        )
        claim_filter = {
            "_id": record["_id"],
            "planner_id": owner_id,
            "provider_hostname_id": record.get("provider_hostname_id"),
            "status": record.get("status"),
            "deletion_status": record.get("deletion_status"),
            "deletion_attempt_id": record.get("deletion_attempt_id"),
        }
        try:
            claimed = await collection.update_one(
                claim_filter,
                {
                    "$set": {
                        "status": "deleting",
                        "application_status": DISCONNECTING,
                        "custom_route_enabled": False,
                        "deletion_status": _PROVIDER_DELETE_PENDING,
                        "deletion_attempt_id": deletion_attempt_id,
                        "provider_delete_operation_id": (provider_delete_operation_id),
                        "deletion_requested_at": record.get("deletion_requested_at")
                        or self._now(),
                        "last_error": None,
                        "retry_due_at": self._now(),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$inc": {"delete_attempts": 1},
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain deletion could not be reserved",
            ) from exc
        if not getattr(claimed, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if not current:
                return None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain mapping changed during deletion",
            )

        claimed_record = await collection.find_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "deletion_status": _PROVIDER_DELETE_PENDING,
                "deletion_attempt_id": deletion_attempt_id,
                "provider_delete_operation_id": provider_delete_operation_id,
            }
        )
        if not claimed_record:
            raise self._domain_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "provider_delete_state_unavailable",
                "The provider deletion state could not be read.",
                "Reload domain status before retrying.",
                retryable=True,
            )
        try:
            operation_id, provider_receipt = await self._delete_provider_with_receipt(
                record=claimed_record,
                owner_id=owner_id,
                deletion_attempt_id=deletion_attempt_id,
            )
        except CloudflareServiceError as exc:
            retry_error = self._error_detail(
                "provider_delete_failed",
                "The provider mapping could not be removed.",
                "Retry the disconnect later; the hostname is no longer routable in the application.",
                retryable=True,
                provider={
                    "name": "cloudflare",
                    "operation": "delete_custom_hostname",
                    "status_code": exc.provider_status_code,
                },
            )
            try:
                await collection.update_one(
                    {
                        "_id": record["_id"],
                        "planner_id": owner_id,
                        "deletion_status": _PROVIDER_DELETE_PENDING,
                        "deletion_attempt_id": deletion_attempt_id,
                        "provider_delete_operation_id": (provider_delete_operation_id),
                    },
                    {
                        "$set": {
                            "status": "delete_failed",
                            "application_status": DISCONNECT_FAILED,
                            "custom_route_enabled": False,
                            "action": "action_required",
                            "deletion_status": _PROVIDER_DELETE_RETRY_PENDING,
                            "last_error": retry_error,
                            "retry_due_at": self._now() + timedelta(minutes=5),
                            "updated_at": datetime.now(timezone.utc),
                        },
                        "$unset": {"deletion_attempt_id": ""},
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to persist custom-domain delete retry for owner %s",
                    owner_id,
                )
            raise self._provider_http_error(exc) from exc

        # Provider success is durable before local cleanup. If Mongo cleanup
        # fails, retries can skip the already-completed external deletion.
        provider_deleted_at = datetime.now(timezone.utc)
        try:
            persisted = await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "deletion_status": _PROVIDER_DELETE_PENDING,
                    "deletion_attempt_id": deletion_attempt_id,
                    "provider_delete_operation_id": operation_id,
                },
                {
                    "$set": {
                        "status": "provider_deleted",
                        "provider_status": "deleted",
                        "ssl_status": "inactive",
                        "deletion_status": _LOCAL_CLEANUP_PENDING,
                        "provider_deleted_at": provider_deleted_at,
                        "provider_delete_operation_id": operation_id,
                        "provider_delete_receipt": provider_receipt,
                        "last_error": None,
                        "updated_at": provider_deleted_at,
                    },
                    "$unset": {"deletion_attempt_id": ""},
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Custom-domain provider deletion succeeded but local state "
                    "could not be advanced"
                ),
            ) from exc
        if not getattr(persisted, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if not current:
                return None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain mapping changed after provider deletion",
            )

        await self._finish_local_cleanup(
            collection,
            {
                **record,
                "status": "provider_deleted",
                "deletion_status": _LOCAL_CLEANUP_PENDING,
                "provider_deleted_at": provider_deleted_at,
                "provider_delete_operation_id": operation_id,
                "provider_delete_receipt": provider_receipt,
            },
            owner_id,
        )
        return None

    async def _finish_local_cleanup(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
    ) -> None:
        receipt_id = record.get("deletion_receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id:
            receipt_id = uuid4().hex
            receipt_write = await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "status": "provider_deleted",
                    "deletion_status": _LOCAL_CLEANUP_PENDING,
                },
                {
                    "$set": {
                        "deletion_receipt_id": receipt_id,
                        "updated_at": self._now(),
                    }
                },
            )
            if not getattr(receipt_write, "matched_count", 0):
                raise self._domain_http_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "deletion_receipt_not_reserved",
                    "Provider deletion completed but its receipt could not be reserved.",
                    "Contact support before reconnecting this hostname.",
                    retryable=True,
                )
            record = {**record, "deletion_receipt_id": receipt_id}

        now = self._now()
        cleanup_records = [
            {
                "type": "TXT",
                "name": f"_tsw-storefront.{record.get('hostname')}",
                "value": None,
                "ttl": 300,
                "purpose": "remove_application_ownership",
            },
        ]
        expected_records = record.get("expected_records") or []
        routing_was_requested = bool(record.get("provider_hostname_id")) or any(
            isinstance(expected, dict) and expected.get("type") == "CNAME"
            for expected in expected_records
        )
        if routing_was_requested:
            cleanup_records.append(
                {
                    "type": "CNAME",
                    "name": record.get("hostname"),
                    "value": record.get("cname_target") or self._cname_target,
                    "ttl": 300,
                    "purpose": "remove_storefront_routing",
                }
            )
        tombstone = {
            "deletion_receipt_id": receipt_id,
            "domain_id": str(record["_id"]),
            "planner_id": owner_id,
            "hostname": record.get("hostname"),
            "provider": record.get("provider") or "cloudflare",
            "registrar": record.get("registrar") or "unknown",
            "provider_hostname_id": record.get("provider_hostname_id"),
            "provider_delete_operation_id": record.get("provider_delete_operation_id"),
            "provider_delete_receipt": record.get("provider_delete_receipt"),
            "cname_target": record.get("cname_target") or self._cname_target,
            "cleanup_records": cleanup_records,
            "provider_deleted_at": record.get("provider_deleted_at") or now,
            "deleted_at": now,
            "deletion_requested_at": record.get("deletion_requested_at"),
            "expires_at": now + _LIFECYCLE_RECEIPT_TTL,
        }
        tombstones = self._mongo.db["storefront_domain_tombstones"]
        try:
            await tombstones.insert_one(tombstone)
        except DuplicateKeyError:
            existing_receipt = await tombstones.find_one(
                {"deletion_receipt_id": receipt_id}
            )
            if (
                not existing_receipt
                or existing_receipt.get("planner_id") != owner_id
                or existing_receipt.get("hostname") != record.get("hostname")
                or existing_receipt.get("provider_hostname_id")
                != record.get("provider_hostname_id")
                or existing_receipt.get("provider_delete_operation_id")
                != record.get("provider_delete_operation_id")
                or existing_receipt.get("provider_delete_receipt")
                != record.get("provider_delete_receipt")
            ):
                raise self._domain_http_error(
                    status.HTTP_409_CONFLICT,
                    "deletion_receipt_conflict",
                    "The deletion receipt conflicts with another lifecycle record.",
                    "Contact support before reconnecting this hostname.",
                    retryable=False,
                )

        cleanup_filter = {
            "_id": record["_id"],
            "planner_id": owner_id,
            "status": "provider_deleted",
            "deletion_status": _LOCAL_CLEANUP_PENDING,
        }
        try:
            deleted = await collection.delete_one(cleanup_filter)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Custom-domain provider mapping was deleted; local cleanup "
                    "is pending"
                ),
            ) from exc
        if getattr(deleted, "deleted_count", 0):
            return
        remaining = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not remaining:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Custom-domain provider mapping was deleted; local cleanup is pending"
            ),
        )

    async def resolve_active_hostname(self, raw_hostname: str) -> dict | None:
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except (TypeError, ValueError):
            return None

        record = await self._mongo.db["storefront_domains"].find_one(
            {
                "hostname": hostname,
                "status": "active",
                "application_status": {"$in": [ACTIVE, DEPLOYING]},
                "custom_route_enabled": True,
                "ownership_status": "verified",
                "routing_dns_status": "verified",
                "provider_status": "active",
                "provider_hostname_status": "active",
                "ssl_status": "active",
                "https_status": "verified",
                "deletion_status": None,
            }
        )
        if not record:
            return None
        owner_id = normalize_planner_id(record.get("planner_id"))
        if not owner_id:
            return None
        return {"planner_id": owner_id, "hostname": hostname}


storefront_domain_service = StorefrontDomainService()
