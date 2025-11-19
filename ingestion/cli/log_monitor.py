"""
Log monitor CLI with fan-in support and optional error filtering.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from ingestion.config import Settings

ISO_REGEX = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
)


def _is_error_line(line: str) -> bool:
    lowered = line.lower()
    if "error" in lowered or "traceback" in lowered:
        return True
    if line.startswith("{"):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return False
        for key in ("level", "severity", "log_level", "lv"):
            value = payload.get(key)
            if isinstance(value, str) and value.upper() in {"ERROR", "CRITICAL", "FATAL"}:
                return True
    return False


def _parse_timestamp(raw: str) -> datetime:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        pass
    else:
        for key in ("timestamp", "ts", "time", "@timestamp", "created_at", "created"):
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                try:
                    return datetime.fromtimestamp(float(value))
                except Exception:
                    continue
            if isinstance(value, str):
                candidate = value.replace("Z", "+00:00") if value.endswith("Z") else value
                try:
                    return datetime.fromisoformat(candidate)
                except ValueError:
                    continue
    match = ISO_REGEX.search(raw)
    if match:
        candidate = match.group("ts").replace("Z", "+00:00").replace(" ", "T")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    return datetime.min


def _tail_lines(path: Path, limit: int) -> List[str]:
    buffer: deque[str] = deque(maxlen=limit if limit > 0 else None)
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            buffer.append(line)
    return list(buffer)


def _discover_logs(root: Path, pattern: str) -> List[Path]:
    if not root.exists():
        return []
    files = [path for path in root.rglob(pattern) if path.is_file()]
    files.sort()
    return files


def _resolve_log_path(candidate: str, logs_dir: Path) -> Path:
    path = Path(candidate).expanduser()
    if path.is_file():
        return path
    alt = logs_dir / candidate
    if alt.is_file():
        return alt
    return path


def _list_logs(files: Sequence[Path]) -> None:
    if not files:
        print("No log files found.")
        return
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        print(f"{path.name}\t{path}\t{size} bytes")


def _aggregate_logs(files: Iterable[Path], tail: int, errors_only: bool) -> None:
    entries: List[Tuple[datetime, int, Path, str]] = []
    sequence = 0
    for path in files:
        try:
            lines = _tail_lines(path, tail)
        except FileNotFoundError:
            continue
        for line in lines:
            if errors_only and not _is_error_line(line):
                continue
            timestamp = _parse_timestamp(line)
            entries.append((timestamp, sequence, path, line.rstrip("\n")))
            sequence += 1

    if not entries:
        print("No log entries matched the requested filters.")
        return

    entries.sort(key=lambda item: (item[0], item[1]))
    if tail > 0:
        entries = entries[-tail:]
    for _, _, path, text in entries:
        print(f"[{path.name}] {text}")


def _emit(line: str, errors_only: bool) -> Optional[str]:
    if not errors_only or _is_error_line(line):
        return line
    return None


def _tail_single(path: Path, follow: bool, errors_only: bool) -> None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            if not follow:
                for line in stream:
                    output = _emit(line.rstrip("\n"), errors_only)
                    if output is not None:
                        print(output)
                return

            stream.seek(0, 2)
            while True:
                line = stream.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                output = _emit(line.rstrip("\n"), errors_only)
                if output is not None:
                    print(output)
    except FileNotFoundError:
        print(f"log file not found: {path}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="log_monitor",
        description="Inspect ingestion log files with optional aggregation and filtering.",
    )
    parser.add_argument("--follow", "-f", action="store_true", help="Follow a single log file.")
    parser.add_argument(
        "--file",
        help="Specific log file to tail (relative paths are resolved under the logs directory).",
    )
    parser.add_argument(
        "--errors",
        action="store_true",
        help="Only show entries with severity ERROR or higher.",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=200,
        help="Maximum number of lines to display when aggregating (default: 200).",
    )
    parser.add_argument(
        "--pattern",
        default="*.log",
        help="Glob pattern used when discovering log files (default: *.log).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the available log files and exit.",
    )
    args = parser.parse_args(argv)

    if args.tail < 0:
        parser.error("--tail must be non-negative")

    settings = Settings()
    logs_dir = settings.logs_dir

    if args.list:
        files = _discover_logs(logs_dir, args.pattern)
        _list_logs(files)
        return 0

    if args.file:
        target = _resolve_log_path(args.file, logs_dir)
        _tail_single(target, args.follow, args.errors)
        return 0

    if args.follow:
        default_path = logs_dir / "pipeline.log"
        _tail_single(default_path, True, args.errors)
        return 0

    files = _discover_logs(logs_dir, args.pattern)
    if not files:
        print(f"No log files found under {logs_dir}.")
        return 0

    _aggregate_logs(files, tail=args.tail, errors_only=args.errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
