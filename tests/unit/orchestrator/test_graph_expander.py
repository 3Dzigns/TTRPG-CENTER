"""
Unit tests for graph query expansion service.
"""
import pytest
from unittest.mock import patch, MagicMock

from src_common.orchestrator.graph_expander import (
    GraphQueryExpander, ExpansionTerm, ExpandedQuery
)
from src_common.orchestrator.graph_loader import GraphSnapshot, GraphNode, CrossReference


class TestExpansionTerm:
    """Test ExpansionTerm data structure."""

    def test_expansion_term_creation(self):
        """Test creating an expansion term."""
        term = ExpansionTerm(
            term="mage",
            source="alias",
            confidence=0.8,
            original_term="wizard"
        )

        assert term.term == "mage"
        assert term.source == "alias"
        assert term.confidence == 0.8
        assert term.original_term == "wizard"


class TestExpandedQuery:
    """Test ExpandedQuery data structure."""

    def test_expanded_query_creation(self):
        """Test creating an expanded query."""
        expansion_terms = [
            ExpansionTerm("mage", "alias", 0.8, "wizard"),
            ExpansionTerm("spell", "cross_ref", 0.9, "magic")
        ]

        expanded = ExpandedQuery(
            original_query="wizard spells",
            expanded_query="(wizard spells) OR (\"mage\" OR \"spell\")",
            expansion_terms=expansion_terms,
            entity_mentions=["wizard"],
            expansion_strategy="hybrid",
            processing_time_ms=25.5
        )

        assert expanded.original_query == "wizard spells"
        assert "mage" in expanded.expanded_query
        assert len(expanded.expansion_terms) == 2
        assert expanded.entity_mentions == ["wizard"]
        assert expanded.expansion_strategy == "hybrid"
        assert expanded.processing_time_ms == 25.5


