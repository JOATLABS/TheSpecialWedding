"""Fail-closed target and browser-evidence checks for storefront testbed runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError
from pymongo.errors import ConfigurationError, InvalidURI
from pymongo.uri_parser import parse_uri


_DATABASE_LABELS = frozenset({"test", "testing", "e2e", "storefront", "staging"})
_CHECKPOINT_SLUGS = {
    "CHECKPOINT TIER_BOUNDARY": "tier-boundary",
    "CHECKPOINT DRAFT_PREVIEW": "draft-preview",
    "CHECKPOINT PUBLICATION": "publication",
    "CHECKPOINT INQUIRY": "inquiry",
    "CHECKPOINT PROVIDER_PATHS": "provider-paths",
    "CHECKPOINT PROVIDER_PATHS CONNECTED": "provider-paths-connected",
    "CHECKPOINT PROVIDER_PATHS DISCONNECTED": "provider-paths-disconnected",
}
PROVIDER_DISABLED_ENVIRONMENT_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "BLOG_MEDIA_DOMAIN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_SAAS_API_TOKEN",
    "CLOUDFLARE_ZONE_ID",
    "DOMAIN_CONNECT_PRIVATE_KEY",
    "RESEND_API_KEY",
    "S3_ACCESS_KEY_ID",
    "S3_BLOG_BUCKET_NAME",
    "S3_ENDPOINT_URL",
    "S3_SECRET_ACCESS_KEY",
    "S3_STOREFRONT_STAGING_BUCKET_NAME",
    "STOREFRONT_CNAME_TARGET",
    "STOREFRONT_FALLBACK_ORIGIN",
)

# The deterministic domain-provider harness may opt into real object storage
# without gaining any Cloudflare-for-SaaS, DNS, Domain Connect, or email
# capability.  Keep this list deliberately narrower than
# ``PROVIDER_DISABLED_ENVIRONMENT_KEYS``: these values can only upload to the
# two exact R2 buckets admitted by the live-media safety contract below.
STOREFRONT_MEDIA_LIVE_ENVIRONMENT_KEYS = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "BLOG_MEDIA_DOMAIN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "S3_ACCESS_KEY_ID",
        "S3_BLOG_BUCKET_NAME",
        "S3_ENDPOINT_URL",
        "S3_SECRET_ACCESS_KEY",
        "S3_STOREFRONT_STAGING_BUCKET_NAME",
    }
)


@dataclass(frozen=True)
class SafeStorefrontTarget:
    backend_origin: str
    frontend_origin: str
    mongo_hosts: tuple[str, ...]
    mongo_db: str
    is_loopback: bool = True


@dataclass(frozen=True)
class SafeStorefrontProviderHarness:
    """Validated, non-production coordinates for the fake provider process."""

    run_id: str
    control_token: str
    customer_zone: str
    backend_origin: str
    frontend_origin: str
    browser_origin: str | None
    frontend_ca_certificate: str | None
    mongo_hosts: tuple[str, ...]
    mongo_db: str
    media_mode: str = "disabled"
    media_staging_bucket: str | None = None
    media_public_bucket: str | None = None
    media_public_domain: str | None = None


def _exact_values(value: str | None) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def assert_live_storefront_media_environment(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Authorize only two exact R2 buckets for a loopback browser run.

    This contract intentionally does not accept the Cloudflare for SaaS token,
    zone ID, Domain Connect key, CNAME target, or email credentials.  The
    account API token is retained only because the media service uses it for
    read-only staging privacy/lifecycle/CORS checks.
    """

    required = (
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "S3_ENDPOINT_URL",
        "S3_STOREFRONT_STAGING_BUCKET_NAME",
        "S3_BLOG_BUCKET_NAME",
        "BLOG_MEDIA_DOMAIN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
    )
    values = {name: str(environment.get(name, "")).strip() for name in required}
    missing = sorted(name for name, value in values.items() if not value)
    if missing:
        raise RuntimeError(
            f"Live storefront media proof is missing required configuration: {missing}"
        )

    for flag in (
        "STOREFRONT_CUSTOM_DOMAINS_ENABLED",
        "STOREFRONT_DOMAIN_CONNECT_AUTHORIZATION_ENABLED",
        "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED",
        "STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED",
    ):
        if str(environment.get(flag, "")).strip().lower() != "false":
            raise RuntimeError(
                f"Live media proof requires {flag}=false so customer-domain state cannot mutate"
            )

    account_id = values["CLOUDFLARE_ACCOUNT_ID"].lower()
    if re.fullmatch(r"[0-9a-f]{32}", account_id) is None:
        raise RuntimeError("Live media proof requires an exact Cloudflare account ID")
    if account_id not in _exact_values(
        environment.get("TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ACCOUNT_IDS")
    ):
        raise RuntimeError("Live media Cloudflare account is not in its exact allowlist")

    endpoint = urlparse(values["S3_ENDPOINT_URL"])
    endpoint_host = (endpoint.hostname or "").lower()
    expected_endpoint_host = f"{account_id}.r2.cloudflarestorage.com"
    if (
        endpoint.scheme != "https"
        or endpoint_host != expected_endpoint_host
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.path not in {"", "/"}
        or endpoint.params
        or endpoint.query
        or endpoint.fragment
    ):
        raise RuntimeError(
            "Live media S3 endpoint must be the credential-free HTTPS R2 endpoint "
            "for the exact allowlisted account"
        )

    staging_bucket = values["S3_STOREFRONT_STAGING_BUCKET_NAME"]
    public_bucket = values["S3_BLOG_BUCKET_NAME"]
    if staging_bucket == public_bucket:
        raise RuntimeError("Live media staging and public buckets must be distinct")
    if staging_bucket not in _exact_values(
        environment.get("TESTBED_STOREFRONT_ALLOWED_STAGING_BUCKETS")
    ):
        raise RuntimeError("Live media staging bucket is not in its exact allowlist")
    if public_bucket not in _exact_values(
        environment.get("TESTBED_STOREFRONT_ALLOWED_PUBLIC_BUCKETS")
    ):
        raise RuntimeError("Live media public bucket is not in its exact allowlist")

    public_domain = values["BLOG_MEDIA_DOMAIN"].lower().rstrip(".")
    if public_domain not in parse_exact_hostname_allowlist(
        environment.get("TESTBED_STOREFRONT_ALLOWED_PUBLIC_MEDIA_DOMAINS")
    ):
        raise RuntimeError("Live media public domain is not in its exact allowlist")

    return {
        "account_id": account_id,
        "staging_bucket": staging_bucket,
        "public_bucket": public_bucket,
        "public_domain": public_domain,
        "upload_origin": f"https://{endpoint_host}",
    }


