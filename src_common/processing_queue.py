"""
FR-002: Processing Queue

Lightweight, persistent document processing queue with duplicate detection
and priority ordering.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class QueueItem:
    job_id: str
    path: str
    priority: int = 1
    metadata: Dict[str, Any] = None
    created_at: float = 0.0


class ProcessingQueue:
    def __init__(self, state_file: Path, max_size: int = 1000) -> None:
        self.state_file = Path(state_file)
        self.max_size = max_size
        self._items: List[QueueItem] = []
        self._by_path: Dict[str, QueueItem] = {}
        self._counter = 0
        self._load()

    def add_document(self, path: str, priority: int = 1, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Duplicate detection by path
        if path in self._by_path:
            return {"status": "duplicate", "existing_job_id": self._by_path[path].job_id}

        if len(self._items) >= self.max_size:
            return {"status": "rejected", "reason": "capacity"}

        self._counter += 1
        job_id = f"queue_{self._counter:06d}"
        qi = QueueItem(
            job_id=job_id,
            path=path,
            priority=int(priority),
            metadata=metadata or {},
            created_at=time.time(),
        )
        self._items.append(qi)
        self._by_path[path] = qi
        self._sort()
        self._save()
        return {"status": "added", "job_id": job_id}

    def peek_queue(self) -> List[Dict[str, Any]]:
        """View all items in queue without removing them"""
        return [
            {
                "job_id": item.job_id,
                "path": item.path,
                "priority": item.priority,
                "created_at": item.created_at,
                "metadata": item.metadata
            }
            for item in self._items
        ]

    def get_next_document(self) -> Optional[Dict[str, Any]]:
        if not self._items:
            return None
        qi = self._items.pop(0)
        self._by_path.pop(qi.path, None)
        self._save()
        return {"path": qi.path, "priority": qi.priority, "metadata": qi.metadata}

    def get_status(self) -> Dict[str, Any]:
        return {"total_documents": len(self._items), "capacity": self.max_size}

    def clear_queue(self) -> Dict[str, Any]:
        """Clear all items from the queue and reset state"""
        cleared_count = len(self._items)
        self._items = []
        self._by_path = {}
        self._save()
        return {"status": "cleared", "cleared_count": cleared_count}

    def remove_failed_documents(self, failed_paths: List[str]) -> Dict[str, Any]:
        """Remove specific failed documents from queue"""
        removed_count = 0
        original_items = self._items.copy()
        
        self._items = [item for item in self._items if item.path not in failed_paths]
        removed_count = len(original_items) - len(self._items)
        
        # Rebuild by_path index
        self._by_path = {item.path: item for item in self._items}
        self._save()
        
        return {"status": "removed", "removed_count": removed_count, "remaining_count": len(self._items)}

    def _sort(self) -> None:
        self._items.sort(key=lambda x: (x.priority, x.created_at))

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "counter": self._counter,
            "items": [asdict(i) for i in self._items],
        }
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self._counter = int(data.get("counter", 0))
            self._items = [QueueItem(**i) for i in data.get("items", [])]
            self._by_path = {i.path: i for i in self._items}
            self._sort()
        except Exception:
            # Start empty if corrupted
            self._items = []
            self._by_path = {}
            self._counter = 0

