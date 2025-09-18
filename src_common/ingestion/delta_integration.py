"""
Delta Refresh Integration for FR-029 Incremental Processing

Provides integration points with existing ingestion pipeline components
for seamless delta refresh operations.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from ..ttrpg_logging import get_logger
from .delta_refresh import DeltaRefresh
from .delta_models import DeltaConfig, ProcessingMode, DeltaSession

logger = get_logger(__name__)


class IncrementalIngestionManager:
    """
    Manager for integrating delta refresh with existing ingestion pipeline.

    Provides high-level interface for document refresh operations with
    intelligent routing between incremental and full processing.
    """

    def __init__(self, environment: str = "dev", config: Optional[DeltaConfig] = None):
        """Initialize incremental ingestion manager."""
        self.environment = environment
        self.config = config or DeltaConfig()
        self.delta_refresh = DeltaRefresh(environment, self.config)

        # Integration state
        self.processing_locks: Dict[str, asyncio.Lock] = {}
        self.active_jobs: Dict[str, Dict[str, Any]] = {}

        logger.info(f"IncrementalIngestionManager initialized for environment: {environment}")

    async def refresh_document(
        self,
        document_path: Union[str, Path],
        job_id: Optional[str] = None,
        force_full: bool = False,
        background: bool = False
    ) -> Union[DeltaSession, str]:
        """
        Refresh a document with delta processing.

        Args:
            document_path: Path to document to refresh
            job_id: Optional job ID for tracking
            force_full: Force full reprocessing
            background: Run in background

        Returns:
            DeltaSession if synchronous, job_id if background
        """
        document_path = str(document_path)

        # Prevent concurrent processing of same document
        if document_path not in self.processing_locks:
            self.processing_locks[document_path] = asyncio.Lock()

        async with self.processing_locks[document_path]:
            if background:
                # Start background processing
                job_id = job_id or f"delta_refresh_{int(time.time() * 1000)}"
                task = asyncio.create_task(
                    self._background_refresh_document(document_path, job_id, force_full)
                )

                self.active_jobs[job_id] = {
                    "document_path": document_path,
                    "started_at": time.time(),
                    "task": task,
                    "force_full": force_full
                }

                return job_id
            else:
                # Synchronous processing
                return await self.delta_refresh.refresh_document(document_path, force_full)

    async def refresh_document_collection(
        self,
        document_paths: List[Union[str, Path]],
        max_parallel: Optional[int] = None,
        job_id: Optional[str] = None
    ) -> str:
        """
        Refresh a collection of documents.

        Args:
            document_paths: List of document paths
            max_parallel: Maximum parallel operations
            job_id: Optional job ID for tracking

        Returns:
            Job ID for tracking collection refresh
        """
        job_id = job_id or f"collection_refresh_{int(time.time() * 1000)}"

        # Start background collection processing
        task = asyncio.create_task(
            self._background_refresh_collection(document_paths, max_parallel, job_id)
        )

        self.active_jobs[job_id] = {
            "document_paths": [str(p) for p in document_paths],
            "started_at": time.time(),
            "task": task,
            "collection": True,
            "max_parallel": max_parallel
        }

        return job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a background job."""
        if job_id not in self.active_jobs:
            return None

        job_info = self.active_jobs[job_id]
        task = job_info["task"]

        status = {
            "job_id": job_id,
            "started_at": job_info["started_at"],
            "running_time_s": time.time() - job_info["started_at"],
            "is_collection": job_info.get("collection", False)
        }

        if task.done():
            if task.exception():
                status.update({
                    "status": "failed",
                    "error": str(task.exception()),
                    "completed_at": time.time()
                })
            else:
                result = task.result()
                status.update({
                    "status": "completed",
                    "result": result,
                    "completed_at": time.time()
                })
        else:
            status["status"] = "running"

        return status

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a background job."""
        if job_id not in self.active_jobs:
            return False

        job_info = self.active_jobs[job_id]
        task = job_info["task"]

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        del self.active_jobs[job_id]
        return True

    async def _background_refresh_document(
        self,
        document_path: str,
        job_id: str,
        force_full: bool
    ) -> DeltaSession:
        """Background document refresh processing."""
        try:
            logger.info(f"Starting background refresh for {document_path} (job: {job_id})")

            session = await self.delta_refresh.refresh_document(
                document_path, force_full
            )

            logger.info(f"Completed background refresh for {document_path} (job: {job_id})")
            return session

        except Exception as e:
            logger.error(f"Background refresh failed for {document_path} (job: {job_id}): {e}")
            raise
        finally:
            # Clean up job tracking
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    async def _background_refresh_collection(
        self,
        document_paths: List[str],
        max_parallel: Optional[int],
        job_id: str
    ) -> List[DeltaSession]:
        """Background collection refresh processing."""
        try:
            logger.info(f"Starting background collection refresh for {len(document_paths)} documents (job: {job_id})")

            sessions = await self.delta_refresh.batch_refresh_documents(
                document_paths, max_parallel
            )

            logger.info(f"Completed background collection refresh (job: {job_id})")
            return sessions

        except Exception as e:
            logger.error(f"Background collection refresh failed (job: {job_id}): {e}")
            raise
        finally:
            # Clean up job tracking
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    async def get_processing_summary(self) -> Dict[str, Any]:
        """Get comprehensive processing summary."""
        # Get delta refresh status
        delta_status = self.delta_refresh.get_processing_status()

        # Add job management info
        active_job_info = []
        for job_id, job_info in self.active_jobs.items():
            job_status = await self.get_job_status(job_id)
            if job_status:
                active_job_info.append(job_status)

        return {
            "delta_refresh": delta_status,
            "job_management": {
                "active_jobs": len(self.active_jobs),
                "jobs": active_job_info
            },
            "integration": {
                "processing_locks": len(self.processing_locks),
                "environment": self.environment
            }
        }

    async def cleanup(self):
        """Clean up resources and background tasks."""
        # Cancel all active jobs
        for job_id in list(self.active_jobs.keys()):
            await self.cancel_job(job_id)

        # Clean up delta refresh
        await self.delta_refresh.cleanup_resources()

        logger.info("IncrementalIngestionManager cleaned up")


class PipelineIntegration:
    """
    Integration utilities for connecting delta refresh with existing pipeline.
    """

    @staticmethod
    def create_pass_a_delta_processor(environment: str = "dev"):
        """Create Pass A (unstructured.io) delta processor."""
        # In a full implementation, this would create a specialized
        # unstructured.io processor that handles incremental content
        logger.info(f"Creating Pass A delta processor for {environment}")
        return MockPassADeltaProcessor(environment)

    @staticmethod
    def create_pass_b_delta_processor(environment: str = "dev"):
        """Create Pass B (Haystack) delta processor."""
        # In a full implementation, this would create a specialized
        # Haystack processor for incremental enrichment
        logger.info(f"Creating Pass B delta processor for {environment}")
        return MockPassBDeltaProcessor(environment)

    @staticmethod
    def create_pass_c_delta_processor(environment: str = "dev"):
        """Create Pass C (LlamaIndex) delta processor."""
        # In a full implementation, this would create a specialized
        # LlamaIndex processor for incremental graph updates
        logger.info(f"Creating Pass C delta processor for {environment}")
        return MockPassCDeltaProcessor(environment)


class MockPassADeltaProcessor:
    """Mock Pass A delta processor for demonstration."""

    def __init__(self, environment: str):
        self.environment = environment

    async def process_added_content(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process newly added content."""
        # Simulate unstructured.io processing
        await asyncio.sleep(0.1)
        return [{"content": content, "metadata": metadata, "chunks": ["chunk1", "chunk2"]}]

    async def process_modified_content(self, old_content: str, new_content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process modified content."""
        # Simulate incremental processing
        await asyncio.sleep(0.15)
        return [{"content": new_content, "metadata": metadata, "chunks": ["chunk1_updated", "chunk2_updated"]}]

    async def remove_deleted_content(self, chunk_ids: List[str]) -> bool:
        """Remove deleted content chunks."""
        # Simulate chunk removal
        await asyncio.sleep(0.05)
        return True


class MockPassBDeltaProcessor:
    """Mock Pass B delta processor for demonstration."""

    def __init__(self, environment: str):
        self.environment = environment

    async def enrich_added_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich newly added chunks."""
        # Simulate Haystack enrichment
        await asyncio.sleep(0.2)
        enriched = []
        for chunk in chunks:
            enriched.append({
                **chunk,
                "enriched": True,
                "entities": ["spell", "damage"],
                "categories": ["combat", "magic"]
            })
        return enriched

    async def update_modified_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update modified chunks with new enrichment."""
        # Simulate incremental enrichment
        await asyncio.sleep(0.25)
        return await self.enrich_added_chunks(chunks)

    async def cleanup_deleted_chunks(self, chunk_ids: List[str]) -> bool:
        """Clean up enrichment data for deleted chunks."""
        await asyncio.sleep(0.05)
        return True


class MockPassCDeltaProcessor:
    """Mock Pass C delta processor for demonstration."""

    def __init__(self, environment: str):
        self.environment = environment

    async def add_graph_nodes(self, enriched_chunks: List[Dict[str, Any]]) -> List[str]:
        """Add new graph nodes for chunks."""
        # Simulate LlamaIndex graph addition
        await asyncio.sleep(0.3)
        return [f"node_{chunk.get('id', 'unknown')}" for chunk in enriched_chunks]

    async def update_graph_relationships(self, node_ids: List[str], chunks: List[Dict[str, Any]]) -> bool:
        """Update graph relationships for modified content."""
        # Simulate incremental graph updates
        await asyncio.sleep(0.4)
        return True

    async def remove_graph_nodes(self, node_ids: List[str]) -> bool:
        """Remove graph nodes for deleted content."""
        await asyncio.sleep(0.1)
        return True


def create_incremental_manager(environment: str = "dev", config: Optional[DeltaConfig] = None) -> IncrementalIngestionManager:
    """Create incremental ingestion manager instance."""
    return IncrementalIngestionManager(environment, config)