"""
Signal Extractors for Hybrid Reranking

Implements specialized signal extractors for:
- Vector similarity signals
- Graph relationship signals
- Content feature signals
- Domain-specific TTRPG signals

Each extractor focuses on a specific signal type and returns normalized scores.
"""
from __future__ import annotations

import re
import math
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class BaseSignalExtractor(ABC):
    """Base class for all signal extractors."""

    def __init__(self, environment: str = "dev"):
        self.environment = environment

    @abstractmethod
    def extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        context: Optional[Any] = None
    ) -> Dict[str, float]:
        """Extract signals for a query-result pair."""
        pass


class VectorSignalExtractor(BaseSignalExtractor):
    """Extract vector similarity based signals."""

    def extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        classification: Optional[Any] = None
    ) -> Dict[str, float]:
        """
        Extract vector similarity signals.

        Args:
            query: User query
            result: Search result with vector scores
            classification: Query classification (optional)

        Returns:
            Dictionary with vector similarity signals
        """
        signals = {}

        # Primary vector similarity (from retrieval)
        similarity = result.get('score', 0.0)
        signals['similarity'] = self._normalize_score(similarity)

        # Semantic similarity (enhanced)
        content = result.get('content', '')
        semantic_score = self._compute_semantic_similarity(query, content)
        signals['semantic'] = semantic_score

        # Query-specific vector adjustments
        if classification:
            intent = getattr(classification, 'intent', 'unknown')
            if intent == 'fact_lookup':
                # Boost exact matches for fact lookup
                signals['similarity'] *= 1.2
            elif intent == 'creative_write':
                # Emphasize semantic over exact for creative queries
                signals['semantic'] *= 1.3

        return self._normalize_signals(signals)

    def _compute_semantic_similarity(self, query: str, content: str) -> float:
        """Compute enhanced semantic similarity."""
        if not query or not content:
            return 0.0

        # Simple semantic similarity based on word overlap and order
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        # Jaccard similarity with word frequency weighting
        intersection = query_words & content_words
        union = query_words | content_words

        jaccard = len(intersection) / len(union) if union else 0.0

        # Boost for exact phrase matches
        phrase_boost = 1.0
        if query.lower() in content.lower():
            phrase_boost = 1.5

        return min(1.0, jaccard * phrase_boost)

    def _normalize_score(self, score: float) -> float:
        """Normalize score to [0, 1] range."""
        return max(0.0, min(1.0, score))

    def _normalize_signals(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Ensure all signals are in [0, 1] range."""
        return {k: self._normalize_score(v) for k, v in signals.items()}


class GraphSignalExtractor(BaseSignalExtractor):
    """Extract graph relationship based signals."""

    def __init__(self, environment: str = "dev"):
        super().__init__(environment)

        # Try to import graph components
        try:
            from .graph_loader import GraphLoader
            from .graph_ranker import GraphAwareRanker

            self.graph_loader = GraphLoader(environment)
            self.graph_ranker = GraphAwareRanker(environment)
            self.graph_available = True

        except ImportError:
            logger.warning("Graph components not available for signal extraction")
            self.graph_loader = None
            self.graph_ranker = None
            self.graph_available = False

    def extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        query_plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Extract graph relationship signals.

        Args:
            query: User query
            result: Search result
            query_plan: Query plan with graph expansion (optional)

        Returns:
            Dictionary with graph relationship signals
        """
        signals = {
            'relevance': 0.0,
            'relationships': 0.0,
            'cross_refs': 0.0
        }

        if not self.graph_available:
            return signals

        try:
            # Extract graph expansion from query plan
            graph_expansion = None
            if query_plan:
                graph_expansion = query_plan.get('graph_expansion', {})

            # Graph relevance based on relationship proximity
            signals['relevance'] = self._compute_graph_relevance(
                result, graph_expansion
            )

            # Relationship strength signals
            signals['relationships'] = self._compute_relationship_score(
                query, result, graph_expansion
            )

            # Cross-reference boost
            signals['cross_refs'] = self._compute_cross_reference_boost(
                result, graph_expansion
            )

        except Exception as e:
            logger.warning(f"Error extracting graph signals: {e}")

        return self._normalize_signals(signals)

    def _compute_graph_relevance(
        self,
        result: Dict[str, Any],
        graph_expansion: Optional[Dict[str, Any]]
    ) -> float:
        """Compute relevance based on graph proximity."""
        if not graph_expansion:
            return 0.5  # Neutral score

        # Check if result appears in expanded entities
        expanded_entities = graph_expansion.get('expanded_entities', [])
        result_content = result.get('content', '').lower()

        relevance_score = 0.0
        for entity in expanded_entities:
            entity_name = entity.get('name', '').lower()
            confidence = entity.get('confidence', 0.0)

            if entity_name and entity_name in result_content:
                relevance_score += confidence

        return min(1.0, relevance_score)

    def _compute_relationship_score(
        self,
        query: str,
        result: Dict[str, Any],
        graph_expansion: Optional[Dict[str, Any]]
    ) -> float:
        """Compute score based on relationship strength."""
        if not graph_expansion:
            return 0.5

        relationships = graph_expansion.get('relationships', [])
        if not relationships:
            return 0.5

        # Score based on relationship types and strengths
        relationship_score = 0.0
        result_content = result.get('content', '').lower()

        for rel in relationships:
            rel_type = rel.get('type', '')
            strength = rel.get('strength', 0.0)
            source = rel.get('source', '').lower()
            target = rel.get('target', '').lower()

            # Check if relationship entities appear in result
            if source in result_content or target in result_content:
                relationship_score += strength * self._get_relationship_weight(rel_type)

        return min(1.0, relationship_score)

    def _compute_cross_reference_boost(
        self,
        result: Dict[str, Any],
        graph_expansion: Optional[Dict[str, Any]]
    ) -> float:
        """Compute boost based on cross-references."""
        if not graph_expansion:
            return 0.0

        cross_refs = graph_expansion.get('cross_references', [])
        if not cross_refs:
            return 0.0

        result_content = result.get('content', '').lower()
        boost_score = 0.0

        for cross_ref in cross_refs:
            ref_text = cross_ref.get('text', '').lower()
            confidence = cross_ref.get('confidence', 0.0)

            if ref_text and ref_text in result_content:
                boost_score += confidence

        return min(1.0, boost_score)

    def _get_relationship_weight(self, rel_type: str) -> float:
        """Get weight for relationship type."""
        weights = {
            'is_part_of': 0.9,
            'references': 0.7,
            'similar_to': 0.6,
            'related_to': 0.5,
            'mentions': 0.3
        }
        return weights.get(rel_type, 0.5)

    def _normalize_signals(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Ensure all signals are in [0, 1] range."""
        return {k: max(0.0, min(1.0, v)) for k, v in signals.items()}


class ContentSignalExtractor(BaseSignalExtractor):
    """Extract content feature based signals."""

    def extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        classification: Optional[Any] = None
    ) -> Dict[str, float]:
        """
        Extract content quality and feature signals.

        Args:
            query: User query
            result: Search result
            classification: Query classification (optional)

        Returns:
            Dictionary with content feature signals
        """
        content = result.get('content', '')
        metadata = result.get('metadata', {})

        signals = {
            'quality': self._compute_content_quality(content, metadata),
            'readability': self._compute_readability_score(content),
            'length_penalty': self._compute_length_penalty(content, classification),
            'structure': self._compute_structure_score(content, metadata)
        }

        return self._normalize_signals(signals)

    def _compute_content_quality(self, content: str, metadata: Dict[str, Any]) -> float:
        """Compute overall content quality score."""
        if not content:
            return 0.0

        quality_score = 0.5  # Base score

        # Length appropriateness (sweet spot around 200-800 chars)
        length = len(content)
        if 200 <= length <= 800:
            quality_score += 0.2
        elif length < 50:
            quality_score -= 0.3

        # Sentence structure quality
        sentences = content.split('.')
        if len(sentences) > 1:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if 10 <= avg_sentence_length <= 25:  # Good sentence length
                quality_score += 0.1

        # Punctuation and formatting
        if re.search(r'[.!?]', content):
            quality_score += 0.1

        # Source authority (from metadata)
        source = metadata.get('source', '').lower()
        if any(authoritative in source for authoritative in ['phb', 'dmg', 'official']):
            quality_score += 0.2

        return min(1.0, quality_score)

    def _compute_readability_score(self, content: str) -> float:
        """Compute readability score using simple heuristics."""
        if not content:
            return 0.0

        words = content.split()
        sentences = len(re.split(r'[.!?]+', content))

        if not words or sentences == 0:
            return 0.0

        # Simple readability approximation
        avg_words_per_sentence = len(words) / sentences
        avg_syllables = sum(self._count_syllables(word) for word in words) / len(words)

        # Flesch-like score (simplified)
        readability = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables)

        # Normalize to [0, 1]
        normalized = max(0, min(100, readability)) / 100.0

        return normalized

    def _compute_length_penalty(self, content: str, classification: Optional[Any]) -> float:
        """Compute penalty for inappropriate content length."""
        if not content:
            return 1.0  # Maximum penalty

        length = len(content)

        # Adjust ideal length based on query type
        ideal_min, ideal_max = 100, 500  # Default

        if classification:
            intent = getattr(classification, 'intent', 'unknown')
            if intent == 'fact_lookup':
                ideal_min, ideal_max = 50, 200
            elif intent == 'procedural_howto':
                ideal_min, ideal_max = 200, 1000
            elif intent == 'summarize':
                ideal_min, ideal_max = 300, 800

        # Compute penalty
        if ideal_min <= length <= ideal_max:
            return 0.0  # No penalty
        elif length < ideal_min:
            return (ideal_min - length) / ideal_min
        else:  # length > ideal_max
            return min(1.0, (length - ideal_max) / ideal_max)

    def _compute_structure_score(self, content: str, metadata: Dict[str, Any]) -> float:
        """Compute score based on content structure."""
        if not content:
            return 0.0

        structure_score = 0.5  # Base score

        # Headers and formatting
        if re.search(r'^#+\s', content, re.MULTILINE):  # Markdown headers
            structure_score += 0.2

        # Lists and organization
        if re.search(r'^\s*[-*+]\s', content, re.MULTILINE):  # Lists
            structure_score += 0.1

        # Tables or structured data
        if '|' in content and content.count('|') > 4:  # Table-like
            structure_score += 0.1

        # Page or section references
        if metadata.get('page') or re.search(r'p\.\s*\d+|page\s*\d+', content, re.IGNORECASE):
            structure_score += 0.1

        return min(1.0, structure_score)

    def _count_syllables(self, word: str) -> int:
        """Simple syllable counting heuristic."""
        word = word.lower()
        vowels = 'aeiouy'
        syllables = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllables += 1
            prev_was_vowel = is_vowel

        # Adjust for silent e
        if word.endswith('e') and syllables > 1:
            syllables -= 1

        return max(1, syllables)

    def _normalize_signals(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Ensure all signals are in [0, 1] range."""
        return {k: max(0.0, min(1.0, v)) for k, v in signals.items()}


class DomainSignalExtractor(BaseSignalExtractor):
    """Extract TTRPG domain-specific signals."""

    def __init__(self, environment: str = "dev"):
        super().__init__(environment)
        self._load_domain_patterns()

    def _load_domain_patterns(self):
        """Load TTRPG-specific patterns and entities."""
        # TTRPG entity patterns
        self.entity_patterns = {
            'classes': r'\b(?:fighter|wizard|rogue|cleric|barbarian|bard|druid|monk|paladin|ranger|sorcerer|warlock)\b',
            'spells': r'\b(?:fireball|magic missile|cure wounds|shield|healing word|thunderwave)\b',
            'races': r'\b(?:human|elf|dwarf|halfling|dragonborn|gnome|half-elf|half-orc|tiefling)\b',
            'abilities': r'\b(?:strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)\b',
            'mechanics': r'\b(?:advantage|disadvantage|proficiency|saving throw|armor class|hit points|ac|hp)\b'
        }

        # Compile patterns
        self.compiled_patterns = {
            category: re.compile(pattern, re.IGNORECASE)
            for category, pattern in self.entity_patterns.items()
        }

        # Authority sources
        self.authoritative_sources = {
            'phb': 1.0,  # Player's Handbook
            'dmg': 0.9,  # Dungeon Master's Guide
            'mm': 0.8,   # Monster Manual
            'xgte': 0.8, # Xanathar's Guide
            'tce': 0.8,  # Tasha's Cauldron
            'official': 0.9,
            'homebrew': 0.3,
            'unofficial': 0.2
        }

    def extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        classification: Optional[Any] = None
    ) -> Dict[str, float]:
        """
        Extract TTRPG domain-specific signals.

        Args:
            query: User query
            result: Search result
            classification: Query classification (optional)

        Returns:
            Dictionary with domain-specific signals
        """
        content = result.get('content', '')
        metadata = result.get('metadata', {})

        signals = {
            'entity_match': self._compute_entity_match_score(query, content),
            'mechanics': self._compute_mechanics_relevance(query, content, classification),
            'authority': self._compute_authority_score(metadata)
        }

        return self._normalize_signals(signals)

    def _compute_entity_match_score(self, query: str, content: str) -> float:
        """Compute score based on TTRPG entity matches."""
        if not query or not content:
            return 0.0

        query_lower = query.lower()
        content_lower = content.lower()

        total_score = 0.0
        total_weight = 0.0

        for category, pattern in self.compiled_patterns.items():
            # Find entities in query
            query_entities = set(pattern.findall(query_lower))

            if not query_entities:
                continue

            # Find entities in content
            content_entities = set(pattern.findall(content_lower))

            # Calculate overlap
            overlap = query_entities & content_entities
            if overlap:
                # Weight different entity types
                category_weight = self._get_entity_weight(category)
                overlap_ratio = len(overlap) / len(query_entities)

                total_score += overlap_ratio * category_weight
                total_weight += category_weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _compute_mechanics_relevance(
        self,
        query: str,
        content: str,
        classification: Optional[Any]
    ) -> float:
        """Compute relevance to game mechanics."""
        if not content:
            return 0.0

        mechanics_score = 0.0

        # Check for game mechanics keywords
        mechanics_pattern = self.compiled_patterns['mechanics']
        mechanics_matches = len(mechanics_pattern.findall(content.lower()))

        if mechanics_matches > 0:
            mechanics_score += min(1.0, mechanics_matches * 0.2)

        # Check for dice notation
        dice_pattern = re.compile(r'\bd\d+\b|\d+d\d+|\d+d\d+[+-]\d+', re.IGNORECASE)
        dice_matches = len(dice_pattern.findall(content))

        if dice_matches > 0:
            mechanics_score += min(0.3, dice_matches * 0.1)

        # Check for numeric values (AC, HP, etc.)
        numeric_pattern = re.compile(r'\b(?:ac|armor class)\s*\d+|\b(?:hp|hit points)\s*\d+', re.IGNORECASE)
        numeric_matches = len(numeric_pattern.findall(content))

        if numeric_matches > 0:
            mechanics_score += min(0.2, numeric_matches * 0.1)

        # Boost for rules-related queries
        if classification:
            domain = getattr(classification, 'domain', 'general')
            if domain == 'ttrpg_rules':
                mechanics_score *= 1.5

        return min(1.0, mechanics_score)

    def _compute_authority_score(self, metadata: Dict[str, Any]) -> float:
        """Compute authority score based on source."""
        source = metadata.get('source', '').lower()

        # Check against authoritative sources
        for source_key, score in self.authoritative_sources.items():
            if source_key in source:
                return score

        # Default score for unknown sources
        return 0.5

    def _get_entity_weight(self, category: str) -> float:
        """Get weight for different entity categories."""
        weights = {
            'classes': 0.9,
            'spells': 0.8,
            'races': 0.7,
            'abilities': 0.6,
            'mechanics': 0.8
        }
        return weights.get(category, 0.5)

    def _normalize_signals(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Ensure all signals are in [0, 1] range."""
        return {k: max(0.0, min(1.0, v)) for k, v in signals.items()}