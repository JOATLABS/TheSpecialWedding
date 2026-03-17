# File: app/services/import_service.py

import csv
from fastapi import UploadFile, HTTPException
from app.core.database import mongo
from app.utils.token_generator import generate_token
from app.utils.contact_sanitizer import sanitize_phone, sanitize_email, validate_phone_format, validate_email_format
from datetime import datetime, timezone


class GuestImportService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    async def import_csv(self, file: UploadFile, wedding_id: str):
        if not file.filename or not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        decoded = file.file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded)

        success = 0
        tokens = []

        for row in reader:
            name = row.get("name")
            phone = row.get("phone", None)
            email = row.get("email", None)
            role = row.get("role", "guest")
            plus_one_allowed = row.get("plus_one_allowed", "false").lower() == "true"
            number_of_plus_ones_allowed = int(row.get("number_of_plus_ones_allowed", "0")) if row.get("number_of_plus_ones_allowed", "").isdigit() else 0
            group_id = row.get("group_id", None)

            if not name or len(name.strip()) < 2:
                # TODO log invalid entry
                continue

            # Sanitize phone: strip whitespace and delimiters like (), -, .
            phone = sanitize_phone(phone)
            if phone and not validate_phone_format(phone):
                phone = None  # Drop invalid phone but keep the guest if email exists

            # Sanitize email: strip whitespace and lowercase
            email = sanitize_email(email)
            if email and not validate_email_format(email):
                email = None  # Drop invalid email but keep the guest if phone exists

            # Require at least phone or email for contact
            if not phone and not email:
                # TODO log invalid entry and should not continue because atleast one is required
                continue

            token = generate_token()

            # Ensure logical consistency
            if not plus_one_allowed:
                number_of_plus_ones_allowed = 0

            doc = {
                "wedding_id": wedding_id,
                "name": name.strip(),
                "token": token,
                "phone": phone,
                "email": email,
                "role": role,
                "group_id": group_id,
                "plus_one_allowed": plus_one_allowed,
                "number_of_plus_ones_allowed": number_of_plus_ones_allowed,
                "plus_one_submitted": False,
                "sms_opt_in": True,  # Default to opted-in, guest can opt-out later
                "email_opt_in": True,  # Default to opted-in, guest can opt-out later
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            try:
                await self.collection.insert_one(doc)
                success += 1
                tokens.append(token)
            except Exception:
                continue

        return {"imported": success, "tokens": tokens}
