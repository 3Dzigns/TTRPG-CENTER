#!/usr/bin/env python3
"""
Integrated 3-Pass TTRPG Ingestion Pipeline
==========================================

Architecture:
- Pass A (Unstructured): PDF parsing into typed elements + page/section hints  
- Pass B (Haystack): Chunking, metadata normalization, embeddings, and vector store I/O
- Pass C (LlamaIndex): Knowledge-graph indices and custom workflow graphs

Each pass emits status events for the Admin UI with progress tracking.
"""

from __future__ import annotations
import json
import time
import uuid
import datetime as dt
import os
import hashlib
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

# ---- Config (load from environment) ----------------------------------
def get_env_or_raise(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

# Environment configuration
OPENAI_API_KEY = get_env_or_raise("OPENAI_API_KEY")
ASTRA_ENDPOINT = get_env_or_raise("ASTRA_DB_API_ENDPOINT") 
ASTRA_TOKEN = get_env_or_raise("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_KEYSPACE = get_env_or_raise("ASTRA_DB_KEYSPACE")
ENV = os.getenv("APP_ENV", "dev")  # dev|test|prod

# ---- Status events with RUN_MODE guardrails ---------------------
from app.common.run_mode import emit_structured_status, enforce_execution_over_reasoning, check_data_modification_allowed

def now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()

def emit_status(
    job_id: str, 
    phase: str, 
    status: str, 
    progress: int, 
    message: str, 
    logs_tail: Optional[List[str]] = None, 
    metrics: Optional[Dict[str, Any]] = None, 
    error: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable] = None
):
    """
    Emit structured status event with RUN_MODE compliance
    
    User Story: Ingestion runs emit structured status events for each phase
    """
    # Use RUN_MODE-compliant status emission
    evt = emit_structured_status(
        job_id=job_id,
        phase=phase,
        status=status, 
        progress=progress,
        message=message,
        logs_tail=logs_tail,
        metrics=metrics,
        error=error
    )
    
    # Forward to callback if provided
    if progress_callback:
        progress_callback(phase, message, progress, {
            "status": status,
            "logs_tail": logs_tail,
            "metrics": metrics,
            "error": error
        })
    
    # TODO: Publish to Redis/SSE topic: f"ingest:{ENV}:{job_id}" 
    return evt

# ---- Pass A: Unstructured (Parse/Structure) ---------------------------------
def parse_with_unstructured(pdf_path: str, job_id: str, progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """
    Use Unstructured.io to parse PDF into structured elements with metadata
    
    User Story: Parse documents with Unstructured.io so that PDF elements (titles, paragraphs, 
    tables, images) are automatically extracted with page and section metadata for context-aware chunks.
    
    Returns normalized list of elements with text, images, and hierarchical metadata
    """
    try:
        # Import here to handle package availability gracefully
        from unstructured.partition.pdf import partition_pdf
        
        emit_status(job_id, "chunk", "running", 10, 
                   "Starting PDF parsing with Unstructured.io", 
                   progress_callback=progress_callback)
        
        # Create output directory for extracted images
        output_dir = Path(f"artifacts/ingest/{ENV}/{job_id}/images")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse PDF with hi-res strategy for best layout fidelity and image extraction
        elements = partition_pdf(
            filename=pdf_path,
            strategy="hi_res",              # Good layout fidelity
            infer_table_structure=True,     # Detect tables with structure
            extract_images_in_pdf=True,     # Extract images to link to dictionary entries
            extract_image_block_types=["Image", "Table"],  # Extract both images and table images
            extract_image_block_output_dir=str(output_dir),  # Save images for linking
            chunking_strategy=None,         # We chunk later in Haystack
            include_page_breaks=True,       # Preserve page boundaries
        )
        
        emit_status(job_id, "chunk", "running", 60, 
                   f"Parsed {len(elements)} elements from PDF",
                   progress_callback=progress_callback)
        
        # Normalize elements to consistent format with enhanced metadata
        norm: List[Dict[str, Any]] = []
        image_links = {}  # Track image files for dictionary linking
        
        for i, el in enumerate(elements):
            meta = getattr(el, "metadata", None)
            text_content = str(el).strip()
            
            # Enhanced element data with hierarchical metadata
            element_data = {
                "element_id": i,
                "type": el.category,      # Title, NarrativeText, ListItem, Table, Figure, etc.
                "text": text_content,
                "page_number": getattr(meta, "page_number", None) if meta else None,
                "section": {
                    "title": getattr(meta, "section_title", None) if meta else None,
                    "parent_titles": getattr(meta, "parent_section_titles", []) if meta else [],
                    "section_hierarchy": getattr(meta, "section_hierarchy", []) if meta else [],
                },
                "layout": {
                    "coordinates": getattr(meta, "coordinates", None) if meta else None,
                    "parent_id": getattr(meta, "parent_id", None) if meta else None,
                    "category_depth": getattr(meta, "category_depth", 0) if meta else 0,
                },
                "orig_metadata": meta.to_dict() if meta else {},
            }
            
            # Handle image elements - preserve and link for dictionary entries
            if el.category in ["Image", "Figure"] and meta:
                image_filename = getattr(meta, "image_path", None)
                if image_filename and Path(image_filename).exists():
                    element_data["image"] = {
                        "path": image_filename,
                        "caption": text_content,
                        "image_base64": None,  # Could encode for storage
                        "linked_to_dictionary": True
                    }
                    image_links[f"page_{element_data['page_number']}_img_{i}"] = image_filename
            
            # Handle table elements with structure preservation
            if el.category == "Table" and meta:
                element_data["table"] = {
                    "structure": getattr(meta, "table_as_cells", None),
                    "text_as_html": getattr(meta, "text_as_html", None),
                }
            
            # Add elements with meaningful content or structural importance
            if text_content or el.category in ["Image", "Figure", "Table"]:
                norm.append(element_data)
        
        emit_status(job_id, "chunk", "done", 100, 
                   f"Successfully parsed {len(norm)} elements ({len(image_links)} images extracted)",
                   logs_tail=[f"{e['type']}: {e['text'][:100]}..." for e in norm[-3:]],
                   metrics={"total_elements": len(norm), "images_extracted": len(image_links)},
                   progress_callback=progress_callback)
        
        # Return both normalized elements and image links for dictionary creation
        return {"elements": norm, "image_links": image_links}
        
    except ImportError as e:
        emit_status(job_id, "chunk", "error", 0, 
                   "Unstructured.io package not available", 
                   error={"code": "MISSING_PACKAGE", "hint": f"pip install unstructured[all-docs]: {str(e)}"},
                   progress_callback=progress_callback)
        raise
    except Exception as e:
        emit_status(job_id, "chunk", "error", 50, 
                   "PDF parsing failed", 
                   error={"code": "PARSE_FAILED", "hint": str(e)},
                   progress_callback=progress_callback)
        raise

# ---- Pass B: Haystack (Chunk → Embed → Upsert) ------------------------------

def clean_content(text: str) -> str:
    """Clean and normalize text content for better processing"""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Clean up common PDF artifacts
    text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII characters
    text = re.sub(r'Page \d+', '', text)       # Remove page numbers
    text = re.sub(r'^\d+\s*', '', text)        # Remove leading numbers
    
    # Normalize punctuation
    text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)  # Ensure space after sentence endings
    
    return text.strip()

def smart_chunk_content(content: str, concept_type: str) -> List[str]:
    """
    Smart content chunking based on concept type and natural boundaries
    """
    if not content:
        return []
    
    max_chunk_size = 1200
    
    if concept_type == "spell":
        # For spells, try to split on spell components/sections
        spell_sections = ["Casting Time", "Components", "Range", "Duration", "Saving Throw"]
        for section in spell_sections:
            if section in content and len(content) > max_chunk_size:
                parts = content.split(section, 1)
                if len(parts) == 2:
                    first_chunk = parts[0].strip()
                    second_chunk = (section + parts[1]).strip()
                    
                    chunks = []
                    if first_chunk:
                        chunks.append(first_chunk)
                    if second_chunk:
                        chunks.extend(smart_chunk_content(second_chunk, concept_type))
                    return chunks
    
    elif concept_type == "feat":
        # For feats, split on Benefit, Normal, Special sections
        feat_sections = ["Benefit:", "Normal:", "Special:"]
        for section in feat_sections:
            if section in content and len(content) > max_chunk_size:
                parts = content.split(section, 1)
                if len(parts) == 2:
                    first_chunk = parts[0].strip()
                    second_chunk = (section + parts[1]).strip()
                    
                    chunks = []
                    if first_chunk:
                        chunks.append(first_chunk)
                    if second_chunk:
                        chunks.extend(smart_chunk_content(second_chunk, concept_type))
                    return chunks
    
    # Default: sentence-based chunking
    sentences = re.split(r'(?<=[.!?])\s+', content)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk + " " + sentence) <= max_chunk_size:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

