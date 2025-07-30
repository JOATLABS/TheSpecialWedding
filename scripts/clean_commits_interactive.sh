#!/bin/bash

# Interactive script to remove Claude signatures from recent commits
# This is safer as it only affects recent commits you specify

echo "=== Remove Claude Signatures from Recent Commits ==="
echo ""

# Show recent commits
echo "Recent commits:"
git log --oneline -20
echo ""

read -p "How many recent commits do you want to clean? (e.g., 10): " num_commits

if ! [[ "$num_commits" =~ ^[0-9]+$ ]]; then
    echo "Please enter a valid number"
    exit 1
fi

echo ""
echo "This will open an interactive rebase for the last $num_commits commits."
echo "For each commit you want to clean, change 'pick' to 'reword'."
echo "Then you'll be able to edit each commit message."
echo ""
read -p "Press Enter to continue..."

# Set up a temporary editor script that will clean the commit messages automatically
cat > /tmp/git-clean-msg.sh << 'EOF'
#!/bin/bash
# Remove Claude signatures from the commit message
sed -i -e '/🤖 Generated with \[Claude Code\]/d' \
       -e '/Co-Authored-By: Claude <noreply@anthropic\.com>/d' \
       "$1"
# Remove trailing empty lines
sed -i -e :a -e '/^\s*$/{$d;N;ba' -e '}' "$1"
# Open in default editor for review
${EDITOR:-nano} "$1"
EOF

chmod +x /tmp/git-clean-msg.sh

# Start interactive rebase with custom sequence editor
GIT_SEQUENCE_EDITOR="sed -i 's/^pick/reword/g'" \
GIT_EDITOR="/tmp/git-clean-msg.sh" \
git rebase -i HEAD~$num_commits

# Clean up
rm -f /tmp/git-clean-msg.sh

echo ""
echo "Rebase complete!"
echo ""
echo "Review the changes with: git log --oneline"
echo "If everything looks good, push with: git push --force-with-lease origin main"
echo "If something went wrong, abort with: git rebase --abort"