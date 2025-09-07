# tests/unit/test_graph_build.py
"""
Unit tests for Graph Builder - Phase 3
Tests procedure extraction from text and knowledge graph building
"""

import pytest
import tempfile
from pathlib import Path

from src_common.graph.store import GraphStore
from src_common.graph.build import GraphBuilder, build_procedure_from_chunks

class TestGraphBuilder:
    """Test GraphBuilder procedure extraction and knowledge graph construction"""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary graph store for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_graph"
            store = GraphStore(storage_path=storage_path)
            yield store
    
    @pytest.fixture
    def graph_builder(self, temp_store):
        """Create GraphBuilder instance"""
        return GraphBuilder(temp_store)
    
    @pytest.fixture
    def craft_potion_chunks(self):
        """Sample chunks for crafting potion procedure"""
        return [
            {
                "id": "chunk:craft:1",
                "content": "To craft a healing potion, you must first gather 2 units of healing herbs and 1 vial of purified water.",
                "metadata": {"page": 156, "section": "Alchemy Basics", "chunk_type": "procedure"}
            },
            {
                "id": "chunk:craft:2", 
                "content": "Step 1: Prepare your alchemical workspace with proper ventilation. Step 2: Mix the healing herbs with purified water in a clean alchemical flask.",
                "metadata": {"page": 156, "section": "Alchemy Basics", "chunk_type": "steps"}
            },
            {
                "id": "chunk:craft:3",
                "content": "Step 3: Apply gentle heat for exactly 10 minutes while stirring clockwise. Step 4: Test the potion's potency with a drop on your tongue - it should taste bitter but not burning.",
                "metadata": {"page": 157, "section": "Alchemy Basics", "chunk_type": "steps"}
            }
        ]
    
    def test_detect_procedure_from_chunks(self, graph_builder, craft_potion_chunks):
        """Test procedure detection from chunk content"""
        
        procedure_info = graph_builder._detect_procedure(craft_potion_chunks)
        
        # Verify procedure detection
        assert procedure_info["type"] == "Procedure"
        assert "healing potion" in procedure_info["properties"]["name"].lower()
        assert procedure_info["properties"]["procedure_type"] == "crafting"
        assert procedure_info["properties"]["chunk_count"] == 3
        assert procedure_info["id"].startswith("proc:")
    
    def test_extract_steps_numbered_list(self, graph_builder, craft_potion_chunks):
        """Test step extraction from numbered list format"""
        
        procedure_info = {"id": "proc:test", "properties": {"name": "Test Procedure"}}
        steps = graph_builder._extract_steps(craft_potion_chunks, procedure_info)
        
        # Should extract at least 4 steps from the chunks
        assert len(steps) >= 4
        
        # Verify step structure
        for step in steps:
            assert step["type"] == "Step"
            assert step["id"].startswith("step:")
            assert "properties" in step
            assert "step_number" in step["properties"]
            assert "name" in step["properties"]
            assert "description" in step["properties"]
            assert step["properties"]["procedure_id"] == procedure_info["id"]
    
    def test_build_source_docs(self, graph_builder, craft_potion_chunks):
        """Test source document creation from chunks"""
        
        source_docs = graph_builder._build_source_docs(craft_potion_chunks)
        
        # Should create source docs for pages
        assert len(source_docs) >= 2  # Pages 156 and 157
        
        # Verify source doc structure
        page_156_doc = next((doc for doc in source_docs if doc["properties"].get("page") == 156), None)
        assert page_156_doc is not None
        assert page_156_doc["type"] == "SourceDoc"
        assert page_156_doc["id"] == "source:page:156"
        assert page_156_doc["properties"]["section"] == "Alchemy Basics"
    
    def test_build_edges(self, graph_builder):
        """Test edge creation between procedure, steps, and sources"""
        
        procedure_info = {"id": "proc:test", "properties": {"name": "Test"}}
        steps_info = [
            {"id": "step:1", "properties": {"step_number": 1, "chunk_id": "chunk:1"}},
            {"id": "step:2", "properties": {"step_number": 2, "chunk_id": "chunk:2"}}
        ]
        source_docs = [
            {"id": "source:page:156", "properties": {"page": 156}}
        ]
        
        edges = graph_builder._build_edges(procedure_info, steps_info, source_docs)
        
        # Verify edge structure
        assert len(edges) > 0
        
        # Check for part_of relationships (procedure -> steps)
        part_of_edges = [e for e in edges if e[1] == "part_of"]
        assert len(part_of_edges) == 2  # One for each step
        
        # Check for prereq relationships (step sequence)
        prereq_edges = [e for e in edges if e[1] == "prereq"]
        assert len(prereq_edges) == 1  # Step 2 prereq Step 1
        
        # Check for citation relationships
        cite_edges = [e for e in edges if e[1] == "cites"]
        assert len(cite_edges) >= 2  # Steps cite sources
    
    def test_build_procedure_from_chunks_complete(self, graph_builder, craft_potion_chunks):
        """Test complete procedure building workflow"""
        
        result = graph_builder.build_procedure_from_chunks(craft_potion_chunks)
        
        # Verify complete result structure
        assert result.procedure["type"] == "Procedure"
        assert len(result.steps) >= 4
        assert len(result.edges) > 0
        assert len(result.source_docs) >= 2
        
        # Verify procedure properties
        proc_props = result.procedure["properties"]
        assert "healing" in proc_props["name"].lower()
        assert proc_props["procedure_type"] == "crafting"
        
        # Verify steps are ordered
        step_numbers = [step["properties"]["step_number"] for step in result.steps]
        assert step_numbers == sorted(step_numbers)  # Should be in order
    
    def test_extract_entities_from_enriched_chunks(self, graph_builder):
        """Test entity extraction from enriched chunk metadata"""
        
        enriched_chunk = {
            "id": "chunk:enriched:1",
            "content": "The wizard casts fireball at the dragon.",
            "metadata": {
                "entities": [
                    {"name": "Wizard", "type": "character_class", "description": "Spellcasting class"},
                    {"name": "Dragon", "type": "creature", "description": "Large magical beast"},
                    {"name": "Fireball", "type": "spell", "description": "3rd level evocation spell"}
                ]
            }
        }
        
        entities = graph_builder._extract_entities(enriched_chunk)
        
        assert len(entities) == 3
        
        # Check wizard entity
        wizard_entity = next((e for e in entities if e["properties"]["name"] == "Wizard"), None)
        assert wizard_entity is not None
        assert wizard_entity["properties"]["type"] == "character_class"
        assert wizard_entity["id"].startswith("entity:")
    
    def test_extract_concepts_from_categories(self, graph_builder):
        """Test concept extraction from chunk categories"""
        
        categorized_chunk = {
            "id": "chunk:categorized:1",
            "content": "Combat mechanics and initiative rules.",
            "metadata": {
                "categories": ["combat", "initiative", "turn_order", "mechanics"]
            }
        }
        
        concepts = graph_builder._extract_concepts(categorized_chunk)
        
        assert len(concepts) == 4
        
        # Verify concept structure
        combat_concept = next((c for c in concepts if c["properties"]["name"] == "combat"), None)
        assert combat_concept is not None
        assert combat_concept["properties"]["category"] == "gameplay_concept"
        assert combat_concept["id"].startswith("concept:")
    
    def test_extract_rules_with_patterns(self, graph_builder):
        """Test rule extraction using pattern matching"""
        
        rules_chunk = {
            "id": "chunk:rules:1",
            "content": "The DC 15 Perception check must be made to notice the trap. Roll 2d6+3 for damage. You cannot attack twice in one turn.",
        }
        
        rules = graph_builder._extract_rules(rules_chunk)
        
        assert len(rules) >= 2  # Should find DC and dice notation
        
        # Check for DC rule
        dc_rule = next((r for r in rules if "DC 15" in r["properties"]["text"]), None)
        assert dc_rule is not None
        assert dc_rule["properties"]["rule_type"] == "mechanical"
        
        # Check for dice rule
        dice_rule = next((r for r in rules if "2d6+3" in r["properties"]["text"]), None)
        assert dice_rule is not None
    
    def test_build_knowledge_graph_from_chunks(self, graph_builder):
        """Test complete knowledge graph building from enriched chunks"""
        
        enriched_chunks = [
            {
                "id": "chunk:kg:1",
                "content": "Fireball is a 3rd level evocation spell that deals fire damage.",
                "metadata": {
                    "entities": [
                        {"name": "Fireball", "type": "spell", "description": "Evocation spell"}
                    ],
                    "categories": ["spells", "evocation", "fire"],
                    "page": 241
                }
            },
            {
                "id": "chunk:kg:2", 
                "content": "DC 15 Dexterity save or take 8d6 fire damage.",
                "metadata": {
                    "entities": [
                        {"name": "Dexterity Save", "type": "game_mechanic", "description": "Saving throw"}
                    ],
                    "page": 241
                }
            }
        ]
        
        result = graph_builder.build_knowledge_graph_from_chunks(enriched_chunks)
        
        # Verify knowledge graph construction
        assert result["nodes_created"] >= 4  # Entities + concepts + source docs
        assert result["edges_created"] >= 2  # Citation edges
        assert len(result["nodes"]) == result["nodes_created"]
        assert len(result["edges"]) == result["edges_created"]
    
    def test_convenience_function(self, craft_potion_chunks):
        """Test convenience function for API compatibility"""
        
        result = build_procedure_from_chunks(craft_potion_chunks)
        
        # Verify API-compatible format
        assert "procedure" in result
        assert "steps" in result 
        assert "edges" in result
        
        assert result["procedure"]["type"] == "Procedure"
        assert len(result["steps"]) >= 4
        assert len(result["edges"]) > 0
    
    def test_stable_id_generation(self, graph_builder):
        """Test that same content generates same IDs (deterministic)"""
        
        chunks1 = [{"id": "c1", "content": "Craft healing potion procedure"}]
        chunks2 = [{"id": "c2", "content": "Craft healing potion procedure"}]
        
        proc1 = graph_builder._detect_procedure(chunks1)
        proc2 = graph_builder._detect_procedure(chunks2)
        
        # Same content should generate same procedure ID
        assert proc1["id"] == proc2["id"]
        assert proc1["properties"]["name"] == proc2["properties"]["name"]
    
    def test_duplicate_detection(self, graph_builder):
        """Test handling of duplicate entities and concepts"""
        
        chunks_with_duplicates = [
            {
                "id": "chunk:dup:1",
                "metadata": {
                    "entities": [
                        {"name": "Fireball", "type": "spell"},
                        {"name": "Fireball", "type": "spell"}  # Duplicate
                    ]
                }
            }
        ]
        
        # Build knowledge graph
        result = graph_builder.build_knowledge_graph_from_chunks(chunks_with_duplicates)
        
        # Should handle duplicates gracefully (upsert should merge)
        assert result["nodes_created"] >= 1
        
        # Verify no duplicate nodes in graph store
        fireball_nodes = [
            node for node in result["nodes"] 
            if node.get("properties", {}).get("name") == "Fireball"
        ]
        
        # Should only have one unique fireball node due to ID collision handling
        assert len(set(node["id"] for node in fireball_nodes)) == 1
    
    def test_error_handling_empty_chunks(self, graph_builder):
        """Test error handling with empty or invalid chunks"""
        
        # Test with empty chunks
        empty_result = graph_builder.build_procedure_from_chunks([])
        
        assert empty_result.procedure["type"] == "Procedure"
        assert empty_result.procedure["properties"]["name"] == "Unknown Procedure"
        assert len(empty_result.steps) == 0
        assert len(empty_result.edges) == 0
        
        # Test with malformed chunks
        bad_chunks = [{"not_valid": "missing required fields"}]
        bad_result = graph_builder.build_procedure_from_chunks(bad_chunks)
        
        assert bad_result.procedure["type"] == "Procedure"  # Should still create valid structure
    
    def test_chunk_type_detection(self, graph_builder):
        """Test detection of different chunk types and content patterns"""
        
        # Character creation chunks
        char_chunks = [
            {"id": "c1", "content": "How to build a character: First, choose your ancestry and background."},
            {"id": "c2", "content": "Step 1: Select ability scores. Step 2: Pick your class features."}
        ]
        
        char_procedure = graph_builder._detect_procedure(char_chunks)
        assert char_procedure["properties"]["procedure_type"] == "character_creation"
        
        # General procedure chunks
        general_chunks = [
            {"id": "c1", "content": "The process of resolving combat actions in initiative order."}
        ]
        
        general_procedure = graph_builder._detect_procedure(general_chunks)
        assert general_procedure["properties"]["procedure_type"] == "general"
    
    def test_step_extraction_patterns(self, graph_builder):
        """Test various step extraction patterns"""
        
        procedure_info = {"id": "proc:test", "properties": {"name": "Test"}}
        
        # Test different step formats
        pattern_chunks = [
            {
                "id": "chunk:patterns:1",
                "content": "1. First do this task. 2. Then do that task. 3. Finally complete the work."
            },
            {
                "id": "chunk:patterns:2", 
                "content": "First, gather materials. Next, prepare workspace. Then, execute procedure. Finally, clean up."
            },
            {
                "id": "chunk:patterns:3",
                "content": "Step 1: Initial setup. Step 2: Main execution. Step 3: Verification."
            }
        ]
        
        steps = graph_builder._extract_steps(pattern_chunks, procedure_info)
        
        # Should extract steps from all pattern types
        assert len(steps) >= 6  # Multiple patterns should all be detected
        
        # Verify step ordering
        step_numbers = [s["properties"]["step_number"] for s in steps]
        assert all(isinstance(num, int) for num in step_numbers)
    
    def test_rule_pattern_extraction(self, graph_builder):
        """Test extraction of different rule patterns"""
        
        rules_chunk = {
            "id": "chunk:rules:complex",
            "content": """
            The creature must make a DC 18 Constitution save or be stunned.
            Roll 3d8+5 fire damage on a hit.
            You cannot move more than your speed in one turn.
            The spell always requires a material component.
            Characters may not cast spells while unconscious.
            """
        }
        
        rules = graph_builder._extract_rules(rules_chunk)
        
        # Should extract multiple rule types
        assert len(rules) >= 3
        
        # Check for different rule patterns
        dc_rules = [r for r in rules if "DC" in r["properties"]["text"]]
        dice_rules = [r for r in rules if "d" in r["properties"]["text"] and "+" in r["properties"]["text"]]
        constraint_rules = [r for r in rules if "cannot" in r["properties"]["text"] or "may not" in r["properties"]["text"]]
        
        assert len(dc_rules) >= 1
        assert len(dice_rules) >= 1  
        assert len(constraint_rules) >= 1
    
    def test_source_doc_metadata_handling(self, graph_builder):
        """Test source document creation with various metadata"""
        
        varied_chunks = [
            {
                "id": "chunk:meta:1",
                "content": "Content from page",
                "metadata": {"page": 42, "section": "Rules Section"}
            },
            {
                "id": "chunk:meta:2",
                "content": "Content from section only", 
                "metadata": {"section": "Another Section"}
            },
            {
                "id": "chunk:meta:3",
                "content": "Content with no metadata",
                "metadata": {}
            }
        ]
        
        source_docs = graph_builder._build_source_docs(varied_chunks)
        
        # Should handle all metadata scenarios
        assert len(source_docs) >= 2  # At least page and section sources
        
        # Page-based source
        page_source = next((doc for doc in source_docs if doc["id"] == "source:page:42"), None)
        assert page_source is not None
        assert page_source["properties"]["page"] == 42
        
        # Section-based source
        section_sources = [doc for doc in source_docs if doc["id"].startswith("source:section:")]
        assert len(section_sources) >= 1
    
    def test_content_length_limits(self, graph_builder):
        """Test handling of very long content"""
        
        long_content_chunk = {
            "id": "chunk:long",
            "content": "Very long step description: " + "A" * 2000,  # Very long content
            "metadata": {"page": 999}
        }
        
        procedure_info = {"id": "proc:long", "properties": {"name": "Long Test"}}
        steps = graph_builder._extract_steps([long_content_chunk], procedure_info)
        
        if steps:
            # Step name should be truncated to reasonable length
            step_name = steps[0]["properties"]["name"]
            assert len(step_name) <= 100  # Should be limited per implementation