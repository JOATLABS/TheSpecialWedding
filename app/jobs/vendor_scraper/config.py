"""
Vendor Scraper Configuration

City list, category mappings, and search query templates.
"""

# ─── Pilot cities to scrape ──────────────────────────────────────────────────
# Each entry: (city, state_abbrev, state_full, country)
PILOT_CITIES = [
    ("Atlanta", "GA", "Georgia", "US"),
    ("Houston", "TX", "Texas", "US"),
    ("New York", "NY", "New York", "US"),
    ("Los Angeles", "CA", "California", "US"),
    ("Chicago", "IL", "Illinois", "US"),
]


# ─── Google Places type → VendorCategory mapping ─────────────────────────────
# Google Places uses its own type taxonomy. We map to our VendorCategory enum.
# The scraper searches for each SEARCH_QUERIES entry and maps results using
# the category specified.

SEARCH_QUERIES = [
    # (search_query_template, our_vendor_category)
    ("wedding photographer in {city}, {state}", "photographer"),
    ("wedding videographer in {city}, {state}", "videographer"),
    ("wedding florist in {city}, {state}", "florist"),
    ("wedding caterer in {city}, {state}", "caterer"),
    ("wedding venue in {city}, {state}", "venue"),
    ("wedding DJ in {city}, {state}", "dj"),
    ("wedding MC host in {city}, {state}", "mc"),
    ("wedding band in {city}, {state}", "band"),
    ("wedding officiant in {city}, {state}", "officiant"),
    ("wedding planner in {city}, {state}", "planner"),
    ("wedding decorator in {city}, {state}", "decorator"),
    ("wedding cake bakery in {city}, {state}", "cake"),
    ("bridal hair makeup artist in {city}, {state}", "hair_makeup"),
    ("wedding transportation limo in {city}, {state}", "transportation"),
    ("wedding invitations stationery in {city}, {state}", "stationery"),
    ("wedding rentals in {city}, {state}", "rentals"),
    ("wedding lighting in {city}, {state}", "lighting"),
    ("photo booth rental wedding in {city}, {state}", "photo_booth"),
    ("wedding jewelry in {city}, {state}", "jewelry"),
    ("bridal shop wedding attire in {city}, {state}", "attire"),
]


# ─── Scraper constants ────────────────────────────────────────────────────────
SYSTEM_CREATED_BY = "system@thespecialwedding.com"
MAX_RESULTS_PER_QUERY = 20  # Google Places returns up to 20 per text search
REQUEST_DELAY_SECONDS = 0.5  # Polite delay between API calls
LOGO_MAX_WIDTH = 400  # Max width for downloaded logo images (px)
R2_LOGO_PREFIX = "scraped-vendors"  # Key prefix in R2 bucket
