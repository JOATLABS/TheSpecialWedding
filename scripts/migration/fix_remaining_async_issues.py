#!/usr/bin/env python3
"""
Fix remaining async/await issues in form_service.py
- Convert methods that call async methods to async
- Add await to async method calls
- Convert synchronous find() to async iteration
"""

import re

def fix_form_service():
    file_path = "app/services/form_service.py"

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Convert duplicate_form to async
    content = re.sub(
        r'(\n\s+)def duplicate_form\(',
        r'\1async def duplicate_form(',
        content
    )

    # 2. Convert get_form_responses to async
    content = re.sub(
        r'(\n\s+)def get_form_responses\(',
        r'\1async def get_form_responses(',
        content
    )

    # 3. Convert get_forms to async (it's used by API endpoints)
    content = re.sub(
        r'(\n\s+)def get_forms\(',
        r'\1async def get_forms(',
        content
    )

    # 4. Add await to self.get_form( calls within these methods
    # Find all self.get_form( that don't have await before them
    lines = content.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        # Check if line has self.get_form( or self.create_form( without await
        if 'self.get_form(' in line and 'await' not in line and 'def get_form' not in line:
            # Add await before self.get_form
            line = line.replace('self.get_form(', 'await self.get_form(')
        elif 'self.create_form(' in line and 'await' not in line and 'def create_form' not in line:
            # Add await before self.create_form
            line = line.replace('self.create_form(', 'await self.create_form(')
        elif 'self.get_form_responses(' in line and 'await' not in line and 'def get_form_responses' not in line:
            # Add await before self.get_form_responses
            line = line.replace('self.get_form_responses(', 'await self.get_form_responses(')

        new_lines.append(line)

    content = '\n'.join(new_lines)

    # 5. Convert synchronous find() to async for in get_forms
    # Change: forms = list(self.forms_collection.find(query).sort("created_at", -1))
    # To: forms = await self.forms_collection.find(query).sort("created_at", -1).to_list(length=None)
    content = re.sub(
        r'forms = list\(self\.forms_collection\.find\(query\)\.sort\("created_at", -1\)\)',
        r'forms = await self.forms_collection.find(query).sort("created_at", -1).to_list(length=None)',
        content
    )

    # 6. Convert synchronous find() in get_form_responses
    # Change: responses = list(self.responses_collection.find(...)
    # To: responses = await self.responses_collection.find(...).to_list(length=None)
    content = re.sub(
        r'responses = list\(self\.responses_collection\.find\(\s*\n\s*\{"form_id": form_id\}\s*\n\s*\)\.sort\("submitted_at", -1\)\)',
        r'responses = await self.responses_collection.find(\n                {"form_id": form_id}\n            ).sort("submitted_at", -1).to_list(length=None)',
        content
    )

    # 7. Convert synchronous find() in get_form_analytics (line 714)
    content = re.sub(
        r'distributions = list\(self\.distributions_collection\.find\(\{"form_id": form_id\}\)\)',
        r'distributions = await self.distributions_collection.find({"form_id": form_id}).to_list(length=None)',
        content
    )

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fixed form_service.py:")
    print("   - Converted duplicate_form() to async")
    print("   - Converted get_forms() to async")
    print("   - Converted get_form_responses() to async")
    print("   - Added await to all async method calls")
    print("   - Converted synchronous find() to async .to_list()")

if __name__ == "__main__":
    fix_form_service()
