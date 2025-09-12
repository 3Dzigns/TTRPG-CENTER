"""
P1.1: Pipeline Progress Callback System

Provides interfaces and implementations for capturing detailed progress
from the 6-pass pipeline execution with pass-level granularity.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from .ttrpg_logging import get_logger


class PassType(Enum):
    """6-pass pipeline pass types"""
    PASS_A = "pass_a_toc_parse"
    PASS_B = "pass_b_logical_split" 
    PASS_C = "pass_c_unstructured"
    PASS_D = "pass_d_haystack"
    PASS_E = "pass_e_llamaindex"
    PASS_F = "pass_f_finalizer"


class PassStatus(Enum):
    """Pass execution status"""
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PassProgress:
    """Detailed progress information for a single pass"""
    pass_type: PassType
    status: PassStatus
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    
    # Pass-specific metrics
    toc_entries: Optional[int] = None
    chunks_processed: Optional[int] = None
    vectors_created: Optional[int] = None
    graph_nodes: Optional[int] = None
    graph_edges: Optional[int] = None
    
    # Error information
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    
    # Bypass information (for Pass C SHA-based bypass)
    bypass_reason: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, **kwargs):
        """Mark pass as completed with optional metrics"""
        self.status = PassStatus.COMPLETED
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        # Update metrics from kwargs
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value
                
    def fail(self, error_message: str, error_type: str = None):
        """Mark pass as failed with error information"""
        self.status = PassStatus.FAILED
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.error_message = error_message
        self.error_type = error_type or "UnknownError"


@dataclass 
class JobProgress:
    """Overall job progress tracking"""
    job_id: str
    source_path: str
    environment: str
    start_time: float
    
    passes: Dict[PassType, PassProgress] = field(default_factory=dict)
    current_pass: Optional[PassType] = None
    overall_status: str = "starting"
    
    def get_progress_percentage(self) -> float:
        """Calculate overall progress percentage based on pass completion"""
        # Pass weights for progress calculation
        pass_weights = {
            PassType.PASS_A: 10,  # ToC parsing - quick
            PassType.PASS_B: 15,  # Logical split - medium
            PassType.PASS_C: 30,  # Unstructured.io - heavy
            PassType.PASS_D: 25,  # Haystack vectors - heavy
            PassType.PASS_E: 15,  # LlamaIndex graph - medium
            PassType.PASS_F: 5,   # Finalizer - quick
        }
        
        total_weight = sum(pass_weights.values())
        completed_weight = 0
        
        for pass_type, weight in pass_weights.items():
            if pass_type in self.passes:
                pass_progress = self.passes[pass_type]
                if pass_progress.status == PassStatus.COMPLETED:
                    completed_weight += weight
                elif pass_progress.status == PassStatus.IN_PROGRESS:
                    # Add partial weight for in-progress passes
                    completed_weight += weight * 0.5
                    
        return (completed_weight / total_weight) * 100
    
    def get_estimated_completion_time(self) -> Optional[float]:
        """Estimate completion time based on current progress"""
        progress_pct = self.get_progress_percentage()
        if progress_pct <= 0:
            return None
            
        elapsed_time = time.time() - self.start_time
        estimated_total_time = elapsed_time / (progress_pct / 100)
        return estimated_total_time - elapsed_time
    
    def get_current_pass_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently executing pass"""
        if not self.current_pass or self.current_pass not in self.passes:
            return None
            
        pass_progress = self.passes[self.current_pass]
        return {
            "pass_type": self.current_pass.value,
            "status": pass_progress.status.value,
            "elapsed_time": time.time() - pass_progress.start_time,
            "metrics": {
                "toc_entries": pass_progress.toc_entries,
                "chunks_processed": pass_progress.chunks_processed,
                "vectors_created": pass_progress.vectors_created,
                "graph_nodes": pass_progress.graph_nodes,
                "graph_edges": pass_progress.graph_edges,
            }
        }