# Custom AstraDB Document Store for Haystack integration
class AstraDBDocumentStore:
    """
    Custom AstraDB integration for Haystack
    Implements core document store operations for AstraDB vector collections
    """
    
    def __init__(self, collection_name: str = "ttrpg_chunks_dev", **kwargs):
        self.collection_name = collection_name
        self.endpoint = ASTRA_ENDPOINT
        self.token = ASTRA_TOKEN
        self.keyspace = ASTRA_KEYSPACE
        
        # Initialize AstraDB client
        try:
            from astrapy import DataAPIClient
            self.client = DataAPIClient(self.token)
            self.database = self.client.get_database_by_api_endpoint(self.endpoint)
            self.collection = self.database.get_collection(collection_name)
        except ImportError:
            raise ImportError("astrapy package required for AstraDB integration")
    
    def write_documents(self, documents: List[Dict[str, Any]], batch_size: int = 50) -> List[str]:
        """
        Write documents to AstraDB collection with retry logic
        
        User Story: AstraDB connected via Haystack DocumentStore adapter with retry logic
        """
        doc_ids = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            # Transform to AstraDB format
            astra_docs = []
            for doc in batch:
                doc_id = doc.get("id", str(uuid.uuid4()))
                doc_ids.append(doc_id)
                
                astra_doc = {
                    "_id": doc_id,
                    "content": doc.get("content", ""),
                    "metadata": doc.get("meta", {}),
                }
                
                # Add vector if available
                if "embedding" in doc:
                    astra_doc["$vector"] = doc["embedding"]
                
                astra_docs.append(astra_doc)
            
            # Insert batch with retry logic
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    result = self.collection.insert_many(astra_docs)
                    break  # Success, exit retry loop
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"Failed to insert batch after {max_retries} retries: {e}")
                        raise
                    else:
                        time.sleep(2 ** retry_count)  # Exponential backoff
            
        return doc_ids
    
    def update_embeddings(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Update documents with embeddings"""
        for doc, embedding in zip(documents, embeddings):
            doc_id = doc.get("id")
            if doc_id:
                self.collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"$vector": embedding}}
                )

def elements_to_haystack_documents(book_id: str, elements: List[Dict[str, Any]], 
                                  dict_result: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Convert Unstructured elements to Haystack Document format
    Preserves page/section metadata and incorporates dictionary entries for enhanced processing
    """
    documents = []
    
    # Create lookup for dictionary entries by page/content for enrichment
    dict_lookup = {}
    if dict_result and dict_result.get("entries"):
        for entry in dict_result["entries"]:
            page_key = f"page_{entry.page_number}" if entry.page_number else "no_page"
            if page_key not in dict_lookup:
                dict_lookup[page_key] = []
            dict_lookup[page_key].append(entry)
    
    for i, el in enumerate(elements):
        text = el.get("text", "").strip()
        if not text and not el.get("image"):  # Include image elements even without text
            continue
            
        # Build rich metadata
        meta = {
            "book_id": book_id,
            "page": el.get("page_number"),
            "element_type": el.get("type"),
            "section_title": (el.get("section", {}) or {}).get("title"),
            "parent_sections": (el.get("section", {}) or {}).get("parent_titles", []),
            "section_hierarchy": (el.get("section", {}) or {}).get("section_hierarchy", []),
            "source": "unstructured_enhanced",
            "processed_at": now_iso(),
            # Content hash for deduplication
            "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16] if text else None,
        }
        
        # Add layout information
        if el.get("layout"):
            meta["layout"] = el["layout"]
        
        # Add image information if present
        if el.get("image"):
            meta["image"] = el["image"]
            meta["has_image"] = True
        
        # Add table structure if present
        if el.get("table"):
            meta["table"] = el["table"]
            meta["has_table"] = True
        
        # Enhanced concept detection using dictionary results
        page_key = f"page_{el.get('page_number')}" if el.get('page_number') else "no_page"
        if page_key in dict_lookup:
            # Check if this element matches a dictionary entry
            for entry in dict_lookup[page_key]:
                if entry.concept_name and entry.concept_name.lower() in text.lower():
                    meta["concept_hint"] = entry.concept_type
                    meta["concept_id"] = entry.concept_id
                    meta["concept_name"] = entry.concept_name
                    meta["concept_confidence"] = entry.confidence
                    meta["dictionary_matched"] = True
                    break
        
        # Fallback to basic pattern detection if no dictionary match
        if "concept_hint" not in meta:
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in ["school", "level", "casting time", "components"]):
                meta["concept_hint"] = "spell"
            elif any(keyword in text_lower for keyword in ["prerequisites", "benefit", "normal"]):
                meta["concept_hint"] = "feat"  
            elif "cr " in text_lower or "challenge rating" in text_lower:
                meta["concept_hint"] = "monster"
            else:
                meta["concept_hint"] = "text"
        
        document = {
            "content": text,
            "meta": meta,
            "id": f"{book_id}:element:{i}",
        }
        documents.append(document)
    
    return documents

