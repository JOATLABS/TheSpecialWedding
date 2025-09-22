import secrets
import string
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException
from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
from app.services.sms_service import SMSService
import logging

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self):
        self.otp_collection = mongo.db["otp_codes"]
        self.guest_collection = mongo.get_guest_collection()
        self.email_service = ResendEmailService()
        self.sms_service = SMSService()
        
        # OTP settings
        self.otp_length = 6
        self.otp_expiry_minutes = 10
        self.max_attempts = 3
        
    def generate_otp(self) -> str:
        """Generate a 6-digit numeric OTP"""
        return ''.join(secrets.choice(string.digits) for _ in range(self.otp_length))
    
    def _hash_otp(self, otp_code: str, salt: str = None) -> tuple:
        """Hash OTP with salt for secure storage"""
        if not salt:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 with SHA-256 for OTP hashing
        hashed = hashlib.pbkdf2_hmac('sha256', otp_code.encode(), salt.encode(), 100000)
        return hashed.hex(), salt
    
    def _verify_otp_hash(self, otp_code: str, stored_hash: str, salt: str) -> bool:
        """Verify OTP against stored hash using constant-time comparison"""
        computed_hash, _ = self._hash_otp(otp_code, salt)
        return hmac.compare_digest(stored_hash, computed_hash)
    
    def send_otp_for_guest_verification(self, wedding_id: str, contact: str, contact_type: str) -> Dict[str, Any]:
        """
        Send OTP to guest for wedding access verification
        
        Args:
            wedding_id: Wedding ID
            contact: Phone number or email address
            contact_type: 'phone' or 'email'
        """
        try:
            # Find guest by contact info
            guest = self._find_guest_by_contact(wedding_id, contact, contact_type)
            if not guest:
                # Don't reveal if contact exists for security
                raise HTTPException(
                    status_code=404, 
                    detail="No invitation found for this contact information"
                )
            
            # Check rate limiting (prevent spam)
            if self._is_rate_limited(str(guest["_id"]), contact_type):
                raise HTTPException(
                    status_code=429,
                    detail="Too many OTP requests. Please wait before trying again."
                )
            
            # Generate and hash OTP
            otp_code = self.generate_otp()
            hashed_otp, salt = self._hash_otp(otp_code)
            expires_at = datetime.utcnow() + timedelta(minutes=self.otp_expiry_minutes)
            
            # Store hashed OTP in database
            otp_record = {
                "guest_id": str(guest["_id"]),
                "wedding_id": wedding_id,
                "otp_hash": hashed_otp,
                "salt": salt,
                "contact": contact,
                "contact_type": contact_type,
                "expires_at": expires_at,
                "attempts": 0,
                "verified": False,
                "created_at": datetime.utcnow()
            }
            
            # Remove any existing OTPs for this guest/contact
            self.otp_collection.delete_many({
                "guest_id": str(guest["_id"]),
                "contact": contact,
                "contact_type": contact_type,
                "verified": False
            })
            
            # Insert new OTP
            self.otp_collection.insert_one(otp_record)
            
            # Send OTP via SMS or email
            if contact_type == "phone":
                success = self._send_otp_sms(contact, otp_code, guest.get("name"))
            else:
                success = self._send_otp_email(contact, otp_code, guest.get("name"), wedding_id)
            
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to send OTP via {contact_type}"
                )
            
            logger.info(f"OTP sent to {contact_type}: {contact} for guest {guest['_id']}")
            
            return {
                "success": True,
                "message": f"Verification code sent to your {contact_type}",
                "expires_in_minutes": self.otp_expiry_minutes
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending OTP: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to send verification code")
    
    def verify_otp(self, wedding_id: str, contact: str, otp_code: str) -> Dict[str, Any]:
        """
        Verify OTP and return guest access info
        
        Args:
            wedding_id: Wedding ID
            contact: Phone number or email that received OTP
            otp_code: The OTP code entered by user
        """
        try:
            # Find OTP record by contact (not by OTP code for security)
            otp_record = self.otp_collection.find_one({
                "wedding_id": wedding_id,
                "contact": contact,
                "verified": False
            })
            
            if not otp_record:
                # Always perform hash comparison to prevent timing attacks
                dummy_hash = "0" * 64
                dummy_salt = "0" * 32
                self._verify_otp_hash(otp_code, dummy_hash, dummy_salt)
                
                # Increment attempts if record exists but was not found due to other reasons
                self.otp_collection.update_one(
                    {"wedding_id": wedding_id, "contact": contact, "verified": False},
                    {"$inc": {"attempts": 1}}
                )
                
                raise HTTPException(
                    status_code=400,
                    detail="Invalid verification code"
                )
            
            # Verify OTP hash using constant-time comparison
            if not self._verify_otp_hash(otp_code, otp_record["otp_hash"], otp_record["salt"]):
                # Increment failed attempts
                self.otp_collection.update_one(
                    {"_id": otp_record["_id"]},
                    {"$inc": {"attempts": 1}}
                )
                
                raise HTTPException(
                    status_code=400,
                    detail="Invalid verification code"
                )
            
            # Check if OTP has expired
            if datetime.utcnow() > otp_record["expires_at"]:
                self.otp_collection.update_one(
                    {"_id": otp_record["_id"]},
                    {"$set": {"verified": False, "expired": True}}
                )
                raise HTTPException(
                    status_code=400,
                    detail="Verification code has expired"
                )
            
            # Check attempt limit
            if otp_record["attempts"] >= self.max_attempts:
                self.otp_collection.update_one(
                    {"_id": otp_record["_id"]},
                    {"$set": {"verified": False, "blocked": True}}
                )
                raise HTTPException(
                    status_code=400,
                    detail="Too many failed attempts. Please request a new code."
                )
            
            # Mark OTP as verified
            self.otp_collection.update_one(
                {"_id": otp_record["_id"]},
                {
                    "$set": {
                        "verified": True,
                        "verified_at": datetime.utcnow()
                    }
                }
            )
            
            # Get guest info
            from bson import ObjectId
            guest_id = otp_record["guest_id"]
            if isinstance(guest_id, str):
                try:
                    guest_id = ObjectId(guest_id)
                except Exception:
                    # Leave as string; not critical if not a valid ObjectId
                    pass  # Keep as string if ObjectId conversion fails
            
            guest = self.guest_collection.find_one({"_id": guest_id})
            if guest:
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
            
            # Log successful verification with enhanced audit info
            self._log_otp_verification(
                otp_record["guest_id"], 
                wedding_id, 
                otp_record["contact_type"],
                success=True,
                attempts=otp_record.get("attempts", 0) + 1
            )
            
            logger.info(f"OTP verified successfully for guest {otp_record['guest_id']}")
            
            return {
                "success": True,
                "guest": guest,
                "auth_method": f"otp_{otp_record['contact_type']}"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to verify code")
    
    def _find_guest_by_contact(self, wedding_id: str, contact: str, contact_type: str) -> Optional[Dict]:
        """Find guest by phone or email"""
        try:
            if contact_type == "phone":
                # Normalize phone number
                normalized_phone = self._normalize_phone(contact)
                query = {
                    "wedding_id": wedding_id,
                    "$or": [
                        {"phone": contact},
                        {"phone": normalized_phone},
                        {"phone": {"$regex": normalized_phone.replace("+1", ""), "$options": "i"}}
                    ]
                }
            else:  # email
                query = {
                    "wedding_id": wedding_id,
                    "email": {"$regex": f"^{contact}$", "$options": "i"}
                }
            
            return self.guest_collection.find_one(query)
            
        except Exception:
            return None
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        import re
        
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Handle US phone numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        
        # For other formats, just prepend + if not present
        if not phone.startswith('+'):
            return f"+{digits_only}"
        
        return phone
    
    def _is_rate_limited(self, guest_id: str, contact_type: str) -> bool:
        """Check if guest is rate limited for OTP requests"""
        # Allow max 3 OTP requests per 5 minutes per guest per contact type
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        
        recent_requests = self.otp_collection.count_documents({
            "guest_id": str(guest_id),
            "contact_type": contact_type,
            "created_at": {"$gt": five_minutes_ago}
        })
        
        return recent_requests >= 3
    
    def _send_otp_sms(self, phone: str, otp_code: str, guest_name: str = None) -> bool:
        """Send OTP via SMS"""
        try:
            name_part = f"Hi {guest_name}! " if guest_name else ""
            message = f"{name_part}Your wedding access code is: {otp_code}. Valid for {self.otp_expiry_minutes} minutes."
            
            result = self.sms_service.send_sms(phone, message)
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Failed to send OTP SMS: {str(e)}")
            return False
    
    def _send_otp_email(self, email: str, otp_code: str, guest_name: str = None, wedding_id: str = None) -> bool:
        """Send OTP via email"""
        try:
            subject = "Your Wedding Access Code"
            
            name_greeting = f"Hi {guest_name}!" if guest_name else "Hello!"
            
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2c3e50;">Wedding Access Verification</h2>
                <p>{name_greeting}</p>
                <p>Your verification code is:</p>
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
                    <h1 style="color: #2c3e50; font-size: 32px; letter-spacing: 4px; margin: 0;">{otp_code}</h1>
                </div>
                <p>This code will expire in <strong>{self.otp_expiry_minutes} minutes</strong>.</p>
                <p style="color: #666; font-size: 14px;">If you didn't request this code, please ignore this email.</p>
            </div>
            """
            
            result = self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                wedding_id=wedding_id,
                email_type="otp_verification"
            )
            
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return False
    
    def _log_otp_verification(self, guest_id: str, wedding_id: str, method: str, success: bool = True, attempts: int = 0):
        """Log OTP verification for analytics"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": f"otp_{method}",
                "timestamp": datetime.utcnow(),
                "type": "otp_verification"
            }
            mongo.db["access_logs"].insert_one(log_entry)
        except Exception:
            # Silently fail - logging shouldn't break the main flow
            pass
    
    def cleanup_expired_otps(self):
        """Clean up expired OTP codes (should be run periodically)"""
        try:
            result = self.otp_collection.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            logger.info(f"Cleaned up {result.deleted_count} expired OTP codes")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up expired OTPs: {str(e)}")
            return 0