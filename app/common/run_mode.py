#!/usr/bin/env python3
"""
RUN_MODE Guardrails System
=========================

User Stories:
- Execution vs. Reasoning: Claude/agents execute existing pipeline code instead of fabricating answers
- RUN_MODE=serve/maint flag so that in serve mode, code cannot be altered or regenerated
- Ingestion runs emit structured status events for each phase

This system enforces operational safety and prevents unintended code modification.
"""

import os
import json
import time
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone
from pathlib import Path

class RunMode(Enum):
    """Available run modes with different capabilities"""
    SERVE = "serve"      # Production serving - read-only, no code changes
    MAINT = "maint"      # Maintenance mode - full capabilities
    DEV = "dev"          # Development mode - full capabilities with debug

class GuardrailViolation(Exception):
    """Raised when an operation violates current run mode restrictions"""
    pass

class RunModeManager:
    """Manages run mode enforcement and guardrails"""
    
    def __init__(self):
        self.current_mode = self._detect_run_mode()
        self.status_events = []
        self.lock = threading.Lock()
        
        # Initialize status event storage
        self.status_dir = Path(f"artifacts/status/{os.getenv('APP_ENV', 'dev')}")
        self.status_dir.mkdir(parents=True, exist_ok=True)
        
    def _detect_run_mode(self) -> RunMode:
        """Detect current run mode from environment"""
        mode_str = os.getenv("RUN_MODE", "dev").lower()
        try:
            return RunMode(mode_str)
        except ValueError:
            print(f"Invalid RUN_MODE '{mode_str}', defaulting to dev")
            return RunMode.DEV
    
    def check_code_modification_allowed(self, operation: str) -> None:
        """
        Check if code modification is allowed in current mode
        
        User Story: RUN_MODE=serve prevents code alteration/regeneration
        """
        if self.current_mode == RunMode.SERVE:
            raise GuardrailViolation(
                f"Code modification operation '{operation}' not allowed in SERVE mode. "
                "Switch to MAINT mode for code changes."
            )
    
    def check_data_modification_allowed(self, operation: str) -> None:
        """Check if data modification is allowed"""
        # All modes allow data operations, but with different logging
        if self.current_mode == RunMode.SERVE:
            self.emit_audit_event(f"Data modification in SERVE mode: {operation}")
    
    def emit_audit_event(self, message: str, level: str = "INFO") -> None:
        """Emit audit event for compliance tracking"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_mode": self.current_mode.value,
            "level": level,
            "message": message,
            "pid": os.getpid()
        }
        
        # Log to file
        audit_file = self.status_dir / f"audit_{time.strftime('%Y%m%d')}.jsonl"
        with open(audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')
    
    def emit_structured_status(self, 
                             job_id: str,
                             phase: str, 
                             status: str,
                             progress: int,
                             message: str,
                             logs_tail: Optional[List[str]] = None,
                             metrics: Optional[Dict[str, Any]] = None,
                             error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Emit structured status event for ingestion phases
        
        User Story: Ingestion runs emit structured status events for each phase
        (upload, chunk, dictionary, embed, enrich, verify)
        """
        
        # Validate phase
        valid_phases = ["upload", "chunk", "dictionary", "embed", "enrich", "verify"]
        if phase not in valid_phases:
            raise ValueError(f"Invalid phase '{phase}'. Must be one of: {valid_phases}")
        
        # Validate status
        valid_statuses = ["queued", "running", "stalled", "error", "done"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")
        
        # Create structured event
        event = {
            "job_id": job_id,
            "env": os.getenv("APP_ENV", "dev"),
            "run_mode": self.current_mode.value,
            "phase": phase,
            "status": status,
            "progress": max(0, min(100, progress)),  # Clamp 0-100
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "logs_tail": logs_tail or [],
            "metrics": metrics or {},
            "error": error,
            "pid": os.getpid()
        }
        
        # Store event
        with self.lock:
            self.status_events.append(event)
            
            # Persist to file
            status_file = self.status_dir / f"status_{job_id}.jsonl"
            with open(status_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
        
        # Console output in dev/maint modes
        if self.current_mode in [RunMode.DEV, RunMode.MAINT]:
            print(f"[{event['updated_at']}] {phase}:{status} ({progress}%) - {message}")
            if error:
                print(f"[ERROR] {error}")
        
        return event
    
    def get_job_status(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all status events for a job"""
        try:
            status_file = self.status_dir / f"status_{job_id}.jsonl"
            if not status_file.exists():
                return []
            
            events = []
            with open(status_file, 'r', encoding='utf-8') as f:
                for line in f:
                    events.append(json.loads(line.strip()))
            
            return events
        except Exception as e:
            print(f"Failed to load status for job {job_id}: {e}")
            return []
    
    def get_current_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get most recent status for a job"""
        events = self.get_job_status(job_id)
        return events[-1] if events else None
    
    def enforce_execution_over_reasoning(self, operation: str) -> None:
        """
        Enforce that operations use existing code instead of reasoning/fabrication
        
        User Story: Claude/agents execute existing pipeline code instead of fabricating answers
        """
        if self.current_mode == RunMode.SERVE:
            # In serve mode, only allow reading persisted artifacts
            allowed_operations = [
                "read_dictionary_snapshot", 
                "query_vector_store",
                "get_job_status",
                "load_manifest"
            ]
            
            if operation not in allowed_operations:
                raise GuardrailViolation(
                    f"Operation '{operation}' requires code execution. "
                    f"In SERVE mode, only these operations are allowed: {allowed_operations}. "
                    "Results must come from persisted artifacts."
                )
        
        # Log the operation for audit
        self.emit_audit_event(f"Executed operation: {operation}")

# Global instance
_run_mode_manager = None

def get_run_mode_manager() -> RunModeManager:
    """Get global run mode manager instance"""
    global _run_mode_manager
    if _run_mode_manager is None:
        _run_mode_manager = RunModeManager()
    return _run_mode_manager

def check_code_modification_allowed(operation: str) -> None:
    """Check if code modification is allowed"""
    get_run_mode_manager().check_code_modification_allowed(operation)

def check_data_modification_allowed(operation: str) -> None:
    """Check if data modification is allowed"""
    get_run_mode_manager().check_data_modification_allowed(operation)

def emit_structured_status(job_id: str, phase: str, status: str, progress: int, 
                         message: str, **kwargs) -> Dict[str, Any]:
    """Emit structured status event"""
    return get_run_mode_manager().emit_structured_status(
        job_id, phase, status, progress, message, **kwargs
    )

def enforce_execution_over_reasoning(operation: str) -> None:
    """Enforce execution over reasoning"""
    get_run_mode_manager().enforce_execution_over_reasoning(operation)

def get_current_run_mode() -> RunMode:
    """Get current run mode"""
    return get_run_mode_manager().current_mode

# Decorators for automatic enforcement

def require_maint_mode(func):
    """Decorator to require maintenance mode for function execution"""
    def wrapper(*args, **kwargs):
        manager = get_run_mode_manager()
        if manager.current_mode == RunMode.SERVE:
            raise GuardrailViolation(
                f"Function '{func.__name__}' requires MAINT mode. "
                "Current mode is SERVE."
            )
        return func(*args, **kwargs)
    return wrapper

def audit_operation(operation_name: str):
    """Decorator to audit function execution"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_run_mode_manager()
            manager.emit_audit_event(f"Starting operation: {operation_name}")
            try:
                result = func(*args, **kwargs)
                manager.emit_audit_event(f"Completed operation: {operation_name}")
                return result
            except Exception as e:
                manager.emit_audit_event(f"Failed operation: {operation_name} - {str(e)}", "ERROR")
                raise
        return wrapper
    return decorator

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    print("RUN_MODE Guardrails System Test")
    print("=" * 40)
    
    manager = get_run_mode_manager()
    print(f"Current run mode: {manager.current_mode.value}")
    
    # Test status emission
    job_id = "test-job-123"
    
    # Emit sample status events for all phases
    phases = ["upload", "chunk", "dictionary", "embed", "enrich", "verify"]
    
    for i, phase in enumerate(phases):
        progress = int((i + 1) / len(phases) * 100)
        status = "done" if i < len(phases) - 1 else "running"
        
        event = manager.emit_structured_status(
            job_id=job_id,
            phase=phase,
            status=status,
            progress=progress,
            message=f"Processing {phase} phase",
            metrics={"processed": i * 10, "total": 60}
        )
        
        print(f"Emitted: {phase} - {status} ({progress}%)")
    
    # Test job status retrieval
    print(f"\nJob status events: {len(manager.get_job_status(job_id))}")
    current_status = manager.get_current_status(job_id)
    if current_status:
        print(f"Current status: {current_status['phase']} - {current_status['status']}")
    
    # Test guardrails (if in serve mode)
    if manager.current_mode == RunMode.SERVE:
        print("\nTesting SERVE mode guardrails:")
        try:
            manager.check_code_modification_allowed("modify_pipeline")
        except GuardrailViolation as e:
            print(f"✓ Guardrail working: {e}")
        
        try:
            manager.enforce_execution_over_reasoning("generate_new_code") 
        except GuardrailViolation as e:
            print(f"✓ Execution enforcement working: {e}")
    
    print("\nTest completed successfully!")