def _origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("Storefront testbed URLs must be absolute HTTP(S) origins")
    default_port = 443 if parsed.scheme == "https" else 80
    port = parsed.port or default_port
    authority = parsed.hostname.lower()
    if port != default_port:
        authority = f"{authority}:{port}"
    return f"{parsed.scheme}://{authority}"


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_labelled_database(database: str) -> bool:
    tokens = {
        token for token in re.split(r"[^a-z0-9]+", database.strip().lower()) if token
    }
    return bool(tokens & _DATABASE_LABELS)


def parse_exact_hostname_allowlist(value: str | None) -> frozenset[str]:
    """Parse JSON-array or comma-separated hostnames without wildcard semantics."""

    raw = (value or "").strip()
    if not raw:
        return frozenset()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Custom-domain allowlist is not valid JSON") from exc
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise RuntimeError("Custom-domain allowlist JSON must contain strings")
        candidates = parsed
    else:
        candidates = raw.split(",")

    normalized: set[str] = set()
    for candidate in candidates:
        hostname = candidate.strip().lower()
        if (
            not hostname
            or "://" in hostname
            or "/" in hostname
            or "*" in hostname
            or "@" in hostname
            or hostname.startswith(".")
            or hostname.endswith(".")
            or "." not in hostname
        ):
            raise RuntimeError(
                f"Custom-domain allowlist entry must be an exact hostname: {candidate!r}"
            )
        normalized.add(hostname)
    return frozenset(normalized)


