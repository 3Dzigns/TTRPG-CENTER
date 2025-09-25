"""
Admin API Service

FastAPI service for administrative operations with proper CRUD endpoints.
MVP v2 Microservices Architecture - Task 04 Implementation

Features:
- Dictionary CRUD with bulk operations
- Artifact management with metadata
- HGRN action review system
- External test execution coordination
- Proper service client architecture
- Standardized error handling
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, BackgroundTasks, Query
from fastapi.responses import JSONResponse, StreamingResponse

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.auth_models import UserContext
from src_common.security import bootstrap_app_security, record_audit_event, require_roles

from .models import *
from .clients import ServiceClientFactory, TestRunnerClient, TestRunnerError, OrchestratorError

logger = get_logger(__name__)


# Legacy models removed - using comprehensive models from models.py


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Admin API",
    description="Administrative operations with CRUD endpoints, HGRN actions, and test coordination",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

bootstrap_app_security(app, service_name="admin_api")

# Service configuration
config = get_environment_config()
environment = config.get("environment", "dev")

# Initialize service clients
service_clients = ServiceClientFactory(environment)

STATUS_PROGRESS_MAP = {
    "queued": 0.0,
    "running": 0.5,
    "completed": 1.0,
    "failed": 1.0,
    "timeout": 1.0,
    "cancelled": 1.0,
}


def get_test_executor() -> TestRunnerClient:
    """Return the configured test runner client."""
    return service_clients.get_test_runner_client()


def _status_to_progress(status: Optional[str]) -> float:
    value = (status or "").lower()
    return STATUS_PROGRESS_MAP.get(value, 0.0)


def _build_test_execution(payload: Dict[str, Any], status_payload: Optional[Dict[str, Any]] = None) -> TestExecution:
    summary = payload.get("summary") or {}
    status_payload = status_payload or {}
    progress_value = status_payload.get("progress")
    if progress_value is None:
        progress_value = _status_to_progress(payload.get("status"))
    else:
        try:
            progress_value = max(0.0, min(1.0, float(progress_value)))
        except (TypeError, ValueError):
            progress_value = _status_to_progress(payload.get("status"))

    execution_payload: Dict[str, Any] = {
        "execution_id": payload.get("test_id"),
        "suite_type": payload.get("test_suite", ""),
        "target_environment": payload.get("environment", ""),
        "status": payload.get("status", "queued"),
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
        "duration_seconds": payload.get("duration_seconds"),
        "progress": progress_value,
        "current_test": status_payload.get("current_phase") or summary.get("current_test"),
        "tests_total": summary.get("total_tests"),
        "tests_passed": summary.get("passed"),
        "tests_failed": summary.get("failed"),
        "tests_skipped": summary.get("skipped"),
        "coverage_percent": summary.get("coverage") or summary.get("coverage_percent"),
        "artifacts_available": bool(payload.get("artifacts")),
        "results_available": bool(summary),
        "error_message": payload.get("stderr") or summary.get("error_message") or summary.get("error"),
    }
    return TestExecution(**execution_payload)


# Global storage for in-memory data (would be replaced with database)
_dictionary_entries: Dict[str, DictionaryEntry] = {}
_hgrn_actions: Dict[str, HGRNAction] = {}
_test_executions: Dict[str, TestExecution] = {}

# Startup time for diagnostics
_startup_time = time.time()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Admin API Service v2.0.0 with enhanced CRUD endpoints")

    logger.info(f"Loaded configuration for environment: {environment}")

    # Test service client connectivity
    try:
        test_runner = service_clients.get_test_runner_client()
        orchestrator = service_clients.get_orchestrator_client()

        # These would normally test connectivity, but for now we just initialize
        logger.info("Service clients initialized successfully")
    except Exception as e:
        logger.warning(f"Service client initialization warning: {e}")


@app.get("/healthz", response_model=ServiceHealth)
async def health_check():
    """Enhanced health check with dependency status."""

    uptime_seconds = time.time() - _startup_time

    # Check service dependencies
    dependencies = {}

    try:
        # Check orchestrator connectivity
        orchestrator = service_clients.get_orchestrator_client()
        dependencies["orchestrator"] = "healthy"
    except Exception:
        dependencies["orchestrator"] = "unhealthy"

    try:
        # Check test runner connectivity
        test_runner = service_clients.get_test_runner_client()
        dependencies["test_runner"] = "healthy"
    except Exception:
        dependencies["test_runner"] = "unhealthy"

    # Determine overall health
    overall_status = "healthy"
    if any(status == "unhealthy" for status in dependencies.values()):
        overall_status = "degraded"

    return ServiceHealth(
        status=overall_status,
        service="admin_api",
        version="2.0.0",
        environment=environment,
        uptime_seconds=uptime_seconds,
        dependencies=dependencies
    )


# =============================================================================
# Dictionary Management CRUD
# =============================================================================

@app.post("/dictionary", response_model=DictionaryEntry)
async def create_dictionary_entry(
    entry: DictionaryEntryCreate,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Create a new dictionary entry."""

    try:
        # Check for duplicate terms
        existing = next((e for e in _dictionary_entries.values() if e.term.lower() == entry.term.lower()), None)
        if existing:
            error = build_error("DUPLICATE_TERM", f"Dictionary entry already exists for term: {entry.term}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.dict())

        # Create new entry
        new_entry = DictionaryEntry(
            **entry.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        _dictionary_entries[new_entry.id] = new_entry

        logger.info(f"Created dictionary entry: {new_entry.term} (ID: {new_entry.id})")

        await record_audit_event(
            request,
            {
                "event": "dictionary.create",
                "term": new_entry.term,
                "entry_id": new_entry.id,
            },
        )

        return new_entry

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dictionary entry: {str(e)}")
        error = build_error("CREATION_FAILED", f"Failed to create dictionary entry: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.get("/dictionary", response_model=List[DictionaryEntry])
async def list_dictionary_entries(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of entries"),
    offset: int = Query(0, ge=0, description="Number of entries to skip")
):
    """List dictionary entries with optional filtering."""

    try:
        entries = list(_dictionary_entries.values())

        # Apply filters
        if category:
            entries = [e for e in entries if e.category.lower() == category.lower()]

        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            entries = [e for e in entries if any(tag in [t.lower() for t in e.tags] for tag in tag_list)]

        if min_confidence > 0.0:
            entries = [e for e in entries if e.confidence >= min_confidence]

        # Sort by creation date (newest first)
        entries.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        total_count = len(entries)
        entries = entries[offset:offset + limit]

        logger.info(f"Listed {len(entries)} dictionary entries (total: {total_count})")

        return entries

    except Exception as e:
        logger.error(f"Error listing dictionary entries: {str(e)}")
        error = build_error("LISTING_FAILED", f"Failed to list dictionary entries: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.get("/dictionary/{entry_id}", response_model=DictionaryEntry)
async def get_dictionary_entry(entry_id: str):
    """Get a specific dictionary entry by ID."""

    try:
        if entry_id not in _dictionary_entries:
            error = build_error("ENTRY_NOT_FOUND", f"Dictionary entry not found: {entry_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.dict())

        return _dictionary_entries[entry_id]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dictionary entry: {str(e)}")
        error = build_error("RETRIEVAL_FAILED", f"Failed to get dictionary entry: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.put("/dictionary/{entry_id}", response_model=DictionaryEntry)
async def update_dictionary_entry(
    entry_id: str,
    update_data: DictionaryEntryUpdate,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Update an existing dictionary entry."""

    try:
        if entry_id not in _dictionary_entries:
            error = build_error("ENTRY_NOT_FOUND", f"Dictionary entry not found: {entry_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.dict())

        entry = _dictionary_entries[entry_id]

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(entry, field, value)

        entry.updated_at = datetime.utcnow()
        entry.version += 1

        logger.info(f"Updated dictionary entry: {entry.term} (ID: {entry_id})")

        await record_audit_event(
            request,
            {
                "event": "dictionary.update",
                "entry_id": entry_id,
                "term": entry.term,
                "fields_changed": list(update_dict.keys()),
            },
        )

        return entry

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dictionary entry: {str(e)}")
        error = build_error("UPDATE_FAILED", f"Failed to update dictionary entry: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.delete("/dictionary/{entry_id}")
async def delete_dictionary_entry(
    entry_id: str,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Delete a dictionary entry."""

    try:
        if entry_id not in _dictionary_entries:
            error = build_error("ENTRY_NOT_FOUND", f"Dictionary entry not found: {entry_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.dict())

        entry = _dictionary_entries.pop(entry_id)

        logger.info(f"Deleted dictionary entry: {entry.term} (ID: {entry_id})")

        await record_audit_event(
            request,
            {
                "event": "dictionary.delete",
                "entry_id": entry_id,
                "term": entry.term,
            },
        )

        return {"message": f"Dictionary entry deleted: {entry.term}", "id": entry_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dictionary entry: {str(e)}")
        error = build_error("DELETION_FAILED", f"Failed to delete dictionary entry: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.post("/dictionary/search", response_model=List[DictionaryEntry])
async def search_dictionary_entries(search_request: DictionarySearchRequest):
    """Advanced dictionary search with multiple filters."""

    try:
        entries = list(_dictionary_entries.values())

        # Text search in term and definition
        if search_request.query:
            query_lower = search_request.query.lower()
            entries = [
                e for e in entries
                if query_lower in e.term.lower() or query_lower in e.definition.lower()
            ]

        # Apply filters
        if search_request.categories:
            categories_lower = [c.lower() for c in search_request.categories]
            entries = [e for e in entries if e.category.lower() in categories_lower]

        if search_request.tags:
            tags_lower = [t.lower() for t in search_request.tags]
            entries = [
                e for e in entries
                if any(tag in [t.lower() for t in e.tags] for tag in tags_lower)
            ]

        if search_request.min_confidence > 0.0:
            entries = [e for e in entries if e.confidence >= search_request.min_confidence]

        # Sort by relevance (confidence score) and creation date
        entries.sort(key=lambda x: (x.confidence, x.created_at), reverse=True)

        # Apply pagination
        total_count = len(entries)
        entries = entries[search_request.offset:search_request.offset + search_request.limit]

        logger.info(f"Search returned {len(entries)} entries (total: {total_count}) for query: {search_request.query}")

        return entries

    except Exception as e:
        logger.error(f"Error searching dictionary entries: {str(e)}")
        error = build_error("SEARCH_FAILED", f"Dictionary search failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.post("/dictionary/bulk")
async def bulk_dictionary_operation(
    operation: DictionaryBulkOperation,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Perform bulk operations on dictionary entries."""

    try:
        results = {"created": 0, "updated": 0, "deleted": 0, "errors": []}

        if operation.operation == "create":
            for entry_data in operation.entries:
                try:
                    entry_create = DictionaryEntryCreate(**entry_data)

                    # Check for duplicates if skip_duplicates is True
                    if operation.skip_duplicates:
                        existing = next((e for e in _dictionary_entries.values() if e.term.lower() == entry_create.term.lower()), None)
                        if existing:
                            continue

                    new_entry = DictionaryEntry(**entry_create.dict())
                    _dictionary_entries[new_entry.id] = new_entry
                    results["created"] += 1

                except Exception as e:
                    results["errors"].append(f"Create error for {entry_data.get('term', 'unknown')}: {str(e)}")

        elif operation.operation == "delete":
            for entry_data in operation.entries:
                try:
                    entry_id = entry_data.get("id")
                    if entry_id and entry_id in _dictionary_entries:
                        del _dictionary_entries[entry_id]
                        results["deleted"] += 1

                except Exception as e:
                    results["errors"].append(f"Delete error for {entry_data.get('id', 'unknown')}: {str(e)}")

        logger.info(f"Bulk operation completed: {results}")

        await record_audit_event(
            request,
            {
                "event": "dictionary.bulk",
                "operation": operation.operation,
                "created": results.get("created", 0),
                "updated": results.get("updated", 0),
                "deleted": results.get("deleted", 0),
                "errors": len(results.get("errors", [])),
            },
        )

        return results

    except Exception as e:
        logger.error(f"Error in bulk dictionary operation: {str(e)}")
        error = build_error("BULK_OPERATION_FAILED", f"Bulk operation failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


# =============================================================================
# Artifacts Management
# =============================================================================

@app.get("/artifacts", response_model=List[ArtifactInfo])
async def list_artifacts():
    """List all available job artifacts."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts")

        if not artifacts_dir.exists():
            return []

        artifacts = []
        for job_dir in artifacts_dir.iterdir():
            if job_dir.is_dir():
                try:
                    manifest_path = job_dir / "manifest.json"
                    files = [f.name for f in job_dir.iterdir() if f.is_file()]

                    # Calculate total size
                    total_size = sum(f.stat().st_size for f in job_dir.iterdir() if f.is_file())

                    # Get creation time from manifest or directory
                    created_at = None
                    if manifest_path.exists():
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            created_at = manifest.get('created_at')

                    if not created_at:
                        import datetime
                        stat = job_dir.stat()
                        created_at = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()

                    artifacts.append(ArtifactInfo(
                        job_id=job_dir.name,
                        created_at=created_at,
                        size_bytes=total_size,
                        manifest_available=manifest_path.exists(),
                        files=files
                    ))

                except Exception as e:
                    logger.warning(f"Error processing artifact {job_dir.name}: {str(e)}")
                    continue

        return sorted(artifacts, key=lambda x: x.created_at, reverse=True)

    except Exception as e:
        logger.error(f"Error listing artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list artifacts: {str(e)}"
        )


@app.get("/artifacts/{job_id}")
async def get_job_artifacts(job_id: str):
    """Get detailed artifacts for a specific job."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")

        if not artifacts_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifacts not found for job {job_id}"
            )

        manifest_path = artifacts_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            manifest = {"error": "Manifest not found", "job_id": job_id}

        # Add file listing
        files = []
        for file_path in artifacts_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "modified_at": file_path.stat().st_mtime
                })

        manifest["files"] = files
        return manifest

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job artifacts: {str(e)}"
        )


@app.delete("/artifacts/{job_id}")
async def cleanup_job_artifacts(job_id: str):
    """Clean up artifacts for a specific job."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")

        if not artifacts_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifacts not found for job {job_id}"
            )

        # Remove all files in the job directory
        import shutil
        shutil.rmtree(artifacts_dir)

        logger.info(f"Cleaned up artifacts for job {job_id}")

        return {"message": f"Artifacts cleaned up for job {job_id}", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup artifacts: {str(e)}"
        )


# =============================================================================
# HGRN (Human Generated Review Notes) Action Review System
# =============================================================================

@app.post("/hgrn", response_model=HGRNAction)
async def create_hgrn_action(
    action: HGRNActionCreate,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Create a new HGRN action for review."""

    try:
        new_action = HGRNAction(**action.dict())
        _hgrn_actions[new_action.id] = new_action

        logger.info(f"Created HGRN action: {new_action.action} for {new_action.item_type}:{new_action.item_id}")

        await record_audit_event(
            request,
            {
                "event": "hgrn.create",
                "action_id": new_action.id,
                "item_type": new_action.item_type,
                "item_id": new_action.item_id,
                "action": new_action.action.value if hasattr(new_action.action, "value") else str(new_action.action),
            },
        )

        return new_action

    except Exception as e:
        logger.error(f"Error creating HGRN action: {str(e)}")
        error = build_error("HGRN_CREATION_FAILED", f"Failed to create HGRN action: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.get("/hgrn", response_model=List[HGRNAction], dependencies=[Depends(require_roles("admin"))])
async def list_hgrn_actions(
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    item_id: Optional[str] = Query(None, description="Filter by item ID"),
    reviewer: Optional[str] = Query(None, description="Filter by reviewer"),
    action: Optional[HGRNActionType] = Query(None, description="Filter by action type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of actions"),
    offset: int = Query(0, ge=0, description="Number of actions to skip")
):
    """List HGRN actions with optional filtering."""

    try:
        actions = list(_hgrn_actions.values())

        # Apply filters
        if item_type:
            actions = [a for a in actions if a.item_type == item_type]

        if item_id:
            actions = [a for a in actions if a.item_id == item_id]

        if reviewer:
            actions = [a for a in actions if a.reviewer == reviewer]

        if action:
            actions = [a for a in actions if a.action == action]

        # Sort by creation date (newest first)
        actions.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        total_count = len(actions)
        actions = actions[offset:offset + limit]

        logger.info(f"Listed {len(actions)} HGRN actions (total: {total_count})")

        return actions

    except Exception as e:
        logger.error(f"Error listing HGRN actions: {str(e)}")
        error = build_error("HGRN_LISTING_FAILED", f"Failed to list HGRN actions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.get("/hgrn/{action_id}", response_model=HGRNAction, dependencies=[Depends(require_roles("admin"))])
async def get_hgrn_action(action_id: str):
    """Get a specific HGRN action by ID."""

    try:
        if action_id not in _hgrn_actions:
            error = build_error("HGRN_NOT_FOUND", f"HGRN action not found: {action_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.dict())

        return _hgrn_actions[action_id]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HGRN action: {str(e)}")
        error = build_error("HGRN_RETRIEVAL_FAILED", f"Failed to get HGRN action: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.post("/hgrn/search", response_model=List[HGRNAction], dependencies=[Depends(require_roles("admin"))])
async def search_hgrn_actions(search_request: HGRNActionSearch):
    """Advanced HGRN action search with multiple filters."""

    try:
        actions = list(_hgrn_actions.values())

        # Apply filters
        if search_request.item_type:
            actions = [a for a in actions if a.item_type == search_request.item_type]

        if search_request.item_id:
            actions = [a for a in actions if a.item_id == search_request.item_id]

        if search_request.reviewer:
            actions = [a for a in actions if a.reviewer == search_request.reviewer]

        if search_request.action:
            actions = [a for a in actions if a.action == search_request.action]

        if search_request.from_date:
            actions = [a for a in actions if a.created_at >= search_request.from_date]

        if search_request.to_date:
            actions = [a for a in actions if a.created_at <= search_request.to_date]

        # Filter out expired actions
        now = datetime.utcnow()
        actions = [a for a in actions if not a.expires_at or a.expires_at > now]

        # Sort by creation date (newest first)
        actions.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        total_count = len(actions)
        actions = actions[search_request.offset:search_request.offset + search_request.limit]

        logger.info(f"HGRN search returned {len(actions)} actions (total: {total_count})")

        return actions

    except Exception as e:
        logger.error(f"Error searching HGRN actions: {str(e)}")
        error = build_error("HGRN_SEARCH_FAILED", f"HGRN action search failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.delete("/hgrn/{action_id}")
async def delete_hgrn_action(
    action_id: str,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Delete an HGRN action (admin only)."""

    try:
        if action_id not in _hgrn_actions:
            error = build_error("HGRN_NOT_FOUND", f"HGRN action not found: {action_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.dict())

        action = _hgrn_actions.pop(action_id)

        logger.info(f"Deleted HGRN action: {action.action} for {action.item_type}:{action.item_id}")

        await record_audit_event(
            request,
            {
                "event": "hgrn.delete",
                "action_id": action_id,
                "item_type": action.item_type,
                "item_id": action.item_id,
            },
        )

        return {"message": f"HGRN action deleted: {action.action}", "id": action_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting HGRN action: {str(e)}")
        error = build_error("HGRN_DELETION_FAILED", f"Failed to delete HGRN action: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


@app.get("/hgrn/pending/{item_type}", dependencies=[Depends(require_roles("admin"))])
async def get_pending_hgrn_actions(item_type: str):
    """Get pending HGRN actions for a specific item type."""

    try:
        actions = [
            action for action in _hgrn_actions.values()
            if action.item_type == item_type and action.action in ["request_changes", "defer"]
        ]

        # Filter out expired actions
        now = datetime.utcnow()
        actions = [a for a in actions if not a.expires_at or a.expires_at > now]

        # Group by item_id
        pending_items = {}
        for action in actions:
            item_id = action.item_id
            if item_id not in pending_items:
                pending_items[item_id] = []
            pending_items[item_id].append(action)

        logger.info(f"Found {len(pending_items)} items with pending HGRN actions for type: {item_type}")

        return {
            "item_type": item_type,
            "pending_count": len(pending_items),
            "pending_items": pending_items
        }

    except Exception as e:
        logger.error(f"Error getting pending HGRN actions: {str(e)}")
        error = build_error("HGRN_PENDING_FAILED", f"Failed to get pending HGRN actions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.dict())


# =============================================================================
# External Test Execution (Admin UI Test Console)
# =============================================================================

@app.post("/test/execute", response_model=TestExecution)
async def execute_test_suite(
    suite_request: TestSuiteRequest,
    http_request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """
    Execute external test suite - Core Admin UI Test Console functionality.

    This endpoint enables the Admin UI to run test suites against any environment
    and stream results back in real-time.
    """

    try:
        logger.info(
            f"Starting test execution request: {suite_request.suite_type} on {suite_request.target_environment}"
        )

        valid_suites = ["unit", "functional", "security", "regression", "perf"]
        if suite_request.suite_type not in valid_suites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid suite type. Must be one of: {valid_suites}"
            )

        valid_envs = ["dev", "test", "prod"]
        if suite_request.target_environment not in valid_envs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target environment. Must be one of: {valid_envs}"
            )

        test_executor = get_test_executor()
        execution_payload = await test_executor.start_test_execution(
            suite_type=suite_request.suite_type,
            target_environment=suite_request.target_environment,
            test_filter=suite_request.test_filter,
            timeout_minutes=suite_request.timeout_minutes
        )
        status_payload = await test_executor.get_execution_status(execution_payload["test_id"])

        test_execution = _build_test_execution(execution_payload, status_payload)
        _test_executions[test_execution.execution_id] = test_execution

        await record_audit_event(
            http_request,
            {
                "event": "test.execute",
                "execution_id": test_execution.execution_id,
                "suite_type": test_execution.suite_type,
                "target_environment": test_execution.target_environment,
            },
        )

        return test_execution

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start test execution: {str(e)}"
        )


@app.get("/test/executions/{execution_id}", response_model=TestExecution, dependencies=[Depends(require_roles("admin"))])
async def get_test_execution_status(execution_id: str):
    """Get status of a test execution."""

    try:
        test_executor = get_test_executor()
        execution_payload, status_payload = await asyncio.gather(
            test_executor.get_execution(execution_id),
            test_executor.get_execution_status(execution_id),
        )

        test_execution = _build_test_execution(execution_payload, status_payload)
        _test_executions[execution_id] = test_execution
        return test_execution

    except Exception as e:
        logger.error(f"Error getting execution status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test execution {execution_id} not found"
        )


@app.get("/test/executions", response_model=List[TestExecution], dependencies=[Depends(require_roles("admin"))])
async def list_test_executions():
    """List all test executions."""
    try:
        test_executor = get_test_executor()
        executions_data = await test_executor.list_executions()

        test_executions: List[TestExecution] = []
        for payload in executions_data:
            test_execution = _build_test_execution(payload)
            test_executions.append(test_execution)
            if test_execution.execution_id:
                _test_executions[test_execution.execution_id] = test_execution

        return test_executions

    except Exception as e:
        logger.error(f"Error listing executions: {str(e)}")
        return list(_test_executions.values())


@app.get("/test/executions/{execution_id}/stream", dependencies=[Depends(require_roles("admin"))])
async def stream_test_output(execution_id: str):
    """Stream test execution output in real-time."""

    try:
        test_executor = get_test_executor()

        async def generate_stream():
            """Generate real test output stream using external test executor."""
            try:
                async for output in test_executor.stream_execution_output(execution_id):
                    yield output
            except Exception as e:
                error_msg = f"data: {json.dumps({'error': str(e), 'status': 'failed'})}\n\n"
                yield error_msg

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Error setting up stream for execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test execution {execution_id} not found"
        )


@app.post("/test/executions/{execution_id}/stop", dependencies=[Depends(require_roles("admin"))])
async def stop_test_execution(
    execution_id: str,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Stop a running test execution."""

    try:
        test_executor = get_test_executor()
        await test_executor.stop_execution(execution_id)

        await record_audit_event(
            request,
            {
                "event": "test.stop",
                "execution_id": execution_id,
            },
        )

        return {"status": "stopped", "execution_id": execution_id}

    except Exception as e:
        logger.error(f"Error stopping execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop test execution: {str(e)}"
        )


@app.get("/test/executions/{execution_id}/results", dependencies=[Depends(require_roles("admin"))])
async def download_test_results(
    execution_id: str,
    request: Request,
    _: UserContext = Depends(require_roles("admin")),
):
    """Download test execution results."""

    try:
        test_executor = get_test_executor()
        results = await test_executor.get_execution_results(execution_id)

        await record_audit_event(
            request,
            {
                "event": "test.results",
                "execution_id": execution_id,
                "artifact_count": len(results.get("artifacts", [])) if isinstance(results, dict) else None,
            },
        )

        # Return results as JSON response with appropriate headers for download
        return JSONResponse(
            content=results,
            headers={
                "Content-Disposition": f"attachment; filename=test_results_{execution_id}.json"
            }
        )

    except Exception as e:
        logger.error(f"Error getting results for execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test results for execution {execution_id} not found"
        )


# Mock function removed - now using real external test executor


def _verify_test_runner_setup():
    """Verify that external test runner is properly configured."""

    try:
        # Verify external test executor is available
        test_executor = get_test_executor()
        logger.info("External test executor initialized successfully")

        # Check if pytest is available
        result = subprocess.run(["pytest", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Test runner verified: {result.stdout.strip()}")
        else:
            logger.warning("pytest not available - external test execution may fail")

    except ImportError as e:
        logger.error(f"Failed to import external test executor: {str(e)}")
    except FileNotFoundError:
        logger.warning("pytest not found - external test execution may fail")
    except Exception as e:
        logger.error(f"Error verifying test runner setup: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8001, "test": 8182, "prod": 8283}
    port = port_map.get(env_name, 8001)

    uvicorn.run(
        "services.admin_api.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )