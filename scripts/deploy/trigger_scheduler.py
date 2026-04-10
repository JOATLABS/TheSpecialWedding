#!/usr/bin/env python3
"""Trigger authenticated scheduler endpoints with HMAC or legacy key auth."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable


def _build_url(base_url: str, path: str, query_items: Iterable[str]) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    query_pairs: list[tuple[str, str]] = []
    for raw_item in query_items:
        if "=" not in raw_item:
            raise ValueError(f"Invalid --query value `{raw_item}`; expected key=value")
        key, value = raw_item.split("=", 1)
        query_pairs.append((key, value))
    query_string = urllib.parse.urlencode(query_pairs, doseq=True)
    return f"{normalized_base}{normalized_path}" + (
        f"?{query_string}" if query_string else ""
    )


def _build_headers(
    *,
    method: str,
    path: str,
    hmac_secret: str | None,
    scheduler_key: str | None,
) -> dict[str, str]:
    normalized_path = path if path.startswith("/") else f"/{path}"
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "weddingwebapp-calendar-scheduler/1.0",
    }

    if hmac_secret:
        timestamp = str(int(time.time()))
        payload = f"{timestamp}.{method.upper()}.{normalized_path}"
        digest = hmac.new(
            hmac_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["X-Scheduler-Timestamp"] = timestamp
        headers["X-Scheduler-Signature"] = f"sha256={digest}"
        return headers

    if scheduler_key:
        headers["X-Scheduler-Key"] = scheduler_key
        return headers

    raise ValueError(
        "Provide SCHEDULER_HMAC_SECRET/--hmac-secret or "
        "SCHEDULER_API_KEY/--scheduler-key"  # pragma: allowlist secret
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trigger one scheduler endpoint with signed authentication.",
    )
    parser.add_argument("--base-url", default=os.getenv("SCHEDULER_BASE_URL"))
    parser.add_argument("--path", required=True)
    parser.add_argument("--method", default="POST")
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Optional query item in key=value form. May be repeated.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--hmac-secret", default=os.getenv("SCHEDULER_HMAC_SECRET"))
    parser.add_argument("--scheduler-key", default=os.getenv("SCHEDULER_API_KEY"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request that would be sent without sending it.",
    )
    args = parser.parse_args()

    if not args.base_url:
        print("Missing SCHEDULER_BASE_URL / --base-url", file=sys.stderr)
        return 2

    try:
        url = _build_url(args.base_url, args.path, args.query)
        headers = _build_headers(
            method=args.method,
            path=args.path,
            hmac_secret=args.hmac_secret,
            scheduler_key=args.scheduler_key,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {"url": url, "method": args.method.upper(), "headers": headers},
                indent=2,
            )
        )
        return 0

    request = urllib.request.Request(
        url=url, method=args.method.upper(), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(body)
            return 0 if 200 <= response.status < 300 else 1
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(body or str(exc), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Scheduler request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
