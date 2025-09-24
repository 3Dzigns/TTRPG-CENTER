"""
Ingest Service Pipeline

MVP v2 Pass 0→G Pipeline Implementation
Coordinates execution of all ingestion passes with proper error handling and artifacts.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from src_common.logging import get_logger
from src_common.environment_isolation import get_environment_validator

# Import all pipeline passes
from src_common.pass_0_preflight import run_preflight_checks, create_preflight_manifest
from src_common.pass_a_toc_parser import process_pass_a
from src_common.pass_b_logical_splitter import process_pass_b
from src_common.pass_c_extraction import process_pass_c
from src_common.pass_d_vector_enrichment import process_pass_d
from src_common.pass_e_graph_builder import process_pass_e
from src_common.pass_f_finalizer import process_pass_f
from src_common.pass_g_hgrn_consistency import run_hgrn_consistency_check

logger = get_logger(__name__)


class PipelineError(Exception):
    """Pipeline execution error."""
    pass


class IngestionPipeline:
    """
    MVP v2 Pass 0→G Ingestion Pipeline.

    Coordinates execution of all passes with proper artifact management
    and error recovery.
    """

    def __init__(self, job_id: str, source_file: Path, env_root: Path):
        self.job_id = job_id
        self.source_file = source_file
        self.env_root = env_root
        self.job_dir = env_root / "artifacts" / job_id
        self.manifest: Dict[str, Any] = {}
        self.current_pass = ""

    async def execute(self) -> Dict[str, Any]:
        """
        Execute complete Pass 0→G pipeline.

        Returns:
            Final manifest with all pass results

        Raises:
            PipelineError: If any pass fails critically
        """
        logger.info(f"Starting Pass 0→G pipeline for job {self.job_id}")

        try:
            # Create job directory
            self.job_dir.mkdir(parents=True, exist_ok=True)

            # Pass 0: Preflight & De-dup
            await self._run_pass_0()

            # Check if we should skip due to duplicate
            if self.manifest.get("status") == "skipped":
                logger.info(f"Job {self.job_id} skipped due to duplicate content")
                return self.manifest

            # Pass A: TOC & Dictionary Seed
            await self._run_pass_a()

            # Pass B: Fast Split (≤10 MB parts)
            await self._run_pass_b()

            # Pass C: Extraction (Unstructured.io)
            await self._run_pass_c()

            # Pass D: Normalize + Embeddings (Haystack)
            await self._run_pass_d()

            # Pass E: Graph Compile (LlamaIndex)
            await self._run_pass_e()

            # Pass F: Validation & Manifest
            await self._run_pass_f()

            # Pass G: HGRN Consistency Check
            await self._run_pass_g()

            # Final manifest update
            self.manifest["status"] = "completed"
            self.manifest["completed_at"] = datetime.utcnow().isoformat()
            self.manifest["pipeline_version"] = "mvp_v2_pass_0_g"

            # Write final manifest
            await self._write_manifest()

            logger.info(f"Pipeline completed successfully for job {self.job_id}")
            return self.manifest

        except Exception as e:
            logger.error(f"Pipeline failed for job {self.job_id}: {str(e)}")
            self.manifest["status"] = "failed"
            self.manifest["error"] = str(e)
            self.manifest["failed_at"] = datetime.utcnow().isoformat()
            self.manifest["failed_pass"] = self.current_pass

            await self._write_manifest()
            raise PipelineError(f"Pipeline execution failed: {str(e)}")

    async def _run_pass_0(self) -> None:
        """Run Pass 0: Preflight & De-dup."""
        self.current_pass = "pass_0_preflight"
        logger.info(f"Running Pass 0: Preflight & De-dup for {self.source_file}")

        try:
            # Run preflight checks
            preflight_result = run_preflight_checks(self.source_file)

            if preflight_result.should_skip:
                # Create skip manifest and exit pipeline
                self.manifest = {
                    "job_id": self.job_id,
                    "status": "skipped",
                    "reason": preflight_result.reason,
                    "source_file": str(self.source_file),
                    "source_file_sha": preflight_result.file_sha,
                    "source_page_count": preflight_result.page_count,
                    "existing_job_id": preflight_result.existing_job_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "pass_0_preflight": {
                        "skipped": True,
                        "reason": preflight_result.reason
                    }
                }
                return

            # Create initial manifest with preflight results
            self.manifest = create_preflight_manifest(
                self.job_id, self.source_file, preflight_result, self.env_root
            )

            logger.info(f"Pass 0 completed: SHA={preflight_result.file_sha[:12]}..., pages={preflight_result.page_count}")

        except Exception as e:
            logger.error(f"Pass 0 failed: {str(e)}")
            raise PipelineError(f"Pass 0 failed: {str(e)}")

    async def _run_pass_a(self) -> None:
        """Run Pass A: TOC & Dictionary Seed."""
        self.current_pass = "pass_a_toc"
        logger.info(f"Running Pass A: TOC & Dictionary Seed")

        try:
            # Copy source file to job directory
            job_source = self.job_dir / self.source_file.name
            shutil.copy2(self.source_file, job_source)

            # Run Pass A
            result = process_pass_a(job_source, self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_a_toc"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "sections_extracted": len(result.get("sections", [])),
                "dictionary_entries_seeded": result.get("dictionary_entries_seeded", 0),
                "artifacts": ["toc_sections.json", "dictionary.seed.json"]
            }

            logger.info(f"Pass A completed: {len(result.get('sections', []))} sections extracted")

        except Exception as e:
            logger.error(f"Pass A failed: {str(e)}")
            raise PipelineError(f"Pass A failed: {str(e)}")

    async def _run_pass_b(self) -> None:
        """Run Pass B: Fast Split (≤10 MB parts)."""
        self.current_pass = "pass_b_split"
        logger.info(f"Running Pass B: Fast Split")

        try:
            job_source = self.job_dir / self.source_file.name
            result = process_pass_b(job_source, self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_b_split"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "split_required": result.get("split_required", False),
                "parts_created": result.get("parts_created", 0),
                "total_size_mb": result.get("total_size_mb", 0),
                "artifacts": result.get("artifacts", [])
            }

            logger.info(f"Pass B completed: split_required={result.get('split_required')}, parts={result.get('parts_created', 0)}")

        except Exception as e:
            logger.error(f"Pass B failed: {str(e)}")
            raise PipelineError(f"Pass B failed: {str(e)}")

    async def _run_pass_c(self) -> None:
        """Run Pass C: Extraction (Unstructured.io)."""
        self.current_pass = "pass_c_extraction"
        logger.info(f"Running Pass C: Extraction")

        try:
            job_source = self.job_dir / self.source_file.name
            result = process_pass_c(job_source, self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_c_extraction"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "chunks_extracted": result.get("chunks_extracted", 0),
                "ocr_pages_processed": result.get("ocr_pages_processed", 0),
                "dictionary_proposals": result.get("dictionary_proposals", 0),
                "artifacts": ["chunks.jsonl", "dict_delta.passC.json"]
            }

            logger.info(f"Pass C completed: {result.get('chunks_extracted', 0)} chunks extracted")

        except Exception as e:
            logger.error(f"Pass C failed: {str(e)}")
            raise PipelineError(f"Pass C failed: {str(e)}")

    async def _run_pass_d(self) -> None:
        """Run Pass D: Normalize + Embeddings (Haystack)."""
        self.current_pass = "pass_d_embeddings"
        logger.info(f"Running Pass D: Normalize + Embeddings")

        try:
            result = process_pass_d(self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_d_embeddings"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "chunks_processed": result.get("chunks_processed", 0),
                "vectors_upserted": result.get("vectors_upserted", 0),
                "dictionary_proposals": result.get("dictionary_proposals", 0),
                "artifacts": ["dict_delta.passD.json"]
            }

            logger.info(f"Pass D completed: {result.get('vectors_upserted', 0)} vectors upserted")

        except Exception as e:
            logger.error(f"Pass D failed: {str(e)}")
            raise PipelineError(f"Pass D failed: {str(e)}")

    async def _run_pass_e(self) -> None:
        """Run Pass E: Graph Compile (LlamaIndex)."""
        self.current_pass = "pass_e_graph"
        logger.info(f"Running Pass E: Graph Compile")

        try:
            result = process_pass_e(self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_e_graph"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "nodes_created": result.get("nodes_created", 0),
                "edges_created": result.get("edges_created", 0),
                "dictionary_proposals": result.get("dictionary_proposals", 0),
                "artifacts": ["graph.json", "dict_delta.passE.json"]
            }

            logger.info(f"Pass E completed: {result.get('nodes_created', 0)} nodes, {result.get('edges_created', 0)} edges")

        except Exception as e:
            logger.error(f"Pass E failed: {str(e)}")
            raise PipelineError(f"Pass E failed: {str(e)}")

    async def _run_pass_f(self) -> None:
        """Run Pass F: Validation & Manifest."""
        self.current_pass = "pass_f_validation"
        logger.info(f"Running Pass F: Validation & Manifest")

        try:
            result = process_pass_f(self.job_dir, self.job_id)

            # Update manifest
            self.manifest["pass_f_validation"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "integrity_checks_passed": result.get("integrity_checks_passed", 0),
                "dictionary_deltas_merged": result.get("dictionary_deltas_merged", False),
                "checksums_verified": result.get("checksums_verified", True),
                "artifacts": ["dict_delta.all.json", "manifest.json"]
            }

            logger.info(f"Pass F completed: integrity checks passed")

        except Exception as e:
            logger.error(f"Pass F failed: {str(e)}")
            raise PipelineError(f"Pass F failed: {str(e)}")

    async def _run_pass_g(self) -> None:
        """Run Pass G: HGRN Consistency Check."""
        self.current_pass = "pass_g_hgrn"
        logger.info(f"Running Pass G: HGRN Consistency Check")

        try:
            report, delta, actions = run_hgrn_consistency_check(self.job_dir)

            # Update manifest
            self.manifest["pass_g_hgrn"] = {
                "completed_at": datetime.utcnow().isoformat(),
                "issues_found": report["hgrn_consistency_report"]["total_issues"],
                "critical_issues": report["hgrn_consistency_report"]["severity_breakdown"]["critical"],
                "proposed_changes": delta["pass_g_hgrn_consistency"]["change_count"],
                "recommended_actions": actions["hgrn_actions"]["action_count"],
                "artifacts": ["hgrn.report.json", "dict_delta.passG.json", "hgrn.actions.json"]
            }

            logger.info(f"Pass G completed: {report['hgrn_consistency_report']['total_issues']} issues found")

        except Exception as e:
            logger.error(f"Pass G failed: {str(e)}")
            raise PipelineError(f"Pass G failed: {str(e)}")

    async def _write_manifest(self) -> None:
        """Write updated manifest to disk."""
        manifest_path = self.job_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2)


async def run_ingestion_pipeline(job_id: str, source_file: Path) -> Dict[str, Any]:
    """
    Run complete ingestion pipeline for a document.

    Args:
        job_id: Unique job identifier
        source_file: Path to source document

    Returns:
        Final pipeline manifest

    Raises:
        PipelineError: If pipeline execution fails
    """
    # Get environment root
    env_validator = get_environment_validator()
    env_root = Path(env_validator.get_environment_root())

    # Create and execute pipeline
    pipeline = IngestionPipeline(job_id, source_file, env_root)
    return await pipeline.execute()


if __name__ == "__main__":
    # Test pipeline
    import sys
    if len(sys.argv) > 2:
        test_job_id = sys.argv[1]
        test_file = Path(sys.argv[2])
        result = asyncio.run(run_ingestion_pipeline(test_job_id, test_file))
        print(f"Pipeline result: {result['status']}")