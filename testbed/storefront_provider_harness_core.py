"""Deterministic external-provider adapters for storefront browser E2E.

This module is testbed infrastructure, not a production feature flag. The
runtime entry point validates its loopback environment before constructing any
adapter or importing the production ASGI application.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import html
import json
import re
import secrets
import ssl
from threading import RLock
from typing import Any, Callable, Literal, Mapping
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, urlsplit, urlunsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

import app.api.storefront as storefront_api
from app.core.settings import settings
import app.services.storefront_domain_connect_service as domain_connect_module
import app.services.storefront_domain_reconciliation_service as reconciliation_module
import app.services.storefront_domain_service as domain_service_module
import app.services.storefront_service as storefront_service_module
from app.services.cloudflare_service import CloudflareServiceError
from app.services.storefront_domain_connect_service import (
    StorefrontDomainConnectService,
)
from app.services.storefront_domain_https_probe import (
    MAX_PROBE_RESPONSE_BYTES,
    PROBE_HEADER,
    PROBE_PATH,
    build_probe_challenge,
    verify_probe_attestation,
)
from app.services.storefront_dns_service import StorefrontDnsResolutionError
from app.services.storefront_domain_reconciliation_service import (
    StorefrontDomainReconciliationService,
)
from app.services.storefront_domain_service import (
    StorefrontDomainService,
    normalize_custom_hostname,
)
from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy
from testbed.storefront_testbed_safety import SafeStorefrontProviderHarness


CONTROL_PREFIX = "/__testbed/storefront-provider"
PROVIDER_MODE = "deterministic_testbed"
CNAME_TARGET = "domains.thespecialwedding.com"
DOMAIN_CONNECT_PROVIDER_ID = "thespecialwedding.com"
DOMAIN_CONNECT_SERVICE_ID = "storefront-subdomain"
DOMAIN_CONNECT_TEMPLATE_VERSION = 1
DOMAIN_CONNECT_CALLBACK_HOST = "storefront-provider-callback.invalid"
_PROVIDER_ID_PREFIX = "tb_cf_"
_SIMULATED_MISSING_PROVIDER_CONFIGURATION = (
    "CLOUDFLARE_ZONE_ID",
    "STOREFRONT_CNAME_TARGET",
)


@dataclass
class DeterministicHostnameState:
    hostname: str
    zone: str
    domain_connect_supported: bool = False
    records: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    provider_result: dict[str, Any] | None = None
    provider_generation: int = 0
    provider_status_before_create: str = "pending"
    ssl_status_before_create: str = "pending_validation"
    https_ok: bool = False
    fail_next_create: int = 0
    fail_next_get: int = 0
    fail_next_retry: int = 0
    fail_next_delete: int = 0


class DeterministicProviderState:
    """In-process external observations; application state remains in Mongo."""

    def __init__(self, environment: SafeStorefrontProviderHarness) -> None:
        self.environment = environment
        self.provider_configuration_ready = True
        self.provider_mutations_enabled = True
        self.instruction_delivery_enabled = True
        self._hosts: dict[str, DeterministicHostnameState] = {}
        self._email_receipts: list[dict[str, str]] = []
        self._authoritative_queries: list[dict[str, Any]] = []
        self._https_probe_receipts: list[dict[str, Any]] = []
        self._cloudflare_calls: list[dict[str, str]] = []
        self._lock = RLock()

    def normalize_customer_hostname(self, value: str) -> str:
        hostname = normalize_custom_hostname(
            value,
            platform_domains={
                "thespecialwedding.io",
                "thespecialwedding.com",
                CNAME_TARGET,
            },
        )
        if not hostname.endswith(f".{self.environment.customer_zone}"):
            raise ValueError(
                "Deterministic provider hostnames must be subdomains of the "
                "configured .test or .invalid customer zone"
            )
        return hostname

    def configure(
        self,
        hostname: str,
        *,
        domain_connect_supported: bool,
        provider_configuration_ready: bool,
        provider_mutations_enabled: bool,
    ) -> DeterministicHostnameState:
        normalized = self.normalize_customer_hostname(hostname)
        with self._lock:
            configured = self._hosts.get(normalized)
            if configured is None:
                configured = DeterministicHostnameState(
                    hostname=normalized,
                    zone=self.environment.customer_zone,
                    domain_connect_supported=domain_connect_supported,
                )
                self._hosts[normalized] = configured
            else:
                configured.domain_connect_supported = domain_connect_supported
            self.provider_configuration_ready = provider_configuration_ready
            self.provider_mutations_enabled = provider_mutations_enabled
            return configured

    def require_host(self, hostname: str) -> DeterministicHostnameState:
        normalized = self.normalize_customer_hostname(hostname)
        with self._lock:
            state = self._hosts.get(normalized)
            if state is None:
                raise KeyError(normalized)
            return state

    def host_for_provider_id(self, provider_id: str) -> DeterministicHostnameState:
        with self._lock:
            matches = [
                state
                for state in self._hosts.values()
                if state.provider_result
                and state.provider_result.get("id") == provider_id
            ]
        if len(matches) != 1:
            raise KeyError(provider_id)
        return matches[0]

    def query(self, name: str, record_type: str) -> list[str]:
        normalized_name = name.strip().lower().rstrip(".")
        normalized_type = record_type.strip().upper()
        if (
            normalized_name == self.environment.customer_zone
            and normalized_type == "NS"
        ):
            return [
                "ada.ns.cloudflare.com",
                "bob.ns.cloudflare.com",
            ]
        with self._lock:
            for state in self._hosts.values():
                values = state.records.get(normalized_name, {}).get(normalized_type)
                if values is not None:
                    return list(values)
        return []

    def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]:
        """Return a deterministic observation only for the delegated servers.

        This intentionally checks the exact nameservers discovered for the
        reserved customer zone.  Treating an authoritative lookup as an alias
        for a recursive lookup would let the browser harness pass without
        proving that the production service requested the delegated authority.
        """

        expected = sorted(self.query(self.environment.customer_zone, "NS"))
        supplied = sorted(
            {
                value.strip().lower().rstrip(".")
                for value in nameservers
                if isinstance(value, str) and value.strip()
            }
        )
        if supplied != expected:
            raise StorefrontDnsResolutionError(
                "Deterministic authoritative query used unexpected nameservers"
            )
        normalized_name = name.strip().lower().rstrip(".")
        normalized_type = record_type.strip().upper()
        with self._lock:
            self._authoritative_queries.append(
                {
                    "name": normalized_name,
                    "record_type": normalized_type,
                    "nameservers": supplied,
                }
            )
        return self.query(normalized_name, normalized_type)

    def set_record(
        self, hostname: str, name: str, record_type: str, values: list[str]
    ) -> None:
        state = self.require_host(hostname)
        normalized_name = name.strip().lower().rstrip(".")
        normalized_type = record_type.strip().upper()
        with self._lock:
            state.records.setdefault(normalized_name, {})[normalized_type] = list(
                values
            )

    def set_dns_mode(
        self, hostname: str, mode: Literal["unchanged", "missing", "wrong"]
    ) -> None:
        if mode == "unchanged":
            return
        state = self.require_host(hostname)
        ownership_name = f"_tsw-storefront.{state.hostname}"
        with self._lock:
            for name, record_type in (
                (ownership_name, "TXT"),
                (state.hostname, "CNAME"),
            ):
                record_types = state.records.get(name)
                if record_types:
                    record_types.pop(record_type, None)
                    if not record_types:
                        state.records.pop(name, None)
            if mode == "wrong":
                state.records.setdefault(ownership_name, {})["TXT"] = [
                    "tsw-verification=wrong-testbed-token"
                ]
                state.records.setdefault(state.hostname, {})["CNAME"] = [
                    f"wrong-target.{state.zone}"
                ]

    async def publish_claim(
        self,
        *,
        mongo_client: Any,
        domain_service: StorefrontDomainService,
        hostname: str,
        expected_token: str | None = None,
        include_routing: bool = True,
    ) -> bool:
        state = self.require_host(hostname)
        record = await mongo_client.db["storefront_domains"].find_one(
            {"hostname": state.hostname}
        )
        if not record:
            return False
        token = domain_service._decrypt_claim_token(record)
        if not token or (
            expected_token is not None
            and not hmac.compare_digest(token, expected_token)
        ):
            return False
        self.set_record(
            state.hostname,
            f"_tsw-storefront.{state.hostname}",
            "TXT",
            [f"tsw-verification={token}"],
        )
        if include_routing:
            self.set_record(
                state.hostname,
                state.hostname,
                "CNAME",
                [CNAME_TARGET],
            )
        return True

    def routing_snapshot(self, hostname: str) -> dict[str, Any]:
        """Return only customer-routing records, never verification secrets."""

        state = self.require_host(hostname)
        with self._lock:
            record_types = state.records.get(state.hostname, {})
            return {
                "hostname": state.hostname,
                "A": list(record_types.get("A", [])),
                "AAAA": list(record_types.get("AAAA", [])),
                "CNAME": list(record_types.get("CNAME", [])),
            }

    async def publish_conflict_claim(
        self,
        *,
        mongo_client: Any,
        domain_service: StorefrontDomainService,
        hostname: str,
    ) -> bool:
        """Publish only a claimant's fresh TXT proof, never routing DNS.

        The deterministic run permits exactly one current conflict claim for
        this hostname. Ambiguity fails closed instead of selecting a claimant.
        """

        state = self.require_host(hostname)
        current = (
            await mongo_client.db["storefront_domain_conflict_claims"]
            .find(
                {
                    "hostname": state.hostname,
                    "current_owner_key": {"$exists": True},
                    "application_status": {"$nin": ["disconnected", "expired"]},
                }
            )
            .limit(2)
            .to_list(length=2)
        )
        if len(current) != 1:
            return False
        token = domain_service._decrypt_claim_token(current[0])
        if not token:
            return False
        self.set_record(
            state.hostname,
            f"_tsw-storefront.{state.hostname}",
            "TXT",
            [f"tsw-conflict-verification={token}"],
        )
        return True

    def record_cloudflare_call(self, operation: str, hostname: str) -> None:
        with self._lock:
            self._cloudflare_calls.append(
                {"operation": operation, "hostname": hostname}
            )

    def provider_result(self, state: DeterministicHostnameState) -> dict[str, Any]:
        if state.provider_result is None:
            raise KeyError(state.hostname)
        return deepcopy(state.provider_result)

    def advance(
        self,
        hostname: str,
        *,
        provider_configuration_ready: bool | None = None,
        provider_mutations_enabled: bool | None = None,
        provider_status: str | None = None,
        ssl_status: str | None = None,
        https_ok: bool | None = None,
        fail_next_create: int | None = None,
        fail_next_get: int | None = None,
        fail_next_retry: int | None = None,
        fail_next_delete: int | None = None,
    ) -> DeterministicHostnameState:
        state = self.require_host(hostname)
        with self._lock:
            if provider_configuration_ready is not None:
                self.provider_configuration_ready = provider_configuration_ready
            if provider_mutations_enabled is not None:
                self.provider_mutations_enabled = provider_mutations_enabled
            if provider_status is not None:
                state.provider_status_before_create = provider_status
                if state.provider_result:
                    state.provider_result["status"] = provider_status
            if ssl_status is not None:
                state.ssl_status_before_create = ssl_status
                if state.provider_result:
                    state.provider_result.setdefault("ssl", {})["status"] = ssl_status
                    for record in state.provider_result["ssl"].get(
                        "validation_records", []
                    ):
                        record["status"] = (
                            "active" if ssl_status == "active" else "pending"
                        )
            if https_ok is not None:
                state.https_ok = https_ok
            for field_name, value in (
                ("fail_next_create", fail_next_create),
                ("fail_next_get", fail_next_get),
                ("fail_next_retry", fail_next_retry),
                ("fail_next_delete", fail_next_delete),
            ):
                if value is not None:
                    setattr(state, field_name, value)
        return state

    def record_email(
        self,
        *,
        to_email: str,
        message_id: str,
        hostname: str,
        instruction_url: str,
    ) -> None:
        with self._lock:
            self._email_receipts.append(
                {
                    "recipient_sha256": hashlib.sha256(
                        to_email.strip().lower().encode()
                    ).hexdigest(),
                    "message_id": message_id,
                    "hostname": hostname,
                    "instruction_url": instruction_url,
                }
            )

    def latest_instruction_receipt(self, hostname: str) -> dict[str, str]:
        normalized = self.normalize_customer_hostname(hostname)
        with self._lock:
            for receipt in reversed(self._email_receipts):
                if receipt.get("hostname") == normalized:
                    return dict(receipt)
        raise KeyError(normalized)

    def record_https_probe(
        self,
        *,
        hostname: str,
        status_code: int | None,
        verified: bool,
    ) -> None:
        with self._lock:
            self._https_probe_receipts.append(
                {
                    "hostname": hostname,
                    "path": PROBE_PATH,
                    "status_code": status_code,
                    "verified": verified,
                }
            )

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "run_id": self.environment.run_id,
                "provider_mode": PROVIDER_MODE,
                "external_provider_live": False,
                "provider_configuration_ready": self.provider_configuration_ready,
                "provider_mutations_enabled": self.provider_mutations_enabled,
                "provider_configuration_missing": (
                    []
                    if self.provider_configuration_ready
                    else list(_SIMULATED_MISSING_PROVIDER_CONFIGURATION)
                ),
                "hostnames": sorted(self._hosts),
                "provider_records": sum(
                    state.provider_result is not None for state in self._hosts.values()
                ),
                "instruction_receipts": len(self._email_receipts),
                "authoritative_query_count": len(self._authoritative_queries),
                "https_probe_count": len(self._https_probe_receipts),
                "cloudflare_call_count": len(self._cloudflare_calls),
                "cloudflare_calls": [dict(call) for call in self._cloudflare_calls],
                "latest_https_probe": (
                    dict(self._https_probe_receipts[-1])
                    if self._https_probe_receipts
                    else None
                ),
            }


class DeterministicDnsResolver:
    def __init__(self, state: DeterministicProviderState) -> None:
        self._state = state

    async def query(self, name: str, record_type: str) -> list[str]:
        return self._state.query(name, record_type)

    async def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]:
        return self._state.query_authoritative(name, record_type, nameservers)


class DeterministicCloudflare:
    """Cloudflare-for-SaaS-shaped adapter that never performs network I/O."""

    def __init__(self, state: DeterministicProviderState) -> None:
        self._state = state

    @property
    def is_configured(self) -> bool:
        return True

    def _require_mutations(self, operation: str) -> None:
        if self._state.provider_mutations_enabled:
            return
        raise CloudflareServiceError(
            "Deterministic provider mutations are disabled",
            operation=operation,
            kind="configuration",
            errors=(
                {
                    "code": "testbed_provider_mutations_disabled",
                    "message": "Enable the deterministic provider explicitly",
                },
            ),
        )

    @staticmethod
    def _failure(operation: str) -> CloudflareServiceError:
        return CloudflareServiceError(
            "Deterministic provider injected a retryable failure",
            operation=operation,
            kind="provider",
            provider_status_code=503,
            errors=(
                {
                    "code": "testbed_provider_failure",
                    "message": "A deterministic provider failure was requested",
                },
            ),
        )

    @staticmethod
    def _provider_id(run_id: str, hostname: str, generation: int) -> str:
        digest = hashlib.sha256(
            f"{run_id}:{hostname}:{generation}".encode()
        ).hexdigest()[:24]
        return f"{_PROVIDER_ID_PREFIX}{digest}"

    async def list_custom_hostnames(self, hostname: str) -> list[dict[str, Any]]:
        self._state.record_cloudflare_call("list_custom_hostnames", hostname)
        try:
            state = self._state.require_host(hostname)
        except (KeyError, ValueError):
            return []
        return [self._state.provider_result(state)] if state.provider_result else []

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        self._state.record_cloudflare_call("create_custom_hostname", hostname)
        self._require_mutations("create_custom_hostname")
        state = self._state.require_host(hostname)
        if state.fail_next_create > 0:
            state.fail_next_create -= 1
            raise self._failure("create_custom_hostname")
        if state.provider_result is None:
            state.provider_generation += 1
            state.provider_result = {
                "id": self._provider_id(
                    self._state.environment.run_id,
                    state.hostname,
                    state.provider_generation,
                ),
                "hostname": state.hostname,
                "status": state.provider_status_before_create,
                "ownership_verification": {
                    "type": "txt",
                    "name": f"_cf-custom-hostname.{state.hostname}",
                    "value": "testbed-cloudflare-ownership",
                },
                "ownership_verification_http": None,
                "ssl": {
                    "status": state.ssl_status_before_create,
                    "validation_records": [
                        {
                            "status": (
                                "active"
                                if state.ssl_status_before_create == "active"
                                else "pending"
                            ),
                            "txt_name": f"_acme-challenge.{state.hostname}",
                            "txt_value": "testbed-acme-validation",
                        }
                    ],
                },
            }
        return self._state.provider_result(state)

    async def get_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        try:
            state = self._state.host_for_provider_id(hostname_id)
        except KeyError as exc:
            raise CloudflareServiceError(
                "Deterministic provider hostname was not found",
                operation="get_custom_hostname",
                kind="provider",
                provider_status_code=404,
            ) from exc
        self._state.record_cloudflare_call("get_custom_hostname", state.hostname)
        if state.fail_next_get > 0:
            state.fail_next_get -= 1
            raise self._failure("get_custom_hostname")
        return self._state.provider_result(state)

    async def retry_custom_hostname(
        self,
        hostname_id: str,
        *,
        ssl_method: str,
        ssl_type: str,
    ) -> dict[str, Any]:
        try:
            retry_hostname = self._state.host_for_provider_id(hostname_id).hostname
        except KeyError:
            retry_hostname = hostname_id
        self._state.record_cloudflare_call("retry_custom_hostname", retry_hostname)
        self._require_mutations("retry_custom_hostname")
        if ssl_method not in {"txt", "http", "email"} or ssl_type != "dv":
            raise self._failure("retry_custom_hostname")
        state = self._state.host_for_provider_id(hostname_id)
        if state.fail_next_retry > 0:
            state.fail_next_retry -= 1
            raise self._failure("retry_custom_hostname")
        return self._state.provider_result(state)

    async def delete_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        try:
            delete_hostname = self._state.host_for_provider_id(hostname_id).hostname
        except KeyError:
            delete_hostname = hostname_id
        self._state.record_cloudflare_call("delete_custom_hostname", delete_hostname)
        self._require_mutations("delete_custom_hostname")
        try:
            state = self._state.host_for_provider_id(hostname_id)
        except KeyError as exc:
            raise CloudflareServiceError(
                "Deterministic provider hostname was not found",
                operation="delete_custom_hostname",
                kind="provider",
                provider_status_code=404,
            ) from exc
        if state.fail_next_delete > 0:
            state.fail_next_delete -= 1
            raise self._failure("delete_custom_hostname")
        state.provider_result = None
        return {"id": hostname_id}


class DeterministicDomainConnectDiscovery:
    def __init__(
        self, state: DeterministicProviderState, provider_base_url: str
    ) -> None:
        self._state = state
        self._provider_base_url = provider_base_url

    async def discover(self, zone: str) -> dict[str, Any]:
        supported = any(
            hostname_state.zone == zone and hostname_state.domain_connect_supported
            for hostname_state in self._state._hosts.values()
        )
        if not supported:
            return {
                "supported": False,
                "reason_code": "exact_template_not_supported",
                "provider_id": "cloudflare",
                "provider_name": "Cloudflare Testbed DNS",
            }
        return {
            "supported": True,
            "reason_code": "supported",
            "provider_id": "cloudflare",
            "provider_name": "Cloudflare Testbed DNS",
            "url_sync_ux": self._provider_base_url,
            "url_api": self._provider_base_url,
            "control_panel_url": self._provider_base_url,
            "template_version": DOMAIN_CONNECT_TEMPLATE_VERSION,
        }


class DeterministicStorefrontDomainService(StorefrontDomainService):
    """Keep instruction links first-party on the isolated HTTPS Next origin.

    Production URLs are port 443. The testbed uses a dedicated high loopback
    port, so only this testbed subclass relaxes URL composition while retaining
    the production link persistence, expiry, revocation, and public API logic.
    """

    def __init__(self, *args: Any, testbed_frontend_origin: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        parsed = urlsplit(testbed_frontend_origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "The deterministic instruction origin must be loopback HTTPS"
            )
        self._testbed_frontend_origin = testbed_frontend_origin.rstrip("/")

    def _instruction_link_url(self, token: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
            raise ValueError("Invalid deterministic instruction token")
        return f"{self._testbed_frontend_origin}/domain-instructions/{token}"


class DeterministicHttpsVerifier:
    def __init__(self, state: DeterministicProviderState) -> None:
        self._state = state

    async def verify(self, record: Mapping[str, Any]) -> bool:
        try:
            state = self._state.require_host(str(record.get("hostname") or ""))
        except (KeyError, ValueError):
            return False
        provider = state.provider_result or {}
        ssl = provider.get("ssl") if isinstance(provider.get("ssl"), dict) else {}
        return bool(
            state.https_ok
            and provider.get("id") == record.get("provider_hostname_id")
            and provider.get("hostname") == record.get("hostname")
            and provider.get("status") == "active"
            and ssl.get("status") == "active"
        )


class NextRouteStorefrontHttpsVerifier:
    """Exercise the signed custom-host probe through the real HTTPS Next edge."""

    def __init__(
        self,
        state: DeterministicProviderState,
        *,
        frontend_origin: str,
        ca_certificate: str,
        secret_key: str,
    ) -> None:
        self._state = state
        self._frontend_origin = frontend_origin.rstrip("/")
        self._secret_key = secret_key
        self._ssl_context = ssl.create_default_context(cafile=ca_certificate)

    async def verify(self, record: Mapping[str, Any]) -> bool:
        hostname = str(record.get("hostname") or "")
        status_code: int | None = None
        verified = False
        try:
            state = self._state.require_host(hostname)
            provider = state.provider_result or {}
            ssl_projection = (
                provider.get("ssl") if isinstance(provider.get("ssl"), dict) else {}
            )
            if not (
                state.https_ok
                and provider.get("id") == record.get("provider_hostname_id")
                and provider.get("hostname") == hostname
                and provider.get("status") == "active"
                and ssl_projection.get("status") == "active"
            ):
                return False
            challenge = build_probe_challenge(record, self._secret_key)
            async with httpx.AsyncClient(
                verify=self._ssl_context,
                follow_redirects=False,
                timeout=5.0,
                trust_env=False,
            ) as client:
                response = await client.get(
                    f"{self._frontend_origin}{PROBE_PATH}",
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "Host": hostname,
                        PROBE_HEADER: challenge,
                    },
                )
            status_code = response.status_code
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if (
                response.status_code != 200
                or content_type.strip().lower() != "application/json"
                or not response.content
                or len(response.content) > MAX_PROBE_RESPONSE_BYTES
            ):
                return False
            payload = json.loads(response.content)
            verified = verify_probe_attestation(
                record, challenge, payload, self._secret_key
            )
            return verified
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
        finally:
            # A receipt is written only when the deterministic routing control
            # allowed a real edge probe attempt; intermediate https_ok=false
            # states intentionally remain observation-free.
            if status_code is not None:
                self._state.record_https_probe(
                    hostname=hostname,
                    status_code=status_code,
                    verified=verified,
                )


class DeterministicInstructionEmail:
    def __init__(self, state: DeterministicProviderState) -> None:
        self._state = state

    async def send_email(self, **kwargs: Any) -> dict[str, Any]:
        if not self._state.instruction_delivery_enabled:
            return {"success": False}
        to_email = str(kwargs.get("to_email") or "")
        message_id = (
            "tb_email_"
            + hashlib.sha256(
                f"{self._state.environment.run_id}:{to_email}".encode()
            ).hexdigest()[:20]
        )
        subject = str(kwargs.get("subject") or "")
        subject_match = re.fullmatch(r"DNS setup instructions for (.+)", subject)
        content = str(kwargs.get("html_content") or "")
        link_match = re.search(r'href="([^"]+)"', content)
        if not subject_match or not link_match:
            return {"success": False}
        try:
            hostname = self._state.normalize_customer_hostname(subject_match.group(1))
        except ValueError:
            return {"success": False}
        self._state.record_email(
            to_email=to_email,
            message_id=message_id,
            hostname=hostname,
            instruction_url=html.unescape(link_match.group(1)),
        )
        return {"success": True, "message_id": message_id}


class ConfigureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hostname: str = Field(min_length=1, max_length=253)
    domain_connect_supported: bool = False
    provider_configuration_ready: bool = True
    provider_mutations_enabled: bool = True


class HostnameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hostname: str = Field(min_length=1, max_length=253)


class PublishClaimRequest(HostnameRequest):
    """Testbed-only DNS publication mode used to prove migration safety."""

    ownership_only: bool = False


class InquiryRetryDueRequest(BaseModel):
    """Identify one persisted inquiry without accepting owner identity from the caller."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    inquiry_id: str = Field(pattern=r"^[0-9a-fA-F]{24}$")


