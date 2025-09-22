#!/usr/bin/env python3
"""
Test script to verify the wedding configuration API works with new fields
"""

import requests
import json
import sys

def test_wedding_config_api(base_url="http://localhost:8000", token=None):
 """Test the wedding configuration API endpoints"""
 
 headers = {}
 if token:
 headers["Authorization"] = f"Bearer {token}"
 
 # Test data with all new configuration fields
 test_wedding_update = {
 "rsvp_config": {
 "greeting": "We're getting married! Join us for our special day.",
 "help_text": "If you need assistance with your RSVP, please contact us.",
 "phone_numbers": ["(555) 123-4567", "(555) 987-6543"]
 },
 "registries": [
 {
 "name": "Target",
 "url": "https://www.target.com/gift-registry/123456",
 "color": "bg-red-600"
 },
 {
 "name": "Amazon",
 "url": "https://www.amazon.com/wedding/registry/ABC123",
 "color": "bg-orange-500"
 },
 {
 "name": "Zola",
 "url": "https://www.zola.com/registry/ourwedding",
 "color": "bg-blue-600"
 }
 ],
 "faqs": [
 {
 "question": "What is the dress code?",
 "answer": "Cocktail attire - think dressy but not formal."
 },
 {
 "question": "Is there parking at the venue?",
 "answer": "Yes, free valet parking will be available."
 },
 {
 "question": "Can I bring my children?",
 "answer": "This will be an adults-only celebration."
 }
 ],
 "events": [
 {
 "type": "traditional",
 "date": "2024-06-15",
 "details": {
 "venue_name": "Family Estate",
 "location": "123 Heritage Lane, Lagos, Nigeria",
 "time": "10:00 AM",
 "attire": "Traditional Nigerian attire encouraged"
 }
 },
 {
 "type": "white_wedding",
 "date": "2024-06-16",
 "details": {
 "venue_name": "St. Augustine Cathedral",
 "location": "456 Church Street, Lagos, Nigeria",
 "time": "2:00 PM",
 "attire": "Formal attire"
 }
 },
 {
 "type": "reception",
 "date": "2024-06-16",
 "details": {
 "venue_name": "The Grand Ballroom",
 "location": "789 Event Plaza, Victoria Island, Lagos",
 "time": "6:00 PM",
 "attire": "Cocktail attire"
 }
 }
 ]
 }
 
 print("Wedding Configuration API Test")
 print("=" * 50)
 
 # Step 1: Get list of weddings
 print("\n1. Getting list of weddings...")
 response = requests.get(f"{base_url}/weddings")
 if response.status_code == 200:
 weddings = response.json()
 print(f" Found {len(weddings)} weddings")
 
 if len(weddings) > 0:
 wedding_id = weddings[0]["_id"]
 print(f" Testing with wedding ID: {wedding_id}")
 
 # Step 2: Update wedding with new configuration
 print("\n2. Updating wedding configuration...")
 response = requests.put(
 f"{base_url}/admin/weddings/{wedding_id}",
 json=test_wedding_update,
 headers=headers
 )
 
 if response.status_code == 200:
 print(" Wedding configuration updated successfully")
 else:
 print(f" Failed to update: {response.status_code}")
 print(f" Response: {response.text}")
 
 # Step 3: Verify the update
 print("\n3. Verifying updated configuration...")
 response = requests.get(f"{base_url}/weddings/{wedding_id}")
 if response.status_code == 200:
 updated_wedding = response.json()
 
 # Check each configuration type
 checks = [
 ("RSVP Config", "rsvp_config" in updated_wedding),
 ("Registries", "registries" in updated_wedding and len(updated_wedding["registries"]) > 0),
 ("FAQs", "faqs" in updated_wedding and len(updated_wedding["faqs"]) > 0),
 ("Event Details", 
 "events" in updated_wedding and 
 len(updated_wedding["events"]) > 0 and 
 "details" in updated_wedding["events"][0])
 ]
 
 for check_name, check_result in checks:
 status = "" if check_result else ""
 print(f" {status} {check_name}")
 
 # Print sample data
 if "rsvp_config" in updated_wedding:
 print(f"\n RSVP Greeting: {updated_wedding['rsvp_config']['greeting'][:50]}...")
 if "registries" in updated_wedding and len(updated_wedding["registries"]) > 0:
 print(f" Registries: {', '.join(r['name'] for r in updated_wedding['registries'])}")
 if "faqs" in updated_wedding and len(updated_wedding["faqs"]) > 0:
 print(f" FAQ Count: {len(updated_wedding['faqs'])}")
 if "events" in updated_wedding and len(updated_wedding["events"]) > 0:
 event = updated_wedding["events"][0]
 if "details" in event and event["details"]:
 print(f" First Event Venue: {event['details'].get('venue_name', 'Not set')}")
 else:
 print(f" Failed to get wedding: {response.status_code}")
 else:
 print(" No weddings found to test with")
 else:
 print(f" Failed to get weddings: {response.status_code}")
 print(f" Response: {response.text}")
 
 print("\n" + "=" * 50)
 print("Test complete!")

if __name__ == "__main__":
 # Get command line arguments
 base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
 token = sys.argv[2] if len(sys.argv) > 2 else None
 
 if not token:
 print("Note: No auth token provided. Admin endpoints may fail.")
 print("Usage: python test_wedding_config_api.py [base_url] [token]")
 print()
 
 test_wedding_config_api(base_url, token)