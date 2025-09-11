"""
FR-001: Admin Deletion Queue

Simple JSON-backed deletion queue for missing/stale sources requiring
administrator approval before execution. Stores records with lifecycle
states: PENDING, APPROVED, REJECTED, EXECUTED.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DeletionRequest:
    request_id: str
    source_id: str
    reason: str
    environment: str
    state: str = "PENDING"
    created_at: float = 0.0
    decided_at: Optional[float] = None
    decided_by: Optional[str] = None
    details: Dict[str, Any] = None


class DeletionQueue:
    def __init__(self, base_dir: Path, environment: str) -> None:
        self.base_dir = Path(base_dir)
        self.env = environment
        self.file = self.base_dir / "env" / self.env / "data" / "deletions.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)

    def list_items(self) -> List[Dict[str, Any]]:
        data = self._load()
        return data.get("items", [])

    def enqueue(self, source_id: str, reason: str, details: Optional[Dict[str, Any]] = None) -> str:
        data = self._load()
        req = DeletionRequest(
            request_id=str(uuid.uuid4()),
            source_id=source_id,
            reason=reason,
            environment=self.env,
            state="PENDING",
            created_at=time.time(),
            details=details or {},
        )
        data.setdefault("items", []).append(asdict(req))
        self._save(data)
        return req.request_id

    def approve(self, request_id: str, admin: str) -> bool:
        return self._set_state(request_id, "APPROVED", admin)

    def reject(self, request_id: str, admin: str) -> bool:
        return self._set_state(request_id, "REJECTED", admin)

    def execute(self, request_id: str, executor: str) -> Dict[str, Any]:
        # This method would perform the actual deletion of stale data.
        # Here we only mark as EXECUTED to integrate minimally.
        changed = self._set_state(request_id, "EXECUTED", executor)
        return {"request_id": request_id, "executed": changed}

    def _set_state(self, request_id: str, new_state: str, user: str) -> bool:
        data = self._load()
        updated = False
        for item in data.get("items", []):
            if item.get("request_id") == request_id:
                item["state"] = new_state
                item["decided_at"] = time.time()
                item["decided_by"] = user
                updated = True
                break
        if updated:
            self._save(data)
        return updated

    def _load(self) -> Dict[str, Any]:
        if not self.file.exists():
            return {"items": []}
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return {"items": []}

    def _save(self, data: Dict[str, Any]) -> None:
        self.file.write_text(json.dumps(data, indent=2), encoding="utf-8")

