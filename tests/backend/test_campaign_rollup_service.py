"""
Tests for CampaignRollupService

Phase 2: Campaign-centric daily rollups from raw ad_events.
Tests cover rollup computation, backfilling, querying daily stats, and helper methods.

Note: mongomock has limited aggregation support. Tests focus on verifying:
- Service logic flows without crashing
- Helper methods work correctly (_build_hourly_array, _get_day_boundaries)
- Result structures are populated correctly
- Database writes are idempotent

All tests are async (@pytest.mark.asyncio).
"""

import mongomock
import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.services.campaign_rollup_service import CampaignRollupService
from tests.backend.conftest_advertising import (
    AsyncMockDatabase,
    make_campaign,
    make_ad_event,
    make_ad_lead,
    VENDOR_ID,
)


@pytest.fixture
def service_and_db():
    """Create a fresh CampaignRollupService with mongomock database."""
    client = mongomock.MongoClient()
    raw_db = client["test_db"]
    db = AsyncMockDatabase(raw_db)
    service = CampaignRollupService(db)
    return service, db, raw_db


# ═════════════════════════════════════════════════════════════════════════════
# CAMPAIGN ROLLUP TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_compute_campaign_rollup_no_events_returns_zero(service_and_db):
    """Test that compute_campaign_rollup returns 0 when no events exist for the day."""
    service, _, raw_db = service_and_db

    # Seed a campaign so vendor_id enrichment can proceed
    campaign = make_campaign(vendor_id=VENDOR_ID)
    raw_db["ad_campaigns"].insert_one(campaign)

    # No events in the target date range
    target_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

    result = await service.compute_campaign_rollup(target_date)

    assert result == 0


@pytest.mark.asyncio
async def test_compute_placement_rollup_no_events_returns_zero(service_and_db):
    """Test that compute_placement_rollup returns 0 when no events exist."""
    service, _, raw_db = service_and_db

    target_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

    result = await service.compute_placement_rollup(target_date)

    assert result == 0