class TestGraphQueryExpander:
    """Test GraphQueryExpander functionality."""

    @pytest.fixture
    def mock_graph_snapshot(self):
        """Create mock graph snapshot for testing."""
        nodes = {
            "wizard_node": GraphNode("wizard_node", "entity", "Wizard Class",
                                   content="A spellcasting class that uses intelligence"),
            "spell_node": GraphNode("spell_node", "entity", "Spells",
                                  content="Magical effects cast by spellcasters")
        }

        cross_refs = [
            CrossReference("ref1", "wizard", "fireball", "class_to_spell", 0.9,
                         "Wizards can learn fireball"),
            CrossReference("ref2", "wizard", "intelligence", "class_to_attribute", 0.8,
                         "Wizards use intelligence for spellcasting")
        ]

        aliases = {
            "wizard": {"mage", "spellcaster"},
            "fireball": {"fire spell", "evocation spell"}
        }

        return GraphSnapshot(
            job_id="test_job",
            created_at=1234567890.0,
            nodes=nodes,
            edges=[],
            cross_references=cross_refs,
            aliases=aliases
        )

    @pytest.fixture
    def mock_expander(self, mock_graph_snapshot):
        """Create expander with mocked graph loader."""
        expander = GraphQueryExpander("test")
        expander.graph_loader.load_graph_snapshot = MagicMock(return_value=mock_graph_snapshot)
        return expander

    def test_expander_initialization(self):
        """Test expander initialization."""
        expander = GraphQueryExpander("test")
        assert expander.environment == "test"
        assert len(expander.entity_patterns) > 0

    def test_extract_entities(self, mock_expander):
        """Test entity extraction from queries."""
        entities = mock_expander._extract_entities("What spells can a wizard cast?")
        assert "wizard" in entities
        assert "spell" in entities

        # Test multiple entities
        entities = mock_expander._extract_entities("Compare wizard and sorcerer spells")
        assert "wizard" in entities
        assert "sorcerer" in entities
        assert "spell" in entities

    def test_expand_with_aliases(self, mock_expander, mock_graph_snapshot):
        """Test alias-based expansion."""
        query = "wizard spells"
        entities = ["wizard"]

        expansions = mock_expander._expand_with_aliases(query, mock_graph_snapshot, entities)

        # Should find aliases for wizard
        expansion_terms = [exp.term for exp in expansions]
        assert "mage" in expansion_terms
        assert "spellcaster" in expansion_terms

        # Check expansion metadata
        wizard_expansion = next(exp for exp in expansions if exp.term == "mage")
        assert wizard_expansion.source == "alias"
        assert wizard_expansion.confidence == 0.9  # High confidence for entity aliases
        assert wizard_expansion.original_term == "wizard"

    def test_expand_with_cross_references(self, mock_expander, mock_graph_snapshot):
        """Test cross-reference based expansion."""
        query = "wizard abilities"
        entities = ["wizard"]

        expansions = mock_expander._expand_with_cross_references(query, mock_graph_snapshot, entities)

        # Should find cross-referenced terms
        expansion_terms = [exp.term for exp in expansions]
        assert "fireball" in expansion_terms
        assert "intelligence" in expansion_terms

        # Check cross-reference metadata
        fireball_expansion = next(exp for exp in expansions if exp.term == "fireball")
        assert fireball_expansion.source == "cross_ref"
        assert fireball_expansion.confidence == 0.9
        assert fireball_expansion.original_term == "wizard"

    def test_expand_with_graph_relations(self, mock_expander, mock_graph_snapshot):
        """Test graph relation based expansion."""
        query = "wizard magic"
        entities = ["wizard"]

        # Mock related nodes to return spell node
        mock_graph_snapshot.get_related_nodes = MagicMock(
            return_value=[mock_graph_snapshot.nodes["spell_node"]]
        )

        expansions = mock_expander._expand_with_graph_relations(query, mock_graph_snapshot, entities)

        # Should extract key terms from related nodes
        expansion_terms = [exp.term for exp in expansions]
        # The spell node title "Spells" should contribute "spells" as a term
        assert any("spell" in term.lower() for term in expansion_terms)

    def test_expand_query_alias_strategy(self, mock_expander):
        """Test query expansion with alias strategy."""
        result = mock_expander.expand_query(
            query="wizard spells",
            strategy="alias",
            max_expansions=5,
            min_confidence=0.5
        )

        assert result.original_query == "wizard spells"
        assert result.expansion_strategy == "alias"
        assert len(result.expansion_terms) > 0

        # Should contain aliases
        expansion_terms = [term.term for term in result.expansion_terms]
        assert "mage" in expansion_terms or "spellcaster" in expansion_terms

    def test_expand_query_cross_ref_strategy(self, mock_expander):
        """Test query expansion with cross-reference strategy."""
        result = mock_expander.expand_query(
            query="wizard magic",
            strategy="cross_ref",
            max_expansions=5,
            min_confidence=0.5
        )

        assert result.expansion_strategy == "cross_ref"
        assert len(result.expansion_terms) > 0

    def test_expand_query_hybrid_strategy(self, mock_expander):
        """Test query expansion with hybrid strategy."""
        result = mock_expander.expand_query(
            query="wizard fireball",
            strategy="hybrid",
            max_expansions=10,
            min_confidence=0.3
        )

        assert result.expansion_strategy == "hybrid"
        # Hybrid should potentially include multiple types of expansions
        sources = {term.source for term in result.expansion_terms}
        assert len(sources) >= 1  # Should have at least one type of expansion

    def test_expand_query_no_graph_data(self, mock_expander):
        """Test expansion when no graph data is available."""
        mock_expander.graph_loader.load_graph_snapshot = MagicMock(return_value=None)

        result = mock_expander.expand_query("wizard spells")

        assert result.original_query == "wizard spells"
        assert result.expanded_query == "wizard spells"  # Should be unchanged
        assert len(result.expansion_terms) == 0
        assert result.processing_time_ms == 0.0

    def test_filter_and_rank_expansions(self, mock_expander):
        """Test filtering and ranking of expansion terms."""
        expansions = [
            ExpansionTerm("term1", "alias", 0.9, "original"),
            ExpansionTerm("term2", "cross_ref", 0.5, "original"),
            ExpansionTerm("term3", "graph", 0.2, "original"),  # Below min confidence
            ExpansionTerm("term1", "alias", 0.8, "original"),  # Duplicate
        ]

        filtered = mock_expander._filter_and_rank_expansions(
            expansions, max_expansions=3, min_confidence=0.4
        )

        # Should remove duplicates and low confidence terms
        assert len(filtered) == 2
        terms = [exp.term for exp in filtered]
        assert "term1" in terms
        assert "term2" in terms
        assert "term3" not in terms

        # Should be sorted by confidence
        assert filtered[0].confidence >= filtered[1].confidence

    def test_build_expanded_query(self, mock_expander):
        """Test building expanded query string."""
        expansions = [
            ExpansionTerm("mage", "alias", 0.9, "wizard"),
            ExpansionTerm("fireball", "cross_ref", 0.8, "wizard")
        ]

        expanded_query = mock_expander._build_expanded_query("wizard spells", expansions)

        assert "wizard spells" in expanded_query
        assert "mage" in expanded_query
        assert "fireball" in expanded_query
        assert "OR" in expanded_query  # Should use OR logic

    def test_build_expanded_query_no_expansions(self, mock_expander):
        """Test building query with no expansions."""
        expanded_query = mock_expander._build_expanded_query("wizard spells", [])
        assert expanded_query == "wizard spells"

    def test_tokenize(self, mock_expander):
        """Test query tokenization."""
        tokens = mock_expander._tokenize("Wizard casts fireball spell!")
        expected = ["wizard", "casts", "fireball", "spell"]
        assert tokens == expected

    def test_extract_key_terms(self, mock_expander):
        """Test key term extraction from text."""
        key_terms = mock_expander._extract_key_terms("The wizard casts a powerful fireball spell")

        # Should extract meaningful terms, filter stop words
        assert len(key_terms) <= 3  # Limited to 3 terms
        assert all(len(term) > 3 for term in key_terms)  # No short words
        assert "the" not in key_terms  # No stop words

    def test_get_expansion_stats_with_graph(self, mock_expander, mock_graph_snapshot):
        """Test expansion statistics with available graph."""
        stats = mock_expander.get_expansion_stats(mock_graph_snapshot)

        assert stats["available"] is True
        assert stats["nodes"] == 2
        assert stats["edges"] == 0
        assert stats["cross_references"] == 2
        assert stats["aliases"] == 2
        assert stats["job_id"] == "test_job"

    def test_get_expansion_stats_no_graph(self, mock_expander):
        """Test expansion statistics with no graph available."""
        stats = mock_expander.get_expansion_stats(None)
        assert stats["available"] is False