"""
Vendor Scraper Configuration

State list, category mappings, and search query templates.
States are loaded from states.json — edit that file to change target states.
"""

import json
import logging
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ─── Load states from states.json ────────────────────────────────────────────
# Edit states.json to add/remove/change target states.
# Each entry: {"state": "XX", "state_full": "Oklahoma", "country": "US"}
_STATES_FILE = os.path.join(os.path.dirname(__file__), "states.json")

# Required keys for each state entry
_REQUIRED_KEYS = {"state", "state_full", "country"}

_states_cache: List[Tuple[str, str, str]] | None = None


def get_states() -> List[Tuple[str, str, str]]:
    """
    Load and validate states from the JSON config file.

    Lazy-loaded on first call and cached. This prevents the FastAPI server
    from crashing at import time if states.json is missing or malformed —
    only the scraper CLI fails when it actually tries to use the config.

    Returns:
        List of (state_abbrev, state_full, country) tuples.

    Raises:
        FileNotFoundError: If states.json doesn't exist.
        ValueError: If states.json has invalid structure or entries.
    """
    global _states_cache
    if _states_cache is not None:
        return _states_cache

    if not os.path.exists(_STATES_FILE):
        raise FileNotFoundError(
            f"states.json not found at {_STATES_FILE}. "
            "Create it with an array of state objects: "
            '[{"state": "OK", "state_full": "Oklahoma", "country": "US"}]'
        )

    try:
        with open(_STATES_FILE, "r") as f:
            entries = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in states.json at line {e.lineno}: {e.msg}"
        )

    if not isinstance(entries, list):
        raise ValueError(
            f"states.json must contain a JSON array, got {type(entries).__name__}"
        )

    if len(entries) == 0:
        raise ValueError("states.json is empty — add at least one state entry")

    states = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"states.json entry at index {i} must be an object, "
                f"got {type(entry).__name__}"
            )

        missing = _REQUIRED_KEYS - set(entry.keys())
        if missing:
            raise ValueError(
                f"states.json entry at index {i} is missing required keys: "
                f"{', '.join(sorted(missing))}. "
                f"Got: {entry}"
            )

        state_abbrev = str(entry["state"]).strip()
        state_full = str(entry["state_full"]).strip()
        country = str(entry["country"]).strip()

        if not state_abbrev or not state_full:
            raise ValueError(
                f"states.json entry at index {i} has empty state or state_full"
            )

        states.append((state_abbrev, state_full, country))

    _states_cache = states
    logger.info(f"Loaded {len(states)} states from states.json")
    return _states_cache


# ─── Google Places type → VendorCategory mapping ─────────────────────────────
# Google Places uses its own type taxonomy. We map to our VendorCategory enum.
# The scraper searches for each SEARCH_QUERIES entry and maps results using
# the category specified.
# {state_full} is the full state name (e.g. "Oklahoma") — Google Places handles
# geographic scoping across the entire state.

SEARCH_QUERIES = [
    # (search_query_template, our_vendor_category)
    ("wedding photographer in {state_full}", "photographer"),
    ("wedding videographer in {state_full}", "videographer"),
    ("wedding florist in {state_full}", "florist"),
    ("wedding caterer in {state_full}", "caterer"),
    ("wedding venue in {state_full}", "venue"),
    ("wedding DJ in {state_full}", "dj"),
    ("wedding MC host in {state_full}", "mc"),
    ("wedding band in {state_full}", "band"),
    ("wedding officiant in {state_full}", "officiant"),
    ("wedding planner in {state_full}", "planner"),
    ("wedding decorator in {state_full}", "decorator"),
    ("wedding cake bakery in {state_full}", "cake"),
    ("bridal hair makeup artist in {state_full}", "hair_makeup"),
    ("wedding transportation limo in {state_full}", "transportation"),
    ("wedding invitations stationery in {state_full}", "stationery"),
    ("wedding rentals in {state_full}", "rentals"),
    ("wedding lighting in {state_full}", "lighting"),
    ("photo booth rental wedding in {state_full}", "photo_booth"),
    ("wedding jewelry in {state_full}", "jewelry"),
    ("bridal shop wedding attire in {state_full}", "attire"),
]


# ─── Scraper constants ────────────────────────────────────────────────────────
SYSTEM_CREATED_BY = "system@thespecialwedding.com"
MAX_RESULTS_PER_QUERY = 20  # Google Places returns up to 20 per text search
REQUEST_DELAY_SECONDS = 0.5  # Polite delay between API calls
LOGO_MAX_WIDTH = 400  # Max width for downloaded logo images (px)
R2_LOGO_PREFIX = "scraped-vendors"  # Key prefix in R2 bucket
