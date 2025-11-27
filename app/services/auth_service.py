from fastapi import HTTPException
from app.core.database import mongo
from app.utils.auth_utils import verify_password, create_access_token
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.admin_collection = mongo.db["admin_users"]
        self.users_collection = mongo.db["users"]

    async def authenticate_user(self, email: str, password: str):
        # Check admin users first (legacy)
        user = await self.admin_collection.find_one({"email": email})
        if user:
            if not verify_password(password, user["hashed_password"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return user

        # Check new users collection (wedding planners, vendors, etc.)
        user = await self.users_collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check password
        if not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if account is active
        if not user.get("is_active", False):
            raise HTTPException(status_code=401, detail="Account is not active. Please contact support.")

        # Check if email is verified for public registrations
        if user.get("registration_source") == "public_signup" and not user.get("email_verified", False):
            raise HTTPException(status_code=401, detail="Please verify your email address before logging in. Check your email for the verification link.")

        return user

    async def login_and_get_token(self, email: str, password: str):
        user = self.authenticate_user(email, password)

        # Update last_login timestamp
        login_time = datetime.utcnow()
        try:
            # Check if user is from legacy admin_users collection
            if user.get("_id") and await self.admin_collection.find_one({"_id": user["_id"]}):
                # Update in admin_users collection
                await self.admin_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"last_login": login_time}}
                )
                logger.info(f"Updated last_login for legacy admin user: {email}")
            else:
                # Update in users collection
                await self.users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"last_login": login_time}}
                )
                logger.info(f"Updated last_login for user: {email}")
        except Exception as e:
            logger.error(f"Failed to update last_login for {email}: {str(e)}")
            # Don't fail the login if last_login update fails

        token_data = {"sub": user["email"], "role": user.get("role", "admin")}
        access_token_expires = timedelta(minutes=60)
        token = create_access_token(data=token_data, expires_delta=access_token_expires)
        return {"access_token": token, "token_type": "bearer"}