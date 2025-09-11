"""
FR-002: Nightly Bulk Ingestion Scheduler

Provides a lightweight cron parser and a simple in-process scheduling engine
for defining scheduled jobs and persisting scheduler state. This is a minimal
implementation to support tests and integration with the bulk ingestion
pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ScheduledJob:
    id: str
    name: str
    cron_expression: str
    job_type: str
    priority: int = 1
    created_at: str = ""


class CronParser:
    """Very small cron helper supporting patterns used in tests.

    Supported examples:
    - "0 2 * * *"      -> daily 02:00
    - "0 14 * * *"     -> daily 14:00
    - "0 * * * *"      -> hourly at :00
    - "*/15 * * * *"   -> every 15 minutes
    - "0 3 * * 0"      -> Sundays 03:00
    - "0 2 * * 1"      -> Mondays 02:00
    """

    def __init__(self, cron_expression: str) -> None:
        self.expr = cron_expression.strip()

    def get_next_execution_time(self, from_time: Optional[datetime] = None) -> datetime:
        now = from_time or datetime.now()
        m, h, dom, mon, dow = self._parts()

        # Every N minutes (*/15)
        if m.startswith("*/"):
            step = int(m.split("/")[1])
            minute = ((now.minute // step) + 1) * step
            carry = 0
            if minute >= 60:
                minute = 0
                carry = 1
            next_time = now.replace(second=0, microsecond=0) + timedelta(hours=carry)
            next_time = next_time.replace(minute=minute)
            return next_time

        # Hourly at minute m (0 * * * *)
        if h == "*" and m.isdigit():
            minute = int(m)
            next_time = now.replace(second=0, microsecond=0)
            if now.minute >= minute:
                next_time = next_time + timedelta(hours=1)
            next_time = next_time.replace(minute=minute)
            return next_time

        # Specific day-of-week (0 3 * * 0) -> Sunday 03:00
        if dow != "*" and m.isdigit() and h.isdigit():
            minute = int(m)
            hour = int(h)
            target_wd = int(dow) % 7  # Python Monday=0, crontab Sunday=0
            # Map Python weekday() Mon=0..Sun=6 to cron Sun=0..Sat=6
            # We'll compute days ahead until target weekday at or after now time
            days_ahead = (target_wd - (now.weekday() + 1) % 7) % 7
            candidate = (now + timedelta(days=days_ahead)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if candidate <= now:
                candidate += timedelta(days=7)
            return candidate

        # Daily at hour:minute (0 2 * * *)
        if m.isdigit() and h.isdigit():
            minute = int(m)
            hour = int(h)
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        # Fallback: one minute later rounded to minute
        return (now.replace(second=0, microsecond=0) + timedelta(minutes=1))

    def should_trigger(self, current_time: Optional[datetime] = None) -> bool:
        now = current_time or datetime.now()
        m, h, dom, mon, dow = self._parts()

        if m.startswith("*/"):
            step = int(m.split("/")[1])
            return now.minute % step == 0 and now.second == 0

        if h == "*" and m.isdigit():
            return now.minute == int(m) and now.second == 0

        if dow != "*" and m.isdigit() and h.isdigit():
            target_wd = int(dow) % 7
            # Python weekday Mon=0..Sun=6; convert now to cron-like Sun=0
            now_cron_wd = (now.weekday() + 1) % 7
            return (
                now_cron_wd == target_wd and now.hour == int(h) and now.minute == int(m) and now.second == 0
            )

        if m.isdigit() and h.isdigit():
            return now.hour == int(h) and now.minute == int(m) and now.second == 0

        return False

    def _parts(self):
        parts = self.expr.split()
        while len(parts) < 5:
            parts.append("*")
        return parts[:5]


class SchedulingEngine:
    """Lightweight in-memory scheduler registry with state persistence."""

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = config or {}
        self._jobs: Dict[str, ScheduledJob] = {}
        self._counter = 0

    def schedule_job(self, name: str, cron_schedule: str, job_type: str, priority: int = 1) -> str:
        self._counter += 1
        job_id = f"schedule_{self._counter:06d}"
        job = ScheduledJob(
            id=job_id,
            name=name,
            cron_expression=cron_schedule,
            job_type=job_type,
            priority=priority,
            created_at=datetime.now().isoformat(),
        )
        self._jobs[job_id] = job
        return job_id

    def get_scheduled_jobs(self) -> List[Dict]:
        return [asdict(j) for j in self._jobs.values()]

    def save_state(self, path: Path) -> None:
        state = {
            "jobs": [asdict(j) for j in self._jobs.values()],
            "counter": self._counter,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_state(self, path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self._jobs.clear()
        for jd in data.get("jobs", []):
            self._jobs[jd["id"]] = ScheduledJob(**jd)
        self._counter = int(data.get("counter", len(self._jobs)))

