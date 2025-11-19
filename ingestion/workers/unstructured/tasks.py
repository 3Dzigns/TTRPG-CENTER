"""
Unstructured worker tasks.

Runs the Unstructured.io local pipeline inside the container without relying on
HTTP transport. The current implementation is a stub that records intent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from ingestion.config import Settings
from ingestion.artifacts import write_elements
from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span, send_task_with_tracing

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


def _process_locally(source_path: Path) -> Dict[str, List[dict]]:
    """
    Process document using Unstructured.io library.

    Extracts structured elements (paragraphs, titles, tables, etc.) from PDFs
    and other document formats using automatic detection and high-resolution processing.

    Args:
        source_path: Path to the source document file

    Returns:
        Dictionary with schema_version and list of element dictionaries
    """
    from unstructured.partition.auto import partition
    from unstructured.chunking.title import chunk_by_title

    _LOG.info("Starting real PDF processing", extra={"source": str(source_path)})

    try:
        # Partition the document with high-resolution strategy for better accuracy
        elements = partition(
            filename=str(source_path),
            strategy="hi_res",  # Use high-resolution for better text extraction
            pdf_infer_table_structure=True,  # Detect tables in PDFs
            languages=["eng"],  # English language processing
        )

        _LOG.info(f"Extracted {len(elements)} elements from {source_path.name}")

        # Chunk elements to prevent oversized text blocks and ensure consistent chunk sizes
        # This prevents token limit errors during embedding while maintaining metadata context
        chunked_elements = chunk_by_title(
            elements,
            max_characters=600,              # Hard limit: 600 chars per chunk
            new_after_n_chars=500,           # Soft limit: start looking for split at 500 chars
            overlap=50,                      # 50 character overlap between chunks
            combine_text_under_n_chars=100,  # Combine very small elements
        )

        _LOG.info(
            f"Chunked {len(elements)} elements into {len(chunked_elements)} chunks "
            f"(500-600 chars/chunk, 50 char overlap)"
        )

        # Use chunked elements for remainder of processing
        # NOTE: Metadata (page_number, section_title, etc.) is preserved and replicated
        # to each chunk so every chunk knows its source context
        elements = chunked_elements

        # Convert elements to serializable dictionaries
        element_dicts = []
        for elem in elements:
            element_dict = {
                "type": elem.category if hasattr(elem, "category") else "Unknown",
                "text": str(elem),
                "metadata": {},
            }

            # Extract metadata if available
            if hasattr(elem, "metadata"):
                metadata = elem.metadata
                if hasattr(metadata, "page_number"):
                    element_dict["metadata"]["page_number"] = metadata.page_number
                if hasattr(metadata, "filename"):
                    element_dict["metadata"]["filename"] = metadata.filename
                if hasattr(metadata, "filetype"):
                    element_dict["metadata"]["filetype"] = metadata.filetype
                if hasattr(metadata, "coordinates"):
                    # Store coordinates for layout information
                    coords = metadata.coordinates
                    if coords:
                        element_dict["metadata"]["coordinates"] = str(coords)

            element_dicts.append(element_dict)

        return {
            "schema_version": "1",
            "elements": element_dicts,
        }

    except Exception as exc:
        _LOG.error(f"Failed to process {source_path.name}: {exc}", exc_info=True)
        # Return minimal structure on failure to allow pipeline to continue
        return {
            "schema_version": "1",
            "elements": [
                {
                    "type": "ProcessingError",
                    "text": f"Failed to process document: {exc}",
                    "metadata": {"error": str(exc)},
                }
            ],
        }


def _dispatch(task_ref, job_id: str, app) -> None:
    try:
        if app is not None:
            send_task_with_tracing(app, task_ref, args=[job_id])
        else:
            raise RuntimeError("no-app")
    except Exception as exc:  # pragma: no cover - fallback for local/dev tests
        _LOG.warning("Falling back to inline execution for %s: %s", task_ref, exc)
        if task_ref == "ingestion_engine.elements_to_metadata":
            from ingestion.workers.ingestion_engine.tasks import elements_to_metadata

            elements_to_metadata(None, job_id)
        elif task_ref == "ingestion_engine.dictionary_upsert":
            from ingestion.workers.ingestion_engine.tasks import dictionary_upsert

            dictionary_upsert(None, job_id)
        elif task_ref == "haystack.generate_embeddings":
            from ingestion.workers.haystack.tasks import generate_embeddings

            generate_embeddings(None, job_id)


@shared_task(bind=True, name="unstructured.process", queue="unstructured")
def process_document(self, job_id: str, source_path: str) -> str:
    _LOG.info("Processing document", extra={"job_id": job_id, "source": source_path})
    source = Path(source_path)
    with start_span(
        "unstructured.partition",
        attributes={
            "job_id": job_id,
            "source_id": source.name,
            "stage": "unstructured",
            "source_path": str(source_path),
        },
    ) as span:
        try:
            span.set_attribute("source_bytes", source.stat().st_size)
        except OSError:  # pragma: no cover - source removed while processing
            pass
        result = _process_locally(source)
        span.set_attribute("element_count", len(result.get("elements", [])))

    artifacts_dir = _settings.artifacts_dir / job_id / "unstructured"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "elements.json"
    write_elements(output_path, result)

    _registry.update_state(
        job_id,
        state=JobState.STAGED,
        stage="unstructured",
        message=f"Wrote {output_path}",
    )

    app = getattr(self, "app", None) if self is not None else None
    _dispatch("ingestion_engine.elements_to_metadata", job_id, app)

    return str(output_path)
