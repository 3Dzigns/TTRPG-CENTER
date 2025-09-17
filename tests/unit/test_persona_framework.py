"""
Unit tests for persona testing framework components.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src_common.personas.models import (
    PersonaProfile, PersonaContext, PersonaMetrics, PersonaTestScenario,
    PersonaType, ExperienceLevel, UserRole, SessionContext
)
from src_common.personas.manager import PersonaManager
from src_common.personas.validator import PersonaResponseValidator
from src_common.personas.metrics import PersonaMetricsTracker


class TestPersonaModels:
    """Test persona data models."""

    def test_persona_profile_creation(self):
        """Test PersonaProfile creation and validation."""
        profile = PersonaProfile(
            id="test_persona",
            name="Test Persona",
            persona_type=PersonaType.NEW_USER,
            experience_level=ExperienceLevel.BEGINNER,
            user_role=UserRole.PLAYER,
            technical_comfort=3,
            preferred_detail_level="detailed"
        )

        assert profile.id == "test_persona"
        assert profile.persona_type == PersonaType.NEW_USER
        assert profile.experience_level == ExperienceLevel.BEGINNER
        assert profile.technical_comfort == 3

    def test_persona_profile_serialization(self):
        """Test PersonaProfile to_dict and from_dict methods."""
        profile = PersonaProfile(
            id="serialization_test",
            name="Serialization Test",
            persona_type=PersonaType.EXPERT_USER,
            experience_level=ExperienceLevel.EXPERT,
            user_role=UserRole.GAME_MASTER,
            languages=["English", "Spanish"],
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )

        # Test serialization
        data = profile.to_dict()
        assert data["id"] == "serialization_test"
        assert data["persona_type"] == "expert_user"
        assert data["languages"] == ["English", "Spanish"]
        assert data["created_at"] == "2024-01-01T12:00:00"

        # Test deserialization
        restored_profile = PersonaProfile.from_dict(data)
        assert restored_profile.id == profile.id
        assert restored_profile.persona_type == profile.persona_type
        assert restored_profile.languages == profile.languages
        assert restored_profile.created_at == profile.created_at

    def test_persona_context_creation(self):
        """Test PersonaContext creation."""
        profile = PersonaProfile(
            id="context_test",
            name="Context Test",
            persona_type=PersonaType.MOBILE_USER,
            experience_level=ExperienceLevel.INTERMEDIATE,
            user_role=UserRole.PLAYER
        )

        context = PersonaContext(
            persona_profile=profile,
            session_context=SessionContext.ACTIVE_GAME,
            device_type="mobile",
            time_constraint=30,
            previous_queries=["How do I roll for initiative?"]
        )

        assert context.persona_profile.id == "context_test"
        assert context.session_context == SessionContext.ACTIVE_GAME
        assert context.device_type == "mobile"
        assert len(context.previous_queries) == 1

    def test_persona_metrics_creation(self):
        """Test PersonaMetrics creation and validation."""
        metrics = PersonaMetrics(
            persona_id="metrics_test",
            query_id="query_123",
            appropriateness_score=0.85,
            detail_level_match=0.9,
            language_appropriateness=0.8,
            citation_quality=0.75,
            response_length=250,
            citation_count=2,
            example_count=1,
            technical_terms_count=3,
            response_time_ms=150,
            complexity_match=0.8,
            user_satisfaction_predicted=0.82
        )

        assert metrics.persona_id == "metrics_test"
        assert metrics.appropriateness_score == 0.85
        assert metrics.response_time_ms == 150
        assert metrics.has_hallucinations is False


class TestPersonaManager:
    """Test PersonaManager functionality."""

    def test_persona_manager_initialization(self):
        """Test PersonaManager initialization."""
        manager = PersonaManager()
        assert len(manager.profiles_cache) > 0
        assert "new_user_basic" in manager.profiles_cache
        assert "expert_dm" in manager.profiles_cache

    def test_get_persona(self):
        """Test getting persona by ID."""
        manager = PersonaManager()
        persona = manager.get_persona("expert_dm")

        assert persona is not None
        assert persona.id == "expert_dm"
        assert persona.persona_type == PersonaType.DUNGEON_MASTER
        assert persona.experience_level == ExperienceLevel.EXPERT

    def test_list_personas_filtering(self):
        """Test persona listing with filters."""
        manager = PersonaManager()

        # Filter by persona type
        dm_personas = manager.list_personas(persona_type=PersonaType.DUNGEON_MASTER)
        assert len(dm_personas) > 0
        assert all(p.persona_type == PersonaType.DUNGEON_MASTER for p in dm_personas)

        # Filter by experience level
        expert_personas = manager.list_personas(experience_level=ExperienceLevel.EXPERT)
        assert len(expert_personas) > 0
        assert all(p.experience_level == ExperienceLevel.EXPERT for p in expert_personas)

        # Filter by user role
        player_personas = manager.list_personas(user_role=UserRole.PLAYER)
        assert len(player_personas) > 0
        assert all(p.user_role == UserRole.PLAYER for p in player_personas)

    def test_create_persona_context(self):
        """Test persona context creation."""
        manager = PersonaManager()
        context = manager.create_persona_context(
            persona_id="mobile_casual",
            session_context=SessionContext.ACTIVE_GAME,
            device_type="mobile",
            time_constraint=30
        )

        assert context is not None
        assert context.persona_profile.id == "mobile_casual"
        assert context.session_context == SessionContext.ACTIVE_GAME
        assert context.device_type == "mobile"
        assert context.time_constraint == 30

    def test_extract_persona_context_from_request(self):
        """Test extracting persona context from API request."""
        manager = PersonaManager()

        # Test explicit persona specification
        payload_explicit = {
            "query": "Test query",
            "persona": {
                "id": "expert_dm",
                "session_context": "preparation"
            }
        }

        context = manager.extract_persona_context_from_request(payload_explicit)
        assert context is not None
        assert context.persona_profile.id == "expert_dm"
        assert context.session_context == SessionContext.PREPARATION

        # Test implicit persona inference
        payload_implicit = {
            "query": "Test query",
            "user_agent": "Mobile Safari",
            "device_type": "mobile"
        }

        context = manager.extract_persona_context_from_request(payload_implicit)
        assert context is not None
        assert context.persona_profile.id == "mobile_casual"

    def test_load_test_scenarios(self):
        """Test loading test scenarios."""
        manager = PersonaManager()
        scenarios = manager.load_test_scenarios()

        assert len(scenarios) > 0

        # Check that scenarios were created for each persona
        persona_ids = set(p.id for p in manager.profiles_cache.values())
        scenario_persona_ids = set(s.persona_profile.id for s in scenarios)

        # Should have at least one scenario per persona
        assert len(scenario_persona_ids) > 0


class TestPersonaResponseValidator:
    """Test PersonaResponseValidator functionality."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = PersonaResponseValidator()
        assert len(validator.technical_terms) > 0
        assert "brief" in validator.length_guidelines
        assert "comprehensive" in validator.length_guidelines

    def test_validate_response_appropriateness(self):
        """Test response appropriateness validation."""
        validator = PersonaResponseValidator()

        # Create test persona
        persona = PersonaProfile(
            id="test_persona",
            name="Test Persona",
            persona_type=PersonaType.NEW_USER,
            experience_level=ExperienceLevel.BEGINNER,
            user_role=UserRole.PLAYER,
            technical_comfort=3,
            preferred_detail_level="detailed",
            expects_examples=True,
            expects_citations=True
        )

        context = PersonaContext(
            persona_profile=persona,
            session_context=SessionContext.LEARNING
        )

        # Test appropriate response
        appropriate_response = """
        In D&D 5e, armor class (AC) determines how hard it is to hit you in combat.
        Your AC is calculated by adding your armor's AC value to any relevant ability modifiers.

        For example, if you wear leather armor (AC 11) and have a Dexterity of 14 (+2),
        your total AC would be 13.

        [Player's Handbook, p. 144]
        """

        metrics = validator.validate_response_appropriateness(
            response=appropriate_response,
            persona_context=context,
            query="How does armor class work?"
        )

        assert metrics.persona_id == "test_persona"
        assert metrics.appropriateness_score > 0.7
        assert metrics.citation_count > 0
        assert metrics.example_count > 0

    def test_detail_level_matching(self):
        """Test detail level matching logic."""
        validator = PersonaResponseValidator()

        # Test brief persona
        brief_persona = PersonaProfile(
            id="brief_persona",
            name="Brief Persona",
            persona_type=PersonaType.EXPERT_USER,
            experience_level=ExperienceLevel.EXPERT,
            user_role=UserRole.GAME_MASTER,
            preferred_detail_level="brief"
        )

        # Short response should score well for brief persona
        short_response = "AC = 10 + Dex modifier + armor bonus."
        brief_score = validator._evaluate_detail_level_match(short_response, brief_persona)
        assert brief_score > 0.8

        # Long response should score poorly for brief persona
        long_response = "Armor Class in D&D 5e is a complex system..." + " detailed explanation" * 50
        long_score = validator._evaluate_detail_level_match(long_response, brief_persona)
        assert long_score < 0.7

    def test_technical_complexity_matching(self):
        """Test technical complexity matching."""
        validator = PersonaResponseValidator()

        # High technical comfort persona
        expert_persona = PersonaProfile(
            id="expert_persona",
            name="Expert Persona",
            persona_type=PersonaType.EXPERT_USER,
            experience_level=ExperienceLevel.EXPERT,
            user_role=UserRole.GAME_MASTER,
            technical_comfort=9
        )

        # Technical response should score well for expert
        technical_response = "The bounded accuracy system ensures proficiency bonus scaling maintains challenge rating consistency across tier progression."
        expert_score = validator._evaluate_complexity_match(technical_response, expert_persona)
        assert expert_score > 0.6

        # Simple response should score less well for expert
        simple_response = "You roll a die and add numbers."
        simple_score = validator._evaluate_complexity_match(simple_response, expert_persona)
        assert simple_score < expert_score

    def test_citation_quality_evaluation(self):
        """Test citation quality evaluation."""
        validator = PersonaResponseValidator()

        # Persona that expects citations
        citation_persona = PersonaProfile(
            id="citation_persona",
            name="Citation Persona",
            persona_type=PersonaType.RULES_LAWYER,
            experience_level=ExperienceLevel.EXPERT,
            user_role=UserRole.PLAYER,
            expects_citations=True
        )

        # Response with citations should score well
        cited_response = "According to the Player's Handbook (p. 144), armor class is calculated..."
        cited_score = validator._evaluate_citation_quality(cited_response, citation_persona)
        assert cited_score > 0.5

        # Response without citations should score poorly
        uncited_response = "Armor class is calculated by adding numbers together."
        uncited_score = validator._evaluate_citation_quality(uncited_response, citation_persona)
        assert uncited_score == 0.0

    def test_mobile_friendly_detection(self):
        """Test mobile-friendly response detection."""
        validator = PersonaResponseValidator()

        # Mobile-friendly response
        mobile_friendly = "AC = armor + dex mod. Example: leather armor (11) + dex 2 = AC 13."
        assert validator._is_mobile_friendly(mobile_friendly) is True

        # Not mobile-friendly (too long)
        mobile_unfriendly = "This is a very long explanation that goes on and on with excessive detail that would be hard to read on a mobile device because it contains too much information in long paragraphs without proper formatting or breaks which makes it difficult to parse and understand when viewing on a small screen with limited viewport space and potentially slow connection speeds that make loading large amounts of text problematic for the user experience."
        assert validator._is_mobile_friendly(mobile_unfriendly) is False


