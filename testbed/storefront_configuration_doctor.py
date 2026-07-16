#!/usr/bin/env python3
"""Read-only storefront deployment configuration doctor.

This command inspects canonical loaded settings, checked-in contracts, and the
configured Redis dependency used for production storefront inquiry protection.
It never calls Cloudflare, R2, Resend, DNS, Mongo, or the application API, and it
never prints credential values. External provider acceptance remains a separate
blocked evidence row.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Iterable

from redis import Redis
from redis.exceptions import AuthenticationError as RedisAuthenticationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.settings import settings
from app.services import config_validator

if __package__:
    from testbed.validate_storefront_domain_connect_template import (
        TemplateValidationError,
        validate_template,
    )
else:  # Direct documented invocation: python testbed/storefront_configuration_doctor.py
    from validate_storefront_domain_connect_template import (
        TemplateValidationError,
        validate_template,
    )


REPO_ROOT = Path(__file__).resolve().parent.parent
_REVISION_PLACEHOLDERS = frozenset(
    {"unknown", "unset", "replace-with-deployment-revision"}
)
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def _is_present(value: object) -> bool:
    return bool(str(value or "").strip())


def _missing_labels(pairs: Iterable[tuple[str, object]]) -> list[str]:
    return [label for label, value in pairs if not _is_present(value)]


def _configuration_contract_check() -> DoctorCheck:
    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )
    if recommendations:
        return DoctorCheck(
            name="configuration_contract",
            status="FAIL",
            detail=" | ".join(recommendations),
        )
    return DoctorCheck(
        name="configuration_contract",
        status="PASS",
        detail="Enabled storefront flags have consistent fail-closed prerequisites.",
    )


def _media_check() -> DoctorCheck:
    missing = _missing_labels(
        (
            ("CLOUDFLARE_ACCOUNT_ID", settings.cloudflare_account_id),
            ("CLOUDFLARE_API_TOKEN", settings.cloudflare_api_token),
            ("S3_ENDPOINT_URL", settings.s3_endpoint_url),
            ("S3_ACCESS_KEY_ID", settings.s3_access_key_id),
            ("S3_SECRET_ACCESS_KEY", settings.s3_secret_access_key),
            (
                "S3_STOREFRONT_STAGING_BUCKET_NAME",
                settings.storefront_staging_bucket_name,
            ),
            ("S3_BLOG_BUCKET_NAME", settings.blog_media_bucket_name),
            ("BLOG_MEDIA_DOMAIN", settings.blog_media_domain),
        )
    )
    if missing:
        return DoctorCheck(
            name="storefront_media",
            status="FAIL",
            detail="Missing required configuration: " + ", ".join(missing),
        )
    if settings.storefront_staging_bucket_name == settings.blog_media_bucket_name:
        return DoctorCheck(
            name="storefront_media",
            status="FAIL",
            detail=(
                "S3_STOREFRONT_STAGING_BUCKET_NAME must be separate from the public "
                "sanitized S3_BLOG_BUCKET_NAME."
            ),
        )
    return DoctorCheck(
        name="storefront_media",
        status="PASS",
        detail=(
            "Private staging, sanitized public storage, CDN, and R2 credential "
            "presence are configured; provider privacy remains a live preflight."
        ),
    )


def _email_check() -> DoctorCheck:
    missing = _missing_labels(
        (
            ("RESEND_API_KEY", settings.resend_api_key),
            ("RESEND_FROM_EMAIL", settings.resend_from_email),
            ("RESEND_FROM_NAME", settings.resend_from_name),
        )
    )
    if missing:
        return DoctorCheck(
            name="storefront_email",
            status="FAIL",
            detail="Missing required configuration: " + ", ".join(missing),
        )
    if not _EMAIL_PATTERN.fullmatch(str(settings.resend_from_email).strip()):
        return DoctorCheck(
            name="storefront_email",
            status="FAIL",
            detail="RESEND_FROM_EMAIL is not a syntactically valid mailbox.",
        )
    return DoctorCheck(
        name="storefront_email",
        status="PASS",
        detail="Inquiry and DNS-instruction sender configuration is present.",
    )


def _runtime_revision_check() -> DoctorCheck:
    revision = str(settings.storefront_runtime_revision or "").strip()
    if not revision or revision.lower() in _REVISION_PLACEHOLDERS:
        return DoctorCheck(
            name="runtime_revision",
            status="FAIL",
            detail=(
                "STOREFRONT_RUNTIME_REVISION must identify the immutable deployed "
                "backend revision."
            ),
        )
    return DoctorCheck(
        name="runtime_revision",
        status="PASS",
        detail="An immutable storefront backend revision is configured.",
    )


def _probe_redis_reachability() -> str:
    """Return a non-secret Redis result code using a bounded read-only PING."""

    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        return "reachable" if client.ping() is True else "unexpected_response"
    except RedisAuthenticationError:
        return "authentication_failed"
    except (RedisConnectionError, RedisTimeoutError):
        return "unreachable"
    except Exception:
        return "probe_failed"
    finally:
        try:
            client.close()
        except Exception:
            pass


def _inquiry_shared_rate_limit_check() -> DoctorCheck:
    if not settings.redis_enabled:
        return DoctorCheck(
            name="storefront_inquiry_shared_rate_limit",
            status="FAIL",
            detail=(
                "REDIS_ENABLED must be true for production storefront inquiries. "
                "New inquiry submissions must remain unavailable rather than fall "
                "back to per-replica counters."
            ),
        )

    invalid = _missing_labels(
        (
            ("REDIS_HOST", settings.redis_host),
            ("REDIS_PASSWORD", settings.redis_password),
        )
    )
    if settings.redis_port < 1 or settings.redis_port > 65535:
        invalid.append("REDIS_PORT")
    if settings.redis_db < 0:
        invalid.append("REDIS_DB")
    if settings.redis_max_connections < 1:
        invalid.append("REDIS_MAX_CONNECTIONS")
    if invalid:
        return DoctorCheck(
            name="storefront_inquiry_shared_rate_limit",
            status="FAIL",
            detail="Invalid or missing required configuration: " + ", ".join(invalid),
        )

    probe = _probe_redis_reachability()
    if probe != "reachable":
        return DoctorCheck(
            name="storefront_inquiry_shared_rate_limit",
            status="FAIL",
            detail=(
                f"Shared Redis is unavailable ({probe}). New storefront inquiries "
                "must remain fail-closed; storefront pages and the platform slug "
                "remain available."
            ),
        )
    return DoctorCheck(
        name="storefront_inquiry_shared_rate_limit",
        status="PASS",
        detail="Shared Redis accepted a bounded PING for storefront inquiry limits.",
    )


def _inquiry_client_ip_check() -> DoctorCheck:
    cidrs = list(settings.trusted_proxy_cidrs or ())
    header = settings.trusted_proxy_client_ip_header
    if not cidrs or not header:
        return DoctorCheck(
            name="storefront_inquiry_client_ip",
            status="FAIL",
            detail=(
                "TRUSTED_PROXY_CIDRS and TRUSTED_PROXY_CLIENT_IP_HEADER must identify "
                "the production ingress and one header that ingress overwrites."
            ),
        )
    return DoctorCheck(
        name="storefront_inquiry_client_ip",
        status="PASS",
        detail=(
            f"Client IPs use ingress-overwritten {header} only from explicitly "
            "trusted proxy networks."
        ),
    )


def _custom_domain_check() -> DoctorCheck:
    readiness = config_validator.get_storefront_domain_readiness()
    if readiness["enabled"] is not True:
        return DoctorCheck(
            name="custom_domain_runtime",
            status="PASS",
            detail="Custom domains are disabled; platform storefront URLs are unaffected.",
        )
    if readiness["reason_code"] == "provider_mutations_disabled":
        return DoctorCheck(
            name="custom_domain_runtime",
            status="PASS",
            detail=(
                "New provider mutations are disabled; observe/manual setup remains "
                "fail-closed."
            ),
        )
    if readiness["ready"] is not True:
        reason = str(readiness.get("reason_code") or "configuration_unavailable")
        missing = [str(item) for item in readiness.get("missing", [])]
        suffix = f" Missing: {', '.join(missing)}." if missing else ""
        return DoctorCheck(
            name="custom_domain_runtime",
            status="FAIL",
            detail=f"Custom-domain provider readiness is {reason}.{suffix}",
        )
    return DoctorCheck(
        name="custom_domain_runtime",
        status="PASS",
        detail="New custom-domain mutations satisfy the local rollout fence.",
    )


def _domain_connect_template_check() -> DoctorCheck:
    try:
        validate_template()
    except TemplateValidationError as exc:
        return DoctorCheck(
            name="domain_connect_template",
            status="FAIL",
            detail=str(exc),
        )
    except Exception as exc:  # never surface arbitrary exception text
        return DoctorCheck(
            name="domain_connect_template",
            status="FAIL",
            detail=f"Local template validation failed ({exc.__class__.__name__}).",
        )
    return DoctorCheck(
        name="domain_connect_template",
        status="PASS",
        detail="The checked-in candidate matches the local fixed-record contract.",
    )


def build_report() -> dict[str, object]:
    checks = [
        _configuration_contract_check(),
        _media_check(),
        _email_check(),
        _runtime_revision_check(),
        _inquiry_shared_rate_limit_check(),
        _inquiry_client_ip_check(),
        _custom_domain_check(),
        _domain_connect_template_check(),
        DoctorCheck(
            name="external_provider_acceptance",
            status="BLOCKED",
            detail=(
                "Not tested by this read-only command; retain separate Cloudflare, "
                "Domain Connect, independent-DNS, and browser receipts."
            ),
        ),
    ]
    failed = [check.name for check in checks if check.status == "FAIL"]
    return {
        "schema_version": 2,
        "command_scope": "local_configuration_and_redis_reachability",
        "ok": not failed,
        "checks": [asdict(check) for check in checks],
        "failed_checks": failed,
    }


def _print_human(report: dict[str, object]) -> None:
    print("storefront configuration doctor")
    print("-" * 40)
    for check in report["checks"]:
        assert isinstance(check, dict)
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    print("-" * 40)
    print("local configuration: " + ("PASS" if report["ok"] else "FAIL"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable report containing no credential values.",
    )
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
