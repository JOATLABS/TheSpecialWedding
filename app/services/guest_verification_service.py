from fastapi import HTTPException
from app.core.database import mongo
from typing import Optional, Dict, Any
from datetime import datetime
import re
from app.services.guest_service import GuestService
from app.services.wedding_service import WeddingService

class GuestVerificationService:
    def __init__(self):
        self.guest_service = GuestService()
        self.wedding_service = WeddingService()
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()

    def verify_guest_access(self, slug: str, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify guest access to a wedding based on different authentication methods.
        Returns wedding data and guest info if access is granted.
        """
        try:
            # Get wedding by slug
            wedding = self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check privacy settings
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = privacy_settings.get("privacy_mode", "private")

            # If wedding is public, grant access immediately
            if privacy_mode == "public":
                return {
                    "access": True,
                    "wedding": wedding,
                    "guest": None,
                    "auth_method": "public"
                }

            # If password protected, check password
            if privacy_mode == "password":
                provided_password = verification_data.get("password")
                if provided_password and provided_password == privacy_settings.get("password_protection"):
                    return {
                        "access": True,
                        "wedding": wedding,
                        "guest": None,
                        "auth_method": "password"
                    }

            # For private mode, try different verification methods
            if privacy_mode == "private":
                guest = None

                # Method 1: Token-based verification (highest priority)
                token = verification_data.get("token")
                if token:
                    try:
                        guest = self.guest_service.get_guest_by_token(token, wedding["_id"])
                        if guest:
                            return {
                                "access": True,
                                "wedding": wedding,
                                "guest": guest,
                                "auth_method": "token"
                            }
                    except:
                        pass  # Continue to other methods

                # Method 2: Name and phone verification
                name = verification_data.get("name", "").strip()
                phone = verification_data.get("phone", "").strip()
                
                if name or phone:
                    guest = self._find_guest_by_verification(wedding["_id"], name, phone, privacy_settings)
                    if guest:
                        return {
                            "access": True,
                            "wedding": wedding,
                            "guest": guest,
                            "auth_method": "verification"
                        }

            # Access denied
            return {
                "access": False,
                "wedding": None,
                "guest": None,
                "required_auth": privacy_mode,
                "privacy_settings": {
                    "require_phone_verification": privacy_settings.get("require_phone_verification", True),
                    "require_name_verification": privacy_settings.get("require_name_verification", True),
                    "allow_guest_sharing": privacy_settings.get("allow_guest_sharing", False)
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying guest access: {str(e)}")

    def _find_guest_by_verification(self, wedding_id: str, name: str, phone: str, privacy_settings: Dict) -> Optional[Dict]:
        """Find guest by name and/or phone verification"""
        try:
            # Build query based on privacy settings
            query = {"wedding_id": wedding_id}
            
            require_name = privacy_settings.get("require_name_verification", True)
            require_phone = privacy_settings.get("require_phone_verification", True)
            
            # If both are required, we need both to match
            if require_name and require_phone:
                if not name or not phone:
                    return None
                
                # Normalize phone number for comparison
                normalized_phone = self._normalize_phone(phone)
                
                # Find guest with matching name and phone
                guest = self.guests_collection.find_one({
                    "wedding_id": wedding_id,
                    "$and": [
                        {"name": {"$regex": re.escape(name), "$options": "i"}},
                        {"$or": [
                            {"phone": phone},
                            {"phone": normalized_phone},
                            {"phone": {"$regex": re.escape(normalized_phone.replace("+1", "")), "$options": "i"}}
                        ]}
                    ]
                })
                
            # If only name is required
            elif require_name and not require_phone:
                if not name:
                    return None
                guest = self.guests_collection.find_one({
                    "wedding_id": wedding_id,
                    "name": {"$regex": re.escape(name), "$options": "i"}
                })
                
            # If only phone is required
            elif require_phone and not require_name:
                if not phone:
                    return None
                normalized_phone = self._normalize_phone(phone)
                guest = self.guests_collection.find_one({
                    "wedding_id": wedding_id,
                    "$or": [
                        {"phone": phone},
                        {"phone": normalized_phone},
                        {"phone": {"$regex": re.escape(normalized_phone.replace("+1", "")), "$options": "i"}}
                    ]
                })
                
            # If neither is required (fallback to any match)
            else:
                conditions = []
                if name:
                    conditions.append({"name": {"$regex": re.escape(name), "$options": "i"}})
                if phone:
                    normalized_phone = self._normalize_phone(phone)
                    conditions.append({
                        "$or": [
                            {"phone": phone},
                            {"phone": normalized_phone},
                            {"phone": {"$regex": re.escape(normalized_phone.replace("+1", "")), "$options": "i"}}
                        ]
                    })
                
                if conditions:
                    guest = self.guests_collection.find_one({
                        "wedding_id": wedding_id,
                        "$or": conditions
                    })
                else:
                    return None

            if guest:
                # Convert ObjectId to string and clean up
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
                
                # Log successful verification (for analytics)
                self._log_guest_verification(wedding_id, guest["id"], "verification")
                
            return guest

        except Exception as e:
            # Log error but don't expose details
            print(f"Error in guest verification: {str(e)}")
            return None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Handle US phone numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        elif digits_only.startswith('1') and len(digits_only) > 11:
            return f"+{digits_only}"
        
        # For other formats, just prepend + if not present
        if not phone.startswith('+'):
            return f"+{digits_only}"
        
        return phone

    def _log_guest_verification(self, wedding_id: str, guest_id: str, method: str):
        """Log guest verification for analytics"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": method,
                "timestamp": datetime.utcnow(),
                "type": "guest_verification"
            }
            mongo.db["access_logs"].insert_one(log_entry)
        except Exception:
            # Silently fail - logging shouldn't break the main flow
            pass

    def get_wedding_privacy_info(self, slug: str) -> Dict[str, Any]:
        """Get privacy information about a wedding without granting access"""
        try:
            wedding = self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            privacy_settings = wedding.get("privacy_settings", {})
            
            return {
                "couple_names": wedding.get("couple_names"),
                "privacy_mode": privacy_settings.get("privacy_mode", "private"),
                "requires_password": privacy_settings.get("privacy_mode") == "password",
                "requires_guest_verification": privacy_settings.get("privacy_mode") == "private",
                "verification_requirements": {
                    "require_phone": privacy_settings.get("require_phone_verification", True),
                    "require_name": privacy_settings.get("require_name_verification", True)
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting wedding privacy info: {str(e)}")

    def update_wedding_privacy_settings(self, wedding_id: str, privacy_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update privacy settings for a wedding (admin only)"""
        try:
            # Validate privacy mode
            valid_modes = ["public", "password", "private"]
            privacy_mode = privacy_settings.get("privacy_mode", "private")
            if privacy_mode not in valid_modes:
                raise HTTPException(status_code=400, detail=f"Invalid privacy mode. Must be one of: {valid_modes}")

            # If password mode, ensure password is provided
            if privacy_mode == "password" and not privacy_settings.get("password_protection"):
                raise HTTPException(status_code=400, detail="Password is required for password-protected weddings")

            # Update wedding with new privacy settings
            result = self.weddings_collection.update_one(
                {"_id": wedding_id},
                {
                    "$set": {
                        "privacy_settings": privacy_settings,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": "Privacy settings updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating privacy settings: {str(e)}")