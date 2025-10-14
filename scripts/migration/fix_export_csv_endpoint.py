#!/usr/bin/env python3
"""
Fix the export_form_responses_csv endpoint to be async
"""

import re

def fix_export_endpoint():
    file_path = "app/api/forms.py"

    with open(file_path, 'r') as f:
        content = f.read()

    # Convert export_form_responses_csv to async
    content = re.sub(
        r'(@router\.get\("/forms/\{form_id\}/export/csv"[^\n]*\n)def export_form_responses_csv\(',
        r'\1async def export_form_responses_csv(',
        content
    )

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fixed export_form_responses_csv endpoint")
    print("   - Converted to async def")

if __name__ == "__main__":
    fix_export_endpoint()
