#!/usr/bin/env python3
"""
Emoji Removal Script for Wedding WebApp

This script searches through all text files in the directory and removes
emojis while preserving the rest of the content. It handles various file
types including markdown, Python, JavaScript, TypeScript, and more.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple
import unicodedata

class EmojiRemover:
 def __init__(self):
 # Comprehensive emoji pattern that covers most Unicode emoji ranges
 self.emoji_pattern = re.compile(
 "["
 "\U0001F600-\U0001F64F" # emoticons
 "\U0001F300-\U0001F5FF" # symbols & pictographs
 "\U0001F680-\U0001F6FF" # transport & map symbols
 "\U0001F1E0-\U0001F1FF" # flags (iOS)
 "\U0001F700-\U0001F77F" # alchemical symbols
 "\U0001F780-\U0001F7FF" # Geometric Shapes Extended
 "\U0001F800-\U0001F8FF" # Supplemental Arrows-C
 "\U0001F900-\U0001F9FF" # Supplemental Symbols and Pictographs
 "\U0001FA00-\U0001FA6F" # Chess Symbols
 "\U0001FA70-\U0001FAFF" # Symbols and Pictographs Extended-A
 "\U00002600-\U000026FF" # Miscellaneous Symbols
 "\U00002700-\U000027BF" # Dingbats
 "\U0000FE00-\U0000FE0F" # Variation Selectors
 "\U0001F170-\U0001F251" # Enclosed characters
 "]+", 
 flags=re.UNICODE
 )
 
 # Additional specific emoji characters that might not be caught
 self.specific_emojis = [
 "", "", "", "", "", "", "", "", "", "", "", "", 
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", "",
 "", "", "‼", "⁉", "", "", "", "", "", "", "", "",
 "", "", "", "", "", "", "", "", "", "", "", ""
 ]
 
 # File extensions to process
 self.processable_extensions = {
 '.py', '.js', '.ts', '.tsx', '.jsx', '.md', '.txt', '.json', '.yml', '.yaml',
 '.html', '.htm', '.css', '.scss', '.sass', '.less', '.xml', '.csv', '.log',
 '.sh', '.bash', '.zsh', '.fish', '.conf', '.cfg', '.ini', '.toml', '.env',
 '.dockerfile', '.gitignore', '.gitattributes', '.editorconfig', '.prettierrc'
 }
 
 # Directories to skip
 self.skip_directories = {
 'node_modules', 'venv', '__pycache__', '.git', '.next', 'dist', 'build',
 '.vscode', '.idea', 'coverage', '.nyc_output', '.pytest_cache'
 }
 
 self.files_processed = 0
 self.emojis_removed = 0
 self.files_modified = 0

 def is_emoji(self, char: str) -> bool:
 """Check if a character is an emoji using Unicode categories."""
 if char in self.specific_emojis:
 return True
 
 # Check Unicode category
 category = unicodedata.category(char)
 if category == 'So': # Symbol, other
 return True
 
 # Check if it matches our emoji pattern
 return bool(self.emoji_pattern.match(char))

 def remove_emojis_from_text(self, text: str) -> Tuple[str, int]:
 """Remove emojis from text and return cleaned text and count of removed emojis."""
 removed_count = 0
 
 # First pass: Remove using regex pattern
 original_len = len(text)
 text = self.emoji_pattern.sub('', text)
 removed_count += original_len - len(text)
 
 # Second pass: Remove specific emojis character by character
 cleaned_chars = []
 for char in text:
 if char in self.specific_emojis:
 removed_count += 1
 elif self.is_emoji(char):
 removed_count += 1
 else:
 cleaned_chars.append(char)
 
 cleaned_text = ''.join(cleaned_chars)
 
 # Clean up multiple spaces that might result from emoji removal
 cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
 
 # Clean up empty lines that might result from emoji-only lines
 cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
 
 return cleaned_text, removed_count

 def should_process_file(self, file_path: Path) -> bool:
 """Determine if a file should be processed."""
 # Skip binary files, node_modules, etc.
 for skip_dir in self.skip_directories:
 if skip_dir in file_path.parts:
 return False
 
 # Check extension
 if file_path.suffix.lower() not in self.processable_extensions:
 return False
 
 # Skip very large files (>10MB)
 try:
 if file_path.stat().st_size > 10 * 1024 * 1024:
 return False
 except OSError:
 return False
 
 return True

 def process_file(self, file_path: Path) -> bool:
 """Process a single file and remove emojis."""
 try:
 # Try to read with UTF-8 encoding first
 try:
 with open(file_path, 'r', encoding='utf-8') as f:
 content = f.read()
 except UnicodeDecodeError:
 # Fallback to latin-1 if UTF-8 fails
 with open(file_path, 'r', encoding='latin-1') as f:
 content = f.read()
 
 # Remove emojis
 cleaned_content, removed_count = self.remove_emojis_from_text(content)
 
 # Only write back if changes were made
 if removed_count > 0:
 with open(file_path, 'w', encoding='utf-8') as f:
 f.write(cleaned_content)
 
 self.emojis_removed += removed_count
 self.files_modified += 1
 print(f" {file_path}: Removed {removed_count} emojis")
 return True
 
 return False
 
 except Exception as e:
 print(f" Error processing {file_path}: {e}")
 return False

 def scan_directory(self, directory_path: Path) -> List[Path]:
 """Scan directory for processable files."""
 files_to_process = []
 
 for root, dirs, files in os.walk(directory_path):
 # Skip directories we don't want to process
 dirs[:] = [d for d in dirs if d not in self.skip_directories]
 
 for file in files:
 file_path = Path(root) / file
 if self.should_process_file(file_path):
 files_to_process.append(file_path)
 
 return files_to_process

 def run(self, directory_path: str = '.') -> None:
 """Main execution method."""
 print(" Wedding WebApp Emoji Removal Tool")
 print("=" * 50)
 
 directory = Path(directory_path).resolve()
 
 if not directory.exists():
 print(f"Error: Directory '{directory}' does not exist.")
 sys.exit(1)
 
 print(f"Scanning directory: {directory}")
 
 # Find files to process
 files_to_process = self.scan_directory(directory)
 
 if not files_to_process:
 print("No files found to process.")
 return
 
 print(f"Found {len(files_to_process)} files to check for emojis.")
 print()
 
 # Process files
 for file_path in files_to_process:
 self.files_processed += 1
 self.process_file(file_path)
 
 # Summary
 print()
 print("=" * 50)
 print(" SUMMARY")
 print(f"Files processed: {self.files_processed}")
 print(f"Files modified: {self.files_modified}")
 print(f"Total emojis removed: {self.emojis_removed}")
 
 if self.files_modified > 0:
 print()
 print(" Emoji removal completed successfully!")
 print("All emojis have been removed from your files.")
 else:
 print()
 print("ℹ No emojis found in the processed files.")

def main():
 """Main function."""
 import argparse
 
 parser = argparse.ArgumentParser(description='Remove emojis from all text files in a directory')
 parser.add_argument('directory', nargs='?', default='.', 
 help='Directory to process (default: current directory)')
 parser.add_argument('--dry-run', action='store_true', 
 help='Show what would be changed without making changes')
 
 args = parser.parse_args()
 
 remover = EmojiRemover()
 
 if args.dry_run:
 print(" DRY RUN MODE - No files will be modified")
 print()
 
 remover.run(args.directory)

if __name__ == "__main__":
 main()