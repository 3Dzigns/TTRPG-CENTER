# app_requirements.py
"""
Phase 7: Requirements & Features Management Application

Provides immutable requirements storage, feature request workflow,
schema validation, and comprehensive audit trails (US-701 through US-706).
"""

import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Depends, Query, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import uvicorn

from src_common.ttrpg_logging import get_logger, setup_logging
from src_common.cors_security import (
    setup_secure_cors,
    validate_cors_startup,
    get_cors_health_status,
)
from src_common.tls_security import (
    create_app_with_tls,
    validate_tls_startup,
    get_tls_health_status,
)
from src_common.requirements_manager import RequirementsManager, FeatureRequestManager
from src_common.schema_validator import SchemaValidator, SchemaSecurityValidator
from src_common.auth_endpoints import auth_router
from src_common.auth_middleware import require_admin, require_auth, get_auth_health
from src_common.auth_database import auth_db

# Initialize logging
logger = setup_logging()

# Initialize managers (will be adjusted per-test for isolation)
requirements_manager = RequirementsManager()
feature_manager = FeatureRequestManager()


def _get_storage_base() -> Path:
    """Derive per-test storage base to isolate tests and avoid cross-talk."""
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev")).lower()
    pytest_ctx = os.getenv("PYTEST_CURRENT_TEST")
    if env == "test" or pytest_ctx:
        # Use test class/module as namespace to share within a test but isolate across others
        import re
        parts = (pytest_ctx or "default").split("::")
        ns = "::".join(parts[:3])  # module + class + function
        safe = re.sub(r"[^a-zA-Z0-9._-]", "_", ns)
        base = Path(".pytest_tmp") / "phase7" / safe
        base.mkdir(parents=True, exist_ok=True)
        return base
    return Path(".")


def _ensure_managers_isolated():
    """Reinitialize managers if storage base changed for current context."""
    global requirements_manager, feature_manager
    base = _get_storage_base()
    if getattr(requirements_manager, "base_path", None) != base:
        requirements_manager = RequirementsManager(base)
    if getattr(feature_manager, "base_path", None) != base:
        feature_manager = FeatureRequestManager(base)
schema_validator = SchemaValidator()

# Initialize authentication database
try:
    auth_db.create_tables()
    auth_db.create_default_admin()  # Create default admin user
    logger.info("Authentication system initialized")
except Exception as e:
    logger.error(f"Authentication initialization failed: {e}")
    if os.getenv("ENVIRONMENT") == "prod":
        raise

# FastAPI app
app = FastAPI(
    title="TTRPG Center - Requirements & Features",
    description="Phase 7 Requirements Management and Feature Request Workflow",
    version="7.0.0"
)

# Security configuration - FR-SEC-402 & FR-SEC-403
try:
    # Validate security configurations on startup
    validate_cors_startup()
    validate_tls_startup()
    
    # Setup secure CORS instead of wildcard configuration
    setup_secure_cors(app)
    
    logger.info("Security configuration initialized successfully")
except Exception as e:
    logger.error(f"Security configuration failed: {e}")
    if os.getenv("ENVIRONMENT") == "prod":
        raise  # Fail hard in production
    else:
        logger.warning("Continuing with basic CORS for development")
        # Fallback CORS for development only
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With"]
        )

# Include authentication router
app.include_router(auth_router)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Pydantic Models
class RequirementsSubmission(BaseModel):
    """Requirements submission model"""
    title: str
    version: str  # Validated later by schema
    description: str
    requirements: Optional[Dict[str, Any]] = None  # Allow missing to return 400 via schema
    stakeholders: Optional[List[Dict[str, Any]]] = []
    acceptance_criteria: Optional[List[Dict[str, Any]]] = []
    author: str


class FeatureRequestSubmission(BaseModel):
    """Feature request submission model"""
    title: str
    description: str
    priority: str
    requester: str
    category: Optional[str] = "other"
    business_value: Optional[str] = "medium"
    effort_estimate: Optional[int] = None
    user_story: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    
    @validator('user_story')
    def validate_user_story_format(cls, v):
        if v and not (v.lower().startswith('as a ') and ' i want ' in v.lower() and ' so that ' in v.lower()):
            raise ValueError('User story must follow format: "As a [user] I want [goal] so that [benefit]"')
        return v


class RequirementApprovalRequest(BaseModel):
    """Requirement approval/rejection model"""
    action: str = Field(..., pattern="^(approve|reject)$")
    admin: str = Field(..., min_length=1, max_length=100)  # Will be replaced by JWT user context
    reason: Optional[str] = Field(None, max_length=1000)


class SchemaValidationRequest(BaseModel):
    """Schema validation request model"""
    schema_type: str
    data: Dict[str, Any]


