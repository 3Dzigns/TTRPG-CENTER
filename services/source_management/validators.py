"""
Source Management File Validators

File validation logic for uploads and processing.
"""

import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Tuple

from .models import ValidationError


class FileValidator:
    """File validation utilities."""

    # Default configuration
    DEFAULT_MAX_SIZE_MB = 50
    DEFAULT_ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.json', '.xml'}
    DEFAULT_ALLOWED_MIME_TYPES = {
        'application/pdf',
        'text/plain',
        'text/markdown',
        'application/json',
        'application/xml',
        'text/xml'
    }

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize validator with configuration."""
        config = config or {}

        self.max_size_mb = config.get('max_size_mb', self.DEFAULT_MAX_SIZE_MB)
        self.max_size_bytes = self.max_size_mb * 1024 * 1024

        # File extension validation
        allowed_exts = config.get('allowed_extensions', self.DEFAULT_ALLOWED_EXTENSIONS)
        self.allowed_extensions = {ext.lower() for ext in allowed_exts}

        # MIME type validation
        allowed_types = config.get('allowed_mime_types', self.DEFAULT_ALLOWED_MIME_TYPES)
        self.allowed_mime_types = {mime.lower() for mime in allowed_types}

    def validate_filename(self, filename: str) -> Tuple[bool, List[ValidationError]]:
        """Validate filename for safety and compliance."""
        errors = []

        if not filename:
            errors.append(ValidationError(
                filename="",
                error_type="invalid_filename",
                message="Filename cannot be empty"
            ))
            return False, errors

        # Check for dangerous characters
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in dangerous_chars):
            errors.append(ValidationError(
                filename=filename,
                error_type="unsafe_filename",
                message="Filename contains unsafe characters",
                details={"dangerous_chars": dangerous_chars}
            ))

        # Check file extension
        file_path = Path(filename)
        if file_path.suffix.lower() not in self.allowed_extensions:
            errors.append(ValidationError(
                filename=filename,
                error_type="invalid_extension",
                message=f"File extension {file_path.suffix} not allowed",
                details={
                    "extension": file_path.suffix,
                    "allowed_extensions": list(self.allowed_extensions)
                }
            ))

        return len(errors) == 0, errors

    def validate_file_size(self, size_bytes: int, filename: str) -> Tuple[bool, List[ValidationError]]:
        """Validate file size against limits."""
        errors = []

        if size_bytes <= 0:
            errors.append(ValidationError(
                filename=filename,
                error_type="empty_file",
                message="File is empty (0 bytes)"
            ))
        elif size_bytes > self.max_size_bytes:
            errors.append(ValidationError(
                filename=filename,
                error_type="file_too_large",
                message=f"File size {self._format_bytes(size_bytes)} exceeds limit of {self.max_size_mb}MB",
                details={
                    "size_bytes": size_bytes,
                    "max_size_bytes": self.max_size_bytes,
                    "size_formatted": self._format_bytes(size_bytes),
                    "limit_formatted": f"{self.max_size_mb}MB"
                }
            ))

        return len(errors) == 0, errors

    def validate_content_type(self, content_type: str, filename: str) -> Tuple[bool, List[ValidationError]]:
        """Validate MIME content type."""
        errors = []

        if not content_type:
            # Try to guess from filename
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type:
                content_type = guessed_type
            else:
                errors.append(ValidationError(
                    filename=filename,
                    error_type="unknown_content_type",
                    message="Cannot determine file content type"
                ))
                return False, errors

        if content_type.lower() not in self.allowed_mime_types:
            errors.append(ValidationError(
                filename=filename,
                error_type="invalid_content_type",
                message=f"Content type {content_type} not allowed",
                details={
                    "content_type": content_type,
                    "allowed_types": list(self.allowed_mime_types)
                }
            ))

        return len(errors) == 0, errors

    def validate_upload_file(self, filename: str, size_bytes: int, content_type: str = None) -> Tuple[bool, List[ValidationError]]:
        """Validate a complete file upload."""
        all_errors = []

        # Validate filename
        filename_valid, filename_errors = self.validate_filename(filename)
        all_errors.extend(filename_errors)

        # Validate size
        size_valid, size_errors = self.validate_file_size(size_bytes, filename)
        all_errors.extend(size_errors)

        # Validate content type if provided
        if content_type:
            content_valid, content_errors = self.validate_content_type(content_type, filename)
            all_errors.extend(content_errors)

        return len(all_errors) == 0, all_errors

    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"


def get_environment_validator(environment: str) -> FileValidator:
    """Get validator configured for specific environment."""
    # Environment-specific configurations
    config_map = {
        'dev': {
            'max_size_mb': 100,  # More lenient in dev
            'allowed_extensions': {'.pdf', '.txt', '.md', '.json', '.xml', '.docx', '.jpg', '.png'}
        },
        'test': {
            'max_size_mb': 50,
            'allowed_extensions': {'.pdf', '.txt', '.md', '.json', '.xml'}
        },
        'prod': {
            'max_size_mb': 25,   # Stricter in production
            'allowed_extensions': {'.pdf'}  # Only PDFs in production
        }
    }

    config = config_map.get(environment, config_map['dev'])
    return FileValidator(config)