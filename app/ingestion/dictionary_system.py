#!/usr/bin/env python3
"""
TTRPG Dictionary Creation & Maintenance System
==============================================

User Stories:
- Automatic dictionary creation from document context awareness (headings, stat-blocks, etc.)
- Dictionary persistence as snapshot documents in AstraDB and manifest files
- Extensible concept types and cross-system normalization
- Edit capability via Admin UI

This system builds comprehensive dictionaries of TTRPG concepts with rich metadata.
"""

import json
import re
import hashlib
import time
from typing import Dict, List, Any, Optional, Set, Callable
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict

from astrapy import DataAPIClient
import os

@dataclass 
class DictionaryEntry:
    """Structured dictionary entry for TTRPG concepts"""
    concept_id: str
    concept_name: str
    concept_type: str  # spell, feat, monster, heritage, archetype, etc.
    description: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    parent_sections: Optional[List[str]] = None
    
    # Rich metadata fields
    metadata: Optional[Dict[str, Any]] = None
    
    # Cross-references and relationships
    prerequisites: Optional[List[str]] = None
    related_concepts: Optional[List[str]] = None
    
    # Source tracking
    book_id: str = None
    system: str = None
    edition: str = None
    
    # Images and illustrations
    images: Optional[List[Dict[str, str]]] = None
    
    # Processing metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: str = "auto_extraction"
    confidence: float = 1.0

