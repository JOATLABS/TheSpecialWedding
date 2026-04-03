"""
Vendor Scraper Configuration

State list, category mappings, and search query templates.
States are loaded from states.json — edit that file to change target states.
"""

import json
import os

# ─── Load states from states.json ────────────────────────────────────────────
# Edit states.json to add/remove/change target states.
# Each entry: {"state": "XX", "state_full": "Oklahoma", "country": "US"}
_STATES_FILE = os.path.join(os.path.dirname(__file__), "states.json")

def _load_states():
    """Load states from the JSON config file."""
    if not os.path.exists(_STATES_FILE):
        raise FileNotFoundError(
            f"states.json not found at {_STATES_FILE}. "
            "Create it with an array of state objects: "
            '[{"state": "OK", "state_full": "Oklahoma", "country": "US"}]'
        )
    with open(_STATES_FILE, "r") as f:
        entries = json.load(f)
    return [(e["state"], e["state_full"], e["country"]) for e in entries]

STATES = _load_states()


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
