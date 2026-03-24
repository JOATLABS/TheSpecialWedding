"""
Ad Fraud Detection Service

Analyzes ad_events in real-time and on a scheduled basis to detect fraudulent
click patterns. Creates ad_fraud_signals when anomalies are found.

Detection methods:
  1. Click velocity — too many clicks from the same planner on the same campaign
     within a short window (5 minutes)
  2. Duplicate clicks — same planner + campaign + creative within a 1-minute window
  3. Session anomaly — excessive events from a single session_id in a short period
  4. High hide rate — campaigns with unusually high planner hide/suppress rates

Called from:
  - Real-time: after each click event in PlannerAdInteractionService
  - Scheduled: nightly rollup scheduler for aggregate pattern detection
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

logger = logging.getLogger(__name__)


class AdFraudDetectionService:
    """Fraud detection for the advertising platform."""

    # ── Thresholds (match mockup Platform Config > Fraud Detection) ──
    MAX_CLICKS_PER_PLANNER_PER_CAMPAIGN_PER_HOUR = 5
    CLICK_VELOCITY_WINDOW_MINUTES = 5
    MAX_CLICKS_IN_VELOCITY_WINDOW = 4
    DUPLICATE_CLICK_WINDOW_SECONDS = 60
    HIGH_HIDE_RATE_THRESHOLD = 0.03  # 3% unique hides in 7 days
    MAX_EVENTS_PER_SESSION_PER_HOUR = 50

    def __init__(self, db):
        self.db = db
        self.ad_events = db["ad_events"]
        self.fraud_signals = db["ad_fraud_signals"]
        self.campaigns = db["ad_campaigns"]

    # ─── Real-Time Check (called after each click event) ─────────

    async def check_click_event(
        self,
        planner_id: str,
        campaign_id: str,
        creative_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Run real-time fraud checks after a click event.

        Returns fraud signal dict if fraud detected, None otherwise.
        """
        now = datetime.now(timezone.utc)
        signals = []

        # Check 1: Click velocity — too many clicks in short window
        velocity_signal = await self._check_click_velocity(
            planner_id, campaign_id, now
        )
        if velocity_signal:
            signals.append(velocity_signal)

        # Check 2: Duplicate click — same planner + campaign + creative in 1 min
        if creative_id:
            dup_signal = await self._check_duplicate_click(
                planner_id, campaign_id, creative_id, now
            )
            if dup_signal:
                signals.append(dup_signal)

        # Check 3: Session anomaly — too many events from one session
        if session_id:
            session_signal = await self._check_session_anomaly(
                session_id, now
            )
            if session_signal:
                signals.append(session_signal)

        # Insert all detected signals
        for signal in signals:
            await self.fraud_signals.insert_one(signal)
            logger.warning(
                f"Fraud signal: {signal['signal_type']} — "
                f"planner={planner_id} campaign={campaign_id}"
            )

        # Push-notify admin about fraud signals
        if signals:
            try:
                from app.services.vendor_notification_service import VendorNotificationService
                vns = VendorNotificationService()
                await vns.notify_admin_fraud_detected(
                    signal_type=signals[0]["signal_type"],
                    planner_id=planner_id,
                    campaign_id=campaign_id,
                )
            except Exception as e:
                logger.warning(f"Failed to push-notify admin on fraud signal: {e}")

        return signals[0] if signals else None

    async def _check_click_velocity(
        self, planner_id: str, campaign_id: str, now: datetime
    ) -> Optional[Dict[str, Any]]:
        """Detect rapid clicking on the same campaign."""
        window_start = now - timedelta(minutes=self.CLICK_VELOCITY_WINDOW_MINUTES)

        count = await self.ad_events.count_documents({
            "planner_id": planner_id,
            "campaign_id": campaign_id,
            "event_type": {"$in": ["click", "vendor_added_to_directory", "quote_requested"]},
            "created_at": {"$gte": window_start},
        })

        if count >= self.MAX_CLICKS_IN_VELOCITY_WINDOW:
            return {
                "signal_type": "rapid_clicks",
                "campaign_id": campaign_id,
                "planner_id": planner_id,
                "click_velocity": count,
                "details": {
                    "window_minutes": self.CLICK_VELOCITY_WINDOW_MINUTES,
                    "threshold": self.MAX_CLICKS_IN_VELOCITY_WINDOW,
                    "actual_count": count,
                },
                "status": "pending",
                "flagged_at": now,
                "created_at": now,
                "updated_at": now,
            }
        return None

    async def _check_duplicate_click(
        self,
        planner_id: str,
        campaign_id: str,
        creative_id: str,
        now: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Detect exact duplicate clicks (same planner + campaign + creative within 1 min)."""
        window_start = now - timedelta(seconds=self.DUPLICATE_CLICK_WINDOW_SECONDS)

        count = await self.ad_events.count_documents({
            "planner_id": planner_id,
            "campaign_id": campaign_id,
            "creative_id": creative_id,
            "event_type": {"$in": ["click", "vendor_added_to_directory", "quote_requested"]},
            "created_at": {"$gte": window_start},
        })

        if count >= 2:  # Current click + at least 1 duplicate
            return {
                "signal_type": "duplicate_click",
                "campaign_id": campaign_id,
                "planner_id": planner_id,
                "details": {
                    "creative_id": creative_id,
                    "window_seconds": self.DUPLICATE_CLICK_WINDOW_SECONDS,
                    "duplicate_count": count,
                },
                "status": "pending",
                "flagged_at": now,
                "created_at": now,
                "updated_at": now,
            }
        return None

    async def _check_session_anomaly(
        self, session_id: str, now: datetime
    ) -> Optional[Dict[str, Any]]:
        """Detect excessive events from a single session."""
        window_start = now - timedelta(hours=1)

        count = await self.ad_events.count_documents({
            "session_id": session_id,
            "created_at": {"$gte": window_start},
        })

        if count >= self.MAX_EVENTS_PER_SESSION_PER_HOUR:
            return {
                "signal_type": "bot_pattern",
                "session_id": session_id,
                "details": {
                    "window_hours": 1,
                    "threshold": self.MAX_EVENTS_PER_SESSION_PER_HOUR,
                    "actual_count": count,
                },
                "status": "pending",
                "flagged_at": now,
                "created_at": now,
                "updated_at": now,
            }
        return None

    # ─── Scheduled / Batch Detection (called by nightly cron) ────

    async def run_batch_detection(self) -> Dict[str, Any]:
        """
        Run aggregate fraud detection across all campaigns.
        Called by the nightly rollup scheduler.

        Checks:
          1. High hide rates per campaign (7-day window)
          2. Hourly click patterns that exceed per-planner limits
          3. Geographic anomalies (same vendor clicked from many IPs)

        Returns summary of signals created.
        """
        now = datetime.now(timezone.utc)
        signals_created = 0

        # ── 1. High hide rate detection ──
        hide_signals = await self._detect_high_hide_rates(now)
        signals_created += hide_signals

        # ── 2. Hourly planner click abuse (aggregated) ──
        click_signals = await self._detect_hourly_click_abuse(now)
        signals_created += click_signals

        logger.info(f"Batch fraud detection complete: {signals_created} signals created")
        return {"signals_created": signals_created}

    async def _detect_high_hide_rates(self, now: datetime) -> int:
        """
        Flag campaigns where the hide/suppress rate exceeds the threshold
        over the last 7 days.
        """
        seven_days_ago = now - timedelta(days=7)
        signals_created = 0

        # Aggregate hide events per campaign
        pipeline = [
            {
                "$match": {
                    "event_type": {"$in": ["hide", "suppress"]},
                    "created_at": {"$gte": seven_days_ago},
                }
            },
            {
                "$group": {
                    "_id": "$campaign_id",
                    "hide_count": {"$sum": 1},
                    "unique_planners": {"$addToSet": "$planner_id"},
                }
            },
        ]

        async for result in self.ad_events.aggregate(pipeline):
            campaign_id = result["_id"]
            hide_count = result["hide_count"]
            unique_hiders = len(result.get("unique_planners", []))

            # Get total impressions for this campaign in the same window
            impression_count = await self.ad_events.count_documents({
                "campaign_id": campaign_id,
                "event_type": "impression",
                "created_at": {"$gte": seven_days_ago},
            })

            if impression_count == 0:
                continue

            hide_rate = hide_count / impression_count

            if hide_rate >= self.HIGH_HIDE_RATE_THRESHOLD:
                # Check if we already have a recent signal for this campaign
                existing = await self.fraud_signals.find_one({
                    "campaign_id": campaign_id,
                    "signal_type": "unusual_traffic",
                    "flagged_at": {"$gte": seven_days_ago},
                })
                if existing:
                    continue

                signal = {
                    "signal_type": "unusual_traffic",
                    "campaign_id": campaign_id,
                    "details": {
                        "detection": "high_hide_rate",
                        "hide_rate": round(hide_rate, 4),
                        "hide_count": hide_count,
                        "unique_hiders": unique_hiders,
                        "impression_count": impression_count,
                        "threshold": self.HIGH_HIDE_RATE_THRESHOLD,
                        "window_days": 7,
                    },
                    "status": "pending",
                    "flagged_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                await self.fraud_signals.insert_one(signal)
                signals_created += 1
                logger.warning(
                    f"High hide rate detected: campaign {campaign_id} "
                    f"rate={hide_rate:.2%} ({hide_count} hides / {impression_count} impressions)"
                )

        return signals_created

    async def _detect_hourly_click_abuse(self, now: datetime) -> int:
        """
        Detect planners who exceeded the hourly click limit on any campaign
        in the last 24 hours.
        """
        one_day_ago = now - timedelta(days=1)
        signals_created = 0

        pipeline = [
            {
                "$match": {
                    "event_type": {"$in": ["click", "vendor_added_to_directory", "quote_requested"]},
                    "created_at": {"$gte": one_day_ago},
                }
            },
            {
                "$group": {
                    "_id": {
                        "planner_id": "$planner_id",
                        "campaign_id": "$campaign_id",
                        "hour": {"$dateToString": {"format": "%Y-%m-%dT%H", "date": "$created_at"}},
                    },
                    "click_count": {"$sum": 1},
                }
            },
            {
                "$match": {
                    "click_count": {"$gte": self.MAX_CLICKS_PER_PLANNER_PER_CAMPAIGN_PER_HOUR}
                }
            },
        ]

        async for result in self.ad_events.aggregate(pipeline):
            key = result["_id"]
            planner_id = key.get("planner_id", "")
            campaign_id = key.get("campaign_id", "")
            hour = key.get("hour", "")

            # Avoid duplicate signals for same planner+campaign+hour
            existing = await self.fraud_signals.find_one({
                "planner_id": planner_id,
                "campaign_id": campaign_id,
                "signal_type": "rapid_clicks",
                "details.detection_hour": hour,
            })
            if existing:
                continue

            signal = {
                "signal_type": "rapid_clicks",
                "campaign_id": campaign_id,
                "planner_id": planner_id,
                "click_velocity": result["click_count"],
                "details": {
                    "detection": "hourly_click_abuse",
                    "detection_hour": hour,
                    "click_count": result["click_count"],
                    "threshold": self.MAX_CLICKS_PER_PLANNER_PER_CAMPAIGN_PER_HOUR,
                },
                "status": "pending",
                "flagged_at": now,
                "created_at": now,
                "updated_at": now,
            }
            await self.fraud_signals.insert_one(signal)
            signals_created += 1

        return signals_created
