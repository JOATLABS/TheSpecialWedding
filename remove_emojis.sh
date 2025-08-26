#!/bin/bash

# Wedding WebApp Emoji Removal Script
# This script removes all emojis from text files in the project

set -e # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
files_processed=0
files_modified=0
emojis_removed=0

# Function to print colored output
print_status() {
 echo -e "${GREEN}${NC} $1"
}

print_warning() {
 echo -e "${YELLOW}${NC} $1"
}

print_error() {
 echo -e "${RED}${NC} $1"
}

print_info() {
 echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check if a file should be processed
should_process_file() {
 local file="$1"
 
 # Skip directories we don't want
 if [[ "$file" =~ (node_modules|venv|__pycache__|\.git|\.next|dist|build|\.vscode|\.idea) ]]; then
 return 1
 fi
 
 # Only process text files
 local extension="${file##*.}"
 case "$extension" in
 py|js|ts|tsx|jsx|md|txt|json|yml|yaml|html|htm|css|scss|sass|less|xml|csv|log|sh|bash|zsh|fish|conf|cfg|ini|toml|env|dockerfile)
 return 0
 ;;
 *)
 return 1
 ;;
 esac
}

# Function to remove emojis from a file
remove_emojis_from_file() {
 local file="$1"
 local temp_file=$(mktemp)
 local original_size=$(wc -c < "$file")
 
 # Remove emojis using sed with Unicode ranges
 # This removes most common emojis and symbols
 sed -E '
 s/[]//g
 s/[]//g
 s/[]//g
 s/[‼⁉]//g
 s/[]//g
 s/[\U0001F600-\U0001F64F]//g
 s/[\U0001F300-\U0001F5FF]//g
 s/[\U0001F680-\U0001F6FF]//g
 s/[\U0001F1E0-\U0001F1FF]//g
 s/[\U0001F700-\U0001F77F]//g
 s/[\U0001F780-\U0001F7FF]//g
 s/[\U0001F800-\U0001F8FF]//g
 s/[\U0001F900-\U0001F9FF]//g
 s/[\U0001FA00-\U0001FA6F]//g
 s/[\U0001FA70-\U0001FAFF]//g
 s/[\U00002600-\U000026FF]//g
 s/[\U00002700-\U000027BF]//g
 s/[\U0000FE00-\U0000FE0F]//g
 s/[\U0001F170-\U0001F251]//g
 s/ {2,}/ /g
 /^[[:space:]]*$/N; s/\n[[:space:]]*\n/\n/g
 ' "$file" > "$temp_file"
 
 local new_size=$(wc -c < "$temp_file")
 local removed=$((original_size - new_size))
 
 if [ "$removed" -gt 0 ]; then
 mv "$temp_file" "$file"
 print_status "$file: Removed approximately $removed characters (likely emojis)"
 files_modified=$((files_modified + 1))
 emojis_removed=$((emojis_removed + removed))
 else
 rm "$temp_file"
 fi
 
 files_processed=$((files_processed + 1))
}

# Main execution
main() {
 echo " Wedding WebApp Emoji Removal Tool (Shell Version)"
 echo "======================================================"
 
 local directory="${1:-.}"
 
 if [ ! -d "$directory" ]; then
 print_error "Directory '$directory' does not exist."
 exit 1
 fi
 
 print_info "Scanning directory: $(realpath "$directory")"
 
 # Find and process files
 local file_count=0
 
 # Count files first
 while IFS= read -r -d '' file; do
 if should_process_file "$file"; then
 file_count=$((file_count + 1))
 fi
 done < <(find "$directory" -type f -print0)
 
 if [ "$file_count" -eq 0 ]; then
 print_warning "No processable files found."
 exit 0
 fi
 
 print_info "Found $file_count files to check for emojis."
 echo
 
 # Process files
 while IFS= read -r -d '' file; do
 if should_process_file "$file"; then
 # Check if file is readable and writable
 if [ -r "$file" ] && [ -w "$file" ]; then
 remove_emojis_from_file "$file"
 else
 print_warning "Skipping $file (permission denied)"
 fi
 fi
 done < <(find "$directory" -type f -print0)
 
 # Summary
 echo
 echo "======================================================"
 echo " SUMMARY"
 echo "Files processed: $files_processed"
 echo "Files modified: $files_modified"
 echo "Characters removed: $emojis_removed"
 
 if [ "$files_modified" -gt 0 ]; then
 echo
 print_status "Emoji removal completed successfully!"
 print_info "All emojis have been removed from your files."
 else
 echo
 print_info "No emojis found in the processed files."
 fi
}

# Help function
show_help() {
 echo "Wedding WebApp Emoji Removal Tool"
 echo
 echo "Usage: $0 [directory]"
 echo
 echo "Arguments:"
 echo " directory Directory to process (default: current directory)"
 echo
 echo "Options:"
 echo " -h, --help Show this help message"
 echo
 echo "Examples:"
 echo " $0 # Process current directory"
 echo " $0 ./src # Process ./src directory"
 echo " $0 /path/to/project # Process specific directory"
}

# Parse arguments
case "${1:-}" in
 -h|--help)
 show_help
 exit 0
 ;;
 *)
 main "$@"
 ;;
esac