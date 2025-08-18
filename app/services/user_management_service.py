from fastapi import HTTPException
from app.core.database import mongo
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import secrets
import string
from app.utils.auth_utils import get_password_hash
# Email service will be implemented later

class UserManagementService:
    def __init__(self):
        self.users_collection = mongo.db["users"]
        self.invitations_collection = mongo.db["user_invitations"]
        self.weddings_collection = mongo.db["weddings"]
        # Email service will be initialized later

    def generate_invitation_token(self) -> str:
        """Generate a secure invitation token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

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
            print(f"Invitation email would be sent to {email} with token {token}")
            
            return True
            
        except Exception as e:
            print(f"Error sending invitation email: {str(e)}")
            return False

    def list_users(self) -> List[dict]:
        """List all users"""
        try:
            users = list(self.users_collection.find({}, {"password_hash": 0}))  # Exclude password hash
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
        """Public registration for wedding planners"""
        try:
            email = registration_data["email"]
            
            # Check if user already exists
            existing_user = self.users_collection.find_one({"email": email})
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            
            # Create user account
            password_hash = get_password_hash(registration_data["password"])
            user_data = {
                "email": email,
                "password_hash": password_hash,
                "role": registration_data.get("role", "wedding_planner"),
                "first_name": registration_data.get("first_name", ""),
                "last_name": registration_data.get("last_name", ""),
                "company_name": registration_data.get("company_name", ""),
                "subscription_plan_id": registration_data.get("selected_plan_id"),
                "subscription_status": "trial" if registration_data.get("selected_plan_id") else "inactive",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "registration_source": "public_signup"
            }
            
            result = self.users_collection.insert_one(user_data)
            
            # TODO: Send welcome email
            
            return {
                "message": "Registration successful! Welcome to Special Wedding!",
                "user_id": str(result.inserted_id),
                "email": email,
                "role": user_data["role"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")

class EmailService:
    """Placeholder email service - would integrate with actual email provider"""
    def send_email(self, to: str, subject: str, body: str):
        print(f"Email to {to}: {subject}")
        print(body)
        return True