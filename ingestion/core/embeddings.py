"""
Embedding provider abstraction used by Haystack workers.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, Sequence

from ingestion.config import Settings
from ingestion.core.tracing import start_span

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover - the provider will guard against usage
    OpenAI = None  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, texts: Sequence[str], job_id: Optional[str] = None) -> List[List[float]]:
        ...


class TransientEmbeddingError(RuntimeError):
    """Raised to simulate transient provider failures (e.g., HTTP 429)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _MockEmbeddingProvider:
    """Deterministic embedding generator used for tests/offline runs."""

    def __init__(self, *, dimension: int) -> None:
        self._dimension = dimension
        self._chaos_failures_remaining = int(os.getenv("CHAOS_EMBEDDING_FAILURES", "0") or 0)
        status_code = os.getenv("CHAOS_EMBEDDING_FAILURE_STATUS", "429")
        try:
            self._chaos_failure_status = int(status_code)
        except ValueError:
            self._chaos_failure_status = 429
        self._chaos_log_path = os.getenv("CHAOS_EMBEDDING_LOG")

    def _log_attempt(self, outcome: str) -> None:
        if not self._chaos_log_path:
            return
        try:
            with open(self._chaos_log_path, "a", encoding="utf-8") as handle:
                handle.write(f"{outcome}\n")
        except Exception:  # pragma: no cover - best effort logging
            pass

    def embed(self, texts: Sequence[str], job_id: Optional[str] = None) -> List[List[float]]:
        with start_span(
            "embedding.mock",
            attributes={
                "job_id": job_id or "",
                "model": "mock",
                "batch_size": len(texts),
            },
        ) as span:
            if self._chaos_failures_remaining > 0:
                self._chaos_failures_remaining -= 1
                self._log_attempt("failure")
                raise TransientEmbeddingError(
                    "Simulated OpenAI 429 for chaos testing",
                    status_code=self._chaos_failure_status,
                )
            vectors: List[List[float]] = []
            for text in texts:
                seed = hashlib.sha256(text.encode("utf-8")).hexdigest()
                rng = random.Random(int(seed[:16], 16))
                vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dimension)]
                norm = math.sqrt(sum(val * val for val in vector)) or 1.0
                vectors.append([val / norm for val in vector])
            span.set_attribute("vector_count", len(vectors))
            if texts:
                self._log_attempt("success")
            return vectors


@dataclass(slots=True)
class _OpenAIEmbeddingProvider:
    """OpenAI backed embedding provider."""

    model: str
    dimension: int
    client: OpenAI
    batch_size: int = 64

    def embed(self, texts: Sequence[str], job_id: Optional[str] = None) -> List[List[float]]:
        if not texts:
            return []

        vectors: List[List[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            with start_span(
                "embedding.openai_call",
                attributes={
                    "job_id": job_id or "",
                    "model": self.model,
                    "batch_size": len(batch),
                    "batch_index": start // self.batch_size,
                },
            ) as span:
                response = self.client.embeddings.create(model=self.model, input=batch)
            for item in response.data:
                vector = list(item.embedding)
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}"
                    )
                vectors.append(vector)
            try:  # pragma: no cover - optional usage metadata
                tokens = getattr(response, "usage", None)
                if tokens is not None:
                    span.set_attribute("total_tokens", getattr(tokens, "total_tokens", 0))
            except Exception:
                pass
            span.set_attribute("vectors_returned", len(response.data))
        return vectors


def _build_openai_provider(settings: Settings) -> EmbeddingProvider:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed; run `pip install openai`.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set; cannot call OpenAI embeddings API.")

    client = OpenAI(api_key=api_key)
    return _OpenAIEmbeddingProvider(
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        client=client,
        batch_size=settings.embedding_batch_size,
    )


_PROVIDER_CACHE: EmbeddingProvider | None = None
_PROVIDER_KIND: str | None = None


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """
    Return a cached embedding provider instance based on configuration.
    """

    global _PROVIDER_CACHE, _PROVIDER_KIND

    provider_name = settings.embedding_provider.lower()
    if (
        _PROVIDER_CACHE is not None
        and _PROVIDER_KIND == provider_name
        and isinstance(_PROVIDER_CACHE, _MockEmbeddingProvider)
    ):
        return _PROVIDER_CACHE
    if _PROVIDER_CACHE is not None and _PROVIDER_KIND == provider_name:
        return _PROVIDER_CACHE

    if provider_name == "openai":
        try:
            _PROVIDER_CACHE = _build_openai_provider(settings)
            _PROVIDER_KIND = provider_name
        except Exception as exc:  # pragma: no cover - surface error to caller
            _LOG.error("Failed to initialise OpenAI embedding provider: %s", exc)
            raise
    elif provider_name in {"mock", "offline", "memory"}:
        _PROVIDER_CACHE = _MockEmbeddingProvider(dimension=settings.embedding_dimension)
        _PROVIDER_KIND = provider_name
    else:  # pragma: no cover - unexpected provider names
        _LOG.warning("Unknown embedding provider '%s'; using mock provider", provider_name)
        _PROVIDER_CACHE = _MockEmbeddingProvider(dimension=settings.embedding_dimension)
        _PROVIDER_KIND = "mock"

    return _PROVIDER_CACHE


def reset_embedding_provider() -> None:
    """Reset cached provider (used in tests)."""

    global _PROVIDER_CACHE, _PROVIDER_KIND
    _PROVIDER_CACHE = None
    _PROVIDER_KIND = None
