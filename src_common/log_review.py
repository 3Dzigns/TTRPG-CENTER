"""
Log Review & Automatic Bug Bundle Creation (FR-003)

Scans environment log files, detects significant errors, aggregates them
into candidate issues, and creates bug bundles with artifacts and metadata.

Designed to work with the AdminTestingService bug persistence layer.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .logging import get_logger, sanitize_for_logging
from enum import Enum


logger = get_logger(__name__)


CONSOLE_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*-\s*(?P<name>[^-]+?)\s*-\s*(?P<level>\w+)\s*-\s*(?P<msg>.*)$"
)


@dataclass
class LogEvent:
    timestamp: float
    level: str
    name: str
    message: str
    raw: str
    file: str


@dataclass
class BugCandidate:
    signature: str
    message: str
    component: str
    count: int
    first_seen: float
    last_seen: float
    files: List[str]
    severity: "BugSeverity"


def _parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single log line from either JSON or console format.

    Returns:
        dict with keys: timestamp(float), level(str), name(str), message(str)
        or None if not parseable
    """
    s = line.strip()
    if not s:
        return None

    # Try JSON first
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            # Normalize keys
            ts = obj.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = float(ts)
                except Exception:
                    ts = time.time()
            elif ts is None:
                ts = time.time()
            name = obj.get("name") or obj.get("logger") or obj.get("component") or "unknown"
            level = (obj.get("level") or obj.get("levelname") or obj.get("severity") or "INFO").upper()
            msg = str(obj.get("message") or obj.get("msg") or "")
            return {"timestamp": float(ts), "level": level, "name": str(name), "message": msg}
        except Exception:
            pass

    # Fallback to console text format
    m = CONSOLE_LOG_RE.match(s)
    if m:
        try:
            # Best-effort parse; use local time
            struct_time = time.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S")
            ts = time.mktime(struct_time)
        except Exception:
            ts = time.time()
        return {
            "timestamp": float(ts),
            "level": m.group("level").upper(),
            "name": m.group("name").strip(),
            "message": m.group("msg").strip(),
        }

    return None


def _event_signature(evt: LogEvent) -> str:
    """Compute a stable signature for grouping similar errors."""
    # Normalize digits and UUIDs to reduce noise
    msg = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", evt.message, flags=re.I)
    msg = re.sub(r"\bjob_\d+\b", "<job>", msg)
    msg = re.sub(r"\b\d+\b", "<n>", msg)
    # Component + normalized message + level
    return f"{evt.name}|{evt.level}|{msg[:160]}"


class BugSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _infer_severity(name: str, message: str, count: int) -> BugSeverity:
    m = message.lower()
    core = ["pass_d", "pass_e", "astra_loader", "auth", "security", "tls", "database", "ingest", "bulk_ingest"]
    if any(k in name.lower() for k in core) and ("failed" in m or "exception" in m or "error" in m):
        return BugSeverity.CRITICAL if count >= 3 else BugSeverity.HIGH
    if "timeout" in m or "traceback" in m:
        return BugSeverity.HIGH if count >= 2 else BugSeverity.MEDIUM
    return BugSeverity.MEDIUM if count >= 2 else BugSeverity.LOW


