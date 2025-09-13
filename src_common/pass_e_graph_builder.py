# src_common/pass_e_graph_builder.py
"""
Pass E: LlamaIndex (Graph & Cross-Refs)

Build document graph (sections→subsections→chunks), cross-references 
(spells ↔ classes/feats/rules), and ToC lineage.

Responsibilities:
- Load vectorized chunks from Pass D
- Build document graph structure
- Extract cross-references between game elements
- Create ToC lineage and section relationships
- Upsert graph metadata to dictionary
- Update chunks with graph_refs, toc_lineage, related_ids
- Mark chunks as stage:"graph_enriched"

Artifacts:
- graph_snapshot.json: Complete graph structure
- alias_map.json: Term aliases and relationships
- relationship_edges.jsonl: Graph edges and connections
- manifest.json: Updated with graph results
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
import os
from dataclasses import dataclass, asdict
from collections import defaultdict

# LlamaIndex imports (optional)
try:
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.node_parser import SimpleNodeParser
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from .logging import get_logger
from .artifact_validator import write_json_atomically, load_json_with_retry
from .astra_loader import AstraLoader
from .dictionary_loader import DictionaryLoader, DictEntry

logger = get_logger(__name__)
ASTRA_REQUIRE_CREDS = os.getenv('ASTRA_REQUIRE_CREDS', 'true').strip().lower() in ('1','true','yes')


@dataclass
class GraphNode:
    """Node in the document graph"""
    node_id: str
    node_type: str  # section, chunk, entity
    title: str
    content: Optional[str] = None
    parent_id: Optional[str] = None
    children: List[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class GraphEdge:
    """Edge in the document graph"""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str  # contains, references, relates_to
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CrossReference:
    """Cross-reference between game elements"""
    ref_id: str
    source_element: str
    target_element: str
    ref_type: str  # spell_to_class, feat_to_rule, etc.
    confidence: float
    context: str


@dataclass
class PassEResult:
    """Result of Pass E graph building"""
    source_file: str
    job_id: str
    chunks_processed: int
    chunks_updated: int
    graph_nodes: int
    graph_edges: int
    cross_references: int
    dictionary_updates: int
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassEGraphBuilder:
    """Pass E: LlamaIndex Graph & Cross-Reference Builder"""
    
    def __init__(self, job_id: str, env: str = "dev"):
        self.job_id = job_id
        self.env = env
        self.astra_loader = AstraLoader(env)
        self.dict_loader = DictionaryLoader(env)
        # Graph backend selection (FR-006)
        self.graph_backend = os.getenv("GRAPH_BACKEND", "files").strip().lower()
        self.neo4j_uri = os.getenv("NEO4J_URI", "").strip()
        self.neo4j_user = os.getenv("NEO4J_USER", "").strip()
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "").strip()
        
        # Graph storage
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.cross_references: List[CrossReference] = []
        
    def process_chunks(self, output_dir: Path) -> PassEResult:
        """
        Process chunks for Pass E: Graph building and cross-references
        
        Args:
            output_dir: Directory containing Pass D artifacts
            
        Returns:
            PassEResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Pass E starting: Graph building for job {self.job_id}")
        
        try:
            # Load vectorized chunks from Pass D
            vectors_file = output_dir / f"{self.job_id}_pass_d_vectors.jsonl"
            if not vectors_file.exists():
                raise FileNotFoundError(f"Pass D vectors file not found: {vectors_file}")
            
            vectorized_chunks = self._load_vectorized_chunks(vectors_file)
            logger.info(f"Loaded {len(vectorized_chunks)} vectorized chunks from Pass D")
            
            # Build document graph structure
            self._build_document_graph(vectorized_chunks)
            logger.info(f"Built graph with {len(self.nodes)} nodes and {len(self.edges)} edges")
            
            # Extract cross-references
            self._extract_cross_references(vectorized_chunks)
            logger.info(f"Extracted {len(self.cross_references)} cross-references")
            
            # Update chunks with graph metadata
            updated_chunks = self._enrich_chunks_with_graph(vectorized_chunks)
            logger.info(f"Updated {len(updated_chunks)} chunks with graph metadata")
            
            # Update dictionary with aliases and relations
            dict_updates = self._update_dictionary_with_relations()
            logger.info(f"Updated dictionary with {dict_updates} new relations")
            
            # Write graph artifacts
            graph_snapshot_path = self._write_graph_snapshot(output_dir)
            alias_map_path = self._write_alias_map(output_dir)
            edges_path = self._write_relationship_edges(output_dir)
            
            # Update chunks in AstraDB
            chunks_updated = self._batch_update_chunks(updated_chunks)
            
            # Update manifest
            manifest_path = self._update_manifest(
                output_dir,
                len(vectorized_chunks),
                chunks_updated,
                len(self.nodes),
                len(self.edges),
                len(self.cross_references),
                dict_updates,
                [graph_snapshot_path, alias_map_path, edges_path]
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            # Optional: write to Neo4j if configured
            if self.graph_backend == "neo4j" and self.neo4j_uri:
                try:
                    self._write_to_neo4j()
                    logger.info("Neo4j graph upsert completed")
                except Exception as e:
                    logger.warning(f"Neo4j graph upsert failed: {e}")

            logger.info(f"Pass E completed for job {self.job_id} in {processing_time_ms}ms")
            
            return PassEResult(
                source_file="",  # Will be filled from manifest
                job_id=self.job_id,
                chunks_processed=len(vectorized_chunks),
                chunks_updated=chunks_updated,
                graph_nodes=len(self.nodes),
                graph_edges=len(self.edges),
                cross_references=len(self.cross_references),
                dictionary_updates=dict_updates,
                processing_time_ms=processing_time_ms,
                artifacts=[str(graph_snapshot_path), str(alias_map_path), str(edges_path)],
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass E failed for job {self.job_id}: {e}")
            
            return PassEResult(
                source_file="",
                job_id=self.job_id,
                chunks_processed=0,
                chunks_updated=0,
                graph_nodes=0,
                graph_edges=0,
                cross_references=0,
                dictionary_updates=0,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )

    def _write_to_neo4j(self) -> None:
        """Upsert nodes and edges into Neo4j using Bolt driver."""
        from neo4j import GraphDatabase  # type: ignore

        if not (self.neo4j_uri and self.neo4j_user and self.neo4j_password):
            raise RuntimeError("Neo4j credentials not configured")

        driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        try:
            with driver.session() as session:
                # Best-effort unique constraint
                try:
                    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Node) REQUIRE n.node_id IS UNIQUE")
                except Exception:
                    pass

                # Upsert nodes
                for node in self.nodes.values():
                    label = "Section" if node.node_type == "section" else ("Chunk" if node.node_type == "chunk" else "Entity")
                    session.run(
                        f"MERGE (n:{label} {{node_id: $id}}) SET n.title=$title, n.parent_id=$parent, n.metadata=$metadata",
                        {
                            "id": node.node_id,
                            "title": node.title,
                            "parent": node.parent_id,
                            "metadata": node.metadata or {},
                        },
                    )

                # Upsert edges
                for edge in self.edges:
                    rel_type = "CONTAINS" if edge.edge_type == "contains" else "RELATES_TO"
                    session.run(
                        f"MATCH (s {{node_id:$sid}}), (t {{node_id:$tid}}) MERGE (s)-[r:{rel_type}]->(t) SET r.edge_id=$eid, r.edge_type=$etype, r.weight=$w",
                        {
                            "sid": edge.source_id,
                            "tid": edge.target_id,
                            "eid": edge.edge_id,
                            "etype": edge.edge_type,
                            "w": edge.weight,
                        },
                    )
        finally:
            driver.close()
    
    def _load_vectorized_chunks(self, vectors_file: Path) -> List[Dict[str, Any]]:
        """Load vectorized chunks from Pass D JSONL file"""
        
        chunks = []
        with open(vectors_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk_data = json.loads(line)
                    chunks.append(chunk_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
        
        return chunks
    
    def _build_document_graph(self, chunks: List[Dict[str, Any]]):
        """Build hierarchical document graph from chunks"""
        
        # Group chunks by section hierarchy
        sections = defaultdict(list)
        
        for chunk in chunks:
            toc_path = chunk.get("toc_path", "")
            section_id = chunk.get("section_id", "")
            page_span = chunk.get("page_span", "")
            
            # Create section key
            section_key = f"{toc_path}:{section_id}" if toc_path else section_id
            sections[section_key].append(chunk)
        
        # Create section nodes
        for section_key, section_chunks in sections.items():
            toc_path, section_id = section_key.split(":", 1) if ":" in section_key else ("", section_key)
            
            # Create section node
            section_node = GraphNode(
                node_id=f"section_{section_id}",
                node_type="section",
                title=toc_path or f"Section {section_id}",
                metadata={
                    "chunk_count": len(section_chunks),
                    "toc_path": toc_path,
                    "section_id": section_id
                }
            )
            self.nodes[section_node.node_id] = section_node
            
            # Create chunk nodes and link to section
            for chunk in section_chunks:
                chunk_id = chunk.get("chunk_id", "")
                chunk_node = GraphNode(
                    node_id=chunk_id,
                    node_type="chunk",
                    title=f"Chunk {chunk_id}",
                    content=chunk.get("content", "")[:200],  # Truncated content
                    parent_id=section_node.node_id,
                    metadata={
                        "page_number": chunk.get("page_number", 0),
                        "element_type": chunk.get("element_type", ""),
                        "confidence_score": chunk.get("confidence_score", 0.0)
                    }
                )
                self.nodes[chunk_id] = chunk_node
                
                # Add chunk to section's children
                section_node.children.append(chunk_id)
                
                # Create containment edge
                edge = GraphEdge(
                    edge_id=f"contains_{section_node.node_id}_{chunk_id}",
                    source_id=section_node.node_id,
                    target_id=chunk_id,
                    edge_type="contains",
                    weight=1.0
                )
                self.edges.append(edge)
        
        # Build ToC hierarchy
        self._build_toc_hierarchy(chunks)
    
    def _build_toc_hierarchy(self, chunks: List[Dict[str, Any]]):
        """Build ToC hierarchy from chunks"""
        
        # Extract unique ToC paths
        toc_paths = set()
        for chunk in chunks:
            toc_path = chunk.get("toc_path", "")
            if toc_path and " > " in toc_path:
                toc_paths.add(toc_path)
        
        # Create hierarchical relationships
        for toc_path in toc_paths:
            parts = toc_path.split(" > ")
            
            for i in range(len(parts) - 1):
                parent_path = " > ".join(parts[:i+1])
                child_path = " > ".join(parts[:i+2])
                
                parent_node_id = f"toc_{parent_path.replace(' ', '_').lower()}"
                child_node_id = f"toc_{child_path.replace(' ', '_').lower()}"
                
                # Create hierarchy edge
                edge = GraphEdge(
                    edge_id=f"hierarchy_{parent_node_id}_{child_node_id}",
                    source_id=parent_node_id,
                    target_id=child_node_id,
                    edge_type="hierarchy",
                    weight=1.0,
                    metadata={"level_diff": 1}
                )
                self.edges.append(edge)
    
    def _extract_cross_references(self, chunks: List[Dict[str, Any]]):
        """Extract cross-references between game elements"""
        
        # TTRPG element patterns
        spell_pattern = r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) \(spell\)|(?:cast|casting) ([A-Z][a-z]+(?:[ -][A-Z][a-z]+)*)'
        class_pattern = r'\b(Fighter|Wizard|Rogue|Cleric|Barbarian|Ranger|Paladin|Sorcerer|Warlock|Bard|Druid|Monk)\b'
        feat_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+) \(feat\)|gains? the ([A-Z][a-z]+ [A-Z][a-z]+) feat'
        rule_pattern = r'\b(Attack of Opportunity|Sneak Attack|Rage|Spellcasting|Turn Undead)\b'
        
        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            
            # Find spells
            spells = set()
            for match in re.finditer(spell_pattern, content):
                spell_name = match.group(1) or match.group(2)
                if spell_name:
                    spells.add(spell_name)
            
            # Find classes
            classes = set(re.findall(class_pattern, content))
            
            # Find feats
            feats = set()
            for match in re.finditer(feat_pattern, content):
                feat_name = match.group(1) or match.group(2)
                if feat_name:
                    feats.add(feat_name)
            
            # Find rules
            rules = set(re.findall(rule_pattern, content))
            
            # Create cross-references
            ref_counter = 0
            
            # Spell to class relationships
            for spell in spells:
                for class_name in classes:
                    ref_id = f"{chunk_id}_ref_{ref_counter}"
                    cross_ref = CrossReference(
                        ref_id=ref_id,
                        source_element=spell,
                        target_element=class_name,
                        ref_type="spell_to_class",
                        confidence=0.7,
                        context=content[:200]
                    )
                    self.cross_references.append(cross_ref)
                    ref_counter += 1
            
            # Feat to class relationships
            for feat in feats:
                for class_name in classes:
                    ref_id = f"{chunk_id}_ref_{ref_counter}"
                    cross_ref = CrossReference(
                        ref_id=ref_id,
                        source_element=feat,
                        target_element=class_name,
                        ref_type="feat_to_class",
                        confidence=0.8,
                        context=content[:200]
                    )
                    self.cross_references.append(cross_ref)
                    ref_counter += 1
            
            # Rule to class relationships
            for rule in rules:
                for class_name in classes:
                    ref_id = f"{chunk_id}_ref_{ref_counter}"
                    cross_ref = CrossReference(
                        ref_id=ref_id,
                        source_element=rule,
                        target_element=class_name,
                        ref_type="rule_to_class",
                        confidence=0.6,
                        context=content[:200]
                    )
                    self.cross_references.append(cross_ref)
                    ref_counter += 1
    
    def _enrich_chunks_with_graph(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich chunks with graph metadata"""
        
        enriched_chunks = []
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            
            # Find related nodes and references
            related_ids = []
            graph_refs = []
            toc_lineage = []
            
            # Get chunk node
            chunk_node = self.nodes.get(chunk_id)
            if chunk_node and chunk_node.parent_id:
                parent_node = self.nodes.get(chunk_node.parent_id)
                if parent_node:
                    toc_lineage.append(parent_node.title)
            
            # Find cross-references involving this chunk
            chunk_refs = [ref for ref in self.cross_references if chunk_id in ref.ref_id]
            for ref in chunk_refs:
                graph_refs.append({
                    "ref_id": ref.ref_id,
                    "source": ref.source_element,
                    "target": ref.target_element,
                    "type": ref.ref_type,
                    "confidence": ref.confidence
                })
                
                # Add related elements as related_ids
                if ref.source_element not in related_ids:
                    related_ids.append(ref.source_element)
                if ref.target_element not in related_ids:
                    related_ids.append(ref.target_element)
            
            # Create enriched chunk
            enriched_chunk = chunk.copy()
            enriched_chunk.update({
                "stage": "graph_enriched",
                "graph_refs": graph_refs,
                "toc_lineage": toc_lineage,
                "related_ids": related_ids[:10],  # Limit to 10 related IDs
                "graph_updated_at": time.time()
            })
            
            enriched_chunks.append(enriched_chunk)
        
        return enriched_chunks
    
    def _update_dictionary_with_relations(self) -> int:
        """Update dictionary with aliases and relations from cross-references"""
        
        # Extract unique elements from cross-references
        elements = set()
        relations = []
        
        for ref in self.cross_references:
            elements.add(ref.source_element)
            elements.add(ref.target_element)
            
            relations.append({
                "source": ref.source_element,
                "target": ref.target_element,
                "relationship": ref.ref_type,
                "confidence": ref.confidence
            })
        
        # Create dictionary entries for new elements
        dict_entries = []
        for element in elements:
            # Determine category from element name
            category = "general"
            if any(word in element.lower() for word in ["spell", "magic", "cast"]):
                category = "spells"
            elif element in ["Fighter", "Wizard", "Rogue", "Cleric", "Barbarian", "Ranger", "Paladin", "Sorcerer", "Warlock", "Bard", "Druid", "Monk"]:
                category = "classes"
            elif "feat" in element.lower():
                category = "feats"
            elif any(word in element.lower() for word in ["attack", "combat", "action"]):
                category = "mechanics"
            
            dict_entry = DictEntry(
                term=element,
                definition=f"Game element extracted from cross-reference analysis (category: {category})",
                category=category,
                sources=[{
                    "source": self.job_id,
                    "method": "graph_extraction",
                    "relations": [r for r in relations if r["source"] == element or r["target"] == element][:3]
                }]
            )
            dict_entries.append(dict_entry)
        
        # Upsert dictionary entries
        if dict_entries:
            if self.dict_loader.client is None and ASTRA_REQUIRE_CREDS:
                raise RuntimeError("AstraDB credentials missing; cannot update dictionary in strict mode")
            return self.dict_loader.upsert_entries(dict_entries)
        
        return 0
    
    def _write_graph_snapshot(self, output_dir: Path) -> Path:
        """Write complete graph structure snapshot"""
        
        graph_data = {
            "job_id": self.job_id,
            "pass": "E",
            "created_at": time.time(),
            "graph_summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "cross_references": len(self.cross_references)
            },
            "nodes": {
                node_id: asdict(node) for node_id, node in self.nodes.items()
            },
            "edges": [asdict(edge) for edge in self.edges],
            "cross_references": [asdict(ref) for ref in self.cross_references]
        }
        
        snapshot_path = output_dir / "graph_snapshot.json"
        write_json_atomically(graph_data, snapshot_path)
        
        logger.info(f"Wrote graph snapshot to {snapshot_path}")
        return snapshot_path
    
    def _write_alias_map(self, output_dir: Path) -> Path:
        """Write alias map from cross-references"""
        
        aliases = defaultdict(set)
        
        # Build aliases from cross-references
        for ref in self.cross_references:
            # Bidirectional aliases for high-confidence references
            if ref.confidence >= 0.7:
                aliases[ref.source_element].add(ref.target_element)
                aliases[ref.target_element].add(ref.source_element)
        
        # Convert to serializable format
        alias_map = {
            "job_id": self.job_id,
            "created_at": time.time(),
            "aliases": {
                term: list(alias_set) for term, alias_set in aliases.items()
            }
        }
        
        alias_path = output_dir / "alias_map.json"
        write_json_atomically(alias_map, alias_path)
        
        logger.info(f"Wrote alias map to {alias_path}")
        return alias_path
    
    def _write_relationship_edges(self, output_dir: Path) -> Path:
        """Write relationship edges in JSONL format"""
        
        edges_path = output_dir / "relationship_edges.jsonl"
        
        lines = []
        
        # Add graph edges
        for edge in self.edges:
            edge_data = asdict(edge)
            edge_data["source_type"] = "graph"
            lines.append(json.dumps(edge_data, ensure_ascii=False))
        
        # Add cross-reference edges
        for ref in self.cross_references:
            edge_data = {
                "edge_id": f"xref_{ref.ref_id}",
                "source_id": ref.source_element,
                "target_id": ref.target_element,
                "edge_type": ref.ref_type,
                "weight": ref.confidence,
                "source_type": "cross_reference",
                "metadata": {"context": ref.context}
            }
            lines.append(json.dumps(edge_data, ensure_ascii=False))
        
        content = "\n".join(lines)
        
        # Use atomic write
        temp_path = edges_path.with_suffix('.tmp')
        temp_path.write_text(content, encoding='utf-8')
        temp_path.replace(edges_path)
        
        logger.info(f"Wrote {len(lines)} relationship edges to {edges_path}")
        return edges_path
    
    def _batch_update_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Batch update chunks with graph metadata in AstraDB"""
        
        if not chunks:
            return 0
        
        try:
            if self.astra_loader.client:
                collection = self.astra_loader.client.get_collection(self.astra_loader.collection_name)
                
                # Batch update with retry logic
                batch_size = 30
                updated_count = 0
                
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    try:
                        for chunk in batch:
                            collection.find_one_and_replace(
                                {"chunk_id": chunk["chunk_id"]}, 
                                chunk, 
                                upsert=True
                            )
                        updated_count += len(batch)
                        
                        # Rate limiting
                        if i + batch_size < len(chunks):
                            time.sleep(0.1)
                            
                    except Exception as e:
                        logger.warning(f"Batch update failed for batch {i//batch_size + 1}: {e}")
                
                logger.info(f"Batch updated {updated_count} chunks with graph metadata in AstraDB")
                return updated_count
            else:
                logger.info(f"SIMULATION: Would update {len(chunks)} chunks with graph metadata in AstraDB")
                return len(chunks)
                
        except Exception as e:
            logger.error(f"Failed to batch update chunks in AstraDB: {e}")
            return 0
    
    def _update_manifest(
        self,
        output_dir: Path,
        chunks_processed: int,
        chunks_updated: int,
        graph_nodes: int,
        graph_edges: int,
        cross_references: int,
        dictionary_updates: int,
        artifacts: List[Path]
    ) -> Path:
        """Update manifest.json with Pass E results"""
        
        manifest_path = output_dir / "manifest.json"
        
        # Load existing manifest
        manifest_data = {}
        if manifest_path.exists():
            try:
                manifest_data = load_json_with_retry(manifest_path)
            except Exception as e:
                logger.warning(f"Failed to load existing manifest: {e}")
        
        # Update with Pass E information
        manifest_data.update({
            "completed_passes": list(set(manifest_data.get("completed_passes", []) + ["E"])),
            "chunks": manifest_data.get("chunks", []),  # BUG-016: Ensure chunks key exists
            "pass_e_results": {
                "chunks_processed": chunks_processed,
                "chunks_updated": chunks_updated,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "cross_references": cross_references,
                "dictionary_updates": dictionary_updates,
                "graph_enabled": True,
                "collection_name": self.astra_loader.collection_name,
                "dictionary_collection": self.dict_loader.collection_name
            }
        })
        
        # Add artifacts
        for artifact_path in artifacts:
            if artifact_path.exists():
                manifest_data.setdefault("artifacts", []).append({
                    "file": artifact_path.name,
                    "path": str(artifact_path),
                    "size": artifact_path.stat().st_size,
                    "mtime": artifact_path.stat().st_mtime,
                    "checksum": self._compute_file_hash(artifact_path)
                })
        
        # Write updated manifest
        write_json_atomically(manifest_data, manifest_path)
        
        return manifest_path
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        import hashlib
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def process_pass_e(output_dir: Path, job_id: str, env: str = "dev") -> PassEResult:
    """
    Convenience function for Pass E processing
    
    Args:
        output_dir: Directory containing Pass D artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        
    Returns:
        PassEResult with processing statistics
    """
    builder = PassEGraphBuilder(job_id, env)
    return builder.process_chunks(output_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass E: Graph Building with LlamaIndex")
    parser.add_argument("output_dir", help="Output directory containing Pass D artifacts")
    parser.add_argument("--job-id", required=True, help="Job ID")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    result = process_pass_e(output_dir, args.job_id, args.env)
    
    print(f"Pass E Result:")
    print(f"  Success: {result.success}")
    print(f"  Chunks processed: {result.chunks_processed}")
    print(f"  Chunks updated: {result.chunks_updated}")
    print(f"  Graph nodes: {result.graph_nodes}")
    print(f"  Graph edges: {result.graph_edges}")
    print(f"  Cross-references: {result.cross_references}")
    print(f"  Dictionary updates: {result.dictionary_updates}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)
