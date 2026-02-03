from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
from typing import List
from datetime import datetime, timezone
from bson import ObjectId
import secrets
import string
from app.services.email_service_resend import ResendEmailService
import os
import logging

router = APIRouter()
email_service = ResendEmailService()


class VendorFormService:
    def __init__(self):
        self.vendor_forms_collection = mongo.db["vendor_forms"]
        self.vendor_submissions_collection = mongo.db["vendor_submissions"]
        self.weddings_collection = mongo.db["weddings"]

    def generate_form_token(self) -> str:
        """Generate a secure token for vendor form access"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    async def create_vendor_form(self, form_data: dict, created_by: str) -> dict:
        """Create a new vendor form"""
        try:
            # Add system fields
            vendor_form = {
                **form_data,
                "access_token": self.generate_form_token(),
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "sent_at": None,
                "submitted_at": None,
                "submission_data": None
            }

            result = await self.vendor_forms_collection.insert_one(vendor_form)
            vendor_form["_id"] = str(result.inserted_id)

            return {"message": "Vendor form created successfully", "form_id": str(result.inserted_id)}
        except Exception as e:
            logging.error(f"Error creating vendor form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create vendor form: {str(e)}")
 
    async def get_vendor_forms_for_planner(self, planner_email: str) -> List[dict]:
        """Get all vendor forms for a specific planner"""
        try:
            # Get planner's weddings
            planner_weddings = await self.weddings_collection.find(
                {"assigned_planner_email": planner_email},
                {"_id": 1}
            ).to_list(length=None)
            wedding_ids = [str(w["_id"]) for w in planner_weddings]
            # Get vendor forms for these weddings
            vendor_forms = await self.vendor_forms_collection.find({
                "wedding_id": {"$in": wedding_ids}
            }).to_list(length=None)

            # Convert ObjectId to string
            for form in vendor_forms:
                form["_id"] = str(form["_id"])

            return vendor_forms
        except Exception as e:
            logging.error(f"Error fetching vendor forms: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch vendor forms: {str(e)}")

    async def get_all_vendor_forms(self) -> List[dict]:
        """Get all vendor forms (ROOT_ADMIN only)"""
        try:
            vendor_forms = await self.vendor_forms_collection.find().to_list(length=None)

            # Convert ObjectId to string
            for form in vendor_forms:
                form["_id"] = str(form["_id"])

            return vendor_forms
        except Exception as e:
            logging.error(f"Error fetching all vendor forms: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch vendor forms: {str(e)}")

    async def send_vendor_form(self, form_id: str, planner_email: str) -> dict:
        """Send vendor form via email"""
        try:
            # Get the form
            form = await self.vendor_forms_collection.find_one({"_id": ObjectId(form_id)})
            if not form:
                raise HTTPException(status_code=404, detail="Vendor form not found")
            # Get wedding details
            wedding = await self.weddings_collection.find_one({"_id": ObjectId(form["wedding_id"])})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")
            # Generate form link
            base_url = os.getenv("FRONTEND_URL", "")  # Update with your frontend URL
            form_link = f"{base_url}/vendor-form/{form_id}?token={form['access_token']}"

            # Prepare email content
            # Prepare email content
            email_subject = f"Wedding Service Request - {wedding['couple_names']}"
            email_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #d97706 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                    .content {{ background: white; padding: 30px; border: 1px solid #e5e7eb; }}
                    .footer {{ background: #f9fafb; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; font-size: 12px; color: #6b7280; }}
                    .button {{ display: inline-block; background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                    .wedding-details {{ background: #f3f4f6; padding: 15px; border-radius: 6px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Wedding Service Request</h1>
                    </div>

                    <div class="content">
                        <p>Dear {form['vendor_name']},</p>

                        <p>We hope this email finds you well. We are reaching out regarding wedding services for one of our couples.</p>

                        <div class="wedding-details">
                            <h3>Wedding Details:</h3>
                            <p><strong>Couple:</strong> {wedding['couple_names']}</p>
                            <p><strong>Wedding Date:</strong> {wedding['date']}</p>
                            <p><strong>Service Required:</strong> {form['vendor_type'].replace('_', ' ').title()}</p>
                            <p><strong>Form:</strong> {form['form_name']}</p>
                        </div>

                        <p>We would love to learn more about your services and get a quote for this special day. Please click the link below to access our vendor information form:</p>

                        <div style="text-align: center;">
                            <a href="{form_link}" class="button">Complete Service Form</a>
                        </div>

                        <p>This form will help us understand:</p>
                        <ul>
                            <li>Your service offerings and packages</li>
                            <li>Availability for the wedding date</li>
                            <li>Pricing and terms</li>
                            <li>Portfolio and experience</li>
                        </ul>

                        <p>The form should take about 5-10 minutes to complete. Once submitted, we'll review your information and get back to you within 24 hours.</p>

                        <p>If you have any questions or need to discuss anything before filling out the form, please don't hesitate to contact us.</p>

                        <p>Thank you for your time and we look forward to potentially working with you!</p>

                        <p>Best regards,<br>
                        Wedding Planning Team<br>
                        <a href="mailto:{planner_email}">{planner_email}</a></p>
                    </div>
                    <div class="footer">
                        <p>This form link is secure and unique to your request. Please do not share it with others.</p>
                        <p>If you're unable to access the form, please contact us directly.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            # Send email
            email_result = await email_service.send_email(
                to_email=form["vendor_email"],
                subject=email_subject,
                html_content=email_html,
                from_name="Wedding Planning Team"
            )
            if email_result.get("success"):
                # Update form status
                await self.vendor_forms_collection.update_one(
                    {"_id": ObjectId(form_id)},
                    {
                        "$set": {
                            "status": "sent",
                            "sent_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                return {"message": "Vendor form sent successfully", "email_sent": True}
            else:
                raise HTTPException(status_code=500, detail="Failed to send email")

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error sending vendor form: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send vendor form: {str(e)}")


vendor_service = VendorFormService()


@router.post("/vendor-forms", tags=["Vendor Management"])
async def create_vendor_form(form_data: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Create a new vendor form"""
    return await vendor_service.create_vendor_form(form_data, current_user.email)