class ProgressCallback(ABC):
    """Abstract base class for progress callbacks"""
    
    @abstractmethod
    async def on_job_start(self, job_progress: JobProgress) -> None:
        """Called when job starts"""
        pass
    
    @abstractmethod
    async def on_pass_start(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Called when a pass starts"""
        pass
    
    @abstractmethod
    async def on_pass_progress(self, job_progress: JobProgress, pass_progress: PassProgress, **metrics) -> None:
        """Called during pass execution with progress updates"""
        pass
    
    @abstractmethod
    async def on_pass_complete(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Called when a pass completes"""
        pass
    
    @abstractmethod
    async def on_pass_failed(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Called when a pass fails"""
        pass
    
    @abstractmethod
    async def on_job_complete(self, job_progress: JobProgress) -> None:
        """Called when job completes"""
        pass


class LoggingProgressCallback(ProgressCallback):
    """Progress callback that logs detailed progress to structured logs"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def on_job_start(self, job_progress: JobProgress) -> None:
        """Log job start with source information"""
        self.logger.info(
            f"Job {job_progress.job_id} starting 6-pass pipeline "
            f"(source: {job_progress.source_path}, env: {job_progress.environment})"
        )
    
    async def on_pass_start(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Log pass start with progress percentage"""
        progress_pct = job_progress.get_progress_percentage()
        self.logger.info(
            f"Job {job_progress.job_id} starting {pass_progress.pass_type.value} "
            f"(progress: {progress_pct:.1f}%)"
        )
    
    async def on_pass_progress(self, job_progress: JobProgress, pass_progress: PassProgress, **metrics) -> None:
        """Log intermediate progress within a pass"""
        if metrics:
            metric_str = ", ".join(f"{k}={v}" for k, v in metrics.items() if v is not None)
            self.logger.info(
                f"Job {job_progress.job_id} {pass_progress.pass_type.value} progress: {metric_str}"
            )
    
    async def on_pass_complete(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Log pass completion with timing and metrics"""
        duration_s = pass_progress.duration_ms / 1000 if pass_progress.duration_ms else 0
        progress_pct = job_progress.get_progress_percentage()
        
        # Build metrics summary
        metrics_parts = []
        if pass_progress.toc_entries is not None:
            metrics_parts.append(f"toc_entries={pass_progress.toc_entries}")
        if pass_progress.chunks_processed is not None:
            metrics_parts.append(f"chunks={pass_progress.chunks_processed}")
        if pass_progress.vectors_created is not None:
            metrics_parts.append(f"vectors={pass_progress.vectors_created}")
        if pass_progress.graph_nodes is not None:
            metrics_parts.append(f"nodes={pass_progress.graph_nodes}")
        if pass_progress.graph_edges is not None:
            metrics_parts.append(f"edges={pass_progress.graph_edges}")
            
        metrics_str = f" ({', '.join(metrics_parts)})" if metrics_parts else ""
        
        self.logger.info(
            f"Job {job_progress.job_id} completed {pass_progress.pass_type.value} "
            f"in {duration_s:.2f}s{metrics_str} (overall: {progress_pct:.1f}%)"
        )
    
    async def on_pass_failed(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        """Log pass failure with error details"""
        duration_s = pass_progress.duration_ms / 1000 if pass_progress.duration_ms else 0
        error_msg = pass_progress.error_message or "Unknown error"
        
        self.logger.error(
            f"Job {job_progress.job_id} {pass_progress.pass_type.value} FAILED "
            f"after {duration_s:.2f}s: {error_msg[:200]}"
        )
    
    async def on_job_complete(self, job_progress: JobProgress) -> None:
        """Log job completion with overall timing and summary"""
        total_duration = time.time() - job_progress.start_time
        completed_passes = sum(1 for p in job_progress.passes.values() if p.status == PassStatus.COMPLETED)
        failed_passes = sum(1 for p in job_progress.passes.values() if p.status == PassStatus.FAILED)
        
        self.logger.info(
            f"Job {job_progress.job_id} completed in {total_duration:.2f}s "
            f"({completed_passes} passes completed, {failed_passes} failed)"
        )


class CompositeProgressCallback(ProgressCallback):
    """Composite callback that delegates to multiple callbacks"""
    
    def __init__(self, callbacks: List[ProgressCallback]):
        self.callbacks = callbacks
    
    async def on_job_start(self, job_progress: JobProgress) -> None:
        for callback in self.callbacks:
            await callback.on_job_start(job_progress)
    
    async def on_pass_start(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        for callback in self.callbacks:
            await callback.on_pass_start(job_progress, pass_progress)
    
    async def on_pass_progress(self, job_progress: JobProgress, pass_progress: PassProgress, **metrics) -> None:
        for callback in self.callbacks:
            await callback.on_pass_progress(job_progress, pass_progress, **metrics)
    
    async def on_pass_complete(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        for callback in self.callbacks:
            await callback.on_pass_complete(job_progress, pass_progress)
    
    async def on_pass_failed(self, job_progress: JobProgress, pass_progress: PassProgress) -> None:
        for callback in self.callbacks:
            await callback.on_pass_failed(job_progress, pass_progress)
    
    async def on_job_complete(self, job_progress: JobProgress) -> None:
        for callback in self.callbacks:
            await callback.on_job_complete(job_progress)