"""
Persona response validator for evaluating response appropriateness.
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import PersonaProfile, PersonaContext, PersonaMetrics
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class PersonaResponseValidator:
    """Validates response appropriateness for specific personas."""

    def __init__(self):
        # Vocabulary complexity patterns
        self.technical_terms = {
            "dnd5e": ["proficiency bonus", "spell slot", "action economy", "bounded accuracy"],
            "pathfinder": ["trait", "feat", "skill rank", "base attack bonus"],
            "general": ["modifier", "dice pool", "saving throw", "initiative"]
        }

        # Response length guidelines by detail level
        self.length_guidelines = {
            "brief": (50, 200),
            "moderate": (150, 500),
            "detailed": (300, 800),
            "comprehensive": (500, 1500)
        }

    def validate_response_appropriateness(self,
                                        response: str,
                                        persona_context: PersonaContext,
                                        query: str = "") -> PersonaMetrics:
        """Validate if response is appropriate for the given persona."""
        persona = persona_context.persona_profile
        query_id = f"query_{hash(query)}_{int(datetime.now().timestamp())}"

        # Calculate individual scores
        appropriateness_score = self._calculate_appropriateness_score(response, persona)
        detail_level_match = self._evaluate_detail_level_match(response, persona)
        language_appropriateness = self._evaluate_language_appropriateness(response, persona)
        citation_quality = self._evaluate_citation_quality(response, persona)

        # Response characteristics
        response_length = len(response)
        citation_count = self._count_citations(response)
        example_count = self._count_examples(response)
        technical_terms_count = self._count_technical_terms(response)

        # User experience metrics
        complexity_match = self._evaluate_complexity_match(response, persona)
        user_satisfaction_predicted = self._predict_user_satisfaction(
            appropriateness_score, detail_level_match, complexity_match
        )

        # Validation flags
        has_hallucinations = self._detect_potential_hallucinations(response)
        has_inappropriate_content = self._detect_inappropriate_content(response, persona)
        has_accessibility_issues = self._detect_accessibility_issues(response, persona)

        return PersonaMetrics(
            persona_id=persona.id,
            query_id=query_id,
            appropriateness_score=appropriateness_score,
            detail_level_match=detail_level_match,
            language_appropriateness=language_appropriateness,
            citation_quality=citation_quality,
            response_length=response_length,
            citation_count=citation_count,
            example_count=example_count,
            technical_terms_count=technical_terms_count,
            response_time_ms=0,  # Set by caller
            complexity_match=complexity_match,
            user_satisfaction_predicted=user_satisfaction_predicted,
            has_hallucinations=has_hallucinations,
            has_inappropriate_content=has_inappropriate_content,
            has_accessibility_issues=has_accessibility_issues,
            timestamp=datetime.now()
        )

    def _calculate_appropriateness_score(self, response: str, persona: PersonaProfile) -> float:
        """Calculate overall appropriateness score (0-1)."""
        scores = []

        # Detail level appropriateness
        detail_score = self._evaluate_detail_level_match(response, persona)
        scores.append(detail_score)

        # Technical complexity appropriateness
        complexity_score = self._evaluate_complexity_match(response, persona)
        scores.append(complexity_score)

        # Citation appropriateness
        citation_score = self._evaluate_citation_quality(response, persona)
        scores.append(citation_score)

        # Example appropriateness
        example_score = self._evaluate_example_appropriateness(response, persona)
        scores.append(example_score)

        # Language appropriateness
        language_score = self._evaluate_language_appropriateness(response, persona)
        scores.append(language_score)

        return sum(scores) / len(scores)

    def _evaluate_detail_level_match(self, response: str, persona: PersonaProfile) -> float:
        """Evaluate if response detail level matches persona expectations."""
        response_length = len(response)
        expected_range = self.length_guidelines.get(persona.preferred_detail_level, (150, 500))

        min_length, max_length = expected_range

        if min_length <= response_length <= max_length:
            return 1.0
        elif response_length < min_length:
            # Too brief - calculate penalty
            shortage = min_length - response_length
            penalty = min(0.5, shortage / min_length)
            return 1.0 - penalty
        else:
            # Too verbose - calculate penalty
            excess = response_length - max_length
            penalty = min(0.5, excess / max_length)
            return 1.0 - penalty

    def _evaluate_language_appropriateness(self, response: str, persona: PersonaProfile) -> float:
        """Evaluate language complexity and style appropriateness."""
        score = 1.0

        # Check technical complexity vs persona comfort
        technical_terms = self._count_technical_terms(response)
        if persona.technical_comfort < 5 and technical_terms > 3:
            # Too technical for low-comfort user
            score -= 0.3
        elif persona.technical_comfort >= 8 and technical_terms == 0:
            # Not technical enough for expert
            score -= 0.2

        # Check for accessibility considerations
        if persona.accessibility_needs:
            if "screen_reader" in persona.accessibility_needs:
                # Check for screen reader friendly formatting
                if not self._is_screen_reader_friendly(response):
                    score -= 0.3

        # Check mobile-friendly formatting
        if persona.mobile_context:
            if not self._is_mobile_friendly(response):
                score -= 0.2

        return max(0.0, score)

    def _evaluate_citation_quality(self, response: str, persona: PersonaProfile) -> float:
        """Evaluate citation quality relative to persona expectations."""
        citation_count = self._count_citations(response)

        if persona.expects_citations:
            if citation_count == 0:
                return 0.0
            elif citation_count >= 2:
                return 1.0
            else:
                return 0.5
        else:
            # Persona doesn't expect citations
            if citation_count == 0:
                return 1.0
            elif citation_count <= 2:
                return 0.8  # Not bad to have some
            else:
                return 0.6  # Too many might overwhelm

    def _evaluate_complexity_match(self, response: str, persona: PersonaProfile) -> float:
        """Evaluate if response complexity matches persona technical comfort."""
        technical_terms = self._count_technical_terms(response)
        sentences = len(re.findall(r'[.!?]+', response))
        avg_sentence_length = len(response.split()) / max(1, sentences)

        # Calculate complexity score based on technical terms and sentence structure
        complexity_score = 0
        if technical_terms > 5:
            complexity_score += 3
        elif technical_terms > 2:
            complexity_score += 2
        elif technical_terms > 0:
            complexity_score += 1

        if avg_sentence_length > 20:
            complexity_score += 2
        elif avg_sentence_length > 15:
            complexity_score += 1

        # Normalize to 0-10 scale
        response_complexity = min(10, complexity_score)

        # Compare with persona technical comfort
        difference = abs(response_complexity - persona.technical_comfort)
        if difference <= 1:
            return 1.0
        elif difference <= 2:
            return 0.8
        elif difference <= 3:
            return 0.6
        else:
            return 0.4

    def _evaluate_example_appropriateness(self, response: str, persona: PersonaProfile) -> float:
        """Evaluate if examples match persona expectations."""
        example_count = self._count_examples(response)

        if persona.expects_examples:
            if example_count == 0:
                return 0.3  # Missing expected examples
            elif example_count >= 1:
                return 1.0
        else:
            # Persona doesn't expect examples
            if example_count == 0:
                return 1.0
            elif example_count <= 1:
                return 0.8  # One example is okay
            else:
                return 0.6  # Too many examples

        return 0.5

    def _predict_user_satisfaction(self,
                                 appropriateness_score: float,
                                 detail_level_match: float,
                                 complexity_match: float) -> float:
        """Predict user satisfaction based on various factors."""
        # Weighted average of key factors
        weights = {
            "appropriateness": 0.4,
            "detail_level": 0.3,
            "complexity": 0.3
        }

        satisfaction = (
            appropriateness_score * weights["appropriateness"] +
            detail_level_match * weights["detail_level"] +
            complexity_match * weights["complexity"]
        )

        return satisfaction

    def _count_citations(self, response: str) -> int:
        """Count citations in response."""
        # Look for common citation patterns
        patterns = [
            r'\[([^\]]+)\]',  # [Source Name]
            r'\(([^)]+\.pdf[^)]*)\)',  # (filename.pdf)
            r'\(([^)]*p\.\s*\d+[^)]*)\)',  # (p. 123)
            r'source:\s*[^\n]+',  # source: ...
        ]

        total_citations = 0
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            total_citations += len(matches)

        return total_citations

    def _count_examples(self, response: str) -> int:
        """Count examples in response."""
        example_indicators = [
            r'for example',
            r'e\.g\.',
            r'such as',
            r'like:',
            r'example:',
            r'instance:',
            r'consider'
        ]

        example_count = 0
        for indicator in example_indicators:
            matches = re.findall(indicator, response, re.IGNORECASE)
            example_count += len(matches)

        return example_count

    def _count_technical_terms(self, response: str) -> int:
        """Count technical terms in response."""
        response_lower = response.lower()
        technical_count = 0

        for category, terms in self.technical_terms.items():
            for term in terms:
                if term.lower() in response_lower:
                    technical_count += 1

        return technical_count

    def _detect_potential_hallucinations(self, response: str) -> bool:
        """Detect potential hallucinations (basic heuristics)."""
        # Look for overly specific claims without sources
        suspicious_patterns = [
            r'exactly \d+',  # "exactly 42 points"
            r'always results in',  # Absolute claims
            r'never happens',
            r'guaranteed to',
            r'100% chance',
            r'impossible to'
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return True

        return False

    def _detect_inappropriate_content(self, response: str, persona: PersonaProfile) -> bool:
        """Detect inappropriate content for persona."""
        # Check for age-inappropriate content for younger personas
        inappropriate_patterns = [
            r'violence',
            r'explicit',
            r'mature content'
        ]

        # For beginner personas, avoid overly complex terminology
        if persona.experience_level.value == "beginner":
            complex_patterns = [
                r'multiclass optimization',
                r'action economy analysis',
                r'bounded accuracy theory'
            ]
            for pattern in complex_patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    return True

        return False

    def _detect_accessibility_issues(self, response: str, persona: PersonaProfile) -> bool:
        """Detect accessibility issues."""
        if "screen_reader" in persona.accessibility_needs:
            return not self._is_screen_reader_friendly(response)

        if persona.mobile_context:
            return not self._is_mobile_friendly(response)

        return False

    def _is_screen_reader_friendly(self, response: str) -> bool:
        """Check if response is screen reader friendly."""
        # Check for proper structure
        has_structure = bool(re.search(r'^\d+\.|\*|-', response, re.MULTILINE))

        # Check for descriptive link text (avoid "click here")
        has_bad_links = bool(re.search(r'click here|read more|link', response, re.IGNORECASE))

        # Check for alt text on tables or complex formatting
        has_complex_formatting = bool(re.search(r'\|.*\|', response))  # Table format

        return has_structure and not has_bad_links and not has_complex_formatting

    def _is_mobile_friendly(self, response: str) -> bool:
        """Check if response is mobile friendly."""
        # Check response length (mobile users prefer shorter responses)
        if len(response) > 800:
            return False

        # Check for excessive line breaks or formatting
        line_breaks = response.count('\n')
        if line_breaks > 10:
            return False

        # Check for horizontal scrolling issues (wide tables, long URLs)
        lines = response.split('\n')
        for line in lines:
            if len(line) > 80:  # Might cause horizontal scrolling
                return False

        return True