#!/usr/bin/env python3
"""
unstructured_job_cli.py - Inspect asynchronous Unstructured jobs.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from path_utils import resolve_transfer_path

DEFAULT_JOBS_ROOT = resolve_transfer_path("jobs/unstructured")


def load_status(job_dir: Path) -> Dict[str, Any]:
    status_path = job_dir / "status.json"
    if not status_path.exists():
        raise FileNotFoundError(f"Status file not found for job {job_dir.name}")
    with status_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def print_summary(job_id: str, status: Dict[str, Any]) -> None:
    print(f"Job: {job_id}")
    print(f"  State: {status.get('state')}")
    if status.get("error"):
        print(f"  Error: {status['error']}")
    print(f"  Worker: {status.get('worker') or 'unassigned'}")
    print(f"  Created: {status.get('created_at')}")
    if status.get("claimed_at"):
        print(f"  Claimed: {status['claimed_at']}")
    if status.get("completed_at"):
        print(f"  Completed: {status['completed_at']}")
    print(f"  Updated: {status.get('updated_at')}")

    statistics = status.get("statistics") or {}
    if statistics:
        print("\n  Statistics:")
        for key, value in statistics.items():
            if key == "stages":
                continue
            print(f"    {key}: {value}")

        stages = statistics.get("stages") or status.get("stages") or {}
        if stages:
            print("\n  Stages:")
            for stage, data in stages.items():
                state = data.get("status", "unknown")
                duration = data.get("duration_seconds")
                line = f"    {stage}: {state}"
                if duration is not None:
                    line += f" ({duration:.2f}s)" if isinstance(duration, (int, float)) else f" ({duration}s)"
                print(line)
                if data.get("error"):
                    print(f"      Error: {data['error']}")

    outputs = status.get("outputs") or {}
    if outputs:
        print("\n  Outputs:")
        for name, value in outputs.items():
            print(f"    {name}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Unstructured job metadata",
        add_help=True,
    )
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_ROOT, help="Jobs directory (default: Transfer Station share)")
    parser.add_argument("--status", metavar="JOB_ID", help="Show status for a specific job identifier")
    parser.add_argument("--json", action="store_true", help="Output raw JSON for status queries")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    jobs_root = args.jobs_dir

    if not jobs_root.exists():
        print(f"Jobs directory not found: {jobs_root}", file=sys.stderr)
        return 1

    if not args.status:
        print("Queued jobs:")
        for job_dir in sorted(jobs_root.iterdir()):
            if not job_dir.is_dir():
                continue
            status_path = job_dir / "status.json"
            if not status_path.exists():
                continue
            try:
                status = load_status(job_dir)
            except Exception as exc:
                print(f"- {job_dir.name}: error reading status ({exc})")
                continue
            print(f"- {job_dir.name}: {status.get('state', 'unknown')} (updated {status.get('updated_at')})")
        return 0

    job_dir = jobs_root / args.status
    if not job_dir.exists():
        print(f"Job not found: {job_dir}", file=sys.stderr)
        return 1

    try:
        status = load_status(job_dir)
    except Exception as exc:
        print(f"Failed to load status: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print_summary(args.status, status)

    return 0


if __name__ == "__main__":
    sys.exit(main())