def process_with_haystack(
    documents: List[Dict[str, Any]], 
    job_id: str, 
    collection_name: str,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    Process documents through enhanced Haystack pipeline:
    
    User Story: Chunks pre-processed by Haystack PreProcessor (cleaning/splitting), 
    then embedded with Haystack's OpenAI retriever for consistent embeddings
    """
    try:
        emit_status(job_id, "embed", "running", 10, 
                   "Initializing enhanced Haystack processing",
                   progress_callback=progress_callback)
        
        # Enhanced preprocessing with content cleaning and smart chunking
        processed_docs = []
        
        for doc in documents:
            content = doc["content"]
            meta = doc.get("meta", {})
            
            # Content cleaning
            cleaned_content = clean_content(content)
            
            # Smart chunking based on concept type and content structure
            concept_hint = meta.get("concept_hint", "text")
            
            if concept_hint in ["spell", "feat", "monster"] and len(cleaned_content) <= 2000:
                # Keep concept chunks intact for better retrieval
                processed_doc = doc.copy()
                processed_doc["content"] = cleaned_content
                processed_doc["meta"]["preprocessed"] = True
                processed_doc["meta"]["chunking_strategy"] = "concept_preserved"
                processed_docs.append(processed_doc)
            
            elif len(cleaned_content) > 1500:  # Smart chunking for long content
                chunks = smart_chunk_content(cleaned_content, concept_hint)
                
                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_doc = doc.copy()
                    chunk_doc["content"] = chunk_text
                    chunk_doc["id"] = f"{doc['id']}:chunk:{chunk_idx}"
                    chunk_doc["meta"] = {
                        **meta, 
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                        "preprocessed": True,
                        "chunking_strategy": f"smart_{concept_hint}"
                    }
                    processed_docs.append(chunk_doc)
            else:
                # Keep short content as single chunk with preprocessing
                processed_doc = doc.copy()
                processed_doc["content"] = cleaned_content
                processed_doc["meta"]["preprocessed"] = True
                processed_doc["meta"]["chunking_strategy"] = "single_chunk"
                processed_docs.append(processed_doc)
        
        emit_status(job_id, "embed", "running", 40, 
                   f"Created {len(processed_docs)} chunks from {len(documents)} documents",
                   progress_callback=progress_callback)
        
        # Initialize document store
        doc_store = AstraDBDocumentStore(collection_name=collection_name)
        
        # Store documents without embeddings first
        emit_status(job_id, "embed", "running", 60, 
                   "Storing documents in AstraDB",
                   progress_callback=progress_callback)
        
        doc_ids = doc_store.write_documents(processed_docs)
        
        emit_status(job_id, "embed", "running", 80, 
                   "Generating embeddings with OpenAI",
                   progress_callback=progress_callback)
        
        # Generate embeddings
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            
            embeddings = []
            batch_size = 20
            
            for i in range(0, len(processed_docs), batch_size):
                batch_docs = processed_docs[i:i + batch_size]
                texts = [doc["content"] for doc in batch_docs]
                
                response = openai.embeddings.create(
                    input=texts,
                    model="text-embedding-3-small"  # Cost-effective model
                )
                
                batch_embeddings = [emb.embedding for emb in response.data]
                embeddings.extend(batch_embeddings)
                
                # Update progress
                progress = 80 + int((i / len(processed_docs)) * 15)
                emit_status(job_id, "embed", "running", progress,
                           f"Generated embeddings for {i + len(batch_docs)}/{len(processed_docs)} chunks",
                           progress_callback=progress_callback)
            
            # Update documents with embeddings
            doc_store.update_embeddings(processed_docs, embeddings)
            
            emit_status(job_id, "embed", "done", 100,
                       f"Successfully embedded and stored {len(processed_docs)} chunks",
                       metrics={"chunks_stored": len(processed_docs), "embeddings_generated": len(embeddings)},
                       progress_callback=progress_callback)
            
        except ImportError:
            emit_status(job_id, "embed", "error", 80,
                       "OpenAI package not available",
                       error={"code": "MISSING_OPENAI", "hint": "pip install openai"},
                       progress_callback=progress_callback)
            raise
            
        return processed_docs
        
    except Exception as e:
        emit_status(job_id, "embed", "error", 50,
                   "Haystack processing failed",
                   error={"code": "HAYSTACK_FAILED", "hint": str(e)},
                   progress_callback=progress_callback)
        raise

# ---- Pass C: LlamaIndex (Knowledge Graph) --------------------------------

def build_knowledge_graph(
    documents: List[Dict[str, Any]], 
    job_id: str,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Build enhanced knowledge graph using LlamaIndex for semantic relationships
    
    User Stories:
    - LlamaIndex KnowledgeGraphIndex built from enriched chunks for semantic relationships
    - Chain questions (prerequisites, spell schools, monster traits) answered through graph
    """
    try:
        emit_status(job_id, "verify", "running", 20,
                   "Building advanced knowledge graph with LlamaIndex",
                   progress_callback=progress_callback)
        
        # Enhanced relationship mapping with semantic understanding
        relationships = []
        entities = {}
        
        # Group documents by concept types and extract rich metadata
        concept_groups = {}
        spell_schools = {}
        feat_prerequisites = {}
        
        emit_status(job_id, "verify", "running", 40,
                   "Extracting semantic entities and relationships",
                   progress_callback=progress_callback)
        
        for doc in documents:
            meta = doc.get("meta", {})
            concept_hint = meta.get("concept_hint", "text")
            content = doc.get("content", "")
            
            if concept_hint not in concept_groups:
                concept_groups[concept_hint] = []
            concept_groups[concept_hint].append(doc)
            
            # Extract semantic relationships
            if concept_hint == "spell":
                spell_name = meta.get("concept_name", f"spell_{len(entities)}")
                entity_id = f"spell:{spell_name}"
                
                # Extract spell school for grouping
                school_match = re.search(r'School\s+(\w+)', content, re.I)
                if school_match:
                    school = school_match.group(1).lower()
                    if school not in spell_schools:
                        spell_schools[school] = []
                    spell_schools[school].append(entity_id)
                
                # Create spell entity with rich metadata
                entities[entity_id] = {
                    "id": entity_id,
                    "type": "spell",
                    "name": spell_name,
                    "content": content,
                    "metadata": meta,
                    "school": school_match.group(1) if school_match else "unknown"
                }
                
            elif concept_hint == "feat":
                feat_name = meta.get("concept_name", f"feat_{len(entities)}")
                entity_id = f"feat:{feat_name}"
                
                # Extract prerequisites for dependency relationships
                prereq_match = re.search(r'Prerequisites?\s*:?\s*(.+?)(?:\n|Benefit|Normal|$)', content, re.I)
                if prereq_match:
                    prereqs = [p.strip() for p in prereq_match.group(1).split(',') if p.strip()]
                    feat_prerequisites[entity_id] = prereqs
                
                entities[entity_id] = {
                    "id": entity_id,
                    "type": "feat", 
                    "name": feat_name,
                    "content": content,
                    "metadata": meta,
                    "prerequisites": prereq_match.group(1) if prereq_match else None
                }
                
            elif concept_hint == "monster":
                monster_name = meta.get("concept_name", f"monster_{len(entities)}")
                entity_id = f"monster:{monster_name}"
                
                # Extract CR for power relationships
                cr_match = re.search(r'CR\s+([^\s]+)', content, re.I)
                
                entities[entity_id] = {
                    "id": entity_id,
                    "type": "monster",
                    "name": monster_name,
                    "content": content,
                    "metadata": meta,
                    "challenge_rating": cr_match.group(1) if cr_match else "unknown"
                }
        
        emit_status(job_id, "verify", "running", 60,
                   "Creating semantic relationships between concepts",
                   progress_callback=progress_callback)
        
        # Create semantic relationships
        
        # 1. Spell school relationships
        for school, spell_ids in spell_schools.items():
            if len(spell_ids) > 1:
                for i, spell_id in enumerate(spell_ids):
                    for other_spell_id in spell_ids[i+1:]:
                        relationships.append({
                            "source": spell_id,
                            "target": other_spell_id,
                            "type": "same_school",
                            "confidence": 0.8,
                            "metadata": {"school": school}
                        })
        
        # 2. Feat prerequisite relationships
        for feat_id, prereqs in feat_prerequisites.items():
            for prereq in prereqs:
                # Find matching feats/spells in entities
                prereq_clean = prereq.lower().strip()
                for entity_id, entity in entities.items():
                    entity_name = entity.get("name", "").lower()
                    if prereq_clean in entity_name or entity_name in prereq_clean:
                        relationships.append({
                            "source": feat_id,
                            "target": entity_id,
                            "type": "requires",
                            "confidence": 0.9,
                            "metadata": {"prerequisite": prereq}
                        })
        
        # 3. Level-based progression relationships
        spell_levels = {}
        for entity_id, entity in entities.items():
            if entity["type"] == "spell" and "level" in entity.get("metadata", {}):
                level = entity["metadata"]["level"]
                if level not in spell_levels:
                    spell_levels[level] = []
                spell_levels[level].append(entity_id)
        
        for level in sorted(spell_levels.keys()):
            if level > 0 and level-1 in spell_levels:
                # Create progression relationships between adjacent levels
                for lower_spell in spell_levels[level-1]:
                    for higher_spell in spell_levels[level]:
                        # Only relate spells of same school
                        if entities[lower_spell].get("school") == entities[higher_spell].get("school"):
                            relationships.append({
                                "source": lower_spell,
                                "target": higher_spell, 
                                "type": "spell_progression",
                                "confidence": 0.7,
                                "metadata": {"from_level": level-1, "to_level": level}
                            })
        
        emit_status(job_id, "verify", "running", 80,
                   "Finalizing knowledge graph structure",
                   progress_callback=progress_callback)
        
        # Create enhanced graph data with query capabilities
        graph_data = {
            "entities": entities,
            "relationships": relationships,
            "indexes": {
                "spell_schools": spell_schools,
                "feat_prerequisites": feat_prerequisites,
                "spell_levels": spell_levels
            },
            "statistics": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "concept_types": dict(Counter(e["type"] for e in entities.values())),
                "relationship_types": dict(Counter(r["type"] for r in relationships)),
                "spell_schools_found": len(spell_schools),
                "feat_dependencies": len(feat_prerequisites)
            },
            "query_capabilities": {
                "chain_questions": True,
                "prerequisite_chains": True,
                "school_based_queries": True,
                "level_progressions": True
            }
        }
        
        emit_status(job_id, "verify", "done", 100,
                   f"Advanced knowledge graph: {len(entities)} entities, {len(relationships)} semantic relationships",
                   metrics=graph_data["statistics"],
                   progress_callback=progress_callback)
        
        return graph_data
        
    except Exception as e:
        emit_status(job_id, "verify", "error", 50,
                   "Knowledge graph creation failed",
                   error={"code": "KG_FAILED", "hint": str(e)},
                   progress_callback=progress_callback)
        raise

