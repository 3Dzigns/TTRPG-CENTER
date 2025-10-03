"""
Source Management Service API

FastAPI service for document source management operations.
MVP v2 Microservices Architecture
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.auth_models import UserContext
from src_common.security import bootstrap_app_security, record_audit_event

from .models import *
from .storage import StorageManager
from .validators import get_environment_validator

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Source Management Service",
    description="Document source management with upload, storage, and retrieval operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Bootstrap security first
bootstrap_app_security(app, service_name="source_management")

# Add CORS middleware for cross-service communication (after security)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Admin UI origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Accept-Language", "Authorization", "Content-Language", "Content-Type", "X-Requested-With"],
)

# Service configuration
config = get_environment_config()
environment = config.get("environment", "dev")
base_path = config.get("base_path", "/app")

# Initialize storage manager
storage_manager = StorageManager(base_path=base_path, environment=environment)

# Startup time for health checks
_startup_time = time.time()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Source Management Service v1.0.0")
    logger.info(f"Environment: {environment}")
    logger.info(f"Upload directory: {storage_manager.get_upload_path()}")

    # Ensure upload directory exists
    upload_path = storage_manager.get_upload_path()
    upload_path.mkdir(parents=True, exist_ok=True)

    logger.info("Source Management Service ready")


@app.get("/healthz", response_model=ServiceHealth)
async def health_check():
    """Service health check."""
    uptime_seconds = time.time() - _startup_time

    # Get storage status
    storage_stats = storage_manager.get_storage_stats()

    return ServiceHealth(
        status="healthy",
        service="source_management",
        version="1.0.0",
        environment=environment,
        uptime_seconds=uptime_seconds,
        timestamp=datetime.now().isoformat(),
        storage_status=storage_stats
    )


@app.get("/api/sources", response_model=SourceList)
async def list_sources(
    env: Optional[str] = Query(None, description="Environment filter"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of results"),
    offset: Optional[int] = Query(0, ge=0, description="Offset for pagination")
):
    """List all source documents with metadata."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
            documents = temp_storage.list_documents()
            storage_stats = temp_storage.get_storage_stats()
        else:
            documents = storage_manager.list_documents()
            storage_stats = storage_manager.get_storage_stats()

        # Apply pagination if requested
        total_count = len(documents)
        if limit is not None:
            start_idx = offset
            end_idx = offset + limit
            documents = documents[start_idx:end_idx]

        total_size = sum(doc.size_bytes for doc in documents)

        return SourceList(
            documents=documents,
            total_count=total_count,
            total_size_bytes=total_size,
            environment=target_env,
            path=str(storage_stats.get("upload_directory", "unknown"))
        )

    except Exception as e:
        logger.error(f"Failed to list sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sources: {str(e)}")


@app.post("/api/sources/upload", response_model=UploadResponse)
async def upload_sources(
    files: List[UploadFile] = File(..., description="Files to upload"),
    env: Optional[str] = Form(None, description="Target environment"),
    overwrite: bool = Form(False, description="Allow overwriting existing files"),
    validate_content: bool = Form(True, description="Validate file content")
):
    """Upload one or more source documents."""
    try:
        # Use environment from form parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        uploaded_files = []
        failed_files = []

        for uploaded_file in files:
            try:
                # Read file content
                content = await uploaded_file.read()
                filename = uploaded_file.filename or f"unnamed_{int(time.time())}"

                # Check if file exists and handle overwrite
                if not overwrite:
                    existing = temp_storage.get_document_info(filename)
                    if existing:
                        failed_files.append({
                            "filename": filename,
                            "error": "File already exists (set overwrite=true to replace)"
                        })
                        continue

                # Save the file
                success, document, validation_errors = temp_storage.save_uploaded_file(
                    content, filename, uploaded_file.content_type
                )

                if success:
                    uploaded_files.append(document)
                    logger.info(f"Successfully uploaded {filename} ({len(content)} bytes)")
                else:
                    error_messages = [err.message for err in validation_errors]
                    failed_files.append({
                        "filename": filename,
                        "error": "; ".join(error_messages)
                    })
                    logger.warning(f"Failed to upload {filename}: {error_messages}")

            except Exception as e:
                failed_files.append({
                    "filename": uploaded_file.filename or "unknown",
                    "error": f"Upload processing error: {str(e)}"
                })
                logger.error(f"Upload processing error for {uploaded_file.filename}: {e}")

            finally:
                # Ensure file handle is closed
                try:
                    uploaded_file.file.close()
                except:
                    pass

        return UploadResponse(
            uploaded_files=uploaded_files,
            failed_files=failed_files,
            total_uploaded=len(uploaded_files),
            total_failed=len(failed_files)
        )

    except Exception as e:
        logger.error(f"Upload endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/sources/validation-config", response_model=Dict[str, Any])
