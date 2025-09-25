"""Prompt registry loader with hot-reload support."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src_common.logging import get_logger

logger = get_logger(__name__)


class PromptRegistryError(RuntimeError):
    """Raised when prompt assets cannot be loaded."""


class PromptRegistry:
    """Managed registry for orchestrator prompt templates."""

    def __init__(
        self,
        environment: str,
        *,
        hot_reload: bool = False,
        base_config_path: Path = Path("config/prompts"),
        registry_path: Path = Path("MVP-Version-2/Prompt-Registry/templates"),
    ) -> None:
        self.environment = environment
        self.hot_reload = hot_reload
        self.base_config_path = base_config_path
        self.registry_path = registry_path
        self._lock = threading.RLock()
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._registry_index: Dict[str, Dict[str, Any]] = {}
        self._fingerprint = "unknown"
        self._mtimes: Dict[Path, float] = {}
        self._last_loaded = datetime.utcnow()
        self._load()

    # ------------------------------------------------------------------
    # Public API

    @property
    def version(self) -> str:
        return self._fingerprint

    @property
    def last_loaded(self) -> datetime:
        return self._last_loaded

    def get_prompt(self, key: str, *, default: Optional[str] = None) -> Optional[str]:
        """Return a prompt template by key."""
        self._maybe_reload()
        template = self._templates.get(key) or {}
        content = template.get("template") or template.get("content")
        if content is None:
            return default
        return str(content)

    def get_prompt_bundle(self, key: str) -> Dict[str, Any]:
        """Return structured prompt bundle (system + user templates)."""
        self._maybe_reload()
        return self._templates.get(key, {}).copy()

    def get_registry_metadata(self, prompt_id: str) -> Dict[str, Any]:
        self._maybe_reload()
        return self._registry_index.get(prompt_id, {}).copy()

    # ------------------------------------------------------------------
    # Internal helpers

    def _load(self) -> None:
        with self._lock:
            logger.info("Loading prompt registry assets", extra={"env": self.environment})
            payload: Dict[str, Dict[str, Any]] = {}
            registry_index: Dict[str, Dict[str, Any]] = {}
            canonical_paths = list(self._iter_candidate_files())
            for path in canonical_paths:
                try:
                    if path.suffix in {".yaml", ".yml"}:
                        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    elif path.suffix in {".json"}:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        data = {"template": path.read_text(encoding="utf-8")}
                except Exception as exc:  # pragma: no cover - corrupted file guard
                    logger.warning("Failed to load prompt asset", extra={"path": str(path), "error": str(exc)})
                    continue

                key = self._infer_key(path, data)
                payload[key] = self._normalise_payload(data)
                if "id" in data:
                    registry_index[str(data["id"])] = {
                        "path": str(path),
                        "hash": self._hash_text(path.read_text(encoding="utf-8")),
                    }

                self._mtimes[path] = path.stat().st_mtime

            self._templates = payload
            self._registry_index = registry_index
            self._fingerprint = self._calculate_fingerprint(payload, registry_index)
            self._last_loaded = datetime.utcnow()
            logger.info("Prompt registry loaded", extra={"version": self._fingerprint, "count": len(self._templates)})

    def _maybe_reload(self) -> None:
        if not self.hot_reload:
            return
        with self._lock:
            if not any(self._has_changed(path) for path in self._mtimes.keys()):
                # also detect new files
                canonical = set(self._mtimes.keys())
                for path in self._iter_candidate_files():
                    if path not in canonical:
                        self._load()
                        return
                return
        # If we reach here a file changed
        self._load()

    def _has_changed(self, path: Path) -> bool:
        try:
            current = path.stat().st_mtime
        except FileNotFoundError:
            return True
        previous = self._mtimes.get(path)
        return previous is None or current > previous

    def _iter_candidate_files(self):
        env_override = Path(f"env/{self.environment}/config/prompts")
        paths = []
        if env_override.exists():
            paths.extend(sorted(env_override.rglob("*")))
        if self.base_config_path.exists():
            paths.extend(sorted(self.base_config_path.rglob("*")))
        if self.registry_path.exists():
            paths.extend(sorted(self.registry_path.rglob("*.yaml")))
        return [p for p in paths if p.is_file()]

    def _infer_key(self, path: Path, data: Dict[str, Any]) -> str:
        if "id" in data:
            return str(data["id"])
        stem = path.stem
        if path.parent.name != self.base_config_path.name:
            stem = f"{path.parent.name}.{stem}" if path.parent.name else stem
        return stem.replace("-", "_")

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _calculate_fingerprint(self, payload: Dict[str, Dict[str, Any]], registry_index: Dict[str, Dict[str, Any]]) -> str:
        digest = hashlib.sha1()
        for key in sorted(payload):
            digest.update(key.encode("utf-8"))
            digest.update(json.dumps(payload[key], sort_keys=True, default=str).encode("utf-8"))
        for key in sorted(registry_index):
            digest.update(key.encode("utf-8"))
            digest.update(registry_index[key]["hash"].encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _normalise_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        if "template" in data or "content" in data:
            return data
        if {"system_prompt", "user_template"}.issubset(data.keys()):
            return {
                "systemPrompt": data["system_prompt"],
                "userTemplate": data["user_template"],
                "template": "{systemPrompt}\n\n{userTemplate}",
            }
        return data
