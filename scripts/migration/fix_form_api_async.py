#!/usr/bin/env python3
"""
Fix form API endpoints to use async/await for form_service calls
"""

import re

def fix_forms_api():
    file_path = "app/api/forms.py"

    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern 1: Convert def to async def for endpoints that call async form_service methods
    endpoints_to_convert = [
        'create_form',
        'get_form',
        'update_form',
        'delete_form',
        'send_form',
        'get_form_analytics',
        'get_form_by_id_public',
        'submit_form_response_public',
        'create_form_from_template',
    ]

    for endpoint in endpoints_to_convert:
        # Match: def endpoint_name(
        # Replace with: async def endpoint_name(
        pattern = rf'(\n@router\.[^\n]+\n)def ({endpoint})\('
        replacement = r'\1async def \2('
        content = re.sub(pattern, replacement, content)

    # Pattern 2: Add await to form_service method calls
    # Match: form_service.create_form(, form_service.get_form(, etc.
    async_methods = [
        'create_form',
        'get_form',
        'update_form',
        'delete_form',
        'send_form',
        'get_form_analytics',
        'submit_form_response',
    ]

    for method in async_methods:
        # Match: form_service.method( or result = form_service.method( or return form_service.method(
        # But NOT: await form_service.method(
        pattern = rf'([^a-zA-Z_])form_service\.({method})\('
        # Find all matches first
        matches = list(re.finditer(pattern, content))

        # Process in reverse to maintain positions
        for match in reversed(matches):
            start = match.start()
            # Check if 'await' is already before this call
            preceding_text = content[max(0, start-20):start]
            if 'await' not in preceding_text or 'await ' not in preceding_text[-10:]:
                # Insert 'await ' before 'form_service'
                insert_pos = match.start(2) - len('form_service.')
                content = content[:insert_pos] + 'await ' + content[insert_pos:]

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✅ Updated {file_path}")
    print(f"   - Converted endpoint functions to async def")
    print(f"   - Added await to form_service method calls")

if __name__ == "__main__":
    fix_forms_api()
