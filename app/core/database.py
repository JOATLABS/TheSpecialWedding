from pymongo import MongoClient
from app.core.config import settings

class MongoConnector:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_guest_collection(self):
        return self.db["guests"]

    def get_platform_metrics_collection(self):
        collection = self.db["platform_metrics"]
        collection.create_index("snapshot_time")
        return collection

    def get_collection(self, name: str):
        return self.db[name]

mongo = MongoConnector(settings.MONGO_URI, settings.MONGO_DB)
