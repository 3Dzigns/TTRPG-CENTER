#!/usr/bin/env python3
"""
Phase 3: Graph Creation for Complex Workflows
=============================================

FOCUS: RELATIONSHIPS - Create knowledge graphs from enriched content
- Read enriched chunks from AstraDB
- Identify relationships between concepts
- Create graphs for complex workflows
- Enable advanced querying and reasoning

This phase builds on the enriched chunks from Phase 2 to create semantic relationships.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from datetime import datetime, timezone
from collections import defaultdict, Counter
import re

from astrapy import DataAPIClient
import os

logger = logging.getLogger(__name__)

class ConceptRelationship:
    """Represents a relationship between two concepts"""
    
    def __init__(self, source_id: str, target_id: str, relationship_type: str, 
                 confidence: float, metadata: Dict[str, Any] = None):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.confidence = confidence
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "metadata": self.metadata
        }

class Phase3GraphCreation:
    """Phase 3: Create knowledge graphs from enriched chunks"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.relationships: List[ConceptRelationship] = []
        self.concept_index: Dict[str, Dict] = {}
        
        # Initialize AstraDB client
        self.client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
        endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.database = self.client.get_database_by_api_endpoint(endpoint)
        
    def _progress_update(self, phase: str, message: str, progress: float, details: Dict = None):
        """Send progress update"""
        if self.progress_callback:
            self.progress_callback(phase, message, progress, details)
    
    def _load_enriched_chunks(self, collection_name: str, session_id: str = None) -> List[Dict]:
        """Load enriched chunks from AstraDB"""
        collection = self.database.get_collection(collection_name)
        
        # Query for enriched chunks
        query = {"metadata.phase2_processed": True}
        if session_id:
            query["metadata.session_id"] = session_id
        
        chunks = list(collection.find(query))
        logger.info(f"Loaded {len(chunks)} enriched chunks")
        return chunks
    
    def _find_spell_prerequisites(self, spell_chunks: List[Dict]) -> List[ConceptRelationship]:
        """Find prerequisite relationships between spells"""
        relationships = []
        
        # Create spell lookup by name
        spell_lookup = {chunk["metadata"]["concept_name"]: chunk for chunk in spell_chunks}
        
        for chunk in spell_chunks:
            spell_name = chunk["metadata"]["concept_name"]
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})
            
            # Look for spell references in content (heightened versions, prerequisites)
            spell_refs = re.findall(r"\b([A-Z][A-Za-z ]{2,30})\b", content)
            
            for ref in spell_refs:
                ref = ref.strip()
                if ref != spell_name and ref in spell_lookup:
                    target_chunk = spell_lookup[ref]
                    target_level = target_chunk["metadata"].get("level", 0)
                    source_level = metadata.get("level", 0)
                    
                    # If referenced spell is lower level, it might be a prerequisite
                    if target_level < source_level:
                        relationship = ConceptRelationship(
                            source_id=chunk["metadata"]["concept_id"],
                            target_id=target_chunk["metadata"]["concept_id"],
                            relationship_type="requires_knowledge_of",
                            confidence=0.7,
                            metadata={"level_difference": source_level - target_level}
                        )
                        relationships.append(relationship)
        
        return relationships
    
    def _find_spell_school_relationships(self, spell_chunks: List[Dict]) -> List[ConceptRelationship]:
        """Find relationships between spells of the same school"""
        relationships = []
        
        # Group spells by school
        school_groups = defaultdict(list)
        for chunk in spell_chunks:
            school = chunk["metadata"].get("school")
            if school:
                school_groups[school].append(chunk)
        
        # Create within-school relationships
        for school, spells in school_groups.items():
            if len(spells) > 1:
                # Sort by level for progression relationships
                spells.sort(key=lambda x: x["metadata"].get("level", 0))
                
                for i, spell1 in enumerate(spells):
                    for spell2 in spells[i+1:i+4]:  # Limit to nearby levels
                        level1 = spell1["metadata"].get("level", 0)
                        level2 = spell2["metadata"].get("level", 0)
                        
                        if 0 < level2 - level1 <= 2:  # Progressive levels
                            relationship = ConceptRelationship(
                                source_id=spell2["metadata"]["concept_id"],
                                target_id=spell1["metadata"]["concept_id"],
                                relationship_type="school_progression",
                                confidence=0.8,
                                metadata={"school": school, "level_progression": level2 - level1}
                            )
                            relationships.append(relationship)
        
        return relationships
    
    def _find_component_relationships(self, spell_chunks: List[Dict]) -> List[ConceptRelationship]:
        """Find spells that share similar components"""
        relationships = []
        
        # Group spells by component types
        component_groups = defaultdict(list)
        
        for chunk in spell_chunks:
            components = chunk["metadata"].get("components", "")
            if components:
                # Extract component types (V, S, M, F, DF, etc.)
                comp_types = re.findall(r'\b([VSMFDF]+)\b', components.upper())
                for comp_type in comp_types:
                    component_groups[comp_type].append(chunk)
        
        # Find spells with rare component combinations
        for comp_type, spells in component_groups.items():
            if len(spells) > 1 and len(spells) < 20:  # Not too common, not too rare
                for i, spell1 in enumerate(spells):
                    for spell2 in spells[i+1:]:
                        relationship = ConceptRelationship(
                            source_id=spell1["metadata"]["concept_id"],
                            target_id=spell2["metadata"]["concept_id"],
                            relationship_type="shared_component",
                            confidence=0.6,
                            metadata={"component_type": comp_type}
                        )
                        relationships.append(relationship)
        
        return relationships
    
    def _find_thematic_clusters(self, chunks: List[Dict]) -> List[ConceptRelationship]:
        """Find thematic relationships across all concept types"""
        relationships = []
        
        # Extract keywords from all chunks
        keyword_groups = defaultdict(list)
        
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            concept_name = chunk["metadata"]["concept_name"].lower()
            
            # Look for thematic keywords
            keywords = [
                "fire", "ice", "cold", "lightning", "thunder", "acid", "poison",
                "healing", "death", "undead", "divine", "arcane", "nature",
                "illusion", "charm", "fear", "mind", "teleport", "summon",
                "weapon", "armor", "shield", "attack", "defense", "movement"
            ]
            
            for keyword in keywords:
                if keyword in content or keyword in concept_name:
                    keyword_groups[keyword].append(chunk)
        
        # Create thematic relationships
        for theme, chunks_in_theme in keyword_groups.items():
            if len(chunks_in_theme) > 2:
                for i, chunk1 in enumerate(chunks_in_theme):
                    for chunk2 in chunks_in_theme[i+1:i+6]:  # Limit connections
                        # Higher confidence for same concept types
                        confidence = 0.7 if chunk1["metadata"]["concept_type"] == chunk2["metadata"]["concept_type"] else 0.5
                        
                        relationship = ConceptRelationship(
                            source_id=chunk1["metadata"]["concept_id"],
                            target_id=chunk2["metadata"]["concept_id"],
                            relationship_type="thematic_similarity",
                            confidence=confidence,
                            metadata={"theme": theme}
                        )
                        relationships.append(relationship)
        
        return relationships
    
    def _create_concept_workflows(self, chunks: List[Dict]) -> Dict[str, Any]:
        """Create workflow patterns from concept relationships"""
        workflows = {}
        
        # Spell progression workflows
        spell_chunks = [c for c in chunks if c["metadata"]["concept_type"] == "spell"]
        if spell_chunks:
            # Group by school for progression paths
            school_progressions = defaultdict(list)
            for chunk in spell_chunks:
                school = chunk["metadata"].get("school")
                level = chunk["metadata"].get("level", 0)
                if school and level:
                    school_progressions[school].append((level, chunk))
            
            # Create progression workflows
            for school, spells in school_progressions.items():
                spells.sort(key=lambda x: x[0])  # Sort by level
                if len(spells) >= 3:
                    workflow = {
                        "type": "spell_progression",
                        "school": school,
                        "levels": [s[0] for s in spells],
                        "spells": [s[1]["metadata"]["concept_name"] for s in spells],
                        "concept_ids": [s[1]["metadata"]["concept_id"] for s in spells]
                    }
                    workflows[f"progression_{school}"] = workflow
        
        # Combat workflows (spells + feats)
        combat_keywords = ["attack", "damage", "weapon", "armor", "combat", "battle"]
        combat_concepts = []
        
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            if any(keyword in content for keyword in combat_keywords):
                combat_concepts.append(chunk)
        
        if len(combat_concepts) >= 5:
            workflows["combat_system"] = {
                "type": "thematic_workflow",
                "theme": "combat",
                "concept_count": len(combat_concepts),
                "concept_types": Counter(c["metadata"]["concept_type"] for c in combat_concepts),
                "concept_ids": [c["metadata"]["concept_id"] for c in combat_concepts[:20]]  # Limit size
            }
        
        return workflows
    
    def process_collection(self, collection_name: str, session_id: str = None,
                          output_dir: str = "phase3_graphs") -> Dict[str, Any]:
        """
        Create knowledge graphs from enriched collection
        
        Args:
            collection_name: AstraDB collection name
            session_id: Optional session ID to filter chunks
            output_dir: Directory to save graph data
            
        Returns:
            Phase 3 results dictionary
        """
        start_time = time.time()
        
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Load enriched chunks
            self._progress_update("Phase3-Loading", "Loading enriched chunks", 10.0)
            chunks = self._load_enriched_chunks(collection_name, session_id)
            
            if not chunks:
                return {"success": False, "error": "No enriched chunks found"}
            
            # Build concept index
            self._progress_update("Phase3-Indexing", "Building concept index", 20.0)
            for chunk in chunks:
                concept_id = chunk["metadata"]["concept_id"]
                self.concept_index[concept_id] = chunk["metadata"]
            
            # Find relationships by type
            all_relationships = []
            
            # Spell-specific relationships
            spell_chunks = [c for c in chunks if c["metadata"]["concept_type"] == "spell"]
            if spell_chunks:
                self._progress_update("Phase3-Analysis", "Analyzing spell relationships", 30.0)
                all_relationships.extend(self._find_spell_prerequisites(spell_chunks))
                
                self._progress_update("Phase3-Analysis", "Finding school progressions", 40.0)
                all_relationships.extend(self._find_spell_school_relationships(spell_chunks))
                
                self._progress_update("Phase3-Analysis", "Analyzing components", 50.0)
                all_relationships.extend(self._find_component_relationships(spell_chunks))
            
            # Cross-concept relationships
            self._progress_update("Phase3-Analysis", "Finding thematic clusters", 60.0)
            all_relationships.extend(self._find_thematic_clusters(chunks))
            
            # Create workflows
            self._progress_update("Phase3-Workflows", "Creating concept workflows", 70.0)
            workflows = self._create_concept_workflows(chunks)
            
            # Generate graph statistics
            self._progress_update("Phase3-Statistics", "Generating statistics", 80.0)
            relationship_types = Counter(r.relationship_type for r in all_relationships)
            concept_types = Counter(c["metadata"]["concept_type"] for c in chunks)
            
            # Save graph data
            self._progress_update("Phase3-Saving", "Saving graph data", 90.0)
            
            graph_data = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "collection_name": collection_name,
                "concepts": {cid: meta for cid, meta in self.concept_index.items()},
                "relationships": [r.to_dict() for r in all_relationships],
                "workflows": workflows,
                "statistics": {
                    "total_concepts": len(chunks),
                    "total_relationships": len(all_relationships),
                    "concept_types": dict(concept_types),
                    "relationship_types": dict(relationship_types),
                    "workflows_created": len(workflows)
                }
            }
            
            # Save to file
            graph_file = output_path / f"knowledge_graph_{session_id or 'full'}_{int(time.time())}.json"
            with open(graph_file, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)
            
            total_duration = time.time() - start_time
            
            # Final results
            results = {
                "success": True,
                "session_id": session_id,
                "collection_name": collection_name,
                "concepts_processed": len(chunks),
                "relationships_created": len(all_relationships),
                "workflows_created": len(workflows),
                "graph_file": str(graph_file),
                "duration_seconds": total_duration,
                "statistics": graph_data["statistics"]
            }
            
            self._progress_update("Phase3-Complete", "Knowledge graph creation complete", 100.0, results)
            
            logger.info(f"Phase 3 complete: {len(all_relationships)} relationships created in {total_duration:.1f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Phase 3 failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }

def run_phase3_graph_creation(collection_name: str, session_id: str = None,
                             progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to run Phase 3 graph creation
    
    Args:
        collection_name: AstraDB collection name
        session_id: Optional session ID to filter chunks
        progress_callback: Progress callback function
        
    Returns:
        Phase 3 results dictionary
    """
    phase3 = Phase3GraphCreation(progress_callback)
    return phase3.process_collection(collection_name, session_id)

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(phase, message, progress, details=None):
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details:
            print(f"         Details: {details}")
    
    collection_name = sys.argv[1] if len(sys.argv) > 1 else "ttrpg_chunks_dev"
    session_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = run_phase3_graph_creation(
        collection_name=collection_name,
        session_id=session_id,
        progress_callback=progress_callback
    )
    
    print(f"\nPhase 3 Results:")
    print(f"Success: {result['success']}")
    print(f"Concepts processed: {result.get('concepts_processed', 0)}")
    print(f"Relationships created: {result.get('relationships_created', 0)}")
    print(f"Workflows created: {result.get('workflows_created', 0)}")
    print(f"Graph file: {result.get('graph_file', 'N/A')}")
    print(f"Duration: {result.get('duration_seconds', 0):.1f}s")