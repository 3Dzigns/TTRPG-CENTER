# tests/unit/test_reason_graphwalk.py
"""
Unit tests for Graph-Guided Reasoning - Phase 3
Tests hop selection, re-grounding cadence, and reasoning trace generation
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from src_common.graph.store import GraphStore
from src_common.reason.graphwalk import GraphGuidedReasoner, graph_guided_answer, ReasoningHop, ReasoningTrace

class TestGraphGuidedReasoner:
    """Test GraphGuidedReasoner multi-hop reasoning capabilities"""
    
    @pytest.fixture
    def temp_store(self):
        """Create graph store with reasoning test data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_graph"
            store = GraphStore(storage_path=storage_path)
            
            # Create reasoning chain: Spell -> Components -> Rules -> Effects
            store.upsert_node("spell:fireball", "Concept", {
                "name": "Fireball", 
                "type": "evocation_spell",
                "description": "3rd level evocation spell"
            })
            
            store.upsert_node("concept:spell_components", "Concept", {
                "name": "Spell Components",
                "description": "Material, somatic, verbal components"
            })
            
            store.upsert_node("rule:spell_casting", "Rule", {
                "text": "Spells require components and spell slots",
                "rule_type": "mechanical"
            })
            
            store.upsert_node("concept:fire_damage", "Concept", {
                "name": "Fire Damage",
                "description": "Elemental damage type"
            })
            
            # Create reasoning chain edges
            store.upsert_edge("spell:fireball", "depends_on", "concept:spell_components", {"strength": 0.9})
            store.upsert_edge("concept:spell_components", "implements", "rule:spell_casting", {"strength": 0.8})
            store.upsert_edge("spell:fireball", "produces", "concept:fire_damage", {"strength": 1.0})
            
            yield store
    
    @pytest.fixture
    def mock_retriever(self):
        """Create mock retriever function"""
        def retriever(query):
            return [
                {
                    "id": f"chunk:retrieved:{hash(query) % 100}",
                    "content": f"Retrieved information about {query}",
                    "score": 0.8,
                    "metadata": {"page": 123, "section": "Test Section"}
                }
            ]
        return retriever
    
    @pytest.fixture
    def reasoner(self, temp_store, mock_retriever):
        """Create GraphGuidedReasoner instance"""
        return GraphGuidedReasoner(temp_store, mock_retriever)
    
    def test_seed_from_goal_matching(self, reasoner):
        """Test seed node selection from goal"""
        
        # Goal that should match fireball
        goal = "How does fireball spell work?"
        seed_node = reasoner._seed_from_goal(goal)
        
        assert seed_node is not None
        assert seed_node["id"] == "spell:fireball"
        assert "fireball" in seed_node["properties"]["name"].lower()
    
    def test_seed_from_goal_no_match(self, reasoner):
        """Test seed selection when no good match exists"""
        
        goal = "Tell me about unicorns and rainbows"
        seed_node = reasoner._seed_from_goal(goal)
        
        # Should return None or low-scoring match
        assert seed_node is None or len(reasoner.graph_store.nodes) == 0
    
    def test_hop_execution_with_neighbors(self, reasoner, temp_store):
        """Test single reasoning hop execution"""
        
        goal = "What are fireball spell requirements?"
        current_node = temp_store.get_node("spell:fireball")
        
        hop = reasoner._perform_hop(goal, current_node, 1, [])
        
        # Verify hop structure
        assert isinstance(hop, ReasoningHop)
        assert hop.hop_number == 1
        assert hop.current_node["id"] == "spell:fireball"
        assert len(hop.neighbors) > 0  # Should find connected nodes
        assert hop.confidence > 0
        assert hop.reasoning != ""
        
        # Should have selected a focus from neighbors
        if hop.neighbors:
            assert hop.selected_focus is not None
            assert hop.selected_focus["id"] in [n["id"] for n in hop.neighbors]
    
    def test_focus_selection_scoring(self, reasoner):
        """Test focus node selection from neighbors"""
        
        goal = "How to use spell components?"
        
        # Mock neighbors with different relevance
        neighbors = [
            {
                "id": "concept:spell_components",
                "type": "Concept",
                "properties": {"name": "Spell Components", "description": "casting requirements"}
            },
            {
                "id": "rule:unrelated",
                "type": "Rule", 
                "properties": {"name": "Unrelated Rule", "text": "something else entirely"}
            },
            {
                "id": "concept:components",
                "type": "Concept",
                "properties": {"name": "Components", "description": "spell components for casting"}
            }
        ]
        
        selected = reasoner._select_next_focus(goal, neighbors, [])
        
        # Should select most relevant neighbor
        assert selected is not None
        assert "component" in selected["properties"]["name"].lower()
    
    def test_focus_query_generation(self, reasoner):
        """Test targeted query generation from focus node"""
        
        goal = "How does fireball work?"
        focus_node = {
            "id": "concept:spell_components",
            "type": "Concept",
            "properties": {"name": "Spell Components"}
        }
        
        query = reasoner._generate_focus_query(goal, focus_node)
        
        # Should combine goal with focus context
        assert "fireball" in query.lower()
        assert "spell components" in query.lower()
        assert len(query.split()) > len(goal.split())  # Should be expanded
    
    def test_confidence_calculation(self, reasoner):
        """Test hop confidence calculation factors"""
        
        # High confidence scenario: many neighbors, good selection, good retrieval
        neighbors = [{"id": f"node:{i}", "type": "Concept"} for i in range(10)]
        selected_focus = {"id": "node:5", "type": "Concept"}
        retrieved_context = [
            {"content": "relevant content", "score": 0.9},
            {"content": "more relevant content", "score": 0.8}
        ]
        
        high_confidence = reasoner._calculate_hop_confidence(neighbors, selected_focus, retrieved_context)
        
        # Low confidence scenario: few neighbors, no selection, poor retrieval
        low_confidence = reasoner._calculate_hop_confidence([], None, [])
        
        assert high_confidence > low_confidence
        assert 0 <= high_confidence <= 1
        assert 0 <= low_confidence <= 1
    
    def test_regrounding_context_reduction(self, reasoner):
        """Test re-grounding step reduces context appropriately"""
        
        goal = "fireball spell mechanics"
        
        # Large context that needs reduction
        large_context = []
        for i in range(10):
            large_context.append({
                "content": f"Content {i} about {'fireball' if i < 3 else 'unrelated'} mechanics",
                "score": 0.9 - (i * 0.1)
            })
        
        regrounded = reasoner._regrounding_step(goal, large_context)
        
        # Should reduce to manageable size
        assert len(regrounded) <= 5
        
        # Should keep most relevant items (those with "fireball")
        fireball_items = [item for item in regrounded if "fireball" in item["content"]]
        assert len(fireball_items) >= 2  # Should prioritize relevant content
    
    def test_complete_reasoning_trace(self, reasoner):
        """Test complete multi-hop reasoning workflow"""
        
        goal = "Explain fireball spell requirements and effects"
        trace = reasoner.graph_guided_answer(goal, max_hops=3)
        
        # Verify trace structure
        assert isinstance(trace, ReasoningTrace)
        assert trace.goal == goal
        assert trace.seed_node is not None
        assert len(trace.hops) <= 3
        assert trace.total_confidence > 0
        assert trace.duration_s > 0
        assert trace.answer != ""
        assert len(trace.sources) > 0
        
        # Verify hop progression
        for i, hop in enumerate(trace.hops):
            assert hop.hop_number == i + 1
            assert hop.confidence > 0
            assert hop.reasoning != ""
    
    def test_confidence_below_threshold_stops_reasoning(self, reasoner):
        """Test that low confidence stops reasoning early"""
        
        # Mock retriever that returns poor results
        def poor_retriever(query):
            return [{"content": "poor irrelevant content", "score": 0.1}]
        
        reasoner.retriever = poor_retriever
        reasoner.MIN_CONFIDENCE = 0.8  # Set high threshold
        
        goal = "Complex query with poor retrieval"
        trace = reasoner.graph_guided_answer(goal, max_hops=5)
        
        # Should stop early due to low confidence
        assert len(trace.hops) < 5
        if trace.hops:
            # At least one hop should have low confidence
            low_conf_hops = [hop for hop in trace.hops if hop.confidence < 0.8]
            assert len(low_conf_hops) > 0
    
    def test_regrounding_interval_behavior(self, reasoner):
        """Test re-grounding occurs at correct intervals"""
        
        reasoner.REGROUNDING_INTERVAL = 2
        
        # Track when re-grounding occurs (would need more sophisticated mocking in real test)
        goal = "Multi-hop reasoning test"
        trace = reasoner.graph_guided_answer(goal, max_hops=4)
        
        # Verify trace completes (basic structure test)
        assert isinstance(trace, ReasoningTrace)
        assert trace.goal == goal
        
        # In production test, would verify re-grounding called at hops 2, 4, etc.
    
    def test_fallback_reasoning_mode(self, reasoner):
        """Test fallback when no graph path available"""
        
        # Empty graph store
        empty_store = GraphStore()
        empty_reasoner = GraphGuidedReasoner(empty_store, reasoner.retriever)
        
        goal = "Question with no graph support"
        trace = empty_reasoner.graph_guided_answer(goal)
        
        # Should use fallback mode
        assert trace.seed_node["id"] == "fallback"
        assert len(trace.hops) == 0  # No graph hops
        assert len(trace.final_context) > 0  # Should have retrieved context
        assert trace.answer != ""
        assert "no graph path" in trace.answer.lower()
    
    def test_source_extraction_and_deduplication(self, reasoner):
        """Test source citation extraction and deduplication"""
        
        context_with_duplicates = [
            {"content": "Content 1", "metadata": {"page": 123, "section": "A"}, "source": "Book 1"},
            {"content": "Content 2", "metadata": {"page": 123, "section": "A"}, "source": "Book 1"},  # Duplicate
            {"content": "Content 3", "metadata": {"page": 456, "section": "B"}, "source": "Book 2"},
        ]
        
        sources = reasoner._extract_sources(context_with_duplicates)
        
        # Should deduplicate by page/source combination
        assert len(sources) == 2  # Should have deduplicated
        
        # Verify source structure
        for source in sources:
            assert "source" in source or "page" in source
    
    def test_final_confidence_calculation(self, reasoner):
        """Test final confidence calculation from hops"""
        
        # Create hops with decreasing confidence (simulating decay)
        hops = [
            ReasoningHop(1, {}, [], None, [], 0.9, "High confidence hop"),
            ReasoningHop(2, {}, [], None, [], 0.7, "Medium confidence hop"), 
            ReasoningHop(3, {}, [], None, [], 0.5, "Lower confidence hop")
        ]
        
        final_confidence = reasoner._calculate_final_confidence(hops)
        
        # Should be weighted average with decay
        assert 0 < final_confidence < 1
        assert final_confidence < 0.9  # Should be less than first hop due to decay
        assert final_confidence > 0.5  # Should be higher than last hop due to weighting
    
    def test_reasoning_path_analysis(self, reasoner):
        """Test reasoning trace analysis and quality assessment"""
        
        # Create high-quality trace
        high_quality_trace = ReasoningTrace(
            goal="Test goal",
            seed_node={"id": "test", "type": "Concept"},
            hops=[
                ReasoningHop(1, {}, [{"id": "n1"}], {"id": "selected"}, [{"content": "good"}], 0.9, "Good hop"),
                ReasoningHop(2, {}, [{"id": "n2"}], {"id": "selected2"}, [{"content": "also good"}], 0.8, "Also good hop")
            ],
            final_context=[{"content": "final context"}],
            answer="High quality answer",
            total_confidence=0.85,
            sources=[{"source": "Test Source"}],
            duration_s=2.5
        )
        
        analysis = reasoner.analyze_reasoning_path(high_quality_trace)
        
        # Verify analysis structure
        assert analysis["total_hops"] == 2
        assert analysis["final_confidence"] == 0.85
        assert analysis["path_quality"] == "good"  # Should be good for confidence > 0.7
        assert analysis["assessment"] == "high_quality"
        assert len(analysis["hop_analysis"]) == 2
        
        # Verify hop analysis details
        hop1_analysis = analysis["hop_analysis"][0]
        assert hop1_analysis["hop_number"] == 1
        assert hop1_analysis["focus_selected"]
        assert hop1_analysis["confidence"] == 0.9


