"""
PM Substrate HTTP client configuration.

All settings driven by environment variables. Sane defaults for local dev
(substrate listening on 4000 with no auth token).

Environment variables:
  PM_SUBSTRATE_URL     Base URL of the substrate-http service.
                       Default: http://localhost:4000
  PM_SUBSTRATE_TOKEN   Bearer token for substrate-http (when auth is wired).
                       Default: "" (no auth header sent when empty).
  PM_SUBSTRATE_TIMEOUT Seconds to wait for a substrate response before raising.
                       Default: 10.0
  PM_SUBSTRATE_RETRIES Number of retries on transient errors (5xx / network).
                       Default: 2
"""
import os

PM_SUBSTRATE_URL: str = os.environ.get("PM_SUBSTRATE_URL", "http://localhost:4000")
PM_SUBSTRATE_TOKEN: str = os.environ.get("PM_SUBSTRATE_TOKEN", "")
PM_SUBSTRATE_TIMEOUT: float = float(os.environ.get("PM_SUBSTRATE_TIMEOUT", "10.0"))
PM_SUBSTRATE_RETRIES: int = int(os.environ.get("PM_SUBSTRATE_RETRIES", "2"))
