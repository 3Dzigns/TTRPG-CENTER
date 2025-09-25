"""Pass D vector enrichment with Haystack integrations and fallbacks."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src_common.config import ConfigManager
from src_common.logging import get_logger

try:
    from haystack import Document  # type: ignore
    from haystack.nodes import EmbeddingRetriever  # type: ignore
    HAYSTACK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    Document = None
    EmbeddingRetriever = None
    HAYSTACK_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class VectorRecord:
    """Vector enrichment record."""

    doc_id: str
    part_id: str
    section_id: str
    chunk_id: str
    embedding_model: str
    embedding: List[float]
    checksum_sha256: str
    metadata: Dict[str, str]


@dataclass
class PassDResult:
    """Structured Pass D result."""

    job_id: str
    chunks_vectorized: int
    model_used: str
    haystack_used: bool
    fallback_used: bool
    processing_time_ms: int
    artifacts: List[str]
    success: bool = True
    error_message: Optional[str] = None


class VectorEnricher:
    """Handles chunk loading and embedding generation."""

    def __init__(self, job_id: str, env: str) -> None:
        self.job_id = job_id
        self.env = env
        self.config = ConfigManager()
        self.embedding_model = self.config.get_config("PASS_D_EMBEDDING_MODEL", "text-embedding-3-small")
        self.vector_dim = int(self.config.get_config("PASS_D_EMBED_DIM", 384))
        self.haystack_concurrency = int(self.config.get_config("PASS_D_MAX_CONCURRENCY", 4))
        self._haystack_retriever = self._build_haystack_retriever()

    def _build_haystack_retriever(self):
        if not HAYSTACK_AVAILABLE:
            return None
        try:
            api_key = self.config.get_config("HAYSTACK_API_KEY")
            endpoint = self.config.get_config("HAYSTACK_ENDPOINT")
            if not api_key or not endpoint:
                return None
            retriever = EmbeddingRetriever(
                api_key=api_key,
                api_url=endpoint,
                model=self.embedding_model,
                top_k=0,
                progress_bar=False,
            )
            return retriever
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "pass_d_haystack_init_failed",
                extra={"job_id": self.job_id, "reason": str(exc)},
            )
            return None

    def process(self, job_dir: Path) -> PassDResult:
        started_at = time.perf_counter()
        pass_dir = job_dir / "pass_d"
        pass_dir.mkdir(parents=True, exist_ok=True)

        chunks_file = job_dir / "pass_c" / f"{self.job_id}_pass_c_chunks.jsonl"
        if not chunks_file.exists():
            raise FileNotFoundError(f"Pass C chunks not found: {chunks_file}")

        records = list(self._load_chunks(chunks_file))
        vectors: List[VectorRecord] = []
        haystack_used = False
        fallback_used = False

        if records:
            if self._haystack_retriever is not None:
                try:
                    haystack_vectors = self._run_haystack(records)
                    vectors.extend(haystack_vectors)
                    haystack_used = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "pass_d_haystack_failure",
                        extra={"job_id": self.job_id, "reason": str(exc)},
                    )
                    vectors.extend(self._fallback_vectors(records))
                    fallback_used = True
            else:
                vectors.extend(self._fallback_vectors(records))
                fallback_used = True

        vectors_path = pass_dir / f"{self.job_id}_pass_d_vectors.jsonl"
        with vectors_path.open("w", encoding="utf-8") as handle:
            for record in vectors:
                handle.write(json.dumps(asdict(record), ensure_ascii=True))
                handle.write("\n")

        summary_path = pass_dir / "vector_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "model": self.embedding_model,
                    "vector_dim": self.vector_dim,
                    "chunks_vectorized": len(vectors),
                    "haystack_used": haystack_used,
                    "fallback_used": fallback_used,
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )

        delta_path = pass_dir / "dict_delta.passD.json"
        with delta_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "model": self.embedding_model,
                    "chunks": [record.metadata for record in vectors],
                },
                handle,
                indent=2,
            )

        artifacts = [
            vectors_path.relative_to(job_dir).as_posix(),
            summary_path.relative_to(job_dir).as_posix(),
            delta_path.relative_to(job_dir).as_posix(),
        ]

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "pass_d_complete",
            extra={
                "job_id": self.job_id,
                "vectors": len(vectors),
                "model": self.embedding_model,
                "haystack_used": haystack_used,
                "fallback_used": fallback_used,
                "duration_ms": processing_time_ms,
            },
        )

        return PassDResult(
            job_id=self.job_id,
            chunks_vectorized=len(vectors),
            model_used=self.embedding_model,
            haystack_used=haystack_used,
            fallback_used=fallback_used,
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
        )

    def _load_chunks(self, chunks_file: Path) -> Iterable[Dict[str, str]]:
        with chunks_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def _run_haystack(self, records: List[Dict[str, str]]) -> List[VectorRecord]:
        assert self._haystack_retriever is not None
        documents = [Document(content=item["text"], meta=item) for item in records]
        embeddings = self._haystack_retriever.embed_documents(documents)  # type: ignore[attr-defined]
        vectors: List[VectorRecord] = []
        for item, vector in zip(records, embeddings, strict=False):
            vectors.append(
                VectorRecord(
                    doc_id=item["doc_id"],
                    part_id=item.get("part_id", ""),
                    section_id=item.get("section_id", ""),
                    chunk_id=item.get("chunk_id", ""),
                    embedding_model=self.embedding_model,
                    embedding=list(vector),
                    checksum_sha256=_sha256_vector(vector),
                    metadata={"chunk_id": item.get("chunk_id", ""), "doc_id": item["doc_id"]},
                )
            )
        return vectors

    def _fallback_vectors(self, records: List[Dict[str, str]]) -> List[VectorRecord]:
        vectors: List[VectorRecord] = []
        for item in records:
            text = item.get("text", "")
            vector = _hash_to_vector(text, self.vector_dim)
            vectors.append(
                VectorRecord(
                    doc_id=item.get("doc_id", self.job_id),
                    part_id=item.get("part_id", "unknown"),
                    section_id=item.get("section_id", "unknown"),
                    chunk_id=item.get("chunk_id", ""),
                    embedding_model=f"fallback-{self.vector_dim}d",
                    embedding=vector,
                    checksum_sha256=_sha256_vector(vector),
                    metadata={"chunk_id": item.get("chunk_id", ""), "doc_id": item.get("doc_id", self.job_id)},
                )
            )
        return vectors


def process_pass_d(job_dir: Path, job_id: str, env: str) -> PassDResult:
    enricher = VectorEnricher(job_id=job_id, env=env)
    return enricher.process(job_dir)


def _hash_to_vector(text: str, dim: int) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed_bytes = digest * ((dim * 4 + len(digest) - 1) // len(digest))
    vector: List[float] = []
    for index in range(dim):
        chunk = seed_bytes[index * 4 : (index + 1) * 4]
        if len(chunk) < 4:
            chunk = chunk.ljust(4, b"\0")
        value = int.from_bytes(chunk, "big")
        normalized = (value % 10000) / 10000.0
        vector.append(normalized)
    return vector


def _sha256_vector(vector: Iterable[float]) -> str:
    digest = hashlib.sha256()
    for value in vector:
        digest.update(f"{value:.6f}".encode("utf-8"))
    return digest.hexdigest()


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
