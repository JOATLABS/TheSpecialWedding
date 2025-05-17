from pymongo import MongoClient
from app.core.config import settings

class MongoConnector:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_guest_collection(self):
        return self.db["guests"]

mongo = MongoConnector(settings.MONGO_URI, settings.MONGO_DB)