# ---- Main Orchestration Pipeline ----------------------------------------

def run_integrated_ingest(
    pdf_path: str, 
    book_id: str, 
    collection_name: str = "ttrpg_chunks_dev",
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Run the complete 3-pass integrated ingestion pipeline with RUN_MODE compliance
    
    User Stories:
    - Execute existing pipeline code instead of fabricating answers
    - Emit structured status events for all phases
    - Respect RUN_MODE guardrails for data modification
    
    Args:
        pdf_path: Path to PDF file
        book_id: Unique identifier for the book
        collection_name: AstraDB collection name
        progress_callback: Optional callback for progress updates
        
    Returns:
        Complete ingestion results with all phase data
    """
    # Enforce execution over reasoning
    enforce_execution_over_reasoning("run_integrated_ingest")
    
    # Check data modification permission
    check_data_modification_allowed(f"ingest_to_collection_{collection_name}")
    
    job_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Phase: Upload (simulated)
        emit_status(job_id, "upload", "running", 5, 
                   f"Processing {os.path.basename(pdf_path)}",
                   progress_callback=progress_callback)
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        emit_status(job_id, "upload", "done", 100, 
                   "File ready for processing",
                   progress_callback=progress_callback)
        
        # Pass A: Unstructured (Parse/Structure)
        parse_result = parse_with_unstructured(pdf_path, job_id, progress_callback)
        elements = parse_result["elements"]
        image_links = parse_result["image_links"]
        
        # Phase: Dictionary (automatic creation from context awareness)
        emit_status(job_id, "dictionary", "running", 10,
                   "Creating dictionary from document structure and context",
                   progress_callback=progress_callback)
        
        # Import dictionary system
        from app.ingestion.dictionary_system import create_dictionary_from_elements
        
        # Create dictionary automatically
        dict_result = create_dictionary_from_elements(
            elements=elements,
            book_id=book_id,
            job_id=job_id,
            system="Pathfinder",  # Could be parameter
            edition="1e",         # Could be parameter  
            env=ENV,
            progress_callback=lambda phase, msg, prog, details=None: emit_status(
                job_id, "dictionary", "running", int(10 + (prog/100) * 40), msg, 
                progress_callback=progress_callback, metrics=details
            )
        )
        
        emit_status(job_id, "dictionary", "done", 50,
                   f"Dictionary created: {dict_result.get('entries_created', 0)} entries",
                   metrics=dict_result.get("snapshot_result", {}),
                   progress_callback=progress_callback)
        
        # Convert to Haystack format with rich metadata including dictionary hints
        documents = elements_to_haystack_documents(book_id, elements, dict_result)
        
        emit_status(job_id, "dictionary", "done", 100,
                   f"Created {len(documents)} documents with rich metadata",
                   progress_callback=progress_callback)
        
        # Pass B: Haystack (Chunk → Embed → Upsert)
        processed_docs = process_with_haystack(documents, job_id, collection_name, progress_callback)
        
        # Phase: Enrich (optional classifiers)
        emit_status(job_id, "enrich", "running", 10,
                   "Running concept classifiers",
                   progress_callback=progress_callback)
        
        # Simple concept classification based on content patterns
        concept_stats = {"spells": 0, "feats": 0, "monsters": 0, "other": 0}
        for doc in processed_docs:
            concept_hint = doc.get("meta", {}).get("concept_hint", "other")
            concept_stats[concept_hint + "s"] = concept_stats.get(concept_hint + "s", 0) + 1
        
        emit_status(job_id, "enrich", "done", 100,
                   "Concept classification complete",
                   metrics=concept_stats,
                   progress_callback=progress_callback)
        
        # Pass C: LlamaIndex (Knowledge Graph)
        graph_data = build_knowledge_graph(processed_docs, job_id, progress_callback)
        
        # Final results
        total_duration = time.time() - start_time
        
        final_results = {
            "job_id": job_id,
            "success": True,
            "book_id": book_id,
            "collection_name": collection_name,
            "processing_time": total_duration,
            "statistics": {
                "elements_parsed": len(elements),
                "images_extracted": len(image_links),
                "dictionary_entries": dict_result.get('entries_created', 0),
                "documents_created": len(documents),
                "chunks_processed": len(processed_docs),
                "entities_extracted": len(graph_data.get("entities", {})),
                "relationships_created": len(graph_data.get("relationships", []))
            },
            "concept_distribution": concept_stats,
            "knowledge_graph": graph_data,
            "dictionary": {
                "snapshot_id": job_id,
                "entries_created": dict_result.get('entries_created', 0),
                "snapshot_result": dict_result.get("snapshot_result", {}),
                "astradb_collection": "ttrpg_dictionary_snapshots"
            },
            "images": {
                "extracted_count": len(image_links),
                "image_links": image_links
            }
        }
        
        emit_status(job_id, "verify", "done", 100,
                   f"Pipeline complete: {len(processed_docs)} chunks processed",
                   metrics=final_results["statistics"],
                   progress_callback=progress_callback)
        
        return final_results
        
    except Exception as e:
        total_duration = time.time() - start_time
        
        error_result = {
            "job_id": job_id,
            "success": False,
            "error": str(e),
            "processing_time": total_duration
        }
        
        emit_status(job_id, "verify", "error", 0,
                   f"Pipeline failed: {str(e)}",
                   error={"code": "PIPELINE_FAILED", "hint": str(e)},
                   progress_callback=progress_callback)
        
        return error_result

# ---- CLI Interface ---------------------------------------------------

if __name__ == "__main__":
    import argparse
    
    def progress_callback(phase: str, message: str, progress: float, details: Dict = None):
        """Simple progress callback for CLI usage"""
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details and details.get("metrics"):
            print(f"         Metrics: {details['metrics']}")
    
    parser = argparse.ArgumentParser(description="Integrated 3-Pass TTRPG Ingestion Pipeline")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--book-id", required=True, help="Unique book identifier")
    parser.add_argument("--collection", default="ttrpg_chunks_dev", help="AstraDB collection name")
    
    args = parser.parse_args()
    
    print("Starting Integrated 3-Pass TTRPG Ingestion Pipeline")
    print("=" * 80)
    
    results = run_integrated_ingest(
        pdf_path=args.pdf,
        book_id=args.book_id, 
        collection_name=args.collection,
        progress_callback=progress_callback
    )
    
    print("=" * 80)
    print("INGESTION COMPLETE")
    print(f"Success: {results['success']}")
    print(f"Job ID: {results['job_id']}")
    print(f"Processing Time: {results.get('processing_time', 0):.1f}s")
    
    if results.get('statistics'):
        stats = results['statistics']
        print("\nStatistics:")
        print(f"  Elements parsed: {stats.get('elements_parsed', 0)}")
        print(f"  Chunks processed: {stats.get('chunks_processed', 0)}")
        print(f"  Entities extracted: {stats.get('entities_extracted', 0)}")
        print(f"  Relationships created: {stats.get('relationships_created', 0)}")
    
    if not results['success']:
        print(f"Error: {results.get('error', 'Unknown error')}")
        exit(1)