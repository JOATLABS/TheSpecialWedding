# app/services/email_service_resend.py

import os
import resend
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging
from app.core.database import mongo
import base64

logger = logging.getLogger(__name__)

class ResendEmailService:
    def __init__(self):
        # Initialize Resend with API key
        api_key = os.getenv("RESEND_API_KEY")
        if api_key:
            resend.api_key = api_key
            self.configured = True
        else:
            logger.warning("Resend email service not configured. RESEND_API_KEY required.")
            self.configured = False
        
        # Database collections
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.email_log_collection = mongo.db["email_logs"]
        self.wedding_collection = mongo.db["weddings"]
    
    def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str, 
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        reply_to: Optional[str] = None,
        wedding_id: Optional[str] = None,
        email_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a single email using Resend"""
        if not self.configured:
            return {"success": False, "error": "Email service not configured"}
        
        try:
            # Use provided from_email or default
            if not from_email:
                from_email = os.getenv("RESEND_FROM_EMAIL", "noreply@thespecialwedding.com")
            
            # Format from address
            if from_name:
                from_address = f"{from_name} <{from_email}>"
            else:
                from_address = from_email
            
            # Prepare email parameters
            params = {
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
            
            # Add optional parameters
            if reply_to:
                params["reply_to"] = reply_to
            
            if attachments:
                params["attachments"] = attachments
            
            # Send email
            from typing import cast, Any
            email_response = resend.Emails.send(cast(Any, params))

            
            # Log the email
            log_entry = {
                "to": to_email,
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name,
                "wedding_id": wedding_id,
                "email_type": email_type,
                "sent_at": datetime.utcnow(),
                "status": "success",
                "resend_id": email_response.get("id"),
                "provider": "resend"
            }
            self.email_log_collection.insert_one(log_entry)
            
            logger.info(f"Email sent successfully to {to_email}, ID: {email_response.get('id')}")
            return {"success": True, "id": email_response.get("id")}
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            
            # Log the failure
            log_entry = {
                "to": to_email,
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name,
                "wedding_id": wedding_id,
                "email_type": email_type,
                "sent_at": datetime.utcnow(),
                "status": "failed",
                "error": str(e),
                "provider": "resend"
            }
            self.email_log_collection.insert_one(log_entry)
            
            return {"success": False, "error": str(e)}
    
    def send_rsvp_invitations(
        self, 
        wedding_slug: str, 
        custom_html: Optional[str] = None,
        custom_subject: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send RSVP invitation emails to guests with email addresses"""
        # Get wedding details
        wedding = self.wedding_collection.find_one({"slug": wedding_slug})
        if not wedding:
            return {"sent": 0, "failed": 0, "error": "Wedding not found"}
        
        # Get custom from_email or use wedding-specific or default
        from_email = wedding.get("reminder_from_email") or os.getenv("RESEND_FROM_EMAIL", "noreply@thespecialwedding.com")
        from_name = wedding.get("couple_names", "TheSpecialWedding")
        
        # Default subject if not provided
        if not custom_subject:
            custom_subject = f"You're Invited - {from_name}"
        
        base_url = os.getenv("FRONTEND_URL", "https://www.thespecialwedding.com")
        sent = 0
        failed = 0
        
        # Get all guests with email addresses
        guests = self.guest_collection.find({"wedding_id": wedding["_id"]})
        
        for guest in guests:
            email = guest.get("email")
            if not email:
                continue
            
            token = guest.get("token")
            if not token:
                continue
            
            # Generate RSVP URL
            rsvp_url = f"{base_url}/{wedding_slug}/invite/{token}"
            
            # Use custom HTML or generate default
            if custom_html:
                # Replace placeholders in custom HTML
                html_content = custom_html.replace("{name}", guest.get("name", "Guest"))
                html_content = html_content.replace("{guest_name}", guest.get("name", "Guest"))
                html_content = html_content.replace("{url}", rsvp_url)
                html_content = html_content.replace("{rsvp_url}", rsvp_url)
                html_content = html_content.replace("{couple_names}", from_name)
                html_content = html_content.replace("{wedding_date}", wedding.get("date", ""))
            else:
                # Generate default invitation HTML
                html_content = self._generate_default_invitation_html(
                    guest_name=guest.get("name", "Guest"),
                    couple_names=from_name,
                    wedding_date=wedding.get("date", ""),
                    rsvp_url=rsvp_url
                )
            
            # Send email
            result = self.send_email(
                to_email=email,
                subject=custom_subject,
                html_content=html_content,
                from_email=from_email,
                from_name=from_name,
                attachments=attachments,
                wedding_id=str(wedding["_id"]),
                email_type="rsvp_invitation"
            )
            
            if result["success"]:
                sent += 1
            else:
                failed += 1
        
        return {"sent": sent, "failed": failed}
    
    def send_reminders(
        self,
        wedding_slug: str,
        event_type: str,
        custom_html: Optional[str] = None,
        custom_subject: Optional[str] = None,
        target_group: str = "all"
    ) -> Dict[str, Any]:
        """Send reminder emails to guests who have RSVP'd"""
        # Get wedding details
        wedding = self.wedding_collection.find_one({"slug": wedding_slug})
        if not wedding:
            return {"sent": 0, "failed": 0, "error": "Wedding not found"}
        
        # Get event details
        event = next((e for e in wedding.get("events", []) if e["type"] == event_type), None)
        if not event:
            return {"sent": 0, "failed": 0, "error": "Event not found"}
        
        # Get custom from_email or use wedding-specific or default
        from_email = wedding.get("reminder_from_email") or os.getenv("RESEND_FROM_EMAIL", "noreply@thespecialwedding.com")
        from_name = wedding.get("couple_names", "TheSpecialWedding")
        
        # Default subject if not provided
        if not custom_subject:
            event_name = event_type.replace("_", " ").title()
            custom_subject = f"Reminder: {event_name} - {event['date']}"
        
        sent = 0
        failed = 0
        
        # Get guests based on target group
        if target_group in ["guests", "all"]:
            guests = self.guest_collection.find({"wedding_id": wedding["_id"]})
            
            for guest in guests:
                # Check if guest has RSVP'd for this event
                rsvp = self.rsvp_collection.find_one({"guest_id": guest["_id"]})
                if not rsvp or event_type not in rsvp.get("attending", []):
                    continue
                
                email = guest.get("email")
                if not email:
                    continue
                
                # Use custom HTML or generate default
                if custom_html:
                    # Replace placeholders
                    html_content = custom_html.replace("{name}", guest.get("name", "Guest"))
                    html_content = html_content.replace("{guest_name}", guest.get("name", "Guest"))
                    html_content = html_content.replace("{event_type}", event_type.replace("_", " ").title())
                    html_content = html_content.replace("{event_date}", event.get("date", ""))
                    html_content = html_content.replace("{venue_name}", event.get("details", {}).get("venue_name", ""))
                    html_content = html_content.replace("{location}", event.get("details", {}).get("location", ""))
                    html_content = html_content.replace("{time}", event.get("details", {}).get("time", ""))
                    html_content = html_content.replace("{couple_names}", from_name)
                else:
                    # Generate default reminder HTML
                    html_content = self._generate_default_reminder_html(
                        guest_name=guest.get("name", "Guest"),
                        event_type=event_type,
                        event_date=event.get("date", ""),
                        event_details=event.get("details", {}),
                        couple_names=from_name
                    )
                
                # Send email
                result = self.send_email(
                    to_email=email,
                    subject=custom_subject,
                    html_content=html_content,
                    from_email=from_email,
                    from_name=from_name,
                    wedding_id=str(wedding["_id"]),
                    email_type="reminder"
                )
                
                if result["success"]:
                    sent += 1
                else:
                    failed += 1
        
        # TODO: Add plus-ones support if needed
        
        return {"sent": sent, "failed": failed}
    
    def get_email_logs(self, wedding_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get email logs, optionally filtered by wedding"""
        query = {}
        if wedding_id:
            query["wedding_id"] = wedding_id
        
        logs = list(self.email_log_collection.find(
            query, 
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit))
        
        return logs
    
    def _generate_default_invitation_html(self, guest_name: str, couple_names: str, wedding_date: str, rsvp_url: str) -> str:
        """Generate default RSVP invitation HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 32px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 18px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .content p {{ margin: 15px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .details {{ background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{couple_names}</h1>
                    <p>Request the honor of your presence</p>
                </div>
                <div class="content">
                    <p>Dear {guest_name},</p>
                    <p>We would be delighted to have you join us as we celebrate our special day!</p>
                    
                    <div class="details">
                        <p style="margin: 0;"><strong>Save the Date:</strong> {wedding_date}</p>
                    </div>
                    
                    <p>Please let us know if you'll be able to attend by clicking the button below:</p>
                    
                    <div class="button-container">
                        <a href="{rsvp_url}" class="button">RSVP NOW</a>
                    </div>
                    
                    <p style="text-align: center; color: #666; font-size: 14px;">
                        If you're receiving this email and would like to receive SMS reminders,<br>
                        you can add your phone number when you RSVP.
                    </p>
                    
                    <p>We look forward to celebrating with you!</p>
                    
                    <p>With love,<br>{couple_names}</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; color: #c8847e;">{rsvp_url}</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; TheSpecialWedding</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _generate_default_reminder_html(self, guest_name: str, event_type: str, event_date: str, event_details: dict, couple_names: str) -> str:
        """Generate default reminder HTML"""
        event_title = event_type.replace('_', ' ').title()
        venue_name = event_details.get('venue_name', 'Venue details coming soon')
        location = event_details.get('location', '')
        time = event_details.get('time', '')
        attire = event_details.get('attire', '')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 18px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .event-card {{ background: #f8f9fa; border-left: 4px solid #c8847e; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .event-card h2 {{ margin: 0 0 20px 0; color: #1e3a5f; }}
                .event-detail {{ margin: 12px 0; display: flex; align-items: flex-start; }}
                .event-detail strong {{ min-width: 100px; color: #555; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Event Reminder</h1>
                    <p>{event_title}</p>
                </div>
                <div class="content">
                    <p>Dear {guest_name},</p>
                    <p>This is a friendly reminder about the upcoming {event_title}. We're looking forward to celebrating with you!</p>
                    
                    <div class="event-card">
                        <h2>Event Details</h2>
                        <div class="event-detail">
                            <strong>Date:</strong>
                            <span>{event_date}</span>
                        </div>
                        {f'''<div class="event-detail">
                            <strong>Time:</strong>
                            <span>{time}</span>
                        </div>''' if time else ''}
                        <div class="event-detail">
                            <strong>Venue:</strong>
                            <span>{venue_name}</span>
                        </div>
                        {f'''<div class="event-detail">
                            <strong>Location:</strong>
                            <span>{location}</span>
                        </div>''' if location else ''}
                        {f'''<div class="event-detail">
                            <strong>Dress Code:</strong>
                            <span>{attire}</span>
                        </div>''' if attire else ''}
                    </div>
                    
                    <p>We can't wait to see you there!</p>
                    
                    <p>With love,<br>{couple_names}</p>
                </div>
                <div class="footer">
                    <p>If you have any questions, please don't hesitate to reach out.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; TheSpecialWedding</p>
                </div>
            </div>
        </body>
        </html>
        """