def assert_safe_storefront_target(
    *,
    backend_url: str,
    frontend_url: str,
    mongo_uri: str | None,
    mongo_db: str,
) -> SafeStorefrontTarget:
    """Allow only explicit, labelled loopback services before any mutation."""

    if not mongo_uri:
        raise RuntimeError("MONGO_URI or MONGODB_URI is required")
    try:
        mongo_hosts = tuple(host for host, _port in parse_uri(mongo_uri)["nodelist"])
    except (ConfigurationError, InvalidURI, ValueError) as exc:
        raise RuntimeError("Storefront testbed could not validate MONGO_URI") from exc

    backend_origin = _origin(backend_url)
    frontend_origin = _origin(frontend_url)
    backend_host = urlparse(backend_origin).hostname or ""
    frontend_host = urlparse(frontend_origin).hostname or ""
    safe = (
        _is_labelled_database(mongo_db)
        and _is_loopback(backend_host)
        and _is_loopback(frontend_host)
        and bool(mongo_hosts)
        and all(_is_loopback(host) for host in mongo_hosts)
    )
    if not safe:
        raise RuntimeError(
            "Storefront testbed requires an isolated loopback target. Backend, "
            "frontend, and Mongo must use loopback hosts, and MONGO_DB must contain a complete "
            "test, testing, e2e, storefront, or staging token separated by '-' or '_'."
        )
    return SafeStorefrontTarget(
        backend_origin=backend_origin,
        frontend_origin=frontend_origin,
        mongo_hosts=mongo_hosts,
        mongo_db=mongo_db,
    )


