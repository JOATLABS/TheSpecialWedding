"""
Vendor Signup & Onboarding Service

Handles public vendor self-signup, admin approval workflow, temp password
generation, and profile completeness checking.

Reuses existing infrastructure:
  - generate_invitation_token() pattern from UserManagementService
  - get_password_hash() from auth_utils
  - ResendEmailService.send_email() for transactional emails
  - NotificationService.create_notification() for admin alerts
  - Vendor doc schema from bulk_create_vendor_accounts()

Phase 10 of the Vendor Advertising Monetization Platform.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.core.settings import settings as app_settings
from app.services.ad_upload_service import AdUploadService, VendorMediaAssetKind
from app.services.ad_platform_config_service import AdPlatformConfigService
from app.services.email_service_resend import ResendEmailService
from app.services.notification_service import NotificationService
from app.utils.auth_utils import get_password_hash

logger = logging.getLogger(__name__)

# Resolve the portal URL from settings, with a sensible fallback
_PORTAL_URL = (
    f"{app_settings.frontend_url}/portal/ads"
    if app_settings.frontend_url
    else "https://thespecialwedding.com/portal/ads"
)


# ─── Profile Completeness ─────────────────────────────────────────────

REQUIRED_PROFILE_FIELDS = [
    "business_name",
    "email",
    "vendor_category",
    "vendor_location",
]


def check_profile_completeness(vendor_doc: dict) -> Dict[str, Any]:
    """
    Evaluate how complete a vendor's profile is.

    Returns:
        {
            "is_complete": bool,
            "missing_fields": ["vendor_category", ...],
            "completion_percentage": int (0-100),
            "total_fields": int,
            "completed_fields": int,
        }
    """
    completed = []
    missing = []

    for field in REQUIRED_PROFILE_FIELDS:
        value = vendor_doc.get(field, "")
        if value and str(value).strip():
            completed.append(field)
        else:
            missing.append(field)

    # Optional bonus fields (count toward percentage but don't block)
    bonus_fields = ["vendor_phone", "vendor_website", "vendor_description", "logo_url"]
    for field in bonus_fields:
        value = vendor_doc.get(field, "")
        if value and str(value).strip():
            completed.append(field)

    total = len(REQUIRED_PROFILE_FIELDS) + len(bonus_fields)
    pct = int((len(completed) / total) * 100) if total > 0 else 0

    return {
        "is_complete": len(missing) == 0,
        "missing_fields": missing,
        "completion_percentage": pct,
        "total_fields": total,
        "completed_fields": len(completed),
    }


# ─── Service Class ─────────────────────────────────────────────────────


class VendorSignupService:
    """Manages the full vendor signup → approval → onboarding lifecycle."""

    def __init__(self, db=None):
        self.db = db if db is not None else mongo.db
        self.users = self.db["users"]
        self.email_service = ResendEmailService()
        self.notification_service = NotificationService()
        self.config_service = AdPlatformConfigService(self.db)

    # ─── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _generate_temp_password(length: int = 14) -> str:
        """
        Generate a cryptographically random temporary password.

        Guarantees at least 1 uppercase, 1 lowercase, 1 digit, 1 special char
        to pass the existing password validation rules.
        """
        special = "!@#$%^&*_+-="
        # Ensure minimum requirements
        password_chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(special),
        ]
        # Fill remaining with random chars from all categories
        all_chars = string.ascii_letters + string.digits + special
        password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]
        # Shuffle to avoid predictable positions
        result = list(password_chars)
        secrets.SystemRandom().shuffle(result)
        return "".join(result)

    @staticmethod
    def _serialize(doc: dict) -> dict:
        """Convert ObjectId fields to strings for JSON serialization."""
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ─── Public Signup ─────────────────────────────────────────────

    async def signup(self, signup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public vendor self-signup.

        Creates a vendor account with status pending_approval (or auto-approves
        if the platform config flag auto_approve_signups is True).

        Args:
            signup_data: {
                email: str (required),
                business_name: str (required),
                category: str (optional),
                location: str (optional),
                phone: str (optional),
                website: str (optional),
            }

        Returns:
            { status, message, vendor_id }
        """
        email = signup_data.get("email", "").strip().lower()
        business_name = signup_data.get("business_name", "").strip()

        if not email or not business_name:
            raise HTTPException(
                status_code=400,
                detail="Email and business name are required.",
            )

        # Prevent duplicate signups
        existing = await self.users.find_one({"email": email})
        if existing:
            # Don't reveal whether email exists (email enumeration prevention)
            logger.info(f"Vendor signup attempt with existing email: {email}")
            return {
                "status": "pending_approval",
                "message": (
                    "Thank you! If this email is not already registered, "
                    "you will receive a confirmation shortly."
                ),
            }

        now = datetime.now(timezone.utc)
        vendor_doc = {
            "email": email,
            "business_name": business_name,
            "role": "advertising_vendor",
            "vendor_account_status": "pending_approval",
            "vendor_category": signup_data.get("category", ""),
            "vendor_location": signup_data.get("location", ""),
            "vendor_phone": signup_data.get("phone", ""),
            "vendor_website": signup_data.get("website", ""),
            "vendor_description": "",
            "logo_url": "",
            "portfolio_urls": [],
            "is_free_tier": False,
            "is_active": False,  # Not active until approved + password set
            "must_change_password": False,
            "password_hash": None,  # No password until approval
            "registration_source": "vendor_self_signup",
            "created_at": now,
            "updated_at": now,
            # Metrics (same schema as bulk_create_vendor_accounts)
            "total_campaigns": 0,
            "total_impressions": 0,
            "total_clicks": 0,
            "total_leads": 0,
        }

        # Check platform config for auto-approve
        config = await self.config_service.get_config()
        auto_approve = config.get("auto_approve_signups", False)

        result = await self.users.insert_one(vendor_doc)
        vendor_id = str(result.inserted_id)
        logger.info(f"Vendor signup created: {email} (id={vendor_id})")

        if auto_approve:
            # Auto-approve: generate temp password immediately
            await self._approve_vendor(
                vendor_id, email, admin_email="system_auto_approve"
            )
            return {
                "status": "approved",
                "message": (
                    "Your account has been approved! Check your email for "
                    "your temporary password."
                ),
                "vendor_id": vendor_id,
            }

        # Manual approval path: notify admin + send confirmation to vendor
        await self._notify_admin_new_signup(email, business_name, vendor_id)
        await self._send_signup_confirmation_email(email, business_name)

        return {
            "status": "pending_approval",
            "message": (
                "Thank you! Your vendor account is pending approval. "
                "You'll receive an email once your account is reviewed."
            ),
            "vendor_id": vendor_id,
        }

    # ─── Admin Approval Workflow ───────────────────────────────────

    async def approve_vendor(self, vendor_id: str, admin_email: str) -> Dict[str, Any]:
        """
        Admin approves a pending vendor.

        Sets status to active, generates a temp password, and emails the vendor.
        """
        vendor = await self.users.find_one({"_id": ObjectId(vendor_id)})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if vendor.get("role") != "advertising_vendor":
            raise HTTPException(
                status_code=400, detail="User is not an advertising vendor"
            )
        if vendor.get("vendor_account_status") == "active":
            raise HTTPException(status_code=400, detail="Vendor is already active")

        return await self._approve_vendor(vendor_id, vendor["email"], admin_email)

    async def _approve_vendor(
        self, vendor_id: str, vendor_email: str, admin_email: str
    ) -> Dict[str, Any]:
        """Internal approval logic shared by manual and auto-approve paths."""
        temp_password = self._generate_temp_password()
        password_hash = get_password_hash(temp_password)
        now = datetime.now(timezone.utc)

        await self.users.update_one(
            {"_id": ObjectId(vendor_id)},
            {
                "$set": {
                    "vendor_account_status": "active",
                    "password_hash": password_hash,
                    "must_change_password": True,
                    "temp_password_expires_at": now + timedelta(hours=72),
                    "is_active": True,
                    "approved_at": now,
                    "approved_by": admin_email,
                    "updated_at": now,
                }
            },
        )

        # Send temp password email
        await self._send_approval_email(vendor_email, temp_password)

        logger.info(f"Vendor {vendor_id} ({vendor_email}) approved by {admin_email}")
        return {
            "vendor_id": vendor_id,
            "email": vendor_email,
            "status": "active",
            "message": "Vendor approved. Temporary password emailed.",
        }

    async def suspend_vendor(
        self, vendor_id: str, admin_email: str, reason: str = ""
    ) -> Dict[str, Any]:
        """
        Admin suspends an active vendor. Pauses all their active campaigns.
        """
        vendor = await self.users.find_one({"_id": ObjectId(vendor_id)})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if vendor.get("role") != "advertising_vendor":
            raise HTTPException(
                status_code=400, detail="User is not an advertising vendor"
            )
        if vendor.get("vendor_account_status") == "suspended":
            raise HTTPException(status_code=400, detail="Vendor is already suspended")

        now = datetime.now(timezone.utc)
        await self.users.update_one(
            {"_id": ObjectId(vendor_id)},
            {
                "$set": {
                    "vendor_account_status": "suspended",
                    "is_active": False,
                    "suspended_at": now,
                    "suspended_by": admin_email,
                    "suspension_reason": reason,
                    "updated_at": now,
                }
            },
        )

        # Pause all active campaigns for this vendor
        campaigns_result = await self.db["ad_campaigns"].update_many(
            {"vendor_id": vendor_id, "status": "active"},
            {
                "$set": {
                    "status": "paused",
                    "paused_reason": "vendor_suspended",
                    "updated_at": now,
                }
            },
        )

        logger.info(
            f"Vendor {vendor_id} suspended by {admin_email}. "
            f"Reason: {reason}. Campaigns paused: {campaigns_result.modified_count}"
        )

        # Notify vendor (in-portal + email + push)
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_suspended(vendor["email"], reason)
        except Exception as e:
            logger.warning(f"Failed to notify vendor on suspension: {e}")

        return {
            "vendor_id": vendor_id,
            "status": "suspended",
            "campaigns_paused": campaigns_result.modified_count,
            "message": "Vendor suspended and active campaigns paused.",
        }

    async def reactivate_vendor(
        self, vendor_id: str, admin_email: str
    ) -> Dict[str, Any]:
        """Reactivate a suspended vendor."""
        vendor = await self.users.find_one({"_id": ObjectId(vendor_id)})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if vendor.get("vendor_account_status") != "suspended":
            raise HTTPException(
                status_code=400, detail="Vendor is not currently suspended"
            )

        now = datetime.now(timezone.utc)
        await self.users.update_one(
            {"_id": ObjectId(vendor_id)},
            {
                "$set": {
                    "vendor_account_status": "active",
                    "is_active": True,
                    "reactivated_at": now,
                    "reactivated_by": admin_email,
                    "updated_at": now,
                },
                "$unset": {
                    "suspension_reason": "",
                },
            },
        )

        logger.info(f"Vendor {vendor_id} reactivated by {admin_email}")

        # Notify vendor (in-portal + email + push)
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_reactivated(vendor["email"])
        except Exception as e:
            logger.warning(f"Failed to notify vendor on reactivation: {e}")

        return {
            "vendor_id": vendor_id,
            "status": "active",
            "message": "Vendor reactivated. Campaigns remain paused — vendor must resume them manually.",
        }

    # ─── Password Change (First Login) ────────────────────────────

    async def change_temp_password(
        self, vendor_email: str, temp_password: str, new_password: str
    ) -> Dict[str, Any]:
        """
        Vendor changes their temp password on first login.

        Unlike the existing change_password() in UserManagementService, this
        also clears the must_change_password flag and checks temp expiry.
        """
        from app.utils.auth_utils import verify_password

        vendor = await self.users.find_one({"email": vendor_email})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        # Verify temp password
        if not vendor.get("password_hash"):
            raise HTTPException(
                status_code=400, detail="No password set for this account"
            )

        if not verify_password(temp_password, vendor["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        # Check if temp password has expired (72-hour window)
        expires_at = vendor.get("temp_password_expires_at")
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="Temporary password has expired. Please contact support.",
            )

        # Hash new password and clear temp flags
        new_hash = get_password_hash(new_password)
        now = datetime.now(timezone.utc)

        await self.users.update_one(
            {"_id": vendor["_id"]},
            {
                "$set": {
                    "password_hash": new_hash,
                    "must_change_password": False,
                    "password_changed_at": now,
                    "updated_at": now,
                },
                "$unset": {
                    "temp_password_expires_at": "",
                },
            },
        )

        logger.info(f"Vendor {vendor_email} changed temp password successfully")
        return {
            "message": "Password changed successfully. You can now access the portal.",
            "changed_at": now.isoformat(),
        }

    # ─── Profile Update ───────────────────────────────────────────

    async def update_vendor_profile(
        self, vendor_email: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update vendor profile fields.

        Allowed fields: business_name, vendor_category, vendor_location,
        vendor_phone, vendor_website, vendor_description, logo_url, portfolio_urls.
        """
        ALLOWED_FIELDS = {
            "business_name",
            "vendor_category",
            "vendor_location",
            "vendor_phone",
            "vendor_website",
            "vendor_description",
            "logo_url",
            "portfolio_urls",
        }

        filtered = {k: v for k, v in updates.items() if k in ALLOWED_FIELDS}
        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        vendor = await self.users.find_one(
            {"email": vendor_email, "role": "advertising_vendor"}
        )
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        previous_logo_url = vendor.get("logo_url")
        if "logo_url" in filtered:
            filtered["logo_url"] = AdUploadService().ensure_vendor_asset_url(
                filtered.get("logo_url"),
                str(vendor["_id"]),
                VendorMediaAssetKind.VENDOR_LOGO,
                field_name="logo_url",
            )

        filtered["updated_at"] = datetime.now(timezone.utc)

        result = await self.users.update_one(
            {"email": vendor_email, "role": "advertising_vendor"},
            {"$set": filtered},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Vendor not found")

        if "logo_url" in filtered:
            new_logo_url = filtered.get("logo_url")
            await self.db["ad_campaigns"].update_many(
                {"vendor_id": str(vendor["_id"])},
                {
                    "$set": {
                        "vendor_logo_url": new_logo_url,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if previous_logo_url and previous_logo_url != new_logo_url:
                AdUploadService().delete_asset_url(
                    previous_logo_url,
                    str(vendor["_id"]),
                    VendorMediaAssetKind.VENDOR_LOGO,
                )

        # Fetch updated doc for completeness check
        vendor = await self.users.find_one({"email": vendor_email})
        completeness = check_profile_completeness(vendor)

        # Record profile_completed_at if newly complete
        if completeness["is_complete"] and not vendor.get("profile_completed_at"):
            await self.users.update_one(
                {"_id": vendor["_id"]},
                {"$set": {"profile_completed_at": datetime.now(timezone.utc)}},
            )

        logger.info(f"Vendor {vendor_email} profile updated: {list(filtered.keys())}")
        return {
            "message": "Profile updated",
            "updated_fields": list(filtered.keys()),
            "profile_completeness": completeness,
        }

    async def get_vendor_profile(self, vendor_email: str) -> Dict[str, Any]:
        """Get vendor profile with completeness status."""
        vendor = await self.users.find_one(
            {"email": vendor_email, "role": "advertising_vendor"}
        )
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        completeness = check_profile_completeness(vendor)

        return {
            "vendor_id": str(vendor["_id"]),
            "email": vendor["email"],
            "business_name": vendor.get("business_name", ""),
            "vendor_category": vendor.get("vendor_category", ""),
            "vendor_location": vendor.get("vendor_location", ""),
            "vendor_phone": vendor.get("vendor_phone", ""),
            "vendor_website": vendor.get("vendor_website", ""),
            "vendor_description": vendor.get("vendor_description", ""),
            "logo_url": vendor.get("logo_url", ""),
            "portfolio_urls": vendor.get("portfolio_urls", []),
            "vendor_account_status": vendor.get("vendor_account_status"),
            "must_change_password": vendor.get("must_change_password", False),
            "is_free_tier": vendor.get("is_free_tier", False),
            "profile_completeness": completeness,
            "created_at": vendor.get("created_at"),
            "profile_completed_at": vendor.get("profile_completed_at"),
        }

    # ─── Email Templates ──────────────────────────────────────────

    async def _send_signup_confirmation_email(
        self, email: str, business_name: str
    ) -> None:
        """Send confirmation email after vendor signs up (pending approval)."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0; padding:0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a;">
            <div style="max-width: 560px; margin: 40px auto; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
                <div style="padding: 32px 24px; text-align: center; border-bottom: 1px solid #334155;">
                    <h1 style="margin: 0; color: #f1f5f9; font-size: 22px;">The Special Wedding</h1>
                    <p style="margin: 8px 0 0; color: #94a3b8; font-size: 13px;">Vendor Advertising Platform</p>
                </div>
                <div style="padding: 32px 24px;">
                    <h2 style="color: #f1f5f9; font-size: 18px; margin: 0 0 16px;">Thank you, {business_name}!</h2>
                    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
                        We've received your vendor registration. Our team will review your
                        application and you'll receive an email once your account is approved.
                    </p>
                    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6; margin-top: 16px;">
                        This usually takes 1–2 business days. Once approved, you'll receive a
                        temporary password to access your vendor portal where you can create
                        advertising campaigns to reach wedding planners.
                    </p>
                    <div style="margin-top: 24px; padding: 16px; background: #1e293b; border-radius: 8px; border: 1px solid #334155;">
                        <p style="color: #94a3b8; font-size: 12px; margin: 0;">What happens next?</p>
                        <ol style="color: #cbd5e1; font-size: 13px; padding-left: 20px; margin: 8px 0 0;">
                            <li style="margin-bottom: 4px;">We review your application</li>
                            <li style="margin-bottom: 4px;">You receive a temporary password via email</li>
                            <li style="margin-bottom: 4px;">Sign in and complete your profile</li>
                            <li>Create your first advertising campaign</li>
                        </ol>
                    </div>
                </div>
                <div style="padding: 16px 24px; border-top: 1px solid #334155; text-align: center;">
                    <p style="color: #64748b; font-size: 11px; margin: 0;">
                        &copy; The Special Wedding &mdash; Professional Wedding Planning Platform
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        try:
            await self.email_service.send_email(
                to_email=email,
                subject="Vendor Registration Received — The Special Wedding",
                html_content=html,
                from_name="The Special Wedding",
                email_type="vendor_signup_confirmation",
            )
        except Exception as e:
            logger.error(f"Failed to send signup confirmation to {email}: {e}")

    async def _send_approval_email(self, email: str, temp_password: str) -> None:
        """Send approval email with temporary password."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0; padding:0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a;">
            <div style="max-width: 560px; margin: 40px auto; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
                <div style="padding: 32px 24px; text-align: center; border-bottom: 1px solid #334155;">
                    <h1 style="margin: 0; color: #f1f5f9; font-size: 22px;">The Special Wedding</h1>
                    <p style="margin: 8px 0 0; color: #94a3b8; font-size: 13px;">Vendor Advertising Platform</p>
                </div>
                <div style="padding: 32px 24px;">
                    <h2 style="color: #10b981; font-size: 18px; margin: 0 0 16px;">Your Account Has Been Approved!</h2>
                    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
                        Great news! Your vendor account has been approved. Use the temporary
                        password below to sign in for the first time.
                    </p>
                    <div style="margin: 24px 0; padding: 20px; background: #0f172a; border-radius: 8px; border: 1px solid #334155; text-align: center;">
                        <p style="color: #94a3b8; font-size: 12px; margin: 0 0 8px;">Your temporary password</p>
                        <p style="color: #f1f5f9; font-size: 20px; font-family: monospace; letter-spacing: 2px; margin: 0; word-break: break-all;">
                            {temp_password}
                        </p>
                        <p style="color: #f59e0b; font-size: 11px; margin: 12px 0 0;">
                            Expires in 72 hours. You will be required to change it on first login.
                        </p>
                    </div>
                    <a href="{_PORTAL_URL}"
                       style="display: block; text-align: center; background: #6366f1; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
                        Sign In to Vendor Portal
                    </a>
                    <p style="color: #94a3b8; font-size: 12px; margin-top: 16px; line-height: 1.5;">
                        After signing in, you'll be asked to change your password and
                        complete your business profile before creating campaigns.
                    </p>
                </div>
                <div style="padding: 16px 24px; border-top: 1px solid #334155; text-align: center;">
                    <p style="color: #64748b; font-size: 11px; margin: 0;">
                        &copy; The Special Wedding &mdash; Professional Wedding Planning Platform
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        try:
            await self.email_service.send_email(
                to_email=email,
                subject="Account Approved — Sign In to Your Vendor Portal",
                html_content=html,
                from_name="The Special Wedding",
                email_type="vendor_approval",
            )
        except Exception as e:
            logger.error(f"Failed to send approval email to {email}: {e}")

    async def _notify_admin_new_signup(
        self, vendor_email: str, business_name: str, vendor_id: str
    ) -> None:
        """Create in-app notification + push for root admin about new vendor signup."""
        try:
            await self.notification_service.create_notification(
                notification_data={
                    "title": "New Vendor Signup",
                    "message": (
                        f"{business_name} ({vendor_email}) has signed up as an "
                        f"advertising vendor and is awaiting approval."
                    ),
                    "type": "vendor_signup",
                    "target_audience": "root_admin",
                    "is_dismissible": True,
                    "priority": "high",
                    "user_id": vendor_id,
                },
                created_by="system",
            )
        except Exception as e:
            logger.error(f"Failed to create admin notification for signup: {e}")

        # Note: NotificationService.create_notification() above already handles
        # in-portal + push + SSE for root_admin. No extra call needed.
