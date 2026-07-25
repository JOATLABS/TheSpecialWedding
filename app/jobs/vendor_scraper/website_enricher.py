"""
Website Enricher

Given a vendor's website URL, scrapes it for:
- Meta description / og:description → service_description
- Pricing clues → typical_price_min / typical_price_max

This is a best-effort enrichment step. If it fails, the vendor
still gets inserted with Google Places data only.
"""

import ipaddress
import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Regex to find dollar amounts like $500, $1,500, $2500.00
PRICE_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?")


async def enrich_from_website(website_url: str) -> dict:
    """
    Scrape a vendor's website for description and pricing hints.

    Returns dict with optional keys:
        - service_description: str
        - typical_price_min: float
        - typical_price_max: float
    """
    result = {}
    if not website_url:
        return result

    # SSRF protection — block private/reserved IPs and localhost
    try:
        parsed = urlparse(website_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", ""):
            logger.debug(f"Blocked private/local URL: {website_url}")
            return result
        try:
            addr = ipaddress.ip_address(host)
            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_reserved
                or addr.is_link_local
            ):
                logger.debug(f"Blocked private/reserved IP URL: {website_url}")
                return result
        except ValueError:
            pass  # Hostname, not an IP — fine
    except Exception:
        return result

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "TheSpecialWedding-VendorBot/1.0 (+https://thespecialwedding.io/bot)"
            },
        ) as client:
            resp = await client.get(website_url)
            resp.raise_for_status()
            html = resp.text[:50_000]  # Only parse first 50KB

        # Extract description from meta tags
        description = _extract_description(html)
        if description:
            result["service_description"] = description[:2000]

        # Extract pricing hints
        price_min, price_max = _extract_price_range(html)
        if price_min is not None:
            result["typical_price_min"] = price_min
        if price_max is not None:
            result["typical_price_max"] = price_max

    except httpx.HTTPError as e:
        logger.debug(f"Could not fetch {website_url}: {e}")
    except Exception as e:
        logger.debug(f"Website enrichment failed for {website_url}: {e}")

    return result


def _extract_description(html: str) -> str | None:
    """Extract best description from meta tags.

    Handles both attribute orderings:
      <meta property="og:description" content="...">
      <meta content="..." property="og:description">
    """
    # Try og:description first (usually more marketing-friendly)
    # Pattern 1: property/name before content
    og_match = re.search(
        r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not og_match:
        # Pattern 2: content before property/name
        og_match = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\']og:description["\']',
            html,
            re.IGNORECASE,
        )
    if og_match:
        return og_match.group(1).strip()

    # Fall back to meta description
    meta_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not meta_match:
        meta_match = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']description["\']',
            html,
            re.IGNORECASE,
        )
    if meta_match:
        return meta_match.group(1).strip()

    return None


def _extract_price_range(html: str) -> tuple[float | None, float | None]:
    """
    Look for dollar amounts in the page and return a (min, max) range.
    Very heuristic — only captures obvious pricing patterns.
    """
    matches = PRICE_PATTERN.findall(html)
    if not matches:
        return None, None

    prices = []
    for m in matches:
        try:
            val = float(m.replace("$", "").replace(",", ""))
            # Filter out unreasonable amounts (< $50 or > $100k)
            if 50 <= val <= 100_000:
                prices.append(val)
        except ValueError:
            continue

    if not prices:
        return None, None

    return min(prices), max(prices)
