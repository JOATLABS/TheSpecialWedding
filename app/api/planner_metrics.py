from fastapi import APIRouter, HTTPException, Depends
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.core.database import mongo
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

router = APIRouter()

@router.get("/planner/metrics", tags=["Wedding Planner"])
def get_planner_metrics(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
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
            except Exception:
                pass
        
        # Get detailed metrics for each wedding
        guests_collection = mongo.get_guest_collection()
        rsvps_collection = mongo.get_rsvps_collection()

        # Optimized: Get all wedding IDs for batch operations
        wedding_ids = [wedding["_id"] for wedding in weddings]

        # Single aggregation pipeline to get guest counts for all weddings
        guest_count_pipeline = [
            {"$match": {"wedding_id": {"$in": wedding_ids}}},
            {"$group": {
                "_id": "$wedding_id",
                "count": {"$sum": 1}
            }}
        ]
        guest_counts = {doc["_id"]: doc["count"]
                       for doc in guests_collection.aggregate(guest_count_pipeline)}

        # Single aggregation pipeline to get RSVP statistics for all weddings
        rsvp_pipeline = [
            {"$match": {"wedding_id": {"$in": wedding_ids}}},
            {"$group": {
                "_id": "$wedding_id",
                "rsvps": {"$push": "$attending"}
            }}
        ]
        wedding_rsvps = {doc["_id"]: doc["rsvps"]
                        for doc in rsvps_collection.aggregate(rsvp_pipeline)}

        # Process metrics for each wedding using pre-fetched data
        for wedding in weddings:
            wedding_id = wedding["_id"]

            # Get guest count from pre-fetched data
            guest_count = guest_counts.get(wedding_id, 0)
            metrics["summary"]["total_guests"] += guest_count

            # Get RSVP statistics from pre-fetched data
            rsvps = wedding_rsvps.get(wedding_id, [])

            confirmed = 0
            declined = 0
            pending = guest_count - len(rsvps)  # Guests who haven't RSVPed yet

            for attending in rsvps:
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
            except Exception:
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
        
        # Get real recent activity from audit logs and database changes
        recent_activities = []

        try:
            # Get wedding IDs for this planner
            wedding_ids = [ObjectId(w["id"]) for w in metrics["weddings"]]

            if wedding_ids:
                # Get recent RSVP activities
                recent_rsvps = list(rsvps_collection.find({
                    "wedding_id": {"$in": wedding_ids},
                    "created_at": {"$gte": datetime.now() - timedelta(days=7)}
                }).sort("created_at", -1).limit(5))

                for rsvp in recent_rsvps:
                    wedding = next((w for w in weddings if ObjectId(w["_id"]) == rsvp["wedding_id"]), None)
                    if wedding:
                        recent_activities.append({
                            "type": "rsvp_received",
                            "message": f"New RSVP received from {rsvp.get('guest_name', 'Guest')}",
                            "timestamp": rsvp.get("created_at", datetime.now()).isoformat(),
                            "wedding_id": str(rsvp["wedding_id"])
                        })

                # Get recent guest additions
                recent_guests = list(guests_collection.find({
                    "wedding_id": {"$in": wedding_ids},
                    "created_at": {"$gte": datetime.now() - timedelta(days=7)}
                }).sort("created_at", -1).limit(3))

                for guest in recent_guests:
                    wedding = next((w for w in weddings if ObjectId(w["_id"]) == guest["wedding_id"]), None)
                    if wedding:
                        recent_activities.append({
                            "type": "guest_added",
                            "message": f"New guest added: {guest.get('name', 'Unknown')}",
                            "timestamp": guest.get("created_at", datetime.now()).isoformat(),
                            "wedding_id": str(guest["wedding_id"])
                        })

                # Get audit log activities if available
                try:
                    audit_collection = mongo.db["security_audit_logs"]
                    recent_audits = list(audit_collection.find({
                        "wedding_id": {"$in": [str(wid) for wid in wedding_ids]},
                        "timestamp": {"$gte": datetime.now() - timedelta(days=7)},
                        "event_type": {"$in": ["FORM_SUBMISSION", "DATA_EXPORT", "BULK_OPERATION"]}
                    }).sort("timestamp", -1).limit(3))

                    for audit in recent_audits:
                        wedding = next((w for w in weddings if str(w["_id"]) == audit.get("wedding_id")), None)
                        if wedding:
                            recent_activities.append({
                                "type": "system_activity",
                                "message": f"System activity: {audit.get('action', 'Unknown action')}",
                                "timestamp": audit.get("timestamp", datetime.now()).isoformat(),
                                "wedding_id": audit.get("wedding_id")
                            })
                except Exception:
                    # Audit collection may not exist yet
                    pass

                # Sort all activities by timestamp (most recent first)
                recent_activities.sort(key=lambda x: x["timestamp"], reverse=True)

                # Limit to 3 most recent for dashboard
                metrics["recent_activity"] = recent_activities[:3]
            else:
                metrics["recent_activity"] = []

        except Exception as e:
            logging.warning(f"Failed to fetch real activity data: {str(e)}")
            # Fallback to empty list if there's an error
            metrics["recent_activity"] = []
        
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
        # Get planner's assigned weddings first
        weddings_collection = mongo.get_weddings_collection()
        weddings = list(weddings_collection.find({
            "assigned_planner_email": current_user.email,
            "status": {"$ne": "cancelled"}
        }))

        activities = []

        if weddings:
            wedding_ids = [w["_id"] for w in weddings]
            wedding_lookup = {str(w["_id"]): w for w in weddings}

            # Collections to query
            guests_collection = mongo.get_guest_collection()
            rsvps_collection = mongo.get_rsvps_collection()

            # Get recent RSVP activities (last 30 days)
            recent_rsvps = list(rsvps_collection.find({
                "wedding_id": {"$in": wedding_ids},
                "created_at": {"$gte": datetime.now() - timedelta(days=30)}
            }).sort("created_at", -1).limit(limit // 2))

            for rsvp in recent_rsvps:
                wedding = wedding_lookup.get(str(rsvp["wedding_id"]))
                if wedding:
                    activities.append({
                        "id": f"rsvp_{str(rsvp['_id'])}",
                        "type": "rsvp_received",
                        "message": f"New RSVP received from {rsvp.get('guest_name', 'Guest')}",
                        "wedding_id": str(rsvp["wedding_id"]),
                        "wedding_name": wedding.get("couple_names", "Unknown Wedding"),
                        "timestamp": rsvp.get("created_at", datetime.now()).isoformat(),
                        "metadata": {
                            "guest_name": rsvp.get("guest_name", "Guest"),
                            "response": "attending" if rsvp.get("attending") else "declined"
                        }
                    })

            # Get recent guest additions (last 30 days)
            recent_guests = list(guests_collection.find({
                "wedding_id": {"$in": wedding_ids},
                "created_at": {"$gte": datetime.now() - timedelta(days=30)}
            }).sort("created_at", -1).limit(limit // 2))

            for guest in recent_guests:
                wedding = wedding_lookup.get(str(guest["wedding_id"]))
                if wedding:
                    activities.append({
                        "id": f"guest_{str(guest['_id'])}",
                        "type": "guest_added",
                        "message": f"New guest added: {guest.get('name', 'Unknown')}",
                        "wedding_id": str(guest["wedding_id"]),
                        "wedding_name": wedding.get("couple_names", "Unknown Wedding"),
                        "timestamp": guest.get("created_at", datetime.now()).isoformat(),
                        "metadata": {
                            "guest_name": guest.get("name", "Unknown"),
                            "email": guest.get("email", ""),
                            "phone": guest.get("phone", "")
                        }
                    })

            # Get audit log activities if available
            try:
                audit_collection = mongo.db["security_audit_logs"]
                recent_audits = list(audit_collection.find({
                    "wedding_id": {"$in": [str(wid) for wid in wedding_ids]},
                    "timestamp": {"$gte": datetime.now() - timedelta(days=30)},
                    "event_type": {"$in": ["FORM_SUBMISSION", "DATA_EXPORT", "BULK_OPERATION", "FORM_ACCESS"]}
                }).sort("timestamp", -1).limit(limit // 3))

                for audit in recent_audits:
                    wedding = wedding_lookup.get(audit.get("wedding_id"))
                    if wedding:
                        activities.append({
                            "id": f"audit_{str(audit['_id'])}",
                            "type": "system_activity",
                            "message": f"System activity: {audit.get('action', 'Unknown action')}",
                            "wedding_id": audit.get("wedding_id"),
                            "wedding_name": wedding.get("couple_names", "Unknown Wedding"),
                            "timestamp": audit.get("timestamp", datetime.now()).isoformat(),
                            "metadata": {
                                "event_type": audit.get("event_type"),
                                "details": audit.get("details", {})
                            }
                        })
            except Exception:
                # Audit collection may not exist yet
                pass

            # Sort all activities by timestamp (most recent first)
            activities.sort(key=lambda x: x["timestamp"], reverse=True)

            # Apply limit
            activities = activities[:limit]

        return {"activities": activities, "total": len(activities)}

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