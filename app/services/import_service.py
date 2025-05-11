# 2. File: app/services/import_service.py
import csv
from fastapi import UploadFile, HTTPException
from app.core.database import mongo
from app.utils.token_generator import generate_token

class GuestImportService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    def import_csv(self, file: UploadFile):
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        decoded = file.file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded)

        success = 0
        tokens = []

        for row in reader:
            name = row.get("name")
            phone = row.get("phone", None)

            if not name or len(name) < 2:
                continue

            token = generate_token()

            doc = {
                "name": name.strip(),
                "phone": phone.strip() if phone else None,
                "token": token,
                "rsvp": None
            }

            try:
                self.collection.insert_one(doc)
                success += 1
                tokens.append(token)
            except Exception:
                continue

        return {"imported": success, "tokens": tokens}
