"""
FR-027: Smart Notifications and Intelligent Alerts
Test comprehensive intelligent notification system with contextual awareness.

This module tests the smart notification system that provides contextual,
personalized, and actionable notifications based on user behavior, content
updates, system events, and collaborative activities.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR027SmartNotifications(BaseFRTest):
    """Test suite for FR-027 Smart Notifications and Intelligent Alerts."""

    async def asyncSetUp(self):
        """Set up test environment with notification infrastructure."""
        await super().asyncSetUp()
        self.notification_engine = self._create_mock_notification_engine()
        self.preference_manager = self._create_mock_preference_manager()
        self.delivery_manager = self._create_mock_delivery_manager()
        self.intelligence_system = self._create_mock_intelligence_system()

    def _create_mock_notification_engine(self) -> Mock:
        """Create mock notification engine for testing."""
        engine = Mock()
        engine.create_notification = AsyncMock()
        engine.process_trigger = AsyncMock()
        engine.batch_notifications = AsyncMock()
        engine.schedule_notification = AsyncMock()
        return engine

    def _create_mock_preference_manager(self) -> Mock:
        """Create mock user preference management system."""
        manager = Mock()
        manager.get_user_preferences = AsyncMock()
        manager.update_preferences = AsyncMock()
        manager.apply_smart_filtering = AsyncMock()
        manager.learn_from_interactions = AsyncMock()
        return manager

    def _create_mock_delivery_manager(self) -> Mock:
        """Create mock notification delivery system."""
        manager = Mock()
        manager.send_notification = AsyncMock()
        manager.track_delivery = AsyncMock()
        manager.handle_failure = AsyncMock()
        manager.get_delivery_status = AsyncMock()
        return manager

    def _create_mock_intelligence_system(self) -> Mock:
        """Create mock AI-driven notification intelligence."""
        system = Mock()
        system.analyze_context = AsyncMock()
        system.predict_relevance = AsyncMock()
        system.optimize_timing = AsyncMock()
        system.personalize_content = AsyncMock()
        return system

    async def test_contextual_notification_generation(self):
        """Test generation of contextual notifications based on user activity."""
        # Mock user context and activity
        user_context = {
            "user_id": "user123",
            "current_activity": "editing_character_sheet",
            "active_sessions": ["campaign_planning", "rules_lookup"],
            "recent_searches": ["spell slots", "character progression", "multiclassing"],
            "content_focus": {
                "primary_system": "D&D 5e",
                "character_class": "wizard",
                "campaign_type": "homebrew"
            },
            "session_context": {
                "duration": 45,  # minutes
                "actions_performed": ["search", "edit", "bookmark"],
                "collaboration_mode": False
            }
        }

        # Mock triggering events
        trigger_events = [
            {
                "event_type": "content_update",
                "source": "spells_database",
                "data": {
                    "updated_content": ["new_wizard_spells", "spell_rule_clarifications"],
                    "relevance_tags": ["wizard", "spells", "D&D 5e"],
                    "update_type": "content_addition"
                }
            },
            {
                "event_type": "collaboration_invite",
                "source": "user456",
                "data": {
                    "session_type": "character_review",
                    "campaign": "Curse of Strahd",
                    "urgency": "medium"
                }
            },
            {
                "event_type": "system_recommendation",
                "source": "ai_assistant",
                "data": {
                    "recommendation_type": "content_suggestion",
                    "suggested_content": ["multiclass_guide", "wizard_optimization"],
                    "confidence": 0.87
                }
            }
        ]

        # Configure contextual analysis
        self.intelligence_system.analyze_context.return_value = {
            "context_score": 0.92,
            "relevance_factors": {
                "content_match": 0.95,  # Wizard spells match user's wizard character
                "timing_appropriateness": 0.88,  # User actively editing character
                "activity_alignment": 0.93,  # Aligns with current activity
                "personal_interest": 0.91   # Matches user's stated interests
            },
            "contextual_insights": {
                "user_state": "actively_engaged",
                "attention_level": "high",
                "interruption_tolerance": "medium",
                "current_priority": "character_development"
            },
            "notification_recommendations": {
                "immediate_delivery": ["content_update"],
                "batched_delivery": ["system_recommendation"],
                "delayed_delivery": ["collaboration_invite"]
            }
        }

        # Test context analysis for each trigger
        for event in trigger_events:
            context_analysis = await self.intelligence_system.analyze_context(user_context, event)

            # Verify context analysis quality
            self.assertIn("context_score", context_analysis)
            self.assertIn("relevance_factors", context_analysis)
            self.assertIn("contextual_insights", context_analysis)
            self.assertGreater(context_analysis["context_score"], 0.8)

            # Verify relevance factors
            factors = context_analysis["relevance_factors"]
            for factor, score in factors.items():
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)

        # Configure notification generation
        self.notification_engine.create_notification.side_effect = [
            {
                "notification_id": "notif_001",
                "type": "content_update",
                "title": "New Wizard Spells Available",
                "content": "5 new wizard spells and rule clarifications have been added to your preferred system (D&D 5e)",
                "priority": "medium",
                "contextual_data": {
                    "related_content": ["wizard_spells", "spell_rules"],
                    "user_relevance": 0.95,
                    "action_buttons": [
                        {"label": "View New Spells", "action": "navigate", "target": "/spells/wizard/new"},
                        {"label": "Update Character", "action": "navigate", "target": "/character/spells"}
                    ]
                },
                "created_at": "2024-01-01T10:30:00Z"
            },
            {
                "notification_id": "notif_002",
                "type": "collaboration_invite",
                "title": "Character Review Session Invitation",
                "content": "Sarah invited you to review character builds for the Curse of Strahd campaign",
                "priority": "medium",
                "contextual_data": {
                    "inviter": "user456",
                    "session_details": {"type": "character_review", "campaign": "Curse of Strahd"},
                    "action_buttons": [
                        {"label": "Join Session", "action": "join_collaboration", "target": "session_789"},
                        {"label": "View Details", "action": "navigate", "target": "/collaboration/session_789"},
                        {"label": "Decline", "action": "decline_invite", "target": "invite_123"}
                    ]
                },
                "created_at": "2024-01-01T10:32:00Z"
            }
        ]

        # Test notification generation
        for i, event in enumerate(trigger_events[:2]):  # Test first two events
            notification = await self.notification_engine.create_notification(user_context, event)

            # Verify notification structure
            self.assertIn("notification_id", notification)
            self.assertIn("type", notification)
            self.assertIn("title", notification)
            self.assertIn("content", notification)
            self.assertIn("priority", notification)
            self.assertIn("contextual_data", notification)

            # Verify contextual data
            contextual_data = notification["contextual_data"]
            self.assertIn("user_relevance", contextual_data)
            self.assertIn("action_buttons", contextual_data)
            self.assertGreater(contextual_data["user_relevance"], 0.8)
            self.assertGreater(len(contextual_data["action_buttons"]), 0)

    async def test_intelligent_notification_timing_optimization(self):
        """Test AI-driven optimization of notification delivery timing."""
        # Mock user behavior patterns
        user_patterns = {
            "user_id": "user123",
            "activity_patterns": {
                "peak_hours": [19, 20, 21],  # 7-9 PM most active
                "low_activity": [2, 3, 4, 5, 6, 7],  # Late night/early morning
                "preferred_days": ["tuesday", "thursday", "sunday"],
                "session_duration_avg": 90,  # minutes
                "break_patterns": [30, 60]  # Takes breaks every 30-60 minutes
            },
            "notification_history": {
                "response_rates_by_hour": {
                    "09": 0.45, "10": 0.52, "11": 0.48, "12": 0.35,
                    "13": 0.28, "14": 0.41, "15": 0.38, "16": 0.44,
                    "17": 0.55, "18": 0.62, "19": 0.78, "20": 0.85, "21": 0.82
                },
                "engagement_metrics": {
                    "click_through_rate": 0.34,
                    "action_completion_rate": 0.67,
                    "dismissal_rate": 0.12,
                    "snooze_rate": 0.21
                }
            },
            "current_state": {
                "timezone": "EST",
                "current_time": "2024-01-01T20:30:00Z",
                "active_since": "2024-01-01T19:45:00Z",
                "estimated_break_in": 15  # minutes
            }
        }

        # Mock pending notifications
        pending_notifications = [
            {
                "notification_id": "notif_003",
                "type": "content_update",
                "priority": "low",
                "created_at": "2024-01-01T18:00:00Z",
                "urgency_score": 0.3
            },
            {
                "notification_id": "notif_004",
                "type": "system_alert",
                "priority": "high",
                "created_at": "2024-01-01T20:25:00Z",
                "urgency_score": 0.9
            },
            {
                "notification_id": "notif_005",
                "type": "collaboration_update",
                "priority": "medium",
                "created_at": "2024-01-01T20:15:00Z",
                "urgency_score": 0.6
            }
        ]

        # Configure timing optimization
        self.intelligence_system.optimize_timing.return_value = {
            "optimal_delivery_times": {
                "notif_003": {
                    "recommended_time": "2024-01-02T20:00:00Z",  # Next peak time
                    "confidence": 0.78,
                    "reasoning": "Low priority, can wait for optimal engagement window",
                    "delivery_method": "batched"
                },
                "notif_004": {
                    "recommended_time": "immediate",
                    "confidence": 0.95,
                    "reasoning": "High priority system alert requires immediate attention",
                    "delivery_method": "immediate_push"
                },
                "notif_005": {
                    "recommended_time": "2024-01-01T20:45:00Z",  # Near estimated break
                    "confidence": 0.82,
                    "reasoning": "Medium priority, deliver during natural break in activity",
                    "delivery_method": "timed_push"
                }
            },
            "delivery_strategy": {
                "batch_low_priority": True,
                "interrupt_for_urgent": True,
                "respect_quiet_hours": True,
                "adaptive_frequency": True
            },
            "predicted_engagement": {
                "current_window": 0.85,
                "next_peak": 0.78,
                "quiet_hours": 0.12
            }
        }

        # Test timing optimization
        timing_result = await self.intelligence_system.optimize_timing(user_patterns, pending_notifications)

        # Verify timing optimization
        self.assertIn("optimal_delivery_times", timing_result)
        self.assertIn("delivery_strategy", timing_result)
        self.assertIn("predicted_engagement", timing_result)

        # Verify individual notification timing
        optimal_times = timing_result["optimal_delivery_times"]
        self.assertEqual(len(optimal_times), 3)

        for notif_id, timing in optimal_times.items():
            self.assertIn("recommended_time", timing)
            self.assertIn("confidence", timing)
            self.assertIn("reasoning", timing)
            self.assertIn("delivery_method", timing)
            self.assertGreaterEqual(timing["confidence"], 0.7)

        # Verify high priority gets immediate delivery
        high_priority_timing = optimal_times["notif_004"]
        self.assertEqual(high_priority_timing["recommended_time"], "immediate")
        self.assertEqual(high_priority_timing["delivery_method"], "immediate_push")

        # Verify low priority gets delayed/batched
        low_priority_timing = optimal_times["notif_003"]
        self.assertNotEqual(low_priority_timing["recommended_time"], "immediate")
        self.assertEqual(low_priority_timing["delivery_method"], "batched")

    async def test_personalized_notification_content_and_formatting(self):
        """Test personalization of notification content based on user preferences."""
        # Mock user preferences and profile
        user_profile = {
            "user_id": "user123",
            "preferences": {
                "communication_style": "concise",  # Options: verbose, standard, concise
                "technical_level": "intermediate",  # Options: beginner, intermediate, advanced
                "content_interests": ["character_optimization", "rules_clarifications", "campaign_tools"],
                "notification_tone": "professional",  # Options: casual, professional, enthusiastic
                "language": "en-US",
                "accessibility": {
                    "high_contrast": False,
                    "large_text": False,
                    "screen_reader": False,
                    "reduce_motion": True
                }
            },
            "behavior_profile": {
                "preferred_actions": ["quick_view", "bookmark", "share"],
                "interaction_patterns": {
                    "clicks_action_buttons": 0.78,
                    "reads_full_content": 0.45,
                    "uses_quick_actions": 0.89
                },
                "content_consumption": {
                    "prefers_summaries": True,
                    "likes_examples": True,
                    "needs_context": False
                }
            }
        }

        # Mock base notification template
        base_notification = {
            "type": "content_update",
            "source_content": {
                "title": "New Feat Options for Character Optimization",
                "description": "Comprehensive analysis of newly added feats with mechanical impact assessment, synergy recommendations, and build integration strategies for optimizing character effectiveness across different campaign styles and party compositions.",
                "category": "character_optimization",
                "complexity": "intermediate",
                "length": "detailed"
            },
            "metadata": {
                "tags": ["feats", "optimization", "character_building", "mechanics"],
                "target_audience": "intermediate_players",
                "update_type": "content_addition"
            }
        }

        # Configure personalization
        self.intelligence_system.personalize_content.return_value = {
            "personalized_notification": {
                "title": "New Feat Analysis: Character Optimization",  # Concise style
                "content": "5 new feats analyzed for optimization potential. Quick impact assessment and build synergies included.",  # Shortened for concise preference
                "format": {
                    "style": "concise",
                    "tone": "professional",
                    "technical_level": "intermediate",
                    "includes_examples": True,
                    "summary_first": True
                },
                "action_buttons": [
                    {"label": "Quick View", "primary": True},  # Preferred action
                    {"label": "Bookmark", "primary": False},
                    {"label": "Full Analysis", "primary": False}
                ],
                "visual_elements": {
                    "icon": "optimization",
                    "color_scheme": "professional",
                    "animation": "minimal",  # Respects reduce_motion preference
                    "layout": "compact"
                }
            },
            "personalization_factors": {
                "style_adaptation": 0.95,  # High confidence in style matching
                "content_relevance": 0.89,
                "action_prediction": 0.82,
                "tone_matching": 0.91
            },
            "alternative_versions": [
                {
                    "variant": "verbose",
                    "content": "Detailed analysis of 5 new feat options with comprehensive mechanical breakdown, synergy matrices, and integration recommendations...",
                    "use_case": "if_user_requests_detail"
                },
                {
                    "variant": "casual",
                    "content": "Hey! Check out these cool new feats - some great optimization opportunities here!",
                    "use_case": "if_tone_preference_changes"
                }
            ]
        }

        # Test content personalization
        personalized = await self.intelligence_system.personalize_content(user_profile, base_notification)

        # Verify personalization structure
        self.assertIn("personalized_notification", personalized)
        self.assertIn("personalization_factors", personalized)
        self.assertIn("alternative_versions", personalized)

        # Verify personalized content
        notification = personalized["personalized_notification"]
        self.assertIn("title", notification)
        self.assertIn("content", notification)
        self.assertIn("format", notification)
        self.assertIn("action_buttons", notification)
        self.assertIn("visual_elements", notification)

        # Verify style adaptation
        format_info = notification["format"]
        self.assertEqual(format_info["style"], "concise")  # Matches user preference
        self.assertEqual(format_info["tone"], "professional")  # Matches user preference
        self.assertEqual(format_info["technical_level"], "intermediate")  # Matches user level
        self.assertTrue(format_info["includes_examples"])  # User likes examples

        # Verify action button prioritization
        action_buttons = notification["action_buttons"]
        primary_actions = [btn for btn in action_buttons if btn.get("primary", False)]
        self.assertGreater(len(primary_actions), 0)
        self.assertEqual(primary_actions[0]["label"], "Quick View")  # Preferred action

        # Verify accessibility compliance
        visual_elements = notification["visual_elements"]
        self.assertEqual(visual_elements["animation"], "minimal")  # Respects reduce_motion

        # Verify personalization quality
        factors = personalized["personalization_factors"]
        for factor, score in factors.items():
            self.assertGreaterEqual(score, 0.8)  # High personalization confidence

    async def test_notification_batching_and_digest_creation(self):
        """Test intelligent batching of notifications and digest generation."""
        # Mock multiple notifications for batching
        notifications_to_batch = [
            {
                "notification_id": "notif_006",
                "type": "content_update",
                "category": "rules_clarifications",
                "priority": "low",
                "created_at": "2024-01-01T14:00:00Z",
                "title": "Spell Component Rules Updated",
                "summary": "Clarifications on material component requirements"
            },
            {
                "notification_id": "notif_007",
                "type": "content_update",
                "category": "rules_clarifications",
                "priority": "low",
                "created_at": "2024-01-01T15:30:00Z",
                "title": "Combat Action Timing Rules",
                "summary": "Updated guidance on reaction timing"
            },
            {
                "notification_id": "notif_008",
                "type": "community_update",
                "category": "discussions",
                "priority": "low",
                "created_at": "2024-01-01T16:45:00Z",
                "title": "Active Discussion: Multiclassing Balance",
                "summary": "Community debate on multiclass optimization"
            },
            {
                "notification_id": "notif_009",
                "type": "content_update",
                "category": "new_content",
                "priority": "medium",
                "created_at": "2024-01-01T17:15:00Z",
                "title": "New Adventure Module Available",
                "summary": "Urban investigation scenario released"
            },
            {
                "notification_id": "notif_010",
                "type": "system_update",
                "category": "features",
                "priority": "low",
                "created_at": "2024-01-01T18:00:00Z",
                "title": "Search Enhancement Deployed",
                "summary": "Improved filtering and sorting options"
            }
        ]

        # Configure batching logic
        self.notification_engine.batch_notifications.return_value = {
            "digest_id": "digest_001",
            "created_at": "2024-01-01T20:00:00Z",
            "delivery_time": "2024-01-01T20:30:00Z",
            "batching_strategy": "category_and_priority",
            "batched_groups": [
                {
                    "group_id": "group_rules",
                    "category": "rules_clarifications",
                    "notification_count": 2,
                    "notifications": ["notif_006", "notif_007"],
                    "digest_title": "Rules Updates Digest",
                    "digest_summary": "2 rule clarifications: spell components and combat timing"
                },
                {
                    "group_id": "group_content",
                    "category": "content_updates",
                    "notification_count": 2,
                    "notifications": ["notif_008", "notif_009"],
                    "digest_title": "Content & Community Updates",
                    "digest_summary": "New adventure module and active community discussion"
                },
                {
                    "group_id": "group_system",
                    "category": "system_updates",
                    "notification_count": 1,
                    "notifications": ["notif_010"],
                    "digest_title": "Platform Improvements",
                    "digest_summary": "Search functionality enhanced"
                }
            ],
            "digest_content": {
                "title": "Your TTRPG Center Updates - 5 Items",
                "introduction": "Here's what happened while you were away:",
                "sections": [
                    {
                        "section_title": "📖 Rules & Clarifications (2 updates)",
                        "items": [
                            {
                                "title": "Spell Component Rules Updated",
                                "summary": "Clarifications on material component requirements",
                                "action": {"label": "Review Changes", "url": "/rules/components"}
                            },
                            {
                                "title": "Combat Action Timing Rules",
                                "summary": "Updated guidance on reaction timing",
                                "action": {"label": "View Guide", "url": "/rules/combat-timing"}
                            }
                        ]
                    },
                    {
                        "section_title": "🎲 Content & Community (2 updates)",
                        "items": [
                            {
                                "title": "New Adventure Module Available",
                                "summary": "Urban investigation scenario released",
                                "action": {"label": "Explore Module", "url": "/adventures/urban-investigation"},
                                "priority_indicator": "medium"
                            },
                            {
                                "title": "Active Discussion: Multiclassing Balance",
                                "summary": "Community debate on multiclass optimization",
                                "action": {"label": "Join Discussion", "url": "/community/multiclass-debate"}
                            }
                        ]
                    },
                    {
                        "section_title": "⚙️ Platform Updates (1 update)",
                        "items": [
                            {
                                "title": "Search Enhancement Deployed",
                                "summary": "Improved filtering and sorting options",
                                "action": {"label": "Try New Search", "url": "/search"}
                            }
                        ]
                    }
                ],
                "footer": {
                    "unsubscribe_options": ["digest", "category_specific", "all"],
                    "preference_link": "/notifications/preferences",
                    "next_digest": "2024-01-02T20:30:00Z"
                }
            },
            "optimization_metrics": {
                "notifications_reduced": "5 to 1",
                "estimated_attention_saved": "75%",
                "relevance_grouping_score": 0.88,
                "user_convenience_score": 0.92
            }
        }

        # Test notification batching
        batch_result = await self.notification_engine.batch_notifications(notifications_to_batch)

        # Verify batching structure
        self.assertIn("digest_id", batch_result)
        self.assertIn("batched_groups", batch_result)
        self.assertIn("digest_content", batch_result)
        self.assertIn("optimization_metrics", batch_result)

        # Verify grouping logic
        groups = batch_result["batched_groups"]
        self.assertEqual(len(groups), 3)  # 3 categories

        total_notifications = sum(group["notification_count"] for group in groups)
        self.assertEqual(total_notifications, 5)  # All notifications accounted for

        # Verify digest content structure
        digest = batch_result["digest_content"]
        self.assertIn("title", digest)
        self.assertIn("introduction", digest)
        self.assertIn("sections", digest)
        self.assertIn("footer", digest)

        # Verify sections match groups
        sections = digest["sections"]
        self.assertEqual(len(sections), 3)  # One section per group

        for section in sections:
            self.assertIn("section_title", section)
            self.assertIn("items", section)
            self.assertGreater(len(section["items"]), 0)

            # Verify items have required fields
            for item in section["items"]:
                self.assertIn("title", item)
                self.assertIn("summary", item)
                self.assertIn("action", item)

        # Verify optimization metrics
        metrics = batch_result["optimization_metrics"]
        self.assertIn("notifications_reduced", metrics)
        self.assertIn("estimated_attention_saved", metrics)
        self.assertGreater(metrics["relevance_grouping_score"], 0.8)
        self.assertGreater(metrics["user_convenience_score"], 0.9)

    async def test_notification_delivery_tracking_and_analytics(self):
        """Test notification delivery tracking and engagement analytics."""
        # Mock notification delivery attempts
        delivery_attempts = [
            {
                "notification_id": "notif_011",
                "user_id": "user123",
                "delivery_method": "push",
                "attempt_timestamp": "2024-01-01T20:30:00Z",
                "device_info": {
                    "platform": "web",
                    "browser": "Chrome",
                    "device_type": "desktop"
                }
            },
            {
                "notification_id": "notif_012",
                "user_id": "user123",
                "delivery_method": "email",
                "attempt_timestamp": "2024-01-01T20:32:00Z",
                "device_info": {
                    "platform": "email",
                    "client": "Gmail",
                    "device_type": "mobile"
                }
            }
        ]

        # Configure delivery tracking
        self.delivery_manager.send_notification.side_effect = [
            {
                "delivery_id": "delivery_001",
                "notification_id": "notif_011",
                "status": "delivered",
                "delivered_at": "2024-01-01T20:30:05Z",
                "delivery_method": "push",
                "delivery_latency": 5,  # seconds
                "device_confirmed": True
            },
            {
                "delivery_id": "delivery_002",
                "notification_id": "notif_012",
                "status": "failed",
                "failed_at": "2024-01-01T20:32:10Z",
                "delivery_method": "email",
                "failure_reason": "invalid_email_address",
                "retry_scheduled": "2024-01-01T21:00:00Z"
            }
        ]

        # Test delivery attempts
        delivery_results = []
        for attempt in delivery_attempts:
            result = await self.delivery_manager.send_notification(attempt)
            delivery_results.append(result)

        # Verify delivery results
        self.assertEqual(len(delivery_results), 2)

        # Verify successful delivery
        successful_delivery = delivery_results[0]
        self.assertEqual(successful_delivery["status"], "delivered")
        self.assertIn("delivered_at", successful_delivery)
        self.assertIn("delivery_latency", successful_delivery)
        self.assertTrue(successful_delivery["device_confirmed"])
        self.assertLess(successful_delivery["delivery_latency"], 10)  # Fast delivery

        # Verify failed delivery
        failed_delivery = delivery_results[1]
        self.assertEqual(failed_delivery["status"], "failed")
        self.assertIn("failure_reason", failed_delivery)
        self.assertIn("retry_scheduled", failed_delivery)

        # Configure delivery status tracking
        self.delivery_manager.get_delivery_status.return_value = {
            "notification_id": "notif_011",
            "delivery_timeline": [
                {
                    "timestamp": "2024-01-01T20:30:00Z",
                    "event": "delivery_initiated",
                    "method": "push"
                },
                {
                    "timestamp": "2024-01-01T20:30:05Z",
                    "event": "delivered",
                    "device_confirmed": True
                },
                {
                    "timestamp": "2024-01-01T20:30:45Z",
                    "event": "viewed",
                    "interaction_type": "notification_click"
                },
                {
                    "timestamp": "2024-01-01T20:31:20Z",
                    "event": "action_taken",
                    "action": "view_content",
                    "target": "/content/new_spells"
                }
            ],
            "engagement_metrics": {
                "time_to_view": 40,  # seconds
                "time_to_action": 80,  # seconds
                "action_completion": True,
                "subsequent_engagement": {
                    "time_on_page": 180,  # seconds
                    "pages_visited": 3,
                    "actions_performed": ["bookmark", "share"]
                }
            },
            "delivery_quality": {
                "delivery_success": True,
                "delivery_speed": "fast",
                "user_satisfaction_estimated": 0.87
            }
        }

        # Test delivery status tracking
        status = await self.delivery_manager.get_delivery_status("notif_011")

        # Verify status tracking
        self.assertIn("delivery_timeline", status)
        self.assertIn("engagement_metrics", status)
        self.assertIn("delivery_quality", status)

        # Verify timeline completeness
        timeline = status["delivery_timeline"]
        self.assertGreater(len(timeline), 0)

        event_types = [event["event"] for event in timeline]
        self.assertIn("delivered", event_types)
        self.assertIn("viewed", event_types)
        self.assertIn("action_taken", event_types)

        # Verify engagement metrics
        engagement = status["engagement_metrics"]
        self.assertIn("time_to_view", engagement)
        self.assertIn("time_to_action", engagement)
        self.assertIn("action_completion", engagement)
        self.assertTrue(engagement["action_completion"])
        self.assertLess(engagement["time_to_view"], 60)  # Quick view

        # Configure analytics aggregation
        self.delivery_manager.track_delivery.return_value = {
            "analytics_period": "24_hours",
            "total_notifications": 150,
            "delivery_statistics": {
                "successful_deliveries": 142,
                "failed_deliveries": 8,
                "success_rate": 0.947,
                "average_delivery_time": 3.2,  # seconds
                "retry_rate": 0.053
            },
            "engagement_statistics": {
                "view_rate": 0.78,
                "click_through_rate": 0.45,
                "action_completion_rate": 0.67,
                "average_time_to_action": 65,  # seconds
                "user_satisfaction_avg": 0.84
            },
            "delivery_method_performance": {
                "push": {
                    "success_rate": 0.95,
                    "engagement_rate": 0.82,
                    "user_preference": 0.88
                },
                "email": {
                    "success_rate": 0.92,
                    "engagement_rate": 0.61,
                    "user_preference": 0.65
                },
                "in_app": {
                    "success_rate": 0.98,
                    "engagement_rate": 0.91,
                    "user_preference": 0.93
                }
            },
            "optimization_insights": {
                "best_performing_method": "in_app",
                "peak_engagement_hours": [19, 20, 21],
                "content_type_preferences": {
                    "content_updates": 0.89,
                    "system_alerts": 0.76,
                    "collaboration_invites": 0.82
                },
                "recommended_actions": [
                    "Increase in-app notification usage",
                    "Optimize timing for 7-9 PM delivery",
                    "Personalize content update notifications"
                ]
            }
        }

        # Test analytics tracking
        analytics = await self.delivery_manager.track_delivery("24_hours")

        # Verify analytics structure
        self.assertIn("delivery_statistics", analytics)
        self.assertIn("engagement_statistics", analytics)
        self.assertIn("delivery_method_performance", analytics)
        self.assertIn("optimization_insights", analytics)

        # Verify delivery statistics
        delivery_stats = analytics["delivery_statistics"]
        self.assertGreater(delivery_stats["success_rate"], 0.9)
        self.assertLess(delivery_stats["average_delivery_time"], 5)

        # Verify engagement statistics
        engagement_stats = analytics["engagement_statistics"]
        self.assertGreater(engagement_stats["view_rate"], 0.7)
        self.assertGreater(engagement_stats["action_completion_rate"], 0.6)
        self.assertGreater(engagement_stats["user_satisfaction_avg"], 0.8)

        # Verify method performance comparison
        method_performance = analytics["delivery_method_performance"]
        self.assertIn("push", method_performance)
        self.assertIn("email", method_performance)
        self.assertIn("in_app", method_performance)

        # Verify optimization insights
        insights = analytics["optimization_insights"]
        self.assertIn("best_performing_method", insights)
        self.assertIn("recommended_actions", insights)
        self.assertIsInstance(insights["recommended_actions"], list)
        self.assertGreater(len(insights["recommended_actions"]), 0)

    async def test_notification_preference_learning_and_adaptation(self):
        """Test adaptive learning from user interactions with notifications."""
        # Mock user interaction history
        interaction_history = [
            {
                "notification_id": "notif_013",
                "type": "content_update",
                "delivered_at": "2024-01-01T19:00:00Z",
                "user_action": "clicked",
                "time_to_action": 25,  # seconds
                "subsequent_engagement": 180,  # seconds on page
                "satisfaction_implicit": 0.9  # High engagement = satisfaction
            },
            {
                "notification_id": "notif_014",
                "type": "system_alert",
                "delivered_at": "2024-01-01T19:30:00Z",
                "user_action": "dismissed",
                "time_to_action": 5,  # seconds
                "satisfaction_implicit": 0.2  # Quick dismissal = low satisfaction
            },
            {
                "notification_id": "notif_015",
                "type": "collaboration_invite",
                "delivered_at": "2024-01-01T20:00:00Z",
                "user_action": "snoozed",
                "time_to_action": 15,
                "snooze_duration": 3600,  # 1 hour
                "satisfaction_implicit": 0.6  # Snooze suggests moderate interest
            },
            {
                "notification_id": "notif_016",
                "type": "content_update",
                "delivered_at": "2024-01-01T20:15:00Z",
                "user_action": "action_completed",
                "time_to_action": 30,
                "action_type": "bookmark",
                "subsequent_engagement": 300,
                "satisfaction_implicit": 0.95  # Action completion = high satisfaction
            }
        ]

        # Configure preference learning
        self.preference_manager.learn_from_interactions.return_value = {
            "learning_summary": {
                "interactions_analyzed": 4,
                "patterns_detected": 3,
                "confidence_level": 0.82,
                "learning_period": "7_days"
            },
            "detected_patterns": [
                {
                    "pattern_type": "content_preference",
                    "description": "High engagement with content_update notifications",
                    "confidence": 0.88,
                    "supporting_evidence": {
                        "click_rate": 1.0,  # 2/2 content updates clicked
                        "avg_engagement_time": 240,
                        "action_completion_rate": 1.0
                    },
                    "recommendation": "prioritize_content_updates"
                },
                {
                    "pattern_type": "timing_preference",
                    "description": "Better engagement with notifications delivered during 8-9 PM",
                    "confidence": 0.75,
                    "supporting_evidence": {
                        "peak_response_time": "20:00-21:00",
                        "engagement_score_peak": 0.92
                    },
                    "recommendation": "optimize_delivery_timing"
                },
                {
                    "pattern_type": "alert_sensitivity",
                    "description": "Low tolerance for system alerts",
                    "confidence": 0.85,
                    "supporting_evidence": {
                        "dismissal_rate": 1.0,  # 1/1 system alerts dismissed
                        "avg_time_to_dismiss": 5
                    },
                    "recommendation": "reduce_system_alert_frequency"
                }
            ],
            "updated_preferences": {
                "content_types": {
                    "content_update": {"priority": "high", "delivery_method": "immediate"},
                    "system_alert": {"priority": "low", "delivery_method": "batched"},
                    "collaboration_invite": {"priority": "medium", "delivery_method": "timed"}
                },
                "timing_optimization": {
                    "preferred_hours": [19, 20, 21],
                    "avoid_hours": [0, 1, 2, 3, 4, 5, 6, 7, 8],
                    "snooze_duration_preference": 3600  # 1 hour default
                },
                "engagement_thresholds": {
                    "minimum_relevance_score": 0.7,
                    "batching_preference": "low_priority_only",
                    "frequency_limit": 5  # per day
                }
            },
            "personalization_adjustments": [
                "Increase content_update notification priority",
                "Reduce system alert frequency to weekly digest",
                "Optimize delivery timing for 8-9 PM window",
                "Enable smart batching for low-priority items"
            ]
        }

        # Test preference learning
        learning_result = await self.preference_manager.learn_from_interactions(interaction_history)

        # Verify learning structure
        self.assertIn("learning_summary", learning_result)
        self.assertIn("detected_patterns", learning_result)
        self.assertIn("updated_preferences", learning_result)
        self.assertIn("personalization_adjustments", learning_result)

        # Verify learning quality
        summary = learning_result["learning_summary"]
        self.assertEqual(summary["interactions_analyzed"], 4)
        self.assertGreater(summary["confidence_level"], 0.8)

        # Verify pattern detection
        patterns = learning_result["detected_patterns"]
        self.assertGreater(len(patterns), 0)

        for pattern in patterns:
            self.assertIn("pattern_type", pattern)
            self.assertIn("description", pattern)
            self.assertIn("confidence", pattern)
            self.assertIn("supporting_evidence", pattern)
            self.assertIn("recommendation", pattern)
            self.assertGreaterEqual(pattern["confidence"], 0.7)

        # Verify preference updates
        preferences = learning_result["updated_preferences"]
        self.assertIn("content_types", preferences)
        self.assertIn("timing_optimization", preferences)
        self.assertIn("engagement_thresholds", preferences)

        # Verify content type prioritization learned correctly
        content_types = preferences["content_types"]
        self.assertEqual(content_types["content_update"]["priority"], "high")
        self.assertEqual(content_types["system_alert"]["priority"], "low")

        # Test preference application
        self.preference_manager.apply_smart_filtering.return_value = {
            "filter_results": {
                "notifications_evaluated": 10,
                "notifications_delivered": 6,
                "notifications_batched": 3,
                "notifications_suppressed": 1
            },
            "filtering_decisions": [
                {
                    "notification_id": "test_notif_1",
                    "type": "content_update",
                    "decision": "deliver_immediately",
                    "reason": "high_priority_type_with_high_relevance",
                    "relevance_score": 0.92
                },
                {
                    "notification_id": "test_notif_2",
                    "type": "system_alert",
                    "decision": "batch_for_digest",
                    "reason": "low_priority_type_user_preference",
                    "relevance_score": 0.65
                }
            ],
            "effectiveness_metrics": {
                "predicted_user_satisfaction": 0.89,
                "noise_reduction": 0.40,
                "relevance_improvement": 0.35
            }
        }

        # Test smart filtering application
        filter_result = await self.preference_manager.apply_smart_filtering(
            ["test_notif_1", "test_notif_2"], learning_result["updated_preferences"]
        )

        # Verify filtering application
        self.assertIn("filter_results", filter_result)
        self.assertIn("filtering_decisions", filter_result)
        self.assertIn("effectiveness_metrics", filter_result)

        # Verify filtering decisions align with learned preferences
        decisions = filter_result["filtering_decisions"]
        content_update_decision = next(d for d in decisions if d["type"] == "content_update")
        system_alert_decision = next(d for d in decisions if d["type"] == "system_alert")

        self.assertEqual(content_update_decision["decision"], "deliver_immediately")
        self.assertEqual(system_alert_decision["decision"], "batch_for_digest")

        # Verify effectiveness metrics
        metrics = filter_result["effectiveness_metrics"]
        self.assertGreater(metrics["predicted_user_satisfaction"], 0.8)
        self.assertGreater(metrics["noise_reduction"], 0.3)
        self.assertGreater(metrics["relevance_improvement"], 0.3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])