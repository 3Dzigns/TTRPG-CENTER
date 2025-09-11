"""
Adapter for existing 6-pass pipeline (scripts/bulk_ingest.py) providing a
uniform async interface for the FR-002 scheduler with P1 progress callbacks.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .ttrpg_logging import get_logger
from .progress_callback import (
    ProgressCallback, LoggingProgressCallback, JobProgress, PassProgress,
    PassType, PassStatus, CompositeProgressCallback
)
from .job_status_store import get_job_store
from .job_status_api import JobStatusProgressCallback


class ProgressAwarePipelineWrapper:
    """P1.1: Wrapper that adds progress tracking to the existing 6-pass pipeline"""
    
    def __init__(self, pipeline, job_progress: JobProgress, progress_callback: ProgressCallback, loop, artifacts_root: Path):
        self.pipeline = pipeline
        self.job_progress = job_progress
        self.progress_callback = progress_callback
        self.loop = loop
        self.artifacts_root = Path(artifacts_root)
        
    def process_source_6pass_with_progress(self, pdf_path, environment):
        """Execute 6-pass pipeline with progress tracking"""
        
        # Define the pass sequence
        passes_sequence = [
            (PassType.PASS_A, "ToC Parse", self._execute_pass_a),
            (PassType.PASS_B, "Logical Split", self._execute_pass_b),
            (PassType.PASS_C, "Unstructured.io", self._execute_pass_c),
            (PassType.PASS_D, "Haystack", self._execute_pass_d),
            (PassType.PASS_E, "LlamaIndex", self._execute_pass_e),
            (PassType.PASS_F, "Finalizer", self._execute_pass_f),
        ]
        
        try:
            result = None
            
            # Execute each pass with progress tracking
            for pass_type, pass_name, pass_function in passes_sequence:
                # Create pass progress tracker
                pass_progress = PassProgress(
                    pass_type=pass_type,
                    status=PassStatus.STARTING,
                    start_time=time.time()
                )
                
                self.job_progress.passes[pass_type] = pass_progress
                self.job_progress.current_pass = pass_type
                
                # Notify pass start (sync call in thread)
                self._sync_callback(self.progress_callback.on_pass_start(self.job_progress, pass_progress))
                
                pass_progress.status = PassStatus.IN_PROGRESS
                
                try:
                    # Execute the pass
                    result = pass_function(pdf_path, environment, pass_progress)
                    
                    # Check if pass was successful
                    if hasattr(result, 'success') and not result.success:
                        error_msg = getattr(result, 'error_message', f'Pass {pass_name} failed')
                        pass_progress.fail(error_msg)
                        self._sync_callback(self.progress_callback.on_pass_failed(self.job_progress, pass_progress))
                        break
                    else:
                        pass_progress.complete()
                        self._sync_callback(self.progress_callback.on_pass_complete(self.job_progress, pass_progress))
                        
                except Exception as e:
                    pass_progress.fail(str(e), type(e).__name__)
                    self._sync_callback(self.progress_callback.on_pass_failed(self.job_progress, pass_progress))
                    break
            
            # Notify job completion
            self._sync_callback(self.progress_callback.on_job_complete(self.job_progress))
            
            return result or self._create_failed_result("Pipeline execution failed")
            
        except Exception as e:
            # Handle overall pipeline failure
            return self._create_failed_result(f"Pipeline error: {str(e)}")
    
    def _sync_callback(self, coro):
        """Execute async callback from sync context using asyncio.run_coroutine_threadsafe"""
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            future.result(timeout=5.0)  # Wait up to 5 seconds for callback
        except Exception as e:
            # Don't let callback errors break the pipeline
            print(f"Progress callback error: {e}")
    
    def _execute_pass_a(self, pdf_path, environment, pass_progress):
        """Execute Pass A with progress tracking"""
        # Call the original pipeline's Pass A logic
        try:
            # Use existing Pass A functionality
            from src_common.pass_a_toc_parser import process_pass_a
            result = process_pass_a(pdf_path, self.artifacts_root, 
                                  self.job_progress.job_id, environment)
            
            # Update progress with ToC metrics
            if hasattr(result, 'toc_entries'):
                pass_progress.toc_entries = len(result.toc_entries) if result.toc_entries else 0
                self._sync_callback(self.progress_callback.on_pass_progress(
                    self.job_progress, pass_progress, toc_entries=pass_progress.toc_entries
                ))
            
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass A failed: {str(e)}")
    
    def _execute_pass_b(self, pdf_path, environment, pass_progress):
        """Execute Pass B with progress tracking"""
        try:
            # Use existing Pass B functionality  
            from src_common.pass_b_logical_splitter import process_pass_b
            result = process_pass_b(pdf_path, self.artifacts_root,
                                  self.job_progress.job_id, environment)
            
            # Update progress with chunk metrics
            if hasattr(result, 'chunks_created'):
                pass_progress.chunks_processed = result.chunks_created
                self._sync_callback(self.progress_callback.on_pass_progress(
                    self.job_progress, pass_progress, chunks_processed=pass_progress.chunks_processed
                ))
            
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass B failed: {str(e)}")
    
    def _execute_pass_c(self, pdf_path, environment, pass_progress):
        """Execute Pass C with progress tracking"""
        try:
            # Use existing Pass C functionality
            from src_common.pass_c_extraction import process_pass_c  
            result = process_pass_c(pdf_path, self.artifacts_root,
                                  self.job_progress.job_id, environment)
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass C failed: {str(e)}")
    
    def _execute_pass_d(self, pdf_path, environment, pass_progress):
        """Execute Pass D with progress tracking"""
        try:
            # Use existing Pass D functionality
            from src_common.pass_d_vector_enrichment import process_pass_d
            result = process_pass_d(self.artifacts_root,
                                  self.job_progress.job_id, environment)
            
            # Update progress with vector metrics
            if hasattr(result, 'vectors_created'):
                pass_progress.vectors_created = result.vectors_created
                self._sync_callback(self.progress_callback.on_pass_progress(
                    self.job_progress, pass_progress, vectors_created=pass_progress.vectors_created
                ))
            
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass D failed: {str(e)}")
    
    def _execute_pass_e(self, pdf_path, environment, pass_progress):
        """Execute Pass E with progress tracking"""
        try:
            # Use existing Pass E functionality
            from src_common.pass_e_graph_builder import process_pass_e
            result = process_pass_e(self.artifacts_root,
                                  self.job_progress.job_id, environment)
            
            # Update progress with graph metrics
            if hasattr(result, 'nodes_created') and hasattr(result, 'edges_created'):
                pass_progress.graph_nodes = result.nodes_created
                pass_progress.graph_edges = result.edges_created
                self._sync_callback(self.progress_callback.on_pass_progress(
                    self.job_progress, pass_progress, 
                    graph_nodes=pass_progress.graph_nodes,
                    graph_edges=pass_progress.graph_edges
                ))
            
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass E failed: {str(e)}")
    
    def _execute_pass_f(self, pdf_path, environment, pass_progress):
        """Execute Pass F with progress tracking"""
        try:
            # Use existing Pass F functionality
            from src_common.pass_f_finalizer import process_pass_f
            # Pass F operates on the artifacts directory, not the PDF path
            result = process_pass_f(self.artifacts_root,
                                  self.job_progress.job_id, environment)
            return result
        except Exception as e:
            return self._create_failed_result(f"Pass F failed: {str(e)}")
    
    def _create_failed_result(self, error_message):
        """Create a failed result object"""
        from types import SimpleNamespace
        result = SimpleNamespace()
        result.job_id = self.job_progress.job_id
        result.success = False
        result.error_message = error_message
        return result


class Pass6PipelineAdapter:
    def __init__(self, environment: str, progress_callback: Optional[ProgressCallback] = None) -> None:
        self.env = environment
        self.logger = get_logger(__name__)
        self.progress_callback = progress_callback or LoggingProgressCallback()
        self._job_store = None
        
        # Lazy import to avoid heavy imports during test collection
        from scripts.bulk_ingest import Pass6Pipeline  # type: ignore

        self._pipeline = Pass6Pipeline(environment)

    async def process_source(self, source_path: str, environment: str, artifacts_dir: str | None = None) -> Dict[str, Any]:
        # P1.1: Create job progress tracking
        loop = asyncio.get_running_loop()
        pdf = Path(source_path)
        pdf_name = pdf.name
        thread_start_time = time.time()
        # Resolve artifacts root path robustly
        artifacts_root = Path(artifacts_dir) if artifacts_dir else (Path(__file__).resolve().parents[1] / f"artifacts/ingest/{environment}")
        
        # Create job progress tracker
        job_id = f"adapter_job_{int(time.time())}"
        job_progress = JobProgress(
            job_id=job_id,
            source_path=source_path,
            environment=environment,
            start_time=thread_start_time
        )
        
        # P2.1: Setup composite progress callback with job status updates
        if self._job_store is None:
            self._job_store = await get_job_store()
        
        job_status_callback = JobStatusProgressCallback(self._job_store)
        composite_callback = CompositeProgressCallback([
            self.progress_callback,
            job_status_callback
        ])
        
        # P1.1: Notify job start
        await composite_callback.on_job_start(job_progress)
        
        # P0.2: Pre-thread execution logging
        self.logger.info(
            f"Job entering thread pool execution for {pdf_name} "
            f"(environment: {environment}, thread: {threading.current_thread().name})"
        )
        
        def _run_with_logging():
            """P1.1: Enhanced thread execution with progress tracking and detailed logging."""
            execution_start = time.time()
            thread_name = threading.current_thread().name
            
            try:
                # P0.2: Thread execution start logging
                self.logger.info(
                    f"Thread {thread_name} starting 6-pass pipeline execution for {pdf_name}"
                )
                
                # P1.1: Create progress-aware pipeline wrapper
                progress_wrapper = ProgressAwarePipelineWrapper(
                    self._pipeline, job_progress, composite_callback, loop, artifacts_root
                )
                
                # Execute the pipeline with progress tracking
                res = progress_wrapper.process_source_6pass_with_progress(pdf, environment)
                
                # P0.2: Thread execution completion logging
                execution_time = time.time() - execution_start
                self.logger.info(
                    f"Thread {thread_name} completed 6-pass pipeline for {pdf_name} "
                    f"(execution time: {execution_time:.2f}s, success: {getattr(res, 'success', False)})"
                )
                
                # Extract detailed results from pipeline result
                result_job_id = getattr(res, "job_id", job_progress.job_id)
                success = getattr(res, "success", False)
                error_message = getattr(res, "error_message", "")
                
                # P0.2: Result details logging
                if success:
                    self.logger.info(
                        f"Pipeline execution successful for {pdf_name} "
                        f"(job_id: {result_job_id}, execution_time: {execution_time:.2f}s)"
                    )
                else:
                    self.logger.error(
                        f"Pipeline execution failed for {pdf_name} "
                        f"(job_id: {result_job_id}, error: {error_message[:200]})"
                    )
                
                # P1.1: Mark job as complete
                job_progress.overall_status = "completed" if success else "failed"
                
                # Normalize to dict-like shape for scheduled processor
                return {
                    "job_id": result_job_id,
                    "status": "completed" if success else "failed",
                    "processing_time": execution_time,
                    "environment": environment,
                    "artifacts_path": str(artifacts_root.resolve()),
                    "error_message": error_message if not success else None,
                    "thread_name": thread_name,
                    "job_progress": job_progress,  # P1.1: Include progress info
                }
                
            except Exception as e:
                # P0.2: Thread exception logging
                execution_time = time.time() - execution_start
                error_msg = str(e)
                
                self.logger.error(
                    f"Thread {thread_name} exception during 6-pass pipeline for {pdf_name}: "
                    f"{error_msg[:300]} (execution_time: {execution_time:.2f}s)"
                )
                
                # Return failed result with exception details
                return {
                    "job_id": f"failed_{int(time.time())}",
                    "status": "failed",
                    "processing_time": execution_time,
                    "environment": environment,
                    "artifacts_path": str(artifacts_root.resolve()),
                    "error_message": error_msg,
                    "thread_name": thread_name,
                    "exception_type": type(e).__name__,
                }
        
        try:
            # P0.2: Execute in thread pool with enhanced error handling
            result = await loop.run_in_executor(None, _run_with_logging)
            
            # P0.2: Post-thread execution logging
            total_time = time.time() - thread_start_time
            self.logger.info(
                f"Job completed thread pool execution for {pdf_name} "
                f"(total time: {total_time:.2f}s, status: {result.get('status', 'unknown')})"
            )
            
            return result
            
        except Exception as e:
            # P0.2: Thread pool level exception handling
            total_time = time.time() - thread_start_time
            error_msg = str(e)
            
            self.logger.error(
                f"Thread pool execution failed for {pdf_name}: {error_msg} "
                f"(total time: {total_time:.2f}s)"
            )
            
            # Return comprehensive failure result
            return {
                "job_id": f"pool_failed_{int(time.time())}",
                "status": "failed",
                "processing_time": total_time,
                "environment": environment,
                "artifacts_path": str(artifacts_root.resolve()),
                "error_message": f"Thread pool error: {error_msg}",
                "thread_name": "pool_error",
                "exception_type": type(e).__name__,
            }
