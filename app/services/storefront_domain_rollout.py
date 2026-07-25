"""Exact allowlist gate for new storefront custom-domain provider mutations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import idna

from app.core.settings import settings


def _normalize_hostname(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().rstrip(".")
    if not candidate or "*" in candidate:
        return None
    try:
        return (
            idna.encode(
                candidate,
                uts46=True,
                std3_rules=True,
                transitional=False,
            )
            .decode("ascii")
            .lower()
        )
    except idna.IDNAError:
        return None


def _normalize_owner_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    return candidate or None


@dataclass(frozen=True)
class StorefrontDomainRolloutPolicy:
    """Fail-closed policy for provisioning and automatic DNS authorization.

    The allowlists use exact normalized values only; suffixes and wildcards are
    deliberately unsupported so a pilot cannot accidentally become a broad
    customer-DNS mutation grant.
    """

    mode: str = "allowlist"
    hostnames: frozenset[str] = frozenset()
    owner_ids: frozenset[str] = frozenset()

    @classmethod
    def build(
        cls,
        *,
        mode: object = "allowlist",
        hostnames: Iterable[object] = (),
        owner_ids: Iterable[object] = (),
    ) -> StorefrontDomainRolloutPolicy:
        normalized_mode = str(mode or "allowlist").strip().lower()
        if normalized_mode not in {"allowlist", "general"}:
            normalized_mode = "allowlist"
        return cls(
            mode=normalized_mode,
            hostnames=frozenset(
                hostname
                for value in hostnames
                if (hostname := _normalize_hostname(value)) is not None
            ),
            owner_ids=frozenset(
                owner_id
                for value in owner_ids
                if (owner_id := _normalize_owner_id(value)) is not None
            ),
        )

    @classmethod
    def from_settings(cls) -> StorefrontDomainRolloutPolicy:
        return cls.build(
            mode=getattr(
                settings, "storefront_custom_domain_rollout_mode", "allowlist"
            ),
            hostnames=getattr(settings, "storefront_custom_domain_pilot_hostnames", ()),
            owner_ids=getattr(settings, "storefront_custom_domain_pilot_owner_ids", ()),
        )

    def allows(self, owner_id: str, hostname: str) -> bool:
        if self.mode == "general":
            return True
        normalized_owner = _normalize_owner_id(owner_id)
        normalized_hostname = _normalize_hostname(hostname)
        return bool(
            (normalized_owner and normalized_owner in self.owner_ids)
            or (normalized_hostname and normalized_hostname in self.hostnames)
        )
