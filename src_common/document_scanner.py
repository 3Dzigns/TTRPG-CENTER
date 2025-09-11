"""
FR-002: Document Scanner

Watches upload directories for new documents matching supported extensions
and exposes discovered document metadata. Minimal implementation using a
background polling task suitable for tests.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class DocumentScanner:
    def __init__(
        self,
        scan_directories: Iterable[str],
        supported_extensions: Iterable[str] = (".pdf",),
        scan_interval_seconds: float = 10.0,
    ) -> None:
        self.scan_dirs = [Path(p) for p in scan_directories]
        self.exts = {e.lower() for e in supported_extensions}
        self.interval = scan_interval_seconds
        self._found: Dict[str, float] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start_monitoring(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_monitoring(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.interval * 2)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._scan_once()
            # Sleep in small chunks to exit promptly
            wait = 0.0
            while wait < self.interval and not self._stop.is_set():
                time.sleep(0.1)
                wait += 0.1

    def _scan_once(self) -> None:
        now = time.time()
        for d in self.scan_dirs:
            if not d.exists():
                continue
            for p in d.glob("**/*"):
                if p.is_file() and p.suffix.lower() in self.exts:
                    key = str(p.resolve())
                    if key not in self._found:
                        self._found[key] = now

    def get_discovered_documents(self) -> List[Dict[str, any]]:
        return [
            {"path": path, "discovered_at": ts}
            for path, ts in sorted(self._found.items(), key=lambda kv: kv[1])
        ]

