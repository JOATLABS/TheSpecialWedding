from pymongo import MongoClient
from app.core.config import settings

class MongoConnector:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_guest_collection(self):
        return self.db["guests"]
    
    # SAAS collections (backward compatible additions)
    def get_users_collection(self):
        """Extended users collection for wedding planners and vendors"""
        return self.db["users"]
    
    def get_subscription_plans_collection(self):
        """Subscription plans configurable by ROOT_ADMIN"""
        return self.db["subscription_plans"]
    
    def get_saas_content_collection(self):
        """SAAS landing page content configurable by ROOT_ADMIN"""
        return self.db["saas_content"]
    
    def get_ai_usage_collection(self):
        """AI feature usage tracking for billing"""
        return self.db["ai_usage"]
    
    def get_vendors_collection(self):
        """Vendors created by wedding planners"""
        return self.db["vendors"]
    
    def get_wedding_checklist_collection(self):
        """Wedding checklist items that vendors can update"""
        return self.db["wedding_checklist"]
    
    # Existing collections (keeping for backward compatibility)
    def get_admin_users_collection(self):
        """Legacy admin users collection - keeping existing functionality"""
        return self.db["admin_users"]
    
    def get_weddings_collection(self):
        """Weddings collection - existing functionality"""
        return self.db["weddings"]
    
    def get_rsvps_collection(self):
        """RSVPs collection - existing functionality"""
        return self.db["rsvps"]
    
    def get_plus_ones_collection(self):
        """Plus ones collection - existing functionality"""
        return self.db["plus_ones"]
    
    def get_gallery_collection(self):
        """Gallery collection - existing functionality"""
        return self.db["gallery"]
    
    def get_forms_collection(self):
        """Forms collection - custom form builder"""
        return self.db["forms"]
        
    def get_form_responses_collection(self):
        """Form responses collection - form submissions"""
        return self.db["form_responses"]
        
    def get_form_distributions_collection(self):
        """Form distributions collection - email tracking"""
        return self.db["form_distributions"]

mongo = MongoConnector(settings.MONGO_URI, settings.MONGO_DB)