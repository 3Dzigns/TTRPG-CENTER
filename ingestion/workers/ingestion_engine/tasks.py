"""
Ingestion engine worker tasks for Pass A orchestration.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from ingestion.config import Settings
from ingestion.artifacts import load_elements, load_elements_meta, write_elements_meta, load_embeddings_artifact
from ingestion.core.db.dictionary import DictionaryEntry, get_dictionary_store
from ingestion.core.idempotency import fingerprint_payload, mark_stage_completed, stage_completed
from ingestion.core.job_registry import JobRegistry, JobState, new_record
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span, send_task_with_tracing
from ingestion.workers.unstructured.tasks import process_document

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


@lru_cache(maxsize=1)
def _get_dictionary_store():
    """Lazy initialization of dictionary store with caching."""
    return get_dictionary_store(_settings)


def _normalize_term(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _load_elements(job_id: str) -> List[dict]:
    elements_path = _settings.artifacts_dir / job_id / "unstructured" / "elements.json"
    if not elements_path.exists():
        raise FileNotFoundError(f"Elements file not found for job {job_id}: {elements_path}")
    record = _registry.get(job_id)
    source_id = record.source_path if record else job_id
    with start_span(
        "elements.read_file",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "ingestion_engine",
            "path": str(elements_path),
        },
    ) as span:
        try:
            span.set_attribute("bytes", elements_path.stat().st_size)
        except OSError:  # pragma: no cover - file removed between existence check/stat
            pass
        artifact = load_elements(elements_path)
        raw_elements = artifact.elements
        span.set_attribute("elements_count", len(raw_elements))
    normalized: List[dict] = []
    for item in raw_elements:
        if hasattr(item, "model_dump"):
            candidate = item.model_dump()  # type: ignore[attr-defined]
        elif hasattr(item, "dict"):
            candidate = item.dict()  # type: ignore[attr-defined]
        else:
            candidate = item

        if isinstance(candidate, dict):
            text = candidate.get("text") or ""
            metadata = candidate.get("metadata", {}) or {}
            normalized.append(
                {
                    "text": text,
                    "page_number": metadata.get("page_number") or candidate.get("page_number"),
                    "section_title": metadata.get("section_title") or candidate.get("section_title"),
                }
            )
        else:
            normalized.append({"text": str(candidate), "page_number": None, "section_title": None})
    return normalized


def _build_metadata(elements: List[dict]) -> List[dict]:
    metadata: List[dict] = []
    section_counter = 1
    for idx, element in enumerate(elements, start=1):
        text = element.get("text", "").strip()
        if not text:
            continue
        page_number = element.get("page_number") or idx
        section_title = element.get("section_title") or f"Section {section_counter}"
        section_counter += 1
        metadata.append(
            {
                "text": text,
                "page_number": page_number,
                "section_title": section_title,
                "facets": {"system": "ttrpg_center"},
            }
        )
    return metadata


@shared_task(bind=True, name="ingestion_engine.orchestrate", queue="ingestion_engine")
def orchestrate_passes(self, job_id: str) -> str:
    record = _registry.get(job_id)
    if not record:
        _LOG.warning("No job found for orchestration", extra={"job_id": job_id})
        return "job-missing"

    _registry.update_state(
        job_id,
        state=JobState.RUNNING,
        stage="ingestion_engine",
        message="Dispatching Unstructured processing",
    )
    _LOG.info(
        "Queued unstructured processing",
        extra={"job_id": job_id, "source": record.source_path},
    )
    try:
        process_document.delay(job_id, record.source_path)
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline unstructured processing: %s", exc)
        process_document(None, job_id, record.source_path)
    return "unstructured-queued"


@shared_task(bind=True, name="ingestion_engine.elements_to_metadata", queue="ingestion_engine")
def elements_to_metadata(self, job_id: str) -> str:
    record = _registry.get(job_id)
    source_id = record.source_path if record else job_id
    try:
        elements = _load_elements(job_id)
    except FileNotFoundError as exc:
        _LOG.error(str(exc))
        return "missing-elements"

    with start_span(
        "elements.metadata_enrichment",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "ingestion_engine",
            "elements": len(elements),
        },
    ) as span:
        metadata = _build_metadata(elements)
        span.set_attribute("metadata_count", len(metadata))
    metadata_dir = _settings.artifacts_dir / job_id / "metadata"
    metadata_path = metadata_dir / "elements_with_meta.json"
    metadata_fingerprint = fingerprint_payload(metadata)

    if stage_completed(_settings, job_id, "elements_to_metadata", fingerprint=metadata_fingerprint) and metadata_path.exists():
        _LOG.info("Metadata stage already completed", extra={"job_id": job_id})
    else:
        # Write the metadata artifact once per unique fingerprint so retries remain idempotent.
            metadata_dir.mkdir(parents=True, exist_ok=True)
            write_elements_meta(metadata_path, metadata)
            mark_stage_completed(
                _settings,
                job_id,
                "elements_to_metadata",
            fingerprint=metadata_fingerprint,
            details={"count": len(metadata)},
        )

    try:
        _registry.update_state(
            job_id,
            state=JobState.STAGED,
            stage="elements_to_metadata",
            message=f"Enriched metadata ({len(metadata)} elements)",
        )
    except KeyError:
        existing = _registry.get(job_id)
        source_path = existing.source_path if existing else str((_settings.sources_dir / Path(job_id).name))
        fallback = new_record(
            job_id=job_id,
            source_path=source_path,
            state=JobState.STAGED,
            refresh=existing.refresh if existing else False,
            stage="elements_to_metadata",
            message=f"Enriched metadata ({len(metadata)} elements)",
        )
        _registry.upsert(fallback)

    try:
        send_task_with_tracing(self.app, "haystack.generate_embeddings", args=[job_id])
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline haystack task: %s", exc)
        from ingestion.workers.haystack.tasks import generate_embeddings

        generate_embeddings(None, job_id)

    return str(metadata_path)


@shared_task(bind=True, name="ingestion_engine.dictionary_upsert", queue="ingestion_engine")
def dictionary_upsert(self, job_id: str) -> int:
    record = _registry.get(job_id)
    if not record:
        _LOG.warning("No job record found for dictionary upsert", extra={"job_id": job_id})
        return 0

    # Read from embeddings artifact (which now has extracted_terms in facets)
    embeddings_path = _settings.artifacts_dir / job_id / "embeddings" / "embeddings.json"
    if not embeddings_path.exists():
        _LOG.error("Embeddings file missing for job %s", job_id)
        return 0

    source_id = record.source_path if record else job_id
    with start_span(
        "embeddings.read_file",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "dictionary_upsert",
            "path": str(embeddings_path),
        },
    ) as span:
        try:
            span.set_attribute("bytes", embeddings_path.stat().st_size)
        except OSError:  # pragma: no cover
            pass
        embeddings_artifact = load_embeddings_artifact(embeddings_path)
        chunks = embeddings_artifact.chunks
        span.set_attribute("chunk_count", len(chunks))

    # Extract dictionary entries from pre-extracted terms in embeddings
    entries: List[DictionaryEntry] = []
    for chunk in chunks:
        chunk_text = (chunk.text or "").strip()
        if not chunk_text:
            continue

        # Get pre-extracted terms from facets
        facets = chunk.facets or {}
        extracted_terms = facets.get("extracted_terms", [])

        # Create one dictionary entry per extracted term
        for term in extracted_terms:
            if not term or not term.strip():
                continue

            entry: DictionaryEntry = {
                "source_id": job_id,
                "normalized_term": term.lower().strip(),  # Already normalized
                "raw_text": chunk_text,  # Context where term appears
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "facets": {
                    "chunk_id": chunk.chunk_id,
                    "term_source": "haystack_extraction",
                },
            }
            entries.append(entry)

    entries_fingerprint = fingerprint_payload(entries)

    # Removed early idempotency check - now validates after successful upsert
    # This ensures the database is always updated even if stage marker exists
    # The upsert operation itself is idempotent via ON CONFLICT

    try:
        _registry.update_state(
            job_id,
            state=JobState.UPSERTING,
            stage="dictionary_upsert",
            message="Upserting dictionary entries",
        )
    except KeyError:
        fallback = new_record(
            job_id=job_id,
            source_path=record.source_path,
            state=JobState.UPSERTING,
            refresh=record.refresh,
            stage="dictionary_upsert",
            message="Upserting dictionary entries",
        )
        _registry.upsert(fallback)

    purge_stage = "dictionary_upsert_purge"
    # Clear existing dictionary entries exactly once when refresh jobs run.
    should_refresh_clear = record.refresh and not stage_completed(_settings, job_id, purge_stage)
    dictionary_store = _get_dictionary_store()
    count = dictionary_store.upsert_terms(job_id, entries, refresh=should_refresh_clear)
    if should_refresh_clear:
        mark_stage_completed(_settings, job_id, purge_stage)
        _registry.append_history(
            job_id,
            stage="dictionary_upsert",
            message="Dictionary cleared prior to refresh",
        )

    try:
        _registry.update_state(
            job_id,
            state=JobState.UPSERTING,
            stage="dictionary_upsert",
            message=f"Dictionary upsert complete ({count} entries)",
        )
    except KeyError:
        fallback = new_record(
            job_id=job_id,
            source_path=record.source_path,
            state=JobState.UPSERTING,
            refresh=record.refresh,
            stage="dictionary_upsert",
            message=f"Dictionary upsert complete ({count} entries)",
        )
        _registry.upsert(fallback)

    mark_stage_completed(
        _settings,
        job_id,
        "dictionary_upsert",
        fingerprint=entries_fingerprint,
        details={"count": count},
    )

    try:
        send_task_with_tracing(self.app, "cassandra_upsert.write", args=[job_id])
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline cassandra upsert: %s", exc)
        from ingestion.workers.cassandra_upsert.tasks import upsert_embeddings

        upsert_embeddings(None, job_id)

    return count

