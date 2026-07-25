"""Safe Domain Connect discovery, signing, and synchronous-flow receipts."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import secrets
import socket
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
import idna
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException, status

from app.constants.roles import is_wedding_planner_role
from app.constants.storefront_domain import (
    ACTION_REQUIRED,
    AUTHORIZATION_CANCELLED,
    AUTHORIZATION_PENDING,
    DNS_SETUP_PENDING,
)
from app.core.database import mongo
from app.core.settings import settings
from app.services.config_validator import get_storefront_domain_readiness
from app.services.storefront_dns_service import (
    StorefrontDnsResolver,
    storefront_dns_resolver,
)
from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy
from app.services.storefront_domain_service import (
    require_storefront_domain_mutation_allowed,
    storefront_domain_mutation_cas_filter,
)
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
    storefront_entitlement_service,
)
from app.utils.planner_ownership import normalize_planner_id

_FLOW_TTL = timedelta(minutes=20)
_MAX_DISCOVERY_REDIRECTS = 3
_MAX_DISCOVERY_BYTES = 64 * 1024
_INTERNAL_SUFFIXES = (".internal", ".localhost", ".local", ".lan", ".home")
_CALLBACK_ERRORS = frozenset(
    {
        "invalid_request",
        "unauthorized_client",
        "access_denied",
        "unsupported_response_type",
        "invalid_scope",
        "server_error",
        "temporarily_unavailable",
    }
)
_APPROVED_CNAME_TARGET = "domains.thespecialwedding.com"


class DomainConnectDiscoveryError(RuntimeError):
    """Safe discovery failure that never includes a caller-controlled URL."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DomainConnectAddressResolver(Protocol):
    async def resolve(self, hostname: str) -> list[str]: ...


class DomainConnectHttpTransport(Protocol):
    async def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


