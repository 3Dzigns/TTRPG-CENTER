# src_common/pass_b_enricher.py
"""
Pass B - Content enrichment using Haystack
Implements the second pass of the Phase 1 ingestion pipeline.
"""

import json
import os
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict

# Haystack imports
from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.in_memory import InMemoryDocumentStore

from ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class EntityExtraction:
    """Extracted entity information"""
    term: str
    entity_type: str
    confidence: float
    context: str


@dataclass
class EnrichedChunk:
    """Enriched version of a document chunk"""
    chunk_id: str
    original_content: str
    enhanced_content: str
    entities: List[str]
    categories: List[str]
    complexity: str
    confidence: float


@dataclass
class DictionaryUpdate:
    """Dictionary entry update"""
    term: str
    definition: str
    category: str
    source_chunk: str


@dataclass
class PassBOutput:
    """Contract-compliant output for Pass B"""
    job_id: str
    phase: str
    tool: str
    input_file: str
    enriched_chunks: List[Dict[str, Any]]
    dictionary_updates: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    processing_metadata: Dict[str, Any]


class PassBEnricher:
    """Content enricher using Haystack for Pass B of the ingestion pipeline"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.tool_name = "haystack"
        self.document_store = InMemoryDocumentStore()
        
        # TTRPG-specific terminology patterns
        self.ttrpg_patterns = {
            'dice': r'\b(d4|d6|d8|d10|d12|d20|d100)\b',
            'stats': r'\b(strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)\b',
            'mechanics': r'\b(initiative|armor class|hit points|spell slot|saving throw|proficiency|ac|hp)\b',
            'classes': r'\b(fighter|wizard|cleric|rogue|ranger|barbarian|bard|druid|monk|paladin|sorcerer|warlock)\b',
            'races': r'\b(human|elf|dwarf|halfling|dragonborn|gnome|half-elf|half-orc|tiefling)\b',
            'spells': r'\b(magic missile|fireball|heal|shield|counterspell|dispel magic)\b'
        }
    
    def enrich_chunks(self, pass_a_output_path: Path, output_dir: Path) -> PassBOutput:
        """
        Enrich chunks from Pass A output.
        
        Args:
            pass_a_output_path: Path to Pass A JSON output file
            output_dir: Directory to write output files
            
        Returns:
            PassBOutput with enriched chunks and dictionary updates
        """
        logger.info(f"Starting Pass B enrichment for {pass_a_output_path}", extra={
            'job_id': self.job_id,
            'phase': 'pass_b',
            'input_file': str(pass_a_output_path),
            'component': 'pass_b_enricher'
        })
        
        start_time = time.time()
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Load Pass A output
            with open(pass_a_output_path, 'r', encoding='utf-8') as f:
                pass_a_data = json.load(f)
            
            logger.debug(f"Loaded {len(pass_a_data['chunks'])} chunks from Pass A")
            
            # Convert to Haystack documents
            documents = self._create_haystack_documents(pass_a_data['chunks'])
            
            # Enrich each chunk
            enriched_chunks = []
            dictionary_updates = []
            
            for i, doc in enumerate(documents):
                logger.debug(f"Enriching chunk {i+1}/{len(documents)}")
                
                # Enrich the content
                enriched_chunk = self._enrich_single_chunk(doc, pass_a_data['chunks'][i])
                enriched_chunks.append(asdict(enriched_chunk))
                
                # Extract dictionary updates  
                dict_updates = self._extract_dictionary_updates(enriched_chunk)
                dictionary_updates.extend([asdict(update) for update in dict_updates])
            
            logger.info(f"Enriched {len(enriched_chunks)} chunks, extracted {len(dictionary_updates)} dictionary entries")
            
            # Calculate processing statistics
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            statistics = {
                "chunks_processed": len(enriched_chunks),
                "dictionary_entries_added": len(dictionary_updates),
                "average_entities_per_chunk": sum(len(chunk['entities']) for chunk in enriched_chunks) / len(enriched_chunks) if enriched_chunks else 0,
                "processing_time_ms": processing_time_ms,
                "enhancement_ratio": sum(len(chunk['enhanced_content']) / len(chunk['original_content']) for chunk in enriched_chunks) / len(enriched_chunks) if enriched_chunks else 1.0
            }
            
            processing_metadata = {
                "tool": self.tool_name,
                "version": self._get_haystack_version(),
                "pipeline_components": ["entity_extraction", "content_enhancement", "dictionary_extraction"],
                "ttrpg_patterns_applied": list(self.ttrpg_patterns.keys()),
                "timestamp": time.time()
            }
            
            # Create output object
            output = PassBOutput(
                job_id=self.job_id,
                phase="pass_b",
                tool=self.tool_name,
                input_file=str(pass_a_output_path),
                enriched_chunks=enriched_chunks,
                dictionary_updates=dictionary_updates,
                statistics=statistics,
                processing_metadata=processing_metadata
            )
            
            # Write enriched chunks output
            enriched_file = output_dir / f"{self.job_id}_pass_b_enriched.json"
            with open(enriched_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(output), f, indent=2, ensure_ascii=False)
            
            # Write dictionary updates separately for easier consumption
            dict_file = output_dir / f"{self.job_id}_pass_b_dictionary_delta.json"
            with open(dict_file, 'w', encoding='utf-8') as f:
                json.dump({"updates": dictionary_updates}, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Pass B completed successfully", extra={
                'job_id': self.job_id,
                'phase': 'pass_b',
                'chunks_enriched': len(enriched_chunks),
                'dictionary_entries': len(dictionary_updates),
                'processing_time_ms': processing_time_ms,
                'enriched_file': str(enriched_file),
                'dictionary_file': str(dict_file),
                'component': 'pass_b_enricher'
            })
            
            return output
            
        except Exception as e:
            logger.error(f"Pass B enrichment failed: {str(e)}", extra={
                'job_id': self.job_id,
                'phase': 'pass_b',
                'error': str(e),
                'input_file': str(pass_a_output_path),
                'component': 'pass_b_enricher'
            })
            raise
    
    def _create_haystack_documents(self, chunks: List[Dict[str, Any]]) -> List[Document]:
        """Convert Pass A chunks to Haystack documents"""
        documents = []
        
        for chunk in chunks:
            doc = Document(
                content=chunk['content'],
                meta={
                    'chunk_id': chunk['id'],
                    'page': chunk['metadata']['page'],
                    'section': chunk['metadata']['section'],
                    'chunk_type': chunk['metadata']['chunk_type'],
                    'element_id': chunk['metadata']['element_id']
                }
            )
            documents.append(doc)
        
        return documents
    
    def _enrich_single_chunk(self, document: Document, original_chunk: Dict[str, Any]) -> EnrichedChunk:
        """Enrich a single chunk with entities, categories, and enhanced content"""
        content = document.content
        
        # Extract entities using pattern matching
        entities = self._extract_entities(content)
        
        # Categorize content
        categories = self._categorize_content(content)
        
        # Assess complexity
        complexity = self._assess_complexity(content, entities)
        
        # Enhance content with additional context
        enhanced_content = self._enhance_content(content, entities, categories)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(content, entities, categories)
        
        return EnrichedChunk(
            chunk_id=original_chunk['id'],
            original_content=content,
            enhanced_content=enhanced_content,
            entities=entities,
            categories=categories,
            complexity=complexity,
            confidence=confidence
        )
    
    def _extract_entities(self, content: str) -> List[str]:
        """Extract TTRPG-specific entities from content"""
        entities = set()
        content_lower = content.lower()
        
        # Apply pattern matching
        for category, pattern in self.ttrpg_patterns.items():
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            for match in matches:
                entities.add(match.lower())
        
        # Extract numeric patterns (dice rolls, modifiers, etc.)
        numeric_patterns = [
            r'\+\d+',  # Bonuses like +2, +5
            r'\d+d\d+',  # Dice notation like 3d6, 1d20
            r'AC \d+',  # Armor Class
            r'\d+ hit points?',  # Hit points
            r'level \d+',  # Spell/character levels
        ]
        
        for pattern in numeric_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            entities.update(matches)
        
        # Extract capitalized terms that might be proper nouns (spells, abilities, etc.)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', content)
        entities.update([noun.lower() for noun in proper_nouns])
        
        return sorted(list(entities))
    
    def _categorize_content(self, content: str) -> List[str]:
        """Categorize content into TTRPG domains"""
        categories = set()
        content_lower = content.lower()
        
        # Define category keywords
        category_keywords = {
            'character-creation': ['character', 'race', 'class', 'ability score', 'background', 'feat'],
            'combat': ['combat', 'attack', 'damage', 'initiative', 'armor class', 'hit points', 'weapon'],
            'spells': ['spell', 'magic', 'cast', 'concentration', 'spell slot', 'verbal', 'somatic'],
            'mechanics': ['roll', 'dice', 'check', 'saving throw', 'proficiency', 'modifier'],
            'equipment': ['weapon', 'armor', 'shield', 'item', 'equipment', 'gear'],
            'exploration': ['adventure', 'dungeon', 'encounter', 'travel', 'rest'],
            'social': ['charisma', 'persuasion', 'deception', 'intimidation', 'npc']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                categories.add(category)
        
        # Default category if none found
        if not categories:
            categories.add('general')
        
        return sorted(list(categories))
    
    def _assess_complexity(self, content: str, entities: List[str]) -> str:
        """Assess the complexity level of the content"""
        # Simple heuristics for complexity assessment
        word_count = len(content.split())
        entity_count = len(entities)
        
        # Look for complexity indicators
        complex_indicators = ['advanced', 'complex', 'difficult', 'optional', 'variant']
        intermediate_indicators = ['moderate', 'standard', 'typical', 'normal']
        basic_indicators = ['simple', 'basic', 'easy', 'beginner', 'introduction']
        
        content_lower = content.lower()
        
        if any(indicator in content_lower for indicator in complex_indicators):
            return 'advanced'
        elif any(indicator in content_lower for indicator in basic_indicators):
            return 'basic'
        elif word_count > 200 or entity_count > 8:
            return 'advanced'
        elif word_count < 100 and entity_count < 4:
            return 'basic'
        else:
            return 'intermediate'
    
    def _enhance_content(self, content: str, entities: List[str], categories: List[str]) -> str:
        """Enhance content with additional context and normalization"""
        enhanced = content
        
        # Add category context at the beginning
        if categories:
            category_text = f"Content categories: {', '.join(categories)}. "
            enhanced = category_text + enhanced
        
        # Expand common abbreviations
        abbreviations = {
            r'\bAC\b': 'Armor Class (AC)',
            r'\bHP\b': 'Hit Points (HP)',
            r'\bDC\b': 'Difficulty Class (DC)',
            r'\bPC\b': 'Player Character (PC)',
            r'\bNPC\b': 'Non-Player Character (NPC)',
            r'\bDM\b': 'Dungeon Master (DM)',
            r'\bSTR\b': 'Strength (STR)',
            r'\bDEX\b': 'Dexterity (DEX)',
            r'\bCON\b': 'Constitution (CON)',
            r'\bINT\b': 'Intelligence (INT)',
            r'\bWIS\b': 'Wisdom (WIS)',
            r'\bCHA\b': 'Charisma (CHA)'
        }
        
        for abbrev, expansion in abbreviations.items():
            enhanced = re.sub(abbrev, expansion, enhanced, flags=re.IGNORECASE)
        
        return enhanced
    
    def _calculate_confidence(self, content: str, entities: List[str], categories: List[str]) -> float:
        """Calculate confidence score for the enrichment"""
        # Base confidence on entity detection and categorization success
        base_confidence = 0.7
        
        # Boost confidence based on entity count
        entity_boost = min(len(entities) * 0.05, 0.2)
        
        # Boost confidence based on category specificity
        category_boost = min(len(categories) * 0.03, 0.1)
        
        # Reduce confidence for very short content
        if len(content.split()) < 20:
            length_penalty = 0.1
        else:
            length_penalty = 0.0
        
        confidence = base_confidence + entity_boost + category_boost - length_penalty
        return min(max(confidence, 0.1), 1.0)  # Clamp between 0.1 and 1.0
    
    def _extract_dictionary_updates(self, enriched_chunk: EnrichedChunk) -> List[DictionaryUpdate]:
        """Extract dictionary updates from enriched chunk"""
        updates = []
        content = enriched_chunk.enhanced_content
        
        # Extract definitions from content patterns
        definition_patterns = [
            r'([A-Z][a-z\s]+):\s+([^.]+\.)',  # "Term: definition."
            r'([A-Z][a-z\s]+)\s+are\s+([^.]+\.)',  # "Terms are definition."
            r'([A-Z][a-z\s]+)\s+is\s+([^.]+\.)',  # "Term is definition."
        ]
        
        for pattern in definition_patterns:
            matches = re.findall(pattern, content)
            for term, definition in matches:
                term = term.strip()
                definition = definition.strip()
                
                # Skip very short terms or definitions
                if len(term) < 3 or len(definition) < 10:
                    continue
                
                # Determine category based on content
                category = self._determine_term_category(term, definition, enriched_chunk.categories)
                
                updates.append(DictionaryUpdate(
                    term=term,
                    definition=definition,
                    category=category,
                    source_chunk=enriched_chunk.chunk_id
                ))
        
        # Add entity-based updates for important terms
        for entity in enriched_chunk.entities:
            if len(entity) > 3 and entity not in [update.term.lower() for update in updates]:
                definition = self._generate_entity_definition(entity, content)
                if definition:
                    category = self._determine_term_category(entity, definition, enriched_chunk.categories)
                    updates.append(DictionaryUpdate(
                        term=entity.title(),
                        definition=definition,
                        category=category,
                        source_chunk=enriched_chunk.chunk_id
                    ))
        
        return updates[:10]  # Limit to top 10 updates per chunk
    
    def _determine_term_category(self, term: str, definition: str, content_categories: List[str]) -> str:
        """Determine the category for a dictionary term"""
        term_lower = term.lower()
        def_lower = definition.lower()
        
        # Check for specific term types
        if any(dice_word in term_lower for dice_word in ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'dice']):
            return 'mechanics'
        elif any(stat in term_lower for stat in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']):
            return 'character-stats'
        elif any(spell_word in def_lower for spell_word in ['spell', 'magic', 'cast']):
            return 'spells'
        elif any(combat_word in def_lower for combat_word in ['attack', 'damage', 'combat', 'weapon']):
            return 'combat'
        elif content_categories:
            return content_categories[0]  # Use first content category
        else:
            return 'general'
    
    def _generate_entity_definition(self, entity: str, content: str) -> Optional[str]:
        """Generate a simple definition for an entity based on context"""
        # Look for contextual information around the entity
        entity_pattern = rf'\b{re.escape(entity)}\b.{{0,100}}'
        matches = re.findall(entity_pattern, content, re.IGNORECASE | re.DOTALL)
        
        if matches:
            context = matches[0].strip()
            # Try to extract a meaningful definition from the context
            if len(context) > 20:
                return f"Gaming term referenced in context: {context[:100]}..."
        
        return None
    
    def _get_haystack_version(self) -> str:
        """Get version of Haystack library"""
        try:
            import haystack
            return getattr(haystack, '__version__', 'unknown')
        except:
            return 'unknown'


async def run_pass_b(job_id: str, pass_a_output_path: Path, output_dir: Path) -> PassBOutput:
    """
    Async wrapper for Pass B enrichment.
    
    Args:
        job_id: Unique job identifier
        pass_a_output_path: Path to Pass A JSON output
        output_dir: Directory for output files
        
    Returns:
        PassBOutput with enrichment results
    """
    enricher = PassBEnricher(job_id)
    return enricher.enrich_chunks(pass_a_output_path, output_dir)


def run_pass_b_sync(job_id: str, pass_a_output_path: Path, output_dir: Path) -> PassBOutput:
    """
    Synchronous version for testing and simple use cases.
    
    Args:
        job_id: Unique job identifier
        pass_a_output_path: Path to Pass A JSON output
        output_dir: Directory for output files
        
    Returns:
        PassBOutput with enrichment results
    """
    enricher = PassBEnricher(job_id)
    return enricher.enrich_chunks(pass_a_output_path, output_dir)


if __name__ == "__main__":
    # Test with our Pass A output
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        pass_a_file = Path(sys.argv[1])
    else:
        pass_a_file = Path("artifacts/test/test_job_pass_a_chunks.json")
    
    if not pass_a_file.exists():
        print(f"Pass A output file not found: {pass_a_file}")
        sys.exit(1)
    
    output_dir = Path("artifacts/test")
    
    try:
        result = run_pass_b_sync("test_job", pass_a_file, output_dir)
        print(f"Pass B completed successfully!")
        print(f"Chunks enriched: {result.statistics['chunks_processed']}")
        print(f"Dictionary entries: {result.statistics['dictionary_entries_added']}")
        print(f"Processing time: {result.statistics['processing_time_ms']}ms")
        print(f"Enhancement ratio: {result.statistics['enhancement_ratio']:.2f}")
        print(f"Output written to: {output_dir}")
        
    except Exception as e:
        print(f"Pass B failed: {e}")
        sys.exit(1)