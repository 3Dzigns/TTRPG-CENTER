#!/usr/bin/env python3
"""
6-Pass Bulk Ingestion System

Implements the new BUG-018 specification with 6 distinct passes:
- Pass A: ToC Parse (Prime Dictionary)
- Pass B: Logical Split (>25 MB)
- Pass C: Unstructured.io (Extraction)
- Pass D: Haystack (Vector & Enrichment)
- Pass E: LlamaIndex (Graph & Cross-Refs)
- Pass F: Clean Up (Finalize)

Features:
- Per-source barriers (no pass advance until current pass completes)
- Atomic writes and resume integrity checking
- Comprehensive manifest validation
- Concurrent processing with dependency management
- Timestamped logging and artifact management

Usage:
  python scripts/bulk_ingest.py --env dev --threads 4 --upload-dir uploads
  python scripts/bulk_ingest.py --env dev --resume --cleanup-days 14
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import threading

# Ensure repo root on path
from pathlib import Path as _P
import sys as _sys

_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

from src_common.logging import setup_logging, get_logger
from src_common.astra_loader import AstraLoader
from src_common.ttrpg_secrets import _load_env_file
from src_common.ssl_bypass import configure_ssl_bypass_for_development

# Import new 6-pass system
from src_common.pass_a_toc_parser import process_pass_a
from src_common.pass_b_logical_splitter import process_pass_b
from src_common.pass_c_extraction import process_pass_c
from src_common.pass_d_vector_enrichment import process_pass_d
from src_common.pass_e_graph_builder import process_pass_e
from src_common.pass_f_finalizer import process_pass_f

logger = get_logger("bulk_ingest")


@dataclass
class StepTiming:
    """Timing for a processing step"""
    name: str
    start_ms: int
    end_ms: int
    
    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class Source6PassResult:
    """Result of processing a single source through 6-pass pipeline"""
    source: str
    job_id: str
    timings: List[StepTiming]
    pass_results: Dict[str, Dict]
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "job_id": self.job_id,
            "success": self.success,
            "error": self.error,
            "timings": [
                {
                    "step": t.name, 
                    "duration_ms": t.duration_ms, 
                    "start_ms": t.start_ms, 
                    "end_ms": t.end_ms
                } 
                for t in self.timings
            ],
            "pass_results": self.pass_results,
            "total_time_ms": sum(t.duration_ms for t in self.timings)
        }


class Pass6Pipeline:
    """6-Pass Pipeline Orchestrator"""
    
    def __init__(self, env: str):
        self.env = env
        self.source_locks = {}  # Per-source locks for barrier control
        self.lock = threading.Lock()  # Global lock for source_locks dict
    
    def get_source_lock(self, source_path: Path) -> threading.Lock:
        """Get or create a per-source lock for barrier control"""
        source_key = str(source_path)
        with self.lock:
            if source_key not in self.source_locks:
                self.source_locks[source_key] = threading.Lock()
            return self.source_locks[source_key]
    
    def process_source_6pass(
        self, 
        pdf_path: Path, 
        env: str, 
        *, 
        resume: bool = False,
        force_dict_init: bool = False
    ) -> Source6PassResult:
        """
        Process a source through the complete 6-pass pipeline
        
        Args:
            pdf_path: Path to source PDF
            env: Environment (dev/test/prod)
            resume: Whether to resume from existing artifacts
            
        Returns:
            Source6PassResult with comprehensive results
        """
        
        # Per-source barrier: acquire lock for this source
        source_lock = self.get_source_lock(pdf_path)
        
        with source_lock:
            return self._process_source_sequential(pdf_path, env, resume=resume, force_dict_init=force_dict_init)
    
    def _process_source_sequential(
        self, 
        pdf_path: Path, 
        env: str, 
        resume: bool = False,
        force_dict_init: bool = False
    ) -> Source6PassResult:
        """Process source through all passes sequentially (with barrier control)"""
        
        job_id = self._job_id_for(pdf_path)
        output_dir = Path(f"artifacts/ingest/{env}/{job_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timings: List[StepTiming] = []
        pass_results: Dict[str, Dict] = {}
        
        logger.info(f"Starting 6-pass pipeline for {pdf_path.name} (job: {job_id})")
        
        try:
            # Pass A: ToC Parse (Prime Dictionary)
            t0 = self._now_ms()
            if self._should_run_pass("A", output_dir, resume) or force_dict_init:
                if force_dict_init:
                    logger.info(f"Force running Pass A (dict init) for {pdf_path.name}")
                else:
                    logger.info(f"Running Pass A for {pdf_path.name}")
                pass_a_result = process_pass_a(pdf_path, output_dir, job_id, env, force_dict_init=force_dict_init)
                if not pass_a_result.success:
                    raise RuntimeError(f"Pass A failed: {pass_a_result.error_message}")
                pass_results["A"] = asdict(pass_a_result)
            else:
                logger.info("Pass A artifacts exist; skipping for resume")
                pass_results["A"] = {"skipped": True}
            
            t1 = self._now_ms()
            timings.append(StepTiming("pass_a_toc_parse", t0, t1))
            
            # Pass B: Logical Split (>25 MB)
            t2 = self._now_ms()
            if self._should_run_pass("B", output_dir, resume):
                logger.info(f"Running Pass B for {pdf_path.name}")
                pass_a_manifest = output_dir / "manifest.json"
                pass_b_result = process_pass_b(pdf_path, output_dir, job_id, env, pass_a_manifest)
                if not pass_b_result.success:
                    raise RuntimeError(f"Pass B failed: {pass_b_result.error_message}")
                pass_results["B"] = asdict(pass_b_result)
            else:
                logger.info("Pass B artifacts exist; skipping for resume")
                pass_results["B"] = {"skipped": True}
            
            t3 = self._now_ms()
            timings.append(StepTiming("pass_b_logical_split", t2, t3))
            
            # Pass C: Unstructured.io (Extraction)
            t4 = self._now_ms()
            if self._should_run_pass("C", output_dir, resume):
                logger.info(f"Running Pass C for {pdf_path.name}")
                pass_c_result = process_pass_c(pdf_path, output_dir, job_id, env)
                if not pass_c_result.success:
                    raise RuntimeError(f"Pass C failed: {pass_c_result.error_message}")
                pass_results["C"] = asdict(pass_c_result)
            else:
                logger.info("Pass C artifacts exist; skipping for resume")
                pass_results["C"] = {"skipped": True}
            
            t5 = self._now_ms()
            timings.append(StepTiming("pass_c_extraction", t4, t5))
            
            # Pass D: Haystack (Vector & Enrichment)
            t6 = self._now_ms()
            if self._should_run_pass("D", output_dir, resume):
                logger.info(f"Running Pass D for {pdf_path.name}")
                pass_d_result = process_pass_d(output_dir, job_id, env)
                if not pass_d_result.success:
                    raise RuntimeError(f"Pass D failed: {pass_d_result.error_message}")
                pass_results["D"] = asdict(pass_d_result)
            else:
                logger.info("Pass D artifacts exist; skipping for resume")
                pass_results["D"] = {"skipped": True}
            
            t7 = self._now_ms()
            timings.append(StepTiming("pass_d_vector_enrichment", t6, t7))
            
            # Pass E: LlamaIndex (Graph & Cross-Refs)
            t8 = self._now_ms()
            if self._should_run_pass("E", output_dir, resume):
                logger.info(f"Running Pass E for {pdf_path.name}")
                pass_e_result = process_pass_e(output_dir, job_id, env)
                if not pass_e_result.success:
                    raise RuntimeError(f"Pass E failed: {pass_e_result.error_message}")
                pass_results["E"] = asdict(pass_e_result)
            else:
                logger.info("Pass E artifacts exist; skipping for resume")
                pass_results["E"] = {"skipped": True}
            
            t9 = self._now_ms()
            timings.append(StepTiming("pass_e_graph_builder", t8, t9))
            
            # Pass F: Clean Up (Finalize)
            t10 = self._now_ms()
            logger.info(f"Running Pass F (finalization) for {pdf_path.name}")
            pass_f_result = process_pass_f(output_dir, job_id, env)
            if not pass_f_result.success:
                raise RuntimeError(f"Pass F failed: {pass_f_result.error_message}")
            pass_results["F"] = asdict(pass_f_result)
            
            t11 = self._now_ms()
            timings.append(StepTiming("pass_f_finalization", t10, t11))
            
            logger.info(f"6-pass pipeline completed for {pdf_path.name}")
            
            return Source6PassResult(
                source=pdf_path.name,
                job_id=job_id,
                timings=timings,
                pass_results=pass_results,
                success=True
            )
            
        except Exception as e:
            logger.error(f"6-pass pipeline failed for {pdf_path.name}: {e}")
            return Source6PassResult(
                source=pdf_path.name,
                job_id=job_id,
                timings=timings,
                pass_results=pass_results,
                success=False,
                error=str(e)
            )
    
    def _should_run_pass(self, pass_id: str, output_dir: Path, resume: bool) -> bool:
        """Check if a pass should be run based on resume logic and existing artifacts"""
        
        if not resume:
            return True
        
        # Check manifest for completed passes
        manifest_path = output_dir / "manifest.json"
        if manifest_path.exists():
            try:
                from src_common.artifact_validator import load_json_with_retry
                manifest_data = load_json_with_retry(manifest_path)
                completed_passes = manifest_data.get("completed_passes", [])
                return pass_id not in completed_passes
            except Exception as e:
                logger.warning(f"Failed to read manifest for resume check: {e}")
                return True
        
        return True
    
    def _job_id_for(self, pdf_path: Path) -> str:
        """Generate consistent job ID for a PDF"""
        import hashlib
        name_hash = hashlib.md5(pdf_path.name.encode()).hexdigest()[:8]
        return f"job_{int(time.time())}_{name_hash}"
    
    def _now_ms(self) -> int:
        """Current timestamp in milliseconds"""
        return int(time.time() * 1000)


def cleanup_old_artifacts(env: str, days_to_keep: int = 7) -> None:
    """Remove old ingestion artifacts older than specified days."""
    artifacts_dir = Path("artifacts") / "ingest" / env
    if not artifacts_dir.exists():
        logger.info(f"No artifacts directory found: {artifacts_dir}")
        return

    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    removed_count = 0
    removed_size = 0

    for job_dir in artifacts_dir.iterdir():
        if job_dir.is_dir():
            try:
                # Check directory modification time
                dir_mtime = job_dir.stat().st_mtime
                if dir_mtime < cutoff_time:
                    # Calculate size before removal
                    dir_size = sum(f.stat().st_size for f in job_dir.rglob('*') if f.is_file())
                    
                    # Remove old job directory
                    import shutil
                    shutil.rmtree(job_dir)
                    removed_count += 1
                    removed_size += dir_size
                    logger.info(f"Removed old artifact directory: {job_dir.name} ({dir_size} bytes)")
                    
            except Exception as e:
                logger.warning(f"Failed to process artifact directory {job_dir}: {e}")

    if removed_count > 0:
        logger.info(f"Cleanup completed: removed {removed_count} directories, freed {removed_size} bytes")
    else:
        logger.info("No old artifacts found for cleanup")


def setup_environment(env: str) -> None:
    """Setup environment configuration and SSL bypass"""
    
    # Load environment files
    project_root = Path(__file__).resolve().parents[1]
    root_env = project_root / ".env"
    if root_env.exists():
        _load_env_file(root_env)
    
    env_env = project_root / "env" / env / "config" / ".env"
    if env_env.exists():
        _load_env_file(env_env)
    
    # Configure SSL bypass for development environment
    configure_ssl_bypass_for_development()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="6-Pass Bulk Ingestion System")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    parser.add_argument("--threads", type=int, default=4, help="Concurrent processing threads")
    parser.add_argument("--upload-dir", default="uploads", help="Directory containing PDFs")
    parser.add_argument("--empty-first", action="store_true", help="Empty Astra collections first")
    parser.add_argument("--empty-dict-first", action="store_true", help="Empty dictionary collection first")
    parser.add_argument("--force-dict-init", action="store_true", help="Force dictionary initialization even if exists")
    parser.add_argument("--resume", action="store_true", help="Resume from existing artifacts")
    parser.add_argument("--cleanup-days", type=int, default=7, help="Days to keep artifacts")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip artifact cleanup")
    parser.add_argument("--no-logfile", action="store_true", help="No log file, console only")
    
    args = parser.parse_args(argv)
    
    # Setup environment
    setup_environment(args.env)
    
    # Setup logging
    log_file = None
    if not args.no_logfile:
        env_dir = Path(f"env/{args.env}")
        env_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = env_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"bulk_ingest_{timestamp}.log"
    
    setup_logging()
    
    logger.info(f"Starting 6-pass bulk ingestion - env: {args.env}, threads: {args.threads}")
    
    # Cleanup old artifacts if requested
    if not args.no_cleanup:
        cleanup_old_artifacts(args.env, args.cleanup_days)
    
    # Initialize AstraLoader and optionally empty collections
    loader = AstraLoader(args.env)
    
    if args.empty_first:
        logger.info("Emptying Astra collections...")
        if not loader.empty_collection():
            logger.error("Failed to empty Astra collection")
            return 1
    
    # Handle dictionary collection emptying
    if args.empty_first or args.empty_dict_first:
        from src_common.dictionary_loader import DictionaryLoader
        dict_loader = DictionaryLoader(args.env)
        try:
            if dict_loader.client:
                dict_collection = dict_loader.client.get_collection(dict_loader.collection_name)
                dict_collection.delete_many({})
                logger.info("Emptied dictionary collection")
            else:
                logger.info("SIMULATION: Would empty dictionary collection")
        except Exception as e:
            logger.warning(f"Failed to empty dictionary collection: {e}")
    
    # Find PDFs to process
    upload_dir = Path(args.upload_dir)
    if not upload_dir.exists():
        logger.error(f"Upload directory not found: {upload_dir}")
        return 1
    
    pdfs = list(upload_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No PDFs found in {upload_dir}")
        return 0
    
    logger.info(f"Found {len(pdfs)} PDFs to process")
    
    # Process PDFs with 6-pass pipeline
    start_ts = int(time.time() * 1000)
    results: List[Source6PassResult] = []
    pipeline = Pass6Pipeline(args.env)
    
    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        futs = [
            ex.submit(
                pipeline.process_source_6pass,
                pdf,
                args.env,
                resume=args.resume,
                force_dict_init=args.force_dict_init,
            )
            for pdf in pdfs
        ]
        
        for fut in cf.as_completed(futs):
            try:
                res = fut.result()
                results.append(res)
                status = "OK" if res.success else f"FAIL: {res.error}"
                logger.info(f"Completed {res.source}: {status}")
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    end_ts = int(time.time() * 1000)
    elapsed_ms = end_ts - start_ts
    
    # Summary artifact
    summary_dir = Path(f"artifacts/ingest/{args.env}")
    summary_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("bulk_6pass_%Y%m%d_%H%M%S")
    summary_file = summary_dir / f"{run_id}_summary.json"
    
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "pipeline_version": "6-pass-system",
                    "env": args.env,
                    "run_id": run_id,
                    "threads": args.threads,
                    "elapsed_ms": elapsed_ms,
                    "sources": [r.to_dict() for r in results],
                    "summary_stats": {
                        "total_sources": len(results),
                        "successful": sum(1 for r in results if r.success),
                        "failed": sum(1 for r in results if not r.success),
                        "total_passes_completed": sum(
                            len([p for p in r.pass_results.keys() if not r.pass_results[p].get("skipped", False)])
                            for r in results if r.success
                        )
                    }
                },
                f,
                indent=2,
            )
        logger.info(f"Wrote summary: {summary_file}")
    except Exception as e:
        logger.warning(f"Failed writing summary: {e}")
    
    # Print console summary
    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    logger.info(
        f"6-pass bulk ingestion complete in {elapsed_ms}ms — {ok} ok, {fail} failed"
    )
    
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))