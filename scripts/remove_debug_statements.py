#!/usr/bin/env python3
"""
Remove Debug Statements Script
==============================
Removes console.log and print() debug statements from production code
while preserving console.error for legitimate error handling.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Define paths to search
FRONTEND_PATHS = [
    "app/admin",
    "app/components",
    "app/contexts",
]

BACKEND_PATHS = [
    "app/api",
    "app/services",
    "app/middleware",
    "app/core",
    "app/utils",
]

# Files to exclude from cleaning
EXCLUDE_FILES = [
    "node_modules",
    ".next",
    "venv",
    "__pycache__",
    ".git",
    "tests",
    "scripts/remove_debug_statements.py",  # Don't modify this script!
]


def should_process_file(file_path: Path) -> bool:
    """Check if file should be processed"""
    path_str = str(file_path)

    # Check if path contains any excluded directories
    for exclude in EXCLUDE_FILES:
        if exclude in path_str:
            return False

    return True


def remove_console_logs(file_path: Path) -> Tuple[int, List[str]]:
    """Remove console.log statements from TypeScript/JavaScript files"""

    if not file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
        return 0, []

    if not should_process_file(file_path):
        return 0, []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        original_lines = lines.copy()
        removed_statements = []
        count = 0

        # Pattern to match console.log statements (but not console.error or console.warn)
        console_log_pattern = re.compile(r'^\s*console\.log\([^)]*\);?\s*$')

        # Filter out console.log lines
        new_lines = []
        for i, line in enumerate(lines):
            if console_log_pattern.match(line):
                removed_statements.append(f"  Line {i+1}: {line.strip()}")
                count += 1
            else:
                new_lines.append(line)

        # Only write if changes were made
        if count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        return count, removed_statements

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0, []


def remove_print_statements(file_path: Path) -> Tuple[int, List[str]]:
    """Remove print() statements from Python files"""

    if not file_path.suffix == '.py':
        return 0, []

    if not should_process_file(file_path):
        return 0, []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        removed_statements = []
        count = 0

        # Pattern to match print statements
        print_pattern = re.compile(r'^\s*print\([^)]*\).*$')

        # Filter out print lines
        new_lines = []
        for i, line in enumerate(lines):
            if print_pattern.match(line):
                removed_statements.append(f"  Line {i+1}: {line.strip()}")
                count += 1
            else:
                new_lines.append(line)

        # Only write if changes were made
        if count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        return count, removed_statements

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0, []


def main():
    """Main function to remove debug statements"""

    print("=" * 60)
    print("REMOVING DEBUG STATEMENTS FROM PRODUCTION CODE")
    print("=" * 60)

    base_path = Path.cwd()

    # Statistics
    total_console_logs = 0
    total_print_statements = 0
    files_modified = []

    # Process frontend files (TypeScript/JavaScript)
    print("\n📁 Processing Frontend Files...")
    print("-" * 40)

    for search_path in FRONTEND_PATHS:
        path = base_path / search_path
        if not path.exists():
            continue

        for file_path in path.rglob('*'):
            if file_path.is_file():
                count, statements = remove_console_logs(file_path)
                if count > 0:
                    total_console_logs += count
                    files_modified.append(str(file_path))
                    print(f"✅ {file_path.relative_to(base_path)}: Removed {count} console.log statements")
                    for stmt in statements[:3]:  # Show first 3 removed statements
                        print(f"   {stmt}")
                    if len(statements) > 3:
                        print(f"   ... and {len(statements)-3} more")

    # Process backend files (Python)
    print("\n📁 Processing Backend Files...")
    print("-" * 40)

    for search_path in BACKEND_PATHS:
        path = base_path / search_path
        if not path.exists():
            continue

        for file_path in path.rglob('*.py'):
            if file_path.is_file():
                count, statements = remove_print_statements(file_path)
                if count > 0:
                    total_print_statements += count
                    files_modified.append(str(file_path))
                    print(f"✅ {file_path.relative_to(base_path)}: Removed {count} print statements")
                    for stmt in statements[:3]:  # Show first 3 removed statements
                        print(f"   {stmt}")
                    if len(statements) > 3:
                        print(f"   ... and {len(statements)-3} more")

    # Print summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"✅ Console.log statements removed: {total_console_logs}")
    print(f"✅ Print statements removed: {total_print_statements}")
    print(f"✅ Files modified: {len(files_modified)}")
    print(f"✅ Total debug statements removed: {total_console_logs + total_print_statements}")

    if files_modified:
        print("\n📝 Modified files:")
        for file in files_modified[:10]:  # Show first 10 files
            print(f"   • {Path(file).relative_to(base_path)}")
        if len(files_modified) > 10:
            print(f"   ... and {len(files_modified)-10} more files")

    print("\n" + "=" * 60)
    print("🎉 DEBUG STATEMENT CLEANUP COMPLETE!")
    print("=" * 60)
    print("\n⚠️  IMPORTANT NOTES:")
    print("  • console.error statements were preserved (legitimate error handling)")
    print("  • logger statements were preserved (production logging)")
    print("  • Test files were excluded from cleanup")
    print("  • Remember to test your application after these changes")
    print("\n✨ Your code is now cleaner and more secure!")


if __name__ == "__main__":
    main()