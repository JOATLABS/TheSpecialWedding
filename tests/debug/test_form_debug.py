#!/usr/bin/env python3
"""
Simple test to debug form deletion
"""
from app.core.database import mongo
import traceback

def test_form_operations():
    form_id = "form_1755811108929"
    
    print(f"=== Testing Form Operations for {form_id} ===")
    
    try:
        # Test 1: Check if form exists
        print("\n1. Checking if form exists...")
        form = mongo.get_forms_collection().find_one({"_id": form_id})
        
        if form:
            print(f"✅ Form found:")
            print(f"   - ID: {form.get('_id')}")
            print(f"   - Name: {form.get('name', 'N/A')}")
            print(f"   - Created by: {form.get('created_by', 'N/A')}")
            print(f"   - Is active: {form.get('is_active', 'N/A')}")
        else:
            print(f"❌ Form with ID '{form_id}' not found")
            return
        
        # Test 2: Try the ROOT_ADMIN delete query
        print("\n2. Testing ROOT_ADMIN delete query...")
        result = mongo.get_forms_collection().update_one(
            {"_id": form_id},
            {"$set": {"is_active": False, "test_update": True}}
        )
        
        print(f"   Matched count: {result.matched_count}")
        print(f"   Modified count: {result.modified_count}")
        
        if result.matched_count > 0:
            print("✅ ROOT_ADMIN query succeeded")
            
            # Restore the form
            mongo.get_forms_collection().update_one(
                {"_id": form_id},
                {"$set": {"is_active": True}, "$unset": {"test_update": 1}}
            )
            print("   Form restored to original state")
        else:
            print("❌ ROOT_ADMIN query failed")
        
        # Test 3: List first few forms
        print("\n3. Listing first 3 forms...")
        forms = list(mongo.get_forms_collection().find({}).limit(3))
        for i, form in enumerate(forms, 1):
            print(f"   {i}. ID: {form.get('_id')}, Active: {form.get('is_active')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_form_operations()