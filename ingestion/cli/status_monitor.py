"""
Status monitor CLI with optional deep inspection across backing stores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, List

from ingestion.config import Settings
from ingestion.core.db.cassandra_store import get_cassandra_store
from ingestion.core.db.dictionary import get_dictionary_store
from ingestion.core.job_registry import JobRecord, JobRegistry


def _match_source(record: JobRecord, target: str) -> bool:
    if record.source_path == target:
        return True
    return Path(record.source_path).name == Path(target).name


def _collect_rows(jobs: Iterable[JobRecord], *, deep: bool) -> List[dict[str, Any]]:
    settings = Settings()
    dictionary_store = get_dictionary_store(settings) if deep else None
    cassandra_store = get_cassandra_store(settings) if deep else None

    rows: List[dict[str, Any]] = []
    for job in jobs:
        row = {
            "job_id": job.job_id,
            "source": job.source_path,
            "state": job.state.value,
            "stage": job.stage,
            "refresh": job.refresh,
            "expected_checksum": job.expected_checksum or "",
            "expected_count": job.expected_count or 0,
            "updated_at": job.updated_at.isoformat(),
            "message": job.message or "",
        }
        if deep:
            try:
                row["dictionary_terms"] = dictionary_store.count_terms(job.job_id)  # type: ignore[union-attr]
            except Exception:
                row["dictionary_terms"] = None
            try:
                cassandra_rows = cassandra_store.fetch_source(job.job_id)  # type: ignore[union-attr]
                row["cassandra_rows"] = len(cassandra_rows)
            except Exception:
                row["cassandra_rows"] = None
        rows.append(row)
    return rows


def _format_table(rows: List[dict[str, Any]], *, deep: bool) -> str:
    base_headers = [
        "job_id",
        "source",
        "state",
        "stage",
        "refresh",
        "expected_checksum",
        "expected_count",
        "updated_at",
        "message",
    ]
    if deep:
        base_headers.extend(["dictionary_terms", "cassandra_rows"])

    lines = [" | ".join(base_headers)]
    lines.append("-+-".join("-" * len(header) for header in base_headers))
    for row in rows:
        lines.append(
            " | ".join(str(row.get(header, "")) if row.get(header) is not None else "" for header in base_headers)
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="status_monitor", description="Display job registry status."
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table.")
    parser.add_argument("--file", help="Filter by source file path or basename.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Fetch live counts from dictionary and Cassandra backends.",
    )
    args = parser.parse_args(argv)

    registry = JobRegistry.global_instance()
    jobs = list(registry.list())
    if args.file:
        jobs = [job for job in jobs if _match_source(job, args.file)]

    if not jobs:
        print("No matching jobs found.")
        return 0

    rows = _collect_rows(jobs, deep=args.deep)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(_format_table(rows, deep=args.deep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

