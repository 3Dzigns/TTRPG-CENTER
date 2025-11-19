"""
Job management CLI with confirmation prompts and operational previews.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Iterable, List

from ingestion.config import Settings
from ingestion.core.job_registry import JobRegistry, JobState, new_record
from ingestion.core.pipeline import deterministic_job_id, kickoff_ingestion
from ingestion.core.tracing import reset_tracer


def _resolve_source_path(path_str: str, settings: Settings, *, must_exist: bool) -> Path:
    candidate = Path(path_str)
    search: List[Path] = []
    if candidate.is_absolute():
        search.append(candidate)
    else:
        search.append(settings.sources_dir / candidate)
        search.append(candidate)

    for option in search:
        if option.exists():
            return option

    if must_exist:
        raise FileNotFoundError(path_str)
    return search[0]


def _print_preview(title: str, details: Iterable[str]) -> None:
    print(title)
    for line in details:
        print(f"  - {line}")


def _confirm(proceed: bool, assume_yes: bool) -> bool:
    if assume_yes:
        print("Proceeding (auto-confirm).")
        return True
    try:
        answer = input("Proceed? [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer in {"y", "yes"}:
        return True
    if proceed:
        print("Operation cancelled.")
    return False


def _start(registry: JobRegistry, settings: Settings, file_path: str, refresh: bool, assume_yes: bool) -> int:
    try:
        source_path = _resolve_source_path(file_path, settings, must_exist=True)
    except FileNotFoundError:
        print(f"Source file not found: {file_path}", file=sys.stderr)
        return 1

    job_id = deterministic_job_id(source_path)
    _print_preview(
        "Manual ingestion preview:",
        [
            f"Source: {source_path}",
            f"Job ID: {job_id}",
            f"Refresh: {refresh}",
            "Effect: Kick off ingestion pipeline (Unstructured → dictionary → embeddings).",
        ],
    )
    if not _confirm(True, assume_yes):
        return 1

    kickoff_ingestion(source_path, refresh=refresh)
    print(f"Started ingestion job {job_id} for {source_path}.")
    return 0


def _mark_unhealthy(registry: JobRegistry, source: str, assume_yes: bool) -> int:
    affected = [job for job in registry.list() if job.source_path == source]
    if not affected:
        print(f"No job found for {source}", file=sys.stderr)
        return 1

    _print_preview(
        "Mark unhealthy preview:",
        [
            f"{job.job_id}: {job.state.value} → FAILED (stage={job.stage})"
            for job in affected
        ],
    )
    if not _confirm(True, assume_yes):
        return 1

    for job in affected:
        registry.update_state(
            job.job_id,
            state=JobState.FAILED,
            stage="job_management",
            message="Marked unhealthy via CLI",
        )
    print(f"Marked {len(affected)} job(s) for {source} as FAILED.")
    return 0


def _remove(registry: JobRegistry, settings: Settings, source: str, assume_yes: bool) -> int:
    source_path = _resolve_source_path(source, settings, must_exist=False)
    existing = [job for job in registry.list() if job.source_path == str(source_path)]
    removal_job_id = f"remove-{uuid.uuid4().hex[:8]}"

    preview_lines = [
        f"Source: {source_path}",
        f"Removal job ID: {removal_job_id}",
        "Effect: Enqueue housekeeping removal (dictionary, embeddings, artifacts).",
    ]
    if existing:
        preview_lines.append(
            "Existing jobs impacted: " + ", ".join(job.job_id for job in existing)
        )

    _print_preview("Removal preview:", preview_lines)
    if not _confirm(True, assume_yes):
        return 1

    registry.upsert(
        new_record(
            job_id=removal_job_id,
            source_path=str(source_path),
            state=JobState.QUEUED,
            refresh=False,
            stage="job_management.remove",
            message="Removal job enqueued via CLI",
        )
    )
    # Execute removal inline to keep behaviour deterministic during tests/local runs.
    try:
        from ingestion.workers.housekeeping.tasks import remove_source

        remove_source(None, removal_job_id, str(source_path))
    except Exception as exc:  # pragma: no cover - best effort
        print(f"Failed to execute removal immediately: {exc}", file=sys.stderr)

    print(f"Removal job {removal_job_id} created for {source_path}.")
    return 0


def _format_dlq_table(entries: List[dict]) -> str:
    headers = ["timestamp", "job_id", "task", "message", "retries"]
    lines = [" | ".join(headers)]
    lines.append("-+-".join("-" * len(header) for header in headers))
    for item in entries:
        message = item.get("message") or item.get("error") or item.get("exc") or ""
        if isinstance(message, dict):
            message = message.get("message", "")
        message = str(message)
        if len(message) > 60:
            message = message[:57] + "..."
        retries = item.get("retries")
        line = [
            str(item.get("timestamp", "")),
            str(item.get("job_id", "")),
            str(item.get("task", "")),
            message,
            "" if retries is None else str(retries),
        ]
        lines.append(" | ".join(line))
    return "\n".join(lines)


def _parse_dlq_entries(dlq_file: Path) -> List[dict]:
    try:
        lines = dlq_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Failed to read DLQ file: {exc}") from exc

    entries: List[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            entries.append({"raw": line})
            continue
        entries.append(record)
    return entries


def _dlq_inspect(limit: int, *, job: str | None, task: str | None, contains: str | None, as_json: bool) -> int:
    settings = Settings()
    dlq_file = settings.jobs_dir / "dlq.jsonl"
    if not dlq_file.exists():
        print("No DLQ entries found.")
        return 0

    try:
        entries = _parse_dlq_entries(dlq_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Sort newest first using timestamp when available, otherwise preserve file order.
    indexed_entries = list(enumerate(entries))
    indexed_entries.sort(key=lambda pair: (pair[1].get("timestamp") or "", pair[0]))
    entries = [item for _, item in indexed_entries]
    filtered: List[dict] = []
    lowered = contains.lower() if contains else None
    for entry in entries:
        if job and entry.get("job_id") != job:
            continue
        if task and entry.get("task") != task:
            continue
        if lowered:
            blob = json.dumps(entry, ensure_ascii=False).lower()
            if lowered not in blob:
                continue
        filtered.append(entry)

    if not filtered:
        print("No matching DLQ entries found.")
        return 0

    limited = filtered[-limit:] if limit > 0 else filtered

    if as_json:
        print(json.dumps(limited, indent=2, ensure_ascii=False))
    else:
        print(_format_dlq_table(limited))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="job_management",
        description="Manage ingestion jobs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Manually enqueue a job.")
    start_parser.add_argument("--file", required=True, help="Source file path.")
    start_parser.add_argument("--refresh", action="store_true", help="Mark as refresh job.")
    start_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")

    unhealthy_parser = subparsers.add_parser(
        "mark-unhealthy", help="Mark job(s) for a source as unhealthy."
    )
    unhealthy_parser.add_argument("--file", required=True, help="Source file path.")
    unhealthy_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")

    remove_parser = subparsers.add_parser("remove", help="Enqueue a removal job.")
    remove_parser.add_argument("--file", required=True, help="Source file path.")
    remove_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")

    dlq_parser = subparsers.add_parser("dlq-inspect", help="Show DLQ entries.")
    dlq_parser.add_argument("--limit", type=int, default=10, help="Number of entries to show (use 0 for all).")
    dlq_parser.add_argument("--job", help="Filter by job_id.")
    dlq_parser.add_argument("--task", help="Filter by task name.")
    dlq_parser.add_argument("--contains", help="Filter entries whose JSON contains this string.")
    dlq_parser.add_argument("--json", action="store_true", help="Output results as JSON.")

    args = parser.parse_args(argv)
    settings = Settings()
    registry = JobRegistry.global_instance()

    if args.command == "start":
        return _start(registry, settings, args.file, args.refresh, args.yes)
    if args.command == "mark-unhealthy":
        return _mark_unhealthy(registry, args.file, args.yes)
    if args.command == "remove":
        return _remove(registry, settings, args.file, args.yes)
    if args.command == "dlq-inspect":
        limit = max(args.limit, 0)
        return _dlq_inspect(
            limit,
            job=args.job,
            task=args.task,
            contains=args.contains,
            as_json=args.json,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    reset_tracer()
    raise SystemExit(main())
