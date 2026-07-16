"""Publication-independent, owner-bound HTTPS proof for storefront domains.

The reconciliation worker must prove that the exact customer hostname reaches
this application before it enables custom-host routing.  A generic successful
page is not evidence: the challenge and response are both bound to the domain
row identity and lifecycle revision with a server-only derived HMAC key.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Any, Callable, Mapping

from fastapi import HTTPException, status

from app.core.database import mongo
from app.core.settings import settings
from app.services.storefront_domain_service import normalize_custom_hostname
from app.utils.planner_ownership import normalize_planner_id


PROBE_PATH = "/.well-known/tsw-storefront-verification"
PROBE_HEADER = "x-tsw-storefront-probe"
PROBE_HOST_HEADER = "x-tsw-storefront-host"
MAX_PROBE_RESPONSE_BYTES = 8 * 1024

_PROBE_VERSION = "1"
_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SIGNATURE_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ATTESTATION_KEYS = frozenset(
    {"version", "hostname", "revision", "nonce", "domain_binding", "proof"}
)


def _derived_key(secret_key: str) -> bytes:
    if not isinstance(secret_key, str) or len(secret_key) < 32:
        raise ValueError("A strong application secret is required for HTTPS probes")
    return hmac.new(
        secret_key.encode("utf-8"),
        b"weddingwebapp/storefront-domain-https-probe/v1",
        hashlib.sha256,
    ).digest()


def _identity(record: Mapping[str, Any]) -> tuple[str, str, str, int]:
    domain_id = str(record.get("_id") or "").strip()
    owner_id = normalize_planner_id(record.get("planner_id"))
    hostname = normalize_custom_hostname(record.get("hostname"), platform_domains=())
    revision = record.get("revision")
    if (
        not domain_id
        or not owner_id
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 0
    ):
        raise ValueError("Storefront domain probe identity is incomplete")
    return domain_id, owner_id, hostname, revision


def _identity_payload(record: Mapping[str, Any]) -> bytes:
    domain_id, owner_id, hostname, revision = _identity(record)
    return f"{domain_id}\n{owner_id}\n{hostname}\n{revision}".encode("utf-8")


def _signature(key: bytes, label: bytes, payload: bytes) -> str:
    return hmac.new(key, label + b"\n" + payload, hashlib.sha256).hexdigest()


def _parse_challenge(challenge: str) -> tuple[str, str]:
    if not isinstance(challenge, str) or len(challenge) > 256:
        raise ValueError("Invalid storefront HTTPS probe challenge")
    parts = challenge.split(".")
    if (
        len(parts) != 3
        or parts[0] != f"v{_PROBE_VERSION}"
        or not _NONCE_PATTERN.fullmatch(parts[1])
        or not _SIGNATURE_PATTERN.fullmatch(parts[2])
    ):
        raise ValueError("Invalid storefront HTTPS probe challenge")
    return parts[1], parts[2]


def build_probe_challenge(
    record: Mapping[str, Any],
    secret_key: str,
    *,
    nonce: str | None = None,
) -> str:
    challenge_nonce = nonce or secrets.token_urlsafe(32)
    if not _NONCE_PATTERN.fullmatch(challenge_nonce):
        raise ValueError("Invalid storefront HTTPS probe nonce")
    key = _derived_key(secret_key)
    payload = _identity_payload(record) + b"\n" + challenge_nonce.encode("ascii")
    proof = _signature(key, b"request", payload)
    return f"v{_PROBE_VERSION}.{challenge_nonce}.{proof}"


def _validated_nonce(record: Mapping[str, Any], challenge: str, secret_key: str) -> str:
    nonce, supplied = _parse_challenge(challenge)
    key = _derived_key(secret_key)
    payload = _identity_payload(record) + b"\n" + nonce.encode("ascii")
    expected = _signature(key, b"request", payload)
    if not hmac.compare_digest(supplied, expected):
        raise ValueError("Storefront HTTPS probe challenge does not match")
    return nonce


def build_probe_attestation(
    record: Mapping[str, Any], challenge: str, secret_key: str
) -> dict[str, Any]:
    domain_id, _owner_id, hostname, revision = _identity(record)
    nonce = _validated_nonce(record, challenge, secret_key)
    key = _derived_key(secret_key)
    identity = _identity_payload(record)
    domain_binding = _signature(key, b"binding", identity)
    proof_payload = (
        identity
        + b"\n"
        + nonce.encode("ascii")
        + b"\n"
        + domain_binding.encode("ascii")
    )
    # Keep the database identifier inside the keyed binding rather than
    # exposing it in this unauthenticated, challenge-only response.
    _ = domain_id
    return {
        "version": _PROBE_VERSION,
        "hostname": hostname,
        "revision": revision,
        "nonce": nonce,
        "domain_binding": domain_binding,
        "proof": _signature(key, b"response", proof_payload),
    }


def verify_probe_attestation(
    record: Mapping[str, Any],
    challenge: str,
    payload: object,
    secret_key: str,
) -> bool:
    if not isinstance(payload, dict) or set(payload) != _ATTESTATION_KEYS:
        return False
    try:
        expected = build_probe_attestation(record, challenge, secret_key)
    except (TypeError, ValueError):
        return False
    for key, expected_value in expected.items():
        observed = payload.get(key)
        if isinstance(expected_value, str):
            if not isinstance(observed, str) or not hmac.compare_digest(
                observed, expected_value
            ):
                return False
        elif isinstance(observed, bool) or observed != expected_value:
            return False
    return True


class StorefrontDomainHttpsProbeService:
    """Return a signed identity receipt without reading storefront content."""

    def __init__(
        self,
        *,
        mongo_client: Any | None = None,
        secret_key: str | None = None,
        platform_domains: tuple[str, ...] | list[str] | None = None,
        challenge_verifier: Callable[[Mapping[str, Any], str, str], str] | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._secret_key = settings.secret_key if secret_key is None else secret_key
        self._platform_domains = tuple(
            settings.storefront_platform_domains
            if platform_domains is None
            else platform_domains
        )
        self._challenge_verifier = challenge_verifier or _validated_nonce

    @staticmethod
    def _not_found() -> None:
        # Deliberately identical for an unknown hostname, stale revision,
        # disconnect, and invalid proof so this endpoint cannot enumerate rows.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    async def attest(self, raw_hostname: str, challenge: str) -> dict[str, Any]:
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except (TypeError, ValueError):
            self._not_found()

        record = await self._mongo.db["storefront_domains"].find_one(
            {
                "hostname": hostname,
                "ownership_status": "verified",
                "deletion_status": None,
            }
        )
        if not record:
            self._not_found()
        try:
            self._challenge_verifier(record, challenge, self._secret_key)
            return build_probe_attestation(record, challenge, self._secret_key)
        except (TypeError, ValueError):
            self._not_found()


storefront_domain_https_probe_service = StorefrontDomainHttpsProbeService()