class LogReviewService:
    """Service to scan logs and create automatic bug bundles."""

    def __init__(self, base_dir: Optional[Path] = None):
        # Base working directory; defaults to cwd
        self.base_dir = Path(base_dir) if base_dir else Path(".")

    def _logs_dir(self, environment: str) -> Path:
        return self.base_dir / "env" / environment / "logs"

    def scan_logs(
        self,
        environment: str,
        since_ts: Optional[float] = None,
        levels: Iterable[str] = ("ERROR", "CRITICAL"),
        file_glob: str = "*.log",
        max_lines: int = 2_000_000,
    ) -> List[LogEvent]:
        """Scan log files and extract events at specified levels."""
        levels_up = {lvl.upper() for lvl in levels}
        events: List[LogEvent] = []
        logs_dir = self._logs_dir(environment)
        if not logs_dir.exists():
            logger.warning(f"Logs directory not found: {logs_dir}")
            return []

        for path in sorted(logs_dir.glob(file_glob)):
            try:
                line_count = 0
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_count += 1
                        if line_count > max_lines:
                            break
                        parsed = _parse_log_line(line)
                        if not parsed:
                            continue
                        if parsed["level"].upper() not in levels_up:
                            continue
                        ts = parsed["timestamp"]
                        if since_ts and ts < since_ts:
                            continue
                        evt = LogEvent(
                            timestamp=ts,
                            level=parsed["level"].upper(),
                            name=parsed["name"],
                            message=parsed["message"],
                            raw=line.rstrip("\n"),
                            file=str(path),
                        )
                        events.append(evt)
            except Exception as e:
                logger.warning(f"Failed to parse log file {path}: {e}")
        return events

    def aggregate_candidates(self, events: List[LogEvent]) -> List[BugCandidate]:
        groups: Dict[str, BugCandidate] = {}
        for evt in events:
            sig = _event_signature(evt)
            if sig not in groups:
                sev = _infer_severity(evt.name, evt.message, 1)
                groups[sig] = BugCandidate(
                    signature=sig,
                    message=evt.message[:300],
                    component=evt.name,
                    count=1,
                    first_seen=evt.timestamp,
                    last_seen=evt.timestamp,
                    files=[evt.file],
                    severity=sev,
                )
            else:
                g = groups[sig]
                g.count += 1
                g.last_seen = max(g.last_seen, evt.timestamp)
                if evt.file not in g.files:
                    g.files.append(evt.file)
                g.severity = _infer_severity(evt.name, evt.message, g.count)
        # Sort by severity and count
        ordered = sorted(
            groups.values(),
            key=lambda c: ("LHMCR".find(c.severity.name[0]), -c.count, -c.last_seen),
        )
        return ordered

    async def auto_create_bug_bundles(
        self,
        environment: str,
        hours: int = 24,
        max_bundles: int = 5,
        min_count_threshold: int = 1,
    ) -> Dict[str, Any]:
        """Scan recent logs and create bug bundles for top candidates.

        Returns summary with created bug IDs and counts.
        """
        since_ts = time.time() - (hours * 3600)
        events = self.scan_logs(environment, since_ts=since_ts)
        candidates = [c for c in self.aggregate_candidates(events) if c.count >= min_count_threshold]

        # De-dup against existing bugs by title signature (last 7 days)
        existing_titles = self._recent_auto_bug_titles(environment, days=7)

        created: List[str] = []
        examined = 0
        for cand in candidates:
            examined += 1
            if len(created) >= max_bundles:
                break

            title = self._auto_title(cand)
            if title in existing_titles:
                continue

            bug_id = self._create_bundle(environment, cand, title)
            created.append(bug_id)

        return {
            "environment": environment,
            "examined_candidates": examined,
            "created_bundles": created,
            "total_events": len(events),
        }

    def _bugs_file(self, environment: str) -> Path:
        f = self.base_dir / "env" / environment / "data" / "bug_bundles.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        return f

    def _load_bugs(self, environment: str) -> Dict[str, Any]:
        f = self._bugs_file(environment)
        if not f.exists():
            return {"environment": environment, "updated_at": time.time(), "bugs": []}
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {"environment": environment, "updated_at": time.time(), "bugs": []}

    def _save_bugs(self, environment: str, data: Dict[str, Any]) -> None:
        data["environment"] = environment
        data["updated_at"] = time.time()
        self._bugs_file(environment).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _recent_auto_bug_titles(self, environment: str, days: int = 7) -> set:
        data = self._load_bugs(environment)
        cutoff = time.time() - days * 86400
        titles = set()
        for b in data.get("bugs", []):
            if b.get("created_at", 0) >= cutoff and (b.get("title") or "").startswith("Auto: "):
                titles.add(b["title"])
        return titles

    def _auto_title(self, cand: BugCandidate) -> str:
        base = cand.message or "Error"
        # Trim noisy prefixes
        base = re.sub(r"^Pass [A-F]:?\s*", "", base, flags=re.I)
        if len(base) > 80:
            base = base[:77] + "..."
        return f"Auto: {cand.component} - {base}"

    def _create_bundle(self, environment: str, cand: BugCandidate, title: str) -> str:
        # Construct bug dict compatible with admin/testing storage
        bug_id = str(uuid.uuid4())
        bug = {
            "bug_id": bug_id,
            "title": title,
            "description": (
                f"Automatically generated from logs. Count={cand.count}, "
                f"FirstSeen={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cand.first_seen))}, "
                f"LastSeen={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cand.last_seen))}."
            ),
            "environment": environment,
            "severity": cand.severity.value,
            "status": "open",
            "created_at": time.time(),
            "created_by": "auto",
            "assigned_to": None,
            "resolved_at": None,
            "resolution": None,
            "steps_to_reproduce": [],
            "expected_behavior": None,
            "actual_behavior": None,
            "test_data": {
                "signature": cand.signature,
                "count": cand.count,
                "files": cand.files,
            },
            "attachments": [],
            "tags": ["auto", "fr-003", cand.component],
        }

        data = self._load_bugs(environment)
        data.setdefault("bugs", []).append(bug)
        self._save_bugs(environment, data)

        # Create bundle artifact directory
        bundle_dir = self.base_dir / "env" / environment / "artifacts" / "bug_bundles" / bug_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest
        cand_dict = asdict(cand)
        # Normalize enum for JSON
        cand_dict["severity"] = cand.severity.value
        manifest = {
            "bug_id": bug_id,
            "title": title,
            "environment": environment,
            "severity": cand.severity.value,
            "created_at": time.time(),
            "source": "log_review",
            "candidate": cand_dict,
        }
        with open(bundle_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Extract snippets per file
        snippets: Dict[str, List[str]] = {}
        for fpath in cand.files:
            try:
                lines: List[str] = []
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        parsed = _parse_log_line(line)
                        if not parsed:
                            continue
                        if parsed["level"].upper() not in ("ERROR", "CRITICAL"):
                            continue
                        # Only include lines matching signature component substring
                        if cand.component and cand.component not in (parsed.get("name") or ""):
                            continue
                        lines.append(line.rstrip("\n"))
                if lines:
                    snippets[os.path.basename(fpath)] = lines[:1000]  # cap for size
            except Exception as e:
                logger.warning(f"Failed collecting snippets from {fpath}: {e}")

        with open(bundle_dir / "error_snippets.json", "w", encoding="utf-8") as f:
            json.dump(snippets, f, indent=2)

        return bug_id


__all__ = [
    "LogReviewService",
    "LogEvent",
    "BugCandidate",
]
