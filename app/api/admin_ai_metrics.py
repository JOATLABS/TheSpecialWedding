from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database import mongo
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/ai/metrics", response_model=Dict[str, Any])
async def get_ai_metrics(
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Returns AI usage metrics for the Root Admin Dashboard.
    """
    # 1. Total Credits Used Today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Aggregation for today's usage
    pipeline_today = [
        {"$match": {"timestamp": {"$gte": today_start}}},
        {"$group": {"_id": None, "total_credits": {"$sum": "$credits_cost"}}}
    ]
    today_result = await mongo.db.ai_usage_logs.aggregate(pipeline_today).to_list(1)
    credits_used_today = today_result[0]["total_credits"] if today_result else 0

    # 2. Usage per Tenant (Top 10)
    pipeline_tenants = [
        {"$group": {"_id": "$tenant_id", "total_credits": {"$sum": "$credits_cost"}}},
        {"$sort": {"total_credits": -1}},
        {"$limit": 10}
    ]
    top_tenants_raw = await mongo.db.ai_usage_logs.aggregate(pipeline_tenants).to_list(10)

    # Enrich with Wedding Names
    top_tenants = []
    for t in top_tenants_raw:
        wedding = await mongo.db.weddings.find_one({"_id": t["_id"]}, {"couple_names": 1})
        top_tenants.append({
            "tenant_id": t["_id"],
            "name": wedding["couple_names"] if wedding else "Unknown",
            "credits": t["total_credits"]
        })

    # 3. Most Used Feature
    pipeline_features = [
        {"$group": {"_id": "$feature", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    feature_stats = await mongo.db.ai_usage_logs.aggregate(pipeline_features).to_list(10)

    return {
        "credits_used_today": credits_used_today,
        "top_tenants": top_tenants,
        "feature_usage": feature_stats
    }