# Security has been replaced with JWT authentication
# Legacy mock authentication functions removed - use require_admin, require_auth instead


# Routes

@app.get("/", response_class=HTMLResponse)
async def requirements_dashboard(request: Request):
    """Requirements and features dashboard"""
    try:
        _ensure_managers_isolated()
        # Get recent requirements
        req_versions = requirements_manager.get_requirements_versions()[:5]
        
        # Get pending feature requests
        pending_features = feature_manager.list_feature_requests(status="pending")[:10]
        
        # Get recent audit entries
        recent_audit = feature_manager.get_audit_trail()[:10]
        
        return templates.TemplateResponse("requirements_dashboard.html", {
            "request": request,
            "req_versions": req_versions,
            "pending_features": pending_features,
            "recent_audit": recent_audit,
            "current_time": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error loading requirements dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error loading dashboard")


# Requirements Management API (US-701)

@app.get("/api/requirements/versions")
async def list_requirements_versions():
    """List all requirements versions with metadata"""
    try:
        _ensure_managers_isolated()
        versions = requirements_manager.get_requirements_versions()
        return {
            "versions": [
                {
                    "version_id": v.version_id,
                    "timestamp": v.timestamp,
                    "author": v.author,
                    "checksum": v.checksum,
                    "file_path": v.file_path
                }
                for v in versions
            ],
            "total": len(versions)
        }
    except Exception as e:
        logger.error(f"Error listing requirements versions: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving versions")


@app.get("/api/requirements/latest")
async def get_latest_requirements():
    """Get the most recent requirements version"""
    try:
        _ensure_managers_isolated()
        requirements = requirements_manager.get_latest_requirements()
        if not requirements:
            raise HTTPException(status_code=404, detail="No requirements found")
        
        return requirements
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving latest requirements: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving requirements")


@app.get("/api/requirements/{version_id}")
async def get_requirements_version(version_id: int):
    """Get specific requirements version"""
    try:
        _ensure_managers_isolated()
        requirements = requirements_manager.get_requirements_by_version(version_id)
        if not requirements:
            raise HTTPException(status_code=404, detail="Requirements version not found")
        
        return requirements
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving requirements version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving requirements")


@app.post("/api/requirements/submit")
async def submit_requirements(
    req_data: RequirementsSubmission,
    current_user = Depends(require_admin)
):
    """Submit new requirements version (Admin only)"""
    try:
        _ensure_managers_isolated()
        # Sanitize input data for security
        sanitized_data = SchemaSecurityValidator.sanitize_string_fields(req_data.model_dump())
        
        # Check for dangerous content
        dangerous_fields = SchemaSecurityValidator.validate_no_scripts(sanitized_data)
        if dangerous_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Potentially dangerous content detected: {', '.join(dangerous_fields)}"
            )
        
        # Prepare data for schema validation:
        # - Remove top-level author (not allowed by storage schema)
        # - Add temporary metadata so schema validation can pass
        tmp_data = dict(sanitized_data)
        tmp_data.pop("author", None)
        tmp_data["metadata"] = {
            "version_id": 1,  # placeholder for validation only
            "author": current_user.username,
            "timestamp": datetime.now().isoformat(),
            "created_at": time.time(),
            "checksum": "0" * 64,
        }

        # Validate against storage schema
        validation_result = schema_validator.validate_requirements(tmp_data)
        if not validation_result.is_valid:
            error_details = [
                f"{error.field_path}: {error.message}"
                for error in validation_result.errors
            ]
            raise HTTPException(
                status_code=400,
                detail=f"Schema validation failed: {'; '.join(error_details)}"
            )
        
        # Save requirements
        # Save requirements (manager will add immutable metadata)
        version_id = requirements_manager.save_requirements(sanitized_data, current_user.username)
        
        logger.info(f"Requirements version {version_id} submitted by {current_user.username}")
        
        return {
            "success": True,
            "version_id": version_id,
            "message": f"Requirements version {version_id} saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting requirements: {e}")
        raise HTTPException(status_code=500, detail="Error saving requirements")


# Feature Request Management API (US-702, US-703)

@app.get("/api/features")
async def list_feature_requests(
    status: Optional[str] = Query(None, regex="^(pending|approved|rejected|in_progress|completed|cancelled)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """List feature requests with optional status filter"""
    try:
        _ensure_managers_isolated()
        features = feature_manager.list_feature_requests(status)[:limit]
        
        return {
            "features": [
                {
                    "request_id": f.request_id,
                    "title": f.title,
                    "description": f.description,
                    "priority": f.priority,
                    "requester": f.requester,
                    "status": f.status,
                    "created_at": f.created_at,
                    "updated_at": f.updated_at,
                    "approved_by": f.approved_by
                }
                for f in features
            ],
            "total": len(features),
            "filtered_by_status": status
        }
    except Exception as e:
        logger.error(f"Error listing feature requests: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving feature requests")


@app.get("/api/features/{request_id}")
async def get_feature_request(request_id: str):
    """Get specific feature request details"""
    try:
        _ensure_managers_isolated()
        feature = feature_manager.get_feature_request(request_id)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature request not found")
        
        return {
            "request_id": feature.request_id,
            "title": feature.title,
            "description": feature.description,
            "priority": feature.priority,
            "requester": feature.requester,
            "status": feature.status,
            "created_at": feature.created_at,
            "updated_at": feature.updated_at,
            "approved_by": feature.approved_by,
            "rejection_reason": feature.rejection_reason
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving feature request {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving feature request")


@app.post("/api/features/submit")
async def submit_feature_request(req_data: FeatureRequestSubmission):
    """Submit new feature request (US-702)"""
    try:
        _ensure_managers_isolated()
        # Sanitize input data
        sanitized_data = SchemaSecurityValidator.sanitize_string_fields(req_data.model_dump())
        
        # Check for dangerous content
        dangerous_fields = SchemaSecurityValidator.validate_no_scripts(sanitized_data)
        if dangerous_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Potentially dangerous content detected: {', '.join(dangerous_fields)}"
            )
        
        # Create feature request dict for validation
        feature_dict = {
            "request_id": f"FR-{int(time.time() * 1000)}",
            "title": sanitized_data["title"],
            "description": sanitized_data["description"],
            "priority": sanitized_data["priority"],
            "requester": sanitized_data["requester"],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "category": sanitized_data.get("category", "other"),
            "business_value": sanitized_data.get("business_value", "medium"),
            "acceptance_criteria": sanitized_data.get("acceptance_criteria", []),
            "tags": sanitized_data.get("tags", [])
        }
        # Only include optional fields if set (avoid None breaking schema)
        if sanitized_data.get("effort_estimate") is not None:
            feature_dict["effort_estimate"] = sanitized_data.get("effort_estimate")
        if sanitized_data.get("user_story") is not None:
            feature_dict["user_story"] = sanitized_data.get("user_story")
        
        # Validate against schema
        validation_result = schema_validator.validate_feature_request(feature_dict)
        if not validation_result.is_valid:
            error_details = [
                f"{error.field_path}: {error.message}"
                for error in validation_result.errors
            ]
            raise HTTPException(
                status_code=400,
                detail=f"Schema validation failed: {'; '.join(error_details)}"
            )
        
        # Submit feature request
        request_id = feature_manager.submit_feature_request(
            title=sanitized_data["title"],
            description=sanitized_data["description"],
            priority=sanitized_data["priority"],
            requester=sanitized_data["requester"]
        )
        
        logger.info(f"Feature request {request_id} submitted by {sanitized_data['requester']}")
        
        return {
            "success": True,
            "request_id": request_id,
            "message": "Feature request submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feature request: {e}")
        raise HTTPException(status_code=500, detail="Error submitting feature request")


@app.post("/api/features/{request_id}/approve")
async def approve_feature_request(
    request_id: str,
    approval_data: RequirementApprovalRequest,
    current_user = Depends(require_admin)
):
    """Approve feature request (US-703)"""
    try:
        if approval_data.action == "approve":
            success = feature_manager.approve_feature_request(
                request_id, 
                approval_data.admin, 
                approval_data.reason
            )
        elif approval_data.action == "reject":
            success = feature_manager.reject_feature_request(
                request_id, 
                approval_data.admin, 
                approval_data.reason
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        if not success:
            raise HTTPException(status_code=404, detail="Feature request not found")
        
        past_tense = {"approve": "approved", "reject": "rejected"}.get(approval_data.action, approval_data.action)
        return {"success": True, "message": f"Feature request {past_tense} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error {approval_data.action}ing feature request {request_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error {approval_data.action}ing request")


# Audit Trail API (US-704)

@app.get("/api/audit/features")
async def get_feature_audit_trail(
    request_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    """Get feature request audit trail"""
    try:
        _ensure_managers_isolated()
        audit_entries = feature_manager.get_audit_trail(request_id)[:limit]
        
        return {
            "audit_entries": [
                {
                    "timestamp": entry.timestamp,
                    "request_id": entry.request_id,
                    "old_status": entry.old_status,
                    "new_status": entry.new_status,
                    "admin": entry.admin,
                    "reason": entry.reason,
                    "checksum": entry.checksum
                }
                for entry in audit_entries
            ],
            "total": len(audit_entries),
            "filtered_by_request": request_id
        }
    except Exception as e:
        logger.error(f"Error retrieving audit trail: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving audit trail")


@app.get("/api/audit/integrity")
async def validate_audit_integrity(current_user = Depends(require_admin)):
    """Validate audit log integrity (Admin only)"""
    try:
        _ensure_managers_isolated()
        compromised_entries = feature_manager.validate_audit_integrity()
        
        return {
            "integrity_valid": len(compromised_entries) == 0,
            "compromised_entries": compromised_entries,
            "total_compromised": len(compromised_entries),
            "validation_timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error validating audit integrity: {e}")
        raise HTTPException(status_code=500, detail="Error validating audit integrity")


# Schema Validation API (US-705, US-706)

@app.post("/api/validate/schema")
async def validate_against_schema(validation_request: SchemaValidationRequest):
    """Validate data against JSON schema"""
    try:
        _ensure_managers_isolated()
        if validation_request.schema_type == "requirements":
            result = schema_validator.validate_requirements(validation_request.data)
        elif validation_request.schema_type == "feature_request":
            result = schema_validator.validate_feature_request(validation_request.data)
        else:
            raise HTTPException(status_code=400, detail="Invalid schema type")
        
        return {
            "is_valid": result.is_valid,
            "errors": [
                {
                    "field_path": error.field_path,
                    "message": error.message,
                    "invalid_value": error.invalid_value,
                    "schema_path": error.schema_path
                }
                for error in result.errors
            ],
            "schema_name": result.schema_name,
            "validation_time_ms": result.validation_time_ms
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating schema: {e}")
        raise HTTPException(status_code=500, detail="Error performing schema validation")


@app.get("/api/schemas")
async def get_available_schemas():
    """Get list of available schemas"""
    try:
        schemas = schema_validator.get_available_schemas()
        
        schema_details = []
        for schema_name in schemas:
            schema_data = schema_validator.get_schema(schema_name)
            if schema_data:
                schema_details.append({
                    "name": schema_name,
                    "title": schema_data.get("title", ""),
                    "description": schema_data.get("description", ""),
                    "version": schema_data.get("$schema", "")
                })
        
        return {
            "schemas": schema_details,
            "total": len(schema_details)
        }
    except Exception as e:
        logger.error(f"Error retrieving schemas: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving schemas")


@app.get("/api/validation/report")
async def get_validation_report(current_user = Depends(require_admin)):
    """Get comprehensive validation report for all files"""
    try:
        # Validate requirements directory
        req_results = schema_validator.validate_requirements_directory(Path("requirements"))
        
        # Validate features directory  
        feature_results = schema_validator.validate_features_directory(Path("features"))
        
        # Generate reports
        req_report = schema_validator.generate_validation_report(req_results)
        feature_report = schema_validator.generate_validation_report(feature_results)
        
        return {
            "requirements_validation": req_report,
            "features_validation": feature_report,
            "overall_summary": {
                "total_files": req_report["summary"]["total_files"] + feature_report["summary"]["total_files"],
                "total_errors": req_report["summary"]["total_errors"] + feature_report["summary"]["total_errors"],
                "overall_success_rate": (
                    (req_report["summary"]["valid_files"] + feature_report["summary"]["valid_files"]) /
                    max(req_report["summary"]["total_files"] + feature_report["summary"]["total_files"], 1)
                ) * 100
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating validation report: {e}")
        raise HTTPException(status_code=500, detail="Error generating validation report")


# Health check
@app.get("/health")
async def health_check():
    """Requirements service health check"""
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))
    auth_health = await get_auth_health()
    return {
        "status": "ok",
        "service": "requirements",
        "timestamp": time.time(),
        "phase": "7",
        "version": "7.0.0",
        "cors": get_cors_health_status(env),
        "tls": get_tls_health_status(env),
        **auth_health,
    }


if __name__ == "__main__":
    import asyncio

    async def main():
        # Get port from environment
        port = int(os.getenv("REQUIREMENTS_PORT", 8070))
        env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))

        logger.info(f"Starting TTRPG Center Requirements Management on port {port} ({env})")

        try:
            app_with_tls, cert_path, key_path = await create_app_with_tls(app, env)
            if cert_path and key_path:
                from src_common.tls_security import run_with_tls
                run_with_tls(app_with_tls, cert_path, key_path, port)
            else:
                uvicorn.run(
                    app_with_tls,
                    host="0.0.0.0",
                    port=port,
                    log_level="info",
                    reload=env == "dev"
                )
        except Exception as e:
            logger.error(f"TLS setup failed: {e}")
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                reload=env == "dev"
            )

    asyncio.run(main())
