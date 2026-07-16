from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from testbed.storefront_same_zone_canary import (
    SameZoneCanaryRunner,
    load_same_zone_canary_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "canary_20260715_abcd"
HOSTNAME = "canary-20260715.thespecialwedding.com"
ZONE_ID = "0123456789abcdef0123456789abcdef"


def _environment() -> dict[str, str]:
    return {
        "TESTBED_NON_INTERACTIVE": "1",
        "TESTBED_STOREFRONT_EXTERNAL_MODE": "live",
        "TESTBED_STOREFRONT_SAME_ZONE_CANARY_RUN_ID": RUN_ID,
        "TESTBED_STOREFRONT_CUSTOM_DOMAIN": HOSTNAME,
        "TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS": json.dumps([HOSTNAME]),
        "TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ZONE_IDS": json.dumps([ZONE_ID]),
        "TESTBED_STOREFRONT_SAME_ZONE_CANARY_AUTHORIZATION": (
            f"{RUN_ID}:{HOSTNAME}:CREATE_AND_DELETE"
        ),
        "STOREFRONT_CUSTOM_DOMAINS_ENABLED": "true",
        "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED": "true",
        "STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED": "true",
        "STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE": "allowlist",
        "STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES": json.dumps([HOSTNAME]),
        "CLOUDFLARE_ZONE_ID": ZONE_ID,
        "CLOUDFLARE_SAAS_API_TOKEN": "saas-token-for-custom-hostname-only",
        "CLOUDFLARE_PLATFORM_DNS_API_TOKEN": "dns-token-for-owned-zone-only",
        "STOREFRONT_CNAME_TARGET": "domains.thespecialwedding.com",
        "STOREFRONT_FALLBACK_ORIGIN": "storefront-origin.thespecialwedding.com",
        "TESTBED_STOREFRONT_CANARY_TIMEOUT_SECONDS": "60",
        "TESTBED_STOREFRONT_CANARY_POLL_SECONDS": "1",
    }


def test_same_zone_canary_requires_exact_run_bound_mutation_fences():
    environment = _environment()
    config = load_same_zone_canary_config(environment)
    assert config.hostname == HOSTNAME
    assert config.zone_id == ZONE_ID
    assert config.saas_token != config.dns_token

    candidates: list[dict[str, str]] = []
    for mutate in (
        lambda value: value.pop("TESTBED_NON_INTERACTIVE"),
        lambda value: value.__setitem__(
            "TESTBED_STOREFRONT_SAME_ZONE_CANARY_AUTHORIZATION", "wrong"
        ),
        lambda value: value.__setitem__(
            "TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS", "[]"
        ),
        lambda value: value.__setitem__(
            "STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES", "[]"
        ),
        lambda value: value.__setitem__(
            "TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ZONE_IDS", '["*"]'
        ),
        lambda value: value.__setitem__(
            "CLOUDFLARE_PLATFORM_DNS_API_TOKEN", value["CLOUDFLARE_SAAS_API_TOKEN"]
        ),
        lambda value: value.__setitem__(
            "TESTBED_STOREFRONT_CUSTOM_DOMAIN", "domains.thespecialwedding.com"
        ),
    ):
        candidate = _environment()
        mutate(candidate)
        candidates.append(candidate)

    for candidate in candidates:
        with pytest.raises(RuntimeError):
            load_same_zone_canary_config(candidate)


def test_platform_dns_token_is_documented_but_not_in_application_runtime():
    root_env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    testbed_env = (REPO_ROOT / "testbed" / ".env.example").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    guide = (
        REPO_ROOT / "docs" / "guides" / "STOREFRONT_INFRASTRUCTURE_SETUP.md"
    ).read_text(encoding="utf-8")

    assert "CLOUDFLARE_PLATFORM_DNS_API_TOKEN=" in root_env
    assert "CLOUDFLARE_PLATFORM_DNS_API_TOKEN=" in testbed_env
    assert "CLOUDFLARE_PLATFORM_DNS_API_TOKEN" not in compose
    assert "storefront_same_zone_canary.py" in guide
    assert "independent-customer check" in guide


class FakeCanaryClient:
    def __init__(
        self,
        *,
        fail_route_cleanup: bool = False,
        create_commits_then_times_out: bool = False,
    ):
        self.provider_exists = False
        self.dns_exists = False
        self.fail_route_cleanup = fail_route_cleanup
        self.create_commits_then_times_out = create_commits_then_times_out
        self.deleted_provider_ids: list[str] = []
        self.deleted_dns_ids: list[str] = []

    async def get_fallback_origin(self):
        return {
            "origin": "storefront-origin.thespecialwedding.com",
            "status": "active",
        }

    async def list_dns_records(self, name: str):
        if name == "domains.thespecialwedding.com":
            return [
                {
                    "id": "target",
                    "type": "CNAME",
                    "name": name,
                    "content": "storefront-origin.thespecialwedding.com",
                    "proxied": True,
                }
            ]
        if name == "storefront-origin.thespecialwedding.com":
            return [
                {
                    "id": "origin",
                    "type": "A",
                    "name": name,
                    "content": "192.0.2.10",
                    "proxied": True,
                }
            ]
        if name == HOSTNAME and self.dns_exists:
            return [
                {
                    "id": "dns-canary",
                    "type": "CNAME",
                    "name": HOSTNAME,
                    "content": "domains.thespecialwedding.com",
                    "proxied": True,
                }
            ]
        return []

    async def list_custom_hostnames(self):
        if not self.provider_exists:
            return []
        return [
            {
                "id": "cf-canary",
                "hostname": HOSTNAME,
                "created_at": "2026-07-15T12:00:00Z",
            }
        ]

    async def create_custom_hostname(self):
        self.provider_exists = True
        if self.create_commits_then_times_out:
            raise RuntimeError("simulated transport timeout")
        return {"id": "cf-canary", "hostname": HOSTNAME}

    async def create_canary_dns(self):
        self.dns_exists = True
        return {
            "id": "dns-canary",
            "type": "CNAME",
            "name": HOSTNAME,
            "content": "domains.thespecialwedding.com",
            "proxied": True,
        }

    async def get_custom_hostname(self, provider_id: str):
        assert provider_id == "cf-canary"
        return {
            "id": provider_id,
            "hostname": HOSTNAME,
            "status": "active",
            "ssl": {"status": "active"},
        }

    async def delete_custom_hostname(self, provider_id: str):
        self.deleted_provider_ids.append(provider_id)
        if self.fail_route_cleanup:
            raise RuntimeError("simulated safe cleanup failure")
        self.provider_exists = False
        return {"id": provider_id}

    async def delete_dns(self, record_id: str):
        self.deleted_dns_ids.append(record_id)
        self.dns_exists = False
        return {"id": record_id}


@pytest.mark.asyncio
async def test_same_zone_canary_proves_infrastructure_and_exact_cleanup(tmp_path: Path):
    config = replace(
        load_same_zone_canary_config(_environment()),
        artifact_path=tmp_path / "receipt.json",
    )
    client = FakeCanaryClient()

    async def route_probe(hostname: str):
        assert hostname == HOSTNAME
        return {"status_code": 200, "cloudflare_edge": True}

    runner = SameZoneCanaryRunner(
        config,
        client=client,
        route_probe=route_probe,
        now=lambda: datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    )
    receipt = await runner.run()

    assert receipt["status"] == "PASSED"
    assert receipt["evidence_class"] == "same_zone_platform_infrastructure"
    assert receipt["independent_customer_provider"] == "BLOCKED"
    assert receipt["checks"]["provider_hostname"] == "active"
    assert receipt["checks"]["ssl_certificate"] == "active"
    assert receipt["cleanup"] == {
        "provider_hostname": "deleted",
        "dns_record": "deleted",
    }
    assert client.deleted_provider_ids == ["cf-canary"]
    assert client.deleted_dns_ids == ["dns-canary"]
    assert json.loads(config.artifact_path.read_text(encoding="utf-8")) == receipt


@pytest.mark.asyncio
async def test_same_zone_canary_never_passes_when_exact_cleanup_is_unconfirmed(
    tmp_path: Path,
):
    config = replace(
        load_same_zone_canary_config(_environment()),
        artifact_path=tmp_path / "receipt.json",
    )
    client = FakeCanaryClient(fail_route_cleanup=True)

    async def route_probe(_hostname: str):
        return {"status_code": 200, "cloudflare_edge": True}

    receipt = await SameZoneCanaryRunner(
        config,
        client=client,
        route_probe=route_probe,
        now=lambda: datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    ).run()

    assert receipt["status"] == "FAILED"
    assert receipt["cleanup"]["provider_hostname"] == "delete_failed"
    assert receipt["cleanup"]["dns_record"] == "deleted"
    assert receipt["independent_customer_provider"] == "BLOCKED"


@pytest.mark.asyncio
async def test_same_zone_canary_reconciles_one_exact_unknown_create_without_retry(
    tmp_path: Path,
):
    config = replace(
        load_same_zone_canary_config(_environment()),
        artifact_path=tmp_path / "receipt.json",
    )
    client = FakeCanaryClient(create_commits_then_times_out=True)

    async def route_probe(_hostname: str):
        return {"status_code": 200, "cloudflare_edge": True}

    receipt = await SameZoneCanaryRunner(
        config,
        client=client,
        route_probe=route_probe,
        now=lambda: datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    ).run()

    assert receipt["status"] == "PASSED"
    assert (
        receipt["checks"]["provider_create_reconciliation"]
        == "one_exact_new_id_adopted"
    )
    assert client.deleted_provider_ids == ["cf-canary"]
