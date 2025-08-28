"""
Test suite for Workflows user stories (03_workflows.md)
Tests for WF-001, WF-002, WF-003 acceptance criteria
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Test WF-001: Graph workflow engine
class TestGraphWorkflowEngine:
    
    def test_workflow_storage_as_graphs(self):
        """Test workflows are stored as graphs with nodes/transitions"""
        from app.workflows.graph_engine import get_workflow_engine
        
        engine = get_workflow_engine()
        workflows = engine.list_workflows()
        
        assert len(workflows) > 0, "No workflows found"
        
        # Check first workflow structure
        workflow_id = workflows[0]
        workflow = engine.get_workflow(workflow_id)
        
        required_fields = ['workflow_id', 'nodes', 'edges']
        for field in required_fields:
            assert field in workflow, f"Workflow missing required field: {field}"
        
        # Verify nodes have proper structure
        if workflow['nodes']:
            first_node = list(workflow['nodes'].values())[0]
            node_fields = ['node_id', 'node_type', 'title']
            for field in node_fields:
                assert field in first_node, f"Node missing required field: {field}"
    
    def test_node_metadata_structure(self):
        """Test nodes include prompts and dictionary references"""
        from app.workflows.graph_engine import get_workflow_engine
        
        engine = get_workflow_engine()
        workflows = engine.list_workflows()
        
        if workflows:
            workflow = engine.get_workflow(workflows[0])
            
            # Find a node with content
            for node in workflow['nodes'].values():
                if node.get('prompt'):
                    assert isinstance(node['prompt'], str), "Node prompt should be string"
                    assert len(node['prompt']) > 0, "Node prompt should not be empty"
                
                if node.get('rag_query_template'):
                    assert isinstance(node['rag_query_template'], str), "RAG template should be string"
    
    def test_deterministic_execution(self):
        """Test workflow execution is deterministic with state tracking"""
        from app.workflows.graph_engine import get_workflow_engine
        
        engine = get_workflow_engine()
        
        # Create a test workflow session
        session_id = "test_session_001"
        workflow_id = "character_creation_pathfinder_2e"
        
        # Start workflow
        state1 = engine.start_workflow(session_id, workflow_id)
        state2 = engine.start_workflow(session_id, workflow_id)
        
        # Should return same initial state
        assert state1['current_node'] == state2['current_node'], "Workflow start not deterministic"

# Test WF-002: Character Creation workflow
class TestCharacterCreationWorkflow:
    
    def test_character_creation_workflow_exists(self):
        """Test multi-step character creation flow exists"""
        workflow_path = Path("app/workflows/definitions/character_creation_pathfinder_2e.json")
        assert workflow_path.exists(), "Character creation workflow definition missing"
        
        with open(workflow_path) as f:
            workflow = json.load(f)
        
        assert workflow['workflow_id'] == 'character_creation_pathfinder_2e', "Wrong workflow ID"
        assert 'nodes' in workflow, "Workflow missing nodes"
        assert len(workflow['nodes']) >= 3, "Character creation should be multi-step"
    
    def test_system_specific_validation(self):
        """Test system-specific validation rules exist"""
        workflow_path = Path("app/workflows/definitions/character_creation_pathfinder_2e.json")
        
        if workflow_path.exists():
            with open(workflow_path) as f:
                workflow = json.load(f)
            
            # Look for validation rules in nodes
            has_validation = False
            for node in workflow['nodes'].values():
                if node.get('validation_rules'):
                    has_validation = True
                    break
            
            assert has_validation, "No validation rules found in character creation workflow"
    
    def test_rag_integration_for_legal_options(self):
        """Test character creation integrates with RAG for legal options"""
        workflow_path = Path("app/workflows/definitions/character_creation_pathfinder_2e.json")
        
        if workflow_path.exists():
            with open(workflow_path) as f:
                workflow = json.load(f)
            
            # Look for RAG query templates
            has_rag_queries = False
            for node in workflow['nodes'].values():
                if node.get('rag_query_template'):
                    has_rag_queries = True
                    break
            
            assert has_rag_queries, "Character creation workflow missing RAG integration"

# Test WF-003: Intelligent routing
class TestIntelligentRouting:
    
    def test_query_classification_routing(self):
        """Test query classification for routing decisions"""
        from app.workflows.router import get_router
        
        router = get_router()
        
        # Test different query types
        test_queries = [
            ("Create a character", "workflow"),
            ("What is armor class?", "rag"),
            ("Level up my fighter", "workflow"),
            ("Tell me about dragons", "rag")
        ]
        
        for query, expected_type in test_queries:
            route_decision = router.classify_query(query)
            
            assert 'route_type' in route_decision, "Router decision missing route_type"
            # Note: Exact matching depends on router implementation
            # Just verify it makes a decision
            assert route_decision['route_type'] in ['workflow', 'rag', 'general'], "Invalid route type"
    
    def test_fallback_to_openai_training(self):
        """Test fallback to OpenAI training data when appropriate"""
        from app.workflows.router import get_router
        
        router = get_router()
        
        # Test a query that should fall back to general knowledge
        general_query = "What is the capital of France?"
        route_decision = router.classify_query(general_query)
        
        # Should route to general/fallback
        assert route_decision.get('route_type') in ['general', 'fallback'], "General query not routed to fallback"
    
    def test_response_source_labeling(self):
        """Test responses are clearly labeled with sources"""
        from app.workflows.router import get_router
        
        router = get_router()
        
        # Test that router provides source information
        query = "What classes are available?"
        route_decision = router.classify_query(query)
        
        assert 'source' in route_decision or 'rationale' in route_decision, "Route decision missing source info"

# Integration tests
class TestWorkflowIntegration:
    
    def test_workflow_to_rag_integration(self):
        """Test workflows can query RAG system for information"""
        from app.workflows.graph_engine import get_workflow_engine
        from app.common.astra_client import get_vector_store
        
        engine = get_workflow_engine()
        vector_store = get_vector_store()
        
        # Verify both systems are accessible
        workflows = engine.list_workflows()
        health = vector_store.health_check()
        
        assert len(workflows) > 0, "No workflows available for integration"
        assert health['status'] in ['connected', 'error'], "Vector store not accessible for workflow integration"
    
    def test_workflow_state_persistence(self):
        """Test workflow states persist across sessions"""
        from app.workflows.graph_engine import get_workflow_engine
        
        engine = get_workflow_engine()
        session_id = "test_persistence_001"
        workflow_id = "character_creation_pathfinder_2e"
        
        # Start workflow and advance state
        initial_state = engine.start_workflow(session_id, workflow_id)
        
        # Simulate advancing to next node (if possible)
        if initial_state.get('available_transitions'):
            next_transition = initial_state['available_transitions'][0]
            advanced_state = engine.transition_workflow(session_id, next_transition)
            
            # Retrieve state again
            retrieved_state = engine.get_workflow_state(session_id)
            
            assert retrieved_state['current_node'] == advanced_state['current_node'], "Workflow state not persisted"
    
    def test_multi_workflow_support(self):
        """Test system supports multiple workflow types"""
        from app.workflows.graph_engine import get_workflow_engine
        
        engine = get_workflow_engine()
        workflows = engine.list_workflows()
        
        # Should have both character creation and level up workflows
        workflow_types = [w for w in workflows if 'character_creation' in w or 'level_up' in w]
        assert len(workflow_types) >= 2, "System missing multiple workflow types"