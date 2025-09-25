"""Policy loading and hot-reload management for the orchestrator."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from src_common.logging import get_logger
from src_common.orchestrator.policies import choose_plan, load_policies as load_default_policies

logger = get_logger(__name__)


class PolicyManager:
    """Runtime loader for orchestrator retrieval and workflow policies."""

    def __init__(
        self,
        environment: str,
        *,
        hot_reload: bool = False,
        config_root: Path = Path("config"),
    ) -> None:
        self.environment = environment
        self.hot_reload = hot_reload
        self.config_root = config_root
        self._lock = threading.RLock()
        self._retrieval_policies: Dict[str, Any] = {}
        self._policy_settings: Dict[str, Any] = {}
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

    def get_policy_settings(self) -> Dict[str, Any]:
        self._maybe_reload()
        return self._policy_settings.copy()

    def resolve_plan(self, classification: Mapping[str, Any]) -> Dict[str, Any]:
        """Return retrieval plan for a classification."""
        self._maybe_reload()
        if not self._retrieval_policies:
            policies = load_default_policies()
        else:
            policies = self._retrieval_policies
        return choose_plan(policies, dict(classification))

    # ------------------------------------------------------------------
    # Loading & reload helpers

    def _load(self) -> None:
        with self._lock:
            logger.info("Loading orchestrator policies", extra={"env": self.environment})
            retrieval = self._load_yaml_preferences("retrieval_policies.yaml") or load_default_policies()
            policy_settings = self._load_yaml_preferences("policies.yaml") or {}
            self._retrieval_policies = retrieval
            self._policy_settings = policy_settings
            self._fingerprint = self._calculate_fingerprint(retrieval, policy_settings)
            self._last_loaded = datetime.utcnow()
            logger.info("Policies loaded", extra={"version": self._fingerprint})

    def _maybe_reload(self) -> None:
        if not self.hot_reload:
            return
        with self._lock:
            paths = self._candidate_paths()
            dirty = False
            for path in paths:
                try:
                    mtime = path.stat().st_mtime
                except FileNotFoundError:
                    if path in self._mtimes:
                        dirty = True
                        break
                    continue
                previous = self._mtimes.get(path)
                if previous is None or mtime > previous:
                    dirty = True
                    break
            if not dirty:
                return
        self._load()

    def _candidate_paths(self) -> Dict[str, Path]:
        env_root = Path(f"env/{self.environment}/config")
        files = {}
        for name in ("retrieval_policies.yaml", "policies.yaml"):
            if env_root.exists():
                files[name] = env_root / name
            files.setdefault(name, self.config_root / name)
        return files

    def _load_yaml_preferences(self, filename: str) -> Dict[str, Any]:
        candidates = []
        env_specific = Path(f"env/{self.environment}/config/{filename}")
        if env_specific.exists():
            candidates.append(env_specific)
        candidates.append(self.config_root / filename)
        for path in candidates:
            if not path.exists():
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                self._mtimes[path] = path.stat().st_mtime
                return data
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("Failed to load policy file", extra={"path": str(path), "error": str(exc)})
        return {}

    @staticmethod
    def _calculate_fingerprint(policies: Dict[str, Any], settings: Dict[str, Any]) -> str:
        digest = hashlib.sha1()
        digest.update(json.dumps(policies, sort_keys=True, default=str).encode("utf-8"))
        digest.update(json.dumps(settings, sort_keys=True, default=str).encode("utf-8"))
        return digest.hexdigest()

