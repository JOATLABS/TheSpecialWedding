#!/usr/bin/env python3
"""
End-to-End Twilio RSVP Flow Test Script with OTP

Usage:
    python test_e2e_twilio_rsvp.py
"""

import os
import sys
import requests
import json
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('DB_NAME', 'wedding_webapp')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password')
TEST_RECIPIENT = os.getenv('TEST_RECIPIENT', '')

def get_admin_token(base_url, username, password):
    """Authenticate and get admin token."""
    try:
        response = requests.post(f"{base_url}/admin/auth/token", data={"username": username, "password": password})
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Failed to get admin token: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting admin token: {e}")
        return None

def setup_test_guest(mongo_client):
    """Set up a test guest in the database."""
    db = mongo_client[DB_NAME]
    guest_collection = db['guests']
    guest_collection.delete_one({"name": "E2E Test Guest"})
    guest_data = {
        "name": "E2E Test Guest",
        "phone": TEST_RECIPIENT,
        "token": "e2e-test-token",
        "sms_opt_in": True,
        "plus_one_allowed": True
    }
    result = guest_collection.insert_one(guest_data)
    return result.inserted_id

def request_otp(base_url, guest_id):
    """Request an OTP for the test guest."""
    try:
        response = requests.post(f"{base_url}/otp/request", json={"guest_id": str(guest_id)})
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error requesting OTP: {e}")
        return None

def get_otp_from_db(mongo_client, guest_id):
    """Retrieve the OTP from the database."""
    db = mongo_client[DB_NAME]
    otp_collection = db['otps']
    record = otp_collection.find_one({"guest_id": str(guest_id)})
    return record['otp'] if record else None

def verify_otp(base_url, guest_id, otp):
    """Verify the OTP."""
    try:
        response = requests.post(f"{base_url}/otp/verify", json={"guest_id": str(guest_id), "otp": otp})
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error verifying OTP: {e}")
        return None

def simulate_rsvp_submission(base_url, token):
    """Simulate the guest submitting their RSVP."""
    payload = {
        "attending": ["traditional"],
        "dietary": "None",
        "phone": TEST_RECIPIENT,
        "plus_one": {
            "name": "E2E Test Plus One",
            "phone": "",
            "attending": ["traditional"],
            "dietary": "None"
        }
    }
    try:
        response = requests.post(f"{base_url}/rsvp/invite/{token}/rsvp", json=payload)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error submitting RSVP: {e}")
        return None

def verify_rsvp_in_db(mongo_client, guest_id):
    """Verify that the RSVP was recorded in the database."""
    db = mongo_client[DB_NAME]
    rsvp_collection = db['rsvps']
    plus_one_collection = db['plus_ones']

    rsvp_record = rsvp_collection.find_one({"guest_id": ObjectId(guest_id)})
    plus_one_record = plus_one_collection.find_one({"guest_id": str(guest_id)})

    if rsvp_record and "traditional" in rsvp_record.get("attending", []) and plus_one_record:
        return True
    return False

def main():
    """Main test function."""
    print(" E2E Twilio RSVP Flow Test with OTP")
    print("=" * 50)

    print(f"Connecting to MongoDB at {MONGO_URI}")
    time.sleep(30)  # Wait for the server to start

    try:
        mongo_client = MongoClient(MONGO_URI)
        guest_id = setup_test_guest(mongo_client)

        print("1. Requesting OTP...")
        otp_request_result = request_otp(BASE_URL, guest_id)
        if otp_request_result and "message" in otp_request_result:
            print("   OTP requested successfully.")
        else:
            print(f"   Failed to request OTP: {otp_request_result}")
            sys.exit(1)

        print("\n2. Retrieving OTP from database...")
        otp = get_otp_from_db(mongo_client, guest_id)
        if otp:
            print(f"   OTP retrieved: {otp}")
        else:
            print("   Failed to retrieve OTP from database.")
            sys.exit(1)

        print("\n3. Verifying OTP...")
        otp_verify_result = verify_otp(BASE_URL, guest_id, otp)
        if otp_verify_result and "message" in otp_verify_result:
            print("   OTP verified successfully.")
        else:
            print(f"   Failed to verify OTP: {otp_verify_result}")
            sys.exit(1)

        print("\n4. Simulating RSVP submission...")
        rsvp_result = simulate_rsvp_submission(BASE_URL, "e2e-test-token")
        if rsvp_result and "message" in rsvp_result:
            print("   RSVP submitted successfully.")
        else:
            print(f"   Failed to submit RSVP: {rsvp_result}")
            sys.exit(1)

        print("\n5. Verifying RSVP in database...")
        if verify_rsvp_in_db(mongo_client, guest_id):
            print("   SUCCESS: RSVP and Plus One data verified in the database.")
        else:
            print("   ERROR: RSVP data not found or incorrect in the database.")

    finally:
        if 'mongo_client' in locals():
            mongo_client.close()

    print("\n Test completed!")

if __name__ == "__main__":
    main()