class TestPersonaMetricsTracker:
    """Test PersonaMetricsTracker functionality."""

    def test_metrics_tracker_initialization(self, tmp_path):
        """Test metrics tracker initialization."""
        with patch('src_common.personas.metrics.Path') as mock_path:
            mock_path.return_value = tmp_path
            tracker = PersonaMetricsTracker(environment="test")
            assert tracker.environment == "test"
            assert len(tracker.alert_thresholds) > 0

    def test_record_metrics(self, tmp_path):
        """Test recording persona metrics."""
        with patch.object(PersonaMetricsTracker, '_persist_metrics') as mock_persist:
            with patch.object(PersonaMetricsTracker, '_check_alerts') as mock_alerts:
                tracker = PersonaMetricsTracker(environment="test")

                metrics = PersonaMetrics(
                    persona_id="test_persona",
                    query_id="test_query",
                    appropriateness_score=0.85,
                    detail_level_match=0.9,
                    language_appropriateness=0.8,
                    citation_quality=0.75,
                    response_length=200,
                    citation_count=2,
                    example_count=1,
                    technical_terms_count=3,
                    response_time_ms=150,
                    complexity_match=0.8,
                    user_satisfaction_predicted=0.82
                )

                tracker.record_metrics(metrics)

                assert len(tracker.metrics_cache) == 1
                assert tracker.metrics_cache[0].persona_id == "test_persona"
                mock_persist.assert_called_once()
                mock_alerts.assert_called_once()

    def test_alert_generation(self, tmp_path):
        """Test alert generation for poor metrics."""
        with patch.object(PersonaMetricsTracker, '_store_alerts') as mock_store:
            tracker = PersonaMetricsTracker(environment="test")

            # Metrics that should trigger alerts
            poor_metrics = PersonaMetrics(
                persona_id="poor_persona",
                query_id="poor_query",
                appropriateness_score=0.5,  # Below threshold
                detail_level_match=0.4,     # Below threshold
                language_appropriateness=0.6,
                citation_quality=0.3,
                response_length=100,
                citation_count=0,
                example_count=0,
                technical_terms_count=1,
                response_time_ms=200,
                complexity_match=0.5,
                user_satisfaction_predicted=0.5,  # Below threshold
                has_hallucinations=True,
                has_inappropriate_content=True
            )

            tracker._check_alerts(poor_metrics)

            # Should have generated multiple alerts
            mock_store.assert_called_once()
            alerts = mock_store.call_args[0][0]
            assert len(alerts) >= 4  # Multiple alert types


@pytest.fixture
def sample_persona():
    """Sample persona for testing."""
    return PersonaProfile(
        id="test_persona",
        name="Test Persona",
        persona_type=PersonaType.INTERMEDIATE_USER,
        experience_level=ExperienceLevel.INTERMEDIATE,
        user_role=UserRole.PLAYER,
        technical_comfort=5,
        preferred_detail_level="moderate",
        expects_examples=True,
        expects_citations=True
    )


@pytest.fixture
def sample_context(sample_persona):
    """Sample persona context for testing."""
    return PersonaContext(
        persona_profile=sample_persona,
        session_context=SessionContext.RESEARCH,
        device_type="desktop",
        query_complexity=0.6
    )