from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Optional, Sequence, List


class VectorStore(ABC):
    """Abstract base for vector store backends."""

    def __init__(self, env: str) -> None:
        self.env = env

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return backend identifier (e.g. 'astra', 'cassandra')."""

    def ensure_schema(self) -> None:
        """Create required keyspaces/tables if the backend needs it."""
        # Optional for backends that do not manage schema
        return None

    @abstractmethod
    def insert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        """Insert documents that are expected to be new (no overwrite)."""

    @abstractmethod
    def upsert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        """Insert or replace documents keyed by their chunk identifiers."""

    @abstractmethod
    def delete_all(self) -> int:
        """Delete all documents in the active environment collection."""

    @abstractmethod
    def delete_by_source_hash(self, source_hash: str) -> int:
        """Delete all documents that match the provided source hash."""

    @abstractmethod
    def count_documents(self) -> int:
        """Return number of stored documents for the active environment."""

    @abstractmethod
    def count_documents_for_source(self, source_hash: str) -> int:
        """Return number of documents stored for a specific source hash."""

    @abstractmethod
    def get_sources_with_chunk_counts(self) -> Dict[str, Any]:
        """Return metadata about sources and their chunk counts."""

    @abstractmethod
    def query(self,
              vector: Optional[Sequence[float]],
              top_k: int = 5,
              filters: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a similarity query (optional filters) and return documents."""

    def close(self) -> None:
        """Release backend resources."""
        return None
