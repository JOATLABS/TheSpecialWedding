from datetime import datetime, timedelta, timezone
from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
import os
import logging

logger = logging.getLogger(__name__)


class TrialExpirationService:
    def __init__(self):
        self.users_collection = mongo.get_users_collection()
        self.email_service = ResendEmailService()

    async def get_trial_settings(self) -> dict:
        """Get trial settings from SAAS config"""
        try:
            config = await mongo.db["saas_config"].find_one({"type": "main_config"})
            if config and "trial_settings" in config:
                return config["trial_settings"]
        except Exception:
            pass

        # Return defaults if config not found
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False,
        }

    async def check_and_expire_trials(self) -> dict:
        """Check for expired trials and deactivate accounts"""
        try:
            trial_settings = await self.get_trial_settings()

            if not trial_settings.get("auto_expire_trials", True):
                return {"message": "Auto trial expiration is disabled"}

            now = datetime.now(timezone.utc)
            expired_count = 0

            # Find users with expired trials using Motor async cursor
            cursor = self.users_collection.find(
                {
                    "subscription_status": "trial",
                    "trial_end_date": {"$lt": now},
                    "is_active": True,
                }
            )
            expired_users = await cursor.to_list(length=None)

            for user in expired_users:
                user_id = str(user["_id"])

                # Mark trial as expired in users collection
                # Note: is_active stays True so the planner can still log in
                # and access the billing page to upgrade. Only admin-deactivated
                # accounts should have is_active=False.
                await self.users_collection.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "subscription_status": "expired",
                            "trial_expired_at": now,
                        }
                    },
                )

                # Also update the user_subscriptions collection to keep state consistent
                await mongo.db["user_subscriptions"].update_one(
                    {"user_id": user_id, "status": {"$in": ["trial", "active"]}},
                    {
                        "$set": {
                            "status": "expired",
                            "updated_at": now,
                            "trial_expired_at": now,
                        }
                    },
                )

                # Send trial expired email — wrapped in try/except so a single
                # email failure doesn't break the loop for remaining users
                try:
                    await self.send_trial_expired_email(user)
                except Exception as email_err:
                    logger.error(
                        f"Failed to send expiration email to {user.get('email')}: {email_err}"
                    )

                expired_count += 1

                logger.info(f"Expired trial for user: {user['email']}")

            return {
                "message": "Trial expiration check completed",
                "expired_trials": expired_count,
                "checked_at": now.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in trial expiration check: {str(e)}")
            return {"error": str(e)}

    async def send_trial_warning_emails(self) -> dict:
        """Send warning emails for trials expiring soon.

        Email schedule:
          - Day -7: Single early warning (existing trial_warning_sent flag)
          - Day -3: "3 days left" (trial_countdown_last_day = 3)
          - Day -2: "2 days left" (trial_countdown_last_day = 2)
          - Day -1: "Last day"   (trial_countdown_last_day = 1)
        """
        try:
            trial_settings = await self.get_trial_settings()
            now = datetime.now(timezone.utc)

            warning_count = 0

            # ── 7-day early warning (single shot) ──────────────────
            early_warning_days = trial_settings.get("trial_warning_days", 7)
            early_warning_date = now + timedelta(days=early_warning_days)

            cursor = self.users_collection.find(
                {
                    "subscription_status": "trial",
                    "trial_end_date": {
                        "$lte": early_warning_date,
                        "$gt": now + timedelta(days=3),
                    },
                    "trial_warning_sent": {"$ne": True},
                    "is_active": True,
                    "email_verified": True,
                }
            )
            early_users = await cursor.to_list(length=None)

            for user in early_users:
                days_remaining = (user["trial_end_date"] - now).days
                if await self.send_trial_warning_email(user, days_remaining):
                    await self.users_collection.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"trial_warning_sent": True, "warning_sent_at": now}},
                    )
                    warning_count += 1
                    logger.info(f"Sent 7-day trial warning to: {user['email']}")

            # ── 3-day countdown (daily emails) ─────────────────────
            countdown_date = now + timedelta(days=3)

            cursor = self.users_collection.find(
                {
                    "subscription_status": "trial",
                    "trial_end_date": {"$lte": countdown_date, "$gt": now},
                    "is_active": True,
                    "email_verified": True,
                }
            )
            countdown_users = await cursor.to_list(length=None)

            for user in countdown_users:
                days_remaining = max((user["trial_end_date"] - now).days, 0)
                # Which "day" email should we send? day 3 = first, day 1 = last
                target_day = days_remaining + 1  # e.g. 2 days remaining → day 3 email
                if days_remaining == 0:
                    target_day = 1  # Expiring today

                # Simpler logic: target_day counts down 3→2→1
                # We send if trial_countdown_last_day != target_day
                if user.get("trial_countdown_last_day") == target_day:
                    continue  # Already sent today's email

                if await self.send_trial_warning_email(user, days_remaining):
                    await self.users_collection.update_one(
                        {"_id": user["_id"]},
                        {
                            "$set": {
                                "trial_countdown_last_day": target_day,
                                "trial_countdown_last_sent": now,
                            }
                        },
                    )
                    warning_count += 1
                    logger.info(
                        f"Sent countdown email (day {target_day}, {days_remaining} days left) to: {user['email']}"
                    )

            return {
                "message": "Trial warning check completed",
                "warnings_sent": warning_count,
                "checked_at": now.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in trial warning check: {str(e)}")
            return {"error": str(e)}

    async def send_trial_warning_email(
        self, user: dict, days_remaining: int, max_retries: int = 2
    ) -> bool:
        """Send trial warning email to user with retry logic.

        Args:
            user: User document from MongoDB
            days_remaining: Number of days until trial expires
            max_retries: Maximum retry attempts on transient failures (default 2)

        Returns:
            True if email sent successfully, False otherwise
        """
        import asyncio

        if not self.email_service.configured:
            logger.warning(
                "Email service not configured — skipping trial warning email"
            )
            return False

        email = user.get("email")
        if not email:
            logger.error(
                f"User {user.get('_id')} has no email address — skipping trial warning"
            )
            return False

        first_name = user.get("first_name", "")

        html_content = self._generate_trial_warning_email_html(
            email=email, first_name=first_name, days_remaining=days_remaining
        )

        subject = f"Your Special Wedding Trial Expires in {days_remaining} Day{'s' if days_remaining != 1 else ''}"

        for attempt in range(max_retries + 1):
            try:
                result = await self.email_service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    from_name="Special Wedding Team",
                    email_type="trial_warning",
                )

                if result.get("success", False):
                    return True

                # Non-retryable failure (e.g. invalid email)
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Trial warning email to {email} failed: {error_msg}")
                return False

            except Exception as e:
                if attempt < max_retries:
                    wait_s = (attempt + 1) * 2  # 2s, 4s backoff
                    logger.warning(
                        f"Trial warning email to {email} failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {wait_s}s: {e}"
                    )
                    await asyncio.sleep(wait_s)
                else:
                    logger.error(
                        f"Trial warning email to {email} failed after {max_retries + 1} attempts: {e}"
                    )
                    return False

        return False

    async def send_trial_expired_email(self, user: dict) -> bool:
        """Send trial expired email to user"""
        try:
            if not self.email_service.configured:
                return False

            email = user["email"]
            first_name = user.get("first_name", "")

            html_content = self._generate_trial_expired_email_html(
                email=email, first_name=first_name
            )

            subject = "Your Special Wedding Trial Has Expired - Upgrade to Continue"

            result = await self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                from_name="Special Wedding Team",
                email_type="trial_expired",
            )

            return result.get("success", False)

        except Exception as e:
            logger.error(
                f"Error sending trial expired email to {user.get('email', 'unknown')}: {str(e)}"
            )
            return False

    def _generate_trial_warning_email_html(
        self, email: str, first_name: str, days_remaining: int
    ) -> str:
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
                    <h1> Trial Expiring Soon</h1>
                    <p>Action Required</p>
                </div>
                <div class="content">
                    <p>Hello{f" {first_name}" if first_name else ""}!</p>
                    <p>This is a friendly reminder that your Special Wedding trial will expire in <strong>{days_remaining} day{"s" if days_remaining != 1 else ""}</strong>.</p>
                    <div class="warning-card">
                        <h3 style="margin: 0 0 15px 0; color: #1e3a5f;">Trial Status:</h3>
                        <p style="margin: 8px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 8px 0;"><strong>Days Remaining:</strong> {days_remaining}</p>
                        <p style="margin: 8px 0;"><strong>Action Needed:</strong> Upgrade to continue access</p>
                    </div>

                    <p>To continue managing your weddings and accessing all features, please upgrade to a paid plan:</p>

                    <div class="button-container">
                        <a href="{os.getenv("FRONTEND_URL")}/admin/billing" class="button">Upgrade Now</a>
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
                    <p>Hello{f" {first_name}" if first_name else ""}!</p>
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
                        <a href="{os.getenv("FRONTEND_URL")}/admin/billing" class="button">Choose Your Plan</a>
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
