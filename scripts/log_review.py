#!/usr/bin/env python3
"""
CLI for FR-003: Log Review & Automatic Bug Bundle Creation.

Usage:
  python -m scripts.log_review --env dev --hours 24 --max 5 --min 1
"""

import argparse
import asyncio
import os
from pathlib import Path

from src_common.log_review import LogReviewService


def parse_args():
    p = argparse.ArgumentParser(description="Log review and automatic bug bundling")
    p.add_argument("--env", dest="environment", default=os.getenv("APP_ENV", "dev"))
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--max", dest="max_bundles", type=int, default=5)
    p.add_argument("--min", dest="min_count", type=int, default=1)
    p.add_argument("--base", dest="base_dir", default=".")
    return p.parse_args()


def main():
    args = parse_args()
    svc = LogReviewService(base_dir=Path(args.base_dir))
    summary = asyncio.run(
        svc.auto_create_bug_bundles(
            environment=args.environment,
            hours=args.hours,
            max_bundles=args.max_bundles,
            min_count_threshold=args.min_count,
        )
    )
    print(summary)


if __name__ == "__main__":
    main()