class AdvanceRequest(HostnameRequest):
    provider_configuration_ready: bool | None = None
    provider_mutations_enabled: bool | None = None
    provider_status: str | None = Field(default=None, max_length=80)
    ssl_status: str | None = Field(default=None, max_length=80)
    https_ok: bool | None = None
    fail_next_create: int | None = Field(default=None, ge=0, le=5)
    fail_next_get: int | None = Field(default=None, ge=0, le=5)
    fail_next_retry: int | None = Field(default=None, ge=0, le=5)
    fail_next_delete: int | None = Field(default=None, ge=0, le=5)
    dns_mode: Literal["unchanged", "missing", "wrong"] = "unchanged"
    reconcile_passes: int = Field(default=0, ge=0, le=5)


class StorefrontHarnessDispatcher:
    """Route testbed provider traffic separately from the production ASGI app."""

    def __init__(
        self,
        *,
        production_app: Any,
        control_app: FastAPI,
        environment: SafeStorefrontProviderHarness,
    ) -> None:
        self._production_app = production_app
        self._control_app = control_app
        self._environment = environment

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = str(scope.get("path") or "")
            if path.startswith(CONTROL_PREFIX):
                target = self._control_app
            elif path == "/admin/packages" and self._is_domain_callback_bridge(scope):
                query = scope.get("query_string", b"").decode("ascii", errors="ignore")
                location = f"{self._environment.frontend_origin}{path}"
                if query:
                    location = f"{location}?{query}"
                response = RedirectResponse(location, status_code=307)
                await response(scope, receive, send)
                return
            else:
                target = self._production_app

            async def send_with_mode(message: dict) -> None:
                if message.get("type") == "http.response.start":
                    headers = list(message.get("headers") or [])
                    headers.append(
                        (b"x-storefront-provider-mode", b"deterministic-testbed")
                    )
                    message = {**message, "headers": headers}
                await send(message)

            await target(scope, receive, send_with_mode)
            return
        await self._production_app(scope, receive, send)

    @staticmethod
    def _is_domain_callback_bridge(scope: dict) -> bool:
        query = scope.get("query_string", b"").decode("ascii", errors="ignore")
        parsed = parse_qs(query, keep_blank_values=True)
        attempt = parsed.get("attempt", [])
        return (
            parsed.get("storefront") == ["domain"]
            and len(attempt) == 1
            and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", attempt[0]) is not None
        )


