from __future__ import annotations

import os
from typing import Dict, Tuple, Type

from .base import VectorStore
from .astra import AstraVectorStore
from .cassandra import CassandraVectorStore

_BACKENDS: Dict[str, Type[VectorStore]] = {
    "astra": AstraVectorStore,
    "astra_vector": AstraVectorStore,  # legacy alias
    "cassandra": CassandraVectorStore,
}

_CACHE: Dict[Tuple[str, str], VectorStore] = {}


def make_vector_store(env: str, *, backend: str | None = None, fresh: bool = False) -> VectorStore:
    """Return a vector store instance for the requested environment.

    Args:
        env: Logical environment name (e.g. ``dev``).
        backend: Optional explicit backend override. Falls back to ``VECTOR_STORE_BACKEND``
            environment variable and defaults to ``astra`` if unset.
        fresh: When ``True`` the cached instance will be replaced with a new one.
    """
    choice = backend or os.getenv("VECTOR_STORE_BACKEND", "astra").strip().lower() or "astra"
    if choice not in _BACKENDS:
        raise ValueError(f"Unsupported vector store backend: {choice}")

    cache_key = (choice, env)
    if fresh or cache_key not in _CACHE:
        store_cls = _BACKENDS[choice]
        store = store_cls(env)
        try:
            store.ensure_schema()
        except Exception:
            # Schema initialization is best-effort; the caller can retry explicitly
            pass
        _CACHE[cache_key] = store

    return _CACHE[cache_key]

