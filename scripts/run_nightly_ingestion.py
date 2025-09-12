#!/usr/bin/env python3
"""
Nightly ingestion runner that scans upload directories, enqueues documents,
and executes the 6-pass pipeline using the FR-002 scheduler components.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import List

import os
import contextlib
import time
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))  # ensure repo root on path

from src_common.document_scanner import DocumentScanner
from src_common.processing_queue import ProcessingQueue
from src_common.pipeline_adapter import Pass6PipelineAdapter
from src_common.scheduled_processor import ScheduledBulkProcessor
from src_common.job_manager import Job, JobStatus
from src_common.logging import setup_logging, get_logger
from src_common.ttrpg_secrets import load_env
from src_common.preflight_checks import run_preflight_checks, PreflightError


async def main_async(env: str, uploads: List[str], artifacts_base: Path, log_file: Path, max_concurrent: int = 2) -> int:
    # Configure environment + logging
    os.environ["APP_ENV"] = env
    # Load .env files (root + env-specific)
    try:
        project_root = Path(__file__).resolve().parents[1]
        load_env(project_root / f"env/{env}")
    except Exception as e:
        # Fail-fast? For now, log and continue; downstream passes may enforce strictness
        pass
    setup_logging(log_file=log_file)
    logger = get_logger("nightly_runner")

    # Preflight dependency validation (warn-only in nightly to avoid full aborts)
    try:
        run_preflight_checks()
        logger.info("Preflight dependency checks passed (Poppler/Tesseract available)")
    except PreflightError as e:
        logger.warning(f"Preflight checks failed: {e}. Continuing nightly run (dev mode), but PDF processing may fail.")

    # Performance-oriented defaults for nightly runs
    # 1) Reduce heavy model cost by default; allow override via environment
    os.environ.setdefault("PASS_C_INFER_TABLES", os.getenv("PASS_C_INFER_TABLES", "true"))
    # 2) Provide persistent model cache directories to avoid re-downloads across jobs
    try:
        project_root = Path(__file__).resolve().parents[1]
        cache_root = project_root / "env" / env / "cache" / "hf"
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_root))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_root / "hub"))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root / "transformers"))
        os.environ.setdefault("TIMM_HOME", str(cache_root / "timm"))
    except Exception:
        pass

    logger.info(f"Nightly ingestion starting for env={env}")
    logger.info(f"Uploads: {uploads}")
    logger.info(f"Artifacts base: {artifacts_base}")
    logger.info(f"Runtime info: cwd={os.getcwd()}, python={_sys.executable}")

    scanner = DocumentScanner(uploads, supported_extensions=(".pdf",), scan_interval_seconds=1)
    scanner.start_monitoring()
    await asyncio.sleep(1.5)  # Initial scan
    docs = scanner.get_discovered_documents()
    scanner.stop_monitoring()

    queue = ProcessingQueue(state_file=artifacts_base.parent / "queue_state" / "processing_queue.json")
    for d in docs:
        queue.add_document(d["path"], priority=1)
    # Log details of discovered documents (capped)
    for d in docs[:50]:
        logger.info(f"Discovered document: {d['path']}")
    logger.info(f"Discovered {len(docs)} documents; queue size now {queue.get_status().get('total_documents')}")

    pipeline = Pass6PipelineAdapter(environment=env)
    processor = ScheduledBulkProcessor(
        config={
            "environment": env,
            "artifacts_base": str(artifacts_base),
            "max_concurrent_jobs": max_concurrent,
        },
        pipeline=pipeline,
    )

    # Drain queue
    jobs = []
    while True:
        item = queue.get_next_document()
        if not item:
            break
        job = Job(
            id=f"job_{len(jobs)+1:06d}",
            name="nightly_ingestion",
            job_type="bulk_ingestion",
            source_path=item["path"],
            environment=env,
            priority=item["priority"],
            created_at=__import__("datetime").datetime.now(),
            status=JobStatus.PENDING,
        )
        jobs.append(job)
        logger.info(f"Queued job {job.id} for {job.source_path}")

    # Execute with progress and heartbeat
    tasks = [asyncio.create_task(processor.execute_job(j)) for j in jobs]
    execution_start_time = time.time()
    logger.info(f"Launching {len(tasks)} job tasks (max_concurrent={processor.max_concurrent_jobs})")
    
    # P0.3: Enhanced heartbeat with detailed slot usage and timing
    async def _heartbeat():
        try:
            heartbeat_count = 0
            while True:
                heartbeat_count += 1
                heartbeat_time = time.time()
                
                # Calculate job states
                done = sum(1 for t in tasks if t.done())
                pending = len(tasks) - done
                active_jobs = processor._active_jobs
                max_slots = processor.max_concurrent_jobs
                waiting_jobs = max(0, pending - active_jobs)
                
                # Calculate timing metrics
                elapsed_time = heartbeat_time - execution_start_time
                
                # Estimate completion time based on progress
                if done > 0:
                    avg_job_time = elapsed_time / done
                    estimated_remaining = avg_job_time * pending
                    eta_minutes = estimated_remaining / 60
                    eta_str = f", ETA: {eta_minutes:.1f}min" if eta_minutes > 1 else f", ETA: {estimated_remaining:.0f}s"
                else:
                    eta_str = ""
                
                # P0.3: Comprehensive heartbeat logging
                logger.info(
                    f"Heartbeat #{heartbeat_count} [{elapsed_time:.0f}s elapsed]: "
                    f"{done}/{len(tasks)} completed, {pending} pending, "
                    f"active slots: {active_jobs}/{max_slots}, waiting: {waiting_jobs}"
                    f"{eta_str}"
                )
                
                # P0.3: Additional detail every 5th heartbeat (2.5 minutes)
                if heartbeat_count % 5 == 0 and pending > 0:
                    # Get job details for active and waiting jobs
                    job_details = []
                    for i, (task, job) in enumerate(zip(tasks, jobs)):
                        if not task.done():
                            source_name = Path(job.source_path).name
                            if i < active_jobs:
                                job_details.append(f"{job.id}({source_name})")
                    
                    if job_details:
                        active_list = ", ".join(job_details[:max_slots])
                        logger.info(f"Active jobs: {active_list}")
                        
                        if len(job_details) > max_slots:
                            waiting_list = ", ".join(job_details[max_slots:max_slots+3])
                            waiting_suffix = f" (+{len(job_details)-max_slots-3} more)" if len(job_details) > max_slots+3 else ""
                            logger.info(f"Waiting jobs: {waiting_list}{waiting_suffix}")
                
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

    hb = asyncio.create_task(_heartbeat())
    results = []
    for t in asyncio.as_completed(tasks):
        try:
            r = await t
        except Exception as e:
            logger.exception(f"Job task raised an exception: {e}")
            # Continue to next task; include a failed result stub
            r = {
                'job_id': 'unknown',
                'status': 'failed',
                'total_time': time.time() - execution_start_time,
                'wait_time': 0,
                'processing_time': 0,
                'error_message': str(e),
            }
        results.append(r)
        
        # P0.3: Enhanced job completion logging with timing details
        total_time = r.get('total_time', 0)
        wait_time = r.get('wait_time', 0) 
        processing_time = r.get('processing_time', 0)
        job_id = r.get('job_id', 'unknown')
        status = r.get('status', 'unknown')
        
        if status == "completed":
            logger.info(
                f"Job {job_id} COMPLETED - "
                f"Total: {total_time:.1f}s (Wait: {wait_time:.1f}s, Processing: {processing_time:.1f}s), "
                f"Artifacts: {r.get('artifacts_path', 'N/A')}"
            )
        else:
            error_msg = r.get('error_message', 'Unknown error')[:100]
            logger.error(
                f"Job {job_id} FAILED - "
                f"Total: {total_time:.1f}s (Wait: {wait_time:.1f}s), "
                f"Error: {error_msg}"
            )
    hb.cancel()
    # Ensure heartbeat task is fully cancelled before exiting
    with contextlib.suppress(asyncio.CancelledError):
        await hb
    ok = sum(1 for r in results if r.get("status") == "completed")
    fail = len(results) - ok
    logger.info(f"Nightly ingestion complete: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    ap.add_argument("--uploads", action="append", required=True, help="Upload directory (repeatable)")
    ap.add_argument("--artifacts-base", default=None, help="Artifacts base directory (default: artifacts/ingest/{env})")
    ap.add_argument("--log-file", default=None, help="Optional explicit log file path for Python logger")
    ap.add_argument("--max-concurrent", type=int, default=int(os.getenv("NIGHTLY_MAX_CONCURRENT", "2")), help="Max concurrent jobs for nightly scheduler")
    args = ap.parse_args(argv)

    env = args.env
    # Resolve project root to ensure logs go under repo regardless of working dir
    project_root = Path(__file__).resolve().parents[1]
    artifacts = Path(args.artifacts_base) if args.artifacts_base else (project_root / f"artifacts/ingest/{env}")
    artifacts.mkdir(parents=True, exist_ok=True)

    logs_dir = project_root / "env" / env / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_file = Path(args.log_file) if args.log_file else (logs_dir / f"nightly_{ts}.log")

    return asyncio.run(main_async(env, args.uploads, artifacts, log_file, max_concurrent=args.max_concurrent))


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