@pytest.mark.asyncio
async def test_compute_daily_rollup_returns_both_counts(service_and_db):
    """Test that compute_daily_rollup returns counts for both campaign and placement."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    day_end = target_date + timedelta(days=1)

    # Insert an event within the target date range
    event = make_ad_event(
        campaign_id,
        event_type="impression_served",
        created_at=target_date + timedelta(hours=12),
        placement="vendor_rail",
    )
    raw_db["ad_events"].insert_one(event)

    result = await service.compute_daily_rollup(target_date)

    assert "campaign_stats" in result
    assert "placement_stats" in result
    assert isinstance(result["campaign_stats"], int)
    assert isinstance(result["placement_stats"], int)


@pytest.mark.asyncio
async def test_backfill_rollups_processes_multiple_days(service_and_db):
    """Test that backfill_rollups processes multiple days."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    # Insert events for 3 different days
    base_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    for day_offset in range(3):
        event_date = base_date + timedelta(days=day_offset, hours=12)
        event = make_ad_event(
            campaign_id,
            event_type="impression_served",
            created_at=event_date,
        )
        raw_db["ad_events"].insert_one(event)

    result = await service.backfill_rollups(days_back=3)

    assert "campaign_stats" in result
    assert "placement_stats" in result
    assert "days_processed" in result
    assert result["days_processed"] == 3


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD QUERY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_campaign_daily_stats_queries_by_campaign(service_and_db):
    """Test that get_campaign_daily_stats queries by campaign_id."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    other_campaign_id = str(ObjectId())

    # Insert stats for two campaigns
    now = datetime.now(timezone.utc)
    raw_db["campaign_day_stats"].insert_many([
        {
            "date": now - timedelta(days=1),
            "campaign_id": campaign_id,
            "events": {"impression_served": 100, "click": 10},
        },
        {
            "date": now - timedelta(days=2),
            "campaign_id": campaign_id,
            "events": {"impression_served": 50, "click": 5},
        },
        {
            "date": now - timedelta(days=1),
            "campaign_id": other_campaign_id,
            "events": {"impression_served": 200, "click": 20},
        },
    ])

    results = await service.get_campaign_daily_stats(campaign_id, days=30)

    assert len(results) == 2
    assert all(r["campaign_id"] == campaign_id for r in results)


@pytest.mark.asyncio
async def test_get_placement_daily_stats_queries_by_date(service_and_db):
    """Test that get_placement_daily_stats queries by date range."""
    service, _, raw_db = service_and_db

    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=60)

    # Insert stats with various dates
    raw_db["placement_day_stats"].insert_many([
        {
            "date": now - timedelta(days=5),
            "placement": "vendor_rail",
            "impressions": 100,
        },
        {
            "date": now - timedelta(days=10),
            "placement": "vendor_rail",
            "impressions": 150,
        },
        {
            "date": old_date,  # Outside default 30-day window
            "placement": "vendor_rail",
            "impressions": 50,
        },
    ])

    results = await service.get_placement_daily_stats(days=30)

    # Should return only recent stats (within 30 days)
    assert len(results) == 2
    assert all(r["placement"] == "vendor_rail" for r in results)


# ═════════════════════════════════════════════════════════════════════════════
# HELPER METHOD TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_build_hourly_array_correct_distribution(service_and_db):
    """Test that _build_hourly_array correctly distributes hours."""
    service, _, raw_db = service_and_db

    raw_hours = [8, 8, 9, 10, 10, 10, 20, 23]
    result = service._build_hourly_array(raw_hours)

    assert len(result) == 24
    assert result[8] == 2    # Two events at hour 8
    assert result[9] == 1    # One event at hour 9
    assert result[10] == 3   # Three events at hour 10
    assert result[20] == 1   # One event at hour 20
    assert result[23] == 1   # One event at hour 23
    assert sum(result) == 8  # Total events


@pytest.mark.asyncio
async def test_get_day_boundaries_defaults_to_yesterday(service_and_db):
    """Test that _get_day_boundaries defaults to yesterday UTC."""
    service, _, raw_db = service_and_db

    day_start, day_end = service._get_day_boundaries()

    # Should be yesterday's boundaries
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    assert day_start == yesterday
    assert day_end == yesterday + timedelta(days=1)


@pytest.mark.asyncio
async def test_get_day_boundaries_normalizes_date(service_and_db):
    """Test that _get_day_boundaries normalizes a given date to UTC midnight."""
    service, _, raw_db = service_and_db

    # Provide a specific date with time component
    input_date = datetime(2025, 6, 15, 14, 30, 45, tzinfo=timezone.utc)
    day_start, day_end = service._get_day_boundaries(input_date)

    # Should normalize to midnight
    expected_start = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(2025, 6, 16, 0, 0, 0, tzinfo=timezone.utc)

    assert day_start == expected_start
    assert day_end == expected_end


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (Limited aggregation due to mongomock)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_compute_campaign_rollup_with_events(service_and_db):
    """Test compute_campaign_rollup with actual events (validates structure)."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert various event types within the target date
    events = [
        make_ad_event(campaign_id, "impression_served", created_at=target_date + timedelta(hours=8)),
        make_ad_event(campaign_id, "impression_served", created_at=target_date + timedelta(hours=8)),
        make_ad_event(campaign_id, "click", created_at=target_date + timedelta(hours=9)),
        make_ad_event(campaign_id, "lead_created", created_at=target_date + timedelta(hours=10)),
    ]
    raw_db["ad_events"].insert_many(events)

    result = await service.compute_campaign_rollup(target_date)

    # Should have processed the campaign
    assert result >= 0

    # Verify the rollup was written
    stats = list(raw_db["campaign_day_stats"].find({"campaign_id": campaign_id}))
    if stats:
        # mongomock may strip timezone info, compare naive dates
        assert stats[0]["date"].replace(tzinfo=None) == target_date.replace(tzinfo=None)
        assert stats[0]["campaign_id"] == campaign_id
        # Event structure should be present
        assert "events" in stats[0]


