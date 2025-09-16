#!/usr/bin/env python3
"""
Test script to create a notification and test email sending
"""
import os
import sys
import asyncio
from datetime import datetime
from bson import ObjectId

# Add the app directory to Python path
sys.path.insert(0, '/home/emmanuel/Desktop/WeddingApp/WeddingWebApp')

from app.core.database import mongo
from app.services.notification_service import NotificationService

async def test_notification_email():
    """Test creating and sending a notification via email"""

    # Initialize notification service
    notification_service = NotificationService()

    print("🔧 Testing notification email system...")

    # Create a test notification
    notification_data = {
        "title": "🧪 Test Email Notification",
        "message": "This is a test notification to verify that the email integration is working correctly with Celery and Redis. If you receive this email, the system is functioning properly!",
        "type": "info",
        "target_audience": "root_admin",
        "priority": "high",
        "is_dismissible": True
    }

    print("📝 Creating test notification...")

    try:
        # Create notification
        result = await notification_service.create_notification(
            notification_data,
            created_by="test_script@system.local"
        )

        notification_id = result["id"]
        print(f"✅ Notification created successfully: {notification_id}")

        # Send the notification (this should trigger email via Celery)
        print("📧 Sending notification via email...")
        send_result = await notification_service.send_notification(notification_id)

        print(f"✅ Email sending result: {send_result}")
        print(f"📊 Recipients: {send_result.get('recipients', 0)}")
        print(f"📬 Emails queued: {send_result.get('emails_queued', 0)}")
        print(f"❌ Emails failed: {send_result.get('emails_failed', 0)}")

        # Also test the _queue_admin_email function directly
        print("\n🔧 Testing direct admin email queue...")
        await notification_service._queue_admin_email({
            "title": "🧪 Direct Admin Email Test",
            "message": "This is a direct test of the admin email queuing system.",
            "type": "info",
            "source": "test_script",
            "email": "test@example.com",
            "name": "Test User",
            "company": "Test Company",
            "phone": "123-456-7890"
        })
        print("✅ Direct admin email queued successfully")

    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_notification_email())