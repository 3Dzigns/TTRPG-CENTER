#!/usr/bin/env python3
"""Run the FR-004 health report generation workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from src_common.admin.health import AdminHealthService


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily health reports")
    parser.add_argument("--environment", default="dev", help="Environment to profile (default: dev)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if report already exists")
    parser.add_argument("--output", type=Path, default=None, help="Optional override for health artifacts root")
    args = parser.parse_args()

    service = AdminHealthService(base_dir=args.output) if args.output else AdminHealthService()
    result = service.generate_daily_report(args.environment, force=args.force)
    print(f"Generated: {result['generated']} -> {result['environment']} {result['date']}")
    print(f"Report metrics: {result['report']['metrics']}")
    print(f"Actions queued: {len(result['actions'])}")


if __name__ == "__main__":
    main()
