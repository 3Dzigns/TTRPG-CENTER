# src_common/admin/dictionary_models.py
"""
Data models for Dictionary Management Service
Shared between AdminDictionaryService and MongoDictionaryAdapter
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class DictionaryTerm:
    """Dictionary term definition"""
    term: str
    definition: str
    category: str  # 'rule', 'concept', 'procedure', 'entity'
    environment: str
    source: str
    page_reference: Optional[str] = None
    created_at: float = None
    updated_at: float = None
    version: int = 1
    tags: List[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.tags is None:
            self.tags = []


@dataclass
class DictionaryStats:
    """Dictionary statistics"""
    total_terms: int
    categories: Dict[str, int]
    sources: Dict[str, int]
    recent_updates: int
    environment: str