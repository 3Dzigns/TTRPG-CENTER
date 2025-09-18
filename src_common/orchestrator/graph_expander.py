"""
Graph Query Expansion Service

Enhances user queries by leveraging graph structures and relationships to find
related terms, aliases, and cross-referenced concepts for improved retrieval.
"""
from __future__ import annotations

import re
import time
from typing import Dict, Any, List, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from ..ttrpg_logging import get_logger
from .graph_loader import get_graph_loader, GraphSnapshot

logger = get_logger(__name__)


@dataclass
class ExpansionTerm:
    """A term added during query expansion"""
    term: str
    source: str  # 'alias', 'cross_ref', 'graph_relation'
    confidence: float
    original_term: str  # The term that generated this expansion


@dataclass
class ExpandedQuery:
    """Query with expanded terms and metadata"""
    original_query: str
    expanded_query: str
    expansion_terms: List[ExpansionTerm]
    entity_mentions: List[str]
    expansion_strategy: str
    processing_time_ms: float


class GraphQueryExpander:
    """
    Expands queries using graph structures, aliases, and cross-references.

    Strategies:
    - Alias expansion: Find synonyms and alternate names
    - Graph traversal: Find related concepts via graph relationships
    - Cross-reference expansion: Add related game elements
    """

    def __init__(self, environment: str = None):
        self.environment = environment
        self.graph_loader = get_graph_loader(environment)

        # Common TTRPG entity patterns for recognition
        self.entity_patterns = [
            # Classes
            r'\b(?:barbarian|bard|cleric|druid|fighter|monk|paladin|ranger|rogue|sorcerer|wizard)\b',
            # Spell schools
            r'\b(?:abjuration|conjuration|divination|enchantment|evocation|illusion|necromancy|transmutation)\b',
            # Common spells
            r'\b(?:fireball|magic missile|cure light wounds|detect magic|shield|invisibility)\b',
            # Game mechanics
            r'\b(?:spell|feat|skill|attribute|saving throw|armor class|hit points)\b',
        ]

        logger.info(f"GraphQueryExpander initialized for environment: {self.environment}")

    def expand_query(self,
                    query: str,
                    strategy: str = "hybrid",
                    max_expansions: int = 10,
                    min_confidence: float = 0.3) -> ExpandedQuery:
        """
        Expand a query using the specified strategy.

        Args:
            query: Original user query
            strategy: Expansion strategy ('alias', 'graph', 'cross_ref', 'hybrid')
            max_expansions: Maximum number of expansion terms to add
            min_confidence: Minimum confidence score for expansions

        Returns:
            ExpandedQuery with expansion results
        """
        start_time = time.time()

        # Load graph data
        graph = self.graph_loader.load_graph_snapshot()
        if not graph:
            logger.warning("No graph data available for query expansion")
            return ExpandedQuery(
                original_query=query,
                expanded_query=query,
                expansion_terms=[],
                entity_mentions=[],
                expansion_strategy=strategy,
                processing_time_ms=0.0
            )

        # Identify entities in the query
        entity_mentions = self._extract_entities(query)

        # Perform expansion based on strategy
        expansion_terms = []

        if strategy in ["alias", "hybrid"]:
            expansion_terms.extend(self._expand_with_aliases(query, graph, entity_mentions))

        if strategy in ["cross_ref", "hybrid"]:
            expansion_terms.extend(self._expand_with_cross_references(query, graph, entity_mentions))

        if strategy in ["graph", "hybrid"]:
            expansion_terms.extend(self._expand_with_graph_relations(query, graph, entity_mentions))

        # Filter and rank expansions
        expansion_terms = self._filter_and_rank_expansions(
            expansion_terms, max_expansions, min_confidence
        )

        # Build expanded query
        expanded_query = self._build_expanded_query(query, expansion_terms)

        processing_time_ms = (time.time() - start_time) * 1000

        logger.debug(f"Query expanded in {processing_time_ms:.2f}ms: "
                    f"'{query}' -> {len(expansion_terms)} terms added")

        return ExpandedQuery(
            original_query=query,
            expanded_query=expanded_query,
            expansion_terms=expansion_terms,
            entity_mentions=entity_mentions,
            expansion_strategy=strategy,
            processing_time_ms=processing_time_ms
        )

    def _extract_entities(self, query: str) -> List[str]:
        """Extract TTRPG entities from the query"""
        entities = []
        query_lower = query.lower()

        for pattern in self.entity_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            entities.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity.lower() not in seen:
                seen.add(entity.lower())
                unique_entities.append(entity)

        return unique_entities

    def _expand_with_aliases(self,
                           query: str,
                           graph: GraphSnapshot,
                           entities: List[str]) -> List[ExpansionTerm]:
        """Expand query using alias mappings"""
        expansions = []
        query_terms = self._tokenize(query)

        # Check each query term for aliases
        for term in query_terms:
            aliases = graph.expand_aliases(term)
            for alias in aliases:
                if alias.lower() != term.lower():  # Don't include original term
                    expansions.append(ExpansionTerm(
                        term=alias,
                        source="alias",
                        confidence=0.8,  # High confidence for direct aliases
                        original_term=term
                    ))

        # Check entities for aliases
        for entity in entities:
            aliases = graph.expand_aliases(entity)
            for alias in aliases:
                if alias.lower() != entity.lower():
                    expansions.append(ExpansionTerm(
                        term=alias,
                        source="alias",
                        confidence=0.9,  # Very high confidence for entity aliases
                        original_term=entity
                    ))

        return expansions

    def _expand_with_cross_references(self,
                                    query: str,
                                    graph: GraphSnapshot,
                                    entities: List[str]) -> List[ExpansionTerm]:
        """Expand query using cross-references"""
        expansions = []

        # Find cross-references for entities
        for entity in entities:
            cross_refs = graph.find_cross_references(entity)
            for ref in cross_refs:
                # Add related elements with confidence from cross-reference
                if ref.source_element.lower() != entity.lower():
                    expansions.append(ExpansionTerm(
                        term=ref.source_element,
                        source="cross_ref",
                        confidence=ref.confidence,
                        original_term=entity
                    ))

                if ref.target_element.lower() != entity.lower():
                    expansions.append(ExpansionTerm(
                        term=ref.target_element,
                        source="cross_ref",
                        confidence=ref.confidence,
                        original_term=entity
                    ))

        return expansions

    def _expand_with_graph_relations(self,
                                   query: str,
                                   graph: GraphSnapshot,
                                   entities: List[str]) -> List[ExpansionTerm]:
        """Expand query using graph relationship traversal"""
        expansions = []

        # Find nodes related to entities
        for entity in entities:
            # Try to find matching nodes (simple text matching for now)
            matching_nodes = []
            for node_id, node in graph.nodes.items():
                if (entity.lower() in node.title.lower() or
                    (node.content and entity.lower() in node.content.lower())):
                    matching_nodes.append(node)

            # Get related nodes for each match
            for node in matching_nodes[:3]:  # Limit to prevent explosion
                related_nodes = graph.get_related_nodes(node.node_id, max_depth=2)

                for related_node in related_nodes[:5]:  # Limit related nodes
                    # Extract relevant terms from related node titles
                    title_terms = self._extract_key_terms(related_node.title)
                    for term in title_terms:
                        if term.lower() not in query.lower():  # Don't add if already in query
                            expansions.append(ExpansionTerm(
                                term=term,
                                source="graph_relation",
                                confidence=0.6,  # Moderate confidence for graph relations
                                original_term=entity
                            ))

        return expansions

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text (nouns, important words)"""
        if not text:
            return []

        # Simple extraction - split and filter
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter out common stop words and short words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }

        key_terms = []
        for word in words:
            if len(word) > 3 and word not in stop_words:
                key_terms.append(word)

        return key_terms[:3]  # Return top 3 terms

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into meaningful terms"""
        return re.findall(r'\b\w+\b', text.lower())

    def _filter_and_rank_expansions(self,
                                   expansions: List[ExpansionTerm],
                                   max_expansions: int,
                                   min_confidence: float) -> List[ExpansionTerm]:
        """Filter and rank expansion terms"""
        # Remove duplicates (case-insensitive)
        seen_terms = set()
        unique_expansions = []

        for expansion in expansions:
            term_key = expansion.term.lower()
            if term_key not in seen_terms:
                seen_terms.add(term_key)
                unique_expansions.append(expansion)

        # Filter by confidence
        filtered = [exp for exp in unique_expansions if exp.confidence >= min_confidence]

        # Sort by confidence (descending)
        filtered.sort(key=lambda x: x.confidence, reverse=True)

        # Limit to max_expansions
        return filtered[:max_expansions]

    def _build_expanded_query(self, original_query: str, expansions: List[ExpansionTerm]) -> str:
        """Build the expanded query string"""
        if not expansions:
            return original_query

        # For now, simple concatenation with OR logic
        expansion_terms = [exp.term for exp in expansions]
        expanded_query = original_query

        if expansion_terms:
            # Add expansion terms as OR alternatives
            expansion_clause = " OR ".join(f'"{term}"' for term in expansion_terms[:5])
            expanded_query = f"({original_query}) OR ({expansion_clause})"

        return expanded_query

    def get_expansion_stats(self, graph: GraphSnapshot = None) -> Dict[str, Any]:
        """Get statistics about available expansion resources"""
        if not graph:
            graph = self.graph_loader.load_graph_snapshot()

        if not graph:
            return {"available": False}

        return {
            "available": True,
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "cross_references": len(graph.cross_references),
            "aliases": len(graph.aliases),
            "job_id": graph.job_id,
            "created_at": graph.created_at
        }