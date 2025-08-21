from datetime import datetime, timedelta
from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
import os
import logging

logger = logging.getLogger(__name__)

class TrialExpirationService:
    def __init__(self):
        self.users_collection = mongo.db["users"]
        self.email_service = ResendEmailService()
    
    def get_trial_settings(self) -> dict:
        """Get trial settings from SAAS config"""
        try:
            config = mongo.db["saas_config"].find_one({"type": "main_config"})
            if config and "trial_settings" in config:
                return config["trial_settings"]
        except:
            pass
        
        # Return defaults if config not found
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }
    
    def check_and_expire_trials(self) -> dict:
        """Check for expired trials and deactivate accounts"""
        try:
            trial_settings = self.get_trial_settings()
            
            if not trial_settings.get("auto_expire_trials", True):
                return {"message": "Auto trial expiration is disabled"}
            
            now = datetime.utcnow()
            expired_count = 0
            
            # Find users with expired trials
            expired_users = list(self.users_collection.find({
                "subscription_status": "trial",
                "trial_end_date": {"$lt": now},
                "is_active": True
            }))
            
            for user in expired_users:
                # Mark trial as expired
                self.users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "subscription_status": "expired",
                        "is_active": False,
                        "trial_expired_at": now
                    }}
                )
                
                # Send trial expired email
                self.send_trial_expired_email(user)
                expired_count += 1
                
                logger.info(f"Expired trial for user: {user['email']}")
            
            return {
                "message": f"Trial expiration check completed",
                "expired_trials": expired_count,
                "checked_at": now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in trial expiration check: {str(e)}")
            return {"error": str(e)}
    
    def send_trial_warning_emails(self) -> dict:
        """Send warning emails for trials expiring soon"""
        try:
            trial_settings = self.get_trial_settings()
            warning_days = trial_settings.get("trial_warning_days", 7)
            
            now = datetime.utcnow()
            warning_date = now + timedelta(days=warning_days)
            
            # Find users whose trials expire within warning period
            warning_users = list(self.users_collection.find({
                "subscription_status": "trial",
                "trial_end_date": {"$lte": warning_date, "$gt": now},
                "trial_warning_sent": {"$ne": True},
                "is_active": True,
                "email_verified": True
            }))
            
            warning_count = 0
            
            for user in warning_users:
                days_remaining = (user["trial_end_date"] - now).days
                
                # Send warning email
                if self.send_trial_warning_email(user, days_remaining):
                    # Mark warning as sent
                    self.users_collection.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"trial_warning_sent": True, "warning_sent_at": now}}
                    )
                    warning_count += 1
                    logger.info(f"Sent trial warning to user: {user['email']}")
            
            return {
                "message": f"Trial warning check completed",
                "warnings_sent": warning_count,
                "checked_at": now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in trial warning check: {str(e)}")
            return {"error": str(e)}
    
    def send_trial_warning_email(self, user: dict, days_remaining: int) -> bool:
        """Send trial warning email to user"""
        try:
            if not self.email_service.configured:
                return False
            
            email = user["email"]
            first_name = user.get("first_name", "")
            
            html_content = self._generate_trial_warning_email_html(
                email=email,
                first_name=first_name,
                days_remaining=days_remaining
            )
            
            subject = f"⚠️ Your Special Wedding Trial Expires in {days_remaining} Days"
            
            result = self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                from_name="Special Wedding Team",
                email_type="trial_warning"
            )
            
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error sending trial warning email to {user.get('email', 'unknown')}: {str(e)}")
            return False
    
    def send_trial_expired_email(self, user: dict) -> bool:
        """Send trial expired email to user"""
        try:
            if not self.email_service.configured:
                return False
            
            email = user["email"]
            first_name = user.get("first_name", "")
            
            html_content = self._generate_trial_expired_email_html(
                email=email,
                first_name=first_name
            )
            
            subject = "Your Special Wedding Trial Has Expired - Upgrade to Continue"
            
            result = self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                from_name="Special Wedding Team",
                email_type="trial_expired"
            )
            
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error sending trial expired email to {user.get('email', 'unknown')}: {str(e)}")
            return False
    
    def _generate_trial_warning_email_html(self, email: str, first_name: str, days_remaining: int) -> str:
        """Generate trial warning email HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Trial Expiring Soon - Special Wedding</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 0; padding: 0; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); }}
                .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .content {{ padding: 40px 30px; }}
                .warning-card {{ background: linear-gradient(135deg, #fff3cd 0%, #fef3c7 100%); border-radius: 15px; padding: 30px; margin: 25px 0; border-left: 5px solid #f59e0b; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Trial Expiring Soon</h1>
                    <p>Action Required</p>
                </div>
                <div class="content">
                    <p>Hello{f' {first_name}' if first_name else ''}!</p>
                    <p>This is a friendly reminder that your Special Wedding trial will expire in <strong>{days_remaining} day{'s' if days_remaining != 1 else ''}</strong>.</p>
                    
                    <div class="warning-card">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">Trial Status:</h3>
                        <p style="margin: 8px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 8px 0;"><strong>Days Remaining:</strong> {days_remaining}</p>
                        <p style="margin: 8px 0;"><strong>Action Needed:</strong> Upgrade to continue access</p>
                    </div>
                    
                    <p>To continue managing your weddings and accessing all features, please upgrade to a paid plan:</p>
                    
                    <div class="button-container">
                        <a href="{os.getenv('FRONTEND_URL', 'http://localhost:3005')}/admin/billing" class="button">Upgrade Now</a>
                    </div>
                    
                    <p>If you have any questions about our plans or need assistance, please don't hesitate to contact our support team.</p>
                    
                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _generate_trial_expired_email_html(self, email: str, first_name: str) -> str:
        """Generate trial expired email HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Trial Expired - Special Wedding</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 0; padding: 0; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); }}
                .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .content {{ padding: 40px 30px; }}
                .expired-card {{ background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); border-radius: 15px; padding: 30px; margin: 25px 0; border-left: 5px solid #dc3545; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Trial Expired</h1>
                    <p>Upgrade to Continue</p>
                </div>
                <div class="content">
                    <p>Hello{f' {first_name}' if first_name else ''}!</p>
                    <p>Your Special Wedding trial has expired. To continue accessing your wedding planning tools and data, please upgrade to a paid plan.</p>
                    
                    <div class="expired-card">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">Account Status:</h3>
                        <p style="margin: 8px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 8px 0;"><strong>Status:</strong> Trial Expired</p>
                        <p style="margin: 8px 0;"><strong>Access:</strong> Currently Suspended</p>
                    </div>
                    
                    <p><strong>What happens now?</strong></p>
                    <ul>
                        <li>Your account has been temporarily suspended</li>
                        <li>Your data is safe and will be restored when you upgrade</li>
                        <li>Choose a plan that fits your needs and budget</li>
                    </ul>
                    
                    <div class="button-container">
                        <a href="{os.getenv('FRONTEND_URL', 'http://localhost:3005')}/admin/billing" class="button">Choose Your Plan</a>
                    </div>
                    
                    <p>Thank you for trying Special Wedding! We'd love to have you continue as a paid customer.</p>
                    
                    <p>Best regards,<br>The Special Wedding Team</p>
                </div>
                <div class="footer">
                    <p>&copy; Special Wedding - Professional Wedding Planning Platform</p>
                </div>
            </div>
        </body>
        </html>
        """