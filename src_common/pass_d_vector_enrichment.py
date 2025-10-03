"""Pass D vector enrichment with Haystack integrations and fallbacks."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src_common.config import ConfigManager
from src_common.logging import get_logger
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete, log_heartbeat
from src_common.vector_store.factory import make_vector_store

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
    content: str
    chunk_metadata: Dict[str, Any]


@dataclass
class SourceMetadata:
    source_hash: str
    source_file: str
    environment: str
    job_id: str


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
    rows_persisted: int = 0
    success: bool = True
    error_message: Optional[str] = None


class VectorEnricher:
    """Handles chunk loading and embedding generation."""

    def __init__(self, job_id: str, env: str, job_log_file: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file
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

        # Pass start logging
        log_pass_start("D", f"Vector Enrichment & NER (model={self.embedding_model})", self.job_log_file)

        pass_dir = job_dir / "pass_d"
        pass_dir.mkdir(parents=True, exist_ok=True)

        chunks_file = job_dir / "pass_c" / f"{self.job_id}_pass_c_chunks.jsonl"
        if not chunks_file.exists():
            raise FileNotFoundError(f"Pass C chunks not found: {chunks_file}")

        logger.info(f"Pass D: Loading chunks from {chunks_file.name}")
        records = list(self._load_chunks(chunks_file))
        logger.info(f"Pass D: Loaded {len(records)} chunks for vector enrichment")

        vectors: List[VectorRecord] = []
        haystack_used = False
        fallback_used = False
        rows_persisted = 0

        if records:
            if self._haystack_retriever is not None:
                try:
                    logger.info(f"Pass D: Starting Haystack embedding generation for {len(records)} chunks (this may take 30-90s)")
                    log_to_job(f"Starting Haystack embedding for {len(records)} chunks (30-90s operation)", self.job_log_file, "info", "D")
                    embedding_started = time.perf_counter()

                    haystack_vectors = self._run_haystack(records)
                    vectors.extend(haystack_vectors)
                    haystack_used = True

                    embedding_duration = time.perf_counter() - embedding_started
                    logger.info(f"Pass D: Haystack embedding completed in {embedding_duration:.1f}s ({len(vectors)} vectors)")
                    log_to_job(f"Haystack embedding completed in {embedding_duration:.1f}s ({len(vectors)} vectors)", self.job_log_file, "info", "D")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "pass_d_haystack_failure",
                        extra={"job_id": self.job_id, "reason": str(exc)},
                    )
                    logger.info(f"Pass D: Falling back to zero-vector generation")
                    vectors.extend(self._fallback_vectors(records))
                    fallback_used = True
            else:
                logger.info(f"Pass D: Haystack not available, using zero-vector fallback for {len(records)} chunks")
                vectors.extend(self._fallback_vectors(records))
                fallback_used = True

        if vectors:
            rows_persisted = self._persist_vectors(job_dir, vectors)

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
                    "rows_persisted": rows_persisted,
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
                    "rows_persisted": rows_persisted,
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
        duration_seconds = processing_time_ms / 1000

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

        # Pass complete logging
        stats = {
            "chunks_vectorized": len(vectors),
            "model": self.embedding_model,
            "haystack_used": haystack_used,
            "fallback_used": fallback_used,
            "rows_persisted": rows_persisted
        }
        log_pass_complete("D", duration_seconds, stats, self.job_log_file)

        return PassDResult(
            job_id=self.job_id,
            chunks_vectorized=len(vectors),
            model_used=self.embedding_model,
            haystack_used=haystack_used,
            fallback_used=fallback_used,
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
            rows_persisted=rows_persisted,
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
        documents = [Document(content=item.get("text", ""), meta=item) for item in records]
        embeddings = self._haystack_retriever.embed_documents(documents)  # type: ignore[attr-defined]
        vectors: List[VectorRecord] = []
        for item, vector in zip(records, embeddings, strict=False):
            vectors.append(self._build_vector_record(item, vector, self.embedding_model))
        return vectors

    def _fallback_vectors(self, records: List[Dict[str, str]]) -> List[VectorRecord]:
        vectors: List[VectorRecord] = []
        for item in records:
            vector = _hash_to_vector(item.get("text", ""), self.vector_dim)
            vectors.append(self._build_vector_record(item, vector, f"fallback-{self.vector_dim}d"))
        return vectors

    def _build_vector_record(self, item: Dict[str, Any], embedding: Iterable[float], embedding_model: str) -> VectorRecord:
        embedding_list = [float(value) for value in embedding]
        checksum = _sha256_vector(embedding_list)
        metadata: Dict[str, str] = {}
        lineage = item.get("lineage")
        if isinstance(lineage, dict):
            for key, value in lineage.items():
                if value is None:
                    continue
                metadata[str(key)] = str(value)
        page_number = item.get("page_number") or item.get("page")
        if page_number is not None:
            metadata.setdefault("page_number", str(page_number))
        if item.get("section"):
            metadata.setdefault("section", str(item.get("section")))
        doc_id = str(item.get("doc_id", self.job_id))
        part_id = str(item.get("part_id", ""))
        section_id = str(item.get("section_id", ""))
        chunk_id = str(item.get("chunk_id") or f"{doc_id}-chunk-{checksum[:12]}")
        content = str(item.get("text") or item.get("content") or "")
        chunk_metadata = dict(item)
        chunk_metadata.setdefault("chunk_id", chunk_id)
        chunk_metadata.setdefault("doc_id", doc_id)
        return VectorRecord(
            doc_id=doc_id,
            part_id=part_id,
            section_id=section_id,
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            embedding=embedding_list,
            checksum_sha256=checksum,
            metadata=metadata,
            content=content,
            chunk_metadata=chunk_metadata,
        )

    def _persist_vectors(self, job_dir: Path, vectors: List[VectorRecord]) -> int:
        if not vectors:
            return 0

        source_meta = self._load_source_metadata(job_dir)
        documents = self._build_vector_documents(vectors, source_meta)
        vector_store = make_vector_store(self.env)
        try:
            rows_written = vector_store.upsert_documents(documents)
            verification_count = vector_store.count_documents_for_source(
                source_meta.source_hash,
                source_meta.environment,
            )
        finally:
            try:
                vector_store.close()
            except Exception:
                pass

        if rows_written <= 0:
            logger.error("Pass D: Cassandra upsert returned zero rows", extra={"job_id": self.job_id, "source_hash": source_meta.source_hash})
            raise RuntimeError("Pass D: Cassandra upsert returned zero rows")
        expected = len(documents)
        if verification_count < expected:
            logger.error(
                "Pass D: Cassandra verification failed",
                extra={
                    "job_id": self.job_id,
                    "source_hash": source_meta.source_hash,
                    "expected": expected,
                    "actual": verification_count,
                },
            )
            raise RuntimeError(
                f"Pass D: Cassandra verification failed for job {self.job_id} (source {source_meta.source_hash}): expected >= {expected}, got {verification_count}"
            )

        logger.info(
            "pass_d.cassandra.rows_written",
            extra={
                "job_id": self.job_id,
                "rows_written": rows_written,
                "verification_count": verification_count,
            },
        )
        log_to_job(
            f"Persisted {rows_written} rows to Cassandra (verified {verification_count})",
            self.job_log_file,
            "info",
            "D",
        )
        return rows_written

    def _build_vector_documents(self, vectors: List[VectorRecord], source: SourceMetadata) -> List[Dict[str, Any]]:
        now = time.time()
        documents: List[Dict[str, Any]] = []
        for record in vectors:
            metadata: Dict[str, Any] = dict(record.metadata)
            chunk_meta = record.chunk_metadata
            for key in ("page", "page_number", "section", "section_id", "type"):
                value = chunk_meta.get(key)
                if value is not None and key not in metadata:
                    metadata[key] = str(value)
            metadata.setdefault("doc_id", record.doc_id)
            metadata.setdefault("part_id", record.part_id)
            metadata.setdefault("section_id", record.section_id)
            metadata.setdefault("chunk_id", record.chunk_id)
            metadata["job_id"] = source.job_id
            metadata["source_hash"] = source.source_hash
            metadata["source_file"] = source.source_file
            metadata["environment"] = source.environment

            documents.append(
                {
                    "chunk_id": record.chunk_id,
                    "content": record.content,
                    "metadata": metadata,
                    "stage": "pass_d",
                    "embedding": record.embedding,
                    "embedding_model": record.embedding_model,
                    "vector_id": record.checksum_sha256,
                    "source_hash": source.source_hash,
                    "source_file": source.source_file,
                    "environment": source.environment,
                    "updated_at": now,
                    "loaded_at": now,
                }
            )
        return documents

    def _load_source_metadata(self, job_dir: Path) -> SourceMetadata:
        manifest_candidates = [
            job_dir / "manifest.json",
            job_dir / "pass_a" / f"{self.job_id}_pass_a_manifest.json",
        ]
        for candidate in manifest_candidates:
            if not candidate.exists():
                continue
            try:
                with candidate.open("r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
            except Exception as exc:
                logger.debug("Pass D: unable to parse manifest %s: %s", candidate, exc)
                continue

            source_hash = (
                manifest.get("source_info", {}).get("source_hash")
                or manifest.get("pass_0_result", {}).get("source_hash")
                or manifest.get("source_hash")
            )
            source_file = (
                manifest.get("source_file")
                or manifest.get("source")
                or manifest.get("source_path")
                or manifest.get("pdf_path")
            )
            environment = manifest.get("environment") or self.env

            if isinstance(source_file, list) and source_file:
                source_file = source_file[0]

            if source_hash and source_file:
                return SourceMetadata(
                    source_hash=str(source_hash),
                    source_file=str(source_file),
                    environment=str(environment or self.env),
                    job_id=self.job_id,
                )

        raise RuntimeError("Pass D: Unable to determine source metadata for Cassandra persistence")


def process_pass_d(job_dir: Path, job_id: str, env: str, job_log_file: Optional[Path] = None) -> PassDResult:
    enricher = VectorEnricher(job_id=job_id, env=env, job_log_file=job_log_file)
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
