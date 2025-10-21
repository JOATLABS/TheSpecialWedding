# scripts/setup_admin_user.py

from passlib.context import CryptContext
import pymongo
import os
import argparse

from dotenv import load_dotenv
load_dotenv()

# Hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

# Load environment variables
PRIMARY_ADMIN_EMAIL = os.getenv("PRIMARY_ADMIN_EMAIL")
if not PRIMARY_ADMIN_EMAIL:
    raise ValueError("PRIMARY_ADMIN_EMAIL not set in environment variables. Please set it.")

def get_password_hash(password):
    return pwd_context.hash(password)

def auto_create_from_env(collection):
    email = os.getenv("PRIMARY_ADMIN_EMAIL")
    password = os.getenv("PRIMARY_ADMIN_PASSWORD")
    role = os.getenv("PRIMARY_ADMIN_ROLE", "admin")

    if not email or not password:
        print("Missing PRIMARY_ADMIN_EMAIL or PRIMARY_ADMIN_PASSWORD in environment.")
        return

    if collection.find_one({"email": email}):
        print(f"Admin {email} already exists.")
        return

    hashed_password = get_password_hash(password)
    collection.insert_one({
        "email": email,
        "hashed_password": hashed_password,
        "role": role
    })
    print(f"Admin user {email} created from environment variables.")

def main():
    parser = argparse.ArgumentParser(description="Admin user setup tool")
    parser.add_argument("--auto-create", action="store_true", help="Auto create user from environment variables")
    args = parser.parse_args()
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongo_name = os.getenv("MONGO_NAME", "wedding")
    # Check if MONGODB_URI is set
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not set in environment variables. Please set it.")
    # Connect to MongoDB
    client = pymongo.MongoClient(mongodb_uri)
    db = client[mongo_name]
    collection = db["admin_users"]

    if args.auto_create:
        auto_create_from_env(collection)
        return

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