def assert_storefront_provider_harness_environment(
    environment: Mapping[str, str],
) -> SafeStorefrontProviderHarness:
    """Fail closed unless an unattended provider harness is fully isolated.

    The deterministic provider is deliberately stricter than the regular
    storefront lifecycle verifier: it requires an explicit non-interactive
    opt-in, an unguessable control credential, a reserved test-only customer
    zone, and the existing loopback/labelled-database safety contract.
    """

    if environment.get("TESTBED_NON_INTERACTIVE", "").strip() != "1":
        raise RuntimeError(
            "Storefront provider harness requires TESTBED_NON_INTERACTIVE=1"
        )

    media_mode = str(
        environment.get("STOREFRONT_PROVIDER_HARNESS_MEDIA_MODE", "disabled")
    ).strip().lower()
    if media_mode not in {"disabled", "live"}:
        raise RuntimeError(
            "STOREFRONT_PROVIDER_HARNESS_MEDIA_MODE must be disabled or live"
        )
    allowed_provider_keys = (
        STOREFRONT_MEDIA_LIVE_ENVIRONMENT_KEYS if media_mode == "live" else frozenset()
    )
    configured_provider_values = sorted(
        name
        for name in PROVIDER_DISABLED_ENVIRONMENT_KEYS
        if name not in allowed_provider_keys
        and str(environment.get(name, "")).strip()
    )
    if configured_provider_values:
        raise RuntimeError(
            "Deterministic storefront provider proof requires every external-provider "
            "credential and target to be blank: "
            f"{configured_provider_values}"
        )

    run_id = environment.get("STOREFRONT_PROVIDER_HARNESS_RUN_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{11,79}", run_id):
        raise RuntimeError(
            "STOREFRONT_PROVIDER_HARNESS_RUN_ID must be a 12-80 character run nonce"
        )

    control_token = environment.get("STOREFRONT_PROVIDER_HARNESS_TOKEN", "").strip()
    if (
        len(control_token) < 43
        or len(control_token) > 256
        or len(set(control_token)) < 4
        or control_token == run_id
        or any(marker in control_token.lower() for marker in ("change-me", "example"))
    ):
        raise RuntimeError(
            "STOREFRONT_PROVIDER_HARNESS_TOKEN must be an unguessable run token"
        )

    customer_zone = (
        environment.get("STOREFRONT_PROVIDER_HARNESS_CUSTOMER_ZONE", "")
        .strip()
        .lower()
        .rstrip(".")
    )
    if not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",
        customer_zone,
    ) or not customer_zone.endswith((".test", ".invalid")):
        raise RuntimeError(
            "Storefront provider harness customer zone must end in .test or .invalid"
        )

    backend_url = environment.get("BACKEND_URL", "").strip()
    frontend_url = environment.get("FRONTEND_URL", "").strip()
    mongo_uri = (
        environment.get("MONGO_URI") or environment.get("MONGODB_URI") or ""
    ).strip()
    mongo_db = (
        environment.get("MONGO_DB") or environment.get("MONGO_NAME") or ""
    ).strip()
    target = assert_safe_storefront_target(
        backend_url=backend_url,
        frontend_url=frontend_url,
        mongo_uri=mongo_uri,
        mongo_db=mongo_db,
    )
    browser_origin_raw = environment.get(
        "STOREFRONT_PROVIDER_HARNESS_BROWSER_ORIGIN", ""
    ).strip()
    browser_origin: str | None = None
    if browser_origin_raw:
        parsed_browser = urlparse(browser_origin_raw)
        browser_host = parsed_browser.hostname or ""
        try:
            parsed_browser.port
        except ValueError as exc:
            raise RuntimeError(
                "Visible storefront browser origin has an invalid port"
            ) from exc
        if (
            parsed_browser.scheme not in {"http", "https"}
            or not _is_loopback(browser_host)
            or parsed_browser.username is not None
            or parsed_browser.password is not None
            or parsed_browser.path not in {"", "/"}
            or parsed_browser.params
            or parsed_browser.query
            or parsed_browser.fragment
        ):
            raise RuntimeError(
                "Visible storefront browser origin must be a credential-free "
                "loopback HTTP(S) origin without a path, query, or fragment"
            )
        browser_origin = _origin(browser_origin_raw)
    frontend_ca_certificate = (
        environment.get("STOREFRONT_PROVIDER_HARNESS_FRONTEND_CA_CERT", "").strip()
        or None
    )
    media_fence = (
        assert_live_storefront_media_environment(environment)
        if media_mode == "live"
        else {}
    )
    return SafeStorefrontProviderHarness(
        run_id=run_id,
        control_token=control_token,
        customer_zone=customer_zone,
        backend_origin=target.backend_origin,
        frontend_origin=target.frontend_origin,
        browser_origin=browser_origin,
        frontend_ca_certificate=frontend_ca_certificate,
        mongo_hosts=target.mongo_hosts,
        mongo_db=target.mongo_db,
        media_mode=media_mode,
        media_staging_bucket=media_fence.get("staging_bucket"),
        media_public_bucket=media_fence.get("public_bucket"),
        media_public_domain=media_fence.get("public_domain"),
    )


