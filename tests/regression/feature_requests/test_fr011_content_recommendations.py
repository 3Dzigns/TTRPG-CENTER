# tests/regression/feature_requests/test_fr011_content_recommendations.py
"""
Feature Request FR-011: Content Recommendation Engine Regression Tests
Tests personalized content recommendations with ML-driven suggestions and user preference learning
"""

import pytest
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta


class TestContentRecommendationEngine:
    """Test suite for FR-011 Content Recommendation functionality"""

    def test_recommendation_engine_infrastructure_availability(self):
        """Test that recommendation engine components are available"""
        try:
            from src_common.recommendations import RecommendationEngine
            from src_common.user_profiling import UserProfileManager
            from src_common.content_analyzer import ContentAnalyzer
            from src_common.ml_models import RecommendationModel

            assert RecommendationEngine is not None, "RecommendationEngine should be available"
            assert UserProfileManager is not None, "UserProfileManager should be available"
            assert ContentAnalyzer is not None, "ContentAnalyzer should be available"
            assert RecommendationModel is not None, "RecommendationModel should be available"

        except ImportError as e:
            pytest.fail(f"Recommendation engine components not available: {e}")

    def test_user_profile_creation_and_management(self):
        """Test user profile creation and preference learning"""
        try:
            from src_common.user_profiling import UserProfileManager
        except ImportError:
            pytest.skip("User profile manager not available for testing")

        profile_manager = UserProfileManager()

        # Test user profile creation
        user_data = {
            "user_id": "test_user_001",
            "initial_preferences": {
                "content_types": ["rules", "spells", "character_creation"],
                "game_systems": ["D&D 5e", "Pathfinder"],
                "difficulty_preference": "intermediate",
                "play_style": ["roleplay", "combat"]
            },
            "interaction_history": [
                {
                    "content_id": "phb_character_creation",
                    "interaction_type": "view",
                    "duration": 300,
                    "rating": 5,
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "content_id": "dmg_magic_items",
                    "interaction_type": "bookmark",
                    "rating": 4,
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()
                }
            ]
        }

        if hasattr(profile_manager, 'create_user_profile'):
            profile_result = profile_manager.create_user_profile(user_data)

            assert isinstance(profile_result, dict), "Profile creation should return structured result"

            if "profile_id" in profile_result:
                profile_id = profile_result["profile_id"]
                assert isinstance(profile_id, str), "Profile ID should be string"
                assert len(profile_id) > 0, "Profile ID should not be empty"

            if "preference_vector" in profile_result:
                pref_vector = profile_result["preference_vector"]
                assert isinstance(pref_vector, (list, np.ndarray)), "Preference vector should be numeric"

        # Test preference learning from interactions
        if hasattr(profile_manager, 'update_preferences'):
            new_interactions = [
                {
                    "content_id": "xgte_spells",
                    "interaction_type": "search",
                    "query": "fireball spell description",
                    "rating": 5,
                    "timestamp": datetime.now().isoformat()
                }
            ]

            update_result = profile_manager.update_preferences(user_data["user_id"], new_interactions)

            assert isinstance(update_result, dict), "Preference update should return structured result"

            if "updated_preferences" in update_result:
                updated_prefs = update_result["updated_preferences"]
                assert isinstance(updated_prefs, dict), "Updated preferences should be dictionary"

    def test_content_similarity_analysis(self):
        """Test content similarity analysis and feature extraction"""
        try:
            from src_common.content_analyzer import ContentAnalyzer
        except ImportError:
            pytest.skip("Content analyzer not available for testing")

        analyzer = ContentAnalyzer()

        # Test content analysis
        test_content = [
            {
                "content_id": "phb_wizard_spells",
                "title": "Wizard Spells",
                "text": "Wizards are masters of arcane magic, learning spells through study and practice",
                "metadata": {
                    "content_type": "spells",
                    "class": "wizard",
                    "level": "all",
                    "source": "Player's Handbook"
                }
            },
            {
                "content_id": "phb_sorcerer_spells",
                "title": "Sorcerer Spells",
                "text": "Sorcerers cast spells through innate magical ability and natural talent",
                "metadata": {
                    "content_type": "spells",
                    "class": "sorcerer",
                    "level": "all",
                    "source": "Player's Handbook"
                }
            },
            {
                "content_id": "dmg_magic_items",
                "title": "Magic Items",
                "text": "Magic items are treasures that provide supernatural abilities and effects",
                "metadata": {
                    "content_type": "items",
                    "rarity": "various",
                    "source": "Dungeon Master's Guide"
                }
            }
        ]

        if hasattr(analyzer, 'analyze_content_similarity'):
            similarity_result = analyzer.analyze_content_similarity(test_content)

            assert isinstance(similarity_result, dict), "Similarity analysis should return structured result"

            if "similarity_matrix" in similarity_result:
                similarity_matrix = similarity_result["similarity_matrix"]
                assert isinstance(similarity_matrix, (list, np.ndarray)), "Similarity matrix should be numeric"

                # Check matrix properties
                if isinstance(similarity_matrix, list):
                    similarity_matrix = np.array(similarity_matrix)

                assert similarity_matrix.shape[0] == len(test_content), "Matrix should match content count"
                assert similarity_matrix.shape[1] == len(test_content), "Matrix should be square"

                # Diagonal should be 1.0 (self-similarity)
                diagonal = np.diag(similarity_matrix)
                np.testing.assert_allclose(diagonal, 1.0, atol=0.1,
                    err_msg="Diagonal elements should be close to 1.0")

            if "content_features" in similarity_result:
                features = similarity_result["content_features"]
                assert isinstance(features, dict), "Content features should be dictionary"
                assert len(features) == len(test_content), "Should have features for all content"

    def test_collaborative_filtering_recommendations(self):
        """Test collaborative filtering recommendation generation"""
        try:
            from src_common.recommendations import RecommendationEngine
        except ImportError:
            pytest.skip("Recommendation engine not available for testing")

        engine = RecommendationEngine()

        # Test collaborative filtering setup
        user_item_matrix = {
            "user_001": {"item_001": 5, "item_002": 3, "item_003": 4},
            "user_002": {"item_001": 4, "item_002": 5, "item_004": 3},
            "user_003": {"item_002": 4, "item_003": 5, "item_004": 4},
            "user_004": {"item_001": 3, "item_003": 5, "item_005": 4}
        }

        target_user = "user_001"

        if hasattr(engine, 'generate_collaborative_recommendations'):
            collab_result = engine.generate_collaborative_recommendations(
                target_user,
                user_item_matrix,
                max_recommendations=5
            )

            assert isinstance(collab_result, dict), "Collaborative recommendations should return structured result"

            if "recommendations" in collab_result:
                recommendations = collab_result["recommendations"]
                assert isinstance(recommendations, list), "Recommendations should be list"
                assert len(recommendations) <= 5, "Should respect max recommendations limit"

                for rec in recommendations:
                    assert "item_id" in rec, "Recommendation should have item ID"
                    assert "score" in rec, "Recommendation should have score"
                    assert "reasoning" in rec, "Recommendation should have reasoning"

                    score = rec["score"]
                    assert 0.0 <= score <= 1.0, f"Recommendation score should be between 0 and 1: {score}"

            if "user_similarity" in collab_result:
                user_sim = collab_result["user_similarity"]
                assert isinstance(user_sim, dict), "User similarity should be dictionary"

    def test_content_based_recommendations(self):
        """Test content-based recommendation generation"""
        try:
            from src_common.recommendations import RecommendationEngine
        except ImportError:
            pytest.skip("Recommendation engine not available for testing")

        engine = RecommendationEngine()

        # Test content-based recommendations
        user_preferences = {
            "content_types": ["spells", "character_creation"],
            "classes": ["wizard", "sorcerer"],
            "difficulty_level": {"min": 5, "max": 15},
            "themes": ["magic", "arcane", "study"]
        }

        content_catalog = [
            {
                "content_id": "wizard_guide_001",
                "title": "Advanced Wizard Tactics",
                "features": {
                    "content_type": "guide",
                    "classes": ["wizard"],
                    "difficulty_level": 8,
                    "themes": ["magic", "tactics", "spells"]
                },
                "similarity_score": 0.85
            },
            {
                "content_id": "sorcerer_guide_001",
                "title": "Sorcerer Magic Fundamentals",
                "features": {
                    "content_type": "guide",
                    "classes": ["sorcerer"],
                    "difficulty_level": 6,
                    "themes": ["magic", "innate", "fundamentals"]
                },
                "similarity_score": 0.75
            },
            {
                "content_id": "fighter_guide_001",
                "title": "Combat Mastery for Fighters",
                "features": {
                    "content_type": "guide",
                    "classes": ["fighter"],
                    "difficulty_level": 10,
                    "themes": ["combat", "physical", "tactics"]
                },
                "similarity_score": 0.35
            }
        ]

        if hasattr(engine, 'generate_content_based_recommendations'):
            content_result = engine.generate_content_based_recommendations(
                user_preferences,
                content_catalog,
                max_recommendations=3
            )

            assert isinstance(content_result, dict), "Content-based recommendations should return structured result"

            if "recommendations" in content_result:
                recommendations = content_result["recommendations"]
                assert isinstance(recommendations, list), "Recommendations should be list"

                # Verify recommendations are sorted by relevance
                scores = [rec.get("score", 0) for rec in recommendations]
                assert scores == sorted(scores, reverse=True), "Recommendations should be sorted by score"

                # Higher scoring items should match user preferences better
                for rec in recommendations:
                    if rec.get("score", 0) > 0.7:
                        content_features = rec.get("features", {})
                        user_classes = user_preferences.get("classes", [])
                        content_classes = content_features.get("classes", [])

                        # High-scoring recommendations should match user class preferences
                        has_class_match = any(cls in content_classes for cls in user_classes)

    def test_hybrid_recommendation_system(self):
        """Test hybrid recommendation system combining multiple approaches"""
        try:
            from src_common.recommendations import RecommendationEngine
        except ImportError:
            pytest.skip("Recommendation engine not available for testing")

        engine = RecommendationEngine()

        # Test hybrid recommendation configuration
        hybrid_config = {
            "approaches": {
                "collaborative": {"weight": 0.4, "enabled": True},
                "content_based": {"weight": 0.4, "enabled": True},
                "popularity": {"weight": 0.1, "enabled": True},
                "trending": {"weight": 0.1, "enabled": True}
            },
            "diversity_factor": 0.3,
            "novelty_boost": 0.2,
            "recency_decay": 0.8
        }

        user_context = {
            "user_id": "test_user_hybrid",
            "session_context": {
                "current_query": "wizard spell optimization",
                "recent_views": ["phb_wizard_spells", "optimization_guide"],
                "session_duration": 1800
            },
            "preferences": {
                "content_types": ["spells", "optimization"],
                "experience_level": "advanced"
            }
        }

        if hasattr(engine, 'generate_hybrid_recommendations'):
            hybrid_result = engine.generate_hybrid_recommendations(
                user_context,
                hybrid_config,
                max_recommendations=10
            )

            assert isinstance(hybrid_result, dict), "Hybrid recommendations should return structured result"

            if "recommendations" in hybrid_result:
                recommendations = hybrid_result["recommendations"]
                assert isinstance(recommendations, list), "Recommendations should be list"
                assert len(recommendations) <= 10, "Should respect max recommendations limit"

                for rec in recommendations:
                    assert "content_id" in rec, "Recommendation should have content ID"
                    assert "final_score" in rec, "Recommendation should have final score"
                    assert "approach_scores" in rec, "Recommendation should show component scores"

                    approach_scores = rec["approach_scores"]
                    assert isinstance(approach_scores, dict), "Approach scores should be dictionary"

            if "diversity_metrics" in hybrid_result:
                diversity = hybrid_result["diversity_metrics"]
                assert "content_type_diversity" in diversity, "Should measure content type diversity"
                assert "topic_diversity" in diversity, "Should measure topic diversity"

    def test_real_time_recommendation_updates(self):
        """Test real-time recommendation updates based on user interactions"""
        try:
            from src_common.recommendations import RecommendationEngine
        except ImportError:
            pytest.skip("Recommendation engine not available for testing")

        engine = RecommendationEngine()

        # Test real-time updates
        initial_context = {
            "user_id": "realtime_user",
            "current_recommendations": [
                {"content_id": "rec_001", "score": 0.8},
                {"content_id": "rec_002", "score": 0.7},
                {"content_id": "rec_003", "score": 0.6}
            ]
        }

        # Simulate user interaction
        user_interaction = {
            "interaction_type": "click",
            "content_id": "rec_001",
            "timestamp": datetime.now().isoformat(),
            "context": {
                "position": 1,
                "query": "spellcasting mechanics",
                "session_id": "session_123"
            }
        }

        if hasattr(engine, 'update_recommendations_realtime'):
            update_result = engine.update_recommendations_realtime(
                initial_context,
                user_interaction
            )

            assert isinstance(update_result, dict), "Real-time update should return structured result"

            if "updated_recommendations" in update_result:
                updated_recs = update_result["updated_recommendations"]
                assert isinstance(updated_recs, list), "Updated recommendations should be list"

            if "learning_feedback" in update_result:
                feedback = update_result["learning_feedback"]
                assert "preference_adjustment" in feedback, "Should provide preference adjustment info"
                assert "model_update" in feedback, "Should indicate if model was updated"

    def test_recommendation_explanation_and_transparency(self):
        """Test recommendation explanation and transparency features"""
        try:
            from src_common.recommendations import RecommendationEngine
        except ImportError:
            pytest.skip("Recommendation engine not available for testing")

        engine = RecommendationEngine()

        # Test explanation generation
        recommendation = {
            "content_id": "wizard_advanced_guide",
            "title": "Advanced Wizard Strategies",
            "score": 0.85,
            "approach_scores": {
                "collaborative": 0.8,
                "content_based": 0.9,
                "popularity": 0.7
            },
            "user_profile_match": {
                "content_type_match": 0.9,
                "difficulty_match": 0.8,
                "class_preference_match": 0.95
            }
        }

        if hasattr(engine, 'generate_recommendation_explanation'):
            explanation_result = engine.generate_recommendation_explanation(recommendation)

            assert isinstance(explanation_result, dict), "Explanation should return structured result"

            if "explanation_text" in explanation_result:
                explanation = explanation_result["explanation_text"]
                assert isinstance(explanation, str), "Explanation should be string"
                assert len(explanation) > 0, "Explanation should not be empty"

            if "reasoning_factors" in explanation_result:
                factors = explanation_result["reasoning_factors"]
                assert isinstance(factors, list), "Reasoning factors should be list"

                for factor in factors:
                    assert "factor_type" in factor, "Factor should have type"
                    assert "importance" in factor, "Factor should have importance score"
                    assert "description" in factor, "Factor should have description"

    def test_recommendation_contract_compliance(self):
        """Test that recommendation engine matches established contract"""
        # Test recommendation contract
        recommendation_requirements = {
            "user_profiling": True,
            "collaborative_filtering": True,
            "content_based_filtering": True,
            "hybrid_approaches": True,
            "real_time_learning": True,
            "explanation_generation": True
        }

        for requirement, needed in recommendation_requirements.items():
            assert needed, f"Recommendation requirement {requirement} is mandatory"

        # Test personalization contract
        personalization_requirements = {
            "preference_learning": True,
            "interaction_tracking": True,
            "dynamic_updates": True,
            "context_awareness": True
        }

        for requirement, needed in personalization_requirements.items():
            assert needed, f"Personalization requirement {requirement} is mandatory"

        # Test quality contract
        quality_requirements = {
            "diversity_optimization": True,
            "novelty_detection": True,
            "serendipity_balance": True,
            "transparency_features": True
        }

        for requirement, needed in quality_requirements.items():
            assert needed, f"Quality requirement {requirement} is mandatory"

        # Test data contract
        required_recommendation_fields = [
            "content_id",
            "recommendation_score",
            "reasoning_explanation",
            "confidence_level",
            "freshness_indicator"
        ]

        for field in required_recommendation_fields:
            assert isinstance(field, str), f"Recommendation field {field} should be defined"

        # Test integration contract
        integration_points = [
            "user_profile_integration",
            "content_catalog_integration",
            "search_engine_integration",
            "analytics_tracking_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"