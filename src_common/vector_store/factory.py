from __future__ import annotations

import importlib
import os
from typing import Dict, Tuple, Type

from .base import VectorStore

_BACKEND_PATHS: Dict[str, str] = {
    "astra": "src_common.vector_store.astra:AstraVectorStore",
    "astra_vector": "src_common.vector_store.astra:AstraVectorStore",
    "cassandra": "src_common.vector_store.cassandra:CassandraVectorStore",
    "memory": "src_common.vector_store.memory:MemoryVectorStore",
}

_BACKEND_CACHE: Dict[str, Type[VectorStore]] = {}
_CACHE: Dict[Tuple[str, str], VectorStore] = {}


def make_vector_store(env: str, *, backend: str | None = None, fresh: bool = False) -> VectorStore:
    """Return a vector store instance for the requested environment."""
    choice = _resolve_backend_choice(env, backend)

    cache_key = (choice, env)
    if fresh or cache_key not in _CACHE:
        store_cls = _load_backend_class(choice)
        store = store_cls(env)
        try:
            store.ensure_schema()
        except Exception:
            # Schema initialization is best-effort; the caller can retry explicitly
            pass
        _CACHE[cache_key] = store

    return _CACHE[cache_key]


def _resolve_backend_choice(env: str, backend_override: str | None) -> str:
    candidate = backend_override or os.getenv("VECTOR_STORE_BACKEND") or os.getenv("VECTOR_BACKEND") or ""
    candidate = candidate.strip().lower()
    if not candidate:
        candidate = _default_backend_for_env(env)
    elif candidate in {"inmemory", "mock", "test"}:
        candidate = "memory"

    if candidate not in _BACKEND_PATHS:
        raise ValueError(f"Unsupported vector store backend: {candidate}")
    return candidate


def _default_backend_for_env(env: str) -> str:
    env_name = (env or "").strip().lower()
    if _running_under_pytest() or env_name in {"test", "ci"}:
        return "memory"
    return "astra"


def _running_under_pytest() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _load_backend_class(name: str) -> Type[VectorStore]:
    if name in _BACKEND_CACHE:
        return _BACKEND_CACHE[name]
    target = _BACKEND_PATHS[name]
    module_name, class_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    backend_cls = getattr(module, class_name)
    if not issubclass(backend_cls, VectorStore):
        raise TypeError(f"Backend {class_name} does not implement VectorStore")
    _BACKEND_CACHE[name] = backend_cls
    return backend_cls


__all__ = ["make_vector_store"]
