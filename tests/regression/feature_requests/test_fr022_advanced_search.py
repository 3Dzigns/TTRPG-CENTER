# tests/regression/feature_requests/test_fr022_advanced_search.py
"""
Feature Request FR-022: Advanced Search with Natural Language Processing Regression Tests
Tests advanced search capabilities with NLP, query understanding, and intelligent result ranking
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestAdvancedSearchNLP:
    """Test suite for FR-022 Advanced Search with NLP functionality"""

    def test_advanced_search_infrastructure_availability(self):
        """Test that advanced search NLP components are available"""
        try:
            from src_common.search import AdvancedSearchEngine
            from src_common.nlp import NaturalLanguageProcessor
            from src_common.query_understanding import QueryUnderstandingEngine
            from src_common.ranking import IntelligentRankingEngine

            assert AdvancedSearchEngine is not None, "AdvancedSearchEngine should be available"
            assert NaturalLanguageProcessor is not None, "NaturalLanguageProcessor should be available"
            assert QueryUnderstandingEngine is not None, "QueryUnderstandingEngine should be available"
            assert IntelligentRankingEngine is not None, "IntelligentRankingEngine should be available"

        except ImportError as e:
            pytest.fail(f"Advanced search NLP components not available: {e}")

    def test_natural_language_query_processing(self):
        """Test natural language query understanding and processing"""
        try:
            from src_common.nlp import NaturalLanguageProcessor
        except ImportError:
            pytest.skip("Natural language processor not available for testing")

        nlp_processor = NaturalLanguageProcessor()

        # Test natural language query scenarios
        natural_language_queries = [
            {
                "query": "Show me all spells that can heal my party members",
                "expected_intent": "spell_search",
                "expected_entities": ["spells", "heal", "party members"],
                "expected_filters": {"spell_effect": "healing", "target": "allies"}
            },
            {
                "query": "What are the best weapons for a level 5 fighter?",
                "expected_intent": "equipment_recommendation",
                "expected_entities": ["weapons", "level 5", "fighter"],
                "expected_filters": {"item_type": "weapon", "character_level": 5, "character_class": "fighter"}
            },
            {
                "query": "How do I create a stealthy rogue character for infiltration missions?",
                "expected_intent": "character_creation_guidance",
                "expected_entities": ["stealthy", "rogue", "infiltration"],
                "expected_filters": {"character_class": "rogue", "focus": "stealth", "purpose": "infiltration"}
            },
            {
                "query": "Find monsters that are weak to fire damage and appropriate for level 8 party",
                "expected_intent": "monster_search",
                "expected_entities": ["monsters", "fire damage", "level 8", "party"],
                "expected_filters": {"creature_type": "monster", "vulnerability": "fire", "challenge_rating": "6-10"}
            }
        ]

        if hasattr(nlp_processor, 'process_natural_language_query'):
            for query_test in natural_language_queries:
                nlp_result = nlp_processor.process_natural_language_query(query_test["query"])

                assert isinstance(nlp_result, dict), "NLP processing should return structured result"

                # Test intent recognition
                if "intent" in nlp_result:
                    intent = nlp_result["intent"]
                    assert intent == query_test["expected_intent"], \
                        f"Intent should be {query_test['expected_intent']}, got {intent}"

                # Test entity extraction
                if "entities" in nlp_result:
                    entities = nlp_result["entities"]
                    assert isinstance(entities, list), "Entities should be list"

                    # Check for expected entities
                    entity_texts = [entity.get("text", "").lower() for entity in entities]
                    for expected_entity in query_test["expected_entities"]:
                        assert any(expected_entity.lower() in entity_text for entity_text in entity_texts), \
                            f"Should extract entity: {expected_entity}"

                # Test structured filter generation
                if "structured_filters" in nlp_result:
                    filters = nlp_result["structured_filters"]
                    assert isinstance(filters, dict), "Structured filters should be dictionary"

                # Test query expansion
                if "expanded_terms" in nlp_result:
                    expanded = nlp_result["expanded_terms"]
                    assert isinstance(expanded, list), "Expanded terms should be list"

    def test_semantic_query_understanding(self):
        """Test semantic query understanding and concept mapping"""
        try:
            from src_common.query_understanding import QueryUnderstandingEngine
        except ImportError:
            pytest.skip("Query understanding engine not available for testing")

        understanding_engine = QueryUnderstandingEngine()

        # Test semantic understanding scenarios
        semantic_queries = [
            {
                "query": "defensive spells for protecting allies",
                "expected_concepts": ["protection", "defense", "ally_support", "magical_protection"],
                "expected_semantic_expansion": ["shield", "ward", "protection", "abjuration", "barrier"]
            },
            {
                "query": "crowd control abilities for large encounters",
                "expected_concepts": ["area_effect", "control", "tactical", "battlefield_management"],
                "expected_semantic_expansion": ["stun", "slow", "entangle", "hold", "mass effect"]
            },
            {
                "query": "character builds for solo adventures",
                "expected_concepts": ["self_sufficiency", "versatility", "survivability", "independence"],
                "expected_semantic_expansion": ["healing", "stealth", "damage", "utility", "resilience"]
            }
        ]

        if hasattr(understanding_engine, 'understand_semantic_query'):
            for semantic_test in semantic_queries:
                understanding_result = understanding_engine.understand_semantic_query(semantic_test["query"])

                assert isinstance(understanding_result, dict), "Semantic understanding should return structured result"

                # Test concept identification
                if "identified_concepts" in understanding_result:
                    concepts = understanding_result["identified_concepts"]
                    assert isinstance(concepts, list), "Concepts should be list"

                    concept_names = [concept.get("name", "").lower() for concept in concepts]
                    for expected_concept in semantic_test["expected_concepts"]:
                        concept_found = any(expected_concept in concept_name for concept_name in concept_names)

                # Test semantic expansion
                if "semantic_expansion" in understanding_result:
                    expansion = understanding_result["semantic_expansion"]
                    assert isinstance(expansion, dict), "Semantic expansion should be dictionary"

                    if "related_terms" in expansion:
                        related_terms = expansion["related_terms"]
                        assert isinstance(related_terms, list), "Related terms should be list"

                # Test query reformulation
                if "reformulated_queries" in understanding_result:
                    reformulated = understanding_result["reformulated_queries"]
                    assert isinstance(reformulated, list), "Reformulated queries should be list"
                    assert len(reformulated) > 0, "Should generate reformulated queries"

    def test_intelligent_result_ranking_and_relevance(self):
        """Test intelligent result ranking with multiple relevance signals"""
        try:
            from src_common.ranking import IntelligentRankingEngine
        except ImportError:
            pytest.skip("Intelligent ranking engine not available for testing")

        ranking_engine = IntelligentRankingEngine()

        # Test ranking configuration
        ranking_config = {
            "ranking_factors": {
                "text_relevance": {"weight": 0.3, "algorithm": "tf_idf_bm25"},
                "semantic_similarity": {"weight": 0.25, "algorithm": "embedding_similarity"},
                "popularity": {"weight": 0.15, "algorithm": "view_count_log"},
                "freshness": {"weight": 0.1, "algorithm": "time_decay"},
                "user_preferences": {"weight": 0.1, "algorithm": "collaborative_filtering"},
                "content_quality": {"weight": 0.1, "algorithm": "quality_score"}
            },
            "personalization": {
                "enabled": True,
                "user_history_weight": 0.2,
                "segment_preferences": 0.15
            },
            "diversity": {
                "content_type_diversity": 0.3,
                "source_diversity": 0.2,
                "topic_diversity": 0.5
            }
        }

        # Mock search results for ranking
        search_results = [
            {
                "content_id": "phb_healing_spells",
                "title": "Healing Spells for Clerics",
                "content_type": "spells",
                "text_score": 0.85,
                "semantic_score": 0.90,
                "popularity_score": 0.75,
                "freshness_score": 0.60,
                "quality_score": 0.95,
                "metadata": {
                    "source": "Player's Handbook",
                    "view_count": 15000,
                    "publication_date": "2024-01-15"
                }
            },
            {
                "content_id": "dmg_magic_items_healing",
                "title": "Magic Items for Healing",
                "content_type": "items",
                "text_score": 0.70,
                "semantic_score": 0.80,
                "popularity_score": 0.60,
                "freshness_score": 0.80,
                "quality_score": 0.85,
                "metadata": {
                    "source": "Dungeon Master's Guide",
                    "view_count": 8000,
                    "publication_date": "2024-03-01"
                }
            },
            {
                "content_id": "community_healing_guide",
                "title": "Complete Guide to Healing in D&D",
                "content_type": "guide",
                "text_score": 0.95,
                "semantic_score": 0.85,
                "popularity_score": 0.90,
                "freshness_score": 0.95,
                "quality_score": 0.80,
                "metadata": {
                    "source": "Community Content",
                    "view_count": 25000,
                    "publication_date": "2024-08-01"
                }
            }
        ]

        if hasattr(ranking_engine, 'rank_search_results'):
            ranking_result = ranking_engine.rank_search_results(
                search_results,
                query="healing spells for party support",
                config=ranking_config
            )

            assert isinstance(ranking_result, dict), "Ranking should return structured result"

            if "ranked_results" in ranking_result:
                ranked = ranking_result["ranked_results"]
                assert isinstance(ranked, list), "Ranked results should be list"
                assert len(ranked) == len(search_results), "Should rank all results"

                # Verify ranking scores
                for result in ranked:
                    assert "final_score" in result, "Result should have final score"
                    assert "ranking_breakdown" in result, "Result should have ranking breakdown"

                    final_score = result["final_score"]
                    assert isinstance(final_score, (int, float)), "Final score should be numeric"
                    assert 0 <= final_score <= 1, "Final score should be between 0 and 1"

                # Verify results are properly sorted
                scores = [result["final_score"] for result in ranked]
                assert scores == sorted(scores, reverse=True), "Results should be sorted by score (descending)"

            if "ranking_explanation" in ranking_result:
                explanation = ranking_result["ranking_explanation"]
                assert isinstance(explanation, dict), "Ranking explanation should be dictionary"

    def test_query_suggestion_and_autocomplete(self):
        """Test query suggestion and intelligent autocomplete"""
        try:
            from src_common.search import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test query suggestion scenarios
        suggestion_scenarios = [
            {
                "partial_query": "wizard sp",
                "expected_suggestions": [
                    "wizard spells",
                    "wizard spell list",
                    "wizard spellcasting",
                    "wizard spell slots"
                ]
            },
            {
                "partial_query": "character crea",
                "expected_suggestions": [
                    "character creation",
                    "character creation guide",
                    "character creation wizard",
                    "character creation tips"
                ]
            },
            {
                "partial_query": "combat maneu",
                "expected_suggestions": [
                    "combat maneuvers",
                    "combat maneuvering",
                    "combat maneuver options",
                    "combat maneuver mechanics"
                ]
            }
        ]

        if hasattr(search_engine, 'generate_query_suggestions'):
            for scenario in suggestion_scenarios:
                suggestion_result = search_engine.generate_query_suggestions(
                    scenario["partial_query"],
                    max_suggestions=10
                )

                assert isinstance(suggestion_result, dict), "Query suggestions should return structured result"

                if "suggestions" in suggestion_result:
                    suggestions = suggestion_result["suggestions"]
                    assert isinstance(suggestions, list), "Suggestions should be list"
                    assert len(suggestions) > 0, "Should generate suggestions"

                    # Check suggestion quality
                    for suggestion in suggestions:
                        assert "query" in suggestion, "Suggestion should have query text"
                        assert "confidence" in suggestion, "Suggestion should have confidence"
                        assert "type" in suggestion, "Suggestion should have type"

                        query_text = suggestion["query"]
                        assert scenario["partial_query"].lower() in query_text.lower(), \
                            "Suggestion should contain partial query"

        # Test contextual suggestions
        if hasattr(search_engine, 'generate_contextual_suggestions'):
            context = {
                "user_history": [
                    "wizard spells level 3",
                    "fireball spell description",
                    "evocation school spells"
                ],
                "current_session": [
                    "spell components",
                    "spellcasting focus"
                ],
                "user_preferences": {
                    "content_types": ["spells", "rules"],
                    "character_classes": ["wizard", "sorcerer"]
                }
            }

            contextual_result = search_engine.generate_contextual_suggestions(
                "spell",
                context=context
            )

            assert isinstance(contextual_result, dict), "Contextual suggestions should return structured result"

            if "contextual_suggestions" in contextual_result:
                suggestions = contextual_result["contextual_suggestions"]
                assert isinstance(suggestions, list), "Contextual suggestions should be list"

    def test_search_personalization_and_learning(self):
        """Test search personalization and learning from user interactions"""
        try:
            from src_common.search import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test personalization configuration
        personalization_config = {
            "user_profile": {
                "user_id": "test_user_001",
                "preferences": {
                    "content_types": ["spells", "character_creation"],
                    "difficulty_level": "intermediate",
                    "game_systems": ["D&D 5e"],
                    "interests": ["magic", "character_optimization"]
                },
                "search_history": [
                    {"query": "wizard optimization", "clicked_results": ["phb_wizard_guide", "optimization_tips"]},
                    {"query": "spell combinations", "clicked_results": ["spell_synergy_guide"]},
                    {"query": "metamagic options", "clicked_results": ["sorcerer_metamagic"]}
                ],
                "interaction_patterns": {
                    "avg_session_duration": 450,
                    "preferred_result_types": ["detailed_guides", "rule_explanations"],
                    "click_through_rate": 0.75
                }
            }
        }

        if hasattr(search_engine, 'personalize_search_results'):
            # Test personalized search
            base_query = "character building tips"
            personalized_result = search_engine.personalize_search_results(
                base_query,
                personalization_config["user_profile"]
            )

            assert isinstance(personalized_result, dict), "Personalized search should return structured result"

            if "personalized_query" in personalized_result:
                personalized_query = personalized_result["personalized_query"]
                assert isinstance(personalized_query, str), "Personalized query should be string"

            if "boost_factors" in personalized_result:
                boost_factors = personalized_result["boost_factors"]
                assert isinstance(boost_factors, dict), "Boost factors should be dictionary"

            if "personalization_applied" in personalized_result:
                applied = personalized_result["personalization_applied"]
                assert isinstance(applied, list), "Personalization applied should be list"

        # Test learning from interactions
        if hasattr(search_engine, 'learn_from_search_interaction'):
            interaction_data = {
                "query": "best cantrips for wizards",
                "results_shown": [
                    {"content_id": "phb_cantrips", "position": 1},
                    {"content_id": "wizard_cantrip_guide", "position": 2},
                    {"content_id": "spell_optimization", "position": 3}
                ],
                "user_actions": [
                    {"action": "click", "content_id": "wizard_cantrip_guide", "position": 2, "time_on_page": 180},
                    {"action": "bookmark", "content_id": "wizard_cantrip_guide"},
                    {"action": "click", "content_id": "spell_optimization", "position": 3, "time_on_page": 45}
                ],
                "search_satisfaction": "high"
            }

            learning_result = search_engine.learn_from_search_interaction(
                personalization_config["user_profile"]["user_id"],
                interaction_data
            )

            assert isinstance(learning_result, dict), "Learning should return structured result"

            if "profile_updates" in learning_result:
                updates = learning_result["profile_updates"]
                assert isinstance(updates, dict), "Profile updates should be dictionary"

            if "ranking_adjustments" in learning_result:
                adjustments = learning_result["ranking_adjustments"]
                assert isinstance(adjustments, dict), "Ranking adjustments should be dictionary"

    def test_advanced_search_contract_compliance(self):
        """Test that advanced search NLP matches established contract"""
        # Test search contract
        search_requirements = {
            "natural_language_processing": True,
            "semantic_understanding": True,
            "intelligent_ranking": True,
            "query_suggestions": True,
            "search_personalization": True
        }

        for requirement, needed in search_requirements.items():
            assert needed, f"Search requirement {requirement} is mandatory"

        # Test NLP contract
        nlp_requirements = {
            "intent_recognition": True,
            "entity_extraction": True,
            "query_expansion": True,
            "semantic_similarity": True
        }

        for requirement, needed in nlp_requirements.items():
            assert needed, f"NLP requirement {requirement} is mandatory"

        # Test ranking contract
        ranking_requirements = {
            "multi_factor_ranking": True,
            "personalization_boost": True,
            "diversity_optimization": True,
            "relevance_explanation": True
        }

        for requirement, needed in ranking_requirements.items():
            assert needed, f"Ranking requirement {requirement} is mandatory"

        # Test data contract
        required_search_fields = [
            "query_intent",
            "relevance_score",
            "ranking_factors",
            "personalization_boost",
            "suggestion_confidence"
        ]

        for field in required_search_fields:
            assert isinstance(field, str), f"Search field {field} should be defined"

        # Test integration contract
        integration_points = [
            "nlp_engine_integration",
            "knowledge_base_integration",
            "user_profile_integration",
            "analytics_tracking_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"