"""Admin Health Service - FR-004 daily health reporting."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ttrpg_logging import get_logger


logger = get_logger(__name__)


class AdminHealthService:
    """Generate and expose health reports plus recommended corrective actions."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.root = Path(base_dir) if base_dir else Path("artifacts") / "health"
        self.root.mkdir(parents=True, exist_ok=True)

    def _report_dir(self, environment: str, date_slug: str) -> Path:
        return self.root / environment / date_slug

    def _today_slug(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def generate_daily_report(self, environment: str, force: bool = False) -> Dict[str, Any]:
        env = (environment or "dev").lower()
        date_slug = self._today_slug()
        report_dir = self._report_dir(env, date_slug)
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / "report.json"
        actions_path = report_dir / "actions.json"

        if report_path.exists() and not force:
            logger.info("Health report already exists", extra={"environment": env, "date": date_slug})
            return {
                "environment": env,
                "date": date_slug,
                "report": json.loads(report_path.read_text(encoding="utf-8")),
                "actions": json.loads(actions_path.read_text(encoding="utf-8")) if actions_path.exists() else [],
                "generated": False,
            }

        metrics = self._collect_metrics(env)
        actions = self._derive_actions(env, metrics)
        generated_at = datetime.now(timezone.utc).isoformat()

        report_data = {
            "environment": env,
            "generated_at": generated_at,
            "metrics": metrics,
        }
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        actions_path.write_text(json.dumps(actions, indent=2), encoding="utf-8")

        logger.info(
            "Health report generated",
            extra={"environment": env, "date": date_slug, "metrics": metrics},
        )

        return {
            "environment": env,
            "date": date_slug,
            "report": report_data,
            "actions": actions,
            "generated": True,
        }

    def list_reports(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        environments = [environment.lower()] if environment else [p.name for p in self.root.iterdir() if p.is_dir()]
        reports: List[Dict[str, Any]] = []
        for env in sorted(environments):
            env_dir = self.root / env
            if not env_dir.exists():
                continue
            for date_dir in sorted(env_dir.iterdir(), reverse=True):
                report_path = date_dir / "report.json"
                if report_path.exists():
                    try:
                        data = json.loads(report_path.read_text(encoding="utf-8"))
                        reports.append(data)
                    except Exception as exc:
                        logger.warning(f"Failed to load health report {report_path}: {exc}")
        return reports

    def get_actions(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        environments = [environment.lower()] if environment else [p.name for p in self.root.iterdir() if p.is_dir()]
        actions: List[Dict[str, Any]] = []
        for env in sorted(environments):
            env_dir = self.root / env
            if not env_dir.exists():
                continue
            for date_dir in sorted(env_dir.iterdir(), reverse=True):
                actions_path = date_dir / "actions.json"
                if actions_path.exists():
                    try:
                        items = json.loads(actions_path.read_text(encoding="utf-8"))
                        for item in items:
                            item.setdefault("environment", env)
                            actions.append(item)
                    except Exception as exc:
                        logger.warning(f"Failed to load health actions {actions_path}: {exc}")
        return actions

    def _collect_metrics(self, environment: str) -> Dict[str, Any]:
        ingest_dir = Path("artifacts") / "ingest" / environment
        total_sources = 0
        total_chunks = 0
        failed_jobs = 0
        latest_jobs: List[Dict[str, Any]] = []

        if ingest_dir.exists():
            for manifest_path in ingest_dir.rglob("manifest.json"):
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning(f"Invalid manifest {manifest_path}: {exc}")
                    continue
                total_sources += 1
                checksums = manifest.get("checksums", {})
                total_chunks += len(checksums)
                passes = manifest.get("passes_completed", [])
                if "Pass F" not in passes and "PASS_F" not in passes:
                    failed_jobs += 1
                latest_jobs.append(
                    {
                        "source_file": manifest.get("source_file"),
                        "passes_completed": passes,
                        "updated_at": manifest.get("last_updated"),
                    }
                )

        average_chunks = (total_chunks / total_sources) if total_sources else 0
        return {
            "total_sources": total_sources,
            "total_chunks": total_chunks,
            "average_chunks_per_source": round(average_chunks, 2),
            "failed_jobs": failed_jobs,
            "snapshot_taken_at": time.time(),
            "recent_jobs": latest_jobs[:10],
        }

    def _derive_actions(self, environment: str, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        if metrics.get("total_sources", 0) == 0:
            actions.append(
                {
                    "action_id": f"act-{uuid.uuid4().hex[:8]}",
                    "environment": environment,
                    "type": "ingest_run",
                    "title": "No sources ingested",
                    "details": "No ingestion manifests found. Schedule a fresh ingestion run to populate the environment.",
                    "created_at": now,
                    "severity": "critical",
                }
            )

        if metrics.get("failed_jobs", 0):
            actions.append(
                {
                    "action_id": f"act-{uuid.uuid4().hex[:8]}",
                    "environment": environment,
                    "type": "reconcile",
                    "title": "Incomplete ingestion passes detected",
                    "details": "One or more manifests are missing Pass F completion. Re-run reconciliation to ensure data integrity.",
                    "created_at": now,
                    "severity": "high",
                }
            )

        if metrics.get("average_chunks_per_source", 0) < 5 and metrics.get("total_sources", 0) > 0:
            actions.append(
                {
                    "action_id": f"act-{uuid.uuid4().hex[:8]}",
                    "environment": environment,
                    "type": "quality_review",
                    "title": "Low chunk density",
                    "details": "Average chunk output per source is below threshold. Review Pass C parameters or source quality.",
                    "created_at": now,
                    "severity": "medium",
                }
            )

        return actions