def normalize_disabled_provider_settings(settings: Any) -> Any:
    """Normalize the harness's explicit blank S3 endpoint before app imports.

    The deterministic child must keep ``S3_ENDPOINT_URL`` present and blank so
    Pydantic does not reload a real value from the repository ``.env`` file.
    Botocore rejects that blank string while import-time route singletons are
    constructed, even though storage credentials and buckets are disabled.
    Converting only that already-fenced blank value to ``None`` preserves the
    provider-disable boundary and gives Botocore its normal unconfigured state.
    """

    endpoint = getattr(settings, "s3_endpoint_url", None)
    if isinstance(endpoint, str) and not endpoint.strip():
        settings.s3_endpoint_url = None
    return settings


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_aware_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise AssertionError(f"{label} must be an ISO-8601 timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AssertionError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_url_origins(urls: object, allowed_origins: Iterable[str]) -> list[str]:
    if not isinstance(urls, list) or not urls:
        raise AssertionError("Browser evidence must include at least one URL")
    normalized_allowed = {_origin(origin) for origin in allowed_origins}
    normalized_urls: list[str] = []
    for value in urls:
        if not isinstance(value, str) or not value:
            raise AssertionError("Browser evidence URLs must be non-empty strings")
        if _origin(value) not in normalized_allowed:
            raise AssertionError(
                f"Browser evidence URL used an unapproved origin: {value}"
            )
        normalized_urls.append(value)
    return normalized_urls


def validate_browser_checkpoint_evidence(
    *,
    artifact_dir: Path,
    marker: str,
    required_assertions: Iterable[str],
    run_started_at: datetime,
    allowed_origins: Iterable[str],
) -> dict:
    """Validate current screenshot, DOM, console, URL, and assertion evidence."""

    slug = _CHECKPOINT_SLUGS.get(marker)
    if not slug:
        raise ValueError(f"Unknown storefront browser checkpoint: {marker}")
    browser_dir = artifact_dir / "browser"
    evidence_path = browser_dir / f"{slug}.json"
    screenshot_path = browser_dir / f"{slug}.png"
    dom_path = browser_dir / f"{slug}.dom.txt"
    for path in (evidence_path, screenshot_path, dom_path):
        if not path.is_file():
            raise RuntimeError(f"Missing browser checkpoint evidence: {path}")

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Unreadable browser checkpoint evidence: {evidence_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise AssertionError("Browser checkpoint evidence must be a JSON object")
    if payload.get("checkpoint") != marker or payload.get("result") != "passed":
        raise AssertionError("Browser checkpoint marker/result did not attest a pass")

    started = run_started_at.astimezone(timezone.utc)
    captured = _parse_aware_timestamp(payload.get("captured_at"), "captured_at")
    if captured < started:
        raise AssertionError("Browser checkpoint evidence predates this verifier run")
    for path in (evidence_path, screenshot_path, dom_path):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < started:
            raise AssertionError(
                f"Browser checkpoint artifact predates this run: {path}"
            )

    assertions = payload.get("assertions")
    if not isinstance(assertions, dict):
        raise AssertionError("Browser checkpoint assertions must be an object")
    missing_or_failed = [
        name for name in required_assertions if assertions.get(name) is not True
    ]
    if missing_or_failed:
        raise AssertionError(
            f"Browser checkpoint assertions are missing or failed: {missing_or_failed}"
        )

    console = payload.get("console")
    if not isinstance(console, dict):
        raise AssertionError("Browser checkpoint console evidence must be an object")
    if console.get("errors") != [] or console.get("warnings") != []:
        raise AssertionError("Browser checkpoint console contains warnings or errors")

    if payload.get("screenshot_sha256") != _sha256(screenshot_path):
        raise AssertionError("Browser screenshot hash does not match its evidence")
    if payload.get("dom_snapshot_sha256") != _sha256(dom_path):
        raise AssertionError("Browser DOM hash does not match its evidence")
    try:
        with Image.open(screenshot_path) as screenshot:
            screenshot.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise AssertionError("Browser screenshot is not a valid image") from exc
    dom_text = dom_path.read_text(encoding="utf-8")
    if len(dom_text.strip()) < 40:
        raise AssertionError("Browser DOM evidence is empty or implausibly small")

    urls = _validate_url_origins(payload.get("urls"), allowed_origins)
    return {
        "status": "confirmed",
        "captured_at": captured.isoformat(),
        "urls": urls,
        "assertions": {name: True for name in required_assertions},
        "console": {"errors": [], "warnings": []},
        "screenshot": {
            "path": str(screenshot_path),
            "sha256": _sha256(screenshot_path),
        },
        "dom_snapshot": {"path": str(dom_path), "sha256": _sha256(dom_path)},
        "evidence_json": {"path": str(evidence_path), "sha256": _sha256(evidence_path)},
    }
