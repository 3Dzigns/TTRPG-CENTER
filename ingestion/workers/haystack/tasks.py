"""
Haystack worker for embedding generation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import List, Sequence, Tuple

from ingestion.config import Settings
from ingestion.artifacts import load_elements_meta, load_embeddings_artifact, write_embeddings_artifact
from ingestion.core.embeddings import get_embedding_provider
from ingestion.core.idempotency import fingerprint_payload, mark_stage_completed, stage_completed
from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span, send_task_with_tracing
from ingestion.core.term_extraction import TermExtractor, DictionaryFilter

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


def _load_metadata(job_id: str) -> List[dict]:
    metadata_path = _settings.artifacts_dir / job_id / "metadata" / "elements_with_meta.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file missing for embeddings: {metadata_path}")
    record = _registry.get(job_id)
    source_id = record.source_path if record else job_id
    with start_span(
        "metadata.read_file",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "haystack",
            "path": str(metadata_path),
        },
    ) as span:
        try:
            span.set_attribute("bytes", metadata_path.stat().st_size)
        except OSError:  # pragma: no cover
            pass
        artifact = load_elements_meta(metadata_path)
        items = []
        for entry in artifact.items:
            if hasattr(entry, "model_dump"):
                items.append(entry.model_dump())  # type: ignore[attr-defined]
            elif hasattr(entry, "dict"):
                items.append(entry.dict())  # type: ignore[attr-defined]
            else:
                items.append(entry)
        span.set_attribute("metadata_count", len(items))
        return items


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_vector(vector: Sequence[float]) -> str:
    digest = hashlib.sha256()
    for value in vector:
        digest.update(f"{value:.12f}".encode("utf-8"))
    return digest.hexdigest()


def _build_embedding_inputs(payload: List[dict]) -> Tuple[List[str], List[dict]]:
    texts: List[str] = []
    meta: List[dict] = []

    # Initialize term extractor and filter
    extractor = TermExtractor(max_terms_per_chunk=15)
    term_filter = DictionaryFilter(
        min_length=3,
        max_length=100,
        min_alpha_ratio=0.65,
        enable_logging=False,
    )

    for item in payload:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        # Extract dictionary terms from text
        raw_terms = extractor.extract_terms(text)
        valid_terms, _rejected = term_filter.filter_terms(raw_terms)

        # Normalize terms for storage
        normalized_terms = [term.lower().strip() for term in valid_terms]

        # Enrich metadata with extracted terms
        enriched_item = dict(item)
        existing_facets = enriched_item.get("facets") or {}
        enriched_item["facets"] = {
            **existing_facets,
            "extracted_terms": normalized_terms,
        }

        texts.append(text)
        meta.append(enriched_item)

    # Log term extraction stats
    stats = term_filter.get_statistics()
    if stats["terms_processed"] > 0:
        _LOG.info(
            "Term extraction complete",
            extra={
                "chunks": len(texts),
                "terms_extracted": stats["terms_accepted"],
                "terms_rejected": stats["terms_processed"] - stats["terms_accepted"],
                "rejection_rate": f"{stats['rejection_rate_percent']}%",
            },
        )

    return texts, meta


@shared_task(bind=True, name="haystack.generate_embeddings", queue="haystack")
def generate_embeddings(self, job_id: str) -> str:
    try:
        payload = _load_metadata(job_id)
    except FileNotFoundError as exc:
        _LOG.error(str(exc))
        return "metadata-missing"

    record = _registry.get(job_id)
    source_id = record.source_path if record else job_id

    with start_span(
        "haystack.chunking",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "haystack",
        },
    ) as span:
        texts, meta = _build_embedding_inputs(payload)
        total_chars = sum(len(text) for text in texts)
        span.set_attribute("chunk_count", len(texts))
        span.set_attribute("total_chars", total_chars)
    metadata_payloads: List[dict] = []
    fingerprint_items: List[dict] = []
    for text, item in zip(texts, meta):
        metadata_payload = {
            "page_number": item.get("page_number"),
            "section_title": item.get("section_title"),
            "facets": item.get("facets"),
        }
        metadata_payloads.append(metadata_payload)
        fingerprint_items.append(
            {
                "text_hash": _hash_text(text),
                "metadata_hash": _hash_text(json.dumps(metadata_payload, sort_keys=True)),
            }
        )

    stage_fingerprint = fingerprint_payload(
        {"model": _settings.embedding_model, "items": fingerprint_items}
    )
    embeddings_dir = _settings.artifacts_dir / job_id / "embeddings"
    embeddings_path = embeddings_dir / "embeddings.json"
    chunks_vectors_path = embeddings_dir / "chunks_with_vectors.json"

    # Reuse previously generated embeddings if the content/model fingerprint is unchanged.
    if stage_completed(_settings, job_id, "haystack", fingerprint=stage_fingerprint) and embeddings_path.exists():
        if not chunks_vectors_path.exists():
            try:
                existing = load_embeddings_artifact(embeddings_path)
                write_embeddings_artifact(chunks_vectors_path, existing)
                _LOG.info("Backfilled chunks_with_vectors artifact", extra={"job_id": job_id})
            except Exception as exc:  # pragma: no cover - best effort backfill
                _LOG.warning("Failed to backfill chunks_with_vectors.json: %s", exc, extra={"job_id": job_id})
        _LOG.info("Embeddings already generated", extra={"job_id": job_id})
    else:
        provider = get_embedding_provider(_settings)
        with start_span(
            "haystack.openai_embeddings",
            attributes={
                "job_id": job_id,
                "source_id": source_id,
                "stage": "haystack",
                "model": _settings.embedding_model,
                "batch_size": _settings.embedding_batch_size,
                "input_count": len(texts),
            },
        ) as span:
            try:
                vectors = provider.embed(texts, job_id=job_id)
            except Exception as exc:
                _LOG.exception("Embedding generation failed", extra={"job_id": job_id})
                raise
            span.set_attribute("vector_count", len(vectors))
        if len(vectors) != len(texts):
            raise ValueError(
                f"Embedding provider returned {len(vectors)} vectors for {len(texts)} inputs"
            )

        chunks: List[dict] = []
        for index, (text, metadata_payload, vector, fingerprint_info) in enumerate(
            zip(texts, metadata_payloads, vectors, fingerprint_items), start=1
        ):
            vector_hash = _hash_vector(vector)
            chunk_id = f"{job_id}-chunk-{index}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "chunk_index": index,
                    "text": text,
                    "page_number": metadata_payload["page_number"],
                    "section_title": metadata_payload["section_title"],
                    "facets": metadata_payload["facets"],
                    "text_hash": fingerprint_info["text_hash"],
                    "metadata_hash": fingerprint_info["metadata_hash"],
                    "vector_hash": vector_hash,
                    "embedding": vector,
                }
            )

        embeddings_dir.mkdir(parents=True, exist_ok=True)
        embeddings_payload = {
            "model": _settings.embedding_model,
            "provider": _settings.embedding_provider,
            "dimension": _settings.embedding_dimension,
            "chunks": chunks,
        }
        write_embeddings_artifact(chunks_vectors_path, embeddings_payload)
        # Maintain legacy path for downstream compatibility.
        write_embeddings_artifact(embeddings_path, embeddings_payload)
        manifest = {
            "schema_version": "1",
            "job_id": job_id,
            "document_id": job_id,
            "chunk_count": len(chunks),
            "fingerprint": stage_fingerprint,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "model": _settings.embedding_model,
            "provider": _settings.embedding_provider,
            "dimension": _settings.embedding_dimension,
            "total_chars": total_chars,
            "metadata_fields": sorted({key for item in payload for key in item.keys()}),
        }
        (embeddings_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        mark_stage_completed(
            _settings,
            job_id,
            "haystack",
            fingerprint=stage_fingerprint,
            details={"count": len(chunks)},
        )

        _registry.update_state(
            job_id,
            state=JobState.UPSERTING,
            stage="haystack",
            message=f"Generated {len(chunks)} embeddings",
        )

    try:
        send_task_with_tracing(self.app, "ingestion_engine.dictionary_upsert", args=[job_id])
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline dictionary upsert: %s", exc)
        from ingestion.workers.ingestion_engine.tasks import dictionary_upsert

        dictionary_upsert(None, job_id)

    return str(embeddings_path)
