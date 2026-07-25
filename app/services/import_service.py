# File: app/services/import_service.py

import csv
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile

from app.core.database import mongo
from app.utils.contact_sanitizer import (
    sanitize_email,
    sanitize_phone,
    validate_email_format,
    validate_phone_format,
)
from app.utils.token_generator import generate_token


class GuestImportService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    async def import_csv(self, file: UploadFile, wedding_id: str):
        if not file.filename or not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        decoded = file.file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)

        success = 0
        tokens = []
        warnings = []

        for row_number, row in enumerate(reader, start=2):
            name = row.get("name")
            phone = row.get("phone", None)
            email = row.get("email", None)
            role = row.get("role", "guest")
            plus_one_allowed = row.get("plus_one_allowed", "false").lower() == "true"
            number_of_plus_ones_allowed = (
                int(row.get("number_of_plus_ones_allowed", "0"))
                if row.get("number_of_plus_ones_allowed", "").isdigit()
                else 0
            )
            group_id = row.get("group_id", None)

            if not name or len(name.strip()) < 2:
                warnings.append(
                    f"Row {row_number} was skipped: name is required and must be at least 2 characters."
                )
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
                warnings.append(
                    f"Row {row_number} was skipped: at least one valid phone or email is required."
                )
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
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }

            try:
                await self.collection.insert_one(doc)
                success += 1
                tokens.append(token)
            except Exception:
                continue

        return {"imported": success, "tokens": tokens, "warnings": warnings}
