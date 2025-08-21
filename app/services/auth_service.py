from fastapi import HTTPException
from app.core.database import mongo
from app.utils.auth_utils import verify_password, create_access_token
from datetime import timedelta

class AuthService:
    def __init__(self):
        self.admin_collection = mongo.db["admin_users"]
        self.users_collection = mongo.db["users"]

    def authenticate_user(self, email: str, password: str):
        # Check admin users first (legacy)
        user = self.admin_collection.find_one({"email": email})
        if user:
            if not verify_password(password, user["hashed_password"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return user
        
        # Check new users collection (wedding planners, vendors, etc.)
        user = self.users_collection.find_one({"email": email})
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

    def login_and_get_token(self, email: str, password: str):
        user = self.authenticate_user(email, password)
        token_data = {"sub": user["email"], "role": user.get("role", "admin")}
        access_token_expires = timedelta(minutes=60)
        token = create_access_token(data=token_data, expires_delta=access_token_expires)
        return {"access_token": token, "token_type": "bearer"}