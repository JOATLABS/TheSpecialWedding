from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from app.services import config_validator
from testbed import storefront_configuration_doctor as doctor


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def configured_storefront(monkeypatch):
    values = {
        "storefront_custom_domains_enabled": False,
        "storefront_domain_connect_discovery_enabled": False,
        "storefront_domain_connect_authorization_enabled": False,
        "storefront_cloudflare_mutations_enabled": False,
        "storefront_cloudflare_cleanup_enabled": False,
        "storefront_custom_domain_rollout_mode": "allowlist",
        "storefront_custom_domain_pilot_hostnames": [],
        "storefront_custom_domain_pilot_owner_ids": [],
        "cloudflare_saas_api_token": None,
        "cloudflare_zone_id": None,
        "storefront_fallback_origin": None,
        "storefront_cname_target": None,
        "domain_connect_provider_id": "thespecialwedding.com",
        "domain_connect_service_id": "storefront-subdomain",
        "domain_connect_template_version": 1,
        "domain_connect_private_key": None,
        "domain_connect_key_id": "_dcpubkeyv1",
        "domain_connect_public_key_domain": "domainconnect.thespecialwedding.com",
        "domain_connect_callback_url": None,
        "cloudflare_account_id": "account-id",
        "cloudflare_api_token": "r2-control-secret",
        "s3_endpoint_url": "https://account-id.r2.cloudflarestorage.com",
        "s3_access_key_id": "r2-access-secret",
        "s3_secret_access_key": "r2-signing-secret",
        "s3_storefront_staging_bucket_name": "storefront-staging",
        "s3_blog_bucket_name": "storefront-public",
        "blog_media_domain": "https://media.thespecialwedding.com",
        "resend_api_key": "resend-secret",
        "resend_from_email": "storefront@thespecialwedding.com",
        "resend_from_name": "The Special Wedding",
        "storefront_runtime_revision": "git-sha-0123456789",
        "redis_enabled": True,
        "redis_host": "redis",
        "redis_port": 6379,
        "redis_password": "test-redis-password",
        "redis_db": 0,
        "redis_max_connections": 20,
        "trusted_proxy_cidrs": ["172.26.0.0/16"],
        "trusted_proxy_client_ip_header": "X-Real-IP",
    }
    for name, value in values.items():
        monkeypatch.setattr(config_validator.settings, name, value)
    monkeypatch.setattr(doctor, "_probe_redis_reachability", lambda: "reachable")
    return values


