"""Admin Deletion Queue Service - FR-001 support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .deletion_queue import DeletionQueue
from ..ttrpg_logging import get_logger


logger = get_logger(__name__)


class AdminDeletionService:
    """Expose deletion queue operations for admin workflows."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()
        self._queues: Dict[str, DeletionQueue] = {}

    def _get_queue(self, environment: str) -> DeletionQueue:
        env = (environment or "dev").lower()
        if env not in self._queues:
            self._queues[env] = DeletionQueue(self._base_dir, env)
            logger.debug(f"Initialized deletion queue for environment {env}")
        return self._queues[env]

    def list_items(self, environment: str) -> List[Dict[str, Any]]:
        queue = self._get_queue(environment)
        items = queue.list_items()
        logger.debug(f"Retrieved {len(items)} deletion queue items for {environment}")
        return items

    def enqueue(self, environment: str, source_id: str, reason: str, details: Optional[Dict[str, Any]] = None) -> str:
        queue = self._get_queue(environment)
        request_id = queue.enqueue(source_id, reason, details)
        logger.info(
            "Deletion request enqueued",
            extra={"environment": environment, "source_id": source_id, "request_id": request_id},
        )
        return request_id

    def approve(self, environment: str, request_id: str, admin_user: str) -> bool:
        queue = self._get_queue(environment)
        updated = queue.approve(request_id, admin_user)
        logger.info(
            "Deletion request approval",
            extra={"environment": environment, "request_id": request_id, "approved": updated},
        )
        return updated

    def reject(self, environment: str, request_id: str, admin_user: str) -> bool:
        queue = self._get_queue(environment)
        updated = queue.reject(request_id, admin_user)
        logger.info(
            "Deletion request rejection",
            extra={"environment": environment, "request_id": request_id, "rejected": updated},
        )
        return updated

    def execute(self, environment: str, request_id: str, executor: str) -> Dict[str, Any]:
        queue = self._get_queue(environment)
        result = queue.execute(request_id, executor)
        logger.info(
            "Deletion request execution",
            extra={"environment": environment, "request_id": request_id, "executed": result.get("executed")},
        )
        return result
