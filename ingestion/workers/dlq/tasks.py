"""
Dead-letter queue handler tasks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ingestion.config import Settings
from ingestion.core.task_utils import shared_task

_LOG = logging.getLogger(__name__)
_settings = Settings()


@shared_task(bind=True, name="dlq.record_failure", queue="dlq")
def record_failure(self, payload: dict) -> str:
    dlq_dir = _settings.jobs_dir
    dlq_dir.mkdir(parents=True, exist_ok=True)
    dlq_file = dlq_dir / "dlq.jsonl"
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        **payload,
    }
    try:
        with dlq_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        _LOG.error("Failed to write DLQ entry: %s", exc)
    return payload.get("job_id", "")
