"""
Helpers for reading and writing artifact files with validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type, TypeVar, Union

from pydantic import ValidationError

from .models import (
    ChunksVectorsV1,
    ElementsMetaV1,
    ElementsV1,
    LlamaIndexManifestV1,
    LlamaIndexNodesV1,
    LlamaIndexReadyMarkerV1,
    LlamaIndexSimilarityV1,
)

ArtifactModel = TypeVar("ArtifactModel", ElementsV1, ElementsMetaV1, ChunksVectorsV1, LlamaIndexNodesV1, LlamaIndexSimilarityV1, LlamaIndexManifestV1, LlamaIndexReadyMarkerV1)


def _model_validate(model: Type[ArtifactModel], data: Any) -> ArtifactModel:
    try:
        if hasattr(model, "model_validate"):
            return model.model_validate(data)  # type: ignore[attr-defined]
        return model.parse_obj(data)  # type: ignore[attr-defined]
    except ValidationError as exc:  # pragma: no cover - validation surface
        raise ValueError(f"{model.__name__} validation failed: {exc}") from exc


def _model_dump(instance: ArtifactModel) -> dict:
    if hasattr(instance, "model_dump"):
        return instance.model_dump(by_alias=True)  # type: ignore[attr-defined]
    return instance.dict(by_alias=True)  # type: ignore[attr-defined]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_elements(path: Path) -> ElementsV1:
    raw = _read_json(path)
    return _model_validate(ElementsV1, raw)


def write_elements(path: Path, data: Union[ElementsV1, dict]) -> ElementsV1:
    model = data if isinstance(data, ElementsV1) else _model_validate(ElementsV1, data)
    _write_json(path, _model_dump(model))
    return model


def load_elements_meta(path: Path) -> ElementsMetaV1:
    raw = _read_json(path)
    return _model_validate(ElementsMetaV1, raw)


def write_elements_meta(path: Path, data: Union[ElementsMetaV1, dict, list]) -> ElementsMetaV1:
    if isinstance(data, ElementsMetaV1):
        model = data
    else:
        payload = data
        if isinstance(data, list):
            payload = {"items": data}
        model = _model_validate(ElementsMetaV1, payload)
    _write_json(path, _model_dump(model))
    return model


def load_embeddings_artifact(path: Path) -> ChunksVectorsV1:
    raw = _read_json(path)
    return _model_validate(ChunksVectorsV1, raw)


def write_embeddings_artifact(path: Path, data: Union[ChunksVectorsV1, dict]) -> ChunksVectorsV1:
    model = data if isinstance(data, ChunksVectorsV1) else _model_validate(ChunksVectorsV1, data)
    _write_json(path, _model_dump(model))
    return model


def write_llamaindex_nodes(path: Path, data: Union[LlamaIndexNodesV1, dict]) -> LlamaIndexNodesV1:
    model = data if isinstance(data, LlamaIndexNodesV1) else _model_validate(LlamaIndexNodesV1, data)
    _write_json(path, _model_dump(model))
    return model


def write_llamaindex_similarity(path: Path, data: Union[LlamaIndexSimilarityV1, dict]) -> LlamaIndexSimilarityV1:
    model = data if isinstance(data, LlamaIndexSimilarityV1) else _model_validate(LlamaIndexSimilarityV1, data)
    _write_json(path, _model_dump(model))
    return model


def write_llamaindex_manifest(path: Path, data: Union[LlamaIndexManifestV1, dict]) -> LlamaIndexManifestV1:
    model = data if isinstance(data, LlamaIndexManifestV1) else _model_validate(LlamaIndexManifestV1, data)
    _write_json(path, _model_dump(model))
    return model


def write_llamaindex_ready_marker(path: Path, data: Union[LlamaIndexReadyMarkerV1, dict]) -> LlamaIndexReadyMarkerV1:
    model = data if isinstance(data, LlamaIndexReadyMarkerV1) else _model_validate(LlamaIndexReadyMarkerV1, data)
    _write_json(path, _model_dump(model))
    return model
