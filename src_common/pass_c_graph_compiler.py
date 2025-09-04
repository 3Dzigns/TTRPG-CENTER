# src_common/pass_c_graph_compiler.py
"""
Pass C - Graph compilation using LlamaIndex
Implements the third pass of the Phase 1 ingestion pipeline.
"""

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

# LlamaIndex imports
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.extractors import KeywordExtractor
from llama_index.core.schema import BaseNode, TextNode

from ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphNode:
    """Node in the knowledge graph"""
    id: str
    node_type: str  # Concept, Rule, Procedure, Entity
    content: str
    chunk_refs: List[str]
    properties: Dict[str, Any]
    embedding_vector: Optional[List[float]] = None


@dataclass  
class GraphEdge:
    """Edge in the knowledge graph"""
    from_node: str
    to_node: str
    edge_type: str  # depends_on, part_of, related_to, implements
    weight: float
    properties: Dict[str, Any]


@dataclass
class PassCOutput:
    """Contract-compliant output for Pass C"""
    job_id: str
    phase: str
    tool: str
    input_file: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    processing_metadata: Dict[str, Any]


class PassCGraphCompiler:
    """Graph compiler using LlamaIndex for Pass C of the ingestion pipeline"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.tool_name = "llama_index"
        
        # TTRPG-specific node type classification
        self.node_type_patterns = {
            'Rule': ['rule', 'mechanic', 'system', 'roll', 'check', 'save', 'saving throw'],
            'Procedure': ['combat', 'turn order', 'sequence', 'step', 'process', 'phase'],
            'Entity': ['character', 'monster', 'item', 'spell', 'ability', 'feat'],
            'Concept': ['lore', 'world', 'setting', 'background', 'story', 'narrative']
        }
        
        # Relationship patterns for edge detection
        self.relationship_patterns = {
            'depends_on': ['requires', 'needs', 'must have', 'prerequisite'],
            'part_of': ['component', 'element', 'aspect', 'feature'],
            'related_to': ['similar', 'like', 'also', 'see also', 'compare'],
            'implements': ['uses', 'applies', 'follows', 'based on']
        }
    
    def compile_graph(self, pass_b_output_path: Path, output_dir: Path) -> PassCOutput:
        """
        Compile knowledge graph from Pass B output.
        
        Args:
            pass_b_output_path: Path to Pass B JSON output file
            output_dir: Directory to write output files
            
        Returns:
            PassCOutput with graph nodes and edges
        """
        logger.info(f"Starting Pass C graph compilation for {pass_b_output_path}", extra={
            'job_id': self.job_id,
            'phase': 'pass_c',
            'input_file': str(pass_b_output_path),
            'component': 'pass_c_graph_compiler'
        })
        
        start_time = time.time()
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Load Pass B output
            with open(pass_b_output_path, 'r', encoding='utf-8') as f:
                pass_b_data = json.load(f)
            
            logger.debug(f"Loaded {len(pass_b_data['enriched_chunks'])} enriched chunks from Pass B")
            
            # Create LlamaIndex documents
            documents = self._create_documents(pass_b_data['enriched_chunks'])
            
            # Generate graph nodes
            nodes = self._generate_nodes(documents, pass_b_data['enriched_chunks'])
            logger.info(f"Generated {len(nodes)} graph nodes")
            
            # Generate graph edges
            edges = self._generate_edges(nodes, pass_b_data['enriched_chunks'])
            logger.info(f"Generated {len(edges)} graph edges")
            
            # Calculate processing statistics
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            statistics = {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "graph_density": len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0.0,
                "node_types": {node_type: sum(1 for node in nodes if node.node_type == node_type) 
                             for node_type in ['Concept', 'Rule', 'Procedure', 'Entity']},
                "edge_types": {edge_type: sum(1 for edge in edges if edge.edge_type == edge_type)
                             for edge_type in ['depends_on', 'part_of', 'related_to', 'implements']},
                "average_node_connections": len(edges) / len(nodes) if nodes else 0,
                "processing_time_ms": processing_time_ms
            }
            
            processing_metadata = {
                "tool": self.tool_name,
                "version": self._get_llama_index_version(),
                "node_extraction_method": "semantic_analysis",
                "edge_detection_method": "pattern_matching_and_similarity",
                "max_nodes_per_chunk": 3,
                "similarity_threshold": 0.7,
                "timestamp": time.time()
            }
            
            # Create output object
            output = PassCOutput(
                job_id=self.job_id,
                phase="pass_c",
                tool=self.tool_name,
                input_file=str(pass_b_output_path),
                nodes=[asdict(node) for node in nodes],
                edges=[asdict(edge) for edge in edges],
                statistics=statistics,
                processing_metadata=processing_metadata
            )
            
            # Write output file
            output_file = output_dir / f"{self.job_id}_pass_c_graph.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(output), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Pass C completed successfully", extra={
                'job_id': self.job_id,
                'phase': 'pass_c',
                'nodes_created': len(nodes),
                'edges_created': len(edges),
                'graph_density': statistics['graph_density'],
                'processing_time_ms': processing_time_ms,
                'output_file': str(output_file),
                'component': 'pass_c_graph_compiler'
            })
            
            return output
            
        except Exception as e:
            logger.error(f"Pass C graph compilation failed: {str(e)}", extra={
                'job_id': self.job_id,
                'phase': 'pass_c',
                'error': str(e),
                'input_file': str(pass_b_output_path),
                'component': 'pass_c_graph_compiler'
            })
            raise
    
    def _create_documents(self, enriched_chunks: List[Dict[str, Any]]) -> List[Document]:
        """Convert enriched chunks to LlamaIndex documents"""
        documents = []
        
        for chunk in enriched_chunks:
            doc = Document(
                text=chunk['enhanced_content'],
                metadata={
                    'chunk_id': chunk['chunk_id'],
                    'entities': chunk['entities'],
                    'categories': chunk['categories'],
                    'complexity': chunk['complexity'],
                    'confidence': chunk['confidence'],
                    'original_content': chunk['original_content']
                }
            )
            documents.append(doc)
        
        return documents
    
    def _generate_nodes(self, documents: List[Document], enriched_chunks: List[Dict[str, Any]]) -> List[GraphNode]:
        """Generate graph nodes from documents"""
        nodes = []
        
        for i, (doc, chunk) in enumerate(zip(documents, enriched_chunks)):
            # Extract key concepts from the enriched content
            key_concepts = self._extract_key_concepts(doc.text, chunk)
            
            # Create nodes for each concept
            for j, concept in enumerate(key_concepts):
                node_id = self._generate_node_id(concept['content'])
                
                # Determine node type based on content
                node_type = self._classify_node_type(concept['content'], chunk['categories'])
                
                # Create properties
                properties = {
                    'source_chunk': chunk['chunk_id'],
                    'confidence': concept['confidence'],
                    'categories': chunk['categories'],
                    'entities': [e for e in chunk['entities'] if e.lower() in concept['content'].lower()],
                    'complexity': chunk['complexity']
                }
                
                node = GraphNode(
                    id=node_id,
                    node_type=node_type,
                    content=concept['content'],
                    chunk_refs=[chunk['chunk_id']],
                    properties=properties
                )
                
                # Check if we already have a similar node (merge if so)
                existing_node = self._find_similar_node(nodes, node)
                if existing_node:
                    self._merge_nodes(existing_node, node)
                else:
                    nodes.append(node)
        
        return nodes
    
    def _extract_key_concepts(self, content: str, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key concepts from content"""
        concepts = []
        
        # Extract from entities (high confidence concepts)
        for entity in chunk['entities'][:3]:  # Limit to top 3 entities per chunk
            if len(entity) > 2:  # Skip very short entities
                concepts.append({
                    'content': entity.title(),
                    'confidence': 0.9,
                    'source': 'entity'
                })
        
        # Extract from section headers and important phrases
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Check for headers (capitalized lines, chapter titles, etc.)
            if (line.isupper() and len(line) > 3) or line.startswith('Chapter '):
                concepts.append({
                    'content': line[:100],  # Limit length
                    'confidence': 0.8,
                    'source': 'header'
                })
            
            # Extract terms in definitions (pattern: "Term: definition")
            if ':' in line and len(line) < 200:
                term = line.split(':')[0].strip()
                if len(term) > 3 and term[0].isupper():
                    concepts.append({
                        'content': term,
                        'confidence': 0.7,
                        'source': 'definition'
                    })
        
        # Limit total concepts per chunk
        return concepts[:3]
    
    def _classify_node_type(self, content: str, categories: List[str]) -> str:
        """Classify node type based on content and categories"""
        content_lower = content.lower()
        
        # Check patterns for each node type
        for node_type, patterns in self.node_type_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                return node_type
        
        # Check categories
        if 'mechanics' in categories or 'combat' in categories:
            return 'Rule'
        elif 'spells' in categories or 'equipment' in categories:
            return 'Entity'
        elif 'character-creation' in categories:
            return 'Concept'
        else:
            return 'Concept'  # Default
    
    def _generate_node_id(self, content: str) -> str:
        """Generate a consistent node ID based on content"""
        # Create a hash of the normalized content
        normalized = content.lower().strip()
        hash_object = hashlib.md5(normalized.encode())
        return f"node_{hash_object.hexdigest()[:8]}"
    
    def _find_similar_node(self, nodes: List[GraphNode], target_node: GraphNode) -> Optional[GraphNode]:
        """Find a similar existing node for merging"""
        for node in nodes:
            # Check for exact content match
            if node.content.lower().strip() == target_node.content.lower().strip():
                return node
            
            # Check for substantial overlap in content
            similarity = self._calculate_content_similarity(node.content, target_node.content)
            if similarity > 0.8:  # High similarity threshold
                return node
        
        return None
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings"""
        # Simple word-based similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _merge_nodes(self, existing_node: GraphNode, new_node: GraphNode) -> None:
        """Merge a new node into an existing similar node"""
        # Merge chunk references
        for chunk_ref in new_node.chunk_refs:
            if chunk_ref not in existing_node.chunk_refs:
                existing_node.chunk_refs.append(chunk_ref)
        
        # Merge properties
        if 'entities' in new_node.properties and 'entities' in existing_node.properties:
            existing_entities = set(existing_node.properties['entities'])
            new_entities = set(new_node.properties['entities'])
            existing_node.properties['entities'] = list(existing_entities.union(new_entities))
        
        # Update confidence (take higher confidence)
        if 'confidence' in new_node.properties:
            existing_conf = existing_node.properties.get('confidence', 0)
            new_conf = new_node.properties['confidence']
            existing_node.properties['confidence'] = max(existing_conf, new_conf)
    
    def _generate_edges(self, nodes: List[GraphNode], enriched_chunks: List[Dict[str, Any]]) -> List[GraphEdge]:
        """Generate edges between nodes"""
        edges = []
        
        # Generate edges based on chunk co-occurrence
        edges.extend(self._generate_chunk_cooccurrence_edges(nodes))
        
        # Generate edges based on content relationships
        edges.extend(self._generate_content_relationship_edges(nodes))
        
        # Generate edges based on entity relationships
        edges.extend(self._generate_entity_relationship_edges(nodes))
        
        return edges
    
    def _generate_chunk_cooccurrence_edges(self, nodes: List[GraphNode]) -> List[GraphEdge]:
        """Generate edges between nodes that appear in the same chunk"""
        edges = []
        
        # Group nodes by chunk
        chunk_nodes = {}
        for node in nodes:
            for chunk_ref in node.chunk_refs:
                if chunk_ref not in chunk_nodes:
                    chunk_nodes[chunk_ref] = []
                chunk_nodes[chunk_ref].append(node)
        
        # Create edges between nodes in the same chunk
        for chunk_id, chunk_node_list in chunk_nodes.items():
            for i, node1 in enumerate(chunk_node_list):
                for node2 in chunk_node_list[i+1:]:
                    # Determine edge type based on node types
                    edge_type = self._determine_edge_type(node1, node2)
                    
                    # Calculate weight based on content similarity and co-occurrence
                    weight = self._calculate_edge_weight(node1, node2, 'cooccurrence')
                    
                    if weight > 0.3:  # Only create edges with sufficient weight
                        edge = GraphEdge(
                            from_node=node1.id,
                            to_node=node2.id,
                            edge_type=edge_type,
                            weight=weight,
                            properties={
                                'source': 'chunk_cooccurrence',
                                'shared_chunks': [chunk_id]
                            }
                        )
                        edges.append(edge)
        
        return edges
    
    def _generate_content_relationship_edges(self, nodes: List[GraphNode]) -> List[GraphEdge]:
        """Generate edges based on content relationships"""
        edges = []
        
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                # Check for relationship patterns in content
                edge_type, confidence = self._detect_content_relationship(node1.content, node2.content)
                
                if confidence > 0.5:  # Minimum confidence threshold
                    weight = confidence * 0.8  # Scale down content-based weights
                    
                    edge = GraphEdge(
                        from_node=node1.id,
                        to_node=node2.id,
                        edge_type=edge_type,
                        weight=weight,
                        properties={
                            'source': 'content_analysis',
                            'confidence': confidence
                        }
                    )
                    edges.append(edge)
        
        return edges
    
    def _generate_entity_relationship_edges(self, nodes: List[GraphNode]) -> List[GraphEdge]:
        """Generate edges based on shared entities"""
        edges = []
        
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                # Check for shared entities
                entities1 = set(node1.properties.get('entities', []))
                entities2 = set(node2.properties.get('entities', []))
                
                shared_entities = entities1.intersection(entities2)
                
                if shared_entities:
                    # Weight based on number of shared entities
                    weight = min(len(shared_entities) * 0.2, 0.8)
                    
                    edge = GraphEdge(
                        from_node=node1.id,
                        to_node=node2.id,
                        edge_type='related_to',
                        weight=weight,
                        properties={
                            'source': 'shared_entities',
                            'shared_entities': list(shared_entities)
                        }
                    )
                    edges.append(edge)
        
        return edges
    
    def _determine_edge_type(self, node1: GraphNode, node2: GraphNode) -> str:
        """Determine the edge type between two nodes"""
        # Rules for edge types based on node types
        type1, type2 = node1.node_type, node2.node_type
        
        if type1 == 'Concept' and type2 == 'Rule':
            return 'implements'
        elif type1 == 'Rule' and type2 == 'Procedure':
            return 'part_of'
        elif type1 == 'Entity' and type2 in ['Rule', 'Procedure']:
            return 'depends_on'
        else:
            return 'related_to'
    
    def _calculate_edge_weight(self, node1: GraphNode, node2: GraphNode, source: str) -> float:
        """Calculate edge weight between two nodes"""
        base_weight = 0.5
        
        # Boost weight for shared chunks
        shared_chunks = len(set(node1.chunk_refs).intersection(set(node2.chunk_refs)))
        chunk_boost = min(shared_chunks * 0.2, 0.3)
        
        # Boost weight for content similarity
        similarity = self._calculate_content_similarity(node1.content, node2.content)
        similarity_boost = similarity * 0.3
        
        # Boost weight for compatible node types
        type_compatibility = self._calculate_type_compatibility(node1.node_type, node2.node_type)
        type_boost = type_compatibility * 0.2
        
        weight = base_weight + chunk_boost + similarity_boost + type_boost
        return min(weight, 1.0)
    
    def _detect_content_relationship(self, content1: str, content2: str) -> Tuple[str, float]:
        """Detect relationship between content strings"""
        content1_lower = content1.lower()
        content2_lower = content2.lower()
        
        # Check for explicit relationship patterns
        for edge_type, patterns in self.relationship_patterns.items():
            for pattern in patterns:
                if (pattern in content1_lower and any(word in content2_lower for word in content1_lower.split())) or \
                   (pattern in content2_lower and any(word in content1_lower for word in content2_lower.split())):
                    return edge_type, 0.8
        
        # Default to related_to with lower confidence if content is similar
        similarity = self._calculate_content_similarity(content1, content2)
        if similarity > 0.3:
            return 'related_to', similarity
        
        return 'related_to', 0.0
    
    def _calculate_type_compatibility(self, type1: str, type2: str) -> float:
        """Calculate compatibility score between node types"""
        compatibility_matrix = {
            ('Concept', 'Rule'): 0.8,
            ('Concept', 'Entity'): 0.6,
            ('Rule', 'Procedure'): 0.9,
            ('Rule', 'Entity'): 0.7,
            ('Entity', 'Procedure'): 0.5,
            ('Concept', 'Concept'): 0.4,
            ('Rule', 'Rule'): 0.6,
            ('Entity', 'Entity'): 0.5,
            ('Procedure', 'Procedure'): 0.7
        }
        
        return compatibility_matrix.get((type1, type2), compatibility_matrix.get((type2, type1), 0.3))
    
    def _get_llama_index_version(self) -> str:
        """Get version of LlamaIndex library"""
        try:
            import llama_index
            return getattr(llama_index, '__version__', 'unknown')
        except:
            return 'unknown'


async def run_pass_c(job_id: str, pass_b_output_path: Path, output_dir: Path) -> PassCOutput:
    """
    Async wrapper for Pass C graph compilation.
    
    Args:
        job_id: Unique job identifier
        pass_b_output_path: Path to Pass B JSON output
        output_dir: Directory for output files
        
    Returns:
        PassCOutput with graph compilation results
    """
    compiler = PassCGraphCompiler(job_id)
    return compiler.compile_graph(pass_b_output_path, output_dir)


def run_pass_c_sync(job_id: str, pass_b_output_path: Path, output_dir: Path) -> PassCOutput:
    """
    Synchronous version for testing and simple use cases.
    
    Args:
        job_id: Unique job identifier
        pass_b_output_path: Path to Pass B JSON output
        output_dir: Directory for output files
        
    Returns:
        PassCOutput with graph compilation results
    """
    compiler = PassCGraphCompiler(job_id)
    return compiler.compile_graph(pass_b_output_path, output_dir)


if __name__ == "__main__":
    # Test with our Pass B output
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        pass_b_file = Path(sys.argv[1])
    else:
        pass_b_file = Path("artifacts/test/test_job_pass_b_enriched.json")
    
    if not pass_b_file.exists():
        print(f"Pass B output file not found: {pass_b_file}")
        sys.exit(1)
    
    output_dir = Path("artifacts/test")
    
    try:
        result = run_pass_c_sync("test_job", pass_b_file, output_dir)
        print(f"Pass C completed successfully!")
        print(f"Nodes created: {result.statistics['total_nodes']}")
        print(f"Edges created: {result.statistics['total_edges']}")
        print(f"Graph density: {result.statistics['graph_density']:.3f}")
        print(f"Processing time: {result.statistics['processing_time_ms']}ms")
        print(f"Node types: {result.statistics['node_types']}")
        print(f"Edge types: {result.statistics['edge_types']}")
        print(f"Output written to: {output_dir}")
        
    except Exception as e:
        print(f"Pass C failed: {e}")
        sys.exit(1)