"""
Pydantic models describing ingestion artifacts.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

try:  # pragma: no cover
    from pydantic import BaseModel, Field, ValidationError, ConfigDict, model_validator
except ImportError:  # pragma: no cover - pydantic v1 fallback
    from pydantic import BaseModel, Field, ValidationError, root_validator
    ConfigDict = None
    model_validator = None
else:  # pragma: no cover
    try:
        from pydantic import root_validator  # type: ignore
    except ImportError:  # pragma: no cover
        root_validator = None


class _ArtifactBase(BaseModel):
    schema_version: str = Field(default="1", alias="schema_version")

    if ConfigDict is not None:  # pragma: no cover
        model_config = ConfigDict(extra="ignore", populate_by_name=True)
    else:  # pragma: no cover
        class Config:
            extra = "ignore"
            allow_population_by_field_name = True


class _EmbeddedModel(BaseModel):
    if ConfigDict is not None:  # pragma: no cover
        model_config = ConfigDict(extra="ignore", populate_by_name=True)
    else:  # pragma: no cover
        class Config:
            extra = "ignore"
            allow_population_by_field_name = True


class ElementContent(_EmbeddedModel):
    text: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    facets: Optional[dict] = None


ElementEntry = Union[str, ElementContent]


class ElementsV1(_ArtifactBase):
    elements: List[ElementEntry]


class ElementMeta(_EmbeddedModel):
    text: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    facets: Optional[dict] = None


class ElementsMetaV1(_ArtifactBase):
    items: List[ElementMeta]

    if model_validator is not None:  # pragma: no cover

        @model_validator(mode="before")
        def _coerce(cls, values):
            if isinstance(values, list):
                return {"items": values}
            if isinstance(values, dict) and "items" not in values and "elements" in values:
                converted = dict(values)
                converted["items"] = converted.pop("elements")
                return converted
            return values

    elif root_validator is not None:  # pragma: no cover

        @root_validator(pre=True)
        def _coerce(cls, values):
            if isinstance(values, list):
                return {"items": values}
            if isinstance(values, dict) and "items" not in values and "elements" in values:
                converted = dict(values)
                converted["items"] = converted.pop("elements")
                return converted
            return values


class EmbeddingChunk(_EmbeddedModel):
    chunk_id: str
    chunk_index: int
    text: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    facets: Optional[dict] = None
    text_hash: Optional[str] = None
    metadata_hash: Optional[str] = None
    vector_hash: Optional[str] = None
    embedding: List[float]


class ChunksVectorsV1(_ArtifactBase):
    model: str
    provider: str
    dimension: int
    chunks: List[EmbeddingChunk]

    if model_validator is not None:  # pragma: no cover

        @model_validator(mode="after")
        def _validate_embeddings(cls, instance):
            dimension = instance.dimension
            if dimension:
                for chunk in instance.chunks or []:
                    if len(chunk.embedding) != dimension:
                        raise ValueError(
                            f"Chunk {chunk.chunk_id} has embedding length {len(chunk.embedding)} "
                            f"(expected {dimension})"
                        )
            return instance

    elif root_validator is not None:  # pragma: no cover

        @root_validator
        def _validate_embeddings(cls, values):
            dimension = values.get("dimension")
            chunks = values.get("chunks") or []
            if dimension:
                for chunk in chunks:
                    if len(chunk.embedding) != dimension:
                        raise ValueError(
                            f"Chunk {chunk.chunk_id} has embedding length {len(chunk.embedding)} "
                            f"(expected {dimension})"
                        )
            return values


class LlamaIndexNode(_EmbeddedModel):
    id: str
    chunk_index: int
    text: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    facets: Optional[dict] = None
    text_hash: Optional[str] = None
    metadata_hash: Optional[str] = None
    vector_hash: Optional[str] = None


class LlamaIndexNodesV1(_ArtifactBase):
    document_id: str
    nodes: List[LlamaIndexNode]


class LlamaIndexSimilarityEntry(_EmbeddedModel):
    chunk_id: str
    score: float


class LlamaIndexSimilarityV1(_ArtifactBase):
    document_id: str
    top_k: int
    entries: Dict[str, List[LlamaIndexSimilarityEntry]]


class LlamaIndexManifestV1(_ArtifactBase):
    job_id: str
    document_id: str
    chunk_count: int
    generated_at: str
    embedding_checksum: Optional[str] = None
    artifacts: dict
    sections: Optional[List[dict]] = None


class LlamaIndexReadyMarkerV1(_ArtifactBase):
    job_id: str
    document_id: str
    generated_at: str
    checksum: Optional[str] = None
    chunks: int


__all__ = [
    "ElementsV1",
    "ElementsMetaV1",
    "ChunksVectorsV1",
    "LlamaIndexNodesV1",
    "LlamaIndexSimilarityV1",
    "LlamaIndexManifestV1",
    "LlamaIndexReadyMarkerV1",
    "ValidationError",
]
