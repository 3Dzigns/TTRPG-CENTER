"""
AEHRL Fact Extractor

Extracts factual claims from model outputs for verification against sources.
Uses NLP techniques and pattern matching to identify verifiable statements.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .models import FactClaim
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionPattern:
    """Pattern for extracting specific types of facts."""
    name: str
    pattern: str
    claim_type: str
    confidence_base: float = 0.8


class FactExtractor:
    """
    Extracts factual claims from model-generated text.

    Identifies statements that can be verified against source material,
    including entity attributes, relationships, and quantitative claims.
    """

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize fact extractor.

        Args:
            confidence_threshold: Minimum confidence for extracted facts
        """
        self.confidence_threshold = confidence_threshold
        self.extraction_patterns = self._load_extraction_patterns()

    def _load_extraction_patterns(self) -> List[ExtractionPattern]:
        """Load patterns for extracting different types of facts."""
        return [
            # Quantitative facts
            ExtractionPattern(
                name="damage_dice",
                pattern=r"(?:deals?|takes?|inflicts?)\s+(\d+d\d+(?:\s*[+\-]\s*\d+)?)\s+(?:damage|hit points?)",
                claim_type="damage",
                confidence_base=0.9
            ),
            ExtractionPattern(
                name="armor_class",
                pattern=r"(?:AC|armor class|armou?r class)\s+(?:of\s+)?(\d+)",
                claim_type="armor_class",
                confidence_base=0.95
            ),
            ExtractionPattern(
                name="hit_points",
                pattern=r"(?:has|have)\s+(\d+)\s+hit\s+points?",
                claim_type="hit_points",
                confidence_base=0.9
            ),
            ExtractionPattern(
                name="ability_score",
                pattern=r"(?:STR|DEX|CON|INT|WIS|CHA|Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+(?:of\s+)?(\d+)",
                claim_type="ability_score",
                confidence_base=0.85
            ),
            ExtractionPattern(
                name="level_requirement",
                pattern=r"(?:level\s+)?(\d+)(?:st|nd|rd|th)?\s+level\s+(?:spell|character|requirement)",
                claim_type="level",
                confidence_base=0.8
            ),

            # Entity relationships
            ExtractionPattern(
                name="creature_type",
                pattern=r"(\w+)\s+is\s+a\s+(small|medium|large|huge|gargantuan|tiny)?\s*(aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant|humanoid|monstrosity|ooze|plant|undead)",
                claim_type="creature_type",
                confidence_base=0.85
            ),
            ExtractionPattern(
                name="alignment",
                pattern=r"(\w+)\s+is\s+(lawful|neutral|chaotic)\s+(good|neutral|evil)",
                claim_type="alignment",
                confidence_base=0.8
            ),
            ExtractionPattern(
                name="spell_school",
                pattern=r"(\w+)\s+is\s+a\s+(?:(\d+)(?:st|nd|rd|th)\s+level\s+)?(abjuration|conjuration|divination|enchantment|evocation|illusion|necromancy|transmutation)\s+spell",
                claim_type="spell_school",
                confidence_base=0.9
            ),

            # Location and spatial relationships
            ExtractionPattern(
                name="location_in",
                pattern=r"(\w+(?:\s+\w+)*)\s+(?:is\s+)?(?:located\s+)?(?:in|within|inside)\s+(?:the\s+)?(\w+(?:\s+\w+)*)",
                claim_type="location",
                confidence_base=0.75
            ),
            ExtractionPattern(
                name="distance",
                pattern=r"(\w+(?:\s+\w+)*)\s+is\s+(\d+)\s+(?:feet|miles|yards)\s+(?:from|away from)\s+(\w+(?:\s+\w+)*)",
                claim_type="distance",
                confidence_base=0.8
            ),

            # Descriptive attributes
            ExtractionPattern(
                name="appearance",
                pattern=r"(\w+(?:\s+\w+)*)\s+(?:is|has|appears)\s+((?:tall|short|blue|red|green|golden|silver|dark|light|\w+)\s*(?:\s+and\s+\w+)*)",
                claim_type="appearance",
                confidence_base=0.6
            ),

            # Actions and abilities
            ExtractionPattern(
                name="can_cast",
                pattern=r"(\w+(?:\s+\w+)*)\s+can\s+cast\s+(\w+(?:\s+\w+)*)",
                claim_type="ability",
                confidence_base=0.8
            ),
            ExtractionPattern(
                name="has_resistance",
                pattern=r"(\w+(?:\s+\w+)*)\s+(?:has\s+)?(?:resistance|immunity)\s+to\s+(\w+(?:\s+damage)?)",
                claim_type="resistance",
                confidence_base=0.85
            )
        ]

    def extract_facts(self, text: str, context: str = "") -> List[FactClaim]:
        """
        Extract factual claims from text.

        Args:
            text: Text to extract facts from
            context: Additional context for extraction

        Returns:
            List of extracted fact claims
        """
        try:
            logger.debug(f"Extracting facts from text: {text[:100]}...")

            claims = []

            # Apply each extraction pattern
            for pattern in self.extraction_patterns:
                pattern_claims = self._extract_with_pattern(text, pattern, context)
                claims.extend(pattern_claims)

            # Extract general assertions
            general_claims = self._extract_general_assertions(text, context)
            claims.extend(general_claims)

            # Filter by confidence threshold
            filtered_claims = [
                claim for claim in claims
                if claim.confidence >= self.confidence_threshold
            ]

            logger.info(f"Extracted {len(filtered_claims)} fact claims from text")
            return filtered_claims

        except Exception as e:
            logger.error(f"Error extracting facts: {str(e)}")
            return []

    def _extract_with_pattern(
        self,
        text: str,
        pattern: ExtractionPattern,
        context: str
    ) -> List[FactClaim]:
        """Extract facts using a specific pattern."""
        claims = []

        try:
            matches = re.finditer(pattern.pattern, text, re.IGNORECASE)

            for match in matches:
                # Calculate confidence based on pattern and context
                confidence = self._calculate_confidence(
                    pattern, match, text, context
                )

                if confidence >= self.confidence_threshold:
                    claim = FactClaim(
                        text=match.group(0),
                        confidence=confidence,
                        context=context,
                        source_span=(match.start(), match.end()),
                        claim_type=pattern.claim_type,
                        metadata={
                            "pattern_name": pattern.name,
                            "extracted_groups": match.groups(),
                            "extraction_method": "pattern_based"
                        }
                    )
                    claims.append(claim)

        except Exception as e:
            logger.warning(f"Error applying pattern {pattern.name}: {str(e)}")

        return claims

    def _extract_general_assertions(self, text: str, context: str) -> List[FactClaim]:
        """Extract general factual assertions using linguistic patterns."""
        claims = []

        try:
            # Split into sentences
            sentences = re.split(r'[.!?]+', text)

            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if len(sentence) < 10:  # Skip very short sentences
                    continue

                # Look for factual assertion patterns
                if self._is_factual_assertion(sentence):
                    confidence = self._calculate_assertion_confidence(sentence, context)

                    if confidence >= self.confidence_threshold:
                        # Calculate sentence position in text
                        sentence_start = text.find(sentence)
                        sentence_end = sentence_start + len(sentence)

                        claim = FactClaim(
                            text=sentence,
                            confidence=confidence,
                            context=context,
                            source_span=(sentence_start, sentence_end),
                            claim_type="general_assertion",
                            metadata={
                                "sentence_index": i,
                                "extraction_method": "assertion_based",
                                "assertion_type": self._classify_assertion(sentence)
                            }
                        )
                        claims.append(claim)

        except Exception as e:
            logger.warning(f"Error extracting general assertions: {str(e)}")

        return claims

    def _is_factual_assertion(self, sentence: str) -> bool:
        """Check if a sentence contains a factual assertion."""
        # Patterns that suggest factual content
        factual_patterns = [
            r'\b(?:is|are|has|have|can|cannot|does|do not)\b',  # State verbs
            r'\b(?:always|never|often|sometimes|usually)\b',    # Frequency
            r'\b(?:all|most|some|many|few|no)\b',              # Quantifiers
            r'\b\d+\b',                                         # Numbers
            r'\b(?:must|should|will|would)\b'                  # Modal verbs
        ]

        # Check for factual indicators
        for pattern in factual_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True

        return False

    def _classify_assertion(self, sentence: str) -> str:
        """Classify the type of assertion."""
        if re.search(r'\b(?:spell|magic|enchant)\b', sentence, re.IGNORECASE):
            return "magic"
        elif re.search(r'\b(?:damage|attack|weapon)\b', sentence, re.IGNORECASE):
            return "combat"
        elif re.search(r'\b(?:creature|monster|beast)\b', sentence, re.IGNORECASE):
            return "creature"
        elif re.search(r'\b(?:location|place|room|area)\b', sentence, re.IGNORECASE):
            return "location"
        else:
            return "general"

    def _calculate_confidence(
        self,
        pattern: ExtractionPattern,
        match: re.Match,
        text: str,
        context: str
    ) -> float:
        """Calculate confidence score for a pattern match."""
        base_confidence = pattern.confidence_base

        # Adjust based on context specificity
        if any(keyword in context.lower() for keyword in ['statistics', 'stats', 'block']):
            base_confidence += 0.1

        # Adjust based on surrounding text patterns
        start, end = match.span()
        surrounding = text[max(0, start-50):min(len(text), end+50)]

        if re.search(r'\b(?:exactly|precisely|specifically)\b', surrounding, re.IGNORECASE):
            base_confidence += 0.05

        if re.search(r'\b(?:approximately|about|roughly|around)\b', surrounding, re.IGNORECASE):
            base_confidence -= 0.05

        # Ensure confidence stays within valid range
        return max(0.0, min(1.0, base_confidence))

    def _calculate_assertion_confidence(self, sentence: str, context: str) -> float:
        """Calculate confidence for general assertions."""
        base_confidence = 0.6

        # Boost confidence for specific patterns
        if re.search(r'\b(?:AC|hit points|damage|level)\b', sentence, re.IGNORECASE):
            base_confidence += 0.2

        if re.search(r'\b\d+\b', sentence):  # Contains numbers
            base_confidence += 0.1

        if re.search(r'\b(?:spell|magic|creature|location)\b', sentence, re.IGNORECASE):
            base_confidence += 0.1

        # Reduce confidence for uncertain language
        if re.search(r'\b(?:might|may|could|perhaps|possibly)\b', sentence, re.IGNORECASE):
            base_confidence -= 0.2

        if re.search(r'\b(?:seems|appears|looks like)\b', sentence, re.IGNORECASE):
            base_confidence -= 0.1

        return max(0.0, min(1.0, base_confidence))

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.

        Returns:
            Dictionary mapping entity types to lists of entities
        """
        entities = {
            "creatures": [],
            "spells": [],
            "locations": [],
            "items": [],
            "characters": []
        }

        try:
            # Simple pattern-based entity extraction
            # Creatures (capitalized, often with descriptors)
            creature_pattern = r'\b(?:Ancient|Young|Adult)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Dragon|Goblin|Orc|Elf|Dwarf|Giant|Wizard|Fighter|Rogue|Cleric)\b'
            creatures = re.findall(creature_pattern, text)
            entities["creatures"].extend(creatures)

            # Spells (often italicized or quoted, common spell patterns)
            spell_pattern = r'\b(?:casts?|casting)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
            spells = re.findall(spell_pattern, text)
            entities["spells"].extend(spells)

            # Locations (capitalized, often with descriptors)
            location_pattern = r'\b(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Castle|Tower|Dungeon|Forest|Mountain|City|Temple|Shrine)\b'
            locations = re.findall(location_pattern, text)
            entities["locations"].extend(locations)

            # Remove duplicates
            for entity_type in entities:
                entities[entity_type] = list(set(entities[entity_type]))

        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")

        return entities