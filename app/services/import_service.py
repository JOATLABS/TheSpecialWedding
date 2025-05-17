# File: app/services/import_service.py

import csv
from fastapi import UploadFile, HTTPException
from app.core.database import mongo
from app.utils.token_generator import generate_token

class GuestImportService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    def import_csv(self, file: UploadFile, wedding_id: str):
        if not file.filename.endswith('.csv'):
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
            group_id = row.get("group_id", None)

            if not name or len(name) < 2:
                continue

            token = generate_token()

            doc = {
                "wedding_id": wedding_id,
                "name": name.strip(),
                "token": token,
                "phone": phone.strip() if phone else None,
                "email": email.strip() if email else None,
                "role": role,
                "group_id": group_id,
                "plus_one_allowed": plus_one_allowed
            }

            try:
                self.collection.insert_one(doc)
                success += 1
                tokens.append(token)
            except Exception:
                continue

        return {"imported": success, "tokens": tokens}



# import csv
# from fastapi import UploadFile, HTTPException
# from app.core.database import mongo
# from app.utils.token_generator import generate_token

# class GuestImportService:
#     def __init__(self):
#         self.collection = mongo.get_guest_collection()

#     def import_csv(self, file: UploadFile):
#         if not file.filename.endswith('.csv'):
#             raise HTTPException(status_code=400, detail="File must be a CSV")

#         decoded = file.file.read().decode('utf-8').splitlines()
#         reader = csv.DictReader(decoded)

#         success = 0
#         tokens = []

#         for row in reader:
#             name = row.get("name")
#             phone = row.get("phone", None)
#             allow_plus_ones = self._parse_boolean(row.get("allow_guest_to_add_plus_ones", "false"))
#             number_of_allowed_plus_ones = self._parse_int(row.get("number_of_allowed_plus_ones", "0"))

#             if not name or len(name) < 2:
#                 continue

#             # Validate and adjust plus-one settings
#             if not allow_plus_ones:
#                 number_of_allowed_plus_ones = 0

#             token = generate_token()

#             doc = {
#                 "name": name.strip(),
#                 "phone": phone.strip() if phone else None,
#                 "token": token,
#                 "rsvp": None,
#                 "allow_plus_ones": allow_plus_ones,
#                 "number_of_allowed_plus_ones": number_of_allowed_plus_ones,
#                 "plus_ones": []
#             }

#             try:
#                 self.collection.insert_one(doc)
#                 success += 1
#                 tokens.append(token)
#             except Exception:
#                 continue

#         return {"imported": success, "tokens": tokens}

#     def _parse_boolean(self, value):
#         """Convert string value to boolean"""
#         if isinstance(value, bool):
#             return value
#         return value.lower() in ('yes', 'true', '1', 'y', 't')

#     def _parse_int(self, value):
#         """Convert string value to integer with fallback to 0"""
#         try:
#             return int(value)
#         except (ValueError, TypeError):
#             return 0
