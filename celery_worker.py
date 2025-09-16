#!/usr/bin/env python3
"""
Celery worker entry point for wedding app
Run with: celery -A celery_worker worker --loglevel=info
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import the Celery app
from app.core.celery_app import celery_app

if __name__ == '__main__':
    celery_app.start()