class ConceptRecognizer:
    """Base class for concept recognition patterns"""
    
    def __init__(self, concept_type: str):
        self.concept_type = concept_type
    
    def matches(self, element: Dict[str, Any]) -> bool:
        """Check if element matches this concept type"""
        raise NotImplementedError
    
    def extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Extract concept-specific metadata"""
        return {}

class SpellRecognizer(ConceptRecognizer):
    """Recognizes D&D/Pathfinder spells"""
    
    def __init__(self):
        super().__init__("spell")
        self.spell_patterns = [
            r"School\s+(\w+)(?:\s*\[([^\]]+)\])?\s*;?\s*Level\s+(.+)",
            r"Casting Time\s+(.+)",
            r"Components\s+(.+)",
            r"Range\s+(.+)",
            r"Duration\s+(.+)",
        ]
    
    def matches(self, element: Dict[str, Any]) -> bool:
        text = element.get("text", "").strip()
        if not text:
            return False
            
        # Check for spell signature patterns
        text_lower = text.lower()
        spell_indicators = [
            "school " in text_lower and "level " in text_lower,
            "casting time" in text_lower,
            text_lower.startswith(("acid", "aid", "alarm", "animate", "antimagic", "arcane", 
                                  "bane", "bless", "blur", "burning", "charm", "chill",
                                  "cone", "cure", "darkness", "detect", "dimension", "dispel",
                                  "divine", "dominate", "energy", "enlarge", "entangle", "fear",
                                  "fire", "flame", "fly", "greater", "harm", "heal", "hold",
                                  "ice", "identify", "illusion", "invisibility", "lesser",
                                  "light", "lightning", "magic", "mass", "mind", "plane",
                                  "protection", "ray", "reduce", "resist", "shield", "silence",
                                  "sleep", "slow", "spell", "stone", "summon", "teleport",
                                  "true", "wall", "water", "wind", "zone"))
        ]
        return any(spell_indicators)
    
    def extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        text = element.get("text", "")
        metadata = {}
        
        # Extract school, level, descriptors
        school_match = re.search(r"School\s+(\w+)(?:\s*\[([^\]]+)\])?\s*;?\s*Level\s+(.+)", text, re.I)
        if school_match:
            metadata["school"] = school_match.group(1)
            if school_match.group(2):
                metadata["descriptors"] = [d.strip() for d in school_match.group(2).split(',')]
            metadata["level_text"] = school_match.group(3)
            
            # Extract numeric level
            level_match = re.search(r'\b(\d+)(?:st|nd|rd|th)?\b', metadata["level_text"])
            if level_match:
                metadata["level"] = int(level_match.group(1))
        
        # Extract other fields
        field_patterns = {
            "casting_time": r"Casting Time\s+(.+?)(?:\n|$)",
            "components": r"Components\s+(.+?)(?:\n|$)",
            "range": r"Range\s+(.+?)(?:\n|$)",
            "duration": r"Duration\s+(.+?)(?:\n|$)",
            "saving_throw": r"Saving Throw\s+(.+?)(?:\n|$)",
            "spell_resistance": r"Spell Resistance\s+(.+?)(?:\n|$)",
        }
        
        for field, pattern in field_patterns.items():
            match = re.search(pattern, text, re.I | re.M)
            if match:
                metadata[field] = match.group(1).strip()
        
        return metadata

class FeatRecognizer(ConceptRecognizer):
    """Recognizes D&D/Pathfinder feats"""
    
    def __init__(self):
        super().__init__("feat")
    
    def matches(self, element: Dict[str, Any]) -> bool:
        text = element.get("text", "").strip()
        if not text:
            return False
            
        text_lower = text.lower()
        feat_indicators = [
            "benefit:" in text_lower or "prerequisite" in text_lower,
            "(combat)" in text_lower or "(general)" in text_lower or "(metamagic)" in text_lower,
            text_lower.startswith(("combat ", "improved ", "greater ", "weapon focus",
                                  "weapon specialization", "skill focus", "dodge", "toughness",
                                  "power attack", "cleave", "great cleave", "point blank"))
        ]
        return any(feat_indicators)
    
    def extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        text = element.get("text", "")
        metadata = {}
        
        # Extract feat type from parentheses
        type_match = re.search(r'\(([^)]+)\)', text)
        if type_match:
            metadata["feat_type"] = type_match.group(1)
        
        # Extract prerequisites, benefit, etc.
        field_patterns = {
            "prerequisites": r"Prerequisites?\s*:?\s*(.+?)(?:\n|Benefit|Normal|Special|$)",
            "benefit": r"Benefit\s*:?\s*(.+?)(?:\n|Normal|Special|$)",
            "normal": r"Normal\s*:?\s*(.+?)(?:\n|Special|$)",
            "special": r"Special\s*:?\s*(.+?)(?:\n|$)",
        }
        
        for field, pattern in field_patterns.items():
            match = re.search(pattern, text, re.I | re.M | re.S)
            if match:
                metadata[field] = match.group(1).strip()
        
        return metadata

class MonsterRecognizer(ConceptRecognizer):
    """Recognizes D&D/Pathfinder monsters/creatures"""
    
    def __init__(self):
        super().__init__("monster")
    
    def matches(self, element: Dict[str, Any]) -> bool:
        text = element.get("text", "").strip()
        if not text:
            return False
            
        text_lower = text.lower()
        monster_indicators = [
            "cr " in text_lower or "challenge rating" in text_lower,
            "ac " in text_lower and ("hp" in text_lower or "hit points" in text_lower),
            "str " in text_lower and "dex " in text_lower and "con " in text_lower,
            any(size in text_lower for size in ["tiny", "small", "medium", "large", "huge", "gargantuan"])
        ]
        return any(monster_indicators)
    
    def extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        text = element.get("text", "")
        metadata = {}
        
        # Extract CR
        cr_match = re.search(r'CR\s+([^\s]+)', text, re.I)
        if cr_match:
            metadata["challenge_rating"] = cr_match.group(1)
        
        # Extract basic stats  
        field_patterns = {
            "size": r'\b(Tiny|Small|Medium|Large|Huge|Gargantuan)\b',
            "type": r'\b(aberration|animal|construct|dragon|elemental|fey|fiend|giant|humanoid|monstrosity|ooze|plant|undead)\b',
            "alignment": r'\b(lawful good|neutral good|chaotic good|lawful neutral|true neutral|chaotic neutral|lawful evil|neutral evil|chaotic evil|unaligned)\b',
            "ac": r'AC\s+(\d+)',
            "hp": r'(?:hp|Hit Points)\s+(\d+)',
        }
        
        for field, pattern in field_patterns.items():
            match = re.search(pattern, text, re.I)
            if match:
                metadata[field] = match.group(1)
        
        return metadata

class HeritageRecognizer(ConceptRecognizer):
    """Recognizes PF2e heritages (extensible concept type)"""
    
    def __init__(self):
        super().__init__("heritage")
    
    def matches(self, element: Dict[str, Any]) -> bool:
        text = element.get("text", "").strip()
        text_lower = text.lower()
        return "heritage" in text_lower or text_lower.endswith(" heritage")
    
    def extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        text = element.get("text", "")
        metadata = {}
        
        # Extract ancestry if mentioned
        ancestry_match = re.search(r'(\w+)\s+heritage', text, re.I)
        if ancestry_match:
            metadata["ancestry"] = ancestry_match.group(1)
        
        return metadata

class DictionaryCreationSystem:
    """Main system for automatic dictionary creation"""
    
    def __init__(self, env: str = "dev"):
        self.env = env
        self.recognizers = [
            SpellRecognizer(),
            FeatRecognizer(), 
            MonsterRecognizer(),
            HeritageRecognizer(),
        ]
        
        # Initialize AstraDB client
        self.client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
        endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.database = self.client.get_database_by_api_endpoint(endpoint)
        
    def analyze_elements(self, elements: List[Dict[str, Any]], 
                        book_id: str, system: str = "Pathfinder", edition: str = "1e") -> List[DictionaryEntry]:
        """
        Analyze elements and create dictionary entries
        
        User Story: Derive dictionary entries from document context awareness 
        (headings, stat-blocks, traits, prerequisites) so concepts are identified without manual tagging
        """
        entries = []
        current_section = None
        parent_sections = []
        
        for element in elements:
            # Track section hierarchy
            if element.get("type") in ["Title", "Header"]:
                section_title = element.get("text", "").strip()
                if section_title:
                    # Determine section level based on element metadata
                    depth = element.get("layout", {}).get("category_depth", 0)
                    
                    # Update section hierarchy
                    if depth == 0 or not parent_sections:
                        parent_sections = [section_title]
                    elif depth < len(parent_sections):
                        parent_sections = parent_sections[:depth] + [section_title]
                    else:
                        parent_sections.append(section_title)
                    
                    current_section = section_title
                continue
            
            # Try each recognizer
            for recognizer in self.recognizers:
                if recognizer.matches(element):
                    # Create dictionary entry
                    concept_name = self._extract_concept_name(element, recognizer.concept_type)
                    if not concept_name:
                        continue
                    
                    concept_id = f"{system.lower()}/{edition.lower()}/{recognizer.concept_type}/{concept_name.lower().replace(' ', '_')}"
                    
                    # Extract rich metadata
                    rich_metadata = recognizer.extract_metadata(element)
                    
                    # Handle images linked to this concept
                    images = []
                    if element.get("image"):
                        images.append({
                            "path": element["image"]["path"],
                            "caption": element["image"]["caption"],
                            "type": "illustration"
                        })
                    
                    entry = DictionaryEntry(
                        concept_id=concept_id,
                        concept_name=concept_name,
                        concept_type=recognizer.concept_type,
                        description=element.get("text", "")[:500] + "..." if len(element.get("text", "")) > 500 else element.get("text", ""),
                        page_number=element.get("page_number"),
                        section_title=current_section,
                        parent_sections=parent_sections.copy() if parent_sections else None,
                        metadata=rich_metadata,
                        book_id=book_id,
                        system=system,
                        edition=edition,
                        images=images if images else None,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        source="unstructured_auto",
                        confidence=self._calculate_confidence(element, recognizer)
                    )
                    
                    entries.append(entry)
                    break  # Only match first recognizer
        
        return entries
    
    def _extract_concept_name(self, element: Dict[str, Any], concept_type: str) -> Optional[str]:
        """Extract the primary name/title of a concept"""
        text = element.get("text", "").strip()
        if not text:
            return None
        
        # Extract name from first line, removing common prefixes
        first_line = text.split('\n')[0].strip()
        
        # Clean up the name
        name = re.sub(r'\([^)]*\)', '', first_line)  # Remove parentheticals
        name = re.sub(r'\s+', ' ', name).strip()     # Normalize whitespace
        
        # For spells, take everything before spell-specific keywords
        if concept_type == "spell":
            spell_keywords = ["School", "Level", "Casting Time", "Components"]
            for keyword in spell_keywords:
                if keyword in name:
                    name = name.split(keyword)[0].strip()
                    break
        
        # For feats, clean up common patterns
        if concept_type == "feat":
            name = re.sub(r'\s*\((?:Combat|General|Metamagic|Item Creation)\)\s*', '', name)
        
        return name if len(name) > 2 else None
    
    def _calculate_confidence(self, element: Dict[str, Any], recognizer: ConceptRecognizer) -> float:
        """Calculate confidence score for concept recognition"""
        text = element.get("text", "").strip()
        
        # Base confidence
        confidence = 0.8
        
        # Boost for strong patterns
        if recognizer.concept_type == "spell":
            if "School" in text and "Level" in text:
                confidence = 0.95
            elif "Casting Time" in text:
                confidence = 0.9
        elif recognizer.concept_type == "feat":
            if "Benefit:" in text and "Prerequisites" in text:
                confidence = 0.95
            elif "(Combat)" in text or "(General)" in text:
                confidence = 0.9
        elif recognizer.concept_type == "monster":
            if "CR " in text and ("AC" in text or "hp" in text):
                confidence = 0.95
        
        # Reduce for very short text
        if len(text) < 50:
            confidence *= 0.8
        
        return min(confidence, 1.0)
    
    def save_dictionary_snapshot(self, entries: List[DictionaryEntry], job_id: str, 
                                collection_name: str = "ttrpg_dictionary_snapshots") -> Dict[str, Any]:
        """
        User Story: Persist dictionary as snapshot document in AstraDB for fast single-read retrieval
        """
        # Create snapshot document
        snapshot = {
            "_id": job_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "env": self.env,
            "collection_name": collection_name,
            "statistics": {
                "total_entries": len(entries),
                "concept_types": dict(Counter(entry.concept_type for entry in entries)),
                "systems": dict(Counter(entry.system for entry in entries)),
                "books": dict(Counter(entry.book_id for entry in entries))
            },
            "entries": [asdict(entry) for entry in entries]
        }
        
        # Store in AstraDB
        dict_collection = self.database.get_collection("ttrpg_dictionary_snapshots")
        dict_collection.insert_one(snapshot)
        
        # Also save to artifacts manifest
        manifest_dir = Path(f"artifacts/ingest/{self.env}/{job_id}")
        manifest_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_path = manifest_dir / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        return {
            "snapshot_id": job_id,
            "total_entries": len(entries),
            "astradb_collection": "ttrpg_dictionary_snapshots",
            "manifest_path": str(manifest_path),
            "statistics": snapshot["statistics"]
        }
    
    def get_dictionary_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve dictionary snapshot for Admin UI display"""
        try:
            dict_collection = self.database.get_collection("ttrpg_dictionary_snapshots")
            docs = list(dict_collection.find({"_id": snapshot_id}, limit=1))
            return docs[0] if docs else None
        except Exception:
            return None
    
    def update_dictionary_entry(self, entry_id: str, updates: Dict[str, Any], 
                               user_id: str = "admin") -> bool:
        """
        User Story: Edit dictionary terms via Admin UI for cross-system normalization
        """
        try:
            # Find the snapshot containing this entry
            dict_collection = self.database.get_collection("ttrpg_dictionary_snapshots")
            
            # This is a simplified implementation - in practice you'd want more sophisticated updates
            update_result = dict_collection.update_many(
                {"entries.concept_id": entry_id},
                {
                    "$set": {
                        "entries.$.updated_at": datetime.now(timezone.utc).isoformat(),
                        "entries.$.updated_by": user_id,
                        **{f"entries.$.{k}": v for k, v in updates.items()}
                    }
                }
            )
            
            return update_result.modified_count > 0
        except Exception as e:
            print(f"Failed to update dictionary entry {entry_id}: {e}")
            return False

