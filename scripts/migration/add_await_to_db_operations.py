#!/usr/bin/env python3
"""
Script to automatically add 'await' to MongoDB database operations
AND convert functions to 'async def' when they use await.
"""
import re
import sys
from pathlib import Path

# Database operations that need await
DB_OPERATIONS = [
    'insert_one', 'insert_many', 'find_one', 'update_one', 'update_many',
    'delete_one', 'delete_many', 'count_documents', 'replace_one',
    'find_one_and_update', 'find_one_and_delete', 'find_one_and_replace',
]

def process_file(file_path):
    """Add await to database operations AND convert functions to async def"""
    print(f"\n{'='*80}")
    print(f"Processing: {file_path}")
    print('='*80)

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    original_content = ''.join(lines)
    changes_made = []

    # PHASE 1: Add 'await' to database operations
    content = original_content
    for operation in DB_OPERATIONS:
        pattern = r'(?<!await\s)(\s+)([a-zA-Z_][a-zA-Z0-9_\.]*\.' + operation + r'\()'
        def replacer(match):
            indent = match.group(1)
            db_call = match.group(2)
            changes_made.append(f"  + Added await to: {db_call}")
            return f"{indent}await {db_call}"
        content = re.sub(pattern, replacer, content)

    # PHASE 2: Convert cursor iterations
    cursor_pattern = r'(\s+)for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+(cursor|[a-zA-Z_][a-zA-Z0-9_\.]*\.find\()'
    def cursor_replacer(match):
        indent = match.group(1)
        var = match.group(2)
        cursor_expr = match.group(3)
        changes_made.append(f"  + Converted to async for: {var} in {cursor_expr}")
        return f"{indent}async for {var} in {cursor_expr}"
    content = re.sub(cursor_pattern, cursor_replacer, content)

    # PHASE 3: Convert functions to async def if they contain await
    lines = content.split('\n')
    functions_to_convert = set()

    # Find all functions that contain 'await' or 'async for'
    current_function = None
    for i, line in enumerate(lines):
        # Check if entering a function definition (any indentation level)
        func_match = re.match(r'^(\s*)def\s+(\w+)\s*\(', line)
        if func_match:
            indent = func_match.group(1)
            func_name = func_match.group(2)
            current_function = (i, func_name, indent)

        # Check if this line has await or async for
        if current_function and ('await ' in line or 'async for ' in line):
            # Make sure it's not already async
            func_line = lines[current_function[0]]
            if 'async def' not in func_line:
                functions_to_convert.add(current_function)

    # Convert functions to async def
    for line_idx, func_name, indent in sorted(functions_to_convert):
        old_line = lines[line_idx]
        # Replace 'def' with 'async def'
        new_line = old_line.replace(f'{indent}def ', f'{indent}async def ')
        lines[line_idx] = new_line
        changes_made.append(f"  + Converted to async def: {func_name}()")

    content = '\n'.join(lines)

    if content != original_content:
        # Backup original
        backup_path = file_path.parent / f"{file_path.name}.await_backup2"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)

        # Write modified content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ MODIFIED - {len(changes_made)} changes made")
        print(f"   Backup saved to: {backup_path.name}")
        for change in changes_made[:15]:  # Show first 15 changes
            print(change)
        if len(changes_made) > 15:
            print(f"   ... and {len(changes_made) - 15} more changes")
        return True
    else:
        print("✓ No changes needed")
        return False

def main():
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_file():
            files = [target]
        else:
            print(f"Error: {target} is not a file")
            return
    else:
        print("Usage: python3 add_await_to_db_operations.py <file_path>")
        return

    print("MongoDB Async Migration Script v2")
    print("=" * 80)
    print("This script will:")
    print("  1. Add 'await' to database operations")
    print("  2. Convert 'for x in cursor' to 'async for x in cursor'")
    print("  3. Convert 'def func()' to 'async def func()' if it uses await")
    print("  4. Create .await_backup2 files for safety")
    print()

    modified_count = 0
    for file_path in files:
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        if process_file(file_path):
            modified_count += 1

    print("\n" + "="*80)
    print(f"Summary: Modified {modified_count} of {len(files)} files")
    print("="*80)

    if modified_count > 0:
        print("\n⚠️  NEXT STEPS:")
        print("   1. Test the modified file(s)")
        print("   2. Find callers of converted async functions")
        print("   3. Add 'await' to those caller sites")
        print("   4. Repeat step 2-3 recursively up the call chain")

if __name__ == "__main__":
    main()
