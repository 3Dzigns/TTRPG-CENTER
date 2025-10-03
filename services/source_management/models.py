"""
Source Management Service Models

Pydantic models for API requests and responses.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """Source document metadata model."""

    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    modified_at: float = Field(..., description="File modification timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UploadRequest(BaseModel):
    """File upload request metadata."""

    environment: Optional[str] = Field("dev", description="Target environment")
    overwrite: bool = Field(False, description="Allow overwriting existing files")
    validate_content: bool = Field(True, description="Validate file content")


class UploadResponse(BaseModel):
    """File upload response."""

    uploaded_files: List[SourceDocument] = Field(..., description="Successfully uploaded files")
    failed_files: List[Dict[str, str]] = Field(default_factory=list, description="Failed file uploads with reasons")
    total_uploaded: int = Field(..., description="Number of files successfully uploaded")
    total_failed: int = Field(..., description="Number of files that failed to upload")


class SourceList(BaseModel):
    """Source document listing response."""

    documents: List[SourceDocument] = Field(..., description="List of source documents")
    total_count: int = Field(..., description="Total number of documents")
    total_size_bytes: int = Field(..., description="Total size of all documents")
    environment: str = Field(..., description="Environment queried")
    path: str = Field(..., description="Storage path")


class DeleteResponse(BaseModel):
    """File deletion response."""

    deleted_files: List[str] = Field(..., description="Successfully deleted filenames")
    failed_deletions: List[Dict[str, str]] = Field(default_factory=list, description="Failed deletions with reasons")
    total_deleted: int = Field(..., description="Number of files successfully deleted")


class DocumentInfo(BaseModel):
    """Detailed document information."""

    document: SourceDocument = Field(..., description="Document metadata")
    exists: bool = Field(..., description="Whether file exists on filesystem")
    readable: bool = Field(..., description="Whether file is readable")
    path: str = Field(..., description="Full file path")


class ServiceHealth(BaseModel):
    """Service health status."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Environment")
    uptime_seconds: float = Field(..., description="Service uptime")
    timestamp: str = Field(..., description="Health check timestamp")
    storage_status: Dict[str, Any] = Field(..., description="Storage system status")


class ValidationError(BaseModel):
    """File validation error details."""

    filename: str = Field(..., description="Filename that failed validation")
    error_type: str = Field(..., description="Type of validation error")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")