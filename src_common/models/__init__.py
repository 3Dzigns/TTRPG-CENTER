# src_common/models/__init__.py
"""
Unified data models for TTRPG Center.
This package re-exports the legacy SQLModel definitions found in
``src_common/models.py`` so callers can reliably import
``src_common.models`` regardless of how ``src_common`` is added to
``PYTHONPATH``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import List

from .unified_dictionary import UnifiedDictionaryTerm, UnifiedDictionaryStats

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "models.py"
_spec = importlib.util.spec_from_file_location("_legacy_models", _LEGACY_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - defensive fallback
    raise ImportError(f"Unable to load legacy models from {_LEGACY_PATH}")
_legacy_models = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy_models)

LEGACY_EXPORTS: List[str] = getattr(_legacy_models, '__all__', [])
for _name in LEGACY_EXPORTS:
    globals()[_name] = getattr(_legacy_models, _name)

__all__ = [
    'UnifiedDictionaryTerm',
    'UnifiedDictionaryStats',
    *LEGACY_EXPORTS,
]
