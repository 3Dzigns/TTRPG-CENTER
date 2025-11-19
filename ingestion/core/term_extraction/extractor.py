"""
Term extraction for dictionary building.

Extracts meaningful terms from text without requiring heavy NLP dependencies.
Uses regex patterns optimized for TTRPG content (spells, abilities, mechanics).
"""

from __future__ import annotations

import logging
import re
from typing import List, Set

_LOG = logging.getLogger(__name__)


class TermExtractor:
    """
    Extract dictionary terms from text using pattern matching.

    Optimized for TTRPG content: spells, abilities, character classes,
    game mechanics, and other domain-specific terminology.
    """

    def __init__(self, max_terms_per_chunk: int = 15):
        """
        Initialize term extractor.

        Args:
            max_terms_per_chunk: Maximum number of terms to extract per text chunk
        """
        self.max_terms_per_chunk = max_terms_per_chunk

        # Common stop words to filter out
        self.stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "you",
            "your",
            "it",
            "its",
            "they",
            "their",
            "them",
            "he",
            "she",
            "his",
            "her",
            "we",
            "our",
            "us",
        }

        # Patterns for extracting terms
        self.patterns = [
            # Capitalized multi-word phrases (spell names, abilities)
            # Example: "Fireball", "Magic Missile", "Improved Critical"
            (r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", 1.0),
            # Hyphenated terms (game mechanics)
            # Example: "Hit-Point", "Armor-Class"
            (r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)+)\b", 0.9),
            # Terms in quotes (often important concepts)
            # Example: "sneak attack", "rage"
            (r'"([a-z\s]{3,30})"', 0.8),
            # Technical terms with numbers (levels, DCs)
            # Example: "DC 15", "Level 3"
            (r"\b([A-Z]{2,}\s+\d+)\b", 0.7),
            # Single capitalized words (proper nouns, character classes)
            # Example: "Fighter", "Wizard", "Barbarian"
            (r"\b([A-Z][a-z]{3,})\b", 0.5),
        ]

    def extract_terms(self, text: str) -> List[str]:
        """
        Extract dictionary terms from text.

        Args:
            text: Text to extract terms from

        Returns:
            List of extracted terms (deduplicated and scored)
        """
        if not text or not text.strip():
            return []

        # Store terms with their scores
        term_scores: dict[str, float] = {}

        # Apply each pattern
        for pattern, base_score in self.patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                term = match.strip()

                # Skip if it's just a stop word
                if term.lower() in self.stop_words:
                    continue

                # Skip if too short or too long
                if len(term) < 3 or len(term) > 100:
                    continue

                # Calculate final score (prefer terms that appear multiple times)
                occurrences = text.count(term)
                final_score = base_score * min(occurrences, 3)  # Cap bonus at 3x

                # Keep highest score for each term
                if term not in term_scores or term_scores[term] < final_score:
                    term_scores[term] = final_score

        # Sort by score (descending) and return top N
        sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)
        return [term for term, score in sorted_terms[: self.max_terms_per_chunk]]

    def extract_and_normalize(self, text: str) -> List[str]:
        """
        Extract and normalize terms.

        Args:
            text: Text to extract terms from

        Returns:
            List of normalized terms (lowercased, deduplicated)
        """
        terms = self.extract_terms(text)

        # Normalize: lowercase and deduplicate
        normalized: Set[str] = set()
        for term in terms:
            normalized_term = term.lower().strip()
            if normalized_term:
                normalized.add(normalized_term)

        return sorted(list(normalized))  # Sort for consistency
