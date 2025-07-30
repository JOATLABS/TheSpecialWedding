#!/bin/bash

# Script to find all commits with Claude signatures

echo "=== Commits with Claude signatures ==="
echo ""

# Find commits with Claude signature
commits_with_claude=$(git log --all --grep="🤖 Generated with \[Claude Code\]" --pretty=format:"%h %s" | head -20)

if [ -z "$commits_with_claude" ]; then
    echo "No commits found with Claude signatures."
else
    echo "Found the following commits with Claude signatures:"
    echo ""
    echo "$commits_with_claude"
    echo ""
    
    # Count total
    total=$(git log --all --grep="🤖 Generated with \[Claude Code\]" --oneline | wc -l)
    echo "Total commits with Claude signatures: $total"
fi

echo ""
echo "To remove these signatures, you can use:"
echo "  ./scripts/clean_commit_messages.sh     - Clean ALL commits (rewrites entire history)"
echo "  ./scripts/clean_commits_interactive.sh - Clean recent commits interactively"