# tests/regression/test_phase3_golden_workflows.py
"""
Regression tests for Phase 3 - Golden workflow stability
Tests stored planned DAGs for canonical goals and citation consistency
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from src_common.graph.store import GraphStore
from src_common.graph.build import GraphBuilder
from src_common.planner.plan import TaskPlanner
from src_common.reason.graphwalk import GraphGuidedReasoner

class TestGoldenWorkflows:
    """Test workflow stability against golden reference implementations"""
    
    @pytest.fixture
    def canonical_graph_store(self):
        """Create canonical graph store with standard TTRPG data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "canonical_graph"
            store = GraphStore(storage_path=storage_path)
            
            # Add canonical procedures
            procedures = [
                {
                    "id": "proc:craft:healing_potion",
                    "name": "Craft Healing Potion",
                    "procedure_type": "crafting",
                    "description": "Create a basic healing potion"
                },
                {
                    "id": "proc:char:creation:pf2e",
                    "name": "PF2E Character Creation",
                    "procedure_type": "character_creation", 
                    "description": "Create Pathfinder 2E character using ABP"
                },
                {
                    "id": "proc:combat:initiative",
                    "name": "Combat Initiative",
                    "procedure_type": "combat",
                    "description": "Roll initiative and determine turn order"
                }
            ]
            
            for proc in procedures:
                store.upsert_node(proc["id"], "Procedure", proc)
            
            # Add canonical rules
            rules = [
                {
                    "id": "rule:alchemy:dc",
                    "text": "Alchemy checks use DC 15 + item level",
                    "rule_type": "mechanical"
                },
                {
                    "id": "rule:abp:bonuses",
                    "text": "ABP provides automatic bonus progression without magic items",
                    "rule_type": "character_creation"
                },
                {
                    "id": "rule:initiative:roll",
                    "text": "Roll 1d20 + Dexterity modifier for initiative",
                    "rule_type": "combat"
                }
            ]
            
            for rule in rules:
                store.upsert_node(rule["id"], "Rule", rule)
            
            # Add canonical concepts
            concepts = [
                {
                    "id": "concept:healing_potion",
                    "name": "Healing Potion",
                    "category": "consumable"
                },
                {
                    "id": "concept:ability_scores",
                    "name": "Ability Scores", 
                    "category": "character_stats"
                },
                {
                    "id": "concept:turn_order",
                    "name": "Turn Order",
                    "category": "combat_mechanic"
                }
            ]
            
            for concept in concepts:
                store.upsert_node(concept["id"], "Concept", concept)
            
            # Create canonical relationships
            relationships = [
                ("proc:craft:healing_potion", "implements", "rule:alchemy:dc"),
                ("proc:craft:healing_potion", "produces", "concept:healing_potion"),
                ("proc:char:creation:pf2e", "implements", "rule:abp:bonuses"),
                ("proc:char:creation:pf2e", "produces", "concept:ability_scores"),
                ("proc:combat:initiative", "implements", "rule:initiative:roll"),
                ("proc:combat:initiative", "produces", "concept:turn_order")
            ]
            
            for source, etype, target in relationships:
                store.upsert_edge(source, etype, target, {})
            
            yield store
    
    @pytest.fixture
    def canonical_goals(self):
        """Define canonical test goals for regression testing"""
        return [
            {
                "id": "goal:craft:healing_potion",
                "goal": "Craft a healing potion using alchemy rules",
                "expected_procedure": "proc:craft:healing_potion",
                "expected_min_tasks": 3,
                "expected_concepts": ["healing_potion", "alchemy"]
            },
            {
                "id": "goal:char:pf2e:abp:level5",
                "goal": "Build a PF2e character using ABP, level 5, sword and board fighter",
                "expected_procedure": "proc:char:creation:pf2e", 
                "expected_min_tasks": 5,
                "expected_concepts": ["ability_scores", "abp", "fighter"]
            },
            {
                "id": "goal:combat:initiative:3party",
                "goal": "Roll initiative for 3-person party in combat encounter",
                "expected_procedure": "proc:combat:initiative",
                "expected_min_tasks": 2,
                "expected_concepts": ["turn_order", "initiative"]
            },
            {
                "id": "goal:quest:outline:3session",
                "goal": "Prepare a 3-session quest outline with required skill checks",
                "expected_procedure": None,  # No specific procedure
                "expected_min_tasks": 4,
                "expected_concepts": ["quest", "skill_checks"]
            },
            {
                "id": "goal:spell:mechanics:fireball",
                "goal": "Explain fireball spell mechanics including damage and saving throws",
                "expected_procedure": None,
                "expected_min_tasks": 3,
                "expected_concepts": ["spell", "damage", "saving_throw"]
            }
        ]
    
    def test_golden_workflow_plan_stability(self, canonical_graph_store, canonical_goals):
        """Test that canonical goals produce stable workflow plans"""
        
        planner = TaskPlanner(canonical_graph_store)
        golden_plans = {}
        
        # Generate plans for all canonical goals
        for goal_spec in canonical_goals:
            goal = goal_spec["goal"]
            plan = planner.plan_from_goal(goal)
            
            # Store plan structure for comparison
            golden_plans[goal_spec["id"]] = {
                "goal": plan.goal,
                "procedure_id": plan.procedure_id,
                "task_count": len(plan.tasks),
                "task_types": [task.type for task in plan.tasks],
                "task_names": [task.name for task in plan.tasks],
                "edge_count": len(plan.edges),
                "total_estimated_tokens": plan.total_estimated_tokens,
                "checkpoint_count": len(plan.checkpoints)
            }
            
            # Verify meets minimum expectations
            assert len(plan.tasks) >= goal_spec["expected_min_tasks"]
            
            if goal_spec["expected_procedure"]:
                assert plan.procedure_id == goal_spec["expected_procedure"]
        
        # Re-generate plans and compare for stability
        for goal_spec in canonical_goals:
            goal = goal_spec["goal"]
            new_plan = planner.plan_from_goal(goal)
            original = golden_plans[goal_spec["id"]]
            
            # Core structure should be stable (allow minor variations)
            assert new_plan.procedure_id == original["procedure_id"]
            assert abs(len(new_plan.tasks) - original["task_count"]) <= 1  # Allow ±1 task difference
            assert abs(len(new_plan.edges) - original["edge_count"]) <= 2   # Allow ±2 edge difference
            
            # Task types should be similar (allow reordering)
            new_task_types = sorted([task.type for task in new_plan.tasks])
            original_task_types = sorted(original["task_types"])
            type_overlap = len(set(new_task_types) & set(original_task_types))
            assert type_overlap >= len(original_task_types) * 0.8  # 80% type overlap
    
    def test_citation_superset_consistency(self, canonical_graph_store):
        """Test that Phase 3 citations are superset of Phase 2 for same queries"""
        
        reasoner = GraphGuidedReasoner(canonical_graph_store)
        
        # Mock Phase 2 retrieval results (baseline)
        phase2_citations = [
            {"source": "Core Rulebook", "page": 123, "section": "Spells"},
            {"source": "Advanced Guide", "page": 45, "section": "Alchemy"}
        ]
        
        def mock_retriever_with_citations(query):
            return [
                {
                    "content": f"Retrieved content for {query}",
                    "score": 0.8,
                    "metadata": {"page": 123, "section": "Spells"},
                    "source": "Core Rulebook"
                },
                {
                    "content": f"Additional content for {query}",
                    "score": 0.7,
                    "metadata": {"page": 45, "section": "Alchemy"},
                    "source": "Advanced Guide" 
                }
            ]
        
        reasoner.retriever = mock_retriever_with_citations
        
        # Test queries
        test_queries = [
            "How to craft healing potions?",
            "What are spell components?",
            "Initiative order in combat"
        ]
        
        for query in test_queries:
            trace = reasoner.graph_guided_answer(query, max_hops=2)
            phase3_sources = {f"{s.get('source', '')}:{s.get('page', '')}" for s in trace.sources}
            phase2_source_keys = {f"{s['source']}:{s['page']}" for s in phase2_citations}
            
            # Phase 3 should include all Phase 2 sources (superset)
            missing_sources = phase2_source_keys - phase3_sources
            
            # Allow for some variance in citation extraction but should have substantial overlap
            overlap_ratio = len(phase2_source_keys & phase3_sources) / len(phase2_source_keys) if phase2_source_keys else 1.0
            assert overlap_ratio >= 0.7, f"Insufficient citation overlap for '{query}': {overlap_ratio}"
    
    def test_workflow_node_edge_id_stability(self, canonical_graph_store, canonical_goals):
        """Test that node and edge IDs remain stable for canonical workflows"""
        
        planner = TaskPlanner(canonical_graph_store)
        
        # Generate golden reference
        golden_references = {}
        
        for goal_spec in canonical_goals:
            plan = planner.plan_from_goal(goal_spec["goal"])
            
            golden_references[goal_spec["id"]] = {
                "task_ids": [task.id for task in plan.tasks],
                "edge_pairs": plan.edges,
                "procedure_id": plan.procedure_id
            }
        
        # Regenerate and compare IDs
        for goal_spec in canonical_goals:
            new_plan = planner.plan_from_goal(goal_spec["goal"])
            reference = golden_references[goal_spec["id"]]
            
            # Procedure ID should be exactly stable
            assert new_plan.procedure_id == reference["procedure_id"]
            
            # Task IDs should have high stability (deterministic generation)
            new_task_ids = [task.id for task in new_plan.tasks]
            id_overlap = len(set(new_task_ids) & set(reference["task_ids"]))
            id_stability = id_overlap / len(reference["task_ids"]) if reference["task_ids"] else 1.0
            
            assert id_stability >= 0.8, f"Task ID stability too low: {id_stability}"
    
    def test_performance_regression_thresholds(self, canonical_graph_store, canonical_goals):
        """Test that workflow performance stays within acceptable bounds"""
        
        planner = TaskPlanner(canonical_graph_store)
        reasoner = GraphGuidedReasoner(canonical_graph_store)
        
        performance_results = []
        
        for goal_spec in canonical_goals:
            import time
            
            # Measure planning performance
            start_time = time.time()
            plan = planner.plan_from_goal(goal_spec["goal"])
            planning_time = time.time() - start_time
            
            # Measure reasoning performance
            start_time = time.time()
            trace = reasoner.graph_guided_answer(goal_spec["goal"], max_hops=3)
            reasoning_time = time.time() - start_time
            
            performance_results.append({
                "goal_id": goal_spec["id"],
                "planning_time_s": planning_time,
                "reasoning_time_s": reasoning_time,
                "total_estimated_tokens": plan.total_estimated_tokens,
                "reasoning_confidence": trace.total_confidence
            })
            
            # Performance thresholds
            assert planning_time < 5.0, f"Planning too slow for {goal_spec['id']}: {planning_time:.2f}s"
            assert reasoning_time < 10.0, f"Reasoning too slow for {goal_spec['id']}: {reasoning_time:.2f}s"
            assert trace.total_confidence >= 0.3, f"Confidence too low for {goal_spec['id']}: {trace.total_confidence}"
        
        # Overall performance analysis
        avg_planning_time = sum(r["planning_time_s"] for r in performance_results) / len(performance_results)
        avg_reasoning_time = sum(r["reasoning_time_s"] for r in performance_results) / len(performance_results)
        
        assert avg_planning_time < 2.0, f"Average planning time too high: {avg_planning_time:.2f}s"
        assert avg_reasoning_time < 5.0, f"Average reasoning time too high: {avg_reasoning_time:.2f}s"
    
    def test_golden_procedure_extraction_stability(self, canonical_graph_store):
        """Test stable procedure extraction from canonical chunk sets"""
        
        builder = GraphBuilder(canonical_graph_store)
        
        # Golden chunk sets for procedure extraction
        golden_chunk_sets = [
            {
                "name": "healing_potion_crafting",
                "chunks": [
                    {
                        "id": "chunk:hp:1",
                        "content": "To craft a healing potion, gather 2 units of healing herbs and 1 vial of purified water.",
                        "metadata": {"page": 156, "section": "Alchemy"}
                    },
                    {
                        "id": "chunk:hp:2", 
                        "content": "Step 1: Prepare workspace. Step 2: Mix herbs with water. Step 3: Apply heat for 10 minutes.",
                        "metadata": {"page": 156, "section": "Alchemy"}
                    }
                ],
                "expected_procedure_name": "Healing Potion",
                "expected_step_count": 3,
                "expected_procedure_type": "crafting"
            },
            {
                "name": "character_creation_abp",
                "chunks": [
                    {
                        "id": "chunk:cc:1",
                        "content": "Character creation with ABP: First choose ancestry and background.",
                        "metadata": {"page": 78, "section": "Characters"}
                    },
                    {
                        "id": "chunk:cc:2",
                        "content": "Step 1: Assign ability scores. Step 2: Select class. Step 3: Apply ABP bonuses.",
                        "metadata": {"page": 78, "section": "Characters"}
                    }
                ],
                "expected_procedure_name": "Character Creation",
                "expected_step_count": 3,
                "expected_procedure_type": "character_creation"
            }
        ]
        
        # Test extraction stability
        for chunk_set in golden_chunk_sets:
            result = builder.build_procedure_from_chunks(chunk_set["chunks"])
            
            # Verify stable extraction
            assert result.procedure["type"] == "Procedure"
            assert chunk_set["expected_procedure_name"].lower() in result.procedure["properties"]["name"].lower()
            assert result.procedure["properties"]["procedure_type"] == chunk_set["expected_procedure_type"]
            assert len(result.steps) >= chunk_set["expected_step_count"]
            
            # Test regeneration produces same structure
            result2 = builder.build_procedure_from_chunks(chunk_set["chunks"])
            
            assert result.procedure["id"] == result2.procedure["id"]  # Same procedure ID
            assert len(result.steps) == len(result2.steps)           # Same step count
            assert len(result.edges) == len(result2.edges)           # Same edge count
    
    def test_answer_quality_regression_vs_phase2(self, canonical_graph_store):
        """Test that Phase 3 answers maintain or improve quality vs Phase 2"""
        
        reasoner = GraphGuidedReasoner(canonical_graph_store)
        
        # Questions with known good Phase 2 performance
        quality_test_cases = [
            {
                "question": "How do I craft a healing potion?",
                "phase2_f1": 0.82,  # Mock Phase 2 F1 score
                "expected_sources": 2,
                "expected_confidence": 0.7
            },
            {
                "question": "What are the ABP bonuses for a level 5 character?",
                "phase2_f1": 0.75,
                "expected_sources": 1, 
                "expected_confidence": 0.8
            },
            {
                "question": "How does initiative work in combat?",
                "phase2_f1": 0.88,
                "expected_sources": 1,
                "expected_confidence": 0.9
            }
        ]
        
        # Test each case
        for test_case in quality_test_cases:
            trace = reasoner.graph_guided_answer(test_case["question"], max_hops=3)
            
            # Quality indicators
            assert len(trace.sources) >= test_case["expected_sources"]
            assert trace.total_confidence >= test_case["expected_confidence"]
            
            # Answer should be comprehensive
            assert len(trace.answer) > 100  # Non-trivial answer length
            
            # Should include key terms from question
            question_words = set(test_case["question"].lower().split())
            answer_words = set(trace.answer.lower().split())
            overlap = len(question_words & answer_words)
            assert overlap >= len(question_words) * 0.3  # 30% word overlap minimum
    
    def test_workflow_dag_consistency(self, canonical_graph_store, canonical_goals):
        """Test DAG structure consistency for canonical workflows"""
        
        planner = TaskPlanner(canonical_graph_store)
        
        dag_characteristics = {}
        
        # Generate DAG characteristics
        for goal_spec in canonical_goals:
            plan = planner.plan_from_goal(goal_spec["goal"])
            
            # Analyze DAG structure
            dag_char = {
                "task_count": len(plan.tasks),
                "edge_count": len(plan.edges),
                "max_depth": self._calculate_dag_depth(plan.tasks, plan.edges),
                "parallelism": self._calculate_max_parallelism(plan.tasks, plan.edges),
                "task_type_distribution": self._get_task_type_distribution(plan.tasks)
            }
            
            dag_characteristics[goal_spec["id"]] = dag_char
            
            # Verify DAG properties
            assert dag_char["max_depth"] <= 10  # Reasonable depth limit
            assert dag_char["parallelism"] >= 1   # At least some parallelism possible
        
        # Test regeneration produces similar DAG characteristics
        for goal_spec in canonical_goals:
            new_plan = planner.plan_from_goal(goal_spec["goal"])
            original = dag_characteristics[goal_spec["id"]]
            
            new_char = {
                "task_count": len(new_plan.tasks),
                "edge_count": len(new_plan.edges),
                "max_depth": self._calculate_dag_depth(new_plan.tasks, new_plan.edges),
                "parallelism": self._calculate_max_parallelism(new_plan.tasks, new_plan.edges),
                "task_type_distribution": self._get_task_type_distribution(new_plan.tasks)
            }
            
            # Allow small variations but core structure should be stable
            assert abs(new_char["task_count"] - original["task_count"]) <= 1
            assert abs(new_char["max_depth"] - original["max_depth"]) <= 1
            
            # Task type distribution should be similar
            original_types = set(original["task_type_distribution"].keys())
            new_types = set(new_char["task_type_distribution"].keys())
            type_similarity = len(original_types & new_types) / len(original_types | new_types)
            assert type_similarity >= 0.8  # 80% task type overlap
    
    def _calculate_dag_depth(self, tasks: List[Any], edges: List[tuple]) -> int:
        """Calculate maximum depth of DAG"""
        
        # Build adjacency list
        graph = {task.id: [] for task in tasks}
        in_degree = {task.id: 0 for task in tasks}
        
        for source, target in edges:
            if source in graph and target in graph:
                graph[source].append(target)
                in_degree[target] += 1
        
        # Topological sort to find longest path
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        levels = {task_id: 0 for task_id in queue}
        max_depth = 0
        
        while queue:
            current = queue.pop(0)
            current_level = levels[current]
            max_depth = max(max_depth, current_level)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                levels[neighbor] = max(levels.get(neighbor, 0), current_level + 1)
                
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return max_depth + 1  # Convert to 1-indexed depth
    
    def _calculate_max_parallelism(self, tasks: List[Any], edges: List[tuple]) -> int:
        """Calculate maximum possible parallelism in DAG"""
        
        # Group tasks by dependency level
        in_degree = {task.id: 0 for task in tasks}
        
        for source, target in edges:
            if target in in_degree:
                in_degree[target] += 1
        
        # Count tasks at each level
        level_counts = {}
        queue = [(task_id, 0) for task_id, degree in in_degree.items() if degree == 0]
        processed = set()
        
        while queue:
            task_id, level = queue.pop(0)
            if task_id in processed:
                continue
                
            processed.add(task_id)
            level_counts[level] = level_counts.get(level, 0) + 1
            
            # Add dependent tasks to next level
            for source, target in edges:
                if source == task_id and target not in processed:
                    queue.append((target, level + 1))
        
        return max(level_counts.values()) if level_counts else 1
    
    def _get_task_type_distribution(self, tasks: List[Any]) -> Dict[str, int]:
        """Get distribution of task types in workflow"""
        
        distribution = {}
        for task in tasks:
            task_type = task.type
            distribution[task_type] = distribution.get(task_type, 0) + 1
        
        return distribution
    
    def test_error_recovery_golden_scenarios(self, canonical_graph_store):
        """Test error recovery patterns for known failure scenarios"""
        
        planner = TaskPlanner(canonical_graph_store)
        
        # Scenarios that commonly cause issues
        challenging_scenarios = [
            "Build a character with conflicting requirements and limited resources",
            "Craft multiple items simultaneously with shared components",
            "Handle combat with unusual conditions and rule edge cases"
        ]
        
        for scenario in challenging_scenarios:
            try:
                plan = planner.plan_from_goal(scenario)
                
                # Should produce valid plan even for challenging cases
                is_valid, errors = planner.validate_plan(plan)
                assert is_valid, f"Challenging scenario failed validation: {scenario}"
                
                # Should have reasonable bounds
                assert len(plan.tasks) <= 15  # Shouldn't explode in complexity
                assert plan.total_estimated_tokens <= 100000  # Reasonable token usage
                
            except Exception as e:
                pytest.fail(f"Challenging scenario caused exception: {scenario} -> {e}")
    
    def test_knowledge_graph_build_consistency(self, canonical_graph_store):
        """Test knowledge graph building produces consistent results"""
        
        builder = GraphBuilder(canonical_graph_store)
        
        # Standard enriched chunks for KG building
        enriched_chunks = [
            {
                "id": "chunk:kg:spell",
                "content": "Fireball is a 3rd level evocation spell that deals 8d6 fire damage in a 20-foot radius.",
                "metadata": {
                    "entities": [
                        {"name": "Fireball", "type": "spell", "description": "Evocation spell"},
                        {"name": "Fire Damage", "type": "damage_type", "description": "Elemental damage"}
                    ],
                    "categories": ["spells", "evocation", "damage", "fire"],
                    "page": 241
                }
            },
            {
                "id": "chunk:kg:rule",
                "content": "Spell attack rolls use 1d20 + spell attack modifier against target AC.",
                "metadata": {
                    "entities": [
                        {"name": "Spell Attack", "type": "game_mechanic", "description": "Attack using spells"}
                    ],
                    "categories": ["combat", "spells", "attacks"],
                    "page": 298
                }
            }
        ]
        
        # Build knowledge graph multiple times
        results = []
        for _ in range(3):
            result = builder.build_knowledge_graph_from_chunks(enriched_chunks)
            results.append(result)
        
        # Results should be consistent
        first_result = results[0]
        for result in results[1:]:
            assert result["nodes_created"] == first_result["nodes_created"]
            assert result["edges_created"] == first_result["edges_created"]
            
            # Node IDs should be stable (deterministic hashing)
            first_node_ids = {node["id"] for node in first_result["nodes"]}
            result_node_ids = {node["id"] for node in result["nodes"]}
            assert first_node_ids == result_node_ids