@dataclass
class StorefrontProviderHarnessBundle:
    app: Any
    state: DeterministicProviderState
    domain_service: StorefrontDomainService
    domain_connect_service: StorefrontDomainConnectService
    reconciliation_service: StorefrontDomainReconciliationService
    _restore: Callable[[], None]
    _restored: bool = False

    def restore(self) -> None:
        if self._restored:
            return
        self._restore()
        self._restored = True


def _private_key_pem() -> tuple[str, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return pem, private_key.public_key()


def _provider_request_values(
    request: Request,
    *,
    public_key: rsa.RSAPublicKey,
    expected_key_id: str,
    environment: SafeStorefrontProviderHarness,
) -> dict[str, str]:
    names = ("domain", "host", "redirect_uri", "verificationToken")
    values: dict[str, str] = {}
    for name in names:
        occurrences = request.query_params.getlist(name)
        if len(occurrences) != 1 or not occurrences[0]:
            raise HTTPException(
                status_code=400, detail="Invalid signed provider request"
            )
        values[name] = occurrences[0]
    if request.query_params.get("key") != expected_key_id:
        raise HTTPException(status_code=400, detail="Invalid provider signing key")
    if values["domain"] != environment.customer_zone:
        raise HTTPException(status_code=400, detail="Invalid provider customer zone")
    try:
        hostname = normalize_custom_hostname(
            f"{values['host']}.{values['domain']}", platform_domains=()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid provider hostname"
        ) from exc
    values["hostname"] = hostname
    canonical = urlencode(
        [(name, values[name]) for name in names], quote_via=quote, safe=""
    )
    try:
        signature = base64.b64decode(request.query_params.get("sig", ""), validate=True)
        public_key.verify(
            signature,
            canonical.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="Invalid provider signature"
        ) from exc
    callback = urlsplit(values["redirect_uri"])
    if (
        callback.scheme != "https"
        or callback.hostname != DOMAIN_CONNECT_CALLBACK_HOST
        or callback.path != "/admin/storefront/custom-domain/domain-connect/callback"
        or not callback.query
        or callback.fragment
    ):
        raise HTTPException(status_code=400, detail="Invalid provider callback")
    return values


def _local_callback_url(
    environment: SafeStorefrontProviderHarness,
    signed_redirect_uri: str,
    *,
    cancelled: bool,
) -> str:
    parsed = urlsplit(signed_redirect_uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    if cancelled:
        query.extend(
            [
                ("error", "access_denied"),
                ("error_description", "user_cancel_testbed"),
            ]
        )
    return urlunsplit(
        (
            urlsplit(environment.backend_origin).scheme,
            urlsplit(environment.backend_origin).netloc,
            parsed.path,
            urlencode(query),
            "",
        )
    )


def _patch_service_globals(
    *,
    domain_service: StorefrontDomainService,
    domain_connect_service: StorefrontDomainConnectService,
    reconciliation_service: StorefrontDomainReconciliationService,
) -> Callable[[], None]:
    assignments = [
        (storefront_api, "storefront_domain_service", domain_service),
        (
            storefront_api,
            "storefront_domain_connect_service",
            domain_connect_service,
        ),
        (domain_service_module, "storefront_domain_service", domain_service),
        (
            domain_connect_module,
            "storefront_domain_connect_service",
            domain_connect_service,
        ),
        (
            reconciliation_module,
            "storefront_domain_reconciliation_service",
            reconciliation_service,
        ),
    ]
    previous = [
        (target, name, getattr(target, name)) for target, name, _ in assignments
    ]
    previous_domains = storefront_service_module.storefront_service._domains
    for target, name, replacement in assignments:
        setattr(target, name, replacement)
    storefront_service_module.storefront_service._domains = domain_service

    def restore() -> None:
        for target, name, value in reversed(previous):
            setattr(target, name, value)
        storefront_service_module.storefront_service._domains = previous_domains

    return restore


def create_storefront_provider_harness(
    *,
    environment: SafeStorefrontProviderHarness,
    mongo_client: Any,
    entitlement_service: Any,
    production_app: Any,
) -> StorefrontProviderHarnessBundle:
    """Inject deterministic adapters behind the real storefront services/routes."""

    state = DeterministicProviderState(environment)
    dns = DeterministicDnsResolver(state)
    cloudflare = DeterministicCloudflare(state)
    https = (
        NextRouteStorefrontHttpsVerifier(
            state,
            frontend_origin=environment.frontend_origin,
            ca_certificate=environment.frontend_ca_certificate,
            secret_key=settings.secret_key,
        )
        if environment.frontend_ca_certificate
        else DeterministicHttpsVerifier(state)
    )
    instruction_email = DeterministicInstructionEmail(state)
    provider_path_token = secrets.token_urlsafe(32)
    provider_base = (
        f"{environment.backend_origin}{CONTROL_PREFIX}/provider/"
        f"{environment.run_id}/{provider_path_token}"
    )
    discovery = DeterministicDomainConnectDiscovery(state, provider_base)

    def readiness() -> dict[str, Any]:
        configuration_ready = state.provider_configuration_ready
        mutations_enabled = state.provider_mutations_enabled
        ready = configuration_ready and mutations_enabled
        if not configuration_ready:
            reason_code = "configuration_unavailable"
            missing = list(_SIMULATED_MISSING_PROVIDER_CONFIGURATION)
        elif not mutations_enabled:
            reason_code = "provider_mutations_disabled"
            missing = []
        else:
            reason_code = "deterministic_testbed_ready"
            missing = []
        return {
            "enabled": True,
            "ready": ready,
            "reason_code": reason_code,
            "missing": missing,
            "provider_mode": PROVIDER_MODE,
            "external_provider_live": False,
        }

    domain_service = DeterministicStorefrontDomainService(
        mongo_client=mongo_client,
        cloudflare_service=cloudflare,
        entitlement_service=entitlement_service,
        dns_resolver=dns,
        claim_encryption_key=(
            f"testbed:{environment.run_id}:{environment.control_token}"
        ),
        cname_target=CNAME_TARGET,
        platform_domains={"thespecialwedding.io", "thespecialwedding.com"},
        readiness_resolver=readiness,
        instruction_email_service=instruction_email,
        instruction_public_base_url=environment.frontend_origin,
        domain_connect_discovery=discovery,
        rollout_policy=StorefrontDomainRolloutPolicy.build(mode="general"),
        testbed_frontend_origin=environment.frontend_origin,
    )
    private_key_pem, public_key = _private_key_pem()
    key_id = f"testbed-{environment.run_id}"
    domain_connect_service = StorefrontDomainConnectService(
        mongo_client=mongo_client,
        entitlement_service=entitlement_service,
        discovery_service=discovery,
        private_key_pem=private_key_pem,
        provider_id=DOMAIN_CONNECT_PROVIDER_ID,
        service_id=DOMAIN_CONNECT_SERVICE_ID,
        template_version=DOMAIN_CONNECT_TEMPLATE_VERSION,
        key_id=key_id,
        callback_url=(
            f"https://{DOMAIN_CONNECT_CALLBACK_HOST}"
            "/admin/storefront/custom-domain/domain-connect/callback"
        ),
        cname_target=CNAME_TARGET,
        authorization_enabled=True,
        readiness_resolver=readiness,
        claim_token_reader=domain_service._decrypt_claim_token,
        record_serializer=domain_service._serialize,
        rollout_policy=StorefrontDomainRolloutPolicy.build(mode="general"),
    )
    reconciliation_service = StorefrontDomainReconciliationService(
        mongo_client=mongo_client,
        cloudflare_service=cloudflare,
        dns_resolver=dns,
        https_verifier=https,
        domain_service=domain_service,
        cname_target=CNAME_TARGET,
        jitter=lambda _start, _end: 0.0,
    )
    restore = _patch_service_globals(
        domain_service=domain_service,
        domain_connect_service=domain_connect_service,
        reconciliation_service=reconciliation_service,
    )

    control_app = FastAPI(
        title="Storefront deterministic provider harness",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def require_control(request: Request) -> None:
        supplied_run = request.headers.get("x-storefront-testbed-run-id", "")
        supplied_token = request.headers.get("x-storefront-testbed-control-token", "")
        if not (
            hmac.compare_digest(supplied_run, environment.run_id)
            and hmac.compare_digest(supplied_token, environment.control_token)
        ):
            raise HTTPException(status_code=404, detail="Not found")

    @control_app.post(f"{CONTROL_PREFIX}/configure")
    async def configure(request: Request, payload: ConfigureRequest):
        require_control(request)
        try:
            configured = state.configure(
                payload.hostname,
                domain_connect_supported=payload.domain_connect_supported,
                provider_configuration_ready=payload.provider_configuration_ready,
                provider_mutations_enabled=payload.provider_mutations_enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            **state.status(),
            "hostname": configured.hostname,
            "domain_connect_supported": configured.domain_connect_supported,
        }

    @control_app.post(f"{CONTROL_PREFIX}/publish-claim")
    async def publish_claim(request: Request, payload: PublishClaimRequest):
        require_control(request)
        try:
            published = await state.publish_claim(
                mongo_client=mongo_client,
                domain_service=domain_service,
                hostname=payload.hostname,
                include_routing=not payload.ownership_only,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Testbed hostname not found"
            ) from exc
        if not published:
            raise HTTPException(status_code=409, detail="No resumable DNS claim exists")
        return {
            "published": True,
            "hostname": payload.hostname.lower(),
            "ownership_only": payload.ownership_only,
            "routing_changed": not payload.ownership_only,
        }

    @control_app.get(f"{CONTROL_PREFIX}/routing-snapshot")
    async def routing_snapshot(request: Request, hostname: str):
        require_control(request)
        try:
            snapshot = state.routing_snapshot(hostname)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Testbed hostname not found"
            ) from exc
        return {"run_id": environment.run_id, **snapshot}

    @control_app.post(f"{CONTROL_PREFIX}/publish-conflict-claim")
    async def publish_conflict_claim(request: Request, payload: HostnameRequest):
        require_control(request)
        try:
            published = await state.publish_conflict_claim(
                mongo_client=mongo_client,
                domain_service=domain_service,
                hostname=payload.hostname,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Testbed hostname not found"
            ) from exc
        if not published:
            raise HTTPException(
                status_code=409, detail="No unambiguous conflict claim exists"
            )
        return {
            "published": True,
            "hostname": payload.hostname.lower(),
            "record_type": "TXT",
            "routing_changed": False,
        }

    @control_app.post(f"{CONTROL_PREFIX}/advance")
    async def advance(request: Request, payload: AdvanceRequest):
        require_control(request)
        try:
            advanced = state.advance(
                payload.hostname,
                provider_configuration_ready=payload.provider_configuration_ready,
                provider_mutations_enabled=payload.provider_mutations_enabled,
                provider_status=payload.provider_status,
                ssl_status=payload.ssl_status,
                https_ok=payload.https_ok,
                fail_next_create=payload.fail_next_create,
                fail_next_get=payload.fail_next_get,
                fail_next_retry=payload.fail_next_retry,
                fail_next_delete=payload.fail_next_delete,
            )
            state.set_dns_mode(advanced.hostname, payload.dns_mode)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Testbed hostname not found"
            ) from exc
        processed = 0
        for _ in range(payload.reconcile_passes):
            now = datetime.now(timezone.utc)
            await mongo_client.db["storefront_domains"].update_one(
                {"hostname": advanced.hostname},
                {
                    "$set": {"retry_due_at": now},
                    "$unset": {
                        "lease_token": "",
                        "lease_expires_at": "",
                        "reconciliation_started_at": "",
                    },
                },
            )
            processed += await reconciliation_service.sweep_due(batch_size=1)
        return {
            **state.status(),
            "hostname": advanced.hostname,
            "reconciled": processed,
        }

    @control_app.get(f"{CONTROL_PREFIX}/status")
    async def control_status(request: Request):
        require_control(request)
        return state.status()

    @control_app.post(f"{CONTROL_PREFIX}/inquiry-retry-due")
    async def make_inquiry_retry_due(
        request: Request,
        payload: InquiryRetryDueRequest,
    ):
        """Make one exact-run retry observable without mutating its outcome."""

        require_control(request)
        inquiry_id = ObjectId(payload.inquiry_id)
        inquiries = mongo_client.db["storefront_inquiries"]
        inquiry = await inquiries.find_one({"_id": inquiry_id})
        if not inquiry:
            raise HTTPException(status_code=404, detail="Testbed inquiry not found")

        planner_id = inquiry.get("planner_id")
        owner_ids: list[Any] = [planner_id]
        if isinstance(planner_id, str) and ObjectId.is_valid(planner_id):
            owner_ids.append(ObjectId(planner_id))
        owner = await mongo_client.db["users"].find_one(
            {
                "_id": {"$in": owner_ids},
                "testbed_run_id": environment.run_id,
            }
        )
        message = inquiry.get("message")
        if (
            not owner
            or not isinstance(message, str)
            or environment.run_id not in message
        ):
            # Do not disclose whether an inquiry belongs to another owner or run.
            raise HTTPException(status_code=404, detail="Testbed inquiry not found")

        notification = inquiry.get("notification")
        attempt_count = (
            notification.get("attempt_count")
            if isinstance(notification, dict)
            else None
        )
        if (
            not isinstance(notification, dict)
            or notification.get("status") != "retry_pending"
            or not isinstance(attempt_count, int)
            or attempt_count < 1
        ):
            raise HTTPException(
                status_code=409,
                detail="Testbed inquiry notification is not retry-pending",
            )

        due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        result = await inquiries.update_one(
            {
                "_id": inquiry_id,
                "planner_id": planner_id,
                "message": message,
                "notification.status": "retry_pending",
                "notification.attempt_count": attempt_count,
            },
            {"$set": {"notification.next_attempt_at": due_at}},
        )
        if getattr(result, "matched_count", 0) != 1:
            raise HTTPException(
                status_code=409,
                detail="Testbed inquiry notification changed during retry setup",
            )
        return {
            "run_id": environment.run_id,
            "inquiry_id": payload.inquiry_id.lower(),
            "notification_status": "retry_pending",
            "attempt_count": attempt_count,
            "retry_due": True,
            "next_attempt_at": due_at.isoformat(),
            "external_provider_live": False,
        }

    @control_app.get(f"{CONTROL_PREFIX}/instruction-receipt")
    async def instruction_receipt(request: Request, hostname: str):
        require_control(request)
        try:
            receipt = state.latest_instruction_receipt(hostname)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Instruction receipt not found"
            ) from exc
        return {
            "hostname": receipt["hostname"],
            "instruction_url": receipt["instruction_url"],
            "message_id": receipt["message_id"],
        }

    provider_route = (
        f"{CONTROL_PREFIX}/provider/{{run_id}}/{{provider_token}}/v2/"
        "domainTemplates/providers/{provider_id}/services/{service_id}/apply"
    )

    def require_provider_path(
        *, run_id: str, provider_token: str, provider_id: str, service_id: str
    ) -> None:
        if not (
            hmac.compare_digest(run_id, environment.run_id)
            and hmac.compare_digest(provider_token, provider_path_token)
            and provider_id == DOMAIN_CONNECT_PROVIDER_ID
            and service_id == DOMAIN_CONNECT_SERVICE_ID
        ):
            raise HTTPException(status_code=404, detail="Not found")

    @control_app.get(provider_route, response_class=HTMLResponse)
    async def provider_consent(
        request: Request,
        run_id: str,
        provider_token: str,
        provider_id: str,
        service_id: str,
    ):
        require_provider_path(
            run_id=run_id,
            provider_token=provider_token,
            provider_id=provider_id,
            service_id=service_id,
        )
        values = _provider_request_values(
            request,
            public_key=public_key,
            expected_key_id=key_id,
            environment=environment,
        )
        try:
            state.require_host(values["hostname"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=404, detail="Testbed hostname not found"
            ) from exc
        hostname = html.escape(values["hostname"])
        txt_name = html.escape(f"_tsw-storefront.{values['hostname']}")
        txt_value = html.escape(f"tsw-verification={values['verificationToken']}")
        return HTMLResponse(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Cloudflare Testbed DNS consent</title></head><body>"
            "<main><p>Deterministic testbed provider — no external DNS account.</p>"
            f"<h1>Authorize DNS changes for {hostname}</h1>"
            "<p>The testbed provider will publish exactly these records:</p><ul>"
            f"<li>TXT <code>{txt_name}</code> = <code>{txt_value}</code></li>"
            f"<li>CNAME <code>{hostname}</code> = <code>{CNAME_TARGET}</code></li>"
            "</ul><form method='post'>"
            "<button type='submit' name='decision' value='authorize'>Authorize DNS changes</button>"
            "<button type='submit' name='decision' value='authorize_without_dns'>Authorize callback without publishing DNS (testbed)</button>"
            "<button type='submit' name='decision' value='cancel'>Cancel</button>"
            "</form></main></body></html>"
        )

    @control_app.post(provider_route)
    async def provider_decision(
        request: Request,
        run_id: str,
        provider_token: str,
        provider_id: str,
        service_id: str,
    ):
        require_provider_path(
            run_id=run_id,
            provider_token=provider_token,
            provider_id=provider_id,
            service_id=service_id,
        )
        values = _provider_request_values(
            request,
            public_key=public_key,
            expected_key_id=key_id,
            environment=environment,
        )
        raw_body = await request.body()
        body = parse_qs(raw_body.decode("utf-8", errors="strict"))
        decision = body.get("decision", [""])[0]
        if decision not in {"authorize", "authorize_without_dns", "cancel"}:
            raise HTTPException(status_code=422, detail="Choose authorize or cancel")
        if decision == "authorize":
            try:
                published = await state.publish_claim(
                    mongo_client=mongo_client,
                    domain_service=domain_service,
                    hostname=values["hostname"],
                    expected_token=values["verificationToken"],
                )
            except (KeyError, ValueError) as exc:
                raise HTTPException(
                    status_code=404, detail="Testbed hostname not found"
                ) from exc
            if not published:
                raise HTTPException(
                    status_code=409, detail="DNS claim no longer exists"
                )
        callback_url = _local_callback_url(
            environment,
            values["redirect_uri"],
            cancelled=decision == "cancel",
        )
        return RedirectResponse(callback_url, status_code=303)

    dispatcher = StorefrontHarnessDispatcher(
        production_app=production_app,
        control_app=control_app,
        environment=environment,
    )
    return StorefrontProviderHarnessBundle(
        app=dispatcher,
        state=state,
        domain_service=domain_service,
        domain_connect_service=domain_connect_service,
        reconciliation_service=reconciliation_service,
        _restore=restore,
    )
