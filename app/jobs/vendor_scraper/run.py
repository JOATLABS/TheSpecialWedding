"""
Vendor Directory Scraper — Main Runner

Scrapes wedding vendors state-by-state using Google Places API,
enriches with website data, uploads logos to R2, and upserts
into the vendor_profiles collection.

Usage:
    # From project root:
    python -m app.jobs.vendor_scraper.run

    # Scrape specific state(s):
    python -m app.jobs.vendor_scraper.run --state OK
    python -m app.jobs.vendor_scraper.run --state OK TX CA

    # Dry run (no DB writes):
    python -m app.jobs.vendor_scraper.run --dry-run

    # Limit categories:
    python -m app.jobs.vendor_scraper.run --categories photographer,florist,venue
"""

import asyncio
import argparse
import logging
import time
from typing import List, Optional

from app.core.database import mongo
from app.services.vendor_service import VendorService
from app.jobs.vendor_scraper.config import (
    get_states,
    SEARCH_QUERIES,
    REQUEST_DELAY_SECONDS,
)
from app.jobs.vendor_scraper.google_places import search_vendors
from app.jobs.vendor_scraper.website_enricher import enrich_from_website
from app.jobs.vendor_scraper.logo_uploader import download_and_upload_logo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def scrape_state(
    state: str,
    state_full: str,
    country: str,
    vendor_service: VendorService,
    categories_filter: Optional[List[str]] = None,
    dry_run: bool = False,
) -> dict:
    """
    Scrape all vendor categories for a single state.

    Returns stats: {inserted: int, updated: int, skipped: int, errors: int}
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    for query_template, vendor_category in SEARCH_QUERIES:
        # Filter to specific categories if requested
        if categories_filter and vendor_category not in categories_filter:
            continue

        query = query_template.format(state=state, state_full=state_full)
        logger.info(f"Searching: {query}")

        # 1. Search Google Places
        places = await search_vendors(query)
        if not places:
            logger.info(f"  → 0 results")
            continue

        logger.info(f"  → {len(places)} results")

        for place in places:
            try:
                place["service_category"] = vendor_category
                place["scraped_from_state"] = state

                # 2. Download and upload logo to R2
                photo_url = place.pop("photo_url", None)
                if photo_url and not dry_run:
                    logo_url = await download_and_upload_logo(
                        photo_url=photo_url,
                        business_name=place["business_name"],
                        city=place.get("city"),
                        state=state_full,
                    )
                    if logo_url:
                        place["logo_url"] = logo_url

                # 3. Enrich from vendor website
                if place.get("website"):
                    enrichment = await enrich_from_website(place["website"])
                    # Only fill in fields not already set by Google Places
                    for key, val in enrichment.items():
                        if key not in place or place[key] is None:
                            place[key] = val

                # 4. Upsert into vendor_profiles
                if dry_run:
                    logger.info(f"  [DRY RUN] Would upsert: {place['business_name']} ({vendor_category})")
                    stats["skipped"] += 1
                else:
                    result = await vendor_service.upsert_scraped_vendor(place)
                    if result is None:
                        stats["skipped"] += 1
                    elif result.get("source") == "manual":
                        # Manual entry was not overwritten
                        stats["skipped"] += 1
                    elif result.get("created_at") == result.get("updated_at"):
                        # Newly inserted — created_at and updated_at match
                        stats["inserted"] += 1
                    else:
                        stats["updated"] += 1

            except Exception as e:
                logger.error(f"  Error processing {place.get('business_name', '?')}: {e}")
                stats["errors"] += 1

        # Be polite — delay between queries
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

    return stats


async def run_scraper(
    states: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    dry_run: bool = False,
):
    """
    Main entry point. Scrapes all configured states (or a specific subset).
    """
    # Load states config (lazy — only loaded when scraper actually runs)
    all_states = get_states()

    try:
        # Motor connects lazily on first DB operation — no explicit connect needed.
        # Verify the connection is live before starting the scrape.
        await mongo.test_connection()
        vendor_service = VendorService()

        # Filter to specific states if requested
        state_list = all_states
        if states:
            states_lower = {x.lower() for x in states}
            state_list = [
                s for s in all_states
                if s[0].lower() in states_lower
                or s[1].lower() in states_lower
            ]
            if not state_list:
                logger.error(f"No matching states for: {states}")
                logger.info(f"Available (from states.json): {[(s[0], s[1]) for s in all_states]}")
                return

        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        start_time = time.time()

        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Starting vendor scraper for {len(state_list)} states")

        for state, state_full, country in state_list:
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping: {state_full} ({state})")
            logger.info(f"{'='*60}")

            stats = await scrape_state(
                state=state,
                state_full=state_full,
                country=country,
                vendor_service=vendor_service,
                categories_filter=categories,
                dry_run=dry_run,
            )

            for key in total_stats:
                total_stats[key] += stats[key]

            logger.info(f"State {state_full} done: {stats}")

        elapsed = time.time() - start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraper complete in {elapsed:.1f}s")
        logger.info(f"Total: {total_stats}")
        logger.info(f"{'='*60}")

    finally:
        mongo.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape wedding vendors from Google Places")
    parser.add_argument(
        "--state",
        action="extend",
        nargs="+",
        dest="states",
        help="State(s) to scrape (abbrev or full name). Repeatable: --state OK TX",
    )
    parser.add_argument("--categories", type=str, help="Comma-separated categories to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Search but don't write to DB")
    args = parser.parse_args()

    categories = args.categories.split(",") if args.categories else None

    asyncio.run(run_scraper(states=args.states, categories=categories, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
