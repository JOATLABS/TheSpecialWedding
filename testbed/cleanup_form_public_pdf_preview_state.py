#!/usr/bin/env python3
"""Cleanup paired with verify_form_public_pdf_preview.py.

The public PDF endpoint is stateless — no Mongo rows to remove. This
script exists to satisfy the "every driver ships a cleanup pair"
testbed house rule; it is intentionally a no-op so re-runs are safe.
"""

from __future__ import annotations

from testbed._form_lifecycle_common import banner


def main() -> None:
    banner("cleanup_form_public_pdf_preview_state — no-op")
    print("  • Endpoint is stateless. Process-side LRU cache clears on app restart.")


if __name__ == "__main__":
    main()
