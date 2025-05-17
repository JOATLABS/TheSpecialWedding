# scripts/setup_admin_user.py

from passlib.context import CryptContext
import pymongo
import os
from dotenv import load_dotenv
load_dotenv()

# Hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Load environment variables
PRIMARY_ADMIN_EMAIL = os.getenv("PRIMARY_ADMIN_EMAIL")


def get_password_hash(password):
    return pwd_context.hash(password)

def main():
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client["wedding"]
    collection = db["admin_users"]

    print("Options: [create], [update], [delete]")
    action = input("Action: ").strip().lower()

    email = input("Admin email: ").strip()

    if action not in {"create", "update", "delete"}:
        print("Invalid action.")
        return

    if action == "create":
        if collection.find_one({"email": email}):
            print("Admin already exists.")
            return
        password = input("Admin password: ").strip()
        role = input("Admin role [default: admin]: ").strip() or "admin"
        hashed_password = get_password_hash(password)
        collection.insert_one({
            "email": email,
            "hashed_password": hashed_password,
            "role": role
        })
        print("Admin created successfully.")

    elif action == "update":
        user = collection.find_one({"email": email})
        if not user:
            print("User not found.")
            return
        password = input("New password (leave blank to keep current): ").strip()
        role = input("New role (leave blank to keep current): ").strip()
        updates = {}
        if password:
            updates["hashed_password"] = get_password_hash(password)
        if role:
            updates["role"] = role
        if updates:
            collection.update_one({"email": email}, {"$set": updates})
            print("User updated.")
        else:
            print("No updates provided.")

    elif action == "delete":
        if email == PRIMARY_ADMIN_EMAIL:
            print("You cannot delete the primary developer admin.")
            return
        result = collection.delete_one({"email": email})
        if result.deleted_count:
            print("User deleted.")
        else:
            print("User not found.")

if __name__ == "__main__":
    main()