class TestReasoningComponents:
    """Test individual reasoning components and utilities"""
    
    def test_reasoning_hop_structure(self):
        """Test ReasoningHop data structure"""
        
        hop = ReasoningHop(
            hop_number=1,
            current_node={"id": "test", "type": "Concept"},
            neighbors=[{"id": "neighbor1"}, {"id": "neighbor2"}],
            selected_focus={"id": "neighbor1"},
            retrieved_context=[{"content": "context"}],
            confidence=0.75,
            reasoning="Test reasoning explanation"
        )
        
        # Verify all fields accessible
        assert hop.hop_number == 1
        assert hop.current_node["id"] == "test"
        assert len(hop.neighbors) == 2
        assert hop.selected_focus["id"] == "neighbor1"
        assert hop.confidence == 0.75
        assert hop.reasoning == "Test reasoning explanation"
    
    def test_reasoning_trace_structure(self):
        """Test ReasoningTrace data structure"""
        
        trace = ReasoningTrace(
            goal="Test goal",
            seed_node={"id": "seed"},
            hops=[],
            final_context=[],
            answer="Test answer",
            total_confidence=0.8,
            sources=[],
            duration_s=1.5
        )
        
        # Verify structure
        assert trace.goal == "Test goal"
        assert trace.seed_node["id"] == "seed"
        assert trace.answer == "Test answer"
        assert trace.total_confidence == 0.8
        assert trace.duration_s == 1.5
    
    def test_edge_weight_preferences(self):
        """Test edge type weighting for navigation preferences"""
        
        reasoner = GraphGuidedReasoner(GraphStore())
        
        # Verify edge weights are defined and reasonable
        weights = reasoner.edge_weights
        
        assert "depends_on" in weights
        assert "part_of" in weights
        assert "implements" in weights
        assert "cites" in weights
        
        # Verify reasonable weight ordering
        assert weights["depends_on"] > weights["cites"]  # Dependencies more important than citations
        assert weights["part_of"] > weights["variant_of"]  # Structural more than variant relationships
    
    def test_max_hops_enforcement(self, reasoner):
        """Test maximum hops limit enforcement"""
        
        goal = "Test max hops enforcement"
        
        # Request more hops than allowed
        trace = reasoner.graph_guided_answer(goal, max_hops=20)  # More than MAX_HOPS
        
        # Should be limited by MAX_HOPS
        assert len(trace.hops) <= reasoner.MAX_HOPS
    
    def test_synthesis_with_limited_context(self, reasoner):
        """Test answer synthesis with various context sizes"""
        
        goal = "Synthesize from limited context"
        
        # Test with no context
        answer_empty = reasoner._synthesize_answer(goal, [])
        assert answer_empty != ""
        assert goal.lower() in answer_empty.lower()
        
        # Test with single context item
        single_context = [{"content": "Single piece of information", "metadata": {"page": 1}}]
        answer_single = reasoner._synthesize_answer(goal, single_context)
        assert answer_single != ""
        assert "single piece" in answer_single.lower()
        
        # Test with multiple context items
        multi_context = [
            {"content": f"Information piece {i}", "metadata": {"page": i}} 
            for i in range(5)
        ]
        answer_multi = reasoner._synthesize_answer(goal, multi_context)
        assert answer_multi != ""
        assert len(answer_multi) > len(answer_single)  # Should be more comprehensive