async def get_validation_config(
    env: Optional[str] = Query(None, description="Environment to get config for")
):
    """Get validation configuration for the specified environment."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # Get environment-specific validator
        validator = get_environment_validator(target_env)

        return {
            "environment": target_env,
            "max_size_mb": validator.max_size_mb,
            "max_size_bytes": validator.max_size_bytes,
            "max_size_formatted": f"{validator.max_size_mb}MB",
            "allowed_extensions": list(validator.allowed_extensions),
            "allowed_mime_types": list(validator.allowed_mime_types),
            "validation_rules": {
                "max_files_per_upload": 10,
                "dangerous_chars": ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
            }
        }

    except Exception as e:
        logger.error(f"Failed to get validation config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get validation config: {str(e)}")


@app.get("/api/sources/{filename}", response_model=DocumentInfo)
async def get_source_info(
    filename: str,
    env: Optional[str] = Query(None, description="Environment to check")
):
    """Get detailed information about a specific source document."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        document = temp_storage.get_document_info(filename)

        if not document:
            raise HTTPException(status_code=404, detail=f"Document {filename} not found")

        # Check file system status
        file_path = temp_storage.get_upload_path() / temp_storage._sanitize_filename(filename)
        exists = file_path.exists()
        readable = exists and os.access(file_path, os.R_OK)

        return DocumentInfo(
            document=document,
            exists=exists,
            readable=readable,
            path=str(file_path)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source info for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get source info: {str(e)}")


@app.get("/api/sources/{filename}/download")
async def download_source(
    filename: str,
    env: Optional[str] = Query(None, description="Environment to download from")
):
    """Download a source document."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        # Get document info to ensure it exists
        document = temp_storage.get_document_info(filename)
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {filename} not found")

        # Get file path
        file_path = temp_storage.get_upload_path() / temp_storage._sanitize_filename(filename)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File {filename} not found on filesystem")

        # Return file response
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=document.content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.delete("/api/sources/{filename}", response_model=DeleteResponse)
async def delete_source(
    filename: str,
    env: Optional[str] = Query(None, description="Environment to delete from")
):
    """Delete a source document."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        # Attempt deletion
        success, message = temp_storage.delete_document(filename)

        if success:
            logger.info(f"Successfully deleted {filename}")
            return DeleteResponse(
                deleted_files=[filename],
                failed_deletions=[],
                total_deleted=1
            )
        else:
            logger.warning(f"Failed to delete {filename}: {message}")
            return DeleteResponse(
                deleted_files=[],
                failed_deletions=[{"filename": filename, "error": message}],
                total_deleted=0
            )

    except Exception as e:
        logger.error(f"Delete endpoint error for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@app.delete("/api/sources", response_model=DeleteResponse)
async def delete_multiple_sources(
    filenames: List[str] = Query(..., description="Filenames to delete"),
    env: Optional[str] = Query(None, description="Environment to delete from")
):
    """Delete multiple source documents."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        deleted_files = []
        failed_deletions = []

        for filename in filenames:
            try:
                success, message = temp_storage.delete_document(filename)
                if success:
                    deleted_files.append(filename)
                    logger.info(f"Successfully deleted {filename}")
                else:
                    failed_deletions.append({"filename": filename, "error": message})
                    logger.warning(f"Failed to delete {filename}: {message}")
            except Exception as e:
                failed_deletions.append({"filename": filename, "error": str(e)})
                logger.error(f"Error deleting {filename}: {e}")

        return DeleteResponse(
            deleted_files=deleted_files,
            failed_deletions=failed_deletions,
            total_deleted=len(deleted_files)
        )

    except Exception as e:
        logger.error(f"Bulk delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")


@app.get("/api/sources/stats", response_model=Dict[str, Any])
async def get_storage_stats(
    env: Optional[str] = Query(None, description="Environment to check")
):
    """Get storage statistics and system information."""
    try:
        # Use environment from query parameter or default to service environment
        target_env = env or environment

        # If different environment requested, create temporary storage manager
        if target_env != environment:
            temp_storage = StorageManager(base_path=base_path, environment=target_env)
        else:
            temp_storage = storage_manager

        stats = temp_storage.get_storage_stats()
        stats["environment"] = target_env
        stats["service_uptime_seconds"] = time.time() - _startup_time

        return stats

    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)