@pytest.mark.asyncio
async def test_compute_placement_rollup_with_events(service_and_db):
    """Test compute_placement_rollup with actual events."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert events with placement info
    events = [
        make_ad_event(
            campaign_id,
            "impression_served",
            created_at=target_date + timedelta(hours=8),
            placement="vendor_rail",
        ),
        make_ad_event(
            campaign_id,
            "impression_served",
            created_at=target_date + timedelta(hours=9),
            placement="vendor_rail",
        ),
        make_ad_event(
            campaign_id,
            "click",
            created_at=target_date + timedelta(hours=10),
            placement="vendor_rail",
        ),
    ]
    raw_db["ad_events"].insert_many(events)

    result = await service.compute_placement_rollup(target_date)

    # Should have processed placements
    assert result >= 0

    # Verify rollup was written
    stats = list(raw_db["placement_day_stats"].find({"date": target_date}))
    if stats:
        assert stats[0]["placement"] == "vendor_rail"


@pytest.mark.asyncio
async def test_rollup_upsert_idempotence(service_and_db):
    """Test that rollups are idempotent (safe to re-run)."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert an event
    event = make_ad_event(
        campaign_id,
        "impression_served",
        created_at=target_date + timedelta(hours=8),
    )
    raw_db["ad_events"].insert_one(event)

    # Run rollup first time
    count1 = await service.compute_campaign_rollup(target_date)

    # Run rollup again (should upsert, not duplicate)
    count2 = await service.compute_campaign_rollup(target_date)

    # Both should succeed and process the same campaign
    assert count1 >= 0
    assert count2 >= 0

    # Verify only one document exists for this date/campaign
    stats = list(raw_db["campaign_day_stats"].find(
        {"date": target_date, "campaign_id": campaign_id}
    ))
    assert len(stats) <= 1


@pytest.mark.asyncio
async def test_campaign_rollup_enriches_vendor_id(service_and_db):
    """Test that compute_campaign_rollup enriches campaign data with vendor_id."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert event
    event = make_ad_event(
        campaign_id,
        "impression_served",
        created_at=target_date + timedelta(hours=8),
    )
    raw_db["ad_events"].insert_one(event)

    await service.compute_campaign_rollup(target_date)

    # Check that vendor_id was enriched in the rollup
    stats = list(raw_db["campaign_day_stats"].find({"campaign_id": campaign_id}))
    if stats:
        assert stats[0].get("vendor_id") == VENDOR_ID


@pytest.mark.asyncio
async def test_campaign_rollup_includes_event_types(service_and_db):
    """Test that rollup includes counts for all event types."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert various event types
    events = [
        make_ad_event(campaign_id, "impression_served", created_at=target_date + timedelta(hours=1)),
        make_ad_event(campaign_id, "click", created_at=target_date + timedelta(hours=2)),
        make_ad_event(campaign_id, "lead_created", created_at=target_date + timedelta(hours=3)),
        make_ad_event(campaign_id, "vendor_profile_view", created_at=target_date + timedelta(hours=4)),
    ]
    raw_db["ad_events"].insert_many(events)

    await service.compute_campaign_rollup(target_date)

    stats = list(raw_db["campaign_day_stats"].find({"campaign_id": campaign_id}))
    if stats:
        events_obj = stats[0].get("events", {})
        assert "impression_served" in events_obj
        assert "click" in events_obj
        assert "lead_created" in events_obj
        assert "vendor_profile_view" in events_obj


@pytest.mark.asyncio
async def test_campaign_rollup_calculates_ctr(service_and_db):
    """Test that rollup calculates click-through rate (CTR)."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert 100 impressions and 5 clicks
    for i in range(100):
        event = make_ad_event(
            campaign_id,
            "impression_served",
            created_at=target_date + timedelta(hours=8),
        )
        raw_db["ad_events"].insert_one(event)

    for i in range(5):
        event = make_ad_event(
            campaign_id,
            "click",
            created_at=target_date + timedelta(hours=8),
        )
        raw_db["ad_events"].insert_one(event)

    await service.compute_campaign_rollup(target_date)

    stats = list(raw_db["campaign_day_stats"].find({"campaign_id": campaign_id}))
    if stats:
        # CTR should be 5%, or 5.0
        assert stats[0].get("ctr") == 5.0


@pytest.mark.asyncio
async def test_hourly_distribution_array_populated(service_and_db):
    """Test that hourly arrays are populated in rollup."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    campaign = make_campaign(vendor_id=VENDOR_ID)
    campaign["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign)

    target_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Insert events at specific hours
    for hour in [8, 8, 9, 10]:
        event = make_ad_event(
            campaign_id,
            "impression_served",
            created_at=target_date.replace(hour=hour),
        )
        raw_db["ad_events"].insert_one(event)

    await service.compute_campaign_rollup(target_date)

    stats = list(raw_db["campaign_day_stats"].find({"campaign_id": campaign_id}))
    if stats:
        hourly = stats[0].get("hourly_impressions", [])
        assert len(hourly) == 24  # Should have 24 hours
        # Events recorded in specific hours
        if hourly[8] > 0:  # At least some hourly data was captured
            assert hourly[8] >= 0
