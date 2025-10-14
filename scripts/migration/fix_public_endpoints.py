#!/usr/bin/env python3
"""
Fix public form endpoints to be async
"""

import re

def fix_public_endpoints():
    file_path = "app/api/forms.py"

    with open(file_path, 'r') as f:
        content = f.read()

    # Convert get_public_form to async
    content = re.sub(
        r'(@router\.get\("/public/forms/\{form_id\}"[^\n]*\n)def get_public_form\(',
        r'\1async def get_public_form(',
        content
    )

    # Convert submit_form to async
    content = re.sub(
        r'(@router\.post\("/public/forms/\{form_id\}/submit"[^\n]*\n)def submit_form\(',
        r'\1async def submit_form(',
        content
    )

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fixed public form endpoints:")
    print("   - Converted get_public_form() to async def")
    print("   - Converted submit_form() to async def")

if __name__ == "__main__":
    fix_public_endpoints()