class SystemDomainConnectAddressResolver:
    """Resolve every outbound hostname so unsafe address classes fail closed."""

    async def resolve(self, hostname: str) -> list[str]:
        try:
            answers = await asyncio.get_running_loop().getaddrinfo(
                hostname,
                443,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise DomainConnectDiscoveryError(
                "domain_connect_dns_unavailable",
                "The DNS provider discovery host could not be resolved.",
            ) from exc
        return sorted({answer[4][0] for answer in answers})


class DomainConnectDiscovery:
    """Perform bounded, SSRF-resistant synchronous Domain Connect discovery."""

    def __init__(
        self,
        *,
        dns_resolver: StorefrontDnsResolver | None = None,
        address_resolver: DomainConnectAddressResolver | None = None,
        http_transport: DomainConnectHttpTransport | None = None,
        discovery_enabled: bool | None = None,
        provider_id: str | None = None,
        service_id: str | None = None,
        template_version: int | None = None,
        allowed_dns_provider_ids: set[str] | None = None,
        allowed_discovery_hosts: set[str] | None = None,
        allowed_sync_hosts: set[str] | None = None,
        allowed_api_hosts: set[str] | None = None,
        allowed_control_panel_hosts: set[str] | None = None,
        timeout_seconds: float = 5.0,
        max_response_bytes: int = _MAX_DISCOVERY_BYTES,
        max_redirects: int = _MAX_DISCOVERY_REDIRECTS,
    ) -> None:
        self._dns = dns_resolver or storefront_dns_resolver
        self._addresses = address_resolver or SystemDomainConnectAddressResolver()
        self._transport = http_transport
        self._discovery_enabled = (
            settings.storefront_domain_connect_discovery_enabled
            if discovery_enabled is None
            else discovery_enabled
        )
        self._provider_id = provider_id or settings.domain_connect_provider_id
        self._service_id = service_id or settings.domain_connect_service_id
        self._template_version = (
            settings.domain_connect_template_version
            if template_version is None
            else template_version
        )
        self._allowed_dns_provider_ids = allowed_dns_provider_ids or {"cloudflare.com"}
        self._allowed_discovery_hosts = allowed_discovery_hosts or {
            "domainconnect.cloudflare.com"
        }
        self._allowed_sync_hosts = allowed_sync_hosts or {
            "domainconnect.cloudflare.com"
        }
        self._allowed_api_hosts = allowed_api_hosts or {
            "api.domainconnect.cloudflare.com"
        }
        self._allowed_control_panel_hosts = allowed_control_panel_hosts or {
            "dash.cloudflare.com"
        }
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects

    @staticmethod
    def _ascii_hostname(hostname: str) -> str:
        try:
            return (
                idna.encode(
                    hostname.rstrip("."),
                    uts46=True,
                    std3_rules=True,
                    transitional=False,
                )
                .decode("ascii")
                .lower()
            )
        except idna.IDNAError as exc:
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an unsafe discovery destination.",
            ) from exc

    async def _validate_destination(self, raw_url: str) -> str:
        candidate = raw_url.strip()
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        try:
            split = urlsplit(candidate)
            port = split.port
        except ValueError as exc:
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an unsafe discovery destination.",
            ) from exc
        if (
            split.scheme.lower() != "https"
            or not split.hostname
            or split.username is not None
            or split.password is not None
            or port not in {None, 443}
            or split.fragment
        ):
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an unsafe discovery destination.",
            )
        hostname = self._ascii_hostname(split.hostname)
        if hostname == "localhost" or hostname.endswith(_INTERNAL_SUFFIXES):
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an unsafe discovery destination.",
            )
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "IP-literal discovery destinations are not allowed.",
            )

        addresses = await self._addresses.resolve(hostname)
        if not addresses:
            raise DomainConnectDiscoveryError(
                "domain_connect_dns_unavailable",
                "The DNS provider discovery host could not be resolved.",
            )
        try:
            parsed_addresses = [ipaddress.ip_address(value) for value in addresses]
        except ValueError as exc:
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an invalid network destination.",
            ) from exc
        if any(not address.is_global for address in parsed_addresses):
            raise DomainConnectDiscoveryError(
                "unsafe_domain_connect_destination",
                "The DNS provider returned an unsafe network destination.",
            )

        normalized_netloc = hostname if port is None else f"{hostname}:443"
        return urlunsplit(
            ("https", normalized_netloc, split.path or "", split.query or "", "")
        )

    async def _send(
        self,
        url: str,
        *,
        hostname: str,
        addresses: list[str],
    ) -> Any:
        if self._transport is not None:
            return await self._transport.request(
                "GET",
                url,
                timeout=self._timeout_seconds,
                follow_redirects=False,
                headers={"Accept": "application/json"},
            )
        split = urlsplit(url)
        last_error: httpx.RequestError | None = None
        async with httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for address in addresses:
                ip = ipaddress.ip_address(address)
                netloc = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
                pinned_url = urlunsplit(("https", netloc, split.path, split.query, ""))
                try:
                    return await client.request(
                        "GET",
                        pinned_url,
                        timeout=self._timeout_seconds,
                        headers={"Accept": "application/json", "Host": hostname},
                        extensions={"sni_hostname": hostname},
                    )
                except httpx.RequestError as exc:
                    last_error = exc
        if last_error is not None:
            raise last_error
        raise DomainConnectDiscoveryError(
            "domain_connect_dns_unavailable",
            "The DNS provider discovery host could not be resolved.",
        )

    async def _request(self, raw_url: str, *, allowed_hosts: set[str]) -> Any:
        current = raw_url
        for redirect_count in range(self._max_redirects + 1):
            safe_url = await self._validate_destination(current)
            safe_hostname = str(urlsplit(safe_url).hostname)
            if safe_hostname not in allowed_hosts:
                raise DomainConnectDiscoveryError(
                    "domain_connect_provider_not_allowed",
                    "The DNS provider returned an unapproved service destination.",
                )
            addresses = await self._addresses.resolve(safe_hostname)
            try:
                parsed_addresses = [ipaddress.ip_address(value) for value in addresses]
            except ValueError as exc:
                raise DomainConnectDiscoveryError(
                    "unsafe_domain_connect_destination",
                    "The DNS provider returned an invalid network destination.",
                ) from exc
            if not parsed_addresses or any(
                not address.is_global for address in parsed_addresses
            ):
                raise DomainConnectDiscoveryError(
                    "unsafe_domain_connect_destination",
                    "The DNS provider returned an unsafe network destination.",
                )
            try:
                response = await self._send(
                    safe_url,
                    hostname=safe_hostname,
                    addresses=[address.compressed for address in parsed_addresses],
                )
            except (TimeoutError, httpx.RequestError) as exc:
                raise DomainConnectDiscoveryError(
                    "domain_connect_request_failed",
                    "The DNS provider discovery request could not be completed.",
                ) from exc
            content = bytes(getattr(response, "content", b""))
            if len(content) > self._max_response_bytes:
                raise DomainConnectDiscoveryError(
                    "domain_connect_response_too_large",
                    "The DNS provider discovery response exceeded the safety limit.",
                )
            response_status = int(getattr(response, "status_code", 0))
            if response_status not in {301, 302, 303, 307, 308}:
                return response
            if redirect_count >= self._max_redirects:
                raise DomainConnectDiscoveryError(
                    "domain_connect_redirect_limit",
                    "The DNS provider discovery request redirected too many times.",
                )
            headers = getattr(response, "headers", None) or {}
            location = headers.get("location") or headers.get("Location")
            if not isinstance(location, str) or not location:
                raise DomainConnectDiscoveryError(
                    "domain_connect_invalid_redirect",
                    "The DNS provider returned an invalid redirect.",
                )
            current = urljoin(safe_url, location)
        raise AssertionError("redirect loop bound is unreachable")

    async def _request_json(
        self, raw_url: str, *, allowed_hosts: set[str]
    ) -> tuple[int, object]:
        response = await self._request(raw_url, allowed_hosts=allowed_hosts)
        response_status = int(getattr(response, "status_code", 0))
        if not 200 <= response_status < 300:
            return response_status, None
        try:
            return response_status, response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DomainConnectDiscoveryError(
                "domain_connect_invalid_response",
                "The DNS provider returned an unreadable discovery response.",
            ) from exc

    async def discover(self, zone: str) -> dict[str, Any]:
        if not self._discovery_enabled:
            return {"supported": False, "reason_code": "discovery_disabled"}
        try:
            normalized_zone = self._ascii_hostname(zone)
            discovery_values = await self._dns.query(
                f"_domainconnect.{normalized_zone}", "TXT"
            )
        except DomainConnectDiscoveryError:
            raise
        except Exception as exc:
            raise DomainConnectDiscoveryError(
                "domain_connect_dns_unavailable",
                "The DNS provider discovery record could not be checked.",
            ) from exc
        if len(discovery_values) != 1:
            return {
                "supported": False,
                "reason_code": "discovery_record_not_found",
            }

        prefix = await self._validate_destination(discovery_values[0])
        if urlsplit(prefix).hostname not in self._allowed_discovery_hosts:
            return {"supported": False, "reason_code": "provider_not_allowed"}
        settings_url = (
            f"{prefix.rstrip('/')}/v2/{quote(normalized_zone, safe='')}/settings"
        )
        settings_status, provider_settings = await self._request_json(
            settings_url,
            allowed_hosts=self._allowed_discovery_hosts,
        )
        if settings_status == 404 or not isinstance(provider_settings, dict):
            return {"supported": False, "reason_code": "settings_not_found"}
        provider_id = provider_settings.get("providerId")
        if provider_id not in self._allowed_dns_provider_ids:
            return {"supported": False, "reason_code": "provider_not_allowed"}

        sync_url = provider_settings.get("urlSyncUX")
        api_url = provider_settings.get("urlAPI")
        if not isinstance(sync_url, str) or not isinstance(api_url, str):
            return {"supported": False, "reason_code": "sync_flow_not_supported"}
        safe_sync_url = await self._validate_destination(sync_url)
        safe_api_url = await self._validate_destination(api_url)
        sync_parts = urlsplit(safe_sync_url)
        api_parts = urlsplit(safe_api_url)
        if (
            sync_parts.hostname not in self._allowed_sync_hosts
            or api_parts.hostname not in self._allowed_api_hosts
            or sync_parts.path not in {"", "/"}
            or api_parts.path not in {"", "/"}
            or sync_parts.query
            or api_parts.query
        ):
            return {"supported": False, "reason_code": "provider_not_allowed"}
        support_url = (
            f"{safe_api_url.rstrip('/')}/v2/domainTemplates/providers/"
            f"{quote(self._provider_id, safe='')}/services/"
            f"{quote(self._service_id, safe='')}"
        )
        support_status, template = await self._request_json(
            support_url,
            allowed_hosts=self._allowed_api_hosts,
        )
        version = template.get("version") if isinstance(template, dict) else None
        if support_status != 200 or version != self._template_version:
            return {
                "supported": False,
                "reason_code": "exact_template_not_supported",
                "provider_id": provider_id,
                "provider_name": provider_settings.get("providerDisplayName")
                or provider_settings.get("providerName"),
            }
        control_panel_url = provider_settings.get("urlControlPanel")
        if isinstance(control_panel_url, str):
            try:
                control_panel_url = await self._validate_destination(control_panel_url)
            except DomainConnectDiscoveryError:
                control_panel_url = None
            if (
                control_panel_url
                and urlsplit(control_panel_url).hostname
                not in self._allowed_control_panel_hosts
            ):
                control_panel_url = None
        else:
            control_panel_url = None
        return {
            "supported": True,
            "reason_code": "supported",
            "provider_id": provider_id,
            "provider_name": provider_settings.get("providerDisplayName")
            or provider_settings.get("providerName"),
            "url_sync_ux": safe_sync_url,
            "url_api": safe_api_url,
            "control_panel_url": control_panel_url,
            "template_version": version,
        }


