"""
Graph-Aware Result Ranking and Query Processing

Provides advanced ranking and processing capabilities that leverage graph structures
for improved result relevance and relationship-aware scoring.
"""
from __future__ import annotations

import re
import time
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import math

from ..ttrpg_logging import get_logger
from .graph_loader import get_graph_loader, GraphSnapshot, GraphNode, CrossReference

logger = get_logger(__name__)


@dataclass
class RankedResult:
    """A search result with graph-enhanced scoring"""
    chunk_id: str
    text: str
    source: str
    base_score: float
    graph_score: float
    combined_score: float
    metadata: Dict[str, Any]
    graph_relationships: List[Dict[str, Any]]


@dataclass
class GraphRankingContext:
    """Context for graph-aware ranking operations"""
    query: str
    entity_mentions: List[str]
    expansion_terms: List[str]
    graph_snapshot: Optional[GraphSnapshot]
    ranking_strategy: str = "hybrid"  # vector, graph, hybrid
    graph_weight: float = 0.3  # Weight for graph score vs vector score


class GraphQueryProcessor:
    """
    Processes queries to extract entities and relationships for graph-aware retrieval.
    """

    def __init__(self, environment: str = None):
        self.environment = environment
        self.graph_loader = get_graph_loader(environment)

        # TTRPG-specific entity patterns for recognition
        self.entity_patterns = {
            'classes': r'\b(?:barbarian|bard|cleric|druid|fighter|monk|paladin|ranger|rogue|sorcerer|wizard)\b',
            'spells': r'\b(?:fireball|magic missile|cure light wounds|detect magic|shield|invisibility|lightning bolt)\b',
            'schools': r'\b(?:abjuration|conjuration|divination|enchantment|evocation|illusion|necromancy|transmutation)\b',
            'mechanics': r'\b(?:spell|feat|skill|attribute|saving throw|armor class|hit points|damage|attack)\b',
            'equipment': r'\b(?:sword|armor|shield|staff|wand|potion|scroll|ring)\b',
            'abilities': r'\b(?:strength|dexterity|constitution|intelligence|wisdom|charisma)\b'
        }

        logger.info(f"GraphQueryProcessor initialized for environment: {self.environment}")

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a query to extract entities, relationships, and context.

        Args:
            query: User query string

        Returns:
            Dictionary with extracted query components
        """
        start_time = time.time()

        # Extract entities by category
        entities_by_type = self._extract_entities_by_type(query)
        all_entities = []
        for entity_list in entities_by_type.values():
            all_entities.extend(entity_list)

        # Identify query patterns
        query_patterns = self._identify_query_patterns(query)

        # Find relationships between mentioned entities
        relationships = self._find_entity_relationships(all_entities)

        # Determine recommended retrieval strategy
        strategy = self._recommend_strategy(query, entities_by_type, query_patterns)

        processing_time_ms = (time.time() - start_time) * 1000

        return {
            "original_query": query,
            "entities_by_type": entities_by_type,
            "all_entities": all_entities,
            "query_patterns": query_patterns,
            "entity_relationships": relationships,
            "recommended_strategy": strategy,
            "processing_time_ms": processing_time_ms
        }

    def _extract_entities_by_type(self, query: str) -> Dict[str, List[str]]:
        """Extract entities from query, organized by type"""
        entities_by_type = {}
        query_lower = query.lower()

        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            if matches:
                # Remove duplicates while preserving order
                unique_matches = []
                seen = set()
                for match in matches:
                    if match.lower() not in seen:
                        seen.add(match.lower())
                        unique_matches.append(match)
                entities_by_type[entity_type] = unique_matches

        return entities_by_type

    def _identify_query_patterns(self, query: str) -> List[str]:
        """Identify common query patterns for strategy selection"""
        patterns = []
        query_lower = query.lower()

        # Comparison patterns
        if any(word in query_lower for word in ['vs', 'versus', 'compare', 'difference', 'better']):
            patterns.append('comparison')

        # Relationship patterns
        if any(word in query_lower for word in ['with', 'using', 'combine', 'interaction']):
            patterns.append('relationship')

        # List/enumeration patterns
        if any(word in query_lower for word in ['list', 'all', 'every', 'which']):
            patterns.append('enumeration')

        # How-to patterns
        if any(phrase in query_lower for phrase in ['how to', 'how do', 'steps', 'guide']):
            patterns.append('procedural')

        # Definition patterns
        if any(phrase in query_lower for phrase in ['what is', 'what are', 'define', 'explain']):
            patterns.append('definition')

        return patterns

    def _find_entity_relationships(self, entities: List[str]) -> List[Dict[str, Any]]:
        """Find relationships between mentioned entities using graph data"""
        if len(entities) < 2:
            return []

        relationships = []
        graph = self.graph_loader.load_graph_snapshot()
        if not graph:
            return relationships

        # Check cross-references for entity pairs
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                refs = self._find_cross_references_between_entities(entity1, entity2, graph)
                if refs:
                    relationships.append({
                        "entity1": entity1,
                        "entity2": entity2,
                        "cross_references": refs,
                        "relationship_strength": max(ref.confidence for ref in refs)
                    })

        return relationships

    def _find_cross_references_between_entities(self, entity1: str, entity2: str,
                                              graph: GraphSnapshot) -> List[CrossReference]:
        """Find cross-references between two specific entities"""
        relevant_refs = []

        for ref in graph.cross_references:
            e1_lower, e2_lower = entity1.lower(), entity2.lower()
            source_lower, target_lower = ref.source_element.lower(), ref.target_element.lower()

            # Check if both entities are mentioned in this cross-reference
            if ((e1_lower in source_lower and e2_lower in target_lower) or
                (e2_lower in source_lower and e1_lower in target_lower) or
                (e1_lower in source_lower and e2_lower in ref.context.lower()) or
                (e2_lower in source_lower and e1_lower in ref.context.lower())):
                relevant_refs.append(ref)

        return relevant_refs

    def _recommend_strategy(self, query: str, entities_by_type: Dict[str, List[str]],
                          patterns: List[str]) -> str:
        """Recommend graph expansion strategy based on query analysis"""
        # Admin or code queries - no expansion
        if any(word in query.lower() for word in ['admin', 'status', 'health', 'error', 'python']):
            return "none"

        # Multiple entities suggest cross-reference expansion
        total_entities = sum(len(entities) for entities in entities_by_type.values())
        if total_entities >= 2 and 'comparison' in patterns:
            return "cross_ref"

        # Single entity with procedural pattern suggests alias expansion
        if total_entities == 1 and 'procedural' in patterns:
            return "alias"

        # Complex patterns with multiple entity types suggest graph traversal
        if len(entities_by_type) >= 2 or 'relationship' in patterns:
            return "graph"

        # Default to hybrid for most queries
        return "hybrid"


class GraphAwareRanker:
    """
    Provides graph-aware ranking for search results, incorporating relationship
    information and entity context for improved relevance scoring.
    """

    def __init__(self, environment: str = None):
        self.environment = environment
        self.graph_loader = get_graph_loader(environment)
        self.query_processor = GraphQueryProcessor(environment)

        logger.info(f"GraphAwareRanker initialized for environment: {self.environment}")

    def rank_results(self,
                    query: str,
                    results: List[Dict[str, Any]],
                    graph_expansion: Optional[Dict[str, Any]] = None,
                    ranking_strategy: str = "hybrid",
                    graph_weight: float = 0.3) -> List[RankedResult]:
        """
        Rank search results using graph-aware scoring.

        Args:
            query: Original user query
            results: List of search results to rank
            graph_expansion: Graph expansion metadata from query planning
            ranking_strategy: Ranking strategy (vector, graph, hybrid)
            graph_weight: Weight for graph score component (0.0 to 1.0)

        Returns:
            List of ranked results with graph-enhanced scoring
        """
        if not results:
            return []

        start_time = time.time()

        # Process query for entity extraction
        query_context = self.query_processor.process_query(query)

        # Load graph data
        graph = self.graph_loader.load_graph_snapshot()

        # Create ranking context
        expansion_terms = []
        if graph_expansion and graph_expansion.get("expansion_terms"):
            expansion_terms = [term["term"] for term in graph_expansion["expansion_terms"]]

        ranking_context = GraphRankingContext(
            query=query,
            entity_mentions=query_context.get("all_entities", []),
            expansion_terms=expansion_terms,
            graph_snapshot=graph,
            ranking_strategy=ranking_strategy,
            graph_weight=graph_weight
        )

        # Score and rank results
        ranked_results = []
        for result in results:
            ranked_result = self._score_result(result, ranking_context)
            ranked_results.append(ranked_result)

        # Sort by combined score
        ranked_results.sort(key=lambda r: r.combined_score, reverse=True)

        processing_time_ms = (time.time() - start_time) * 1000
        logger.debug(f"Ranked {len(results)} results in {processing_time_ms:.2f}ms")

        return ranked_results

    def _score_result(self, result: Dict[str, Any], context: GraphRankingContext) -> RankedResult:
        """Score a single result using graph-aware metrics"""
        text = result.get("text", "")
        base_score = result.get("score", 0.0)

        # Calculate graph score
        graph_score = self._calculate_graph_score(text, result.get("metadata", {}), context)

        # Combine scores based on strategy
        if context.ranking_strategy == "vector":
            combined_score = base_score
        elif context.ranking_strategy == "graph":
            combined_score = graph_score
        else:  # hybrid
            combined_score = (1 - context.graph_weight) * base_score + context.graph_weight * graph_score

        # Find graph relationships for this result
        relationships = self._find_result_relationships(text, context)

        return RankedResult(
            chunk_id=result.get("id", ""),
            text=text,
            source=result.get("source", ""),
            base_score=base_score,
            graph_score=graph_score,
            combined_score=combined_score,
            metadata=result.get("metadata", {}),
            graph_relationships=relationships
        )

    def _calculate_graph_score(self, text: str, metadata: Dict[str, Any],
                             context: GraphRankingContext) -> float:
        """Calculate graph-based relevance score"""
        if not context.graph_snapshot:
            return 0.0

        score = 0.0
        text_lower = text.lower()

        # Entity mention score
        entity_mentions = 0
        for entity in context.entity_mentions:
            if entity.lower() in text_lower:
                entity_mentions += 1
                score += 0.3

        # Expansion term score
        expansion_hits = 0
        for term in context.expansion_terms:
            if term.lower() in text_lower:
                expansion_hits += 1
                score += 0.2

        # Cross-reference bonus
        cross_ref_bonus = self._calculate_cross_reference_bonus(text_lower, context)
        score += cross_ref_bonus

        # Normalize score (0 to 1 range)
        max_possible = len(context.entity_mentions) * 0.3 + len(context.expansion_terms) * 0.2 + 0.5
        if max_possible > 0:
            score = min(score / max_possible, 1.0)

        return score

    def _calculate_cross_reference_bonus(self, text_lower: str, context: GraphRankingContext) -> float:
        """Calculate bonus score based on cross-reference density"""
        if not context.graph_snapshot or len(context.entity_mentions) < 2:
            return 0.0

        cross_ref_score = 0.0

        # Check for co-occurrence of entities that have cross-references
        for ref in context.graph_snapshot.cross_references:
            source_in_text = ref.source_element.lower() in text_lower
            target_in_text = ref.target_element.lower() in text_lower

            # Bonus for text that mentions both sides of a cross-reference
            if source_in_text and target_in_text:
                cross_ref_score += ref.confidence * 0.5

        return min(cross_ref_score, 0.5)  # Cap the bonus

    def _find_result_relationships(self, text: str, context: GraphRankingContext) -> List[Dict[str, Any]]:
        """Find graph relationships relevant to this result"""
        relationships = []

        if not context.graph_snapshot:
            return relationships

        text_lower = text.lower()

        # Find cross-references mentioned in the text
        for ref in context.graph_snapshot.cross_references:
            source_mentioned = ref.source_element.lower() in text_lower
            target_mentioned = ref.target_element.lower() in text_lower

            if source_mentioned or target_mentioned:
                relationships.append({
                    "type": "cross_reference",
                    "source": ref.source_element,
                    "target": ref.target_element,
                    "ref_type": ref.ref_type,
                    "confidence": ref.confidence,
                    "context": ref.context,
                    "relevance": "high" if source_mentioned and target_mentioned else "medium"
                })

        return relationships


# Convenience functions for easy integration
def rank_with_graph(query: str,
                   results: List[Dict[str, Any]],
                   graph_expansion: Optional[Dict[str, Any]] = None,
                   environment: str = None) -> List[RankedResult]:
    """
    Convenience function for graph-aware result ranking.

    Args:
        query: User query
        results: Search results to rank
        graph_expansion: Graph expansion metadata
        environment: Environment name

    Returns:
        List of ranked results
    """
    ranker = GraphAwareRanker(environment)
    return ranker.rank_results(query, results, graph_expansion)


def process_query_for_graph(query: str, environment: str = None) -> Dict[str, Any]:
    """
    Convenience function for query processing.

    Args:
        query: User query
        environment: Environment name

    Returns:
        Query processing results
    """
    processor = GraphQueryProcessor(environment)
    return processor.process_query(query)