#!/usr/bin/env python3
"""
Concept-Aware TTRPG Chunker
===========================

Battle-tested approach for chunking TTRPG content where each chunk = one concept:
- One spell per chunk
- One feat per chunk  
- One monster per chunk
- Rich metadata extraction without LLM calls

Based on production-proven patterns for maximum speed and minimal token usage.
"""
import re
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

class TTRPGConcept:
    """Lightweight concept for TTRPG content"""
    
    def __init__(self, concept_id: str, content: str, concept_type: str, 
                 concept_name: str, metadata: Dict[str, Any] = None):
        self.concept_id = concept_id
        self.content = content
        self.concept_type = concept_type
        self.concept_name = concept_name
        self.metadata = metadata or {}
        self.char_count = len(content)
        self.token_estimate = max(1, len(content) // 4)
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.content_sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "concept_id": self.concept_id,
            "content": self.content,
            "concept_type": self.concept_type,
            "concept_name": self.concept_name,
            "char_count": self.char_count,
            "token_estimate": self.token_estimate,
            "created_at": self.created_at,
            "content_sha256": self.content_sha256,
            "metadata": self.metadata
        }

class ConceptChunker:
    """Fast concept-aware chunker for TTRPG content"""
    
    def __init__(self, system: str = "Pathfinder", edition: str = "1e", book: str = "Core Rulebook"):
        self.system = system
        self.edition = edition  
        self.book = book
        self.max_chunk_size = 7500  # Under 8000 byte AstraDB limit
        
        # Concept patterns - tuned for Pathfinder format
        self.spell_header_pattern = re.compile(
            r"\n(?=[A-Z][A-Za-z0-9' \-]+\n(?:School|Level|Traits|Traditions|Cast))", 
            re.MULTILINE
        )
        
        self.feat_header_pattern = re.compile(
            r"\n(?=[A-Z][A-Za-z0-9' \-]+\s*(?:\([^)]+\))?\s*\n(?:Prerequisites|Benefit|Normal|Special))", 
            re.MULTILINE
        )
        
        self.monster_header_pattern = re.compile(
            r"\n(?=[A-Z][A-Za-z0-9' \-]+\s+CR\s+\d+)", 
            re.MULTILINE
        )
    
    def split_oversized_chunk(self, content: str, concept_name: str, concept_type: str, base_metadata: Dict[str, Any]) -> List[TTRPGConcept]:
        """Split chunks that exceed AstraDB size limits"""
        if len(content.encode('utf-8')) <= self.max_chunk_size:
            # Single chunk fits
            concept_id = self.slugify(self.system, self.edition, concept_type, concept_name)
            return [TTRPGConcept(concept_id, content, concept_type, concept_name, base_metadata)]
        
        # Need to split the chunk
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        part_num = 1
        
        # Keep the header in the first chunk
        if lines:
            header = lines[0]
            current_chunk.append(header)
            current_size = len(header.encode('utf-8'))
            lines = lines[1:]
        
        for line in lines:
            line_size = len((line + '\n').encode('utf-8'))
            
            if current_size + line_size > self.max_chunk_size and current_chunk:
                # Create chunk from accumulated lines
                chunk_content = '\n'.join(current_chunk)
                concept_id = self.slugify(self.system, self.edition, concept_type, f"{concept_name}-part-{part_num}")
                
                # Add part info to metadata
                chunk_metadata = {**base_metadata, "part_number": part_num, "is_split_chunk": True}
                
                chunks.append(TTRPGConcept(concept_id, chunk_content, concept_type, concept_name, chunk_metadata))
                
                # Start new chunk with header if this isn't the first part
                current_chunk = [f"{concept_name} (continued)"] if part_num > 1 else []
                current_size = len(f"{concept_name} (continued)\n".encode('utf-8')) if part_num > 1 else 0
                part_num += 1
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            concept_id = self.slugify(self.system, self.edition, concept_type, f"{concept_name}-part-{part_num}")
            chunk_metadata = {**base_metadata, "part_number": part_num, "is_split_chunk": True}
            chunks.append(TTRPGConcept(concept_id, chunk_content, concept_type, concept_name, chunk_metadata))
        
        return chunks
    
    def canonicalize_name(self, block: str) -> str:
        """Extract canonical name from first line of block"""
        first_line = block.strip().split('\n')[0].strip()
        # Clean up common artifacts
        first_line = re.sub(r'\s+', ' ', first_line)
        return first_line
    
    def slugify(self, *parts) -> str:
        """Create stable concept ID slug"""
        base = "/".join(str(p).strip().lower().replace(" ", "-") for p in parts if p)
        return re.sub(r"[^a-z0-9/_-]", "", base)
    
    def extract_field(self, block: str, field: str) -> Optional[str]:
        """Extract field value using regex"""
        pattern = rf"{re.escape(field)}\s*:?\s*(.+?)(?:\n|$)"
        match = re.search(pattern, block, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None
    
    def parse_spell_fields(self, block: str) -> Dict[str, Any]:
        """Extract spell-specific metadata fields"""
        fields = {}
        
        # School and level
        school = self.extract_field(block, "School")
        if school:
            # Parse "School evocation [fire]; Level sorcerer/wizard 3"
            school_match = re.search(r"School\s+(\w+)(?:\s*\[([^\]]+)\])?\s*;\s*Level\s+(.+)", school, re.I)
            if school_match:
                fields["school"] = school_match.group(1)
                if school_match.group(2):
                    fields["descriptors"] = [d.strip() for d in school_match.group(2).split(',')]
                fields["level_text"] = school_match.group(3)
                
                # Extract numeric level
                level_match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", fields["level_text"])
                if level_match:
                    fields["level"] = int(level_match.group(1))
        
        # Other spell fields
        fields["casting_time"] = self.extract_field(block, "Casting Time")
        fields["components"] = self.extract_field(block, "Components")
        fields["range"] = self.extract_field(block, "Range")
        fields["effect"] = self.extract_field(block, "Effect")
        fields["area"] = self.extract_field(block, "Area")
        fields["targets"] = self.extract_field(block, "Targets")
        fields["duration"] = self.extract_field(block, "Duration")
        fields["saving_throw"] = self.extract_field(block, "Saving Throw")
        fields["spell_resistance"] = self.extract_field(block, "Spell Resistance")
        
        # Clean up None values
        return {k: v for k, v in fields.items() if v is not None}
    
    def parse_feat_fields(self, block: str) -> Dict[str, Any]:
        """Extract feat-specific metadata fields"""
        fields = {}
        
        fields["prerequisites"] = self.extract_field(block, "Prerequisites")
        fields["benefit"] = self.extract_field(block, "Benefit")
        fields["normal"] = self.extract_field(block, "Normal")
        fields["special"] = self.extract_field(block, "Special")
        
        # Extract feat type from parentheses in name line
        first_line = block.split('\n')[0]
        type_match = re.search(r'\(([^)]+)\)', first_line)
        if type_match:
            fields["feat_type"] = type_match.group(1)
        
        return {k: v for k, v in fields.items() if v is not None}
    
    def parse_monster_fields(self, block: str) -> Dict[str, Any]:
        """Extract monster-specific metadata fields"""
        fields = {}
        
        # Extract CR from first line
        first_line = block.split('\n')[0]
        cr_match = re.search(r'CR\s+(\d+(?:/\d+)?)', first_line, re.I)
        if cr_match:
            fields["challenge_rating"] = cr_match.group(1)
        
        fields["alignment"] = self.extract_field(block, "Alignment")
        fields["size"] = self.extract_field(block, "Size")
        fields["type"] = self.extract_field(block, "Type")
        fields["init"] = self.extract_field(block, "Init")
        fields["senses"] = self.extract_field(block, "Senses")
        
        return {k: v for k, v in fields.items() if v is not None}
    
    def split_spells_from_text(self, text: str, page_num: int = None) -> List[TTRPGConcept]:
        """Split text into individual spell concepts"""
        concepts = []
        
        # Find spell boundaries
        indices = [m.start() for m in self.spell_header_pattern.finditer(text)]
        indices = [0] + indices + [len(text)]
        
        for i in range(len(indices) - 1):
            block = text[indices[i]:indices[i + 1]].strip()
            if not block:
                continue
                
            # Validate this looks like a spell block
            if not re.search(r"\b(School|Level|Cast|Components|Range|Duration|Saving Throw)\b", block, re.I):
                continue
                
            name = self.canonicalize_name(block)
            concept_id = self.slugify(self.system, self.edition, "spell", name)
            
            # Extract spell metadata
            spell_fields = self.parse_spell_fields(block)
            
            metadata = {
                "system": self.system,
                "edition": self.edition,
                "book": self.book,
                "extraction_method": "concept_spell",
                **spell_fields
            }
            
            if page_num:
                metadata["page"] = page_num
            
            # Use size limiting to handle oversized chunks
            split_concepts = self.split_oversized_chunk(block, name, "spell", metadata)
            concepts.extend(split_concepts)
        
        return concepts
    
    def split_feats_from_text(self, text: str, page_num: int = None) -> List[TTRPGConcept]:
        """Split text into individual feat concepts"""
        concepts = []
        
        # Find feat boundaries  
        indices = [m.start() for m in self.feat_header_pattern.finditer(text)]
        indices = [0] + indices + [len(text)]
        
        for i in range(len(indices) - 1):
            block = text[indices[i]:indices[i + 1]].strip()
            if not block:
                continue
                
            # Validate this looks like a feat block
            if not re.search(r"\b(Prerequisites|Benefit|Normal|Special)\b", block, re.I):
                continue
                
            name = self.canonicalize_name(block)
            concept_id = self.slugify(self.system, self.edition, "feat", name)
            
            # Extract feat metadata
            feat_fields = self.parse_feat_fields(block)
            
            metadata = {
                "system": self.system,
                "edition": self.edition,
                "book": self.book,
                "extraction_method": "concept_feat",
                **feat_fields
            }
            
            if page_num:
                metadata["page"] = page_num
            
            # Use size limiting to handle oversized chunks
            split_concepts = self.split_oversized_chunk(block, name, "feat", metadata)
            concepts.extend(split_concepts)
        
        return concepts
    
    def route_and_split(self, text: str, page_num: int = None, section_hint: str = "") -> List[TTRPGConcept]:
        """Route text to appropriate concept splitter based on content analysis"""
        concepts = []
        
        # Check section hints and content patterns
        text_lower = text.lower()
        section_lower = section_hint.lower()
        
        # Spell content detection
        spell_indicators = ["school ", "level ", "casting time", "components", "saving throw", "spell resistance"]
        spell_score = sum(1 for indicator in spell_indicators if indicator in text_lower)
        
        # Feat content detection  
        feat_indicators = ["prerequisites", "benefit:", "normal:", "special:"]
        feat_score = sum(1 for indicator in feat_indicators if indicator in text_lower)
        
        # Monster content detection
        monster_indicators = [" cr ", "challenge rating", "alignment", "armor class", "hit points"]
        monster_score = sum(1 for indicator in monster_indicators if indicator in text_lower)
        
        # Route to best splitter
        if ("spell" in section_lower or spell_score >= 2):
            concepts.extend(self.split_spells_from_text(text, page_num))
        elif ("feat" in section_lower or feat_score >= 2):
            concepts.extend(self.split_feats_from_text(text, page_num))
        elif ("monster" in section_lower or "creature" in section_lower or monster_score >= 2):
            # Monster splitter - placeholder for now
            name = self.canonicalize_name(text)
            concept_id = self.slugify(self.system, self.edition, "monster", name)
            metadata = {
                "system": self.system,
                "edition": self.edition,
                "book": self.book,
                "extraction_method": "concept_monster"
            }
            if page_num:
                metadata["page"] = page_num
            
            # Use size limiting to handle oversized chunks
            split_concepts = self.split_oversized_chunk(text, name, "monster", metadata)
            concepts.extend(split_concepts)
        else:
            # Fallback: treat as general text but try to split reasonably
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            
            for para in paragraphs:
                if len(para) < 100:  # Skip very short fragments
                    continue
                    
                name = self.canonicalize_name(para)
                concept_id = self.slugify(self.system, self.edition, "text", name[:50])
                
                metadata = {
                    "system": self.system,
                    "edition": self.edition, 
                    "book": self.book,
                    "extraction_method": "concept_text"
                }
                if page_num:
                    metadata["page"] = page_num
                
                # Use size limiting to handle oversized chunks
                split_concepts = self.split_oversized_chunk(para, name, "text", metadata)
                concepts.extend(split_concepts)
        
        return concepts

def concept_chunk_document(text: str, page_num: int = None, section_title: str = "", 
                          system: str = "Pathfinder", edition: str = "1e", 
                          book: str = "Core Rulebook") -> List[TTRPGConcept]:
    """
    Fast concept-aware chunking for TTRPG content
    
    Args:
        text: Raw text content 
        page_num: Page number for citation
        section_title: Section hint for routing
        system: TTRPG system name
        edition: System edition
        book: Source book name
        
    Returns:
        List of TTRPGConcept objects, each containing one semantic concept
    """
    chunker = ConceptChunker(system, edition, book)
    return chunker.route_and_split(text, page_num, section_title)