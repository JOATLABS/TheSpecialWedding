from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from app.core.database import mongo
from app.utils.pydantic_objectid import PyObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ContactFormSubmission(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    message: str = Field(..., min_length=1, max_length=2000)
    planningExperience: Optional[str] = Field(None)
    interestedServices: List[str] = Field(default_factory=list)
    source: Optional[str] = Field(default="saas_landing_page")
    timestamp: Optional[str] = Field(None)

    @validator('email')
    def validate_email(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower()

@router.post("/contact-form-submission", tags=["Public"])
async def submit_contact_form(submission: ContactFormSubmission):
    """Submit contact form from SAAS landing page - No auth required"""
    try:
        # Create submission document
        submission_doc = {
            "name": submission.name,
            "email": submission.email,
            "company": submission.company,
            "phone": submission.phone,
            "message": submission.message,
            "planning_experience": submission.planningExperience,
            "interested_services": submission.interestedServices,
            "source": submission.source,
            "status": "new",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_read": False,
            "notes": []
        }

        # Save to database
        result = mongo.db["contact_submissions"].insert_one(submission_doc)

        # Create notification for admin
        notification_doc = {
            "title": f"New Contact Form Submission from {submission.name}",
            "message": f"A new contact form has been submitted by {submission.name} ({submission.email}) from {submission.company or 'an unnamed company'}. Message: {submission.message[:200]}{'...' if len(submission.message) > 200 else ''}",
            "type": "info",
            "target_audience": "root_admin",
            "priority": "medium",
            "source": "contact_form",
            "submission_id": str(result.inserted_id),
            "status": "active",
            "is_dismissible": True,
            "created_at": datetime.utcnow(),
            "read_by": [],
            "dismissed_by": []
        }

        mongo.db["notifications"].insert_one(notification_doc)

        # Log the submission
        logger.info(f"Contact form submission received from {submission.email} ({submission.name})")

        return {
            "success": True,
            "message": "Thank you for your inquiry! We'll get back to you within 24 hours.",
            "submission_id": str(result.inserted_id)
        }

    except Exception as e:
        logger.error(f"Error processing contact form submission: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing your submission. Please try again.")

@router.get("/contact-submissions", tags=["ROOT_ADMIN"])
async def get_contact_submissions(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    unread_only: bool = False
):
    """Get contact form submissions - ROOT_ADMIN only (implement auth later)"""
    try:
        # Build query
        query = {}
        if status:
            query["status"] = status
        if unread_only:
            query["is_read"] = False

        # Calculate skip
        skip = (page - 1) * limit

        # Get submissions
        submissions = list(mongo.db["contact_submissions"].find(query)
                          .sort("created_at", -1)
                          .skip(skip)
                          .limit(limit))

        # Convert ObjectId to string
        for submission in submissions:
            submission["_id"] = str(submission["_id"])
            if submission.get("created_at"):
                submission["created_at"] = submission["created_at"].isoformat()
            if submission.get("updated_at"):
                submission["updated_at"] = submission["updated_at"].isoformat()

        # Get total count
        total = mongo.db["contact_submissions"].count_documents(query)

        return {
            "submissions": submissions,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    except Exception as e:
        logger.error(f"Error fetching contact submissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching contact submissions")

@router.put("/contact-submissions/{submission_id}/status", tags=["ROOT_ADMIN"])
async def update_submission_status(
    submission_id: str,
    status: str,
    notes: Optional[str] = None
):
    """Update contact submission status - ROOT_ADMIN only (implement auth later)"""
    try:
        valid_statuses = ["new", "in_progress", "responded", "closed"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(valid_statuses)}")

        update_doc = {
            "status": status,
            "updated_at": datetime.utcnow(),
            "is_read": True
        }

        if notes:
            # Add note to notes array
            note = {
                "content": notes,
                "created_at": datetime.utcnow(),
                "created_by": "admin"  # TODO: Get from auth
            }
            update_doc["$push"] = {"notes": note}

        result = mongo.db["contact_submissions"].update_one(
            {"_id": PyObjectId(submission_id)},
            {"$set": update_doc} if not notes else {"$set": {k: v for k, v in update_doc.items() if k != "$push"}, "$push": update_doc["$push"]}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Submission not found")

        return {"success": True, "message": "Submission status updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating submission status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating submission status")