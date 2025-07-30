#!/bin/bash

# Script to remove Claude signatures from commit messages
# This will rewrite Git history, so use with caution!

echo "This script will remove Claude signatures from all commit messages."
echo "WARNING: This will rewrite Git history!"
echo "Make sure you have a backup and coordinate with your team."
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Create a backup branch
git branch backup-before-clean-$(date +%Y%m%d-%H%M%S)
echo "Created backup branch"

# Use git filter-branch to rewrite commit messages
git filter-branch --msg-filter '
    # Remove the Claude signature lines
    sed -e "/🤖 Generated with \[Claude Code\]/d" \
        -e "/Co-Authored-By: Claude <noreply@anthropic\.com>/d" \
        -e "/^[[:space:]]*$/d" | \
    # Remove trailing empty lines
    awk "/^$/ {empty=1; next} {if (empty) print \"\"; empty=0; print}"
' -- --all

echo ""
echo "Commit messages have been cleaned!"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Review the changes with: git log --oneline"
echo "2. If everything looks good, force push with: git push --force-with-lease origin main"
echo "3. If something went wrong, restore from backup branch"
echo ""
echo "Note: Force pushing will rewrite history on the remote repository."
echo "Make sure no one else is working on the repository when you do this."