@router.get("/vendor-forms", tags=["Vendor Management"])
async def get_vendor_forms(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get vendor forms - planners see only their forms, ROOT_ADMIN sees all"""
    if current_user.is_root_admin:
        return await vendor_service.get_all_vendor_forms()
    else:
        return await vendor_service.get_vendor_forms_for_planner(current_user.email)


@router.post("/vendor-forms/{form_id}/send", tags=["Vendor Management"])
async def send_vendor_form(form_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Send vendor form via email"""
    return await vendor_service.send_vendor_form(form_id, current_user.email)


@router.get("/vendor-forms/{form_id}", tags=["Vendor Management"])
async def get_vendor_form(form_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get a specific vendor form"""
    try:
        form = await vendor_service.vendor_forms_collection.find_one({"_id": ObjectId(form_id)})
        if not form:
            raise HTTPException(status_code=404, detail="Vendor form not found")
        form["_id"] = str(form["_id"])
        return form
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Public endpoint for vendors to access forms
@router.get("/vendor-form/{form_id}/public", tags=["Public Vendor Form"])
async def get_vendor_form_public(form_id: str, token: str):
    """Get vendor form for public access (no auth required)"""
    try:
        form = await vendor_service.vendor_forms_collection.find_one({
            "_id": ObjectId(form_id),
            "access_token": token
        })

        if not form:
            raise HTTPException(status_code=404, detail="Form not found or invalid token")

        # Get wedding details
        wedding = await vendor_service.weddings_collection.find_one({"_id": ObjectId(form["wedding_id"])})

        # Return form data without sensitive information
        return {
            "_id": str(form["_id"]),
            "form_name": form["form_name"],
            "vendor_name": form["vendor_name"],
            "vendor_type": form["vendor_type"],
            "fields": form["fields"],
            "status": form["status"],
            "wedding": {
                "couple_names": wedding["couple_names"] if wedding else "Unknown",
                "date": wedding["date"] if wedding else "Unknown"
            }
        }
    except Exception as e:
        logging.error(f"Error getting public vendor form: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load form")


@router.post("/vendor-form/{form_id}/submit", tags=["Public Vendor Form"])
async def submit_vendor_form(form_id: str, submission_data: dict, token: str):
    """Submit vendor form (no auth required)"""
    try:
        # Verify form and token
        form = await vendor_service.vendor_forms_collection.find_one({
            "_id": ObjectId(form_id),
            "access_token": token
        })

        if not form:
            raise HTTPException(status_code=404, detail="Form not found or invalid token")

        if form["status"] == "submitted":
            raise HTTPException(status_code=400, detail="Form has already been submitted")

        # Save submission
        submission = {
            "form_id": form_id,
            "vendor_email": form["vendor_email"],
            "vendor_name": form["vendor_name"],
            "wedding_id": form["wedding_id"],
            "submission_data": submission_data,
            "submitted_at": datetime.now(timezone.utc),
            "status": "submitted"
        }

        result = await vendor_service.vendor_submissions_collection.insert_one(submission)

        # Update form status
        await vendor_service.vendor_forms_collection.update_one(
            {"_id": ObjectId(form_id)},
            {
                "$set": {
                    "status": "submitted",
                    "submitted_at": datetime.now(timezone.utc),
                    "submission_data": submission_data,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        # Send notification email to planner
        try:
            wedding = await vendor_service.weddings_collection.find_one({"_id": ObjectId(form["wedding_id"])})
            planner_email = wedding.get("assigned_planner_email") if wedding else form.get("created_by")
            if planner_email:
                notification_subject = f"Vendor Submission Received - {form['vendor_name']}"
                base_url = os.getenv("FRONTEND_URL", "").rstrip("/")
                dashboard_url = f"{base_url}/admin/vendors"

                notification_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #1e3a8a;">New Vendor Submission Received</h2>

                        <p>A vendor has completed and submitted their information form.</p>

                        <div style="background: #f3f4f6; padding: 15px; border-radius: 6px; margin: 20px 0;">
                            <h3>Submission Details:</h3>
                            <p><strong>Vendor:</strong> {form['vendor_name']}</p>
                            <p><strong>Email:</strong> {form['vendor_email']}</p>
                            <p><strong>Service Type:</strong> {form['vendor_type'].replace('_', ' ').title()}</p>
                            <p><strong>Wedding:</strong> {wedding['couple_names'] if wedding else 'Unknown'}</p>
                            <p><strong>Form:</strong> {form['form_name']}</p>
                            <p><strong>Submitted:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                        </div>

                        <p>Please log in to your dashboard to review the vendor's submission and take appropriate action.</p>

                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{dashboard_url}"
                               style="display: inline-block; background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                               View Vendor Submissions
                            </a>
                        </div>
                    </div>
                </body>
                </html>
                """
                await email_service.send_email(
                    to_email=planner_email,
                    subject=notification_subject,
                    html_content=notification_html,
                    from_name="Wedding Platform"
                )

                # Send push notification to planner
                try:
                    from app.services.planner_notification_service import planner_notification_service
                    await planner_notification_service.notify_vendor_response(
                        planner_id=planner_email,
                        wedding_id=form["wedding_id"],
                        vendor_name=form["vendor_name"],
                        response_type=f"submitted {form['form_name']}",
                        vendor_id=str(result.inserted_id)
                    )
                except Exception as push_error:
                    logging.warning(f"Failed to send push notification: {str(push_error)}")
                    # Continue even if push notification fails

        except Exception as e:
            logging.error(f"Failed to send notification email: {str(e)}")
            # Continue even if notification fails

        return {"message": "Form submitted successfully", "submission_id": str(result.inserted_id)}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error submitting vendor form: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit form")