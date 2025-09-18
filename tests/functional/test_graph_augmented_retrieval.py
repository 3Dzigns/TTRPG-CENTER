"""
End-to-end functional tests for graph augmented retrieval integration.
Tests the complete flow from query planning through graph-enhanced retrieval.
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.orchestrator.query_planner import get_planner
from src_common.orchestrator.graph_loader import GraphSnapshot, GraphNode, CrossReference
from src_common.orchestrator.retriever import retrieve
from src_common.orchestrator.graph_ranker import rank_with_graph, process_query_for_graph


class TestGraphAugmentedRetrievalEndToEnd:
    """
    Test complete graph augmented retrieval integration.
    """

    @pytest.fixture
    def mock_graph_data(self):
        """Create comprehensive mock graph data."""
        nodes = {
            "wizard_class": GraphNode(
                "wizard_class", "entity", "Wizard",
                content="A spellcasting class that uses intelligence and arcane magic",
                metadata={"type": "character_class"}
            ),
            "fireball_spell": GraphNode(
                "fireball_spell", "entity", "Fireball",
                content="A 3rd-level evocation spell that creates a fiery explosion",
                metadata={"type": "spell", "level": 3, "school": "evocation"}
            ),
            "intelligence_attr": GraphNode(
                "intelligence_attr", "entity", "Intelligence",
                content="Mental attribute that affects spellcasting for wizards",
                metadata={"type": "attribute"}
            ),
            "spellbook_item": GraphNode(
                "spellbook_item", "entity", "Spellbook",
                content="A book containing spells that wizards use to prepare magic",
                metadata={"type": "equipment"}
            )
        }

        cross_refs = [
            CrossReference(
                "ref1", "wizard", "fireball", "class_to_spell", 0.9,
                "Wizards can learn and cast fireball spells"
            ),
            CrossReference(
                "ref2", "wizard", "intelligence", "class_to_attribute", 0.95,
                "Wizards use intelligence for their spellcasting ability"
            ),
            CrossReference(
                "ref3", "wizard", "spellbook", "class_to_equipment", 0.8,
                "Wizards record spells in their spellbooks"
            ),
            CrossReference(
                "ref4", "fireball", "evocation", "spell_to_school", 0.9,
                "Fireball is an evocation school spell"
            )
        ]

        aliases = {
            "wizard": {"mage", "arcanist", "spellcaster"},
            "fireball": {"fire spell", "explosive spell"},
            "intelligence": {"int", "mental attribute"},
            "spellbook": {"grimoire", "spell tome"}
        }

        return GraphSnapshot(
            job_id="test_job_comprehensive",
            created_at=time.time(),
            nodes=nodes,
            edges=[],
            cross_references=cross_refs,
            aliases=aliases
        )

    @pytest.fixture
    def mock_search_results(self):
        """Create mock search results for ranking tests."""
        return [
            {
                "id": "chunk_1",
                "text": "Wizards are intelligent spellcasters who study arcane magic. They use spellbooks to record their spells and rely on intelligence for casting.",
                "source": "pathfinder_core.pdf",
                "score": 0.85,
                "metadata": {"page": 42, "section": "Classes"}
            },
            {
                "id": "chunk_2",
                "text": "Fireball is a powerful evocation spell that creates a fiery explosion. It requires precise targeting and deals significant damage.",
                "source": "spells_compendium.pdf",
                "score": 0.70,
                "metadata": {"page": 156, "section": "Spells", "spell_level": 3}
            },
            {
                "id": "chunk_3",
                "text": "Combat tactics for fighters include weapon specialization and armor optimization. Heavy armor provides excellent protection.",
                "source": "combat_guide.pdf",
                "score": 0.60,
                "metadata": {"page": 23, "section": "Combat"}
            },
            {
                "id": "chunk_4",
                "text": "Mages, also known as wizards, require high intelligence to cast spells effectively. Their arcane power comes from study and preparation.",
                "source": "magic_guide.pdf",
                "score": 0.75,
                "metadata": {"page": 89, "section": "Arcane Magic"}
            }
        ]

    def test_query_planning_with_graph_expansion(self, mock_graph_data):
        """Test that query planning includes graph expansion metadata."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            planner = get_planner("test")
            plan = planner.get_plan("What spells can wizards cast?")

            # Verify plan includes graph expansion
            assert plan.graph_expansion is not None
            assert plan.graph_expansion.get("enabled") is True
            assert "expansion_terms" in plan.graph_expansion

            # Check for expected expansions
            expansion_terms = [term["term"] for term in plan.graph_expansion.get("expansion_terms", [])]
            # Should include aliases like "mage" or cross-references like "fireball"
            assert len(expansion_terms) > 0

    def test_graph_enhanced_retrieval_scoring(self, mock_graph_data, mock_search_results):
        """Test that graph enhancement improves retrieval scoring."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            # Create a mock query plan with graph expansion
            mock_plan = MagicMock()
            mock_plan.retrieval_strategy = {"vector_top_k": 5}
            mock_plan.graph_expansion = {
                "enabled": True,
                "expansion_terms": [
                    {"term": "mage", "source": "alias", "confidence": 0.9, "original_term": "wizard"},
                    {"term": "fireball", "source": "cross_ref", "confidence": 0.9, "original_term": "wizard"}
                ],
                "expanded_query": "(wizard spells) OR (\"mage\" OR \"fireball\")"
            }

            # Mock the vector store to return our test results
            with patch('src_common.orchestrator.retriever._retrieve_from_store') as mock_vector_store:
                mock_vector_store.return_value = []  # Force fallback to local scoring

                with patch('src_common.orchestrator.retriever._iter_candidate_chunks') as mock_chunks:
                    # Convert mock results to DocChunk-like objects
                    chunk_objects = []
                    for result in mock_search_results:
                        chunk_obj = MagicMock()
                        chunk_obj.id = result["id"]
                        chunk_obj.text = result["text"]
                        chunk_obj.source = result["source"]
                        chunk_obj.metadata = result["metadata"]
                        chunk_objects.append(chunk_obj)

                    mock_chunks.return_value = chunk_objects

                    # Retrieve with graph enhancement
                    results = retrieve(mock_plan, "wizard spells", "test", limit=4)

                    # Verify results are returned
                    assert len(results) > 0

                    # Results should be scored with graph awareness
                    # Chunks mentioning both "wizard" and graph expansion terms should score higher
                    wizard_chunk = next((r for r in results if "wizard" in r.text.lower() and "mage" in r.text.lower()), None)
                    if wizard_chunk:
                        # Should have received graph boost
                        assert wizard_chunk.score > 0

    def test_graph_aware_result_ranking(self, mock_graph_data, mock_search_results):
        """Test graph-aware result ranking functionality."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            # Mock graph expansion metadata
            graph_expansion = {
                "enabled": True,
                "expansion_terms": [
                    {"term": "mage", "source": "alias", "confidence": 0.9, "original_term": "wizard"},
                    {"term": "fireball", "source": "cross_ref", "confidence": 0.8, "original_term": "wizard"}
                ]
            }

            # Rank results with graph awareness
            ranked_results = rank_with_graph(
                query="wizard spells",
                results=mock_search_results,
                graph_expansion=graph_expansion,
                environment="test"
            )

            assert len(ranked_results) == len(mock_search_results)

            # Results should be properly ranked
            for result in ranked_results:
                assert hasattr(result, 'combined_score')
                assert hasattr(result, 'graph_score')
                assert hasattr(result, 'base_score')

            # Chunks with more entity matches should rank higher
            # The wizard chunk and mage chunk should score well
            wizard_scores = [r.combined_score for r in ranked_results
                           if "wizard" in r.text.lower() or "mage" in r.text.lower()]
            other_scores = [r.combined_score for r in ranked_results
                          if not ("wizard" in r.text.lower() or "mage" in r.text.lower())]

            if wizard_scores and other_scores:
                assert max(wizard_scores) >= max(other_scores)

    def test_query_processing_entity_extraction(self, mock_graph_data):
        """Test entity extraction and relationship finding."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            # Process a complex query
            result = process_query_for_graph(
                "What spells can wizards cast using intelligence?",
                environment="test"
            )

            # Should extract relevant entities
            assert "wizard" in result.get("all_entities", []) or "wizards" in result.get("all_entities", [])
            assert "spell" in result.get("all_entities", []) or "spells" in result.get("all_entities", [])

            # Should identify query patterns
            patterns = result.get("query_patterns", [])
            assert len(patterns) > 0

            # Should recommend appropriate strategy
            strategy = result.get("recommended_strategy", "")
            assert strategy in ["alias", "cross_ref", "graph", "hybrid", "none"]

    def test_end_to_end_graph_retrieval_flow(self, mock_graph_data, mock_search_results):
        """Test complete end-to-end graph augmented retrieval flow."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            # Step 1: Query Planning with graph expansion
            planner = get_planner("test")
            plan = planner.get_plan("wizard fireball spell")

            # Verify plan has graph expansion
            assert plan.graph_expansion is not None

            # Step 2: Retrieval with graph enhancement
            with patch('src_common.orchestrator.retriever._retrieve_from_store') as mock_vector:
                mock_vector.return_value = []  # Force local retrieval

                with patch('src_common.orchestrator.retriever._iter_candidate_chunks') as mock_chunks:
                    chunk_objects = []
                    for result in mock_search_results:
                        chunk_obj = MagicMock()
                        chunk_obj.id = result["id"]
                        chunk_obj.text = result["text"]
                        chunk_obj.source = result["source"]
                        chunk_obj.metadata = result["metadata"]
                        chunk_objects.append(chunk_obj)

                    mock_chunks.return_value = chunk_objects

                    # Retrieve using the plan
                    retrieval_results = retrieve(plan, "wizard fireball spell", "test", limit=3)

            # Step 3: Convert to ranking format and rank
            ranking_results = []
            for chunk in retrieval_results:
                ranking_results.append({
                    "id": chunk.id,
                    "text": chunk.text,
                    "source": chunk.source,
                    "score": chunk.score,
                    "metadata": chunk.metadata
                })

            ranked_results = rank_with_graph(
                query="wizard fireball spell",
                results=ranking_results,
                graph_expansion=plan.graph_expansion,
                environment="test"
            )

            # Verify end-to-end flow produces meaningful results
            assert len(ranked_results) > 0

            # Results should have enhanced scoring
            for result in ranked_results:
                assert result.combined_score >= 0
                assert hasattr(result, 'graph_relationships')

            # Relevant results should rank higher than irrelevant ones
            fireball_results = [r for r in ranked_results if "fireball" in r.text.lower()]
            combat_results = [r for r in ranked_results if "fighter" in r.text.lower() and "fireball" not in r.text.lower()]

            if fireball_results and combat_results:
                best_fireball_score = max(r.combined_score for r in fireball_results)
                best_combat_score = max(r.combined_score for r in combat_results)
                assert best_fireball_score >= best_combat_score

    def test_fallback_behavior_no_graph_data(self, mock_search_results):
        """Test graceful fallback when no graph data is available."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = None  # No graph data
            mock_loader.return_value = mock_loader_instance

            # Query planning should still work
            planner = get_planner("test")
            plan = planner.get_plan("wizard spells")

            # Graph expansion should be None or indicate fallback
            assert plan.graph_expansion is None or plan.graph_expansion.get("fallback") is True

            # Retrieval should still work without graph enhancement
            with patch('src_common.orchestrator.retriever._retrieve_from_store') as mock_vector:
                mock_vector.return_value = []

                with patch('src_common.orchestrator.retriever._iter_candidate_chunks') as mock_chunks:
                    chunk_objects = []
                    for result in mock_search_results:
                        chunk_obj = MagicMock()
                        chunk_obj.id = result["id"]
                        chunk_obj.text = result["text"]
                        chunk_obj.source = result["source"]
                        chunk_obj.metadata = result["metadata"]
                        chunk_objects.append(chunk_obj)

                    mock_chunks.return_value = chunk_objects

                    results = retrieve(plan, "wizard spells", "test", limit=3)

            # Should still return results
            assert len(results) > 0

            # Ranking should also work without graph data
            ranking_results = []
            for chunk in results:
                ranking_results.append({
                    "id": chunk.id,
                    "text": chunk.text,
                    "source": chunk.source,
                    "score": chunk.score,
                    "metadata": chunk.metadata
                })

            ranked_results = rank_with_graph(
                query="wizard spells",
                results=ranking_results,
                environment="test"
            )

            assert len(ranked_results) > 0

    def test_performance_requirements(self, mock_graph_data):
        """Test that graph operations meet performance requirements."""
        with patch('src_common.orchestrator.graph_loader.get_graph_loader') as mock_loader:
            mock_loader_instance = MagicMock()
            mock_loader_instance.load_graph_snapshot.return_value = mock_graph_data
            mock_loader.return_value = mock_loader_instance

            # Test query planning performance
            start_time = time.time()
            planner = get_planner("test")
            plan = planner.get_plan("wizard spells for beginners")
            planning_time = (time.time() - start_time) * 1000

            # Graph expansion should complete within reasonable time
            if plan.graph_expansion and "processing_time_ms" in plan.graph_expansion:
                expansion_time = plan.graph_expansion["processing_time_ms"]
                assert expansion_time < 100  # Should be under 100ms

            # Overall planning should be fast
            assert planning_time < 500  # Should be under 500ms total