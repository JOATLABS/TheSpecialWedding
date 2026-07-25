"""Independent DNS observations for storefront-domain ownership workflows."""

from __future__ import annotations

import ipaddress
from typing import Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver


class StorefrontDnsResolutionError(RuntimeError):
    """A retryable failure to obtain an authoritative DNS observation."""


class StorefrontDnsResolver(Protocol):
    async def query(self, name: str, record_type: str) -> list[str]: ...

    async def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]: ...


class DnspythonStorefrontDnsResolver:
    """Small injectable resolver that returns normalized textual record values."""

    def __init__(self, *, lifetime_seconds: float = 5.0) -> None:
        self._lifetime_seconds = lifetime_seconds

    @staticmethod
    def _text(record_type: str, value: object) -> str:
        if record_type == "TXT" and hasattr(value, "strings"):
            chunks = getattr(value, "strings", ())
            return b"".join(chunks).decode("utf-8", errors="strict")
        text = str(value.to_text())
        if record_type in {"NS", "CNAME"}:
            return text.rstrip(".").lower()
        return text

    async def query(self, name: str, record_type: str) -> list[str]:
        normalized_name = name.strip().lower().rstrip(".")
        normalized_type = record_type.strip().upper()
        try:
            answer = await dns.asyncresolver.resolve(
                normalized_name,
                normalized_type,
                lifetime=self._lifetime_seconds,
                search=False,
            )
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except (
            dns.resolver.NoNameservers,
            dns.resolver.LifetimeTimeout,
            dns.exception.Timeout,
        ) as exc:
            raise StorefrontDnsResolutionError(
                f"DNS {normalized_type} lookup failed for {normalized_name}"
            ) from exc

        values = {self._text(normalized_type, value) for value in answer}
        return sorted(value for value in values if value)

    async def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]:
        """Query the delegated servers directly and fail closed on disagreement.

        Recursive DNS is used only to bootstrap the public IP addresses of the
        already-discovered NS hostnames. Customer-controlled delegation is never
        allowed to turn this service into a private-network DNS client.
        """

        normalized_name = name.strip().lower().rstrip(".")
        normalized_type = record_type.strip().upper()
        normalized_nameservers = sorted(
            {
                value.strip().lower().rstrip(".")
                for value in nameservers
                if isinstance(value, str) and value.strip()
            }
        )[:8]
        if not normalized_nameservers:
            raise StorefrontDnsResolutionError(
                f"No authoritative nameservers are available for {normalized_name}"
            )

        addresses: list[str] = []
        for nameserver in normalized_nameservers:
            for address_type in ("A", "AAAA"):
                try:
                    candidates = await self.query(nameserver, address_type)
                except StorefrontDnsResolutionError:
                    continue
                for candidate in candidates:
                    try:
                        parsed = ipaddress.ip_address(candidate)
                    except ValueError:
                        continue
                    if parsed.is_global and parsed.compressed not in addresses:
                        addresses.append(parsed.compressed)
                    if len(addresses) >= 16:
                        break
                if len(addresses) >= 16:
                    break
            if len(addresses) >= 16:
                break
        if not addresses:
            raise StorefrontDnsResolutionError(
                f"Authoritative nameserver addresses are unavailable for {normalized_name}"
            )

        observations: list[set[str]] = []
        for address in addresses:
            resolver = dns.asyncresolver.Resolver(configure=False)
            resolver.nameservers = [address]
            resolver.lifetime = self._lifetime_seconds
            try:
                answer = await resolver.resolve(
                    normalized_name,
                    normalized_type,
                    lifetime=self._lifetime_seconds,
                    search=False,
                )
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                observations.append(set())
                continue
            except (
                dns.resolver.NoNameservers,
                dns.resolver.LifetimeTimeout,
                dns.exception.Timeout,
            ):
                continue
            observations.append(
                {
                    self._text(normalized_type, value)
                    for value in answer
                    if self._text(normalized_type, value)
                }
            )

        if not observations:
            raise StorefrontDnsResolutionError(
                f"Authoritative DNS {normalized_type} lookup failed for {normalized_name}"
            )
        # Intersection is deliberately conservative during DNS propagation: a
        # proof is accepted only when every reachable authoritative server that
        # answered agrees that the value exists.
        agreed = set.intersection(*observations)
        return sorted(agreed)


storefront_dns_resolver = DnspythonStorefrontDnsResolver()
