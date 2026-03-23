"""
Ad Auction Service

Implements a second-price auction engine for the advertising platform.

Formula: AdRank = Bid × EstimatedActionRate × QualityScore

Where:
  - Bid: vendor's bid_amount (CPL bid) or daily_budget-derived effective bid
  - EstimatedActionRate: historical action rate (CTR, lead rate) for the campaign,
    smoothed with Bayesian priors to handle cold-start campaigns
  - QualityScore: admin-set quality score (1-100), normalized to 0-1

The auction determines:
  1. Which campaigns are eligible to serve (budget check, active status, targeting)
  2. Their ranking order (by AdRank descending)
  3. The effective cost (second-price: pay just enough to beat the next bidder)

PRD Reference: Phase 9 — Auction Engine
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Bayesian smoothing for EstimatedActionRate ──
# We use a beta prior so cold-start campaigns don't get unfairly boosted/penalized.
# Prior: ~2% action rate (industry average for display advertising)
PRIOR_ACTIONS = 2       # pseudo-observations of actions
PRIOR_IMPRESSIONS = 100  # pseudo-observations of impressions
# This gives a prior rate of 2/100 = 2%

# Default bid for free-tier campaigns (ensures they still serve, just ranked lower)
DEFAULT_FREE_TIER_BID = 0.01

# Minimum AdRank required to serve (prevents very low quality from serving)
MIN_ADRANK_TO_SERVE = 0.001


class AdAuctionService:
    """
    Auction engine for ranking and pricing advertising campaign impressions.

    Reads from: ad_campaigns, campaign_day_stats
    Does not write — the auction is a pure scoring function.
    """

    def __init__(self, db):
        self.db = db
        self.campaigns = db["ad_campaigns"]
        self.day_stats = db["campaign_day_stats"]

    async def compute_estimated_action_rate(
        self, campaign_id: str, lookback_days: int = 30
    ) -> float:
        """
        Compute Bayesian-smoothed estimated action rate for a campaign.

        Uses campaign_day_stats aggregated over the lookback period.
        Smoothed with beta prior to handle cold-start campaigns.

        Returns: float between 0 and 1
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        pipeline = [
            {
                "$match": {
                    "campaign_id": campaign_id,
                    "date": {"$gte": cutoff},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_impressions": {
                        "$sum": "$events.impression_served"
                    },
                    "total_clicks": {
                        "$sum": "$events.click"
                    },
                    "total_leads": {
                        "$sum": "$events.lead_created"
                    },
                }
            },
        ]

        impressions = 0
        actions = 0  # clicks + leads (weighted)

        async for doc in self.day_stats.aggregate(pipeline):
            impressions = doc.get("total_impressions", 0)
            clicks = doc.get("total_clicks", 0)
            leads = doc.get("total_leads", 0)
            # Leads are worth more than clicks in CPL model
            actions = clicks + (leads * 3)

        # Bayesian smoothing: (observed_actions + prior_actions) / (observed_impressions + prior_impressions)
        smoothed_rate = (actions + PRIOR_ACTIONS) / (impressions + PRIOR_IMPRESSIONS)

        return min(smoothed_rate, 1.0)

    def compute_adrank(
        self,
        bid: float,
        estimated_action_rate: float,
        quality_score: int,
    ) -> float:
        """
        Compute AdRank for a campaign.

        AdRank = Bid × EstimatedActionRate × NormalizedQualityScore

        Where NormalizedQualityScore = quality_score / 100 (maps 1-100 to 0.01-1.0)
        """
        normalized_qs = max(quality_score, 1) / 100.0
        adrank = bid * estimated_action_rate * normalized_qs
        return round(adrank, 6)

    def compute_second_price(
        self,
        winner_adrank: float,
        runner_up_adrank: float,
        winner_estimated_action_rate: float,
        winner_quality_score: int,
    ) -> float:
        """
        Compute second-price cost: the minimum bid the winner needs to beat
        the runner-up.

        second_price_bid = runner_up_adrank / (estimated_action_rate × quality_score)
        actual_cost = max(second_price_bid, min_bid)
        """
        normalized_qs = max(winner_quality_score, 1) / 100.0
        denominator = winner_estimated_action_rate * normalized_qs

        if denominator <= 0:
            return DEFAULT_FREE_TIER_BID

        second_price = runner_up_adrank / denominator
        # Ensure minimum floor price
        return max(round(second_price, 4), DEFAULT_FREE_TIER_BID)

    async def run_auction(
        self,
        eligible_campaigns: List[Dict[str, Any]],
        max_winners: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Run a full auction on a list of eligible campaigns.

        Steps:
          1. Compute EstimatedActionRate for each campaign
          2. Compute AdRank = Bid × EAR × QS
          3. Sort by AdRank descending
          4. Select top N winners
          5. Compute second-price cost for each winner

        Args:
            eligible_campaigns: List of campaign docs (must have _id, bid_amount,
                                quality_score, is_free_tier fields)
            max_winners: Maximum number of winning slots

        Returns:
            List of winner dicts with:
              - campaign: original campaign doc
              - adrank: computed AdRank
              - estimated_action_rate: EAR
              - effective_cost: second-price cost (what vendor actually pays)
        """
        if not eligible_campaigns:
            return []

        # ── Step 1-2: Score all campaigns ──
        scored = []
        for campaign in eligible_campaigns:
            campaign_id = str(campaign.get("_id", ""))
            bid = campaign.get("bid_amount", 0.0)
            quality_score = campaign.get("quality_score", 50)
            is_free_tier = campaign.get("is_free_tier", False)

            # Free tier campaigns get a minimal default bid
            if bid <= 0 or is_free_tier:
                bid = DEFAULT_FREE_TIER_BID

            ear = await self.compute_estimated_action_rate(campaign_id)
            adrank = self.compute_adrank(bid, ear, quality_score)

            if adrank >= MIN_ADRANK_TO_SERVE:
                scored.append({
                    "campaign": campaign,
                    "adrank": adrank,
                    "estimated_action_rate": ear,
                    "bid": bid,
                    "quality_score": quality_score,
                })

        if not scored:
            logger.warning(
                f"Auction: no campaigns met MIN_ADRANK_TO_SERVE={MIN_ADRANK_TO_SERVE}. "
                f"Candidates evaluated: {len(eligible_campaigns)}"
            )
            return []

        # ── Step 3: Sort by AdRank ──
        scored.sort(key=lambda x: x["adrank"], reverse=True)

        # ── Step 4-5: Select winners and compute pricing ──
        winners = []
        for i, entry in enumerate(scored[:max_winners]):
            # Second-price: next bidder's AdRank determines actual cost
            if i + 1 < len(scored):
                runner_up_adrank = scored[i + 1]["adrank"]
            else:
                # No runner-up — pay minimum
                runner_up_adrank = MIN_ADRANK_TO_SERVE

            effective_cost = self.compute_second_price(
                winner_adrank=entry["adrank"],
                runner_up_adrank=runner_up_adrank,
                winner_estimated_action_rate=entry["estimated_action_rate"],
                winner_quality_score=entry["quality_score"],
            )

            winners.append({
                "campaign": entry["campaign"],
                "adrank": entry["adrank"],
                "estimated_action_rate": round(entry["estimated_action_rate"], 4),
                "effective_cost": effective_cost,
                "position": i + 1,
            })

        return winners
