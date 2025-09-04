# src_common/graph/build.py
"""
Graph Builder - Convert Phase 1/2 chunks into Knowledge Graph nodes and edges
US-302: Graph Builder from Retrieval implementation
"""

import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..ttrpg_logging import get_logger
from .store import GraphStore, NodeType, EdgeType

logger = get_logger(__name__)

@dataclass
class ProcedureGraph:
    """Result of building a procedure from chunks"""
    procedure: Dict[str, Any]
    steps: List[Dict[str, Any]]
    edges: List[Tuple[str, EdgeType, str, Dict[str, Any]]]
    source_docs: List[Dict[str, Any]]

class GraphBuilder:
    """
    Converts retrieval chunks and detected procedures into KG/WG nodes/edges
    
    Uses heuristics and LLM tagging to identify:
    - Procedures and their steps
    - Dependencies and prerequisites  
    - Source document citations
    - Rules and concepts
    """
    
    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store
        
    def build_procedure_from_chunks(self, chunks: List[Dict[str, Any]]) -> ProcedureGraph:
        """
        Convert chunks into a Procedure with Steps and dependencies
        
        Args:
            chunks: List of chunk dictionaries from Phase 1/2
        
        Returns:
            ProcedureGraph with procedure, steps, edges, and source docs
        """
        logger.info(f"Building procedure from {len(chunks)} chunks")
        
        try:
            # Detect procedure from chunk content
            procedure_info = self._detect_procedure(chunks)
            
            # Extract steps from chunks
            steps_info = self._extract_steps(chunks, procedure_info)
            
            # Build source document references
            source_docs = self._build_source_docs(chunks)
            
            # Create edges between procedure, steps, and sources
            edges = self._build_edges(procedure_info, steps_info, source_docs)
            
            return ProcedureGraph(
                procedure=procedure_info,
                steps=steps_info,
                edges=edges,
                source_docs=source_docs
            )
            
        except Exception as e:
            logger.error(f"Error building procedure from chunks: {e}")
            # Return minimal valid structure
            return ProcedureGraph(
                procedure={"id": "proc:unknown", "type": "Procedure", "properties": {"name": "Unknown Procedure"}},
                steps=[],
                edges=[],
                source_docs=[]
            )
    
    def build_knowledge_graph_from_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build knowledge graph nodes and edges from enriched chunks
        
        Args:
            chunks: Enriched chunks from Phase 2
        
        Returns:
            Dictionary with created nodes and edges
        """
        logger.info(f"Building knowledge graph from {len(chunks)} enriched chunks")
        
        created_nodes = []
        created_edges = []
        
        try:
            for chunk in chunks:
                # Extract entities and concepts
                entities = self._extract_entities(chunk)
                concepts = self._extract_concepts(chunk)
                rules = self._extract_rules(chunk)
                
                # Create nodes
                for entity in entities:
                    node_data = self.graph_store.upsert_node(
                        entity["id"], "Entity", entity["properties"]
                    )
                    created_nodes.append(node_data)
                
                for concept in concepts:
                    node_data = self.graph_store.upsert_node(
                        concept["id"], "Concept", concept["properties"]
                    )
                    created_nodes.append(node_data)
                
                for rule in rules:
                    node_data = self.graph_store.upsert_node(
                        rule["id"], "Rule", rule["properties"]
                    )
                    created_nodes.append(node_data)
                
                # Create source document node
                source_doc = self._create_source_doc_node(chunk)
                if source_doc:
                    node_data = self.graph_store.upsert_node(
                        source_doc["id"], "SourceDoc", source_doc["properties"]
                    )
                    created_nodes.append(node_data)
                    
                    # Create citation edges
                    for entity in entities + concepts + rules:
                        edge_data = self.graph_store.upsert_edge(
                            entity["id"], "cites", source_doc["id"], 
                            {"chunk_id": chunk.get("id", ""), "confidence": chunk.get("confidence", 1.0)}
                        )
                        created_edges.append(edge_data)
            
            return {
                "nodes_created": len(created_nodes),
                "edges_created": len(created_edges),
                "nodes": created_nodes,
                "edges": created_edges
            }
            
        except Exception as e:
            logger.error(f"Error building knowledge graph: {e}")
            return {"nodes_created": 0, "edges_created": 0, "nodes": [], "edges": []}
    
    def _detect_procedure(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect procedure name and properties from chunks"""
        
        # Look for procedure indicators in chunk content
        procedure_patterns = [
            r'(?:craft|create|make|build|construct)\s+([a-z\s]+)',
            r'(?:how to|steps to|process of)\s+([a-z\s]+)',
            r'([a-z\s]+)\s+(?:procedure|process|creation|crafting)',
        ]
        
        procedure_name = "Unknown Procedure"
        procedure_type = "general"
        
        # Combine all chunk content
        combined_content = " ".join([chunk.get("content", "") for chunk in chunks]).lower()
        
        for pattern in procedure_patterns:
            match = re.search(pattern, combined_content)
            if match:
                procedure_name = match.group(1).strip().title()
                if any(word in combined_content for word in ["potion", "alchemical", "brew"]):
                    procedure_type = "crafting"
                elif any(word in combined_content for word in ["character", "build", "level"]):
                    procedure_type = "character_creation"
                break
        
        # Generate stable ID
        procedure_id = f"proc:{hashlib.sha256(procedure_name.lower().encode()).hexdigest()[:16]}"
        
        return {
            "id": procedure_id,
            "type": "Procedure",
            "properties": {
                "name": procedure_name,
                "procedure_type": procedure_type,
                "description": f"Procedure for {procedure_name.lower()}",
                "chunk_count": len(chunks)
            }
        }
    
    def _extract_steps(self, chunks: List[Dict[str, Any]], procedure_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract ordered steps from chunks using heuristics"""
        
        steps = []
        step_patterns = [
            r'(\d+)\.\s*([^.]+)',  # Numbered list: "1. Do something"
            r'(?:first|second|third|next|then|finally)[,:]\s*([^.]+)',  # Sequential words
            r'step\s+(\d+)[:\s]+([^.]+)',  # "Step 1: Do something"
        ]
        
        step_counter = 1
        
        for chunk in chunks:
            content = chunk.get("content", "")
            
            # Look for step patterns
            for pattern in step_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) == 2:
                        step_num = match.group(1) if match.group(1).isdigit() else str(step_counter)
                        step_text = match.group(2).strip()
                    else:
                        step_num = str(step_counter)
                        step_text = match.group(1).strip()
                    
                    # Generate step ID
                    step_id = f"step:{procedure_info['id']}:{step_num}"
                    
                    steps.append({
                        "id": step_id,
                        "type": "Step",
                        "properties": {
                            "name": step_text[:100],  # Limit length
                            "description": step_text,
                            "step_number": int(step_num) if step_num.isdigit() else step_counter,
                            "chunk_id": chunk.get("id", ""),
                            "procedure_id": procedure_info["id"]
                        }
                    })
                    
                    step_counter += 1
        
        # If no explicit steps found, create generic steps from chunks
        if not steps:
            for i, chunk in enumerate(chunks[:5]):  # Limit to first 5 chunks
                step_id = f"step:{procedure_info['id']}:{i+1}"
                content = chunk.get("content", "")[:200]  # First 200 chars
                
                steps.append({
                    "id": step_id,
                    "type": "Step", 
                    "properties": {
                        "name": f"Step {i+1}",
                        "description": content,
                        "step_number": i+1,
                        "chunk_id": chunk.get("id", ""),
                        "procedure_id": procedure_info["id"]
                    }
                })
        
        return steps
    
    def _build_source_docs(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build SourceDoc nodes from chunks"""
        
        source_docs = []
        seen_sources = set()
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            
            # Extract source information
            source_id = None
            source_name = "Unknown Source"
            
            if "page" in metadata:
                source_name = f"Page {metadata['page']}"
                source_id = f"source:page:{metadata['page']}"
            elif "section" in metadata:
                source_name = metadata["section"]
                source_id = f"source:section:{hashlib.sha256(source_name.encode()).hexdigest()[:16]}"
            else:
                source_id = f"source:chunk:{chunk.get('id', 'unknown')}"
            
            if source_id not in seen_sources:
                seen_sources.add(source_id)
                
                source_docs.append({
                    "id": source_id,
                    "type": "SourceDoc",
                    "properties": {
                        "name": source_name,
                        "page": metadata.get("page"),
                        "section": metadata.get("section"),
                        "chunk_type": metadata.get("chunk_type", "text"),
                        "source_type": "document"
                    }
                })
        
        return source_docs
    
    def _build_edges(self, procedure_info: Dict[str, Any], steps_info: List[Dict[str, Any]], 
                     source_docs: List[Dict[str, Any]]) -> List[Tuple[str, EdgeType, str, Dict[str, Any]]]:
        """Build edges between procedure, steps, and sources"""
        
        edges = []
        
        # Procedure -> Steps (part_of relationships)
        for step in steps_info:
            edges.append((
                procedure_info["id"], "part_of", step["id"],
                {"step_number": step["properties"]["step_number"]}
            ))
        
        # Steps -> Steps (prereq relationships for sequential steps)
        sorted_steps = sorted(steps_info, key=lambda s: s["properties"]["step_number"])
        for i in range(len(sorted_steps) - 1):
            current_step = sorted_steps[i]
            next_step = sorted_steps[i + 1]
            
            edges.append((
                next_step["id"], "prereq", current_step["id"],
                {"sequence": i + 1}
            ))
        
        # Steps -> SourceDocs (cites relationships)
        for step in steps_info:
            step_chunk_id = step["properties"].get("chunk_id")
            
            for source_doc in source_docs:
                # Simple heuristic: if step came from a chunk, cite the corresponding source
                edges.append((
                    step["id"], "cites", source_doc["id"],
                    {"chunk_id": step_chunk_id, "confidence": 0.8}
                ))
        
        return edges
    
    def _extract_entities(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract Entity nodes from enriched chunk"""
        entities = []
        
        # Check if chunk has enriched metadata with entities
        metadata = chunk.get("metadata", {})
        chunk_entities = metadata.get("entities", [])
        
        for entity_data in chunk_entities:
            if isinstance(entity_data, dict):
                entity_id = f"entity:{hashlib.sha256(entity_data.get('name', 'unknown').encode()).hexdigest()[:16]}"
                entities.append({
                    "id": entity_id,
                    "properties": {
                        "name": entity_data.get("name", "Unknown Entity"),
                        "type": entity_data.get("type", "general"),
                        "description": entity_data.get("description", ""),
                        "chunk_id": chunk.get("id", "")
                    }
                })
        
        return entities
    
    def _extract_concepts(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract Concept nodes from enriched chunk"""
        concepts = []
        
        metadata = chunk.get("metadata", {})
        categories = metadata.get("categories", [])
        
        for category in categories:
            if isinstance(category, str):
                concept_id = f"concept:{hashlib.sha256(category.encode()).hexdigest()[:16]}"
                concepts.append({
                    "id": concept_id,
                    "properties": {
                        "name": category,
                        "category": "gameplay_concept",
                        "chunk_id": chunk.get("id", "")
                    }
                })
        
        return concepts
    
    def _extract_rules(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract Rule nodes from chunk content"""
        rules = []
        
        content = chunk.get("content", "")
        
        # Look for rule patterns
        rule_patterns = [
            r'DC\s+(\d+)',  # Difficulty Class
            r'(\d+d\d+(?:\+\d+)?)',  # Dice notation
            r'(?:must|required|cannot|may not|always|never)\s+([^.]+)',  # Rule language
        ]
        
        rule_counter = 1
        for pattern in rule_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                rule_text = match.group(0)
                rule_id = f"rule:{hashlib.sha256(rule_text.encode()).hexdigest()[:16]}"
                
                rules.append({
                    "id": rule_id,
                    "properties": {
                        "name": f"Rule {rule_counter}",
                        "text": rule_text,
                        "rule_type": "mechanical",
                        "chunk_id": chunk.get("id", "")
                    }
                })
                rule_counter += 1
                
                if rule_counter > 10:  # Limit rules per chunk
                    break
        
        return rules
    
    def _create_source_doc_node(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a SourceDoc node for the chunk"""
        metadata = chunk.get("metadata", {})
        
        if metadata.get("page"):
            source_id = f"source:page:{metadata['page']}"
            return {
                "id": source_id,
                "properties": {
                    "name": f"Page {metadata['page']}",
                    "page": metadata["page"],
                    "document_type": "rulebook",
                    "chunk_id": chunk.get("id", "")
                }
            }
        
        return None


# Convenience function matching Phase 3 spec
def build_procedure_from_chunks(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function for building procedures from chunks
    Returns dictionary format matching Phase 3 specification
    """
    # Create temporary graph store for building
    from pathlib import Path
    temp_store = GraphStore(storage_path=Path("artifacts/temp_graph"))
    builder = GraphBuilder(temp_store)
    
    result = builder.build_procedure_from_chunks(chunks)
    
    return {
        "procedure": result.procedure,
        "steps": result.steps,
        "edges": result.edges
    }