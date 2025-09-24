"""
Query Intent Classification (QIC) - US-201

Classify queries into intent, domain, and complexity with confidence scoring.
Sub-150ms p95 response time requirement.
"""

from __future__ import annotations

import re
import time
from typing import Dict, List, Literal, TypedDict

from src_common.logging import get_logger


logger = get_logger(__name__)


class Classification(TypedDict):
    """Classification result structure."""

    intent: Literal[
        'fact_lookup',
        'procedural_howto',
        'creative_write',
        'code_help',
        'summarize',
        'multi_hop_reasoning'
    ]
    domain: Literal['ttrpg_rules', 'ttrpg_lore', 'admin', 'system', 'unknown']
    complexity: Literal['low', 'medium', 'high']
    needs_tools: bool
    confidence: float


class QueryClassifier:
    """Heuristic query classifier with optional LLM fallback."""

    def __init__(self):
        """Initialize classifier with patterns and keywords."""

        # Intent classification patterns
        self.intent_patterns = {
            'fact_lookup': [
                r'\bwhat is\b', r'\bdefine\b', r'\bexplain\b', r'\btell me about\b',
                r'\bstats?\b', r'\bac\b', r'\bhp\b', r'\bdamage\b', r'\bmodifier\b'
            ],
            'procedural_howto': [
                r'\bhow to\b', r'\bhow do i\b', r'\bstep by step\b', r'\bguide\b',
                r'\bprocess\b', r'\bprocedure\b', r'\bcreate\b', r'\bmake\b'
            ],
            'creative_write': [
                r'\bwrite\b', r'\bcreate.*story\b', r'\bgenerate\b', r'\bcome up with\b',
                r'\bbackground\b', r'\bcharacter.*idea\b', r'\bplot\b', r'\bcampaign\b'
            ],
            'code_help': [
                r'\bcode\b', r'\bscript\b', r'\bfunction\b', r'\bapi\b', r'\bbug\b',
                r'\berror\b', r'\bdebugging\b', r'\bprogramming\b'
            ],
            'summarize': [
                r'\bsummarize\b', r'\boverview\b', r'\bkey points\b', r'\bmain\b',
                r'\bbrief\b', r'\bquick.*summary\b'
            ],
            'multi_hop_reasoning': [
                r'\bcompare\b', r'\banalyze\b', r'\brelationship\b', r'\bconsequences\b',
                r'\bif.*then\b', r'\bbecause\b', r'\bresult\b'
            ]
        }

        # Domain classification keywords
        self.domain_keywords = {
            'ttrpg_rules': [
                'rules', 'mechanics', 'dice', 'roll', 'saving throw', 'armor class',
                'spell', 'ability score', 'skill check', 'combat', 'initiative',
                'hp', 'hit points', 'damage', 'resistance', 'advantage', 'disadvantage'
            ],
            'ttrpg_lore': [
                'lore', 'history', 'background', 'story', 'character', 'world',
                'setting', 'kingdom', 'deity', 'faction', 'culture', 'legend',
                'mythology', 'campaign', 'adventure', 'quest'
            ],
            'admin': [
                'admin', 'configuration', 'settings', 'user', 'permission',
                'access', 'manage', 'system', 'database', 'cleanup'
            ],
            'system': [
                'api', 'service', 'server', 'debug', 'log', 'error', 'performance',
                'monitor', 'health', 'status', 'deployment'
            ]
        }

        # Complexity indicators
        self.complexity_indicators = {
            'high': [
                r'\bmultiple\b', r'\bcomplex\b', r'\banalyze\b', r'\bcompare\b',
                r'\brelationship\b', r'\bconsequences\b', r'\bimplications\b'
            ],
            'medium': [
                r'\bhow.*work\b', r'\bexplain.*why\b', r'\bprocess\b',
                r'\bstep.*step\b', r'\bguide\b'
            ],
            'low': [
                r'\bwhat is\b', r'\bdefine\b', r'\bsimple\b', r'\bbasic\b',
                r'\bquick\b', r'\bbrief\b'
            ]
        }


    def classify_query(self, query: str) -> Classification:
        """
        Heuristic classifier with optional LLM fallback.

        Args:
            query: Raw user query.

        Returns:
            Classification dict with confidence in [0,1].
        """
        start_time = time.perf_counter()

        try:
            query_lower = query.lower().strip()

            # Classify intent
            intent_scores = self._score_intent(query_lower)
            best_intent = max(intent_scores.items(), key=lambda x: x[1])

            # Classify domain
            domain_scores = self._score_domain(query_lower)
            best_domain = max(domain_scores.items(), key=lambda x: x[1])

            # Classify complexity
            complexity_scores = self._score_complexity(query_lower)
            best_complexity = max(complexity_scores.items(), key=lambda x: x[1])

            # Determine if tools are needed
            needs_tools = self._needs_tools(query_lower, best_intent[0])

            # Calculate overall confidence
            confidence = min(best_intent[1], best_domain[1], best_complexity[1])

            # Ensure minimum confidence and fallback to defaults if needed
            if confidence < 0.3:
                logger.warning(f"Low confidence classification for query: {query[:50]}...")
                confidence = 0.3

            if best_domain[1] < 0.2:
                best_domain = ('unknown', 0.2)

            result = Classification(
                intent=best_intent[0],
                domain=best_domain[0],
                complexity=best_complexity[0],
                needs_tools=needs_tools,
                confidence=confidence
            )

            # Performance logging
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Classification completed in {duration_ms:.1f}ms: {result}")

            # Check p95 performance requirement (150ms)
            if duration_ms > 150:
                logger.warning(f"Classification exceeded p95 target: {duration_ms:.1f}ms")

            return result

        except Exception as e:
            logger.error(f"Classification error: {str(e)}")
            # Return safe defaults
            return Classification(
                intent='fact_lookup',
                domain='unknown',
                complexity='medium',
                needs_tools=True,
                confidence=0.1
            )


    def _score_intent(self, query: str) -> Dict[str, float]:
        """Score query against intent patterns."""
        scores = {}

        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                if re.search(pattern, query):
                    score += 0.3

            # Boost scores for clear indicators
            if intent == 'fact_lookup' and any(word in query for word in ['what', 'define', 'explain']):
                score += 0.2
            elif intent == 'procedural_howto' and 'how' in query:
                score += 0.2

            scores[intent] = min(score, 1.0)

        # Ensure at least one intent has some score
        if all(score == 0 for score in scores.values()):
            scores['fact_lookup'] = 0.4

        return scores


    def _score_domain(self, query: str) -> Dict[str, float]:
        """Score query against domain keywords."""
        scores = {}

        for domain, keywords in self.domain_keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword in query:
                    score += 0.2

            scores[domain] = min(score, 1.0)

        # Unknown domain gets default score if others are low
        scores['unknown'] = 0.1

        return scores


    def _score_complexity(self, query: str) -> Dict[str, float]:
        """Score query complexity."""
        scores = {'low': 0.0, 'medium': 0.0, 'high': 0.0}

        for complexity, patterns in self.complexity_indicators.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    scores[complexity] += 0.3

        # Query length heuristic
        word_count = len(query.split())
        if word_count < 5:
            scores['low'] += 0.2
        elif word_count > 15:
            scores['high'] += 0.2
        else:
            scores['medium'] += 0.2

        # Default to medium if all scores are low
        if all(score < 0.1 for score in scores.values()):
            scores['medium'] = 0.5

        return scores


    def _needs_tools(self, query: str, intent: str) -> bool:
        """Determine if query needs tool usage."""

        # Always need tools for these intents
        if intent in ['code_help', 'multi_hop_reasoning']:
            return True

        # System/admin queries usually need tools
        if any(word in query for word in ['system', 'admin', 'api', 'debug']):
            return True

        # Simple fact lookups may not need tools
        if intent == 'fact_lookup' and len(query.split()) < 5:
            return False

        # Default to needing tools for comprehensive answers
        return True