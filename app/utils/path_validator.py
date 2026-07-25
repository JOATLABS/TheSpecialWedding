"""
Path Validation Utility - Prevents Directory Traversal and Path Injection
Implements comprehensive path validation and sanitization for secure file operations.
"""

import logging
import os
import re
import unicodedata
from pathlib import Path

# Configure logging
path_logger = logging.getLogger("wedding_path_security")


class PathValidator:
    """
    Comprehensive path validation utility to prevent directory traversal attacks.
    Security Features:
    - Directory traversal prevention
    - Path canonicalization
    - Whitelist-based validation
    - Unicode normalization
    - Symlink detection and prevention
    - File extension validation
    - Path length limits
    """

    def __init__(self):
        # Security configuration
        self.max_path_length = 260  # Windows MAX_PATH limit
        self.max_filename_length = 255  # Most filesystems limit
        self.blocked_patterns = [
            # Directory traversal patterns
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"%252e%252e%252f",
            r"%252e%252e%255c",
            r"..%2f",
            r"..%5c",
            r"%2e%2e/",
            r"\.\./\.\./\.\./\.\./\.\./\.\./\.\.",
            # System file patterns
            r"/etc/passwd",
            r"/etc/shadow",
            r"/proc/",
            r"/sys/",
            r"C:\\Windows\\",
            r"C:\\Users\\",
            r"C:\\Program Files",
            r"\\Windows\\",
            r"\\Users\\",
            r"\\Program Files",
            # Device files (Unix/Linux)
            r"/dev/",
            r"/proc/",
            r"/sys/",
            r"/tmp/",  # nosec B108
            # Hidden files and directories
            r"/\\.",
            r"\\\\.",
            r"^\\.",
            # Null bytes and control characters
            r"\\x00",
            r"%00",
            r"\\0",
            r"\\u0000",
            # Command injection attempts
            r"\|",
            r";",
            r"&",
            r"\$\(",
            r"`",
            # Script injection
            r"<script",
            r"javascript:",
            r"vbscript:",
            # File inclusion attempts
            r"php://",
            r"file://",
            r"data://",
            r"expect://",
            r"zip://",
            r"ftp://",
            r"http://",
            r"https://",
        ]

        # Allowed file extensions for uploads
        self.allowed_extensions = {
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"],
            "document": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
            "archive": [".zip", ".tar", ".gz"],
            "video": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
            "audio": [".mp3", ".wav", ".ogg", ".m4a"],
        }
        # Blocked file extensions
        self.blocked_extensions = [
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".pif",
            ".scr",
            ".vbs",
            ".js",
            ".jar",
            ".jsp",
            ".php",
            ".asp",
            ".aspx",
            ".py",
            ".pl",
            ".rb",
            ".sh",
            ".bash",
            ".ps1",
            ".psm1",
            ".dll",
            ".so",
            ".dylib",
        ]
        # Safe base directories (must be absolute paths)
        self.safe_base_dirs = [
            "/app/uploads/",
            "/app/static/",
            "/app/media/",
            "/var/wedding_uploads/",
            "/tmp/wedding_temp/",  # nosec B108
        ]

    def validate_path(
        self, path: str, base_dir: str | None = None, file_type: str | None = None
    ) -> tuple[bool, str | None, str]:
        """
        Validate and sanitize a file path.

        Args:
            path: Path to validate
            base_dir: Base directory to restrict access to
            file_type: Expected file type (image, document, etc.)
        Returns:
            Tuple of (is_valid, sanitized_path, error_message)
        """
        try:
            if not path or not isinstance(path, str):
                return False, None, "Path is empty or invalid type"

            # Log validation attempt
            path_logger.info(f"Validating path: {path[:100]}...")

            # 1. Length validation
            if len(path) > self.max_path_length:
                path_logger.warning(f"Path too long: {len(path)} chars")
                return (
                    False,
                    None,
                    f"Path too long (max {self.max_path_length} characters)",
                )
            # 2. Unicode normalization to prevent bypass attempts
            try:
                normalized_path = unicodedata.normalize("NFKC", path)
            except UnicodeError:
                return False, None, "Invalid Unicode characters in path"

            # 3. URL decoding to catch encoded traversal attempts
            decoded_path = self._safe_url_decode(normalized_path)

            # 4. Check for malicious patterns
            if self._contains_malicious_patterns(decoded_path):
                path_logger.warning(f"Malicious pattern detected in path: {path}")
                return False, None, "Path contains potentially dangerous patterns"
            # 5. Path canonicalization and normalization
            try:
                canonical_path = self._canonicalize_path(decoded_path)
            except Exception as e:
                path_logger.error(f"Path canonicalization failed: {e!s}")
                return False, None, "Path normalization failed"
            # 6. Directory traversal check
            if not self._check_directory_traversal(canonical_path, base_dir):
                path_logger.warning(f"Directory traversal attempt: {path}")
                return False, None, "Directory traversal detected"
            # 7. File extension validation
            if file_type:
                if not self._validate_file_extension(canonical_path, file_type):
                    return False, None, f"Invalid file extension for type '{file_type}'"
            # 8. Filename validation
            filename = os.path.basename(canonical_path)
            if not self._validate_filename(filename):
                return False, None, "Invalid filename"
            # 9. Symlink detection (if path exists)
            if os.path.exists(canonical_path) and os.path.islink(canonical_path):
                path_logger.warning(f"Symlink detected: {canonical_path}")
                return False, None, "Symbolic links are not allowed"
            # 10. Final security check
            if not self._final_security_check(canonical_path, base_dir):
                path_logger.warning(f"Failed final security check: {canonical_path}")
                return False, None, "Path failed security validation"

            path_logger.info(f"Path validation successful: {canonical_path}")
            return True, canonical_path, "Path is valid"

        except Exception as e:
            path_logger.error(f"Path validation error: {e!s}")
            return False, None, "Path validation failed due to error"

    def _safe_url_decode(self, path: str) -> str:
        """Safely decode URL-encoded characters"""
        import urllib.parse

        try:
            # Multiple rounds of decoding to catch double-encoding
            decoded = path
            for _ in range(3):  # Max 3 rounds to prevent infinite loops
                new_decoded = urllib.parse.unquote(decoded, errors="ignore")
                if new_decoded == decoded:
                    break
                decoded = new_decoded

            return decoded

        except Exception:
            return path  # Return original if decoding fails

    def _contains_malicious_patterns(self, path: str) -> bool:
        """Check if path contains any malicious patterns"""

        path_lower = path.lower()

        for pattern in self.blocked_patterns:
            try:
                if re.search(pattern, path_lower, re.IGNORECASE):
                    return True
            except re.error:
                # If regex fails, check for literal string
                if pattern.replace("\\", "") in path_lower:
                    return True

        return False

    def _canonicalize_path(self, path: str) -> str:
        """Canonicalize path to prevent bypasses"""

        # Convert to Path object for safe manipulation
        try:
            path_obj = Path(path)

            # Resolve to absolute path
            if path_obj.is_absolute():
                resolved = path_obj.resolve()
            else:
                # Make relative paths absolute by joining with safe base
                resolved = Path("/safe_root").joinpath(path_obj).resolve()

            return str(resolved)

        except (OSError, ValueError, RuntimeError):
            # If path resolution fails, fall back to manual normalization
            return os.path.normpath(os.path.abspath(path))

    def _check_directory_traversal(
        self, canonical_path: str, base_dir: str | None
    ) -> bool:
        """Check for directory traversal attempts"""

        if not base_dir:
            # If no base directory specified, check against safe base dirs
            for safe_dir in self.safe_base_dirs:
                if canonical_path.startswith(safe_dir):
                    return True
            # If no safe base directory matches, allow only if within reasonable bounds
            return not any(
                danger in canonical_path.lower()
                for danger in [
                    "/etc/",
                    "/proc/",
                    "/sys/",
                    "/dev/",
                    "/root/",
                    "/home/",
                    "\\windows\\",
                    "\\users\\",
                    "\\program files",
                ]
            )

        # Canonicalize base directory
        try:
            canonical_base = os.path.abspath(os.path.normpath(base_dir))

            # Ensure canonical_path is within base_dir
            return (
                canonical_path.startswith(canonical_base + os.sep)
                or canonical_path == canonical_base
            )

        except Exception:
            return False

    def _validate_file_extension(self, path: str, file_type: str) -> bool:
        """Validate file extension against allowed types"""

        if file_type not in self.allowed_extensions:
            return True  # Allow if file type not in validation list

        _, ext = os.path.splitext(path.lower())

        # Check if extension is explicitly blocked
        if ext in self.blocked_extensions:
            return False

        # Check if extension is in allowed list for the file type
        allowed = self.allowed_extensions[file_type]
        return ext in allowed

    def _validate_filename(self, filename: str) -> bool:
        """Validate filename for security"""

        if not filename or filename in [".", ".."]:
            return False

        # Check filename length
        if len(filename) > self.max_filename_length:
            return False

        # Check for control characters and other dangerous characters
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\0", "\n", "\r", "\t"]
        if any(char in filename for char in dangerous_chars):
            return False
        # Check for reserved names on Windows
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            return False

        # Check for leading/trailing spaces or periods
        if filename != filename.strip(" ."):
            return False

        return True

    def _final_security_check(self, canonical_path: str, base_dir: str | None) -> bool:
        """Perform final security validation"""

        # Check path doesn't contain null bytes
        if "\0" in canonical_path:
            return False

        # Check path doesn't contain control characters
        if any(ord(c) < 32 for c in canonical_path):
            return False

        # Check path doesn't access system directories
        system_dirs = [
            "/etc/",
            "/proc/",
            "/sys/",
            "/dev/",
            "/boot/",
            "/root/",
            "C:\\Windows\\",
            "C:\\Program Files\\",
            "C:\\Users\\Administrator",
        ]
        canonical_lower = canonical_path.lower()
        for system_dir in system_dirs:
            if system_dir.lower() in canonical_lower:
                return False

        return True

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing/replacing dangerous characters"""

        if not filename:
            return "unnamed_file"

        # Unicode normalization
        try:
            filename = unicodedata.normalize("NFKC", filename)
        except UnicodeError:
            filename = "invalid_unicode_filename"

        # Replace dangerous characters
        dangerous_chars = [
            "<",
            ">",
            ":",
            '"',
            "|",
            "?",
            "*",
            "/",
            "\\",
            "\0",
            "\n",
            "\r",
            "\t",
        ]
        sanitized = filename

        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "_")

        # Remove leading/trailing spaces and periods
        sanitized = sanitized.strip(" .")

        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "sanitized_filename"

        # Limit length
        if len(sanitized) > self.max_filename_length:
            name, ext = os.path.splitext(sanitized)
            max_name_len = self.max_filename_length - len(ext)
            sanitized = name[:max_name_len] + ext

        return sanitized

    def get_safe_upload_path(
        self, base_upload_dir: str, filename: str, user_id: str = "anonymous"
    ) -> tuple[bool, str | None, str]:
        """
        Generate a safe upload path for files.

        Args:
            base_upload_dir: Base directory for uploads
            filename: Original filename
            user_id: User ID for path organization

        Returns:
            Tuple of (is_valid, safe_path, error_message)
        """

        try:
            # Sanitize filename
            safe_filename = self.sanitize_filename(filename)

            # Create user-specific subdirectory
            safe_user_id = re.sub(r"[^\w\-_]", "_", str(user_id))[:50]

            # Create path structure
            upload_path = os.path.join(base_upload_dir, safe_user_id, safe_filename)

            # Validate the constructed path
            is_valid, canonical_path, error_msg = self.validate_path(
                upload_path, base_upload_dir, None
            )
            if is_valid:
                # Create directory if it doesn't exist
                dir_path = os.path.dirname(canonical_path)
                try:
                    os.makedirs(dir_path, mode=0o755, exist_ok=True)
                except OSError as e:
                    return False, None, f"Failed to create upload directory: {e!s}"

            return is_valid, canonical_path, error_msg

        except Exception as e:
            path_logger.error(f"Safe upload path generation failed: {e!s}")
            return False, None, "Failed to generate safe upload path"


# Global path validator instance
path_validator = PathValidator()
