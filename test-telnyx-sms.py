#!/usr/bin/env python3
"""
Telnyx SMS Test Script
Tests sending SMS messages using Telnyx API

Usage:
    python test-telnyx-sms.py
"""

import os
import sys
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
TELNYX_API_KEY = os.getenv('TELNYX_API_KEY', '')
TELNYX_PUBLIC_KEY = os.getenv('TELNYX_PUBLIC_KEY', '')
TELNYX_PHONE_NUMBER = os.getenv('TELNYX_PHONE_NUMBER', '')
TEST_RECIPIENT = os.getenv('TEST_RECIPIENT', '')
TELNYX_PROFILE_ID = os.getenv('TELNYX_PROFILE_ID', '')
TELNYX_TEST_WEBHOOK_URL = os.getenv('TELNYX_TEST_WEBHOOK_URL', '')

# Telnyx API endpoint
TELNYX_API_URL = "https://api.telnyx.com/v2/messages"

def send_test_sms(to_number: str, from_number: str, message: str, api_key: str, profile_id: str = None, webhook_url: str = None) -> dict:
    """
    Send a test SMS using Telnyx API
    
    Args:
        to_number: Recipient phone number in E.164 format (+1234567890)
        from_number: Your Telnyx phone number in E.164 format
        message: The message to send
        api_key: Your Telnyx API key
        profile_id: Messaging profile ID (optional)
        webhook_url: Webhook URL for delivery receipts (optional)
        
    Returns:
        Response from Telnyx API
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": from_number,
        "to": to_number,
        "text": message,
        "type": "SMS",
        "use_profile_webhooks": True
    }
    
    # Add optional parameters if provided
    if profile_id:
        payload["messaging_profile_id"] = profile_id
    
    if webhook_url:
        payload["webhook_url"] = webhook_url
    
    try:
        print(f"\n Sending SMS...")
        print(f"   From: {from_number}")
        print(f"   To: {to_number}")
        print(f"   Message: {message}")
        
        response = requests.post(TELNYX_API_URL, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code in [200, 201, 202]:
            print(f"\n SUCCESS! Message sent successfully")
            print(f"   Message ID: {response_data.get('data', {}).get('id', 'N/A')}")
            print(f"   Status: {response_data.get('data', {}).get('status', 'N/A')}")
            return response_data
        else:
            print(f"\n ERROR: Failed to send message")
            print(f"   Status Code: {response.status_code}")
            print(f"   Error: {json.dumps(response_data, indent=2)}")
            return response_data
            
    except requests.exceptions.RequestException as e:
        print(f"\n REQUEST ERROR: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        print(f"\n UNEXPECTED ERROR: {str(e)}")
        return {"error": str(e)}

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (basic E.164 check)"""
    return phone.startswith('+') and len(phone) >= 10 and phone[1:].isdigit()

def main():
    """Main test function"""
    print(" Telnyx SMS Test Script")
    print("=" * 50)
    
    # Check for credentials
    if not TELNYX_API_KEY:
        api_key = input("Enter your Telnyx API Key: ").strip()
    else:
        api_key = TELNYX_API_KEY
        print(f" Using API Key from environment: {api_key[:20]}...")
    
    if not TELNYX_PHONE_NUMBER:
        from_number = input("Enter your Telnyx phone number (E.164 format, e.g., +1234567890): ").strip()
    else:
        from_number = TELNYX_PHONE_NUMBER
        print(f" Using phone number from environment: {from_number}")
    
    if not TEST_RECIPIENT:
        to_number = input("Enter recipient phone number (E.164 format, e.g., +1234567890): ").strip()
    else:
        to_number = TEST_RECIPIENT
        print(f" Using test recipient from environment: {to_number}")
    
    # Show additional configuration
    if TELNYX_PROFILE_ID:
        print(f" Using messaging profile ID: {TELNYX_PROFILE_ID}")
    
    if TELNYX_TEST_WEBHOOK_URL:
        print(f" Using webhook URL: {TELNYX_TEST_WEBHOOK_URL}")
    
    # Validate phone numbers
    if not validate_phone_number(from_number):
        print(" ERROR: From number must be in E.164 format (e.g., +1234567890)")
        sys.exit(1)
    
    if not validate_phone_number(to_number):
        print(" ERROR: To number must be in E.164 format (e.g., +1234567890)")
        sys.exit(1)
    
    # Create test message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_message = f" Telnyx SMS Test - {timestamp}\n\nIf you received this, Telnyx integration is working!"
    
    # Ask for confirmation
    print(f"\n Ready to send test SMS:")
    print(f"   From: {from_number}")
    print(f"   To: {to_number}")
    print(f"   Message: {test_message}")
    
    confirm = input("\nSend test SMS? (y/n): ").strip().lower()
    if confirm != 'y':
        print(" Test cancelled")
        sys.exit(0)
    
    # Send the SMS
    result = send_test_sms(to_number, from_number, test_message, api_key, TELNYX_PROFILE_ID, TELNYX_TEST_WEBHOOK_URL)
    
    # Additional tests
    if result and not result.get('error'):
        print("\n Additional Test Options:")
        print("1. Send another test message")
        print("2. Test with custom message")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            # Send another test
            test_message = " Second test message from Telnyx!"
            send_test_sms(to_number, from_number, test_message, api_key, TELNYX_PROFILE_ID, TELNYX_TEST_WEBHOOK_URL)
        
        elif choice == '2':
            # Custom message
            custom_msg = input("Enter custom message: ").strip()
            if custom_msg:
                send_test_sms(to_number, from_number, custom_msg, api_key, TELNYX_PROFILE_ID, TELNYX_TEST_WEBHOOK_URL)
    
    print("\n Test completed!")
    print("\n Next steps:")
    print("1. Check that the SMS was received on the test phone")
    print("2. Review the Telnyx dashboard for message status")
    print("3. If successful, update your wedding app configuration")

if __name__ == "__main__":
    main()