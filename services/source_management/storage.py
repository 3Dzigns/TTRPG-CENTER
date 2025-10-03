"""
Source Management Storage Layer

File system operations and storage abstractions.
"""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .models import SourceDocument, ValidationError
from .validators import FileValidator, get_environment_validator


class StorageManager:
    """Manages file system operations for source documents."""

    def __init__(self, base_path: str = "/app", environment: str = "dev"):
        """Initialize storage manager."""
        self.base_path = Path(base_path)
        self.environment = environment
        self.upload_dir = self.base_path / "env" / environment / "uploads"

        # Create upload directory if it doesn't exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Get environment-specific validator
        self.validator = get_environment_validator(environment)

    def get_upload_path(self) -> Path:
        """Get the upload directory path."""
        return self.upload_dir

    def list_documents(self) -> List[SourceDocument]:
        """List all documents in the uploads directory."""
        documents = []

        try:
            for file_path in self.upload_dir.iterdir():
                if file_path.is_file():
                    try:
                        doc = self._create_document_metadata(file_path)
                        documents.append(doc)
                    except Exception as e:
                        # Skip files that can't be processed
                        continue

        except Exception as e:
            # Directory doesn't exist or can't be read
            pass

        # Sort by upload time, newest first
        documents.sort(key=lambda x: x.uploaded_at, reverse=True)
        return documents

    def get_document_info(self, filename: str) -> Optional[SourceDocument]:
        """Get information about a specific document."""
        safe_filename = self._sanitize_filename(filename)
        file_path = self.upload_dir / safe_filename

        if not file_path.exists() or not file_path.is_file():
            return None

        return self._create_document_metadata(file_path)

    def save_uploaded_file(self, file_data: bytes, filename: str, content_type: str = None) -> Tuple[bool, SourceDocument, List[ValidationError]]:
        """Save uploaded file data to storage."""
        # Validate the file first
        file_size = len(file_data)
        is_valid, validation_errors = self.validator.validate_upload_file(filename, file_size, content_type)

        if not is_valid:
            return False, None, validation_errors

        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        file_path = self.upload_dir / safe_filename

        try:
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(file_data)

            # Create metadata
            document = self._create_document_metadata(file_path, content_type)
            return True, document, []

        except Exception as e:
            error = ValidationError(
                filename=filename,
                error_type="storage_error",
                message=f"Failed to save file: {str(e)}"
            )
            return False, None, [error]

    def delete_document(self, filename: str) -> Tuple[bool, str]:
        """Delete a document from storage."""
        safe_filename = self._sanitize_filename(filename)
        file_path = self.upload_dir / safe_filename

        if not file_path.exists():
            return False, f"File {filename} not found"

        if not file_path.is_file():
            return False, f"{filename} is not a regular file"

        try:
            file_path.unlink()
            return True, f"Successfully deleted {filename}"
        except Exception as e:
            return False, f"Failed to delete {filename}: {str(e)}"

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            documents = self.list_documents()
            total_size = sum(doc.size_bytes for doc in documents)

            # Get disk usage
            disk_usage = shutil.disk_usage(self.upload_dir)

            return {
                "total_files": len(documents),
                "total_size_bytes": total_size,
                "total_size_formatted": self._format_bytes(total_size),
                "upload_directory": str(self.upload_dir),
                "directory_exists": self.upload_dir.exists(),
                "directory_writable": os.access(self.upload_dir, os.W_OK),
                "disk_usage": {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free,
                    "free_percentage": (disk_usage.free / disk_usage.total) * 100
                }
            }
        except Exception as e:
            return {
                "error": str(e),
                "upload_directory": str(self.upload_dir),
                "directory_exists": False
            }

    def _create_document_metadata(self, file_path: Path, content_type: str = None) -> SourceDocument:
        """Create document metadata from file path."""
        stat = file_path.stat()

        # Guess content type if not provided
        if not content_type:
            import mimetypes
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

        return SourceDocument(
            filename=file_path.name,
            size_bytes=stat.st_size,
            content_type=content_type,
            uploaded_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=stat.st_mtime,
            metadata={
                "path": str(file_path),
                "extension": file_path.suffix.lower(),
                "created_timestamp": stat.st_ctime,
                "modified_timestamp": stat.st_mtime,
                "size_formatted": self._format_bytes(stat.st_size)
            }
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system operations."""
        # Use os.path.basename to prevent directory traversal
        safe_name = os.path.basename(filename)

        # Remove or replace dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            safe_name = safe_name.replace(char, '_')

        # Ensure filename is not empty after sanitization
        if not safe_name:
            safe_name = f"unnamed_{int(time.time())}"

        return safe_name

    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"