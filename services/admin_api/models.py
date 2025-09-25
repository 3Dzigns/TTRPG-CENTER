"""
Pydantic models for Admin API service.

Comprehensive models for CRUD operations, error handling, and service communication.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from enum import Enum

from pydantic import BaseModel, Field, validator


# =============================================================================
# Error Models (Standardized Error Envelopes)
# =============================================================================

class ErrorDetail(BaseModel):
    """Standard error payload detail."""

    code: str = Field(..., description="Stable application error code")
    message: str = Field(..., description="Human-readable description of the error")
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Trace identifier for correlation")


class ErrorEnvelope(BaseModel):
    """Standard error envelope returned by the admin API."""

    error: ErrorDetail


# =============================================================================
# Dictionary Management Models
# =============================================================================

class DictionaryEntry(BaseModel):
    """Dictionary entry model with comprehensive metadata."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique entry ID")
    term: str = Field(..., min_length=1, max_length=200, description="Dictionary term")
    definition: str = Field(..., min_length=1, max_length=2000, description="Term definition")
    category: str = Field(..., description="Entry category (rules, lore, mechanics, etc.)")
    source: str = Field(..., description="Source document or reference")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    tags: List[str] = Field(default_factory=list, description="Classification tags")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1, ge=1, description="Entry version")


class DictionaryEntryCreate(BaseModel):
    """Model for creating dictionary entries."""

    term: str = Field(..., min_length=1, max_length=200)
    definition: str = Field(..., min_length=1, max_length=2000)
    category: str
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)


class DictionaryEntryUpdate(BaseModel):
    """Model for updating dictionary entries."""

    term: Optional[str] = Field(None, min_length=1, max_length=200)
    definition: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: Optional[List[str]] = None


class DictionaryBulkOperation(BaseModel):
    """Model for bulk dictionary operations."""

    operation: Literal["create", "update", "delete"] = Field(..., description="Bulk operation type")
    entries: List[Dict[str, Any]] = Field(..., description="Entry data for bulk operation")
    skip_duplicates: bool = Field(default=True, description="Skip duplicate entries on create")


class DictionarySearchRequest(BaseModel):
    """Model for dictionary search requests."""

    query: str = Field(..., min_length=1, description="Search query")
    categories: Optional[List[str]] = Field(None, description="Filter by categories")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# =============================================================================
# Artifact Management Models
# =============================================================================

class ArtifactInfo(BaseModel):
    """Enhanced artifact information model."""

    job_id: str = Field(..., description="Job identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    size_bytes: int = Field(..., ge=0, description="Total size in bytes")
    manifest_available: bool = Field(..., description="Whether manifest exists")
    files: List[Dict[str, Any]] = Field(..., description="File listing with metadata")
    status: str = Field(default="available", description="Artifact status")
    environment: str = Field(..., description="Environment where created")


class ArtifactFile(BaseModel):
    """Individual artifact file information."""

    name: str = Field(..., description="File name")
    size_bytes: int = Field(..., ge=0)
    modified_at: datetime
    content_type: Optional[str] = None
    checksum: Optional[str] = None


class BulkCleanupRequest(BaseModel):
    """Model for bulk artifact cleanup operations."""

    job_ids: List[str] = Field(..., min_items=1, description="Job IDs to clean up")
    older_than_days: Optional[int] = Field(None, ge=1, description="Clean artifacts older than N days")
    dry_run: bool = Field(default=False, description="Preview cleanup without executing")


# =============================================================================
# Test Execution Models
# =============================================================================

class TestSuiteType(str, Enum):
    """Valid test suite types."""
    UNIT = "unit"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    REGRESSION = "regression"
    PERFORMANCE = "performance"


class TestEnvironment(str, Enum):
    """Valid test environments."""
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class TestExecutionStatus(str, Enum):
    """Test execution status values."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestSuiteRequest(BaseModel):
    """Enhanced test suite execution request."""

    suite_type: TestSuiteType = Field(..., description="Test suite type")
    target_environment: TestEnvironment = Field(..., description="Target environment")
    test_filter: Optional[str] = Field(None, description="Test filter pattern (pytest -k style)")
    timeout_minutes: int = Field(default=30, ge=1, le=120, description="Execution timeout")
    parallel: bool = Field(default=False, description="Enable parallel execution")
    coverage: bool = Field(default=False, description="Generate coverage report")
    notify_on_completion: bool = Field(default=False, description="Send notification when done")


class TestExecution(BaseModel):
    """Enhanced test execution status model."""

    execution_id: str = Field(..., description="Unique execution identifier")
    suite_type: TestSuiteType
    target_environment: TestEnvironment
    status: TestExecutionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Execution progress")
    current_test: Optional[str] = None
    tests_total: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_skipped: Optional[int] = None
    coverage_percent: Optional[float] = None
    artifacts_available: bool = Field(default=False)
    log_stream_url: Optional[str] = None
    results_url: Optional[str] = None
    error_message: Optional[str] = None


class TestResults(BaseModel):
    """Test execution results model."""

    execution_id: str
    summary: Dict[str, Any] = Field(..., description="Test summary statistics")
    failures: List[Dict[str, Any]] = Field(default_factory=list, description="Failed test details")
    artifacts: List[str] = Field(default_factory=list, description="Generated artifact paths")
    coverage_report: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None


# =============================================================================
# HGRN (Human Generated Review Notes) Models
# =============================================================================

class HGRNActionType(str, Enum):
    """HGRN action types."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DEFER = "defer"


class HGRNAction(BaseModel):
    """HGRN action model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_type: str = Field(..., description="Type of item being reviewed (job, entry, etc.)")
    item_id: str = Field(..., description="ID of item being reviewed")
    action: HGRNActionType
    reviewer: str = Field(..., description="Reviewer identifier")
    notes: str = Field(..., description="Review notes")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class HGRNActionCreate(BaseModel):
    """Model for creating HGRN actions."""

    item_type: str
    item_id: str
    action: HGRNActionType
    reviewer: str
    notes: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class HGRNActionSearch(BaseModel):
    """Model for searching HGRN actions."""

    item_type: Optional[str] = None
    item_id: Optional[str] = None
    reviewer: Optional[str] = None
    action: Optional[HGRNActionType] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# =============================================================================
# Service Health and Status Models
# =============================================================================

class ServiceHealth(BaseModel):
    """Service health status model."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Current environment")
    uptime_seconds: float = Field(..., ge=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency health status")


class ServiceDiagnostics(BaseModel):
    """Service diagnostic information model."""

    service: str
    version: str
    environment: str
    uptime_seconds: float
    timestamp: datetime
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    active_connections: Optional[int] = None
    cache_stats: Optional[Dict[str, Any]] = None
    error_rates: Optional[Dict[str, float]] = None
    feature_flags: Dict[str, bool] = Field(default_factory=dict)


# =============================================================================
# Helper Functions
# =============================================================================

def build_error(code: str, message: str, trace_id: Optional[str] = None) -> ErrorEnvelope:
    """Helper for constructing standardized error responses."""

    detail = ErrorDetail(code=code, message=message, trace_id=trace_id or uuid.uuid4().hex)
    return ErrorEnvelope(error=detail)