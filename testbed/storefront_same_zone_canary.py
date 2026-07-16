#!/usr/bin/env python3
"""Authorized same-zone Cloudflare for SaaS infrastructure canary.

This driver is deliberately separate from the customer-domain browser E2E. It
proves only the provider-owned ``thespecialwedding.com`` fallback origin,
friendly CNAME target, custom-hostname/certificate lifecycle, edge routing, and
exact cleanup. It can never mark an independently authoritative customer-DNS
row as passed.

The driver creates one exact, previously unused CNAME and one exact Cloudflare
custom hostname, then deletes both in ``finally``. Every mutation requires a
run-bound authorization string, exact hostname/zone allowlists, independently
scoped DNS and SaaS tokens, and the production rollout fences.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Awaitable, Callable, Mapping

import httpx

from app.services.storefront_domain_service import normalize_custom_hostname
from testbed.storefront_testbed_safety import parse_exact_hostname_allowlist


API_ROOT = "https://api.cloudflare.com/client/v4"
PLATFORM_ZONE = "thespecialwedding.com"
EXPECTED_CNAME_TARGET = "domains.thespecialwedding.com"
EXPECTED_FALLBACK_ORIGIN = "storefront-origin.thespecialwedding.com"
RESERVED_HOSTNAMES = frozenset(
    {
        EXPECTED_CNAME_TARGET,
        EXPECTED_FALLBACK_ORIGIN,
        "domainconnect.thespecialwedding.com",
    }
)
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{11,79}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _exact_values(value: str | None) -> frozenset[str]:
    raw = (value or "").strip()
    if not raw:
        return frozenset()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Exact identifier allowlist is not valid JSON") from exc
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) and item.strip() for item in parsed
        ):
            raise RuntimeError("Exact identifier allowlist must contain strings")
        values = parsed
    else:
        values = raw.split(",")
    normalized = frozenset(item.strip() for item in values if item.strip())
    if any("*" in item or "/" in item for item in normalized):
        raise RuntimeError("Exact identifier allowlists do not permit patterns")
    return normalized


def _enabled(environment: Mapping[str, str], name: str) -> bool:
    return environment.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SameZoneCanaryConfig:
    run_id: str
    hostname: str
    zone_id: str
    saas_token: str
    dns_token: str
    cname_target: str
    fallback_origin: str
    poll_timeout_seconds: int
    poll_interval_seconds: float
    artifact_path: Path


def load_same_zone_canary_config(
    environment: Mapping[str, str],
) -> SameZoneCanaryConfig:
    """Validate all external-mutation fences without returning secret values."""

    if environment.get("TESTBED_NON_INTERACTIVE", "").strip() != "1":
        raise RuntimeError("Same-zone canary requires TESTBED_NON_INTERACTIVE=1")
    if environment.get("TESTBED_STOREFRONT_EXTERNAL_MODE", "").strip() != "live":
        raise RuntimeError("Same-zone canary requires live external mode")

    run_id = environment.get("TESTBED_STOREFRONT_SAME_ZONE_CANARY_RUN_ID", "").strip()
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RuntimeError("Same-zone canary run ID must be a 12-80 character nonce")

    raw_hostname = environment.get("TESTBED_STOREFRONT_CUSTOM_DOMAIN", "").strip()
    try:
        hostname = normalize_custom_hostname(raw_hostname, platform_domains=())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Same-zone canary hostname is invalid") from exc
    if not hostname.endswith(f".{PLATFORM_ZONE}") or hostname in RESERVED_HOSTNAMES:
        raise RuntimeError(
            "Same-zone canary must be a non-reserved subdomain of thespecialwedding.com"
        )
    if hostname.count(".") != 2:
        raise RuntimeError(
            "Same-zone canary uses one exact host label beneath the zone"
        )

    allowed_hostnames = parse_exact_hostname_allowlist(
        environment.get("TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS")
    )
    pilot_hostnames = parse_exact_hostname_allowlist(
        environment.get("STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES")
    )
    if hostname not in allowed_hostnames or hostname not in pilot_hostnames:
        raise RuntimeError(
            "Same-zone canary hostname must appear in both exact test and rollout allowlists"
        )
    if environment.get("STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE", "").strip() != (
        "allowlist"
    ):
        raise RuntimeError("Same-zone canary requires allowlist rollout mode")

    for flag in (
        "STOREFRONT_CUSTOM_DOMAINS_ENABLED",
        "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED",
        "STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED",
    ):
        if not _enabled(environment, flag):
            raise RuntimeError(f"Same-zone canary requires {flag}=true")

    zone_id = environment.get("CLOUDFLARE_ZONE_ID", "").strip()
    allowed_zone_ids = _exact_values(
        environment.get("TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ZONE_IDS")
    )
    if not zone_id or zone_id not in allowed_zone_ids:
        raise RuntimeError("Cloudflare zone must match the exact canary zone allowlist")

    saas_token = environment.get("CLOUDFLARE_SAAS_API_TOKEN", "").strip()
    dns_token = environment.get("CLOUDFLARE_PLATFORM_DNS_API_TOKEN", "").strip()
    if not saas_token or not dns_token:
        raise RuntimeError("Separate SaaS and platform-DNS tokens are required")
    if saas_token == dns_token:
        raise RuntimeError("The SaaS token must not be reused for platform DNS")

    cname_target = environment.get("STOREFRONT_CNAME_TARGET", "").strip().lower()
    fallback_origin = environment.get("STOREFRONT_FALLBACK_ORIGIN", "").strip().lower()
    if cname_target != EXPECTED_CNAME_TARGET:
        raise RuntimeError(
            "Same-zone canary requires the production friendly CNAME target"
        )
    if fallback_origin != EXPECTED_FALLBACK_ORIGIN:
        raise RuntimeError("Same-zone canary requires the production fallback origin")

    expected_authorization = f"{run_id}:{hostname}:CREATE_AND_DELETE"
    if (
        environment.get("TESTBED_STOREFRONT_SAME_ZONE_CANARY_AUTHORIZATION", "").strip()
        != expected_authorization
    ):
        raise RuntimeError("Run-bound same-zone create/delete authorization is missing")

    try:
        poll_timeout = int(
            environment.get("TESTBED_STOREFRONT_CANARY_TIMEOUT_SECONDS", "1200")
        )
        poll_interval = float(
            environment.get("TESTBED_STOREFRONT_CANARY_POLL_SECONDS", "10")
        )
    except ValueError as exc:
        raise RuntimeError("Same-zone canary polling values are invalid") from exc
    if not 60 <= poll_timeout <= 3600 or not 1 <= poll_interval <= 60:
        raise RuntimeError("Same-zone canary polling bounds are unsafe")

    artifact_value = environment.get(
        "TESTBED_STOREFRONT_SAME_ZONE_CANARY_ARTIFACT",
        f"testbed/.testbed/artifacts/storefront/same-zone/{run_id}.json",
    ).strip()
    artifact_path = Path(artifact_value).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[1]
    allowed_root = (repository_root / "testbed" / ".testbed" / "artifacts").resolve()
    if allowed_root not in artifact_path.parents:
        raise RuntimeError(
            "Same-zone canary artifact must remain under testbed artifacts"
        )

    return SameZoneCanaryConfig(
        run_id=run_id,
        hostname=hostname,
        zone_id=zone_id,
        saas_token=saas_token,
        dns_token=dns_token,
        cname_target=cname_target,
        fallback_origin=fallback_origin,
        poll_timeout_seconds=poll_timeout,
        poll_interval_seconds=poll_interval,
        artifact_path=artifact_path,
    )


class CloudflareCanaryClient:
    """Two-token Cloudflare client whose exceptions never include secrets."""

    def __init__(
        self,
        config: SameZoneCanaryConfig,
        *,
        http_client: httpx.AsyncClient | Any | None = None,
    ) -> None:
        self.config = config
        self._http = http_client

    async def _request(
        self,
        *,
        token: str,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        url = f"{API_ROOT}/zones/{self.config.zone_id}{path}"
        kwargs: dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": 15.0,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        if params is not None:
            kwargs["params"] = params
        try:
            if self._http is not None:
                response = await self._http.request(method, url, **kwargs)
            else:
                async with httpx.AsyncClient(
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise RuntimeError("Cloudflare canary transport failed") from exc
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Cloudflare canary received an unreadable response"
            ) from exc
        if (
            not response.is_success
            or not isinstance(payload, dict)
            or payload.get("success") is not True
        ):
            raise RuntimeError(
                f"Cloudflare canary operation failed with HTTP {response.status_code}"
            )
        return payload.get("result")

    async def list_dns_records(self, name: str) -> list[dict[str, Any]]:
        result = await self._request(
            token=self.config.dns_token,
            method="GET",
            path="/dns_records",
            params={"name.exact": name, "per_page": "100"},
        )
        if not isinstance(result, list) or any(
            not isinstance(row, dict) for row in result
        ):
            raise RuntimeError("Cloudflare DNS list response is invalid")
        return result

    async def create_canary_dns(self) -> dict[str, Any]:
        result = await self._request(
            token=self.config.dns_token,
            method="POST",
            path="/dns_records",
            json_body={
                "type": "CNAME",
                "name": self.config.hostname,
                "content": self.config.cname_target,
                "proxied": True,
                "ttl": 1,
                "comment": f"WeddingWebApp storefront canary {self.config.run_id}",
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("id"), str):
            raise RuntimeError("Cloudflare DNS create response is invalid")
        return result

    async def delete_dns(self, record_id: str) -> dict[str, Any]:
        result = await self._request(
            token=self.config.dns_token,
            method="DELETE",
            path=f"/dns_records/{record_id}",
        )
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare DNS delete response is invalid")
        return result

    async def get_fallback_origin(self) -> dict[str, Any]:
        result = await self._request(
            token=self.config.saas_token,
            method="GET",
            path="/custom_hostnames/fallback_origin",
        )
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare fallback-origin response is invalid")
        return result

    async def list_custom_hostnames(self) -> list[dict[str, Any]]:
        result = await self._request(
            token=self.config.saas_token,
            method="GET",
            path="/custom_hostnames",
            params={"hostname": self.config.hostname, "per_page": "50"},
        )
        if not isinstance(result, list) or any(
            not isinstance(row, dict) for row in result
        ):
            raise RuntimeError("Cloudflare custom-hostname list response is invalid")
        return [
            row
            for row in result
            if str(row.get("hostname") or "").strip().lower() == self.config.hostname
        ]

    async def create_custom_hostname(self) -> dict[str, Any]:
        result = await self._request(
            token=self.config.saas_token,
            method="POST",
            path="/custom_hostnames",
            json_body={
                "hostname": self.config.hostname,
                "ssl": {
                    "method": "txt",
                    "type": "dv",
                    "settings": {"min_tls_version": "1.2"},
                },
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("id"), str):
            raise RuntimeError("Cloudflare custom-hostname create response is invalid")
        return result

    async def get_custom_hostname(self, provider_id: str) -> dict[str, Any]:
        result = await self._request(
            token=self.config.saas_token,
            method="GET",
            path=f"/custom_hostnames/{provider_id}",
        )
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare custom-hostname response is invalid")
        return result

    async def delete_custom_hostname(self, provider_id: str) -> dict[str, Any]:
        result = await self._request(
            token=self.config.saas_token,
            method="DELETE",
            path=f"/custom_hostnames/{provider_id}",
        )
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare custom-hostname delete response is invalid")
        return result


class SameZoneCanaryRunner:
    def __init__(
        self,
        config: SameZoneCanaryConfig,
        *,
        client: CloudflareCanaryClient | Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = _utc_now,
        route_probe: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self.client = client or CloudflareCanaryClient(config)
        self._sleep = sleep
        self._now = now
        self._route_probe = route_probe or self._probe_route

    async def _probe_route(self, hostname: str) -> dict[str, Any]:
        url = f"https://{hostname}/api/health-ssr"
        async with httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=15.0,
        ) as client:
            response = await client.get(url)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Canary HTTPS route returned unreadable content"
            ) from exc
        if response.status_code != 200 or payload != {
            "status": "ok",
            "api_base": "redacted",
        }:
            raise RuntimeError(
                "Canary HTTPS route did not reach the expected application"
            )
        if not response.headers.get("cf-ray"):
            raise RuntimeError(
                "Canary HTTPS route did not include Cloudflare edge evidence"
            )
        return {"status_code": response.status_code, "cloudflare_edge": True}

    @staticmethod
    def _dns_record_matches(row: Mapping[str, Any], *, name: str, content: str) -> bool:
        return (
            str(row.get("name") or "").lower().rstrip(".") == name
            and str(row.get("content") or "").lower().rstrip(".") == content
            and row.get("proxied") is True
        )

    @staticmethod
    def _provider_created_within(
        row: Mapping[str, Any], *, started_at: datetime, observed_at: datetime
    ) -> bool:
        raw = row.get("created_at")
        if not isinstance(raw, str):
            return False
        try:
            created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (
            started_at - timedelta(minutes=1)
            <= created
            <= observed_at + timedelta(minutes=1)
        )

    async def _verify_platform_records(self) -> dict[str, Any]:
        fallback = await self.client.get_fallback_origin()
        if (
            str(fallback.get("origin") or "").lower().rstrip(".")
            != self.config.fallback_origin
            or fallback.get("status") != "active"
        ):
            raise RuntimeError("Cloudflare fallback origin is not active and exact")

        target_rows = await self.client.list_dns_records(self.config.cname_target)
        if len(target_rows) != 1 or not self._dns_record_matches(
            target_rows[0],
            name=self.config.cname_target,
            content=self.config.fallback_origin,
        ):
            raise RuntimeError("Friendly CNAME target is not one exact proxied record")

        origin_rows = await self.client.list_dns_records(self.config.fallback_origin)
        valid_origins = [
            row
            for row in origin_rows
            if str(row.get("name") or "").lower().rstrip(".")
            == self.config.fallback_origin
            and row.get("proxied") is True
            and row.get("type") in {"A", "AAAA", "CNAME"}
        ]
        if not valid_origins:
            raise RuntimeError("Fallback-origin DNS record is not proxied")
        return {
            "fallback_origin": "active",
            "cname_target": "exact_proxied",
            "origin_dns": "proxied",
        }

    async def _wait_until_active(self, provider_id: str) -> dict[str, Any]:
        deadline = self._now() + timedelta(seconds=self.config.poll_timeout_seconds)
        last: dict[str, Any] = {}
        while self._now() < deadline:
            last = await self.client.get_custom_hostname(provider_id)
            if (
                str(last.get("id") or "") != provider_id
                or str(last.get("hostname") or "").lower() != self.config.hostname
            ):
                raise RuntimeError("Cloudflare returned a mismatched canary hostname")
            ssl = last.get("ssl") if isinstance(last.get("ssl"), dict) else {}
            if last.get("status") == "active" and ssl.get("status") == "active":
                return last
            await self._sleep(self.config.poll_interval_seconds)
        raise RuntimeError(
            "Canary custom hostname or certificate did not become active before timeout"
        )

    async def run(self) -> dict[str, Any]:
        started_at = self._now()
        provider_id: str | None = None
        dns_record_id: str | None = None
        checks: dict[str, Any] = {}
        cleanup = {
            "provider_hostname": "not_created",
            "dns_record": "not_created",
        }
        failure: str | None = None
        try:
            checks["platform"] = await self._verify_platform_records()
            if await self.client.list_custom_hostnames():
                raise RuntimeError(
                    "Canary hostname already exists at the SaaS provider"
                )
            if await self.client.list_dns_records(self.config.hostname):
                raise RuntimeError("Canary hostname already has DNS records")

            create_started_at = self._now()
            try:
                provider = await self.client.create_custom_hostname()
                checks["provider_create_reconciliation"] = "direct_receipt"
            except Exception:
                # A transport timeout can happen after Cloudflare committed the
                # create. Reconcile only one exact hostname demonstrably created
                # inside this fixed attempt window; never issue a blind retry.
                candidates = [
                    row
                    for row in await self.client.list_custom_hostnames()
                    if self._provider_created_within(
                        row,
                        started_at=create_started_at,
                        observed_at=self._now(),
                    )
                ]
                if len(candidates) != 1:
                    raise RuntimeError(
                        "Canary custom-hostname create outcome is ambiguous; operator cleanup is required"
                    )
                provider = candidates[0]
                checks["provider_create_reconciliation"] = "one_exact_new_id_adopted"
            provider_id = provider["id"]
            if str(provider.get("hostname") or "").lower() != self.config.hostname:
                raise RuntimeError(
                    "Created provider hostname does not match the canary"
                )

            dns_record = await self.client.create_canary_dns()
            dns_record_id = dns_record["id"]
            if not self._dns_record_matches(
                dns_record,
                name=self.config.hostname,
                content=self.config.cname_target,
            ):
                raise RuntimeError(
                    "Created canary DNS record does not match authorization"
                )

            active = await self._wait_until_active(provider_id)
            checks["provider_hostname"] = active.get("status")
            checks["ssl_certificate"] = (
                active.get("ssl", {}).get("status")
                if isinstance(active.get("ssl"), dict)
                else "unknown"
            )
            checks["https_route"] = await self._route_probe(self.config.hostname)
        except Exception as exc:
            failure = (
                str(exc) if isinstance(exc, RuntimeError) else exc.__class__.__name__
            )
        finally:
            if provider_id:
                try:
                    await self.client.delete_custom_hostname(provider_id)
                    remaining = await self.client.list_custom_hostnames()
                    cleanup["provider_hostname"] = (
                        "deleted" if not remaining else "delete_unconfirmed"
                    )
                except Exception:
                    try:
                        remaining = await self.client.list_custom_hostnames()
                        cleanup["provider_hostname"] = (
                            "deleted_after_unknown_outcome"
                            if not remaining
                            else "delete_failed"
                        )
                    except Exception:
                        cleanup["provider_hostname"] = "delete_failed"
            if dns_record_id:
                try:
                    await self.client.delete_dns(dns_record_id)
                    remaining_dns = await self.client.list_dns_records(
                        self.config.hostname
                    )
                    cleanup["dns_record"] = (
                        "deleted" if not remaining_dns else "delete_unconfirmed"
                    )
                except Exception:
                    try:
                        remaining_dns = await self.client.list_dns_records(
                            self.config.hostname
                        )
                        cleanup["dns_record"] = (
                            "deleted_after_unknown_outcome"
                            if not remaining_dns
                            else "delete_failed"
                        )
                    except Exception:
                        cleanup["dns_record"] = "delete_failed"

        cleanup_passed = cleanup["provider_hostname"] in {
            "deleted",
            "deleted_after_unknown_outcome",
            "not_created",
        } and cleanup["dns_record"] in {
            "deleted",
            "deleted_after_unknown_outcome",
            "not_created",
        }
        status = "PASSED" if failure is None and cleanup_passed else "FAILED"
        receipt = {
            "schema_version": 1,
            "evidence_class": "same_zone_platform_infrastructure",
            "independent_customer_provider": "BLOCKED",
            "run_id": self.config.run_id,
            "hostname": self.config.hostname,
            "started_at": started_at.isoformat(),
            "finished_at": self._now().isoformat(),
            "status": status,
            "checks": checks,
            "cleanup": cleanup,
            "failure": failure,
        }
        self.config.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.artifact_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt


def _safe_config_report(config: SameZoneCanaryConfig) -> dict[str, Any]:
    safe = asdict(config)
    safe["saas_token"] = "configured"
    safe["dns_token"] = "configured"
    safe["artifact_path"] = str(config.artifact_path)
    return {
        "status": "BLOCKED",
        "evidence_class": "same_zone_platform_infrastructure",
        "external_mutations": "not_run",
        "independent_customer_provider": "BLOCKED",
        "config": safe,
    }


async def _async_main(args: argparse.Namespace) -> int:
    config = load_same_zone_canary_config(os.environ)
    if args.config_only:
        print(json.dumps(_safe_config_report(config), indent=2, sort_keys=True))
        return 0
    receipt = await SameZoneCanaryRunner(config).run()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Validate fences without network calls or mutations; status remains BLOCKED.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_async_main(args))
    except RuntimeError as exc:
        print(f"same-zone canary refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
