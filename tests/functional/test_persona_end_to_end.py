"""
Functional end-to-end tests for persona testing framework.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src_common.app import app
from src_common.personas.models import PersonaType, ExperienceLevel, UserRole, SessionContext


class TestPersonaEndToEnd:
    """Test complete persona testing workflow."""

    def test_persona_enabled_query_processing(self, test_client):
        """Test query processing with persona context enabled."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            # Test request with explicit persona context
            payload = {
                'query': 'How do I calculate spell save DC in D&D 5e?',
                'persona': {
                    'id': 'new_user_basic',
                    'session_context': 'learning'
                },
                'device_type': 'desktop'
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Should include persona section in response
            assert 'persona' in data
            assert data['persona']['enabled'] is True
            assert data['persona']['context'] is not None
            assert data['persona']['context']['persona_id'] == 'new_user_basic'
            assert data['persona']['context']['persona_name'] == 'New User - Basic'
            assert data['persona']['validation'] is not None

            # Should have persona validation metrics
            validation = data['persona']['validation']
            assert 'appropriateness_score' in validation
            assert 'detail_level_match' in validation
            assert 'user_satisfaction_predicted' in validation
            assert 'response_appropriate' in validation

    def test_persona_disabled_query_processing(self, test_client):
        """Test query processing with persona context disabled."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'false'}):
            payload = {
                'query': 'How do I calculate spell save DC in D&D 5e?',
                'persona': {
                    'id': 'expert_dm'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Should include persona section but disabled
            assert 'persona' in data
            assert data['persona']['enabled'] is False
            assert data['persona']['context'] is None
            assert data['persona']['validation'] is None

    def test_implicit_persona_inference(self, test_client):
        """Test implicit persona inference from request context."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            # Mobile user without explicit persona
            payload = {
                'query': 'Quick rule lookup needed',
                'user_agent': 'Mobile Safari/604.1',
                'device_type': 'mobile'
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Should infer mobile persona
            assert data['persona']['enabled'] is True
            assert data['persona']['context']['persona_id'] == 'mobile_casual'
            assert data['persona']['context']['persona_type'] == 'mobile_user'

    def test_expert_persona_response_characteristics(self, test_client):
        """Test that expert persona gets appropriate response characteristics."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            payload = {
                'query': 'Explain multiclass spellcasting slot calculation',
                'persona': {
                    'id': 'expert_dm',
                    'session_context': 'preparation'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Expert persona should get validation scores
            validation = data['persona']['validation']
            assert validation['appropriateness_score'] is not None

            # Expert should prefer brief, technical responses
            persona_context = data['persona']['context']
            assert persona_context['experience_level'] == 'expert'
            assert persona_context['persona_type'] == 'dungeon_master'

    def test_new_user_persona_response_characteristics(self, test_client):
        """Test that new user persona gets appropriate response characteristics."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            payload = {
                'query': 'What is armor class?',
                'persona': {
                    'id': 'new_user_basic',
                    'session_context': 'learning'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # New user should get detailed, example-rich responses
            validation = data['persona']['validation']
            assert validation['appropriateness_score'] is not None

            persona_context = data['persona']['context']
            assert persona_context['experience_level'] == 'beginner'
            assert persona_context['persona_type'] == 'new_user'

    def test_streaming_host_persona_time_pressure(self, test_client):
        """Test streaming host persona under time pressure."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            payload = {
                'query': 'Quick: how does grappling work?',
                'persona': {
                    'id': 'streaming_host',
                    'session_context': 'active_game'
                },
                'time_constraint': 15  # 15 seconds
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Streaming host should get quick, audience-friendly responses
            validation = data['persona']['validation']
            assert validation['appropriateness_score'] is not None

            persona_context = data['persona']['context']
            assert persona_context['persona_type'] == 'streaming_host'

    def test_multilingual_persona_support(self, test_client):
        """Test multilingual persona support."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            payload = {
                'query': 'Comment calculer la classe d\'armure?',  # French query
                'persona': {
                    'id': 'multilingual_user',
                    'session_context': 'research'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Should handle multilingual context
            validation = data['persona']['validation']
            assert validation['language_appropriateness'] is not None

            persona_context = data['persona']['context']
            assert persona_context['persona_type'] == 'multilingual'


class TestPersonaIntegrationWithAEHRL:
    """Test persona integration with AEHRL system."""

    def test_persona_aware_aehrl_evaluation(self, test_client):
        """Test AEHRL evaluation considers persona context."""
        with patch.dict('os.environ', {
            'PERSONA_TESTING_ENABLED': 'true',
            'AEHRL_ENABLED': 'true'
        }):
            payload = {
                'query': 'What is the damage for a greataxe?',
                'persona': {
                    'id': 'rules_lawyer',
                    'session_context': 'preparation'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Both AEHRL and persona should be enabled
            assert data['aehrl']['enabled'] is True
            assert data['persona']['enabled'] is True

            # Should have persona validation metrics
            assert data['persona']['validation'] is not None
            validation = data['persona']['validation']
            assert 'appropriateness_score' in validation

    def test_persona_affects_response_appropriateness(self, test_client):
        """Test that persona affects response appropriateness scoring."""
        with patch.dict('os.environ', {
            'PERSONA_TESTING_ENABLED': 'true',
            'AEHRL_ENABLED': 'true'
        }):
            # Same query, different personas should yield different appropriateness scores
            base_payload = {
                'query': 'Explain the action economy in combat'
            }

            # Test with beginner persona
            beginner_payload = {
                **base_payload,
                'persona': {
                    'id': 'new_user_basic',
                    'session_context': 'learning'
                }
            }

            beginner_response = test_client.post('/rag/ask', json=beginner_payload)
            beginner_data = beginner_response.json()

            # Test with expert persona
            expert_payload = {
                **base_payload,
                'persona': {
                    'id': 'expert_dm',
                    'session_context': 'preparation'
                }
            }

            expert_response = test_client.post('/rag/ask', json=expert_payload)
            expert_data = expert_response.json()

            # Both should have validation, but potentially different scores
            assert beginner_data['persona']['validation'] is not None
            assert expert_data['persona']['validation'] is not None

            beginner_score = beginner_data['persona']['validation']['appropriateness_score']
            expert_score = expert_data['persona']['validation']['appropriateness_score']

            # Scores should be numeric and in valid range
            assert isinstance(beginner_score, (int, float))
            assert isinstance(expert_score, (int, float))
            assert 0 <= beginner_score <= 1
            assert 0 <= expert_score <= 1


class TestPersonaErrorHandling:
    """Test persona system error handling and graceful degradation."""

    def test_invalid_persona_id_graceful_handling(self, test_client):
        """Test handling of invalid persona ID."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            payload = {
                'query': 'Test query',
                'persona': {
                    'id': 'nonexistent_persona',
                    'session_context': 'research'
                }
            }

            response = test_client.post('/rag/ask', json=payload)

            assert response.status_code == 200
            data = response.json()

            # Should still process query successfully
            assert 'query' in data
            assert 'answers' in data

            # Persona section should indicate failure gracefully
            assert data['persona']['enabled'] is True
            # Context might be None due to invalid persona ID

    def test_persona_validation_failure_graceful_degradation(self, test_client):
        """Test graceful degradation when persona validation fails."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            with patch('src_common.orchestrator.service.PersonaResponseValidator') as mock_validator:
                # Make validator raise an exception
                mock_validator.side_effect = Exception("Validation service unavailable")

                payload = {
                    'query': 'Test query',
                    'persona': {
                        'id': 'expert_dm',
                        'session_context': 'preparation'
                    }
                }

                response = test_client.post('/rag/ask', json=payload)

                # Query should still succeed despite persona validation failure
                assert response.status_code == 200
                data = response.json()

                assert 'query' in data
                assert 'answers' in data

                # Persona should be enabled but validation should be None
                assert data['persona']['enabled'] is True
                assert data['persona']['validation'] is None

    def test_persona_manager_failure_graceful_degradation(self, test_client):
        """Test graceful degradation when persona manager fails."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            with patch('src_common.orchestrator.service.PersonaManager') as mock_manager:
                # Make persona manager raise an exception
                mock_manager.side_effect = Exception("Persona manager unavailable")

                payload = {
                    'query': 'Test query',
                    'persona': {
                        'id': 'expert_dm'
                    }
                }

                response = test_client.post('/rag/ask', json=payload)

                # Query should still succeed
                assert response.status_code == 200
                data = response.json()

                assert 'query' in data
                assert 'answers' in data

                # Persona context should be None due to manager failure
                assert data['persona']['enabled'] is True
                assert data['persona']['context'] is None


class TestPersonaMetricsCollection:
    """Test persona metrics collection and reporting."""

    def test_persona_metrics_recorded(self, test_client):
        """Test that persona metrics are properly recorded."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'true'}):
            with patch('src_common.orchestrator.service.PersonaMetricsTracker') as mock_tracker:
                mock_tracker_instance = MagicMock()
                mock_tracker.return_value = mock_tracker_instance

                payload = {
                    'query': 'How does stealth work?',
                    'persona': {
                        'id': 'new_user_basic',
                        'session_context': 'learning'
                    }
                }

                response = test_client.post('/rag/ask', json=payload)

                assert response.status_code == 200

                # Should have called record_metrics
                mock_tracker_instance.record_metrics.assert_called_once()

                # Check the metrics that were recorded
                recorded_metrics = mock_tracker_instance.record_metrics.call_args[0][0]
                assert recorded_metrics.persona_id == 'new_user_basic'
                assert recorded_metrics.response_time_ms > 0

    def test_persona_metrics_without_persona_context(self, test_client):
        """Test that metrics are not recorded without persona context."""
        with patch.dict('os.environ', {'PERSONA_TESTING_ENABLED': 'false'}):
            with patch('src_common.orchestrator.service.PersonaMetricsTracker') as mock_tracker:
                mock_tracker_instance = MagicMock()
                mock_tracker.return_value = mock_tracker_instance

                payload = {
                    'query': 'How does stealth work?'
                }

                response = test_client.post('/rag/ask', json=payload)

                assert response.status_code == 200

                # Should not have called record_metrics
                mock_tracker_instance.record_metrics.assert_not_called()


@pytest.fixture
def test_client():
    """Create test client for FastAPI application."""
    return TestClient(app)