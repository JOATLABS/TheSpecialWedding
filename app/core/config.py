import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Wedding WebApp"
    VERSION: str = "0.1.0"
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "wedding")
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    API_KEY: Optional[str] = os.getenv("API_KEY")
    
    def __init__(self):
        """Validate required environment variables"""
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable is required")
        if not self.API_KEY:
            raise ValueError("API_KEY environment variable is required")

settings = Settings()