class TestConvenienceFunctions:
    """Test module-level convenience functions"""
    
    def test_graph_guided_answer_function(self):
        """Test graph_guided_answer convenience function"""
        
        # Create minimal test setup
        graph_store = GraphStore()
        graph_store.upsert_node("test:node", "Concept", {"name": "Test"})
        
        def mock_retriever(query):
            return [{"content": f"Retrieved: {query}", "score": 0.7}]
        
        result = graph_guided_answer("Test question", graph_store, mock_retriever, hops=2)
        
        # Verify API-compatible result format
        assert "answer" in result
        assert "confidence" in result
        assert "sources" in result
        assert "reasoning_trace" in result
        
        # Verify reasoning trace format
        trace = result["reasoning_trace"]
        assert "seed_node" in trace
        assert "hops" in trace
        assert "duration_s" in trace
        
        # Verify hop format in trace
        if trace["hops"]:
            hop = trace["hops"][0]
            assert "hop_number" in hop
            assert "confidence" in hop
            assert "reasoning" in hop
    
    def test_mock_retriever_functionality(self, reasoner):
        """Test built-in mock retriever"""
        
        query = "Test query for mock retriever"
        results = reasoner._mock_retriever(query)
        
        # Should return reasonable mock results
        assert len(results) == 1
        assert query in results[0]["content"]
        assert "score" in results[0]
        assert "metadata" in results[0]
        assert 0 < results[0]["score"] <= 1
    
    def test_reasoning_configuration_limits(self):
        """Test reasoning configuration and safety limits"""
        
        reasoner = GraphGuidedReasoner(GraphStore())
        
        # Verify safety limits are set
        assert reasoner.MAX_HOPS > 0
        assert reasoner.MAX_HOPS <= 10  # Reasonable upper bound
        assert 0 < reasoner.MIN_CONFIDENCE < 1
        assert reasoner.REGROUNDING_INTERVAL > 0
        
        # Verify edge weights sum to reasonable range
        total_weights = sum(reasoner.edge_weights.values())
        assert total_weights > 2.0  # Should have substantial cumulative weight
    
    def test_error_handling_in_hop_execution(self, reasoner):
        """Test error handling during hop execution"""
        
        # Create reasoner with broken graph store
        broken_store = Mock()
        broken_store.neighbors.side_effect = Exception("Graph store error")
        
        broken_reasoner = GraphGuidedReasoner(broken_store, reasoner.retriever)
        
        goal = "Test error handling"
        current_node = {"id": "test", "type": "Concept"}
        
        # Should handle error gracefully
        hop = broken_reasoner._perform_hop(goal, current_node, 1, [])
        
        assert hop.hop_number == 1
        assert hop.confidence == 0.0
        assert "failed" in hop.reasoning.lower()
        assert hop.selected_focus is None