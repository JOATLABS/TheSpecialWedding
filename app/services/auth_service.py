from fastapi import HTTPException
from app.core.database import mongo
from app.utils.auth_utils import verify_password, create_access_token
from datetime import timedelta

class AuthService:
    def __init__(self):
        self.collection = mongo.db["admin_users"]

    def authenticate_user(self, email: str, password: str):
        user = self.collection.find_one({"email": email})
        if not user or not verify_password(password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user

    def login_and_get_token(self, email: str, password: str):
        user = self.authenticate_user(email, password)
        token_data = {"sub": user["email"], "role": user.get("role", "admin")}
        token = create_access_token(data=token_data, expires_delta=timedelta(minutes=60))
        return {"access_token": token, "token_type": "bearer"}