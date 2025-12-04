#!/usr/bin/env python3
"""
MongoDB Connection Test Script

Usage:
    python test_db_connection.py
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')

def main():
    """Main test function."""
    print(" MongoDB Connection Test")
    print("=" * 50)
    print(f"Attempting to connect to: {MONGO_URI}")

    try:
        # Set a short server selection timeout to fail fast
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        print("SUCCESS: MongoDB connection established successfully.")
    except ConnectionFailure as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
