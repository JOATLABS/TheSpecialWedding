from fastapi import HTTPException
from app.core.database import mongo
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import secrets
import string
import os
import requests
from app.utils.auth_utils import get_password_hash, verify_password
from app.services.email_service_resend import ResendEmailService
from app.core.events import event_bus, EventFactory

class UserManagementService:
    def __init__(self):
        self.users_collection = mongo.db["users"]
        self.invitations_collection = mongo.db["user_invitations"]
        self.weddings_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()

    def generate_invitation_token(self) -> str:
        """Generate a secure invitation token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    def get_trial_settings(self) -> dict:
        """Get trial settings from SAAS config"""
        try:
            # Try to get from SAAS config API
            base_url = os.getenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
            response = requests.get(f"{base_url}/saas/trial-settings", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # Fallback to direct database query
        try:
            config = mongo.db["saas_config"].find_one({"type": "main_config"})
            if config and "trial_settings" in config:
                return config["trial_settings"]
        except:
            pass
        
        # Return defaults if all else fails
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }
    
    def check_previous_trial_usage(self, email: str) -> bool:
        """Check if email has been used for a trial before"""
        try:
            # Check current users collection for trial usage
            existing_trial = self.users_collection.find_one({
                "email": email,
                "$or": [
                    {"subscription_status": {"$in": ["trial", "expired"]}},
                    {"previous_trial_used": True}
                ]
            })
            
            # Check deleted users collection if it exists
            deleted_users = mongo.db.get("deleted_users", None)
            if deleted_users:
                deleted_trial = deleted_users.find_one({
                    "email": email,
                    "$or": [
                        {"subscription_status": {"$in": ["trial", "expired"]}},
                        {"previous_trial_used": True}
                    ]
                })
                if deleted_trial:
                    return True
            
            return existing_trial is not None
        except:
            return False

    def invite_user(self, invite_data: dict, inviter_email: str) -> dict:
        """Invite a new user to the platform"""
        try:
            email = invite_data["email"]
            role = invite_data["role"]
            
            # Check if user already exists
            existing_user = self.users_collection.find_one({"email": email})
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            
            # Check for pending invitation
            existing_invitation = self.invitations_collection.find_one({
                "email": email, 
                "status": "pending",
                "expires_at": {"$gt": datetime.utcnow()}
            })
            if existing_invitation:
                raise HTTPException(status_code=400, detail="Pending invitation already exists for this email")
            
            # Create invitation record
            invitation_token = self.generate_invitation_token()
            invitation = {
                "email": email,
                "role": role,
                "token": invitation_token,
                "invite_data": invite_data,
                "invited_by": inviter_email,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=7),
                "status": "pending"
            }
            
            self.invitations_collection.insert_one(invitation)
            
            # Send invitation email
            self.send_invitation_email(email, invitation_token, role, invite_data.get("company_name"))
            
            return {
                "message": f"Invitation sent to {email}",
                "invitation_id": str(invitation["_id"]),
                "expires_at": invitation["expires_at"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error sending invitation: {str(e)}")

    def send_invitation_email(self, email: str, token: str, role: str, company_name: str = None):
        """Send invitation email to user"""
        try:
            subject = "Invitation to Join Special Wedding Platform"
            setup_url = f"http://localhost:3003/setup-account?token={token}"
            
            # Create email content based on role
            if role == "wedding_planner":
                role_description = "Wedding Planner"
                welcome_message = f"You've been invited to join Special Wedding as a {role_description}."
                if company_name:
                    welcome_message += f" You'll be managing weddings for {company_name}."
            elif role == "vendor":
                role_description = "Vendor"
                welcome_message = f"You've been invited to join Special Wedding as a {role_description}."
            else:
                role_description = role.replace("_", " ").title()
                welcome_message = f"You've been invited to join Special Wedding as a {role_description}."
            
            body = f"""
            <html>
            <body>
                <h2>Welcome to Special Wedding!</h2>
                <p>{welcome_message}</p>
                <p>To complete your account setup, please click the link below:</p>
                <p><a href="{setup_url}" style="background-color: #1e3a5f; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Set Up My Account</a></p>
                <p>This invitation will expire in 7 days.</p>
                <p>If you have any questions, please contact support.</p>
                <hr>
                <p><small>This is an automated message from Special Wedding Platform.</small></p>
            </body>
            </html>
            """
            
            # Note: This would integrate with your email service
            # For now, we'll just log it or use a simple email service
            # Send invitation email using ResendEmailService
            if self.email_service.configured:
                base_url = os.getenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:3000")
                setup_url = f"{base_url}/setup-account?token={token}"
                
                # Create professional invitation email
                html_content = self._generate_invitation_email_html(
                    email=email,
                    role=role,
                    company_name=company_name,
                    setup_url=setup_url,
                    invited_by=invited_by
                )
                
                subject = f"Welcome to Special Wedding - Complete Your Account Setup"
                
                result = self.email_service.send_email(
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
            
        except Exception as e:
            # Log error without exposing sensitive information
            return False

    def list_users(self, role_filter: Optional[str] = None) -> List[dict]:
        """List all users with optional role filter"""
        try:
            query = {}
            if role_filter:
                query["role"] = role_filter
            
            users = list(self.users_collection.find(query, {"password_hash": 0, "password": 0}))  # Exclude password fields
            
            # Convert ObjectId to string for JSON serialization
            for user in users:
                user["_id"] = str(user["_id"])
            
            return users
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing users: {str(e)}")

    def get_user(self, user_id: str) -> dict:
        """Get user by ID"""
        try:
            user = self.users_collection.find_one({"_id": user_id}, {"password_hash": 0})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return user
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving user: {str(e)}")

    def update_user(self, user_id: str, update_data: dict) -> dict:
        """Update user details"""
        try:
            # Remove protected fields
            protected_fields = ["_id", "email", "password_hash", "created_at"]
            for field in protected_fields:
                update_data.pop(field, None)
            
            # Add update timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            result = self.users_collection.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {"message": "User updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")

    def delete_user(self, user_id: str) -> dict:
        """Delete user"""
        try:
            # Get user first to check if they exist and get their email
            user = self.users_collection.find_one({"_id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check if user has assigned weddings
            assigned_weddings = list(self.weddings_collection.find({"assigned_planner_email": user["email"]}))
            if assigned_weddings:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete user: {len(assigned_weddings)} weddings are assigned to this user"
                )
            
            # Delete user
            result = self.users_collection.delete_one({"_id": user_id})
            
            return {"message": "User deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

    def assign_wedding_to_planner(self, user_id: str, wedding_id: str) -> dict:
        """Assign a wedding to a planner"""
        try:
            # Get user to verify they exist and are a planner
            user = self.users_collection.find_one({"_id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if user["role"] != "wedding_planner":
                raise HTTPException(status_code=400, detail="User is not a wedding planner")
            
            # Update wedding with assigned planner
            result = self.weddings_collection.update_one(
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

    def unassign_wedding_from_planner(self, user_id: str, wedding_id: str) -> dict:
        """Unassign a wedding from a planner"""
        try:
            # Update wedding to remove assigned planner
            result = self.weddings_collection.update_one(
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

    def suspend_user(self, user_id: str) -> dict:
        """Suspend user account"""
        try:
            result = self.users_collection.update_one(
                {"_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {"message": "User suspended successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error suspending user: {str(e)}")

    def activate_user(self, user_id: str) -> dict:
        """Activate user account"""
        try:
            result = self.users_collection.update_one(
                {"_id": user_id},
                {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {"message": "User activated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error activating user: {str(e)}")

    def validate_invitation_token(self, token: str) -> dict:
        """Validate invitation token and return invitation details"""
        try:
            invitation = self.invitations_collection.find_one({
                "token": token,
                "status": "pending",
                "expires_at": {"$gt": datetime.utcnow()}
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

    def complete_account_setup(self, token: str, password: str) -> dict:
        """Complete account setup with password"""
        try:
            # Validate token first
            invitation = self.invitations_collection.find_one({
                "token": token,
                "status": "pending",
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if not invitation:
                raise HTTPException(status_code=404, detail="Invalid or expired invitation token")
            
            # Check if user already exists
            existing_user = self.users_collection.find_one({"email": invitation["email"]})
            if existing_user:
                raise HTTPException(status_code=400, detail="User account already exists")
            
            # Create user account
            password_hash = get_password_hash(password)
            user_data = {
                "email": invitation["email"],
                "password_hash": password_hash,
                "role": invitation["role"],
                "company_name": invitation["invite_data"].get("company_name", ""),
                "subscription_plan_id": invitation["invite_data"].get("subscription_plan_id"),
                "subscription_status": "inactive",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "setup_completed_at": datetime.utcnow()
            }
            
            result = self.users_collection.insert_one(user_data)
            
            # Mark invitation as completed
            self.invitations_collection.update_one(
                {"token": token},
                {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
            )
            
            return {
                "message": "Account setup completed successfully",
                "user_id": str(result.inserted_id),
                "email": invitation["email"],
                "role": invitation["role"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error completing account setup: {str(e)}")

    def register_wedding_planner(self, registration_data: dict) -> dict:
        """Public registration for wedding planners with email verification"""
        try:
            email = registration_data["email"]
            
            # Get trial settings from SAAS config
            trial_settings = self.get_trial_settings()
            
            # Check if user already exists
            existing_user = self.users_collection.find_one({"email": email})
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            
            # Check for previous trial usage if not allowed
            if not trial_settings.get("allow_multiple_trials", False):
                if self.check_previous_trial_usage(email):
                    raise HTTPException(
                        status_code=400, 
                        detail="Free trial has already been used with this email address. Please contact support for assistance."
                    )
            
            # Generate email verification token
            verification_token = self.generate_invitation_token()
            verification_expires = datetime.utcnow() + timedelta(hours=48)  # 48 hours to verify
            
            # Create user account (inactive until email verification)
            password_hash = get_password_hash(registration_data["password"])
            trial_days = trial_settings.get("default_trial_days", 30)
            trial_end_date = datetime.utcnow() + timedelta(days=trial_days)
            
            user_data = {
                "email": email,
                "password_hash": password_hash,
                "role": registration_data.get("role", "wedding_planner"),
                "first_name": registration_data.get("first_name", ""),
                "last_name": registration_data.get("last_name", ""),
                "company_name": registration_data.get("company_name", ""),
                "subscription_plan_id": registration_data.get("selected_plan_id"),
                "subscription_status": "trial",
                "trial_end_date": trial_end_date,
                "trial_warning_sent": False,
                "is_active": False,  # Account inactive until email verification
                "email_verified": False,
                "email_verification_token": verification_token,
                "verification_token_expires": verification_expires,
                "created_at": datetime.utcnow(),
                "registration_source": "public_signup"
            }
            
            result = self.users_collection.insert_one(user_data)
            
            # Send email verification email
            if self.email_service.configured:
                # Create verification URL
                base_url = os.getenv("FRONTEND_URL", "http://localhost:3005")
                verification_url = f"{base_url}/verify-email/{verification_token}"
                
                html_content = self._generate_verification_email_html(
                    email=email,
                    first_name=user_data.get("first_name", ""),
                    verification_url=verification_url
                )
                
                subject = "Verify Your Email - Special Wedding"
                
                self.email_service.send_email(
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

    def verify_email(self, token: str) -> dict:
        """Verify email address using verification token"""
        try:
            # Find user with matching verification token
            user = self.users_collection.find_one({
                "email_verification_token": token,
                "email_verified": False
            })
            
            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired verification token")
            
            # Check if token has expired
            if user.get("verification_token_expires") and user["verification_token_expires"] < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Verification token has expired. Please register again.")
            
            # Update user to verified status
            self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "email_verified": True,
                        "is_active": True,
                        "verified_at": datetime.utcnow()
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
                
                self.email_service.send_email(
                    to_email=user["email"],
                    subject=subject,
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="welcome_email"
                )
            
            return {
                "message": "Email verified successfully! Your account is now active. You can log in.",
                "email": user["email"],
                "verified_at": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying email: {str(e)}")

    def _generate_invitation_email_html(self, email: str, role: str, company_name: str, setup_url: str, invited_by: str) -> str:
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
                        <a href="{os.getenv('NEXT_PUBLIC_API_BASE_URL', 'http://localhost:3000')}/admin" class="button">Start Planning</a>
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
    async def change_password(self, user_email: str, current_password: str, new_password: str) -> dict:
        """Change user password after verifying current password"""
        try:
            # Find the user
            user = self.users_collection.find_one({"email": user_email})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify current password
            if not verify_password(current_password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            
            # Hash new password
            new_password_hash = get_password_hash(new_password)
            
            # Update password in database
            result = self.users_collection.update_one(
                {"email": user_email},
                {
                    "$set": {
                        "password_hash": new_password_hash,
                        "password_changed_at": datetime.utcnow()
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
                "changed_at": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error changing password: {str(e)}")

    async def change_email(self, current_email: str, new_email: str, password: str) -> dict:
        """Change user email address after password verification"""
        try:
            # Find the user
            user = self.users_collection.find_one({"email": current_email})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify password
            if not verify_password(password, user["password_hash"]):
                raise HTTPException(status_code=400, detail="Password is incorrect")
            
            # Check if new email is already in use
            existing_user = self.users_collection.find_one({"email": new_email})
            if existing_user:
                raise HTTPException(status_code=400, detail="Email address is already in use")
            
            # Generate email verification token for new email
            verification_token = self.generate_invitation_token()
            verification_expires = datetime.utcnow() + timedelta(hours=24)  # 24 hours to verify
            
            # Update user with new email (but keep it unverified until verification)
            result = self.users_collection.update_one(
                {"email": current_email},
                {
                    "$set": {
                        "pending_email": new_email,
                        "email_change_token": verification_token,
                        "email_change_token_expires": verification_expires,
                        "email_change_requested_at": datetime.utcnow()
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
            user = self.users_collection.find_one({
                "email_change_token": token
            })
            
            if not user:
                raise HTTPException(status_code=400, detail="Invalid or expired verification token")
            
            # Check if token has expired
            if user.get("email_change_token_expires") and user["email_change_token_expires"] < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Verification token has expired. Please request a new email change.")
            
            # Update user email to the new email
            old_email = user["email"]
            new_email = user["pending_email"]
            
            self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "email": new_email,
                        "email_changed_at": datetime.utcnow()
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
                "changed_at": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying email change: {str(e)}")

    def get_user_profile(self, user_email: str) -> dict:
        """Get user profile information"""
        try:
            user = self.users_collection.find_one(
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
            user = self.users_collection.find_one({"email": user_email})
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

            if not update_data:
                raise HTTPException(status_code=400, detail="No valid profile data provided")

            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow()

            # Update user profile
            result = self.users_collection.update_one(
                {"email": user_email},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Profile update failed")

            # Emit profile updated event
            await event_bus.emit(EventFactory.create_user_profile_updated_event(
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
