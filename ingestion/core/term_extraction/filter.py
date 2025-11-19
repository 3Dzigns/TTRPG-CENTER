"""
Dictionary term validation filter.

Filters invalid dictionary terms to prevent OCR noise, table fragments,
and formatting artifacts from polluting the dictionary.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

_LOG = logging.getLogger(__name__)


class DictionaryFilter:
    """
    Validates dictionary terms extracted during processing.

    Filters out:
    - OCR noise (backslashes, repeated words)
    - Table fragments (currency, measurements, ellipses)
    - Formatting artifacts (parenthetical-only terms)
    - Terms that are too short or too long
    - Terms with low alphabetic character ratio
    """

    def __init__(
        self,
        min_length: int = 3,
        max_length: int = 100,
        min_alpha_ratio: float = 0.65,
        enable_logging: bool = False,
    ):
        """
        Initialize dictionary filter.

        Args:
            min_length: Minimum term length (default: 3)
            max_length: Maximum term length (default: 100)
            min_alpha_ratio: Minimum alphabetic character ratio (default: 0.65 = 65%)
            enable_logging: Enable detailed logging (default: False)
        """
        self.min_length = min_length
        self.max_length = max_length
        self.min_alpha_ratio = min_alpha_ratio
        self.enable_logging = enable_logging

        # Table indicators - common in TTRPG rulebooks
        self.table_indicators = [
            "gp",
            "sp",
            "cp",
            "pp",  # Currency
            "lbs",
            "lb",
            "pounds",
            "ounces",
            "oz",  # Weight
            "ft",
            "feet",
            "miles",
            "yards",  # Distance
            "$",
            "\u00a3",
            "\u20ac",  # Currency symbols
            "...",  # Ellipsis (common in tables)
        ]

        # OCR noise patterns
        self.ocr_noise_patterns = [
            r"\\[A-Z]+",  # Backslash followed by caps (e.g., \ODIFIER)
            r"([A-Z]+)\s+\1",  # Repeated words (e.g., MODIFIER MODIFIER)
            r"^[^a-zA-Z]+$",  # Only special characters
        ]

        self.stats = {
            "terms_processed": 0,
            "terms_accepted": 0,
            "rejected_too_short": 0,
            "rejected_too_long": 0,
            "rejected_low_alpha": 0,
            "rejected_parenthetical": 0,
            "rejected_table_indicator": 0,
            "rejected_ocr_noise": 0,
            "rejected_excessive_spaces": 0,
        }

    def is_valid_term(self, term: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a dictionary term against all filters.

        Args:
            term: Dictionary term to validate

        Returns:
            Tuple of (is_valid: bool, rejection_reason: Optional[str])
        """
        self.stats["terms_processed"] += 1

        if not term or not term.strip():
            self.stats["rejected_too_short"] += 1
            return False, "empty"

        term = term.strip()

        # Filter 1: Length constraints
        if len(term) < self.min_length:
            self.stats["rejected_too_short"] += 1
            if self.enable_logging:
                _LOG.debug(f"Rejected (too short): '{term}' (length: {len(term)})")
            return False, "too_short"

        if len(term) > self.max_length:
            self.stats["rejected_too_long"] += 1
            if self.enable_logging:
                _LOG.debug(f"Rejected (too long): '{term}' (length: {len(term)})")
            return False, "too_long"

        # Filter 2: Alphabetic character ratio
        alpha_count = sum(c.isalpha() for c in term)
        alpha_ratio = alpha_count / len(term)

        if alpha_ratio < self.min_alpha_ratio:
            self.stats["rejected_low_alpha"] += 1
            if self.enable_logging:
                _LOG.debug(
                    f"Rejected (low alpha ratio): '{term}' "
                    f"({alpha_ratio:.2%} < {self.min_alpha_ratio:.0%})"
                )
            return False, "low_alpha_ratio"

        # Filter 3: Parenthetical-only terms
        if term.startswith("(") and term.endswith(")"):
            self.stats["rejected_parenthetical"] += 1
            if self.enable_logging:
                _LOG.debug(f"Rejected (parenthetical-only): '{term}'")
            return False, "parenthetical_only"

        # Filter 4: Table indicators
        term_lower = term.lower()
        for indicator in self.table_indicators:
            if indicator in term_lower:
                self.stats["rejected_table_indicator"] += 1
                if self.enable_logging:
                    _LOG.debug(f"Rejected (table indicator '{indicator}'): '{term}'")
                return False, f"table_indicator_{indicator}"

        # Filter 5: OCR noise patterns
        for pattern in self.ocr_noise_patterns:
            if re.search(pattern, term):
                self.stats["rejected_ocr_noise"] += 1
                if self.enable_logging:
                    _LOG.debug(f"Rejected (OCR noise pattern): '{term}'")
                return False, "ocr_noise"

        # Filter 6: Excessive spaces (>8 spaces suggests table/list fragment)
        if term.count(" ") > 8:
            self.stats["rejected_excessive_spaces"] += 1
            if self.enable_logging:
                _LOG.debug(
                    f"Rejected (excessive spaces): '{term}' (spaces: {term.count(' ')})"
                )
            return False, "excessive_spaces"

        # Passed all filters
        self.stats["terms_accepted"] += 1
        return True, None

    def filter_terms(self, terms: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Filter a list of dictionary terms.

        Args:
            terms: List of dictionary terms to validate

        Returns:
            Tuple of (accepted_terms: List[str], rejected_terms: List[Tuple[str, reason]])
        """
        accepted = []
        rejected = []

        for term in terms:
            is_valid, reason = self.is_valid_term(term)

            if is_valid:
                accepted.append(term)
            else:
                rejected.append((term, reason))

        return accepted, rejected

    def get_statistics(self) -> dict:
        """Get filtering statistics."""
        rejection_rate = 0.0
        if self.stats["terms_processed"] > 0:
            rejected_count = (
                self.stats["rejected_too_short"]
                + self.stats["rejected_too_long"]
                + self.stats["rejected_low_alpha"]
                + self.stats["rejected_parenthetical"]
                + self.stats["rejected_table_indicator"]
                + self.stats["rejected_ocr_noise"]
                + self.stats["rejected_excessive_spaces"]
            )
            rejection_rate = (rejected_count / self.stats["terms_processed"]) * 100

        return {**self.stats, "rejection_rate_percent": round(rejection_rate, 2)}

    def log_statistics(self):
        """Log filtering statistics."""
        stats = self.get_statistics()
        _LOG.info(
            "Dictionary filter stats",
            extra={
                "processed": stats["terms_processed"],
                "accepted": stats["terms_accepted"],
                "rejected": stats["terms_processed"] - stats["terms_accepted"],
                "rejection_rate": f"{stats['rejection_rate_percent']}%",
            },
        )
