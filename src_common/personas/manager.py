"""
Persona management system for loading, caching, and managing persona profiles.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import (
    PersonaProfile, PersonaContext, PersonaTestScenario,
    PersonaType, ExperienceLevel, UserRole, SessionContext
)
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class PersonaManager:
    """Manages persona profiles and contexts for testing."""

    def __init__(self, personas_dir: Optional[Path] = None):
        self.personas_dir = personas_dir or Path("Personas")
        self.profiles_cache: Dict[str, PersonaProfile] = {}
        self.scenarios_cache: Dict[str, PersonaTestScenario] = {}
        self._load_default_personas()

    def _load_default_personas(self) -> None:
        """Load default persona profiles."""
        # Create comprehensive set of personas for testing
        default_personas = [
            # Experience-based personas
            PersonaProfile(
                id="new_user_basic",
                name="New User - Basic",
                persona_type=PersonaType.NEW_USER,
                experience_level=ExperienceLevel.BEGINNER,
                user_role=UserRole.PLAYER,
                technical_comfort=3,
                preferred_detail_level="detailed",
                expects_examples=True,
                expects_citations=False,
                description="Brand new to TTRPGs, needs explanations and examples"
            ),
            PersonaProfile(
                id="expert_dm",
                name="Expert Dungeon Master",
                persona_type=PersonaType.DUNGEON_MASTER,
                experience_level=ExperienceLevel.EXPERT,
                user_role=UserRole.GAME_MASTER,
                technical_comfort=8,
                preferred_detail_level="brief",
                expects_examples=False,
                expects_citations=True,
                description="Experienced DM who wants quick, accurate rule references"
            ),
            PersonaProfile(
                id="mobile_casual",
                name="Mobile Casual Player",
                persona_type=PersonaType.MOBILE_USER,
                experience_level=ExperienceLevel.INTERMEDIATE,
                user_role=UserRole.PLAYER,
                mobile_context=True,
                time_pressure=True,
                preferred_detail_level="brief",
                technical_comfort=6,
                description="Playing on mobile during break, needs quick answers"
            ),
            PersonaProfile(
                id="streaming_host",
                name="Streaming Host",
                persona_type=PersonaType.STREAMING_HOST,
                experience_level=ExperienceLevel.ADVANCED,
                user_role=UserRole.GAME_MASTER,
                time_pressure=True,
                expects_visual_aids=True,
                technical_comfort=7,
                description="Streaming host who needs quick, audience-friendly explanations"
            ),
            PersonaProfile(
                id="rules_lawyer",
                name="Rules Lawyer",
                persona_type=PersonaType.RULES_LAWYER,
                experience_level=ExperienceLevel.EXPERT,
                user_role=UserRole.PLAYER,
                preferred_detail_level="comprehensive",
                expects_citations=True,
                expects_examples=True,
                technical_comfort=9,
                description="Wants detailed, accurate rule interpretations with sources"
            ),
            PersonaProfile(
                id="world_builder",
                name="World Builder",
                persona_type=PersonaType.WORLD_BUILDER,
                experience_level=ExperienceLevel.ADVANCED,
                user_role=UserRole.GAME_MASTER,
                preferred_detail_level="detailed",
                expects_examples=True,
                expects_visual_aids=True,
                technical_comfort=7,
                description="Creating custom content, needs comprehensive information"
            ),
            PersonaProfile(
                id="multilingual_user",
                name="Multilingual User",
                persona_type=PersonaType.MULTILINGUAL,
                experience_level=ExperienceLevel.INTERMEDIATE,
                user_role=UserRole.PLAYER,
                languages=["English", "Arabic", "Spanish"],
                preferred_detail_level="moderate",
                description="Comfortable with multiple languages, may ask in non-English"
            )
        ]

        for persona in default_personas:
            persona.created_at = datetime.now()
            self.profiles_cache[persona.id] = persona
            logger.info(f"Loaded default persona: {persona.id} ({persona.name})")

    def load_legacy_personas(self) -> List[PersonaProfile]:
        """Load personas from existing Personas/ directory markdown files."""
        legacy_personas = []

        if not self.personas_dir.exists():
            logger.warning(f"Personas directory not found: {self.personas_dir}")
            return legacy_personas

        for persona_file in self.personas_dir.glob("*.md"):
            try:
                profile = self._parse_legacy_persona_file(persona_file)
                if profile:
                    legacy_personas.append(profile)
                    self.profiles_cache[profile.id] = profile
                    logger.info(f"Loaded legacy persona: {profile.id} from {persona_file.name}")
            except Exception as e:
                logger.error(f"Failed to parse persona file {persona_file}: {e}")

        return legacy_personas

    def _parse_legacy_persona_file(self, file_path: Path) -> Optional[PersonaProfile]:
        """Parse legacy persona .md file into PersonaProfile."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            # Extract persona name from first heading
            persona_name = None
            for line in lines:
                if line.strip().startswith("# "):
                    persona_name = line.strip().lstrip("# ").strip()
                    break

            if not persona_name:
                persona_name = file_path.stem

            # Determine persona characteristics from name and content
            persona_id = f"legacy_{file_path.stem.lower()}"

            # Parse persona characteristics from name
            name_lower = persona_name.lower()

            # Determine experience level
            if "expert" in name_lower or "advanced" in name_lower:
                experience_level = ExperienceLevel.EXPERT
            elif "intermediate" in name_lower:
                experience_level = ExperienceLevel.INTERMEDIATE
            elif "new" in name_lower or "beginner" in name_lower:
                experience_level = ExperienceLevel.BEGINNER
            else:
                experience_level = ExperienceLevel.INTERMEDIATE

            # Determine user role
            if "gm" in name_lower or "dm" in name_lower or "master" in name_lower:
                user_role = UserRole.GAME_MASTER
                persona_type = PersonaType.DUNGEON_MASTER
            else:
                user_role = UserRole.PLAYER
                persona_type = PersonaType.PLAYER

            # Detect languages from Q/A patterns
            languages = ["English"]
            if "arabic" in content.lower() or "**arabic" in content.lower():
                languages.append("Arabic")

            # Count Q/A pairs to estimate technical comfort
            qa_count = len(re.findall(r'\*\*\w+\s+[QA]:\*\*', content))
            technical_comfort = min(10, max(3, qa_count // 2 + 3))

            return PersonaProfile(
                id=persona_id,
                name=persona_name,
                persona_type=persona_type,
                experience_level=experience_level,
                user_role=user_role,
                languages=languages,
                technical_comfort=technical_comfort,
                preferred_detail_level="moderate",
                expects_examples=True,
                expects_citations=True,
                description=f"Legacy persona from {file_path.name}",
                tags=["legacy", "imported"],
                created_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error parsing legacy persona file {file_path}: {e}")
            return None

    def get_persona(self, persona_id: str) -> Optional[PersonaProfile]:
        """Get persona profile by ID."""
        return self.profiles_cache.get(persona_id)

    def list_personas(self,
                     persona_type: Optional[PersonaType] = None,
                     experience_level: Optional[ExperienceLevel] = None,
                     user_role: Optional[UserRole] = None) -> List[PersonaProfile]:
        """List personas with optional filtering."""
        personas = list(self.profiles_cache.values())

        if persona_type:
            personas = [p for p in personas if p.persona_type == persona_type]
        if experience_level:
            personas = [p for p in personas if p.experience_level == experience_level]
        if user_role:
            personas = [p for p in personas if p.user_role == user_role]

        return personas

    def create_persona_context(self,
                              persona_id: str,
                              session_context: SessionContext,
                              **kwargs) -> Optional[PersonaContext]:
        """Create persona context for runtime use."""
        persona = self.get_persona(persona_id)
        if not persona:
            logger.error(f"Persona not found: {persona_id}")
            return None

        return PersonaContext(
            persona_profile=persona,
            session_context=session_context,
            **kwargs
        )

    def extract_persona_context_from_request(self, payload: Dict) -> Optional[PersonaContext]:
        """Extract persona context from API request payload."""
        # Look for explicit persona specification
        persona_data = payload.get("persona")
        if not persona_data:
            # Try to infer from user agent, device info, etc.
            user_agent = payload.get("user_agent", "")
            device_type = "mobile" if "mobile" in user_agent.lower() else "desktop"

            # Use a default persona based on device type
            if device_type == "mobile":
                persona_id = "mobile_casual"
            else:
                persona_id = "expert_dm"  # Default to expert user

            session_context = SessionContext.CASUAL_BROWSING
        else:
            persona_id = persona_data.get("id", "expert_dm")
            session_context_str = persona_data.get("session_context", "casual_browsing")
            try:
                session_context = SessionContext(session_context_str)
            except ValueError:
                session_context = SessionContext.CASUAL_BROWSING

        return self.create_persona_context(
            persona_id=persona_id,
            session_context=session_context,
            device_type=payload.get("device_type", "desktop"),
            query_complexity=payload.get("query_complexity", 0.5),
            time_constraint=payload.get("time_constraint"),
            previous_queries=payload.get("previous_queries", [])
        )

    def load_test_scenarios(self) -> List[PersonaTestScenario]:
        """Load comprehensive test scenarios for persona validation."""
        scenarios = []

        # Create test scenarios for each persona
        for persona in self.profiles_cache.values():
            # Basic functionality scenario
            basic_scenario = PersonaTestScenario(
                id=f"{persona.id}_basic_query",
                name=f"{persona.name} - Basic Query",
                persona_profile=persona,
                session_context=SessionContext.RESEARCH,
                query="How do I calculate armor class in D&D 5e?",
                expected_appropriateness_score=0.8,
                expected_detail_level=persona.preferred_detail_level,
                expected_response_traits=self._get_expected_traits(persona),
                tags=["basic", "mechanics"],
                description=f"Basic query test for {persona.name}"
            )
            scenarios.append(basic_scenario)

            # Complex scenario for advanced users
            if persona.experience_level in [ExperienceLevel.ADVANCED, ExperienceLevel.EXPERT]:
                complex_scenario = PersonaTestScenario(
                    id=f"{persona.id}_complex_query",
                    name=f"{persona.name} - Complex Query",
                    persona_profile=persona,
                    session_context=SessionContext.PREPARATION,
                    query="What are the multiclass spellcasting rules and how do spell slots combine between different caster classes?",
                    expected_appropriateness_score=0.9,
                    expected_detail_level=persona.preferred_detail_level,
                    expected_response_traits=self._get_expected_traits(persona),
                    tags=["complex", "multiclass", "spells"],
                    priority=2,
                    description=f"Complex rules query for {persona.name}"
                )
                scenarios.append(complex_scenario)

        self.scenarios_cache = {s.id: s for s in scenarios}
        return scenarios

    def _get_expected_traits(self, persona: PersonaProfile) -> List[str]:
        """Get expected response traits for a persona."""
        traits = []

        if persona.expects_examples:
            traits.append("has_examples")
        if persona.expects_citations:
            traits.append("cites_sources")
        if persona.preferred_detail_level == "brief":
            traits.append("concise")
        elif persona.preferred_detail_level == "comprehensive":
            traits.append("detailed")
        if persona.technical_comfort >= 8:
            traits.append("technical_language_ok")
        else:
            traits.append("accessible_language")
        if persona.time_pressure:
            traits.append("quick_answer")
        if persona.mobile_context:
            traits.append("mobile_friendly")

        return traits

    def get_test_scenario(self, scenario_id: str) -> Optional[PersonaTestScenario]:
        """Get test scenario by ID."""
        return self.scenarios_cache.get(scenario_id)

    def save_persona(self, persona: PersonaProfile) -> bool:
        """Save persona profile to cache and optionally to disk."""
        try:
            self.profiles_cache[persona.id] = persona
            logger.info(f"Saved persona: {persona.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save persona {persona.id}: {e}")
            return False

    def get_personas_by_tag(self, tag: str) -> List[PersonaProfile]:
        """Get personas by tag."""
        return [p for p in self.profiles_cache.values() if tag in p.tags]