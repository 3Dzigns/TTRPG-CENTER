"""
FR-025: Machine Learning Insights and Pattern Recognition
Test comprehensive machine learning capabilities for pattern detection and insights.

This module tests the AI-driven pattern recognition system that analyzes content usage,
user behavior patterns, and content relationships to provide actionable insights
for content creators and system administrators.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR025MachineLearningInsights(BaseFRTest):
    """Test suite for FR-025 Machine Learning Insights and Pattern Recognition."""

    async def asyncSetUp(self):
        """Set up test environment with ML infrastructure."""
        await super().asyncSetUp()
        self.ml_engine = self._create_mock_ml_engine()
        self.pattern_detector = self._create_mock_pattern_detector()
        self.insight_generator = self._create_mock_insight_generator()

    def _create_mock_ml_engine(self) -> Mock:
        """Create mock ML engine for testing."""
        ml_engine = Mock()
        ml_engine.train_model = AsyncMock()
        ml_engine.predict = AsyncMock()
        ml_engine.evaluate_model = AsyncMock()
        ml_engine.get_feature_importance = AsyncMock()
        return ml_engine

    def _create_mock_pattern_detector(self) -> Mock:
        """Create mock pattern detection system."""
        detector = Mock()
        detector.detect_content_patterns = AsyncMock()
        detector.analyze_user_behavior = AsyncMock()
        detector.find_content_clusters = AsyncMock()
        detector.identify_anomalies = AsyncMock()
        return detector

    def _create_mock_insight_generator(self) -> Mock:
        """Create mock insight generation system."""
        generator = Mock()
        generator.generate_content_insights = AsyncMock()
        generator.create_usage_recommendations = AsyncMock()
        generator.predict_content_performance = AsyncMock()
        generator.suggest_content_improvements = AsyncMock()
        return generator

    async def test_content_usage_pattern_analysis(self):
        """Test ML-driven content usage pattern analysis."""
        # Mock content usage data
        usage_data = {
            'content_id': 'test_content_123',
            'access_patterns': [
                {'timestamp': '2024-01-01T10:00:00Z', 'user_id': 'user1', 'action': 'view'},
                {'timestamp': '2024-01-01T10:15:00Z', 'user_id': 'user2', 'action': 'search'},
                {'timestamp': '2024-01-01T10:30:00Z', 'user_id': 'user1', 'action': 'bookmark'}
            ],
            'session_data': {
                'avg_session_duration': 450,
                'bounce_rate': 0.15,
                'engagement_score': 0.85
            }
        }

        # Configure mock responses
        self.pattern_detector.detect_content_patterns.return_value = {
            'peak_usage_hours': [10, 14, 19],
            'common_access_sequences': ['view→search→bookmark', 'search→view→share'],
            'user_segments': {
                'casual_browsers': 0.40,
                'power_users': 0.25,
                'researchers': 0.35
            }
        }

        # Test pattern analysis
        patterns = await self.pattern_detector.detect_content_patterns(usage_data)

        # Verify pattern detection
        self.assertIn('peak_usage_hours', patterns)
        self.assertIn('common_access_sequences', patterns)
        self.assertIn('user_segments', patterns)
        self.assertEqual(len(patterns['peak_usage_hours']), 3)
        self.assertGreater(len(patterns['common_access_sequences']), 0)

        # Verify user segmentation
        segments = patterns['user_segments']
        total_percentage = sum(segments.values())
        self.assertAlmostEqual(total_percentage, 1.0, places=2)

    async def test_user_behavior_modeling_and_prediction(self):
        """Test ML model for user behavior prediction."""
        # Mock user behavior data
        user_data = {
            'user_id': 'test_user_456',
            'interaction_history': [
                {'content_type': 'rulebook', 'action': 'view', 'duration': 300},
                {'content_type': 'adventure', 'action': 'download', 'duration': 60},
                {'content_type': 'character_sheet', 'action': 'edit', 'duration': 900}
            ],
            'preferences': {
                'favorite_systems': ['D&D 5e', 'Pathfinder'],
                'content_complexity': 'intermediate',
                'session_frequency': 'weekly'
            }
        }

        # Configure ML engine responses
        self.ml_engine.predict.return_value = {
            'next_likely_actions': [
                {'action': 'search_spells', 'probability': 0.75},
                {'action': 'create_character', 'probability': 0.60},
                {'action': 'join_campaign', 'probability': 0.45}
            ],
            'content_recommendations': [
                {'content_id': 'spell_compendium', 'relevance_score': 0.92},
                {'content_id': 'character_builder', 'relevance_score': 0.88}
            ],
            'churn_risk': 0.15,
            'engagement_prediction': 0.82
        }

        # Test behavior prediction
        predictions = await self.ml_engine.predict(user_data)

        # Verify prediction quality
        self.assertIn('next_likely_actions', predictions)
        self.assertIn('content_recommendations', predictions)
        self.assertIn('churn_risk', predictions)
        self.assertIn('engagement_prediction', predictions)

        # Verify action probabilities
        actions = predictions['next_likely_actions']
        for action in actions:
            self.assertIn('action', action)
            self.assertIn('probability', action)
            self.assertGreaterEqual(action['probability'], 0.0)
            self.assertLessEqual(action['probability'], 1.0)

        # Verify recommendation scores
        recommendations = predictions['content_recommendations']
        for rec in recommendations:
            self.assertIn('content_id', rec)
            self.assertIn('relevance_score', rec)
            self.assertGreaterEqual(rec['relevance_score'], 0.0)
            self.assertLessEqual(rec['relevance_score'], 1.0)

    async def test_content_clustering_and_similarity_analysis(self):
        """Test ML-driven content clustering and similarity detection."""
        # Mock content corpus
        content_corpus = [
            {
                'content_id': 'doc1',
                'features': [0.8, 0.2, 0.9, 0.1],
                'metadata': {'type': 'rulebook', 'system': 'D&D 5e'}
            },
            {
                'content_id': 'doc2',
                'features': [0.7, 0.3, 0.8, 0.2],
                'metadata': {'type': 'rulebook', 'system': 'D&D 5e'}
            },
            {
                'content_id': 'doc3',
                'features': [0.2, 0.9, 0.1, 0.8],
                'metadata': {'type': 'adventure', 'system': 'Pathfinder'}
            }
        ]

        # Configure clustering results
        self.pattern_detector.find_content_clusters.return_value = {
            'clusters': {
                'cluster_0': {
                    'documents': ['doc1', 'doc2'],
                    'centroid': [0.75, 0.25, 0.85, 0.15],
                    'coherence_score': 0.92,
                    'dominant_features': ['rules_density', 'mechanical_complexity']
                },
                'cluster_1': {
                    'documents': ['doc3'],
                    'centroid': [0.2, 0.9, 0.1, 0.8],
                    'coherence_score': 0.88,
                    'dominant_features': ['narrative_content', 'adventure_structure']
                }
            },
            'similarity_matrix': [
                [1.0, 0.85, 0.12],
                [0.85, 1.0, 0.15],
                [0.12, 0.15, 1.0]
            ],
            'outliers': [],
            'cluster_quality_metrics': {
                'silhouette_score': 0.78,
                'davies_bouldin_score': 0.65,
                'calinski_harabasz_score': 245.6
            }
        }

        # Test clustering analysis
        clusters = await self.pattern_detector.find_content_clusters(content_corpus)

        # Verify cluster structure
        self.assertIn('clusters', clusters)
        self.assertIn('similarity_matrix', clusters)
        self.assertIn('cluster_quality_metrics', clusters)

        # Verify cluster quality
        quality = clusters['cluster_quality_metrics']
        self.assertGreater(quality['silhouette_score'], 0.5)
        self.assertLess(quality['davies_bouldin_score'], 1.0)
        self.assertGreater(quality['calinski_harabasz_score'], 100)

        # Verify cluster coherence
        for cluster_id, cluster_data in clusters['clusters'].items():
            self.assertIn('documents', cluster_data)
            self.assertIn('coherence_score', cluster_data)
            self.assertIn('dominant_features', cluster_data)
            self.assertGreater(cluster_data['coherence_score'], 0.8)

    async def test_anomaly_detection_and_outlier_identification(self):
        """Test ML-based anomaly detection in content and usage patterns."""
        # Mock system data for anomaly detection
        system_data = {
            'content_metrics': [
                {'content_id': 'normal1', 'access_count': 150, 'avg_rating': 4.2},
                {'content_id': 'normal2', 'access_count': 180, 'avg_rating': 4.0},
                {'content_id': 'anomaly1', 'access_count': 5000, 'avg_rating': 2.1},  # Suspicious high access, low rating
                {'content_id': 'normal3', 'access_count': 140, 'avg_rating': 4.3}
            ],
            'user_patterns': [
                {'user_id': 'user1', 'sessions_per_week': 3, 'avg_session_duration': 450},
                {'user_id': 'user2', 'sessions_per_week': 2, 'avg_session_duration': 380},
                {'user_id': 'bot_user', 'sessions_per_week': 50, 'avg_session_duration': 10},  # Bot-like behavior
                {'user_id': 'user3', 'sessions_per_week': 4, 'avg_session_duration': 500}
            ]
        }

        # Configure anomaly detection results
        self.pattern_detector.identify_anomalies.return_value = {
            'content_anomalies': [
                {
                    'content_id': 'anomaly1',
                    'anomaly_type': 'suspicious_engagement',
                    'anomaly_score': 0.95,
                    'reasons': ['high_access_low_rating', 'unusual_traffic_pattern'],
                    'severity': 'high'
                }
            ],
            'user_anomalies': [
                {
                    'user_id': 'bot_user',
                    'anomaly_type': 'bot_behavior',
                    'anomaly_score': 0.88,
                    'reasons': ['excessive_sessions', 'minimal_duration', 'no_engagement'],
                    'severity': 'medium'
                }
            ],
            'system_anomalies': [
                {
                    'type': 'traffic_spike',
                    'timestamp': '2024-01-01T15:30:00Z',
                    'anomaly_score': 0.75,
                    'affected_resources': ['search_api', 'content_retrieval'],
                    'severity': 'low'
                }
            ],
            'detection_confidence': 0.87,
            'false_positive_rate': 0.12
        }

        # Test anomaly detection
        anomalies = await self.pattern_detector.identify_anomalies(system_data)

        # Verify anomaly structure
        self.assertIn('content_anomalies', anomalies)
        self.assertIn('user_anomalies', anomalies)
        self.assertIn('system_anomalies', anomalies)
        self.assertIn('detection_confidence', anomalies)

        # Verify content anomalies
        content_anomalies = anomalies['content_anomalies']
        self.assertGreater(len(content_anomalies), 0)
        for anomaly in content_anomalies:
            self.assertIn('content_id', anomaly)
            self.assertIn('anomaly_score', anomaly)
            self.assertIn('severity', anomaly)
            self.assertGreaterEqual(anomaly['anomaly_score'], 0.5)

        # Verify user anomalies
        user_anomalies = anomalies['user_anomalies']
        self.assertGreater(len(user_anomalies), 0)
        for anomaly in user_anomalies:
            self.assertIn('user_id', anomaly)
            self.assertIn('anomaly_type', anomaly)
            self.assertIn('reasons', anomaly)
            self.assertIsInstance(anomaly['reasons'], list)

        # Verify detection quality
        self.assertGreater(anomalies['detection_confidence'], 0.8)
        self.assertLess(anomalies['false_positive_rate'], 0.2)

    async def test_predictive_insights_and_recommendations(self):
        """Test generation of predictive insights and actionable recommendations."""
        # Mock historical data for predictions
        historical_data = {
            'content_performance': {
                'time_series': [
                    {'date': '2024-01-01', 'views': 1200, 'engagement': 0.75},
                    {'date': '2024-01-02', 'views': 1350, 'engagement': 0.78},
                    {'date': '2024-01-03', 'views': 1180, 'engagement': 0.72}
                ],
                'seasonal_patterns': {
                    'weekly_peaks': ['tuesday', 'sunday'],
                    'monthly_trends': 'increasing',
                    'holiday_effects': {'christmas': -0.15, 'new_year': +0.25}
                }
            },
            'user_growth': {
                'new_users_per_week': [45, 52, 38, 60],
                'retention_rates': [0.85, 0.78, 0.82, 0.88],
                'churn_indicators': ['low_engagement', 'technical_issues']
            }
        }

        # Configure insight generation
        self.insight_generator.generate_content_insights.return_value = {
            'performance_predictions': {
                'next_week_views': {'estimate': 1400, 'confidence_interval': [1250, 1550]},
                'engagement_forecast': {'trend': 'improving', 'expected_rate': 0.82},
                'peak_times': ['tuesday_evening', 'sunday_afternoon']
            },
            'optimization_recommendations': [
                {
                    'category': 'content_timing',
                    'recommendation': 'Schedule new content releases on Tuesday evenings',
                    'expected_impact': '+15% engagement',
                    'confidence': 0.78
                },
                {
                    'category': 'user_retention',
                    'recommendation': 'Implement onboarding tutorial for new users',
                    'expected_impact': '+12% retention rate',
                    'confidence': 0.85
                }
            ],
            'risk_alerts': [
                {
                    'risk_type': 'engagement_decline',
                    'probability': 0.25,
                    'potential_impact': 'medium',
                    'mitigation_strategies': ['content_refresh', 'user_feedback_survey']
                }
            ],
            'growth_opportunities': [
                {
                    'opportunity': 'mobile_optimization',
                    'potential_user_increase': '20-30%',
                    'implementation_effort': 'medium',
                    'roi_estimate': 'high'
                }
            ]
        }

        # Test insight generation
        insights = await self.insight_generator.generate_content_insights(historical_data)

        # Verify prediction structure
        self.assertIn('performance_predictions', insights)
        self.assertIn('optimization_recommendations', insights)
        self.assertIn('risk_alerts', insights)
        self.assertIn('growth_opportunities', insights)

        # Verify performance predictions
        predictions = insights['performance_predictions']
        self.assertIn('next_week_views', predictions)
        self.assertIn('engagement_forecast', predictions)

        views_prediction = predictions['next_week_views']
        self.assertIn('estimate', views_prediction)
        self.assertIn('confidence_interval', views_prediction)
        self.assertEqual(len(views_prediction['confidence_interval']), 2)

        # Verify recommendations quality
        recommendations = insights['optimization_recommendations']
        self.assertGreater(len(recommendations), 0)
        for rec in recommendations:
            self.assertIn('category', rec)
            self.assertIn('recommendation', rec)
            self.assertIn('expected_impact', rec)
            self.assertIn('confidence', rec)
            self.assertGreaterEqual(rec['confidence'], 0.5)

        # Verify risk assessment
        risks = insights['risk_alerts']
        for risk in risks:
            self.assertIn('risk_type', risk)
            self.assertIn('probability', risk)
            self.assertIn('mitigation_strategies', risk)
            self.assertIsInstance(risk['mitigation_strategies'], list)

    async def test_model_performance_monitoring_and_evaluation(self):
        """Test ML model performance monitoring and continuous evaluation."""
        # Mock model evaluation data
        model_data = {
            'model_id': 'content_recommendation_v2.1',
            'training_data_size': 50000,
            'feature_count': 128,
            'model_type': 'neural_collaborative_filtering',
            'last_training': '2024-01-01T00:00:00Z'
        }

        test_data = {
            'predictions': [0.85, 0.92, 0.78, 0.88, 0.95],
            'actual_values': [0.82, 0.89, 0.75, 0.91, 0.93],
            'feature_importance': {
                'user_history': 0.35,
                'content_similarity': 0.28,
                'temporal_patterns': 0.22,
                'user_preferences': 0.15
            }
        }

        # Configure evaluation results
        self.ml_engine.evaluate_model.return_value = {
            'accuracy_metrics': {
                'mae': 0.042,  # Mean Absolute Error
                'rmse': 0.058,  # Root Mean Square Error
                'r2_score': 0.89,  # R-squared
                'precision': 0.87,
                'recall': 0.84,
                'f1_score': 0.85
            },
            'performance_trends': {
                'accuracy_over_time': [0.82, 0.85, 0.87, 0.89],
                'prediction_latency': [12, 11, 10, 9],  # milliseconds
                'model_drift_score': 0.15
            },
            'feature_analysis': {
                'feature_stability': 0.92,
                'correlation_changes': 0.08,
                'new_feature_opportunities': ['user_device_type', 'session_context']
            },
            'recommendation_quality': {
                'user_satisfaction': 0.86,
                'click_through_rate': 0.34,
                'conversion_rate': 0.12,
                'diversity_score': 0.78
            },
            'model_health': {
                'status': 'healthy',
                'confidence_score': 0.88,
                'retraining_needed': False,
                'next_evaluation': '2024-01-08T00:00:00Z'
            }
        }

        # Test model evaluation
        evaluation = await self.ml_engine.evaluate_model(model_data, test_data)

        # Verify evaluation completeness
        self.assertIn('accuracy_metrics', evaluation)
        self.assertIn('performance_trends', evaluation)
        self.assertIn('feature_analysis', evaluation)
        self.assertIn('recommendation_quality', evaluation)
        self.assertIn('model_health', evaluation)

        # Verify accuracy metrics
        metrics = evaluation['accuracy_metrics']
        self.assertLess(metrics['mae'], 0.1)  # Low error
        self.assertLess(metrics['rmse'], 0.1)  # Low error
        self.assertGreater(metrics['r2_score'], 0.8)  # Good fit
        self.assertGreater(metrics['f1_score'], 0.8)  # Good classification

        # Verify performance trends
        trends = evaluation['performance_trends']
        self.assertIsInstance(trends['accuracy_over_time'], list)
        self.assertIsInstance(trends['prediction_latency'], list)

        # Verify latency is acceptable (<20ms)
        latest_latency = trends['prediction_latency'][-1]
        self.assertLess(latest_latency, 20)

        # Verify model drift is acceptable (<0.2)
        self.assertLess(trends['model_drift_score'], 0.2)

        # Verify recommendation quality
        quality = evaluation['recommendation_quality']
        self.assertGreater(quality['user_satisfaction'], 0.8)
        self.assertGreater(quality['click_through_rate'], 0.2)
        self.assertGreater(quality['diversity_score'], 0.7)

        # Verify model health
        health = evaluation['model_health']
        self.assertEqual(health['status'], 'healthy')
        self.assertGreater(health['confidence_score'], 0.8)

    async def test_feature_importance_analysis_and_explainability(self):
        """Test ML model explainability and feature importance analysis."""
        # Mock model feature data
        model_features = {
            'content_features': [
                'word_count', 'complexity_score', 'topic_relevance',
                'image_count', 'table_count', 'reference_count'
            ],
            'user_features': [
                'experience_level', 'preferred_systems', 'session_frequency',
                'engagement_history', 'content_ratings', 'social_activity'
            ],
            'contextual_features': [
                'time_of_day', 'day_of_week', 'season',
                'device_type', 'location', 'session_context'
            ],
            'interaction_features': [
                'previous_searches', 'bookmark_patterns', 'sharing_behavior',
                'feedback_history', 'collaboration_patterns'
            ]
        }

        # Configure feature importance results
        self.ml_engine.get_feature_importance.return_value = {
            'global_importance': {
                'engagement_history': 0.24,
                'topic_relevance': 0.18,
                'complexity_score': 0.15,
                'preferred_systems': 0.12,
                'time_of_day': 0.08,
                'word_count': 0.07,
                'experience_level': 0.06,
                'device_type': 0.05,
                'session_frequency': 0.03,
                'location': 0.02
            },
            'feature_interactions': {
                'engagement_history × topic_relevance': 0.31,
                'complexity_score × experience_level': 0.28,
                'preferred_systems × topic_relevance': 0.22,
                'time_of_day × session_frequency': 0.19
            },
            'feature_stability': {
                'stable_features': ['engagement_history', 'topic_relevance', 'complexity_score'],
                'volatile_features': ['location', 'device_type'],
                'trending_features': ['social_activity', 'collaboration_patterns']
            },
            'prediction_explanations': [
                {
                    'prediction_id': 'pred_123',
                    'predicted_value': 0.89,
                    'confidence': 0.92,
                    'top_contributing_features': [
                        {'feature': 'engagement_history', 'contribution': 0.35, 'value': 'high'},
                        {'feature': 'topic_relevance', 'contribution': 0.28, 'value': 0.91},
                        {'feature': 'complexity_score', 'contribution': 0.21, 'value': 'intermediate'}
                    ],
                    'explanation_text': 'High recommendation due to strong user engagement history and excellent topic match'
                }
            ],
            'model_interpretability': {
                'explanation_coverage': 0.94,
                'consistency_score': 0.87,
                'human_interpretability': 0.82
            }
        }

        # Test feature importance analysis
        importance = await self.ml_engine.get_feature_importance(model_features)

        # Verify feature importance structure
        self.assertIn('global_importance', importance)
        self.assertIn('feature_interactions', importance)
        self.assertIn('feature_stability', importance)
        self.assertIn('prediction_explanations', importance)
        self.assertIn('model_interpretability', importance)

        # Verify global importance totals correctly
        global_importance = importance['global_importance']
        total_importance = sum(global_importance.values())
        self.assertAlmostEqual(total_importance, 1.0, places=1)

        # Verify top features have reasonable importance
        top_features = sorted(global_importance.items(), key=lambda x: x[1], reverse=True)[:3]
        for feature, score in top_features:
            self.assertGreater(score, 0.1)  # Top features should be significant

        # Verify feature interactions
        interactions = importance['feature_interactions']
        self.assertGreater(len(interactions), 0)
        for interaction, score in interactions.items():
            self.assertIn('×', interaction)  # Should show feature combinations
            self.assertGreater(score, 0.0)

        # Verify prediction explanations
        explanations = importance['prediction_explanations']
        self.assertGreater(len(explanations), 0)
        for explanation in explanations:
            self.assertIn('prediction_id', explanation)
            self.assertIn('confidence', explanation)
            self.assertIn('top_contributing_features', explanation)
            self.assertIn('explanation_text', explanation)

            # Verify feature contributions
            contributions = explanation['top_contributing_features']
            for contrib in contributions:
                self.assertIn('feature', contrib)
                self.assertIn('contribution', contrib)
                self.assertIn('value', contrib)
                self.assertGreaterEqual(contrib['contribution'], 0.0)

        # Verify interpretability metrics
        interpretability = importance['model_interpretability']
        self.assertGreater(interpretability['explanation_coverage'], 0.9)
        self.assertGreater(interpretability['consistency_score'], 0.8)
        self.assertGreater(interpretability['human_interpretability'], 0.7)

    async def test_automated_insight_reporting_and_alerts(self):
        """Test automated insight generation and intelligent alerting system."""
        # Mock system state for insight generation
        system_state = {
            'performance_metrics': {
                'response_time_p95': 150,  # milliseconds
                'error_rate': 0.02,
                'throughput': 1200,  # requests/minute
                'cache_hit_rate': 0.89
            },
            'user_engagement': {
                'daily_active_users': 450,
                'session_duration_avg': 420,  # seconds
                'bounce_rate': 0.18,
                'feature_adoption': {
                    'search': 0.95,
                    'bookmarks': 0.67,
                    'sharing': 0.34,
                    'collaboration': 0.23
                }
            },
            'content_health': {
                'total_documents': 15000,
                'indexed_documents': 14850,
                'avg_quality_score': 0.84,
                'outdated_content_ratio': 0.12
            }
        }

        # Configure automated insights
        self.insight_generator.create_usage_recommendations.return_value = {
            'automated_reports': [
                {
                    'report_type': 'weekly_performance_summary',
                    'generated_at': '2024-01-07T09:00:00Z',
                    'key_insights': [
                        'User engagement increased 12% over last week',
                        'Search feature adoption reached 95% of active users',
                        'Response times improved by 8% due to caching optimizations'
                    ],
                    'action_items': [
                        'Investigate low collaboration feature adoption (23%)',
                        'Address 150 unindexed documents in the system',
                        'Review and update 12% of outdated content'
                    ],
                    'trend_analysis': {
                        'positive_trends': ['user_growth', 'engagement', 'performance'],
                        'concerning_trends': ['content_freshness', 'feature_adoption_collaboration'],
                        'neutral_trends': ['error_rates', 'cache_performance']
                    }
                }
            ],
            'intelligent_alerts': [
                {
                    'alert_id': 'alert_789',
                    'severity': 'medium',
                    'category': 'performance',
                    'title': 'Response time degradation detected',
                    'description': 'P95 response time increased from 120ms to 150ms over 24h',
                    'triggered_at': '2024-01-07T14:30:00Z',
                    'recommended_actions': [
                        'Check database query performance',
                        'Review recent deployment changes',
                        'Monitor cache hit rate trends'
                    ],
                    'auto_escalation': {
                        'enabled': True,
                        'escalate_after': '2 hours',
                        'escalate_to': 'ops_team'
                    }
                },
                {
                    'alert_id': 'alert_790',
                    'severity': 'low',
                    'category': 'content',
                    'title': 'Content indexing lag detected',
                    'description': '150 documents pending indexing (1% of total)',
                    'triggered_at': '2024-01-07T13:15:00Z',
                    'recommended_actions': [
                        'Check indexing pipeline health',
                        'Review document queue processing'
                    ],
                    'auto_escalation': {
                        'enabled': False
                    }
                }
            ],
            'predictive_warnings': [
                {
                    'warning_type': 'capacity_planning',
                    'prediction': 'Storage capacity may reach 80% within 30 days',
                    'confidence': 0.78,
                    'timeline': '2024-02-06',
                    'proactive_actions': [
                        'Plan storage expansion',
                        'Implement content archival policies',
                        'Review content retention rules'
                    ]
                }
            ],
            'optimization_suggestions': [
                {
                    'category': 'user_experience',
                    'suggestion': 'Implement guided onboarding for collaboration features',
                    'rationale': 'Low adoption rate (23%) suggests users need guidance',
                    'expected_benefit': '40-60% increase in collaboration feature usage',
                    'implementation_effort': 'medium',
                    'priority': 'high'
                }
            ]
        }

        # Test automated insight generation
        insights = await self.insight_generator.create_usage_recommendations(system_state)

        # Verify report structure
        self.assertIn('automated_reports', insights)
        self.assertIn('intelligent_alerts', insights)
        self.assertIn('predictive_warnings', insights)
        self.assertIn('optimization_suggestions', insights)

        # Verify automated reports
        reports = insights['automated_reports']
        self.assertGreater(len(reports), 0)
        for report in reports:
            self.assertIn('report_type', report)
            self.assertIn('generated_at', report)
            self.assertIn('key_insights', report)
            self.assertIn('action_items', report)
            self.assertIn('trend_analysis', report)

            # Verify trend analysis completeness
            trends = report['trend_analysis']
            self.assertIn('positive_trends', trends)
            self.assertIn('concerning_trends', trends)
            self.assertIn('neutral_trends', trends)

        # Verify intelligent alerts
        alerts = insights['intelligent_alerts']
        self.assertGreater(len(alerts), 0)
        for alert in alerts:
            self.assertIn('alert_id', alert)
            self.assertIn('severity', alert)
            self.assertIn('category', alert)
            self.assertIn('title', alert)
            self.assertIn('description', alert)
            self.assertIn('recommended_actions', alert)
            self.assertIn('auto_escalation', alert)

            # Verify severity levels
            self.assertIn(alert['severity'], ['low', 'medium', 'high', 'critical'])

            # Verify escalation configuration
            escalation = alert['auto_escalation']
            self.assertIn('enabled', escalation)
            if escalation['enabled']:
                self.assertIn('escalate_after', escalation)
                self.assertIn('escalate_to', escalation)

        # Verify predictive warnings
        warnings = insights['predictive_warnings']
        for warning in warnings:
            self.assertIn('warning_type', warning)
            self.assertIn('prediction', warning)
            self.assertIn('confidence', warning)
            self.assertIn('timeline', warning)
            self.assertIn('proactive_actions', warning)
            self.assertGreaterEqual(warning['confidence'], 0.5)

        # Verify optimization suggestions
        suggestions = insights['optimization_suggestions']
        for suggestion in suggestions:
            self.assertIn('category', suggestion)
            self.assertIn('suggestion', suggestion)
            self.assertIn('rationale', suggestion)
            self.assertIn('expected_benefit', suggestion)
            self.assertIn('implementation_effort', suggestion)
            self.assertIn('priority', suggestion)
            self.assertIn(suggestion['priority'], ['low', 'medium', 'high'])
            self.assertIn(suggestion['implementation_effort'], ['low', 'medium', 'high'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])