def _enable_domain_connect(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    values = {
        "storefront_custom_domains_enabled": True,
        "storefront_domain_connect_discovery_enabled": True,
        "storefront_domain_connect_authorization_enabled": True,
        "storefront_cloudflare_mutations_enabled": True,
        "storefront_cloudflare_cleanup_enabled": True,
        "storefront_custom_domain_pilot_hostnames": ["pilot.customer.example"],
        "cloudflare_saas_api_token": "dedicated-saas-secret",
        "cloudflare_zone_id": "zone-id",
        "storefront_fallback_origin": "storefront-origin.thespecialwedding.com",
        "storefront_cname_target": "domains.thespecialwedding.com",
        "domain_connect_provider_id": "thespecialwedding.com",
        "domain_connect_service_id": "storefront-subdomain",
        "domain_connect_template_version": 1,
        "domain_connect_private_key": private_key_pem,
        "domain_connect_key_id": "_dcpubkeyv1",
        "domain_connect_public_key_domain": "domainconnect.thespecialwedding.com",
        "domain_connect_callback_url": (
            "https://domainconnect.thespecialwedding.com/admin/storefront/"
            "custom-domain/domain-connect/callback"
        ),
    }
    for name, value in values.items():
        monkeypatch.setattr(config_validator.settings, name, value)
    return values


def test_doctor_passes_local_contract_and_keeps_external_evidence_blocked(
    configured_storefront,
):
    report = doctor.build_report()

    assert report["ok"] is True
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["configuration_contract"]["status"] == "PASS"
    assert checks["storefront_media"]["status"] == "PASS"
    assert checks["storefront_email"]["status"] == "PASS"
    assert checks["storefront_inquiry_shared_rate_limit"]["status"] == "PASS"
    assert checks["storefront_inquiry_client_ip"]["status"] == "PASS"
    assert checks["custom_domain_runtime"]["status"] == "PASS"
    assert checks["external_provider_acceptance"]["status"] == "BLOCKED"


def test_doctor_reports_redis_down_without_raw_exception_or_disabling_slug(
    monkeypatch, configured_storefront
):
    monkeypatch.setattr(doctor, "_probe_redis_reachability", lambda: "unreachable")

    report = doctor.build_report()
    check = next(
        item
        for item in report["checks"]
        if item["name"] == "storefront_inquiry_shared_rate_limit"
    )

    assert report["ok"] is False
    assert check == {
        "name": "storefront_inquiry_shared_rate_limit",
        "status": "FAIL",
        "detail": (
            "Shared Redis is unavailable (unreachable). New storefront inquiries "
            "must remain fail-closed; storefront pages and the platform slug remain "
            "available."
        ),
    }
    assert "ConnectionError" not in check["detail"]


def test_doctor_fails_closed_when_shared_limiter_or_proxy_trust_is_disabled(
    monkeypatch, configured_storefront
):
    monkeypatch.setattr(config_validator.settings, "redis_enabled", False)
    monkeypatch.setattr(config_validator.settings, "trusted_proxy_cidrs", [])
    monkeypatch.setattr(
        config_validator.settings, "trusted_proxy_client_ip_header", None
    )

    report = doctor.build_report()
    checks = {check["name"]: check for check in report["checks"]}

    assert report["ok"] is False
    assert checks["storefront_inquiry_shared_rate_limit"]["status"] == "FAIL"
    assert checks["storefront_inquiry_client_ip"]["status"] == "FAIL"


def test_doctor_validates_enabled_domain_connect_without_printing_secrets(
    monkeypatch, configured_storefront, capsys
):
    secret_values = _enable_domain_connect(monkeypatch)

    exit_code = doctor.main(["--json"])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 0
    assert report["ok"] is True
    for field in (
        "cloudflare_saas_api_token",
        "domain_connect_private_key",
    ):
        assert secret_values[field] not in output
    assert configured_storefront["cloudflare_api_token"] not in output


def test_authorization_cross_field_validation_rejects_unsafe_configuration(
    monkeypatch, configured_storefront
):
    _enable_domain_connect(monkeypatch)
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_private_key",
        "not-a-private-key-super-secret",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_callback_url",
        "http://127.0.0.1:8000/callback?token=secret",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_provider_id",
        "other-provider.example",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_service_id",
        "other-service",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_template_version",
        2,
    )
    monkeypatch.setattr(config_validator.settings, "domain_connect_key_id", "bad/key")
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_public_key_domain",
        "keys.attacker.example",
    )

    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )
    combined = "\n".join(recommendations)

    for label in (
        "DOMAIN_CONNECT_PRIVATE_KEY",
        "DOMAIN_CONNECT_CALLBACK_URL",
        "DOMAIN_CONNECT_PROVIDER_ID",
        "DOMAIN_CONNECT_SERVICE_ID",
        "DOMAIN_CONNECT_TEMPLATE_VERSION",
        "DOMAIN_CONNECT_KEY_ID",
        "DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN",
    ):
        assert label in combined
    assert "not-a-private-key-super-secret" not in combined
    assert "token=secret" not in combined


def test_mutations_in_empty_allowlist_mode_fail_readiness_closed(
    monkeypatch, configured_storefront
):
    _enable_domain_connect(monkeypatch)
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domain_pilot_hostnames", []
    )
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domain_pilot_owner_ids", []
    )

    readiness = config_validator.get_storefront_domain_readiness()
    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert readiness == {
        "enabled": True,
        "ready": False,
        "reason_code": "rollout_unavailable",
        "missing": [],
    }
    assert any(
        "no valid exact pilot hostname or owner" in item for item in recommendations
    )


