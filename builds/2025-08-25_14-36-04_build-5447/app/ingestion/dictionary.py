import json
import logging
from typing import Dict, List, Set, Any, Optional
from pathlib import Path
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

class TRPGDictionary:
    """Dynamic dictionary system for cross-system TTRPG normalization"""
    
    def __init__(self, dict_path: Optional[str] = None):
        self.dict_path = dict_path or "runtime/dictionary.json"
        self.terms = {}
        self.aliases = {}
        self.categories = {}
        self.load_dictionary()
    
    def load_dictionary(self):
        """Load dictionary from file or create default"""
        dict_file = Path(self.dict_path)
        
        if dict_file.exists():
            try:
                with open(dict_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.terms = data.get("terms", {})
                    self.aliases = data.get("aliases", {})
                    self.categories = data.get("categories", {})
                logger.info(f"Loaded dictionary with {len(self.terms)} terms")
            except Exception as e:
                logger.error(f"Failed to load dictionary: {e}")
                self._create_default_dictionary()
        else:
            self._create_default_dictionary()
    
    def save_dictionary(self):
        """Save dictionary to file"""
        try:
            dict_file = Path(self.dict_path)
            dict_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "terms": self.terms,
                "aliases": self.aliases,
                "categories": self.categories,
                "version": "1.0",
                "last_updated": "2025-08-25"
            }
            
            with open(dict_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved dictionary with {len(self.terms)} terms")
        except Exception as e:
            logger.error(f"Failed to save dictionary: {e}")
    
    def _create_default_dictionary(self):
        """Create default dictionary with common TTRPG terms"""
        # Core game concepts
        self.terms = {
            "ability_score": {
                "canonical": "Ability Score",
                "description": "Core character attributes (STR, DEX, CON, etc.)",
                "systems": ["D&D", "Pathfinder", "Generic"],
                "category": "character_mechanics"
            },
            "armor_class": {
                "canonical": "Armor Class", 
                "description": "Defensive rating against attacks",
                "systems": ["D&D", "Pathfinder"],
                "category": "combat"
            },
            "hit_points": {
                "canonical": "Hit Points",
                "description": "Character health/damage capacity",
                "systems": ["D&D", "Pathfinder", "Generic"],
                "category": "character_mechanics"
            },
            "saving_throw": {
                "canonical": "Saving Throw",
                "description": "Dice roll to resist effects",
                "systems": ["D&D", "Pathfinder"],
                "category": "mechanics"
            },
            "skill_check": {
                "canonical": "Skill Check",
                "description": "Dice roll using character skills",
                "systems": ["D&D", "Pathfinder", "Generic"],
                "category": "mechanics"
            }
        }
        
        # Aliases for cross-system mapping
        self.aliases = {
            "AC": "armor_class",
            "HP": "hit_points",
            "health": "hit_points",
            "defense": "armor_class",
            "stat": "ability_score",
            "attribute": "ability_score",
            "save": "saving_throw"
        }
        
        # Categories for organization
        self.categories = {
            "character_mechanics": "Core character rules and attributes",
            "combat": "Combat rules and mechanics", 
            "mechanics": "General game mechanics",
            "equipment": "Weapons, armor, and gear",
            "spells": "Magic and spell systems",
            "feats": "Special abilities and talents"
        }
        
        self.save_dictionary()
    
    def normalize_term(self, text: str) -> str:
        """Normalize a term using the dictionary"""
        # Clean input
        clean_text = text.lower().strip()
        
        # Direct term lookup
        if clean_text in self.terms:
            return self.terms[clean_text]["canonical"]
        
        # Alias lookup
        if clean_text in self.aliases:
            term_key = self.aliases[clean_text]
            if term_key in self.terms:
                return self.terms[term_key]["canonical"]
        
        # Fuzzy matching for common patterns
        normalized = self._fuzzy_normalize(clean_text)
        if normalized:
            return normalized
        
        # Return original if no match
        return text
    
    def _fuzzy_normalize(self, term: str) -> Optional[str]:
        """Fuzzy matching for term normalization"""
        # Common patterns
        patterns = [
            (r'(\w+)\s+points?', r'\1_points'),  # "hit points" -> "hit_points"
            (r'(\w+)\s+class', r'\1_class'),     # "armor class" -> "armor_class"
            (r'(\w+)\s+throw', r'\1_throw'),     # "saving throw" -> "saving_throw"
            (r'(\w+)\s+check', r'\1_check'),     # "skill check" -> "skill_check"
        ]
        
        for pattern, replacement in patterns:
            if re.match(pattern, term):
                normalized = re.sub(pattern, replacement, term)
                if normalized in self.terms:
                    return self.terms[normalized]["canonical"]
        
        return None
    
    def add_term(self, 
                 key: str, 
                 canonical: str, 
                 description: str = "",
                 systems: List[str] = None,
                 category: str = "general") -> bool:
        """Add new term to dictionary"""
        try:
            self.terms[key.lower()] = {
                "canonical": canonical,
                "description": description,
                "systems": systems or ["Generic"],
                "category": category
            }
            self.save_dictionary()
            logger.info(f"Added term: {key} -> {canonical}")
            return True
        except Exception as e:
            logger.error(f"Failed to add term {key}: {e}")
            return False
    
    def add_alias(self, alias: str, term_key: str) -> bool:
        """Add alias for existing term"""
        try:
            if term_key.lower() not in self.terms:
                logger.error(f"Cannot add alias '{alias}': term '{term_key}' not found")
                return False
            
            self.aliases[alias.lower()] = term_key.lower()
            self.save_dictionary()
            logger.info(f"Added alias: {alias} -> {term_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to add alias {alias}: {e}")
            return False
    
    def enrich_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich chunks with normalized terminology"""
        enriched = []
        
        for chunk in chunks:
            enriched_chunk = chunk.copy()
            
            # Find and normalize terms in chunk text
            normalized_terms = self._extract_normalized_terms(chunk["text"])
            
            # Add to metadata
            enriched_chunk["metadata"]["normalized_terms"] = normalized_terms
            enriched_chunk["metadata"]["term_count"] = len(normalized_terms)
            
            # Add category tags
            categories = set()
            for term in normalized_terms:
                term_key = self._find_term_key(term)
                if term_key and term_key in self.terms:
                    categories.add(self.terms[term_key]["category"])
            
            enriched_chunk["metadata"]["categories"] = list(categories)
            
            enriched.append(enriched_chunk)
        
        return enriched
    
    def _extract_normalized_terms(self, text: str) -> List[str]:
        """Extract and normalize terms from text"""
        words = re.findall(r'\b\w+(?:\s+\w+)*\b', text.lower())
        normalized = []
        
        for word in words:
            norm_term = self.normalize_term(word)
            if norm_term != word:  # Only include if normalized
                normalized.append(norm_term)
        
        return list(set(normalized))  # Remove duplicates
    
    def _find_term_key(self, canonical_term: str) -> Optional[str]:
        """Find term key from canonical form"""
        for key, data in self.terms.items():
            if data["canonical"] == canonical_term:
                return key
        return None
    
    def get_term_info(self, term: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a term"""
        key = term.lower()
        
        if key in self.terms:
            return self.terms[key]
        
        if key in self.aliases:
            term_key = self.aliases[key]
            if term_key in self.terms:
                return self.terms[term_key]
        
        return None
    
    def search_terms(self, query: str) -> List[Dict[str, Any]]:
        """Search terms by partial match"""
        query = query.lower()
        results = []
        
        for key, data in self.terms.items():
            if (query in key or 
                query in data["canonical"].lower() or 
                query in data.get("description", "").lower()):
                results.append({
                    "key": key,
                    **data
                })
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dictionary statistics"""
        category_counts = defaultdict(int)
        system_counts = defaultdict(int)
        
        for data in self.terms.values():
            category_counts[data["category"]] += 1
            for system in data["systems"]:
                system_counts[system] += 1
        
        return {
            "total_terms": len(self.terms),
            "total_aliases": len(self.aliases),
            "categories": dict(category_counts),
            "systems": dict(system_counts)
        }

# Global instance
_dictionary = None

def get_dictionary() -> TRPGDictionary:
    """Get global dictionary instance"""
    global _dictionary
    if _dictionary is None:
        _dictionary = TRPGDictionary()
    return _dictionary