class StorefrontDomainConnectService:
    """Persist one-time signed synchronous Domain Connect authorization flows."""

    def __init__(
        self,
        *,
        mongo_client: Any | None = None,
        entitlement_service: StorefrontEntitlementService | None = None,
        discovery_service: DomainConnectDiscovery | None = None,
        private_key_pem: str | None = None,
        provider_id: str | None = None,
        service_id: str | None = None,
        template_version: int | None = None,
        key_id: str | None = None,
        callback_url: str | None = None,
        cname_target: str | None = None,
        authorization_enabled: bool | None = None,
        readiness_resolver: Callable[[], dict[str, object]] | None = None,
        claim_token_reader: Callable[[dict], str | None] | None = None,
        record_serializer: Callable[[dict], dict] | None = None,
        now: Callable[[], datetime] | None = None,
        rollout_policy: StorefrontDomainRolloutPolicy | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._entitlements = entitlement_service or storefront_entitlement_service
        self._discovery = discovery_service or domain_connect_discovery
        self._private_key_pem = (
            settings.domain_connect_private_key
            if private_key_pem is None
            else private_key_pem
        )
        self._provider_id = provider_id or settings.domain_connect_provider_id
        self._service_id = service_id or settings.domain_connect_service_id
        self._template_version = (
            settings.domain_connect_template_version
            if template_version is None
            else template_version
        )
        self._key_id = key_id or settings.domain_connect_key_id
        self._callback_url = (
            settings.domain_connect_callback_url
            if callback_url is None
            else callback_url
        )
        self._cname_target = (
            settings.storefront_cname_target if cname_target is None else cname_target
        )
        self._authorization_enabled = (
            settings.storefront_domain_connect_authorization_enabled
            if authorization_enabled is None
            else authorization_enabled
        )
        self._readiness = readiness_resolver or get_storefront_domain_readiness
        self._claim_token_reader = claim_token_reader
        self._record_serializer = record_serializer
        self._now = now or (lambda: datetime.now(UTC))
        self._rollout_policy = (
            rollout_policy or StorefrontDomainRolloutPolicy.from_settings()
        )

    @staticmethod
    def _error(
        status_code: int,
        code: str,
        message: str,
        customer_action: str,
        *,
        retryable: bool = False,
    ) -> HTTPException:
        return HTTPException(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "customer_action": customer_action,
                "retryable": retryable,
                "support_id": f"sfd_{uuid4().hex[:16]}",
            },
        )

    @staticmethod
    def _owner_data(owner: Any) -> dict:
        if isinstance(owner, dict):
            return dict(owner)
        user_data = dict(getattr(owner, "user_data", None) or {})
        role = getattr(owner, "role", None)
        if role:
            user_data["role"] = role
        return user_data

    @classmethod
    def _owner_id(cls, owner: Any) -> str:
        data = cls._owner_data(owner)
        owner_id = normalize_planner_id(data.get("_id"))
        if not owner_id or not is_wedding_planner_role(data.get("role")):
            raise cls._error(
                status.HTTP_403_FORBIDDEN,
                "storefront_owner_required",
                "Planner-owner access is required.",
                "Sign in as the planner who owns this storefront.",
            )
        return owner_id

    async def _require_activation_capability(self, owner: Any) -> str:
        owner_data = self._owner_data(owner)
        owner_id = self._owner_id(owner_data)
        try:
            entitlement = await self._entitlements.resolve_for_owner(owner_data)
        except StorefrontEntitlementResolutionError as exc:
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "custom_domain_entitlement_unavailable",
                "Custom-domain eligibility could not be checked.",
                "Keep using the platform storefront URL and retry later.",
                retryable=True,
            ) from exc
        if not (entitlement.storefront_enabled and entitlement.custom_domain_enabled):
            raise self._error(
                status.HTTP_403_FORBIDDEN,
                "custom_domain_not_entitled",
                "Custom-domain activation is not included in the current plan.",
                "Upgrade the planner plan to start or resume activation.",
            )
        return owner_id

    def _require_authorization_configuration(self) -> None:
        if not self._authorization_enabled:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_connect_unavailable",
                "Automatic DNS setup is not available.",
                "Use the manual DNS setup instructions instead.",
            )
        readiness = self._readiness()
        if readiness.get("enabled") is not True:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "custom_domain_configuration_unavailable",
                "Custom domains are not currently available.",
                "Keep using the platform storefront URL.",
            )
        if not all(
            isinstance(value, str) and bool(value.strip())
            for value in (
                self._private_key_pem,
                self._provider_id,
                self._service_id,
                self._key_id,
                self._callback_url,
                self._cname_target,
            )
        ):
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_connect_configuration_unavailable",
                "Automatic DNS authorization is not configured.",
                "Use manual DNS setup and contact support if this persists.",
                retryable=True,
            )
        if str(self._cname_target).rstrip(".").lower() != _APPROVED_CNAME_TARGET:
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_connect_template_target_mismatch",
                "Automatic DNS authorization does not match the approved template.",
                "Use manual DNS setup and contact support.",
                retryable=True,
            )

    def _claim_token(self, record: dict) -> str | None:
        if self._claim_token_reader is not None:
            return self._claim_token_reader(record)
        from app.services.storefront_domain_service import storefront_domain_service

        return storefront_domain_service._decrypt_claim_token(record)

    def _serialize_record(self, record: dict) -> dict:
        if self._record_serializer is not None:
            return self._record_serializer(record)
        from app.services.storefront_domain_service import storefront_domain_service

        return storefront_domain_service._serialize(record)

    @staticmethod
    def _flow_matches_current_authorization(flow: dict, record: dict) -> bool:
        """Bind a provider result to the exact domain phase it authorized.

        A Domain Connect callback may arrive after a manual verification, a
        retry, or provider provisioning has already advanced the domain.  The
        flow's revision is the compare-and-swap fence that prevents that late
        result from moving the canonical domain record backwards.
        """

        flow_revision = flow.get("domain_revision")
        record_revision = record.get("revision")
        return (
            isinstance(flow_revision, int)
            and not isinstance(flow_revision, bool)
            and isinstance(record_revision, int)
            and not isinstance(record_revision, bool)
            and flow_revision == record_revision
            and record.get("application_status") == AUTHORIZATION_PENDING
        )

    @staticmethod
    def _authorized_completion_was_applied(flow: dict, record: dict) -> bool:
        """Recognize the durable domain write after a crash before flow consume."""

        flow_revision = flow.get("domain_revision")
        record_revision = record.get("revision")
        return (
            flow.get("state") == "completing"
            and isinstance(flow_revision, int)
            and not isinstance(flow_revision, bool)
            and isinstance(record_revision, int)
            and not isinstance(record_revision, bool)
            and record_revision == flow_revision + 1
            and record.get("claim_attempt_id") == flow.get("attempt_id")
            and record.get("application_status") == DNS_SETUP_PENDING
            and record.get("provider_hostname_id") is None
            and record.get("deletion_status") is None
        )

    async def _consume_flow(
        self,
        flow: dict,
        owner_id: str,
        *,
        outcome: str,
        current_record: dict | None = None,
    ) -> None:
        """Consume only the exact flow revision, never a restarted flow."""

        now = self._now()
        fields: dict[str, Any] = {
            "state": "consumed",
            "completion_outcome": outcome,
            "consumed_at": now,
            "updated_at": now,
        }
        if outcome == "superseded" and current_record is not None:
            fields.update(
                {
                    "superseded_at": now,
                    "superseded_by_domain_revision": current_record.get("revision"),
                    "superseded_by_application_status": current_record.get(
                        "application_status"
                    ),
                }
            )
        await self._mongo.db["storefront_domain_flows"].update_one(
            {
                "_id": flow["_id"],
                "planner_id": owner_id,
                "domain_revision": flow.get("domain_revision"),
                "state": {"$ne": "consumed"},
            },
            {"$set": fields},
        )

    async def _consume_superseded_flow(
        self,
        flow: dict,
        owner_id: str,
        record: dict,
    ) -> dict:
        await self._consume_flow(
            flow,
            owner_id,
            outcome="superseded",
            current_record=record,
        )
        current = await self._mongo.db["storefront_domains"].find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize_record(current or record)

    def _load_private_key(self) -> rsa.RSAPrivateKey:
        try:
            key = serialization.load_pem_private_key(
                str(self._private_key_pem).encode(), password=None
            )
        except (TypeError, ValueError) as exc:
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_connect_signing_unavailable",
                "Automatic DNS authorization cannot be signed.",
                "Use manual DNS setup and contact support.",
                retryable=True,
            ) from exc
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_connect_signing_unavailable",
                "Automatic DNS authorization cannot be signed.",
                "Use manual DNS setup and contact support.",
                retryable=True,
            )
        return key

    def _callback_redirect(self, flow_token: str) -> str:
        split = urlsplit(str(self._callback_url))
        if (
            split.scheme != "https"
            or not split.hostname
            or split.username is not None
            or split.password is not None
            or split.port not in {None, 443}
            or split.fragment
            or split.query
        ):
            raise self._error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "domain_connect_callback_unavailable",
                "Automatic DNS authorization has no safe callback.",
                "Use manual DNS setup and contact support.",
                retryable=True,
            )
        return (
            f"{self._callback_url}?{urlencode({'flow': flow_token}, quote_via=quote)}"
        )

    def _authorization_url(
        self,
        *,
        sync_url: str,
        domain: str,
        host: str,
        redirect_uri: str,
        verification_token: str,
    ) -> str:
        signed_pairs = [
            ("domain", domain),
            ("host", host),
            ("redirect_uri", redirect_uri),
            ("verificationToken", verification_token),
        ]
        canonical = urlencode(signed_pairs, quote_via=quote, safe="")
        signature = self._load_private_key().sign(
            canonical.encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        signature_value = base64.b64encode(signature).decode()
        path = (
            f"/v2/domainTemplates/providers/{quote(self._provider_id, safe='')}"
            f"/services/{quote(self._service_id, safe='')}/apply"
        )
        return (
            f"{sync_url.rstrip('/')}{path}?{canonical}"
            f"&key={quote(self._key_id, safe='')}"
            f"&sig={quote(signature_value, safe='')}"
        )

    async def start(self, owner: Any, attempt_id: str) -> dict[str, str]:
        owner_id = await self._require_activation_capability(owner)
        self._require_authorization_configuration()
        domains = self._mongo.db["storefront_domains"]
        record = await domains.find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_claim_not_found",
                "The current custom-domain claim could not be found.",
                "Restart domain setup and use its current attempt.",
            )
        require_storefront_domain_mutation_allowed(record, self._error)
        if record.get("provider_hostname_id"):
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_claim_not_found",
                "The current custom-domain claim could not be found.",
                "Restart domain setup and use its current attempt.",
            )
        if record.get("setup_method") != "automatic":
            raise self._error(
                status.HTTP_409_CONFLICT,
                "automatic_setup_not_selected",
                "Automatic setup was not selected for this domain attempt.",
                "Return to domain setup and choose automatic setup first.",
            )
        if record.get("domain_connect_authorized_at"):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_connect_already_authorized",
                "This DNS provider authorization has already been completed.",
                "Review the connection progress instead of starting authorization again.",
            )
        claim_expires_at = self._aware(record.get("claim_expires_at"))
        if not claim_expires_at or claim_expires_at <= self._now():
            raise self._error(
                status.HTTP_410_GONE,
                "domain_claim_expired",
                "The current DNS ownership challenge has expired.",
                "Restart domain setup before authorizing DNS changes.",
            )
        if record.get("intent") == "migration":
            raise self._error(
                status.HTTP_409_CONFLICT,
                "automatic_migration_requires_prevalidation",
                "Automatic cutover is not available for a live-site migration.",
                "Use the assisted migration instructions to pre-validate before cutover.",
            )
        authoritative = record.get("authoritative_dns")
        zone = authoritative.get("zone") if isinstance(authoritative, dict) else None
        hostname = record.get("hostname")
        if (
            not isinstance(zone, str)
            or not isinstance(hostname, str)
            or not hostname.endswith(f".{zone}")
        ):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_claim_invalid",
                "The domain claim has no valid authoritative DNS zone.",
                "Restart domain setup or contact support.",
            )
        if not self._rollout_policy.allows(owner_id, hostname):
            raise self._error(
                status.HTTP_403_FORBIDDEN,
                "domain_connect_rollout_unavailable",
                "Automatic DNS setup is not available for this storefront yet.",
                "Use the platform storefront URL while the production pilot is restricted.",
            )
        discovery = await self._discovery.discover(zone)
        if discovery.get("supported") is not True:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_connect_not_supported",
                "This DNS provider does not advertise the exact approved template.",
                "Use the manual DNS setup instructions.",
            )
        verification_token = self._claim_token(record)
        if not verification_token:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_claim_material_unavailable",
                "The current ownership challenge cannot be authorized safely.",
                "Restart domain setup or contact support.",
            )

        flow_token = secrets.token_urlsafe(32)
        flow_digest = hashlib.sha256(flow_token.encode()).hexdigest()
        redirect_uri = self._callback_redirect(flow_token)
        host = hostname.removesuffix(f".{zone}")
        authorization_url = self._authorization_url(
            sync_url=str(discovery["url_sync_ux"]),
            domain=zone,
            host=host,
            redirect_uri=redirect_uri,
            verification_token=verification_token,
        )
        now = self._now()
        flow_expires_at = now + _FLOW_TTL
        revision = int(record.get("revision") or 0)
        phase_update = await domains.update_one(
            {
                **storefront_domain_mutation_cas_filter(record, owner_id),
                "provider_hostname_id": None,
            },
            {
                "$set": {
                    "application_status": AUTHORIZATION_PENDING,
                    "action": "processing",
                    "domain_connect_provider": discovery.get("provider_name"),
                    "domain_connect_supported": True,
                    "last_error": None,
                    "retry_due_at": flow_expires_at,
                    "updated_at": now,
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(phase_update, "matched_count", 0):
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_claim_changed",
                "The domain claim changed while authorization was starting.",
                "Reload domain status before retrying.",
                retryable=True,
            )
        flow_id = f"dcf_{uuid4().hex}"
        await self._mongo.db["storefront_domain_flows"].update_one(
            {
                "domain_id": str(record["_id"]),
                "attempt_id": attempt_id,
            },
            {
                "$set": {
                    "flow_id": flow_id,
                    "planner_id": owner_id,
                    "hostname_hash": hashlib.sha256(hostname.encode()).hexdigest(),
                    "state": "authorization_pending",
                    "flow_token_digest": flow_digest,
                    "domain_revision": revision + 1,
                    "provider_id": discovery.get("provider_id"),
                    "template_version": self._template_version,
                    "expires_at": flow_expires_at,
                    "updated_at": now,
                    "created_at": now,
                },
                "$unset": {
                    "callback_recorded_at": "",
                    "consumed_at": "",
                    "completion_outcome": "",
                    "superseded_at": "",
                    "superseded_by_domain_revision": "",
                    "superseded_by_application_status": "",
                    "last_error": "",
                },
            },
            upsert=True,
        )
        return {"authorization_url": authorization_url, "attempt_id": attempt_id}

    @staticmethod
    def _aware(value: object) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    async def record_callback(
        self,
        flow_token: str,
        *,
        error: str | None = None,
        error_description: str | None = None,
    ) -> dict[str, str]:
        if not isinstance(flow_token, str) or len(flow_token) < 32:
            raise self._error(
                status.HTTP_400_BAD_REQUEST,
                "domain_connect_flow_invalid",
                "The automatic DNS callback is invalid.",
                "Return to domain setup and start automatic setup again.",
            )
        digest = hashlib.sha256(flow_token.encode()).hexdigest()
        flows = self._mongo.db["storefront_domain_flows"]
        flow = await flows.find_one({"flow_token_digest": digest})
        if not flow:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_connect_flow_not_found",
                "The automatic DNS callback is no longer recognized.",
                "Return to domain setup and start automatic setup again.",
            )
        if flow.get("state") == "consumed":
            return {"attempt_id": flow["attempt_id"], "state": "consumed"}
        expires_at = self._aware(flow.get("expires_at"))
        if not expires_at or expires_at <= self._now():
            raise self._error(
                status.HTTP_410_GONE,
                "domain_connect_flow_expired",
                "The automatic DNS authorization has expired.",
                "Start automatic setup again to create a fresh authorization.",
            )

        if flow.get("state") in {"authorized", "cancelled", "failed"}:
            return {
                "attempt_id": flow["attempt_id"],
                "state": str(flow["state"]),
            }

        normalized_error = error if error in _CALLBACK_ERRORS else None
        cancelled = normalized_error == "access_denied" and bool(
            error_description and error_description.startswith("user_cancel")
        )
        callback_state = (
            "cancelled" if cancelled else ("failed" if error else "authorized")
        )
        safe_error = None
        if callback_state in {"cancelled", "failed"}:
            safe_error = {
                "code": (
                    "domain_connect_authorization_cancelled"
                    if cancelled
                    else "domain_connect_authorization_failed"
                ),
                "message": (
                    "Automatic DNS authorization was cancelled."
                    if cancelled
                    else "The DNS provider did not authorize automatic setup."
                ),
                "customer_action": "Return to domain setup and retry or use manual DNS setup.",
                "retryable": True,
                "support_id": f"sfd_{uuid4().hex[:16]}",
            }
        result = await flows.update_one(
            {
                "_id": flow["_id"],
                "flow_token_digest": digest,
                "state": "authorization_pending",
            },
            {
                "$set": {
                    "state": callback_state,
                    "provider_callback_error": normalized_error,
                    "last_error": safe_error,
                    "callback_recorded_at": self._now(),
                    "updated_at": self._now(),
                }
            },
        )
        if not getattr(result, "matched_count", 0):
            current = await flows.find_one({"_id": flow["_id"]})
            if current and current.get("state") == "consumed":
                return {"attempt_id": flow["attempt_id"], "state": "consumed"}
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_connect_flow_changed",
                "The automatic DNS authorization changed during callback processing.",
                "Reload domain status before retrying.",
                retryable=True,
            )
        return {"attempt_id": flow["attempt_id"], "state": callback_state}

    async def complete(self, owner: Any, attempt_id: str) -> dict:
        owner_id = await self._require_activation_capability(owner)
        flows = self._mongo.db["storefront_domain_flows"]
        flow = await flows.find_one(
            {
                "planner_id": owner_id,
                "attempt_id": attempt_id,
            }
        )
        if not flow:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_connect_flow_not_found",
                "No automatic DNS authorization exists for this attempt.",
                "Start automatic setup again or use manual DNS setup.",
            )
        domains = self._mongo.db["storefront_domains"]
        record = await domains.find_one(
            {"planner_id": owner_id, "claim_attempt_id": attempt_id}
        )
        if not record:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "domain_claim_not_found",
                "The domain claim for this authorization no longer exists.",
                "Restart domain setup.",
            )
        if flow.get("state") == "consumed":
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_connect_flow_consumed",
                "This automatic DNS authorization has already been completed.",
                "Reload domain status before taking another action.",
            )
        if not self._flow_matches_current_authorization(flow, record):
            if self._authorized_completion_was_applied(flow, record):
                await self._consume_flow(flow, owner_id, outcome="authorized")
                return self._serialize_record(record)
            return await self._consume_superseded_flow(flow, owner_id, record)
        expires_at = self._aware(flow.get("expires_at"))
        if not expires_at or expires_at <= self._now():
            raise self._error(
                status.HTTP_410_GONE,
                "domain_connect_flow_expired",
                "The automatic DNS authorization has expired.",
                "Start automatic setup again.",
            )
        if flow.get("state") in {"cancelled", "failed"}:
            phase = (
                AUTHORIZATION_CANCELLED
                if flow.get("state") == "cancelled"
                else ACTION_REQUIRED
            )
            completed = await domains.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "claim_attempt_id": attempt_id,
                    "revision": flow.get("domain_revision"),
                    "application_status": AUTHORIZATION_PENDING,
                    "provider_hostname_id": None,
                    "deletion_status": None,
                },
                {
                    "$set": {
                        "application_status": phase,
                        "action": "action_required",
                        "last_error": flow.get("last_error"),
                        "retry_due_at": None,
                        "updated_at": self._now(),
                    },
                    "$inc": {"revision": 1},
                },
            )
            if not getattr(completed, "matched_count", 0):
                current = await domains.find_one(
                    {"_id": record["_id"], "planner_id": owner_id}
                )
                return await self._consume_superseded_flow(
                    flow, owner_id, current or record
                )
            await self._consume_flow(
                flow,
                owner_id,
                outcome=str(flow.get("state")),
            )
            saved = await domains.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            return self._serialize_record(saved)
        if flow.get("state") not in {"authorized", "completing"}:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "domain_connect_authorization_pending",
                "Automatic DNS authorization has not completed.",
                "Finish or cancel the DNS provider authorization before continuing.",
                retryable=True,
            )

        if flow.get("state") == "authorized":
            completing = await flows.update_one(
                {
                    "_id": flow["_id"],
                    "planner_id": owner_id,
                    "state": "authorized",
                    "domain_revision": flow.get("domain_revision"),
                },
                {"$set": {"state": "completing", "updated_at": self._now()}},
            )
            if not getattr(completing, "matched_count", 0):
                current = await flows.find_one({"_id": flow["_id"]})
                if current and current.get("state") == "consumed":
                    saved = await domains.find_one(
                        {"_id": record["_id"], "planner_id": owner_id}
                    )
                    return self._serialize_record(saved)
                if not current or current.get("state") != "completing":
                    raise self._error(
                        status.HTTP_409_CONFLICT,
                        "domain_connect_flow_changed",
                        "Automatic DNS completion changed concurrently.",
                        "Reload domain status.",
                        retryable=True,
                    )
        scheduled = await domains.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "claim_attempt_id": attempt_id,
                "revision": flow.get("domain_revision"),
                "application_status": AUTHORIZATION_PENDING,
                "provider_hostname_id": None,
                "deletion_status": None,
            },
            {
                "$set": {
                    "application_status": DNS_SETUP_PENDING,
                    "action": "processing",
                    "domain_connect_authorized_at": self._now(),
                    "retry_due_at": self._now(),
                    "last_error": None,
                    "updated_at": self._now(),
                },
                "$inc": {"revision": 1},
            },
        )
        if not getattr(scheduled, "matched_count", 0):
            current = await domains.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            current_flow = await flows.find_one({"_id": flow["_id"]})
            if (
                current
                and current_flow
                and self._authorized_completion_was_applied(current_flow, current)
            ):
                await self._consume_flow(
                    current_flow,
                    owner_id,
                    outcome="authorized",
                )
                return self._serialize_record(current)
            return await self._consume_superseded_flow(
                flow, owner_id, current or record
            )
        await self._consume_flow(
            flow,
            owner_id,
            outcome="authorized",
        )
        saved = await domains.find_one({"_id": record["_id"], "planner_id": owner_id})
        return self._serialize_record(saved)


domain_connect_discovery = DomainConnectDiscovery()
storefront_domain_connect_service = StorefrontDomainConnectService(
    discovery_service=domain_connect_discovery
)
