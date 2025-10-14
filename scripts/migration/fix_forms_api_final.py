#!/usr/bin/env python3
"""
Fix forms API endpoints for newly converted async methods
"""

import re

def fix_forms_api():
    file_path = "app/api/forms.py"

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Convert get_forms endpoint to async
    content = re.sub(
        r'(@router\.get\("/forms"[^\n]*\n)def get_forms\(',
        r'\1async def get_forms(',
        content
    )

    # 2. Convert get_form_responses endpoint to async
    content = re.sub(
        r'(@router\.get\("/forms/\{form_id\}/responses"[^\n]*\n)def get_form_responses\(',
        r'\1async def get_form_responses(',
        content
    )

    # 3. Add await to form_service.get_forms( calls
    content = re.sub(
        r'(\s+)forms = form_service\.get_forms\(',
        r'\1forms = await form_service.get_forms(',
        content
    )

    # 4. Add await to form_service.get_form_responses( calls
    content = re.sub(
        r'(\s+)return form_service\.get_form_responses\(',
        r'\1return await form_service.get_form_responses(',
        content
    )

    # 5. Check for duplicate_form endpoint and fix if it exists
    content = re.sub(
        r'(@router\.post\("/forms/\{form_id\}/duplicate"[^\n]*\n)def duplicate_form\(',
        r'\1async def duplicate_form(',
        content
    )

    content = re.sub(
        r'(\s+)return form_service\.duplicate_form\(',
        r'\1return await form_service.duplicate_form(',
        content
    )

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fixed forms API endpoints:")
    print("   - Converted get_forms() to async def")
    print("   - Converted get_form_responses() to async def")
    print("   - Added await to form_service method calls")

if __name__ == "__main__":
    fix_forms_api()
