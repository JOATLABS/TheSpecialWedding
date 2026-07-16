#!/usr/bin/env python3
"""Deterministically validate the checked-in storefront Domain Connect template.

This local contract check is intentionally narrower than the official Domain
Connect linter and Cloudflare onboarding. Passing it never means the template
has been accepted by either external party.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = (
    REPO_ROOT
    / "domain-connect"
    / "templates"
    / "thespecialwedding.com.storefront-subdomain.json"
)
EXPECTED_PROVIDER_ID = "thespecialwedding.com"
EXPECTED_SERVICE_ID = "storefront-subdomain"
EXPECTED_CNAME_TARGET = "domains.thespecialwedding.com"
EXPECTED_PUBLIC_KEY_DOMAIN = "domainconnect.thespecialwedding.com"
VARIABLE_PATTERN = re.compile(r"%([A-Za-z][A-Za-z0-9]*)%")


class TemplateValidationError(ValueError):
    """The repository template no longer matches the production contract."""


def _variables(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(VARIABLE_PATTERN.findall(value))
    if isinstance(value, list):
        return set().union(*(_variables(item) for item in value), set())
    if isinstance(value, dict):
        return set().union(*(_variables(item) for item in value.values()), set())
    return set()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TemplateValidationError(message)


def validate_template(path: Path = TEMPLATE_PATH) -> dict[str, Any]:
    _require(path.name == path.name.lower(), "template filename must be lowercase")
    _require(
        path.name == f"{EXPECTED_PROVIDER_ID}.{EXPECTED_SERVICE_ID}.json",
        "template filename must be <providerId>.<serviceId>.json",
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateValidationError("template must be readable JSON") from exc
    _require(isinstance(payload, dict), "template root must be an object")

    _require(payload.get("providerId") == EXPECTED_PROVIDER_ID, "providerId drift")
    _require(payload.get("serviceId") == EXPECTED_SERVICE_ID, "serviceId drift")
    _require(payload.get("providerName") == "The Special Wedding", "providerName drift")
    _require(
        payload.get("version") == 1, "template version must be explicitly reviewed"
    )
    _require(payload.get("syncBlock") is False, "Cloudflare requires synchronous flow")
    _require(
        payload.get("syncPubKeyDomain") == EXPECTED_PUBLIC_KEY_DOMAIN,
        "sync public-key domain drift",
    )
    _require(
        payload.get("syncRedirectDomain") == EXPECTED_PUBLIC_KEY_DOMAIN,
        "redirect domain drift",
    )
    _require(payload.get("hostRequired") is True, "apex application must be rejected")
    _require(
        "warnPhishing" not in payload, "signed templates must not use warnPhishing"
    )
    _require(
        _variables(payload) == {"verificationToken"}, "unexpected template variable"
    )

    records = payload.get("records")
    _require(
        isinstance(records, list) and len(records) == 2, "exactly two records required"
    )
    by_type = {
        record.get("type"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("type"), str)
    }
    _require(set(by_type) == {"TXT", "CNAME"}, "only TXT and CNAME are allowed")

    ownership = by_type["TXT"]
    _require(ownership.get("host") == "_tsw-storefront", "ownership host drift")
    _require(
        ownership.get("data") == "tsw-verification=%verificationToken%",
        "ownership token must retain its fixed prefix",
    )
    _require(
        ownership.get("txtConflictMatchingMode") == "Prefix"
        and ownership.get("txtConflictMatchingPrefix") == "tsw-verification=",
        "ownership TXT conflict matching must be prefix-scoped",
    )

    routing = by_type["CNAME"]
    _require(routing.get("host") == "@", "host parameter must select the subdomain")
    _require(routing.get("pointsTo") == EXPECTED_CNAME_TARGET, "CNAME target drift")
    for record in records:
        _require(record.get("ttl") == 300, "storefront template TTL drift")
        _require(record.get("groupId") == "storefront", "record group drift")

    return payload


def main() -> int:
    validate_template()
    print(
        "Storefront Domain Connect template passed the local deterministic contract. "
        "Official linter, repository acceptance, and Cloudflare onboarding remain external gates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