def create_dictionary_from_elements(elements: List[Dict[str, Any]], book_id: str, 
                                   job_id: str, system: str = "Pathfinder", edition: str = "1e",
                                   env: str = "dev", progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Main function to create dictionary from parsed elements
    
    User Story: Dictionary automatically created in Pass B so no manual code generation needed
    """
    try:
        if progress_callback:
            progress_callback("dictionary", "Creating dictionary from document context", 10)
        
        # Initialize dictionary system
        dict_system = DictionaryCreationSystem(env)
        
        if progress_callback:
            progress_callback("dictionary", "Analyzing elements for concept recognition", 30)
        
        # Analyze elements and create entries
        entries = dict_system.analyze_elements(elements, book_id, system, edition)
        
        if progress_callback:
            progress_callback("dictionary", f"Identified {len(entries)} dictionary entries", 60)
        
        # Save snapshot
        snapshot_result = dict_system.save_dictionary_snapshot(entries, job_id)
        
        if progress_callback:
            progress_callback("dictionary", "Dictionary snapshot saved to AstraDB", 100, snapshot_result)
        
        return {
            "success": True,
            "entries_created": len(entries),
            "snapshot_result": snapshot_result,
            "entries": entries
        }
        
    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        if progress_callback:
            progress_callback("dictionary", f"Dictionary creation failed: {str(e)}", 0, error_result)
        return error_result

if __name__ == "__main__":
    # Example usage for testing
    sample_elements = [
        {
            "type": "Title",
            "text": "Spells",
            "page_number": 200
        },
        {
            "type": "NarrativeText", 
            "text": "Fireball\nSchool evocation [fire]; Level sorcerer/wizard 3\nCasting Time 1 standard action\nComponents V, S, M (a tiny ball of bat guano and sulfur)\nRange long (400 ft. + 40 ft./level)\nArea 20-ft.-radius spread\nDuration instantaneous\nSaving Throw Reflex half; Spell Resistance yes\n\nA fireball spell generates a searing explosion of flame that detonates with a low roar and deals 1d6 points of fire damage per caster level (maximum 10d6) to every creature within the area.",
            "page_number": 283
        }
    ]
    
    result = create_dictionary_from_elements(
        elements=sample_elements,
        book_id="pathfinder-core-1e", 
        job_id="test-dict-123",
        progress_callback=lambda phase, msg, prog, details=None: print(f"[{prog}%] {phase}: {msg}")
    )
    
    print(f"Dictionary creation result: {result}")