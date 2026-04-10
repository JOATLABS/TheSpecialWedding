#!/usr/bin/env python3
"""
Automation Attributes Coverage Analyzer
Analyzes TSX/JSX files to identify automation attribute coverage
"""

import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


def count_interactive_elements(file_path: str) -> int:
    """Count interactive elements in a file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        patterns = [
            r"<button[^>]*>",
            r"<Button[^>]*>",
            r"<input[^>]*>",
            r"<Input[^>]*>",
            r"<select[^>]*>",
            r"<Select[^>]*>",
            r"<form[^>]*>",
            r"<Form[^>]*>",
            r"<Link[^>]*>",
            r"<a[^>]*>",
        ]

        total = 0
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            total += len(matches)

        return total
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0


def count_automation_attributes(file_path: str) -> int:
    """Count automation attributes in a file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        patterns = [
            r"data-testid=",
            r"guestAutomationAttrs",
            r"formAutomationAttrs",
            r"authAutomationAttrs",
            r"createAutomationAttrs",
            r"navigationAttrs",
            r"subscriptionAutomationAttrs",
            r"tenantAutomationAttrs",
        ]

        total = 0
        for pattern in patterns:
            matches = re.findall(pattern, content)
            total += len(matches)

        return total
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0


def get_file_category(file_path: str) -> str:
    """Categorize file based on path"""
    path = Path(file_path)
    path_str = str(path)

    if "admin" in path_str:
        return "Admin"
    elif "components" in path_str:
        return "Components"
    elif "contexts" in path_str:
        return "Contexts"
    elif "forms" in path_str:
        return "Forms"
    elif "vendor" in path_str:
        return "Vendor"
    else:
        return "Other"


def analyze_coverage():
    """Main analysis function"""
    print("=" * 60)
    print("🔍 Automation Attributes Coverage Analysis")
    print("=" * 60)
    print()

    # Get all TSX/JSX files
    tsx_files = glob.glob("app/**/*.tsx", recursive=True)
    jsx_files = glob.glob("app/**/*.jsx", recursive=True)
    all_files = tsx_files + jsx_files

    print(f"📊 Found {len(all_files)} TSX/JSX files")
    print()

    # Analysis data
    categories = {}
    high_priority_files = []
    enhanced_files = []
    total_elements = 0
    total_attributes = 0

    # Analyze each file
    for file_path in sorted(all_files):
        rel_path = os.path.relpath(file_path)
        elements = count_interactive_elements(file_path)
        attributes = count_automation_attributes(file_path)

        if elements > 0:
            category = get_file_category(file_path)
            if category not in categories:
                categories[category] = {"files": 0, "elements": 0, "attributes": 0}

            categories[category]["files"] += 1
            categories[category]["elements"] += elements
            categories[category]["attributes"] += attributes

            total_elements += elements
            total_attributes += attributes

            # Calculate coverage
            coverage = (attributes / elements * 100) if elements > 0 else 0

            if attributes > 0:
                enhanced_files.append((rel_path, elements, attributes, coverage))

            # High priority: 5+ elements with low/no automation
            if elements >= 5 and coverage < 50:
                high_priority_files.append((rel_path, elements, attributes, coverage))

            # Print file status
            if coverage == 0:
                status = "❌ No automation"
            elif coverage < 50:
                status = f"⚠️  Partial ({coverage:.1f}%)"
            else:
                status = f"✅ Good ({coverage:.1f}%)"

            print(f"{rel_path:<50} {elements:>2} elements | {status}")

    print()
    print("📊 Category Summary")
    print("=" * 40)
    for category, data in sorted(categories.items()):
        coverage = (
            (data["attributes"] / data["elements"] * 100) if data["elements"] > 0 else 0
        )
        print(
            f"{category:<12} {data['files']:>2} files | {data['elements']:>3} elements | {coverage:>5.1f}% coverage"
        )

    print()
    print("📈 Overall Statistics")
    print("=" * 30)
    print(
        f"Total files with interactive elements: {len([f for f in all_files if count_interactive_elements(f) > 0])}"
    )
    print(f"Files with automation attributes: {len(enhanced_files)}")
    print(f"Total interactive elements: {total_elements}")
    print(f"Elements with automation attributes: {total_attributes}")

    if total_elements > 0:
        overall_coverage = total_attributes / total_elements * 100
        print(f"Overall coverage: {overall_coverage:.1f}%")

    print()
    print("🎯 High Priority Files (5+ elements, <50% coverage)")
    print("=" * 55)
    if high_priority_files:
        for file_path, elements, attributes, coverage in sorted(
            high_priority_files, key=lambda x: x[1], reverse=True
        ):
            print(f"📄 {file_path:<45} {elements:>2} elements ({coverage:.1f}%)")
    else:
        print("🎉 No high-priority files found! Good coverage overall.")

    print()
    print("✅ Enhanced Files")
    print("=" * 20)
    if enhanced_files:
        print("Files with automation attributes:")
        for file_path, elements, attributes, coverage in sorted(
            enhanced_files, key=lambda x: x[3], reverse=True
        ):
            print(f"✓ {file_path:<45} {coverage:>5.1f}% coverage")

    print()
    print("🚀 Implementation Status")
    print("=" * 25)
    print("✅ Authentication flow - Complete")
    print("✅ Guest management (RSVP, Admin) - Complete")
    print("✅ Detection scripts - Complete")
    print("⏳ Form builder system - Next priority")
    print("⏳ UI component library - Pending")
    print("⏳ Admin dashboard - Pending")

    print()
    print("🎉 Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    analyze_coverage()
