from fastapi import APIRouter, HTTPException, Depends
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.core.database import mongo
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

router = APIRouter()

@router.get("/planner/metrics", tags=["Wedding Planner"])
async def get_planner_metrics(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
    """Get comprehensive metrics for wedding planner dashboard"""

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        # Get planner's assigned weddings
        weddings_collection = mongo.get_weddings_collection()
        weddings = list(weddings_collection.find({
            "assigned_planner_email": current_user.email,
            "status": {"$ne": "cancelled"}
        }))
        metrics = {
            "summary": {
                "total_weddings": len(weddings),
                "active_weddings": len([w for w in weddings if w.get("status", "active") == "active"]),
                "upcoming_weddings": 0,
                "total_guests": 0,
                "confirmed_rsvps": 0,
                "pending_rsvps": 0,
                "declined_rsvps": 0
            },
            "weddings": [],
            "recent_activity": [],
            "revenue_metrics": {
                "monthly_bookings": 0,
                "total_revenue": 0,
                "average_wedding_value": 0
            }
        }
        # Calculate upcoming weddings
        current_date = datetime.now()
        for wedding in weddings:
            try:
                wedding_date = datetime.fromisoformat(wedding["date"])
                if wedding_date > current_date:
                    metrics["summary"]["upcoming_weddings"] += 1
            except:
                pass

        # Get detailed metrics for each wedding
        guests_collection = mongo.get_guest_collection()
        rsvps_collection = mongo.get_rsvps_collection()

        for wedding in weddings:
            wedding_id = wedding["_id"]

            # Get guest count
            guest_count = await guests_collection.count_documents({"wedding_id": wedding_id})
            metrics["summary"]["total_guests"] += guest_count

            # Get RSVP statistics
            rsvps = list(rsvps_collection.find({"wedding_id": wedding_id}))

            confirmed = 0
            declined = 0
            pending = guest_count - len(rsvps)  # Guests who haven't RSVPed yet

            for rsvp in rsvps:
                attending = rsvp.get("attending", {})
                if attending and any(attending.values()):
                    confirmed += 1
                elif attending and all(not val for val in attending.values()):
                    declined += 1
                else:
                    pending += 1

            metrics["summary"]["confirmed_rsvps"] += confirmed
            metrics["summary"]["declined_rsvps"] += declined
            metrics["summary"]["pending_rsvps"] += pending

            # Calculate progress percentage
            progress_score = 0
            if guest_count > 0:
                progress_score += min(40, (len(rsvps) / guest_count) * 40)  # 40% for RSVPs
            # Additional progress factors
            if wedding.get("events"):
                progress_score += 20  # 20% for having events configured
            if guest_count > 0:
                progress_score += 20  # 20% for having guests
            if wedding.get("details"):
                progress_score += 20  # 20% for wedding details
            # Calculate days until wedding
            days_until_wedding = 0
            try:
                wedding_date = datetime.fromisoformat(wedding["date"])
                days_until_wedding = (wedding_date - current_date).days
            except:
                pass
            wedding_metrics = {
                "id": str(wedding_id),
                "couple_names": wedding.get("couple_names", ""),
                "date": wedding.get("date", ""),
                "slug": wedding.get("slug", ""),
                "status": wedding.get("status", "active"),
                "guest_count": guest_count,
                "rsvp_stats": {
                    "confirmed": confirmed,
                    "declined": declined,
                    "pending": pending,
                    "response_rate": round((len(rsvps) / guest_count * 100) if guest_count > 0 else 0, 1)
                },
                "progress_percentage": min(100, round(progress_score)),
                "days_until_wedding": days_until_wedding,
                "created_at": wedding.get("created_at").isoformat() if isinstance(wedding.get("created_at"), datetime) else wedding.get("created_at", "")
            }

            metrics["weddings"].append(wedding_metrics)

        # Sort weddings by date
        metrics["weddings"].sort(key=lambda x: x["date"])

        # Generate recent activity (placeholder - would integrate with actual activity log)
        metrics["recent_activity"] = [
            {
                "type": "rsvp_received",
                "message": "New RSVP received",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "wedding_id": metrics["weddings"][0]["id"] if metrics["weddings"] else None
            },
            {
                "type": "guest_updated",
                "message": "Guest list updated",
                "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
                "wedding_id": metrics["weddings"][0]["id"] if metrics["weddings"] else None
            },
            {
                "type": "email_sent",
                "message": "Reminder emails sent",
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "wedding_id": metrics["weddings"][1]["id"] if len(metrics["weddings"]) > 1 else None
            }
        ]

        # Calculate revenue metrics (placeholder - would integrate with subscription data)
        if metrics["weddings"]:
            metrics["revenue_metrics"]["monthly_bookings"] = len([
                w for w in metrics["weddings"]
                if w["created_at"] and (
                    isinstance(w["created_at"], datetime) and w["created_at"].month == current_date.month
                    or isinstance(w["created_at"], str) and datetime.fromisoformat(w["created_at"]).month == current_date.month
                )
            ])
            metrics["revenue_metrics"]["total_revenue"] = len(metrics["weddings"]) * 500  # Placeholder
            metrics["revenue_metrics"]["average_wedding_value"] = 500  # Placeholder

        return metrics

    except Exception as e:
        logging.error(f"Error fetching planner metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch planner metrics: {str(e)}")

@router.get("/planner/activity-log", tags=["Wedding Planner"])
def get_activity_log(current_user: ExtendedAuthUser = Depends(get_current_user_extended), limit: int = 50):
    """Get detailed activity log for wedding planner"""

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        # This would typically fetch from an activity log collection
        # For now, return placeholder data
        activities = [
            {
                "id": "activity_1",
                "type": "rsvp_received",
                "message": "New RSVP received from John Smith",
                "wedding_id": "wedding_123",
                "wedding_name": "Emmanuel & Peace",
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "metadata": {"guest_name": "John Smith", "response": "attending"}
            },
            {
                "id": "activity_2",
                "type": "guest_added",
                "message": "5 new guests added to guest list",
                "wedding_id": "wedding_123",
                "wedding_name": "Emmanuel & Peace",
                "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                "metadata": {"count": 5}
            },
            {
                "id": "activity_3",
                "type": "email_sent",
                "message": "Invitation emails sent to 25 guests",
                "wedding_id": "wedding_123",
                "wedding_name": "Emmanuel & Peace",
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "metadata": {"email_count": 25, "email_type": "invitation"}
            }
        ]

        return {"activities": activities[:limit], "total": len(activities)}

    except Exception as e:
        logging.error(f"Error fetching activity log: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch activity log: {str(e)}")

@router.get("/planner/weddings", tags=["Wedding Planner"])
def get_planner_weddings(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
    """Get all weddings assigned to the current planner"""

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        weddings_collection = mongo.get_weddings_collection()

        # Query for planner's assigned weddings
        query = {"assigned_planner_email": current_user.email}
        if current_user.is_root_admin:
            # ROOT_ADMIN can see all weddings, but this endpoint is for planner view
            query = {"assigned_planner_email": current_user.email}

        weddings = list(weddings_collection.find(query))

        # Convert ObjectId to string and format response
        wedding_list = []
        for wedding in weddings:
            wedding_data = {
                "id": str(wedding["_id"]),
                "_id": str(wedding["_id"]),
                "couple_names": wedding.get("couple_names", ""),
                "date": wedding.get("date", ""),
                "slug": wedding.get("slug", ""),
                "assigned_planner_email": wedding.get("assigned_planner_email"),
                "assigned_planner_id": wedding.get("assigned_planner_id"),
                "status": wedding.get("status", "active"),
                "venue": wedding.get("venue"),
                "guest_count": wedding.get("guest_count", 0),
                "created_at": wedding.get("created_at"),
                "events": wedding.get("events", [])
            }
            wedding_list.append(wedding_data)

        # Sort by date
        wedding_list.sort(key=lambda x: x["date"])

        return wedding_list

    except Exception as e:
        logging.error(f"Error fetching planner weddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch weddings: {str(e)}")