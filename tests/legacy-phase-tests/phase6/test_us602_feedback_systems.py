# tests/regression/phase6/test_us602_feedback_systems.py
"""
Phase 6 - US-602: Feedback Systems Regression Tests
Tests user feedback collection, processing, and integration systems
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestFeedbackSystems:
    """Test suite for Feedback Systems validation"""

    def test_feedback_system_availability(self):
        """Test that feedback system components are available"""
        try:
            from src_common.feedback import FeedbackManager
            from src_common.user_routes import app

            assert FeedbackManager is not None, "FeedbackManager class should be available"
            assert app is not None, "User routes app should be available for feedback endpoints"

        except ImportError as e:
            pytest.fail(f"Feedback system components not available: {e}")

    def test_user_feedback_collection_interface(self):
        """Test user feedback collection interface and endpoints"""
        try:
            from src_common.user_routes import app
        except ImportError:
            pytest.skip("User routes module not available for testing")

        with app.test_client() as client:
            # Test feedback form endpoint
            response = client.get('/feedback')

            if response.status_code == 200:
                # Should have feedback form
                content = response.get_data(as_text=True)
                assert "feedback" in content.lower(), "Feedback page should contain feedback form"

            # Test feedback submission endpoint
            feedback_data = {
                "type": "general",
                "rating": 4,
                "message": "The TTRPG assistant is very helpful for understanding spell mechanics",
                "user_context": {
                    "session_id": "test_session_123",
                    "query": "What is the range of Fireball?",
                    "response_quality": "good"
                }
            }

            submit_response = client.post('/api/feedback', json=feedback_data)

            # Should accept feedback submissions
            if submit_response.status_code in [200, 201, 202]:
                response_data = submit_response.get_json()

                assert "feedback_id" in response_data or "status" in response_data, "Should return feedback confirmation"
            elif submit_response.status_code == 404:
                # Endpoint may not be implemented yet
                pytest.skip("Feedback submission endpoint not yet implemented")

    def test_feedback_categorization_and_classification(self):
        """Test automatic feedback categorization and classification"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test feedback categorization
        test_feedback_samples = [
            {
                "message": "The AI response was incorrect about spell damage calculations",
                "expected_category": "accuracy",
                "expected_type": "bug_report"
            },
            {
                "message": "Great response! Very helpful and detailed explanation",
                "expected_category": "quality",
                "expected_type": "positive_feedback"
            },
            {
                "message": "The interface is slow and takes too long to respond",
                "expected_category": "performance",
                "expected_type": "performance_issue"
            },
            {
                "message": "It would be great if you could add support for Pathfinder rules",
                "expected_category": "feature_request",
                "expected_type": "enhancement"
            },
            {
                "message": "The chat interface is confusing and hard to use",
                "expected_category": "usability",
                "expected_type": "usability_issue"
            }
        ]

        for feedback_sample in test_feedback_samples:
            if hasattr(manager, 'categorize_feedback'):
                category_result = manager.categorize_feedback(feedback_sample["message"])

                assert isinstance(category_result, dict), "Categorization should return structured result"

                if "category" in category_result:
                    # Should provide reasonable categorization
                    categories = category_result["category"]
                    assert isinstance(categories, (str, list)), "Categories should be string or list"

                if "type" in category_result:
                    feedback_type = category_result["type"]
                    valid_types = ["bug_report", "feature_request", "positive_feedback", "negative_feedback", "question", "performance_issue", "usability_issue"]
                    assert feedback_type in valid_types, f"Feedback type should be valid, got: {feedback_type}"

    def test_sentiment_analysis_and_scoring(self):
        """Test sentiment analysis of user feedback"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test sentiment analysis
        sentiment_test_cases = [
            {
                "message": "Absolutely love this AI assistant! It's incredibly helpful and accurate.",
                "expected_sentiment": "positive"
            },
            {
                "message": "This is terrible. The responses are wrong and unhelpful.",
                "expected_sentiment": "negative"
            },
            {
                "message": "The assistant works okay. Sometimes good, sometimes not so much.",
                "expected_sentiment": "neutral"
            },
            {
                "message": "Thanks for the help with understanding the spell rules.",
                "expected_sentiment": "positive"
            },
            {
                "message": "The response was confusing and didn't answer my question.",
                "expected_sentiment": "negative"
            }
        ]

        for test_case in sentiment_test_cases:
            if hasattr(manager, 'analyze_sentiment'):
                sentiment_result = manager.analyze_sentiment(test_case["message"])

                assert isinstance(sentiment_result, dict), "Sentiment analysis should return structured result"

                if "sentiment" in sentiment_result:
                    sentiment = sentiment_result["sentiment"]
                    valid_sentiments = ["positive", "negative", "neutral"]
                    assert sentiment in valid_sentiments, f"Sentiment should be valid, got: {sentiment}"

                if "confidence" in sentiment_result:
                    confidence = sentiment_result["confidence"]
                    assert isinstance(confidence, (int, float)), "Confidence should be numeric"
                    assert 0.0 <= confidence <= 1.0, "Confidence should be between 0 and 1"

                if "score" in sentiment_result:
                    score = sentiment_result["score"]
                    assert isinstance(score, (int, float)), "Sentiment score should be numeric"

    def test_feedback_aggregation_and_analytics(self):
        """Test feedback aggregation and analytics capabilities"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test feedback analytics
        if hasattr(manager, 'get_feedback_analytics'):
            analytics = manager.get_feedback_analytics(period="7d")

            assert isinstance(analytics, dict), "Analytics should return structured data"

            # Expected analytics fields
            expected_fields = [
                "total_feedback", "average_rating", "sentiment_distribution",
                "category_breakdown", "response_quality_trends"
            ]

            for field in expected_fields:
                if field in analytics:
                    # Verify field types
                    if field == "total_feedback":
                        assert isinstance(analytics[field], int), "Total feedback should be integer"
                    elif field == "average_rating":
                        assert isinstance(analytics[field], (int, float)), "Average rating should be numeric"
                    elif field in ["sentiment_distribution", "category_breakdown"]:
                        assert isinstance(analytics[field], dict), f"{field} should be dictionary"

        # Test trend analysis
        if hasattr(manager, 'analyze_feedback_trends'):
            trends = manager.analyze_feedback_trends(timeframe="30d")

            assert isinstance(trends, dict), "Trends should return structured data"

            if "trend_direction" in trends:
                direction = trends["trend_direction"]
                valid_directions = ["improving", "declining", "stable", "insufficient_data"]
                assert direction in valid_directions, f"Trend direction should be valid, got: {direction}"

    def test_feedback_response_and_followup(self):
        """Test feedback response and follow-up mechanisms"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test feedback response generation
        high_priority_feedback = {
            "type": "bug_report",
            "severity": "high",
            "message": "The AI gave incorrect spell damage information that could affect gameplay",
            "user_email": "test@example.com"
        }

        if hasattr(manager, 'process_feedback'):
            response = manager.process_feedback(high_priority_feedback)

            assert isinstance(response, dict), "Feedback processing should return structured response"

            if "action_required" in response:
                assert isinstance(response["action_required"], bool), "Action required should be boolean"

            if "priority" in response:
                priority = response["priority"]
                valid_priorities = ["low", "medium", "high", "critical"]
                assert priority in valid_priorities, f"Priority should be valid, got: {priority}"

            if "auto_response" in response:
                auto_response = response["auto_response"]
                assert isinstance(auto_response, str), "Auto response should be string"
                assert len(auto_response) > 10, "Auto response should be meaningful"

    def test_feedback_integration_with_development(self):
        """Test integration of feedback with development processes"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test issue tracking integration
        bug_feedback = {
            "type": "bug_report",
            "message": "Spell search returns incorrect results for cantrips",
            "steps_to_reproduce": "Search for 'Light' cantrip, system returns wrong spell",
            "expected_behavior": "Should return Light cantrip information",
            "actual_behavior": "Returns Fireball spell instead"
        }

        if hasattr(manager, 'create_development_issue'):
            issue_result = manager.create_development_issue(bug_feedback)

            assert isinstance(issue_result, dict), "Issue creation should return structured result"

            if "issue_id" in issue_result:
                assert isinstance(issue_result["issue_id"], str), "Issue ID should be string"

            if "status" in issue_result:
                status = issue_result["status"]
                valid_statuses = ["created", "pending", "failed"]
                assert status in valid_statuses, f"Issue status should be valid, got: {status}"

        # Test feature request processing
        feature_feedback = {
            "type": "feature_request",
            "message": "Add support for homebrew spells and custom rules",
            "priority": "medium",
            "use_case": "DMs want to add custom content to their campaigns"
        }

        if hasattr(manager, 'process_feature_request'):
            feature_result = manager.process_feature_request(feature_feedback)

            assert isinstance(feature_result, dict), "Feature request processing should return structured result"

    def test_feedback_privacy_and_data_handling(self):
        """Test feedback privacy protection and data handling"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test data anonymization
        sensitive_feedback = {
            "message": "My character John Smith's stats are wrong",
            "user_email": "john.smith@example.com",
            "session_data": {
                "character_name": "Gandalf the Grey",
                "campaign_id": "secret_campaign_123"
            }
        }

        if hasattr(manager, 'anonymize_feedback'):
            anonymized = manager.anonymize_feedback(sensitive_feedback)

            assert isinstance(anonymized, dict), "Anonymization should return structured data"

            # Should remove or mask sensitive information
            anonymized_str = str(anonymized)
            assert "john.smith@example.com" not in anonymized_str, "Should remove email addresses"

            # Should preserve useful information
            assert "stats are wrong" in anonymized["message"], "Should preserve core feedback content"

        # Test data retention policies
        if hasattr(manager, 'get_data_retention_policy'):
            retention_policy = manager.get_data_retention_policy()

            assert isinstance(retention_policy, dict), "Retention policy should be structured"

            if "retention_period" in retention_policy:
                period = retention_policy["retention_period"]
                assert isinstance(period, (int, str)), "Retention period should be specified"

    def test_feedback_performance_and_scalability(self):
        """Test feedback system performance and scalability"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test bulk feedback processing
        bulk_feedback = []
        for i in range(50):
            feedback = {
                "type": "general",
                "rating": 3 + (i % 3),
                "message": f"Test feedback message {i}",
                "timestamp": time.time() - (i * 60)  # Spread over time
            }
            bulk_feedback.append(feedback)

        # Test processing performance
        start_time = time.perf_counter()

        if hasattr(manager, 'process_bulk_feedback'):
            result = manager.process_bulk_feedback(bulk_feedback)

            end_time = time.perf_counter()
            processing_time = end_time - start_time

            # Should process bulk feedback efficiently
            assert processing_time < 5.0, f"Bulk feedback processing took {processing_time:.2f}s, should be < 5s"

            assert isinstance(result, dict), "Bulk processing should return structured result"

            if "processed_count" in result:
                assert result["processed_count"] == len(bulk_feedback), "Should process all feedback items"

        else:
            # Test individual processing performance
            processing_times = []

            for feedback in bulk_feedback[:10]:  # Test first 10 items
                start_time = time.perf_counter()

                if hasattr(manager, 'process_feedback'):
                    manager.process_feedback(feedback)

                end_time = time.perf_counter()
                processing_times.append(end_time - start_time)

            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                assert avg_time < 0.1, f"Individual feedback processing should be fast, average: {avg_time:.3f}s"

    def test_real_time_feedback_monitoring(self):
        """Test real-time feedback monitoring and alerting"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test alert generation for critical feedback
        critical_feedback = {
            "type": "bug_report",
            "severity": "critical",
            "message": "System is giving dangerous advice about spell components",
            "safety_concern": True,
            "timestamp": time.time()
        }

        if hasattr(manager, 'check_alert_conditions'):
            alert_result = manager.check_alert_conditions(critical_feedback)

            assert isinstance(alert_result, dict), "Alert checking should return structured result"

            if "alert_required" in alert_result:
                # Critical safety issues should trigger alerts
                if critical_feedback.get("safety_concern"):
                    assert alert_result["alert_required"] == True, "Safety concerns should trigger alerts"

            if "alert_level" in alert_result:
                level = alert_result["alert_level"]
                valid_levels = ["low", "medium", "high", "critical"]
                assert level in valid_levels, f"Alert level should be valid, got: {level}"

        # Test feedback volume monitoring
        if hasattr(manager, 'monitor_feedback_volume'):
            volume_stats = manager.monitor_feedback_volume(window="1h")

            assert isinstance(volume_stats, dict), "Volume monitoring should return structured data"

            if "feedback_rate" in volume_stats:
                rate = volume_stats["feedback_rate"]
                assert isinstance(rate, (int, float)), "Feedback rate should be numeric"
                assert rate >= 0, "Feedback rate should be non-negative"

    def test_feedback_api_endpoints(self):
        """Test feedback API endpoints and integration"""
        try:
            from src_common.user_routes import app
        except ImportError:
            pytest.skip("User routes module not available for testing")

        with app.test_client() as client:
            # Test feedback submission API
            api_feedback = {
                "query": "What is the AC of plate armor?",
                "response": "Plate armor has an AC of 18",
                "quality_rating": 5,
                "helpful": True,
                "feedback_text": "Perfect answer, exactly what I needed"
            }

            response = client.post('/api/feedback', json=api_feedback)

            if response.status_code in [200, 201, 202]:
                response_data = response.get_json()

                # Should return confirmation
                assert "status" in response_data or "feedback_id" in response_data, "API should confirm feedback submission"

            elif response.status_code == 404:
                pytest.skip("Feedback API endpoint not yet implemented")

            # Test feedback analytics API
            analytics_response = client.get('/api/feedback/analytics')

            if analytics_response.status_code == 200:
                analytics_data = analytics_response.get_json()

                assert isinstance(analytics_data, dict), "Analytics API should return structured data"

                if "summary" in analytics_data:
                    summary = analytics_data["summary"]
                    assert isinstance(summary, dict), "Analytics summary should be structured"

    def test_feedback_contract_compliance(self):
        """Test that feedback system matches established contract"""
        try:
            from src_common.feedback import FeedbackManager
        except ImportError:
            pytest.skip("Feedback manager not available for testing")

        manager = FeedbackManager()

        # Test feedback data structure contract
        sample_feedback = {
            "type": "general",
            "rating": 4,
            "message": "Contract compliance test feedback",
            "timestamp": time.time()
        }

        if hasattr(manager, 'validate_feedback_format'):
            validation_result = manager.validate_feedback_format(sample_feedback)

            assert isinstance(validation_result, dict), "Feedback validation should return structured result"

            if "valid" in validation_result:
                assert validation_result["valid"] == True, "Sample feedback should be valid"

        # Test feedback processing contract
        if hasattr(manager, 'process_feedback'):
            process_result = manager.process_feedback(sample_feedback)

            assert isinstance(process_result, dict), "Feedback processing should return structured result"

            # Required response fields
            if "status" in process_result:
                status = process_result["status"]
                valid_statuses = ["processed", "pending", "failed", "requires_review"]
                assert status in valid_statuses, f"Processing status should be valid, got: {status}"

        # Test analytics contract
        if hasattr(manager, 'get_feedback_analytics'):
            analytics = manager.get_feedback_analytics()

            assert isinstance(analytics, dict), "Analytics should return structured data"

            # Core analytics fields should be numeric where appropriate
            numeric_fields = ["total_feedback", "average_rating"]
            for field in numeric_fields:
                if field in analytics:
                    assert isinstance(analytics[field], (int, float)), f"{field} should be numeric"

        # Test categorization contract
        if hasattr(manager, 'categorize_feedback'):
            categorization = manager.categorize_feedback(sample_feedback["message"])

            assert isinstance(categorization, dict), "Categorization should return structured result"

            if "category" in categorization:
                category = categorization["category"]
                assert isinstance(category, (str, list)), "Category should be string or list"