def test_mutation_readiness_requires_disconnect_cleanup_first(
    monkeypatch, configured_storefront
):
    _enable_domain_connect(monkeypatch)
    monkeypatch.setattr(
        config_validator.settings, "storefront_cloudflare_cleanup_enabled", False
    )

    assert config_validator.get_storefront_domain_readiness() == {
        "enabled": True,
        "ready": False,
        "reason_code": "configuration_unavailable",
        "missing": ["STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED"],
    }


def test_mutation_flag_requires_product_cleanup_and_an_exact_pilot(
    monkeypatch, configured_storefront
):
    monkeypatch.setattr(
        config_validator.settings, "storefront_cloudflare_mutations_enabled", True
    )
    monkeypatch.setattr(
        config_validator.settings, "cloudflare_saas_api_token", "saas-secret"
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", "zone-id")
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_fallback_origin",
        "storefront-origin.thespecialwedding.com",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_cname_target",
        "domains.thespecialwedding.com",
    )

    combined = "\n".join(
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert "STOREFRONT_CUSTOM_DOMAINS_ENABLED" in combined
    assert "STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED" in combined
    assert "STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES/OWNER_IDS" in combined


def test_domain_connect_authorization_requires_discovery_and_provider_mutations(
    monkeypatch, configured_storefront
):
    _enable_domain_connect(monkeypatch)
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_domain_connect_discovery_enabled",
        False,
    )
    monkeypatch.setattr(
        config_validator.settings, "storefront_cloudflare_mutations_enabled", False
    )

    combined = "\n".join(
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert "STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED" in combined
    assert "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED" in combined


def test_malformed_domain_connect_callback_port_fails_closed_without_crashing(
    monkeypatch, configured_storefront
):
    _enable_domain_connect(monkeypatch)
    monkeypatch.setattr(
        config_validator.settings,
        "domain_connect_callback_url",
        "https://domainconnect.thespecialwedding.com:not-a-port/callback",
    )

    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert any("DOMAIN_CONNECT_CALLBACK_URL" in item for item in recommendations)


def test_doctor_fails_when_media_email_or_revision_is_incomplete(
    monkeypatch, configured_storefront
):
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )
    monkeypatch.setattr(config_validator.settings, "resend_api_key", None)
    monkeypatch.setattr(
        config_validator.settings, "storefront_runtime_revision", "unknown"
    )

    report = doctor.build_report()

    assert report["ok"] is False
    assert set(report["failed_checks"]) == {
        "storefront_media",
        "storefront_email",
        "runtime_revision",
    }


def test_operator_guide_wires_the_exact_non_mutating_doctor_command():
    guide = (
        REPO_ROOT / "docs" / "guides" / "STOREFRONT_INFRASTRUCTURE_SETUP.md"
    ).read_text(encoding="utf-8")

    assert (REPO_ROOT / "testbed" / "storefront_configuration_doctor.py").is_file()
    assert "testbed/storefront_configuration_doctor.py" in guide
    assert "external_provider_acceptance` row always remains `BLOCKED" in guide


def test_documented_direct_doctor_invocation_is_import_safe_and_redacted():
    marker = "direct-doctor-secret-must-not-print"
    environment = {
        **os.environ,
        "PYTHONPATH": ".",
        "CLOUDFLARE_API_TOKEN": marker,
        "CLOUDFLARE_SAAS_API_TOKEN": marker,
        "RESEND_API_KEY": marker,
        "DOMAIN_CONNECT_PRIVATE_KEY": marker,
    }

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "testbed" / "storefront_configuration_doctor.py"),
            "--json",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode in {0, 1}
    assert json.loads(completed.stdout)["command_scope"] == (
        "local_configuration_and_redis_reachability"
    )
    assert "Traceback" not in completed.stderr
    assert marker not in completed.stdout
    assert marker not in completed.stderr
