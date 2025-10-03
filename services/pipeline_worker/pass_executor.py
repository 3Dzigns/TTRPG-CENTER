"""
Pass executor wrappers for pipeline-worker.

Wraps existing pass functions from src_common for execution in worker pools.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from .models import PassType, JobStatus, PassResult

logger = logging.getLogger(__name__)


class PassExecutor:
    """Wrapper for executing pipeline passes."""

    def __init__(self, env: str = "dev"):
        self.env = env

    async def execute_pass_0(
        self,
        source_file: str,
        job_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass 0: Preflight & De-dup."""
        from src_common.pass_0_preflight import run_preflight_checks

        source_path = Path(source_file)
        logger.info(f"Pass 0: Preflight checks for {source_path.name}")

        def _run():
            result = run_preflight_checks(source_path)
            return {
                "should_skip": result.should_skip,
                "reason": result.reason,
                "file_sha": result.file_sha,
                "page_count": result.page_count,
                "existing_job_id": result.existing_job_id
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass 0 complete: skip={result.get('should_skip')}")
        return result

    async def execute_pass_a(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass A: TOC parsing and metadata extraction."""
        from src_common.pass_a_toc_parser import process_pass_a

        source_path = Path(source_file)
        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass A: TOC parsing for {source_path.name}")

        def _run():
            result = process_pass_a(source_path, job_path, job_id, self.env)
            return {
                "processed_count": result.dictionary_entries,
                "artifact_count": len(result.artifacts),
                "sections_parsed": result.sections_parsed,
                "duration_ms": result.processing_time_ms,
                "success": result.success,
                "error_message": result.error_message
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass A complete: {result.get('processed_count')} entries")
        return result

    async def execute_pass_b(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass B: Logical splitting (>25MB)."""
        from src_common.pass_b_logical_splitter import process_pass_b

        source_path = Path(source_file)
        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass B: Logical splitting check for {source_path.name}")

        def _run():
            result = process_pass_b(source_path, job_path, job_id, self.env)
            return {
                "processed_count": result.parts_created,
                "artifact_count": len(result.artifacts),
                "split_performed": result.split_performed,
                "total_pages": result.total_pages,
                "duration_ms": result.processing_time_ms,
                "success": result.success,
                "error_message": result.error_message
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass B complete: split={result.get('split_performed')}")
        return result

    async def execute_pass_c(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass C: Content extraction and chunking."""
        from src_common.pass_c_extraction import process_pass_c

        source_path = Path(source_file)
        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass C: Content extraction for {source_path.name}")

        def _run():
            result = process_pass_c(source_path, job_path, job_id, self.env)
            return {
                "processed_count": result.chunks_extracted,
                "artifact_count": len(result.artifacts),
                "chunks_loaded": result.chunks_loaded,
                "parts_processed": result.parts_processed,
                "duration_ms": result.processing_time_ms,
                "success": result.success,
                "error_message": result.error_message
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass C complete: {result.get('processed_count')} chunks")
        return result

    async def execute_pass_d(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass D: Vector enrichment and NER."""
        from src_common.pass_d_vector_enrichment import process_pass_d

        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass D: Vector enrichment for job {job_id}")

        def _run():
            result = process_pass_d(job_path, job_id, self.env)
            return {
                "processed_count": result.chunks_vectorized if hasattr(result, 'chunks_vectorized') else 0,
                "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
                "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
                "success": result.success if hasattr(result, 'success') else True,
                "error_message": result.error_message if hasattr(result, 'error_message') else None
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass D complete: {result.get('processed_count')} vectors")
        return result

    async def execute_pass_e(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass E: Graph building and cross-references."""
        from src_common.pass_e_graph_builder import process_pass_e

        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass E: Graph building for job {job_id}")

        def _run():
            result = process_pass_e(job_path, job_id, self.env)
            processed = 0
            if hasattr(result, 'relationships_persisted'):
                processed = result.relationships_persisted
            elif hasattr(result, 'edges_created'):
                processed = result.edges_created
            return {
                "processed_count": processed,
                "nodes_created": getattr(result, 'nodes_created', 0),
                "neo4j_verified": getattr(result, 'verification_count', 0),
                "neo4j_used": getattr(result, 'neo4j_used', False),
                "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
                "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
                "success": result.success if hasattr(result, 'success') else True,
                "error_message": result.error_message if hasattr(result, 'error_message') else None
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass E complete: {result.get('processed_count')} links")
        return result

    async def execute_pass_f(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass F: Finalization and cleanup."""
        from src_common.pass_f_finalizer import process_pass_f

        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass F: Finalization for job {job_id}")

        def _run():
            result = process_pass_f(job_path, job_id, self.env)
            return {
                "processed_count": 1,
                "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
                "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
                "success": result.success if hasattr(result, 'success') else True,
                "error_message": result.error_message if hasattr(result, 'error_message') else None
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass F complete")
        return result

    async def execute_pass_g(
        self,
        source_file: str,
        job_id: str,
        job_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Pass G: HGRN validation and quality gates."""
        from src_common.pass_g_hgrn_consistency import process_pass_g

        if job_path is None:
            job_path = Path(f"./artifacts/ingest/{self.env}/{job_id}")

        logger.info(f"Pass G: HGRN validation for job {job_id}")

        def _run():
            result = process_pass_g(job_path, job_id, self.env)
            return {
                "processed_count": 1,
                "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
                "quality_score": result.quality_score if hasattr(result, 'quality_score') else 0.0,
                "validation_passed": result.validation_passed if hasattr(result, 'validation_passed') else True,
                "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
                "success": result.success if hasattr(result, 'success') else True,
                "error_message": result.error_message if hasattr(result, 'error_message') else None
            }

        result = await asyncio.to_thread(_run)
        logger.info(f"Pass G complete: validation={result.get('validation_passed')}")
        return result

    def get_executor_map(self) -> Dict[PassType, Any]:
        """Get map of PassType to executor functions."""
        return {
            PassType.PASS_0: self.execute_pass_0,
            PassType.PASS_A: self.execute_pass_a,
            PassType.PASS_B: self.execute_pass_b,
            PassType.PASS_C: self.execute_pass_c,
            PassType.PASS_D: self.execute_pass_d,
            PassType.PASS_E: self.execute_pass_e,
            PassType.PASS_F: self.execute_pass_f,
            PassType.PASS_G: self.execute_pass_g,
        }