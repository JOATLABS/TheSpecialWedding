from fastapi import HTTPException
from app.core.database import mongo
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta, timezone
import secrets
import string
import os
import logging

from app.utils.auth_utils import get_password_hash, verify_password
from app.services.email_service_resend import ResendEmailService
from app.core.events import event_bus, EventFactory


class UserManagementService:
    def __init__(self):
        self.users_collection = mongo.get_users_collection()
        self.invitations_collection = mongo.db["user_invitations"]
        self.weddings_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()
        self._pending_ttl_index_created = False
        self.logger = logging.getLogger(__name__)

    async def _ensure_pending_ttl_index(self):
        """
        Ensure a TTL index exists to clean up stale pending signups.
        Expires documents with subscription_status=pending_payment once pending_expires_at passes.
        """
        if self._pending_ttl_index_created:
            return
        try:
            await self.users_collection.create_index(
                [("pending_expires_at", 1)],
                name="idx_pending_payment_ttl",
                expireAfterSeconds=0,
                partialFilterExpression={
                    "subscription_status": "pending_payment",
                    "pending_expires_at": {"$exists": True}
                }
            )
            self._pending_ttl_index_created = True
        except Exception as e:
            # Non-fatal: log and continue
            self.logger.error(f"Failed to ensure pending TTL index: {str(e)}")

    def generate_invitation_token(self) -> str:
        """Generate a secure invitation token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    async def get_trial_settings(self) -> dict:
        """Get trial settings from SAAS config"""
        # Return defaults (can be extended to read from database later)
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }

    async def check_previous_trial_usage(self, email: str) -> bool:
        """Check if email has been used for a trial before"""
        try:
            # Check current users collection for trial usage
            existing_trial = await self.users_collection.find_one({
                "email": email,
                "$or": [
                    {"subscription_status": {"$in": ["trial", "expired"]}},
                    {"previous_trial_used": True}
                ]
            })
            # Check deleted users collection if it exists
            deleted_users = mongo.db.get("deleted_users", None)
            if deleted_users:
                deleted_trial = await deleted_users.find_one({
                    "email": email,
                    "$or": [
                        {"subscription_status": {"$in": ["trial", "expired"]}},
                        {"previous_trial_used": True}
                    ]
                })
                if deleted_trial:
                    return True
            return existing_trial is not None
        except Exception:
            return False

    async def invite_user(self, invite_data: dict, inviter_email: str) -> dict:
        """
        Invite a new user to the platform.

        If trial_days > 0, pre-creates a Stripe Customer so usage can be tracked
        and a subscription with trial can be created when user completes setup.
        """
        try:
            email = invite_data["email"]
            role = invite_data["role"]
            trial_days = invite_data.get("trial_days", 0)
            plan_id = invite_data.get("plan_id")

            # Check if user already exists
            existing_user = await self.users_collection.find_one({"email": email})
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")

            # Check for pending invitation
            existing_invitation = await self.invitations_collection.find_one({
                "email": email,
                "status": "pending",
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })
            if existing_invitation:
                raise HTTPException(status_code=400, detail="Pending invitation already exists for this email")

            # Pre-create Stripe Customer if trial is configured (best practice per Stripe docs)
            stripe_customer_id = None
            if trial_days > 0 and plan_id:
                try:
                    from app.core.settings import settings

                    if settings.stripe_enabled and settings.stripe_secret_key:
                        import stripe
                        stripe.api_key = settings.stripe_secret_key

                        # Create Stripe Customer ahead of time
                        customer = stripe.Customer.create(
                            email=email,
                            name=invite_data.get("company_name") or email,
                            metadata={
                                "invited_by": inviter_email,
                                "role": role,
                                "plan_id": plan_id,
                                "trial_days": str(trial_days),
                                "pre_subscription": "true"
                            }
                        )
                        stripe_customer_id = customer.id
                        self.logger.info(f"Pre-created Stripe customer {stripe_customer_id} for invited user {email}")
                except Exception as stripe_error:
                    # Log but don't fail invitation if Stripe customer creation fails
                    self.logger.warning(f"Failed to pre-create Stripe customer for {email}: {str(stripe_error)}")

            # Create invitation record
            invitation_token = self.generate_invitation_token()
            invitation = {
                "email": email,
                "role": role,
                "token": invitation_token,
                "invite_data": invite_data,
                "invited_by": inviter_email,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                "status": "pending",
                # Store Stripe customer ID for use during account setup
                "stripe_customer_id": stripe_customer_id,
                # Email tracking fields
                "email_status": "pending",
                "email_sent_at": None,
                "resend_count": 0
            }

            result = await self.invitations_collection.insert_one(invitation)
            invitation_id = str(result.inserted_id)

            # Store invitation-created Stripe customer in stripe_customers collection
            # so the orphaned cleanup job can track it even after invitation TTL-deletion.
            # Uses placeholder user_id (invitation_{token}) so existing cleanup logic
            # correctly identifies it as orphaned (no matching user or subscription).
            if stripe_customer_id:
                try:
                    await mongo.db["stripe_customers"].update_one(
                        {"stripe_customer_id": stripe_customer_id},
                        {"$set": {
                            "stripe_customer_id": stripe_customer_id,
                            "user_id": f"invitation_{invitation_token}",
                            "email": email,
                            "created_at": datetime.now(timezone.utc),
                            "source": "invitation",
                        }},
                        upsert=True
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to store invitation Stripe customer mapping: {e}")

            # Send invitation email with trial info if applicable
            trial_info = f" with a {trial_days}-day free trial" if trial_days > 0 else ""
            email_success = await self.send_invitation_email(
                email,
                invitation_token,
                role,
                inviter_email,
                invite_data.get("company_name") or "",
                trial_days=trial_days
            )

            # Update email status
            email_status = "sent" if email_success else "failed"
            await self.invitations_collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {
                    "email_status": email_status,
                    "email_sent_at": datetime.now(timezone.utc) if email_success else None
                }}
            )

            # Log activity
            try:
                from app.services.admin_activity_service import admin_activity_service
                # Get plan name for activity log
                plan_name = "Unknown"
                if plan_id:
                    plans_collection = mongo.db["subscription_plans"]
                    plan = await plans_collection.find_one({"_id": plan_id}, {"name": 1})
                    if plan:
                        plan_name = plan.get("name", "Unknown")

                await admin_activity_service.log_invitation_sent(
                    admin_id=inviter_email,
                    email=email,
                    plan_name=plan_name,
                    trial_days=trial_days,
                    invitation_id=invitation_id
                )
            except Exception as log_error:
                self.logger.warning(f"Failed to log invitation activity: {str(log_error)}")

            return {
                "message": f"Invitation sent to {email}{trial_info}",
                "invitation_id": invitation_id,
                "expires_at": invitation["expires_at"],
                "trial_days": trial_days,
                "stripe_customer_created": stripe_customer_id is not None,
                "email_status": email_status
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error sending invitation: {str(e)}")

    async def send_invitation_email(self, email: str, token: str, role: str, invited_by: str, company_name: Optional[str] = None, trial_days: int = 0):
        """Send invitation email to user with optional trial information"""
        try:
            # Note: This would integrate with your email service
            # For now, we'll just log it or use a simple email service
            # Send invitation email using ResendEmailService
            if self.email_service.configured:
                frontend_url = os.getenv("FRONTEND_URL")
                if not frontend_url:
                    raise ValueError("FRONTEND_URL environment variable is required")
                setup_url = f"{frontend_url}/setup-account?token={token}"
                # Create professional invitation email
                html_content = self._generate_invitation_email_html(
                    email=email,
                    role=role,
                    company_name=company_name,
                    setup_url=setup_url,
                    invited_by=invited_by
                )

                subject = "Welcome to Special Wedding - Complete Your Account Setup"

                result = await self.email_service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="user_invitation"
                )
                return result["success"]
            else:
                # Email service not configured - log for development
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Email service not configured. Invitation for {email} not sent.")
                return False
        except Exception:
            # Log error without exposing sensitive information
            return False

    async def list_users(self, role_filter: Optional[str] = None) -> List[dict]:
        """List all users with optional role filter"""
        try:
            query = {}
            if role_filter:
                query["role"] = role_filter

            users = await self.users_collection.find(query, {"password_hash": 0, "password": 0}).to_list(length=None)  # Exclude password fields

            # Convert ObjectId to string and calculate wedding_count for each user
            for user in users:
                user["_id"] = str(user["_id"])

                # Count weddings assigned to this user (by email or user ID)
                user_email = user.get("email")
                user_id = user["_id"]
                wedding_count = await self.weddings_collection.count_documents({
                    "$or": [
                        {"assigned_planner_email": user_email},
                        {"assigned_planner_id": user_id}
                    ]
                })
                user["wedding_count"] = wedding_count

            return users
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing users: {str(e)}")

    async def get_user(self, user_id: str) -> dict:
        """Get user by ID"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            user = await self.users_collection.find_one({"_id": obj_id}, {"password_hash": 0})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            # Convert ObjectId to string for JSON serialization
            user["_id"] = str(user["_id"])
            return user
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving user: {str(e)}")

    async def update_user(self, user_id: str, update_data: dict) -> dict:
        """Update user details"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            # Remove protected fields
            protected_fields = ["_id", "email", "password_hash", "created_at"]
            for field in protected_fields:
                update_data.pop(field, None)

            # Add update timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            result = await self.users_collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")

            return {"message": "User updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")

    async def delete_user(self, user_id: str) -> dict:
        """Delete user"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            # Get user first to check if they exist and get their email
            user = await self.users_collection.find_one({"_id": obj_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            # Check if user has assigned weddings
            assigned_weddings = await self.weddings_collection.find({"assigned_planner_email": user["email"]}).to_list(length=None)
            if assigned_weddings:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete user: {len(assigned_weddings)} weddings are assigned to this user"
                )

            # Delete user
            result = await self.users_collection.delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="User not found")

            return {"message": "User deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

    async def assign_wedding_to_planner(self, user_id: str, wedding_id: str) -> dict:
        """Assign a wedding to a planner"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId for user
            try:
                user_obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            # Get user to verify they exist and are a planner
            user = await self.users_collection.find_one({"_id": user_obj_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if user["role"] != "wedding_planner":
                raise HTTPException(status_code=400, detail="User is not a wedding planner")

            # Update wedding with assigned planner (wedding_id may be string slug or ObjectId)
            result = await self.weddings_collection.update_one(
                {"_id": wedding_id},
                {"$set": {"assigned_planner_email": user["email"]}}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": f"Wedding {wedding_id} assigned to {user['email']}"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error assigning wedding: {str(e)}")

    async def unassign_wedding_from_planner(self, user_id: str, wedding_id: str) -> dict:
        """Unassign a wedding from a planner"""
        try:
            # Update wedding to remove assigned planner
            result = await self.weddings_collection.update_one(
                {"_id": wedding_id},
                {"$unset": {"assigned_planner_email": ""}}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": f"Wedding {wedding_id} unassigned"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error unassigning wedding: {str(e)}")

    async def suspend_user(self, user_id: str) -> dict:
        """Suspend user account"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            result = await self.users_collection.update_one(
                {"_id": obj_id},
                {"$set": {"is_active": False, "is_suspended": True, "updated_at": datetime.now(timezone.utc)}}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")

            return {"message": "User suspended successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error suspending user: {str(e)}")

    async def activate_user(self, user_id: str) -> dict:
        """Activate user account"""
        try:
            from bson import ObjectId

            # Convert string to ObjectId
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

            result = await self.users_collection.update_one(
                {"_id": obj_id},
                {"$set": {"is_active": True, "is_suspended": False, "updated_at": datetime.now(timezone.utc)}}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")

            return {"message": "User activated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error activating user: {str(e)}")

    async def validate_invitation_token(self, token: str) -> dict:
        """Validate invitation token and return invitation details"""
        try:
            invitation = await self.invitations_collection.find_one({
                "token": token,
                "status": "pending",
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })

            if not invitation:
                raise HTTPException(status_code=404, detail="Invalid or expired invitation token")

            return {
                "email": invitation["email"],
                "role": invitation["role"],
                "company_name": invitation["invite_data"].get("company_name"),
                "expires_at": invitation["expires_at"]
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error validating token: {str(e)}")

    async def complete_account_setup(self, token: str, password: str, first_name: str, last_name: str) -> dict:
        """
        Complete account setup with password and name.

        If the invitation includes trial_days > 0, creates a Stripe Subscription
        with trial period so usage can be tracked and billing starts automatically
        when the trial ends.
        """
        try:
            # Validate token first
            invitation = await self.invitations_collection.find_one({
                "token": token,
                "status": "pending",
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })

            if not invitation:
                raise HTTPException(status_code=404, detail="Invalid or expired invitation token")

            # Check if user already exists
            existing_user = await self.users_collection.find_one({"email": invitation["email"]})
            if existing_user:
                raise HTTPException(status_code=400, detail="User account already exists")

            # Extract trial configuration from invitation
            invite_data = invitation.get("invite_data", {})
            trial_days = invite_data.get("trial_days", 0)
            plan_id = invite_data.get("plan_id")
            trial_end_behavior = invite_data.get("trial_end_behavior", "pause")
            stripe_customer_id = invitation.get("stripe_customer_id")

            # Determine subscription status based on trial configuration
            subscription_status = "trial" if trial_days > 0 else "inactive"
            trial_end_date = datetime.now(timezone.utc) + timedelta(days=trial_days) if trial_days > 0 else None
            stripe_subscription_id = None

            # Create Stripe Subscription with trial if configured
            if trial_days > 0 and plan_id:
                try:
                    from app.core.settings import settings

                    if settings.stripe_enabled and settings.stripe_secret_key:
                        import stripe
                        stripe.api_key = settings.stripe_secret_key

                        # Get or create Stripe Customer
                        if not stripe_customer_id:
                            customer = stripe.Customer.create(
                                email=invitation["email"],
                                name=invite_data.get("company_name") or invitation["email"],
                                metadata={
                                    "invited_by": invitation.get("invited_by"),
                                    "role": invitation["role"],
                                    "plan_id": plan_id
                                }
                            )
                            stripe_customer_id = customer.id

                        # Get the plan's Stripe price ID
                        plans_collection = mongo.db["subscription_plans"]
                        plan = await plans_collection.find_one({"_id": plan_id})

                        if plan and plan.get("stripe_price_id_monthly"):
                            # Create Stripe Subscription with trial
                            # No payment method required during trial
                            subscription = stripe.Subscription.create(
                                customer=stripe_customer_id,
                                items=[{"price": plan["stripe_price_id_monthly"]}],
                                trial_period_days=trial_days,
                                payment_behavior="default_incomplete",
                                payment_settings={
                                    "save_default_payment_method": "on_subscription"
                                },
                                trial_settings={
                                    "end_behavior": {
                                        "missing_payment_method": trial_end_behavior
                                    }
                                },
                                metadata={
                                    "invited_by": invitation.get("invited_by"),
                                    "plan_id": plan_id,
                                    "admin_granted_trial": "true"
                                }
                            )
                            stripe_subscription_id = subscription.id
                            trial_end_date = datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None
                            self.logger.info(
                                f"Created Stripe subscription {stripe_subscription_id} with "
                                f"{trial_days}-day trial for {invitation['email']}"
                            )

                            # Store customer mapping in stripe_customers collection
                            stripe_customers = mongo.db["stripe_customers"]
                            await stripe_customers.update_one(
                                {"email": invitation["email"]},
                                {
                                    "$set": {
                                        "stripe_customer_id": stripe_customer_id,
                                        "email": invitation["email"],
                                        "updated_at": datetime.now(timezone.utc)
                                    },
                                    "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
                                },
                                upsert=True
                            )
                        else:
                            self.logger.warning(
                                f"Plan {plan_id} not found or missing stripe_price_id_monthly. "
                                f"Trial granted locally only."
                            )

                except Exception as stripe_error:
                    # Log but don't fail account setup if Stripe subscription creation fails
                    # User will still get local trial, just won't have Stripe integration
                    self.logger.error(f"Failed to create Stripe subscription for {invitation['email']}: {str(stripe_error)}")

            # Create user account
            password_hash = get_password_hash(password)
            user_data = {
                "email": invitation["email"],
                "password_hash": password_hash,
                "role": invitation["role"],
                "first_name": first_name,
                "last_name": last_name,
                "company_name": invite_data.get("company_name", ""),
                "plan_id": plan_id,
                "subscription_status": subscription_status,
                "trial_end_date": trial_end_date,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id,
                "is_active": True,
                "email_verified": True,  # Invited users are pre-verified by admin
                "invited_by": invitation.get("invited_by"),
                "admin_notes": invite_data.get("admin_notes"),
                "created_at": datetime.now(timezone.utc),
                "setup_completed_at": datetime.now(timezone.utc)
            }

            result = await self.users_collection.insert_one(user_data)
            user_id = str(result.inserted_id)

            # Update stripe_customers record with real user_id (replaces invitation
            # placeholder "invitation_{token}"). This ensures get_or_create_customer()
            # in assign_subscription finds the existing customer instead of creating
            # a duplicate.
            if stripe_customer_id:
                try:
                    await mongo.db["stripe_customers"].update_one(
                        {"stripe_customer_id": stripe_customer_id},
                        {"$set": {"user_id": user_id, "updated_at": datetime.now(timezone.utc)}}
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to update stripe_customers user_id: {e}")

            # Create subscription record if trial granted
            if trial_days > 0 and plan_id:
                try:
                    from app.services.subscription_service import subscription_service
                    await subscription_service.assign_subscription(
                        user_id=user_id,
                        plan_id=plan_id,
                        billing_interval="monthly",
                        trial_days=trial_days,
                        creator_email=invitation.get("invited_by", "system")
                    )
                except Exception as sub_error:
                    self.logger.error(f"Failed to create subscription record: {str(sub_error)}")
                    # ROLLBACK: Delete the user document since subscription failed
                    await self.users_collection.delete_one({"_id": result.inserted_id})
                    raise HTTPException(
                        status_code=500,
                        detail="Account created but subscription setup failed. Please try again or contact support."
                    )
            elif trial_days > 0 and not plan_id:
                # Trial requested but no plan specified - rollback
                await self.users_collection.delete_one({"_id": result.inserted_id})
                raise HTTPException(
                    status_code=400,
                    detail="Trial requires a subscription plan. Please contact the administrator."
                )

            # Mark invitation as completed and clear expires_at to prevent
            # TTL index from deleting accepted invitation records
            await self.invitations_collection.update_one(
                {"token": token},
                {
                    "$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)},
                    "$unset": {"expires_at": ""}
                }
            )

            # Build response
            response = {
                "message": "Account setup completed successfully",
                "user_id": user_id,
                "email": invitation["email"],
                "role": invitation["role"],
                "subscription_status": subscription_status
            }

            if trial_days > 0:
                response["trial_days"] = trial_days
                response["trial_end_date"] = trial_end_date.isoformat() if trial_end_date else None
                response["stripe_subscription_created"] = stripe_subscription_id is not None

            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error completing account setup: {str(e)}")

    async def register_wedding_planner(self, registration_data: dict) -> dict:
        """Public registration for wedding planners with email verification"""
        try:
            email = registration_data["email"]

            # Get trial settings from SAAS config
            trial_settings = await self.get_trial_settings()
            await self._ensure_pending_ttl_index()

            # Check if user already exists
            existing_user = await self.users_collection.find_one({"email": email})
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            # Check for previous trial usage if not allowed
            if not trial_settings.get("allow_multiple_trials", False):
                if await self.check_previous_trial_usage(email):
                    raise HTTPException(
                        status_code=400,
                        detail="Free trial has already been used with this email address. Please contact support for assistance."
                    )

            # Generate email verification token
            verification_token = self.generate_invitation_token()
            verification_expires = datetime.now(timezone.utc) + timedelta(hours=48)  # 48 hours to verify

            # Create user account (pending until Stripe checkout + verification)
            password_hash = get_password_hash(registration_data["password"])
            pending_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
            user_data = {
                "email": email,
                "password_hash": password_hash,
                "role": registration_data.get("role", "wedding_planner"),
                "first_name": registration_data.get("first_name", ""),
                "last_name": registration_data.get("last_name", ""),
                "company_name": registration_data.get("company_name", ""),
                "plan_id": registration_data.get("selected_plan_id"),
                "subscription_status": "pending_payment",
                "trial_end_date": None,
                "trial_warning_sent": False,
                "is_active": False,  # Account inactive until payment + email verification
                "email_verified": False,  # Will be auto-verified on successful checkout
                "email_verification_token": verification_token,
                "verification_token_expires": verification_expires,
                "pending_expires_at": pending_expires_at,
                "created_at": datetime.now(timezone.utc),
                "registration_source": "public_signup"
            }

            result = await self.users_collection.insert_one(user_data)

            # Auto-complete any pending invitation for this email
            try:
                pending_invitation = await self.invitations_collection.find_one({
                    "email": email,
                    "status": "pending"
                })
                if pending_invitation:
                    await self.invitations_collection.update_one(
                        {"_id": pending_invitation["_id"]},
                        {"$set": {
                            "status": "completed",
                            "completed_at": datetime.now(timezone.utc),
                            "completion_method": "public_registration"
                        }}
                    )
            except Exception as e:
                self.logger.warning(f"Failed to auto-complete invitation for {email}: {e}")

            # Send email verification email
            if self.email_service.configured:
                # Create verification URL
                frontend_url = os.getenv("FRONTEND_URL")
                if not frontend_url:
                    raise ValueError("FRONTEND_URL environment variable is required")
                verification_url = f"{frontend_url}/verify-email/{verification_token}"
                html_content = self._generate_verification_email_html(
                    email=email,
                    first_name=user_data.get("first_name", ""),
                    verification_url=verification_url
                )

                subject = "Verify Your Email - Special Wedding"

                await self.email_service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="email_verification"
                )
            return {
                "message": "Registration successful! Please check your email to verify your account before logging in.",
                "user_id": str(result.inserted_id),
                "email": email,
                "role": user_data["role"],
                "verification_required": True
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")

    async def verify_email(self, token: str) -> dict:
        """Verify email address using verification token"""
        try:
            # Find user with matching verification token
            user = await self.users_collection.find_one({
                "email_verification_token": token,
                "email_verified": False
            })

            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired verification token")

            # Check if token has expired
            if user.get("verification_token_expires") and user["verification_token_expires"] < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Verification token has expired. Please register again.")

            # Update user to verified status
            await self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "email_verified": True,
                        "is_active": True,
                        "verified_at": datetime.now(timezone.utc)
                    },
                    "$unset": {
                        "email_verification_token": "",
                        "verification_token_expires": ""
                    }
                }
            )
            # Send welcome email after successful verification
            if self.email_service.configured:
                html_content = self._generate_welcome_email_html(
                    email=user["email"],
                    first_name=user.get("first_name", ""),
                    role=user.get("role", "wedding_planner"),
                    company_name=user.get("company_name", "")
                )

                subject = "Welcome to Special Wedding - Your Account is Ready!"

                await self.email_service.send_email(
                    to_email=user["email"],
                    subject=subject,
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="welcome_email"
                )
            return {
                "message": "Email verified successfully! Your account is now active. You can log in.",
                "email": user["email"],
                "verified_at": datetime.now(timezone.utc).isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying email: {str(e)}")

    def _generate_invitation_email_html(self, email: str, role: str, company_name: Optional[str], setup_url: str, invited_by: str) -> str:
        """Generate professional invitation email HTML"""
        role_display = role.replace("_", " ").title()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 1px; }}
                .header p {{ margin: 10px 0 0; font-size: 16px; opacity: 0.9; }}
                .content {{ padding: 40px 30px; }}
                .welcome-card {{ background: #f8f9fa; border-left: 4px solid #c8847e; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-top: 1px solid #eee; }}
                .security-note {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Special Wedding</h1>
                    <p>Complete Your Account Setup</p>
                </div>
                <div class="content">
                    <p>Hello!</p>
                    <p>You've been invited to join <strong>Special Wedding</strong> as a <strong>{role_display}</strong> by {invited_by}.</p>
                    <div class="welcome-card">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">Your Account Details:</h3>
                        <p style="margin: 8px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 8px 0;"><strong>Role:</strong> {role_display}</p>
                        {f'<p style="margin: 8px 0;"><strong>Company:</strong> {company_name}</p>' if company_name else ''}
                    </div>

                    <p>To complete your account setup and create your password, please click the button below:</p>

                    <div class="button-container">
                        <a href="{setup_url}" class="button">Complete Account Setup</a>
                    </div>

                    <div class="security-note">
                        <strong>Security Note:</strong> This invitation link is unique to you and will expire in 7 days. If you didn't expect this invitation, please ignore this email.
                    </div>

                    <p>If you have any questions, feel free to contact our support team.</p>

                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; color: #c8847e; font-size: 12px;">{setup_url}</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_verification_email_html(self, email: str, first_name: str, verification_url: str) -> str:
        """Generate email verification email HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email - Special Wedding</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 0; padding: 0; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); }}
                .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; font-size: 16px; }}
                .content {{ padding: 40px 30px; }}
                .verification-card {{ background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 15px; padding: 30px; margin: 25px 0; border-left: 5px solid #c8847e; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-top: 1px solid #eee; }}
                .security-note {{ background: #e8f5e8; border: 1px solid #4caf50; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
                .expiry-warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Verify Your Email</h1>
                    <p>Complete Your Special Wedding Registration</p>
                </div>
                <div class="content">
                    <p>Hello{f' {first_name}' if first_name else ''}!</p>
                    <p>Thank you for registering with <strong>Special Wedding</strong>! To complete your account setup and start planning amazing weddings, please verify your email address.</p>
                    <div class="verification-card">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">Account Details:</h3>
                        <p style="margin: 8px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 8px 0;"><strong>Status:</strong> Pending Verification</p>
                    </div>

                    <p>Click the button below to verify your email address and activate your account:</p>

                    <div class="button-container">
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </div>

                    <div class="expiry-warning">
                        <strong>Important:</strong> This verification link will expire in 48 hours. If you don't verify your email within this time, you'll need to register again.
                    </div>

                    <div class="security-note">
                        <strong>Security Note:</strong> If you didn't create an account with Special Wedding, please ignore this email. Your email address will not be used for any further communications.
                    </div>

                    <p>Once verified, you'll be able to:</p>
                    <ul>
                        <li>Create and manage wedding projects</li>
                        <li>Collaborate with vendors and team members</li>
                        <li>Send beautiful RSVP invitations</li>
                        <li>Track guest responses and analytics</li>
                    </ul>
                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; color: #c8847e; font-size: 12px;">{verification_url}</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_welcome_email_html(self, email: str, first_name: str, role: str, company_name: str) -> str:
        """Generate welcome email HTML for new users"""
        role_display = role.replace("_", " ").title()
        name_display = first_name if first_name else email.split('@')[0].title()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 32px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 18px; opacity: 0.9; }}
                .content {{ padding: 40px 30px; }}
                .feature-list {{ background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; }}
                .feature-list ul {{ margin: 10px 0; padding-left: 20px; }}
                .feature-list li {{ margin: 10px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome!</h1>
                    <p>Your account is ready</p>
                </div>
                <div class="content">
                    <p>Hi {name_display},</p>
                    <p>Welcome to <strong>Special Wedding</strong>! Your account has been successfully created and you're ready to start planning amazing weddings.</p>
                    <div class="feature-list">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">What you can do now:</h3>
                        <ul>
                            <li>Create and manage wedding projects</li>
                            <li>Invite and collaborate with vendors</li>
                            <li>Send beautiful RSVP invitations</li>
                            <li>Track guest responses and analytics</li>
                            <li>Manage photo galleries</li>
                            <li>Send SMS reminders to guests</li>
                        </ul>
                    </div>

                    <p>As a <strong>{role_display}</strong>{f' at {company_name}' if company_name else ''}, you have access to all the tools you need to create memorable wedding experiences.</p>

                    <div class="button-container">
                        <a href="{os.getenv('FRONTEND_URL')}/admin" class="button">Start Planning</a>
                    </div>

                    <p>If you have any questions or need help getting started, our support team is here to help.</p>

                    <p>Happy planning!<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>Need help? Visit our <a href="#" style="color: #c8847e;">support center</a> or reply to this email.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def change_password(self, user_email: str, current_password: str, new_password: str) -> dict:
        """Change user password after verifying current password"""
        try:
            # Find the user
            user = await self.users_collection.find_one({"email": user_email})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify current password
            if not verify_password(current_password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Current password is incorrect")

            # Hash new password
            new_password_hash = get_password_hash(new_password)

            # Update password in database
            result = await self.users_collection.update_one(
                {"email": user_email},
                {
                    "$set": {
                        "password_hash": new_password_hash,
                        "password_changed_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=500, detail="Failed to update password")

            # Publish password changed event
            try:
                event = EventFactory.password_changed(
                    user_id=str(user["_id"]),
                    email=user_email
                )
                await event_bus.publish(event)
            except Exception as e:
                # Log but don't fail the password change if event publishing fails
                print(f"Failed to publish password change event: {e}")
            return {
                "message": "Password changed successfully",
                "changed_at": datetime.now(timezone.utc).isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error changing password: {str(e)}")

    async def change_email(self, current_email: str, new_email: str, password: str) -> dict:
        """Change user email address after password verification"""
        try:
            # Find the user
            user = await self.users_collection.find_one({"email": current_email})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify password
            if not verify_password(password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Password is incorrect")

            # Check if new email is already in use
            existing_user = await self.users_collection.find_one({"email": new_email})
            if existing_user:
                raise HTTPException(status_code=400, detail="Email address is already in use")

            # Generate email verification token for new email
            verification_token = self.generate_invitation_token()
            verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hours to verify

            # Update user with new email (but keep it unverified until verification)
            result = await self.users_collection.update_one(
                {"email": current_email},
                {
                    "$set": {
                        "pending_email": new_email,
                        "email_change_token": verification_token,
                        "email_change_token_expires": verification_expires,
                        "email_change_requested_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=500, detail="Failed to initiate email change")

            # Publish email change requested event
            try:
                event = EventFactory.email_change_requested(
                    user_id=str(user["_id"]),
                    old_email=current_email,
                    new_email=new_email
                )
                await event_bus.publish(event)
            except Exception as e:
                # Log but don't fail the email change if event publishing fails
                print(f"Failed to publish email change requested event: {e}")
            return {
                "message": "Email change requested. Please check your new email address to verify the change.",
                "pending_email": new_email,
                "verification_required": True,
                "expires_at": verification_expires.isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error changing email: {str(e)}")

    async def verify_email_change(self, token: str) -> dict:
        """Verify email change using verification token"""
        try:
            # Find user with matching email change token
            user = await self.users_collection.find_one({
                "email_change_token": token
            })

            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired verification token")

            # Check if token has expired
            if user.get("email_change_token_expires") and user["email_change_token_expires"] < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Verification token has expired. Please request a new email change.")

            # Update user email to the new email
            old_email = user["email"]
            new_email = user["pending_email"]

            await self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "email": new_email,
                        "email_changed_at": datetime.now(timezone.utc)
                    },
                    "$unset": {
                        "pending_email": "",
                        "email_change_token": "",
                        "email_change_token_expires": "",
                        "email_change_requested_at": ""
                    }
                }
            )
            # Publish email changed event
            try:
                event = EventFactory.email_changed(
                    user_id=str(user["_id"]),
                    old_email=old_email,
                    new_email=new_email
                )
                await event_bus.publish(event)
            except Exception as e:
                # Log but don't fail the email change if event publishing fails
                print(f"Failed to publish email changed event: {e}")
            return {
                "message": "Email address changed successfully",
                "old_email": old_email,
                "new_email": new_email,
                "changed_at": datetime.now(timezone.utc).isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying email change: {str(e)}")

    async def get_user_profile(self, user_email: str) -> dict:
        """Get user profile information"""
        try:
            user = await self.users_collection.find_one(
                {"email": user_email},
                {
                    "password_hash": 0,  # Don't return password hash
                    "email_verification_token": 0,  # Don't return sensitive tokens
                    "email_change_token": 0
                }
            )

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Convert ObjectId to string
            user["_id"] = str(user["_id"])

            return user

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving user profile: {str(e)}")

    async def update_profile_info(self, user_email: str, profile_data: dict) -> dict:
        """Update user profile information"""
        try:
            # Validate user exists
            user = await self.users_collection.find_one({"email": user_email})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Prepare update data
            update_data = {}
            if profile_data.get("first_name") is not None:
                update_data["first_name"] = profile_data["first_name"].strip()
            if profile_data.get("last_name") is not None:
                update_data["last_name"] = profile_data["last_name"].strip()
            if profile_data.get("company_name") is not None:
                update_data["company_name"] = profile_data["company_name"].strip()
            if profile_data.get("phone") is not None:
                update_data["phone"] = profile_data["phone"].strip()
            # Handle support phone for SMS HELP responses (wedding planners)
            if profile_data.get("support_phone") is not None:
                update_data["support_phone"] = profile_data["support_phone"].strip() if profile_data["support_phone"] else None
            # Handle profile image URL (can be set to None to remove)
            if "profile_image_url" in profile_data:
                update_data["profile_image_url"] = profile_data["profile_image_url"]
            # Handle push notifications preference
            if "push_notifications_enabled" in profile_data:
                update_data["push_notifications_enabled"] = profile_data["push_notifications_enabled"]
            # Handle timezone preference (IANA timezone string)
            if profile_data.get("timezone") is not None:
                timezone_str = profile_data["timezone"].strip()
                # Basic validation: should look like a valid IANA timezone
                if "/" in timezone_str or timezone_str in ("UTC", "GMT"):
                    update_data["timezone"] = timezone_str

            # Handle onboarding fields (for wedding planners)
            if "onboarding_completed" in profile_data:
                update_data["onboarding_completed"] = profile_data["onboarding_completed"]
            if "onboarding_completed_at" in profile_data:
                update_data["onboarding_completed_at"] = profile_data["onboarding_completed_at"]
            if "onboarding_steps_completed" in profile_data:
                update_data["onboarding_steps_completed"] = profile_data["onboarding_steps_completed"]

            if not update_data:
                raise HTTPException(status_code=400, detail="No valid profile data provided")

            # Add updated timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            # Update user profile
            result = await self.users_collection.update_one(
                {"email": user_email},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Profile update failed")

            # Publish profile updated event
            await event_bus.publish(EventFactory.user_profile_updated(
                user_id=str(user["_id"]),
                email=user_email,
                updated_fields=list(update_data.keys())
            ))

            return {
                "message": "Profile updated successfully",
                "updated_fields": list(update_data.keys())
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

    # ==================== INVITATION MANAGEMENT ====================

    async def list_invitations(
        self,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """
        List invitations with optional status filter.

        Args:
            status: Filter by status (pending, completed, expired, cancelled)
            page: Page number (1-indexed)
            limit: Items per page
        """
        try:
            query: Dict[str, Any] = {}

            if status:
                if status == "expired":
                    # Expired = pending but past expires_at
                    query["status"] = "pending"
                    query["expires_at"] = {"$lt": datetime.now(timezone.utc)}
                elif status == "pending":
                    # Pending = status pending AND not expired
                    query["status"] = "pending"
                    query["expires_at"] = {"$gt": datetime.now(timezone.utc)}
                else:
                    query["status"] = status

            total = await self.invitations_collection.count_documents(query)
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Get subscription plans for enrichment
            plans_collection = mongo.db["subscription_plans"]
            plans_cursor = plans_collection.find({}, {"_id": 1, "name": 1})
            plans_map = {}
            async for plan in plans_cursor:
                plans_map[str(plan["_id"])] = plan.get("name", "Unknown")

            cursor = self.invitations_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            invitations = []

            async for doc in cursor:
                invite_data = doc.get("invite_data", {})
                plan_id = invite_data.get("plan_id")

                # Determine actual status (check if expired)
                actual_status = doc.get("status", "pending")
                if actual_status == "pending" and doc.get("expires_at", datetime.now(timezone.utc)) < datetime.now(timezone.utc):
                    actual_status = "expired"

                invitations.append({
                    "_id": str(doc["_id"]),
                    "id": str(doc["_id"]),
                    "email": doc["email"],
                    "role": doc.get("role", "wedding_planner"),
                    "invite_data": {
                        "plan_id": plan_id,
                        "plan_name": plans_map.get(plan_id, "Unknown") if plan_id else None,
                        "trial_days": invite_data.get("trial_days", 0),
                        "company_name": invite_data.get("company_name"),
                        "trial_end_behavior": invite_data.get("trial_end_behavior", "pause"),
                        "admin_notes": invite_data.get("admin_notes")
                    },
                    "invited_by": doc.get("invited_by"),
                    "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
                    "expires_at": doc["expires_at"].isoformat() if doc.get("expires_at") else None,
                    "status": actual_status,
                    "email_status": doc.get("email_status", "sent"),
                    "email_sent_at": doc["email_sent_at"].isoformat() if doc.get("email_sent_at") else None,
                    "resend_count": doc.get("resend_count", 0),
                    "last_resent_at": doc["last_resent_at"].isoformat() if doc.get("last_resent_at") else None,
                    "completed_at": doc["completed_at"].isoformat() if doc.get("completed_at") else None
                })

            return {
                "invitations": invitations,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            self.logger.error(f"Error listing invitations: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing invitations: {str(e)}")

    async def get_invitation_stats(self) -> dict:
        """Get invitation counts by status"""
        try:
            now = datetime.now(timezone.utc)

            # Pending (not expired)
            pending = await self.invitations_collection.count_documents({
                "status": "pending",
                "expires_at": {"$gt": now}
            })

            # Expired (pending but past expires_at)
            expired = await self.invitations_collection.count_documents({
                "status": "pending",
                "expires_at": {"$lt": now}
            })

            # Completed
            completed = await self.invitations_collection.count_documents({
                "status": "completed"
            })

            # Cancelled
            cancelled = await self.invitations_collection.count_documents({
                "status": "cancelled"
            })

            return {
                "pending": pending,
                "expired": expired,
                "completed": completed,
                "cancelled": cancelled,
                "total": pending + expired + completed + cancelled
            }

        except Exception as e:
            self.logger.error(f"Error getting invitation stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting invitation stats: {str(e)}")

    async def resend_invitation(self, invitation_id: str, resent_by: str) -> dict:
        """
        Resend invitation email with a new token.

        Args:
            invitation_id: The invitation document ID
            resent_by: Email of admin who is resending
        """
        try:
            from bson import ObjectId

            try:
                obj_id = ObjectId(invitation_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid invitation ID")

            # Find the invitation
            invitation = await self.invitations_collection.find_one({"_id": obj_id})

            if not invitation:
                raise HTTPException(status_code=404, detail="Invitation not found")

            if invitation.get("status") == "completed":
                raise HTTPException(status_code=400, detail="Cannot resend completed invitation")

            if invitation.get("status") == "cancelled":
                raise HTTPException(status_code=400, detail="Cannot resend cancelled invitation")

            # Generate new token and reset expiration
            new_token = self.generate_invitation_token()
            new_expires = datetime.now(timezone.utc) + timedelta(days=7)

            # Send new email
            invite_data = invitation.get("invite_data", {})
            email_success = await self.send_invitation_email(
                invitation["email"],
                new_token,
                invitation.get("role", "wedding_planner"),
                resent_by,
                invite_data.get("company_name"),
                trial_days=invite_data.get("trial_days", 0)
            )

            # Update invitation record
            update_data = {
                "token": new_token,
                "expires_at": new_expires,
                "status": "pending",
                "email_status": "sent" if email_success else "failed",
                "last_resent_at": datetime.now(timezone.utc),
                "resent_by": resent_by
            }

            await self.invitations_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": update_data,
                    "$inc": {"resend_count": 1}
                }
            )

            # Log activity
            try:
                from app.services.admin_activity_service import admin_activity_service
                await admin_activity_service.log_invitation_resent(
                    admin_id=resent_by,
                    email=invitation["email"],
                    invitation_id=invitation_id
                )
            except Exception as log_error:
                self.logger.warning(f"Failed to log invitation resent activity: {str(log_error)}")

            return {
                "message": f"Invitation resent to {invitation['email']}",
                "invitation_id": invitation_id,
                "email_status": "sent" if email_success else "failed",
                "new_expires_at": new_expires.isoformat()
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error resending invitation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error resending invitation: {str(e)}")

    async def cancel_invitation(
        self,
        invitation_id: str,
        cancelled_by: str,
        reason: Optional[str] = None
    ) -> dict:
        """
        Cancel a pending invitation.

        Args:
            invitation_id: The invitation document ID
            cancelled_by: Email of admin who is cancelling
            reason: Optional reason for cancellation
        """
        try:
            from bson import ObjectId

            try:
                obj_id = ObjectId(invitation_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid invitation ID")

            # Find the invitation
            invitation = await self.invitations_collection.find_one({"_id": obj_id})

            if not invitation:
                raise HTTPException(status_code=404, detail="Invitation not found")

            if invitation.get("status") == "completed":
                raise HTTPException(status_code=400, detail="Cannot cancel completed invitation")

            if invitation.get("status") == "cancelled":
                raise HTTPException(status_code=400, detail="Invitation already cancelled")

            # Update invitation status
            await self.invitations_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.now(timezone.utc),
                        "cancelled_by": cancelled_by,
                        "cancellation_reason": reason
                    }
                }
            )

            # If Stripe customer was pre-created, optionally delete it
            stripe_customer_id = invitation.get("stripe_customer_id")
            if stripe_customer_id:
                try:
                    from app.core.settings import settings
                    if settings.stripe_enabled and settings.stripe_secret_key:
                        import stripe
                        stripe.api_key = settings.stripe_secret_key
                        # Don't delete, just update metadata to mark as cancelled
                        stripe.Customer.modify(
                            stripe_customer_id,
                            metadata={"invitation_cancelled": "true", "cancelled_at": datetime.now(timezone.utc).isoformat()}
                        )
                except Exception as stripe_error:
                    self.logger.warning(f"Failed to update Stripe customer for cancelled invitation: {str(stripe_error)}")

            # Log activity
            try:
                from app.services.admin_activity_service import admin_activity_service
                await admin_activity_service.log_invitation_cancelled(
                    admin_id=cancelled_by,
                    email=invitation["email"],
                    reason=reason,
                    invitation_id=invitation_id
                )
            except Exception as log_error:
                self.logger.warning(f"Failed to log invitation cancelled activity: {str(log_error)}")

            return {
                "message": f"Invitation for {invitation['email']} cancelled",
                "invitation_id": invitation_id,
                "cancelled_at": datetime.now(timezone.utc).isoformat()
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error cancelling invitation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error cancelling invitation: {str(e)}")

    # ==================== PASSWORD RESET ====================

    async def request_password_reset(self, email: str) -> dict:
        """
        Request a password reset. Generates a reset token and sends email.

        Args:
            email: The user's email address

        Returns:
            Success message (same message whether user exists or not for security)
        """
        try:
            # Always return same message for security (don't reveal if email exists)
            success_message = {
                "message": "If an account with this email exists, you will receive a password reset link shortly.",
                "email": email
            }

            # Find the user
            user = await self.users_collection.find_one({"email": email})
            if not user:
                # Don't reveal that user doesn't exist
                return success_message

            # Check if user account is active
            if not user.get("is_active", True):
                # Don't reveal account status
                return success_message

            # Generate reset token
            reset_token = self.generate_invitation_token()
            reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)  # 1 hour expiry

            # Store reset token in user document
            await self.users_collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "password_reset_token": reset_token,
                        "password_reset_expires": reset_expires,
                        "password_reset_requested_at": datetime.now(timezone.utc)
                    }
                }
            )

            # Send password reset email
            if self.email_service.configured:
                frontend_url = os.getenv("FRONTEND_URL")
                if not frontend_url:
                    self.logger.error("FRONTEND_URL environment variable is required")
                    return success_message

                reset_url = f"{frontend_url}/reset-password?token={reset_token}"
                html_content = self._generate_password_reset_email_html(
                    email=email,
                    first_name=user.get("first_name", ""),
                    reset_url=reset_url
                )

                await self.email_service.send_email(
                    to_email=email,
                    subject="Reset Your Password - Special Wedding",
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="password_reset"
                )
            else:
                self.logger.warning(f"Email service not configured. Password reset for {email} not sent.")

            return success_message

        except Exception as e:
            self.logger.error(f"Error requesting password reset: {str(e)}")
            # Still return success message for security
            return {
                "message": "If an account with this email exists, you will receive a password reset link shortly.",
                "email": email
            }

    async def reset_password(self, token: str, new_password: str) -> dict:
        """
        Reset password using a valid reset token.

        Args:
            token: The password reset token
            new_password: The new password to set

        Returns:
            Success message
        """
        try:
            # Find user with matching reset token
            user = await self.users_collection.find_one({
                "password_reset_token": token
            })

            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired reset token")

            # Check if token has expired
            if user.get("password_reset_expires") and user["password_reset_expires"] < datetime.now(timezone.utc):
                # Clean up expired token
                await self.users_collection.update_one(
                    {"_id": user["_id"]},
                    {
                        "$unset": {
                            "password_reset_token": "",
                            "password_reset_expires": "",
                            "password_reset_requested_at": ""
                        }
                    }
                )
                raise HTTPException(status_code=400, detail="Password reset token has expired. Please request a new one.")

            # Hash new password
            new_password_hash = get_password_hash(new_password)

            # Update password and clear reset token
            await self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "password_hash": new_password_hash,
                        "password_changed_at": datetime.now(timezone.utc)
                    },
                    "$unset": {
                        "password_reset_token": "",
                        "password_reset_expires": "",
                        "password_reset_requested_at": ""
                    }
                }
            )

            # Publish password changed event
            try:
                event = EventFactory.password_changed(
                    user_id=str(user["_id"]),
                    email=user["email"]
                )
                await event_bus.publish(event)
            except Exception as e:
                self.logger.warning(f"Failed to publish password changed event: {e}")

            # Send confirmation email
            if self.email_service.configured:
                html_content = self._generate_password_changed_email_html(
                    email=user["email"],
                    first_name=user.get("first_name", "")
                )

                await self.email_service.send_email(
                    to_email=user["email"],
                    subject="Your Password Has Been Changed - Special Wedding",
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="password_changed"
                )

            return {
                "message": "Password has been reset successfully. You can now log in with your new password.",
                "email": user["email"]
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error resetting password: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error resetting password: {str(e)}")

    async def validate_password_reset_token(self, token: str) -> dict:
        """
        Validate a password reset token without using it.

        Args:
            token: The password reset token

        Returns:
            Token validation status and masked email
        """
        try:
            user = await self.users_collection.find_one({
                "password_reset_token": token
            })

            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired reset token")

            # Check if token has expired
            if user.get("password_reset_expires") and user["password_reset_expires"] < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Password reset token has expired. Please request a new one.")

            # Mask email for privacy (show first 2 chars and domain)
            email = user["email"]
            email_parts = email.split("@")
            if len(email_parts[0]) > 2:
                masked_email = email_parts[0][:2] + "***@" + email_parts[1]
            else:
                masked_email = email_parts[0][0] + "***@" + email_parts[1]

            return {
                "valid": True,
                "email": masked_email,
                "expires_at": user["password_reset_expires"].isoformat()
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error validating reset token: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error validating reset token: {str(e)}")

    def _generate_password_reset_email_html(self, email: str, first_name: str, reset_url: str) -> str:
        """Generate password reset email HTML"""
        name_display = first_name if first_name else "there"
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 1px; }}
                .header p {{ margin: 10px 0 0; font-size: 16px; opacity: 0.9; }}
                .content {{ padding: 40px 30px; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; }}
                .button:hover {{ background-color: #b6736d; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-top: 1px solid #eee; }}
                .security-note {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
                .expiry-warning {{ background: #ffe6e6; border: 1px solid #ffcccc; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                    <p>Special Wedding Platform</p>
                </div>
                <div class="content">
                    <p>Hi {name_display},</p>
                    <p>We received a request to reset the password for your Special Wedding account associated with <strong>{email}</strong>.</p>

                    <p>Click the button below to reset your password:</p>

                    <div class="button-container">
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </div>

                    <div class="expiry-warning">
                        <strong>Important:</strong> This password reset link will expire in 1 hour. After that, you'll need to request a new one.
                    </div>

                    <div class="security-note">
                        <strong>Security Note:</strong> If you didn't request a password reset, please ignore this email. Your password will remain unchanged. If you're concerned about your account security, please contact our support team.
                    </div>

                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; color: #c8847e; font-size: 12px;">{reset_url}</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_password_changed_email_html(self, email: str, first_name: str) -> str:
        """Generate password changed confirmation email HTML"""
        name_display = first_name if first_name else "there"
        frontend_url = os.getenv("FRONTEND_URL", "")
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 1px; }}
                .content {{ padding: 40px 30px; }}
                .success-card {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-top: 1px solid #eee; }}
                .security-note {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Changed Successfully</h1>
                </div>
                <div class="content">
                    <p>Hi {name_display},</p>

                    <div class="success-card">
                        <p style="margin: 0;"><strong>Your password has been successfully changed.</strong></p>
                        <p style="margin: 10px 0 0;">You can now log in to your account with your new password.</p>
                    </div>

                    <div class="button-container">
                        <a href="{frontend_url}/admin/login" class="button">Log In Now</a>
                    </div>

                    <div class="security-note">
                        <strong>Didn't make this change?</strong> If you didn't change your password, your account may have been compromised. Please contact our support team immediately.
                    </div>

                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """
