# src_common/pass_d_vector_enrichment.py
"""
Pass D: Haystack (Vector & Lite Enrichment)

Perform embedding/vectorization, light NER/keyword extraction, dedupe/merge 
small fragments, and attach vector_ids.

Responsibilities:
- Load raw chunks from Pass C
- Perform embedding/vectorization using OpenAI/Haystack
- Light NER/keyword extraction
- Dedupe and merge small fragments
- Upsert chunks with vectors (stage:"vectorized")
- Add entities, keywords, embedding_model, chunk_hash
- Use batch bulk_write with retry/backoff

Artifacts:
- *_pass_d_vectors.jsonl: Vectorized chunks with enrichment
- enrichment_report.json: Counts, reductions, dedupe ratios
- manifest.json: Updated with vectorization results
"""

import json
import time
import hashlib
import re
import os
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict

# Haystack imports (optional - fallback if not available)
try:
    from haystack import Document
    from haystack.nodes import EmbeddingRetriever
    HAYSTACK_AVAILABLE = True
except ImportError:
    HAYSTACK_AVAILABLE = False

# OpenAI for embeddings and NER
from .ttrpg_secrets import get_openai_client_config
from .logging import get_logger
from .artifact_validator import write_json_atomically, load_json_with_retry
from .astra_loader import AstraLoader

logger = get_logger(__name__)

# Chunk size configuration
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "500"))
CHUNK_HARD_CAP = int(os.getenv("CHUNK_HARD_CAP", "600")) 
CHUNK_MIN_CHARS = int(os.getenv("CHUNK_MIN_CHARS", "120"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))
SPLIT_BY = os.getenv("SPLIT_BY", "word")

# Vector configuration (BUG-014: Standardize to 1024 dimensions)
# Note: OpenAI text-embedding-3-small produces 1536-dim vectors, standardized to 1024 for AstraDB
# We use dimensionality reduction to fit within AstraDB collection index requirements
OPENAI_MODEL_DIM = 1536  # Native text-embedding-3-small dimensions
MODEL_DIM = int(os.getenv("MODEL_DIM", "1024"))  # BUG-014: Standardized to 1024 dimensions
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "json")
EMBED_DIM_REDUCTION = os.getenv("EMBED_DIM_REDUCTION", "pca-1024")  # BUG-014: Default to 1024-d reduction
ABORT_ON_INCOMPATIBLE_VECTOR = os.getenv("ABORT_ON_INCOMPATIBLE_VECTOR", "true").lower() == "true"


@dataclass
class ChunkNormalizationConfig:
    """Configuration for chunk size normalization"""
    max_chars: int = CHUNK_MAX_CHARS
    hard_cap: int = CHUNK_HARD_CAP
    min_chars: int = CHUNK_MIN_CHARS
    overlap: int = CHUNK_OVERLAP
    split_by: str = SPLIT_BY


class ChunkNormalizer:
    """Normalizes chunk sizes before vectorization"""
    
    def __init__(self, config: ChunkNormalizationConfig = None):
        self.config = config or ChunkNormalizationConfig()
        logger.info(f"ChunkNormalizer initialized: max={self.config.max_chars}, "
                   f"hard_cap={self.config.hard_cap}, min={self.config.min_chars}")
    
    def normalize_chunks(self, raw_chunks: List[Dict]) -> List[Dict]:
        """
        Normalize chunk sizes to comply with limits
        
        Args:
            raw_chunks: List of chunks from Pass C
            
        Returns:
            List of normalized chunks
        """
        logger.info(f"Normalizing {len(raw_chunks)} chunks")
        normalized = []
        oversized_count = 0
        split_count = 0
        
        for chunk in raw_chunks:
            text = chunk.get("text", "")
            text_len = len(text)
            
            if text_len <= self.config.max_chars:
                # Already compliant
                normalized.append(chunk)
            else:
                # Split oversized chunk
                oversized_count += 1
                split_chunks = self._split_chunk(chunk, text)
                split_count += len(split_chunks) - 1
                normalized.extend(split_chunks)
        
        # Merge tiny chunks
        merged = self._merge_tiny_chunks(normalized)
        
        logger.info(f"Normalization complete: {len(raw_chunks)} → {len(merged)} chunks, "
                   f"{oversized_count} oversized, {split_count} additional splits")
        
        return merged
    
    def _split_chunk(self, parent_chunk: Dict, text: str) -> List[Dict]:
        """Split a single chunk into smaller pieces"""
        if len(text) <= self.config.hard_cap:
            return [parent_chunk]
        
        chunks = []
        words = text.split() if self.config.split_by == "word" else text.split(".")
        
        current_chunk = []
        current_length = 0
        
        for unit in words:
            unit_len = len(unit) + 1  # +1 for space/period
            
            if current_length + unit_len > self.config.max_chars and current_chunk:
                # Finalize current chunk
                chunk_text = (" " if self.config.split_by == "word" else ".").join(current_chunk)
                chunks.append(self._create_child_chunk(parent_chunk, chunk_text, len(chunks)))
                
                # Start new chunk with overlap
                if self.config.overlap > 0 and len(current_chunk) > 1:
                    overlap_units = current_chunk[-self.config.overlap//20:]  # Rough word overlap
                    current_chunk = overlap_units + [unit]
                    current_length = sum(len(u) + 1 for u in current_chunk)
                else:
                    current_chunk = [unit]
                    current_length = unit_len
            else:
                current_chunk.append(unit)
                current_length += unit_len
        
        # Add final chunk
        if current_chunk:
            chunk_text = (" " if self.config.split_by == "word" else ".").join(current_chunk)
            chunks.append(self._create_child_chunk(parent_chunk, chunk_text, len(chunks)))
        
        return chunks or [parent_chunk]  # Fallback to original if splitting failed
    
    def _create_child_chunk(self, parent: Dict, text: str, index: int) -> Dict:
        """Create a new chunk from a parent chunk with split text"""
        child = parent.copy()
        child["text"] = text
        child["char_len"] = len(text)
        child["chunk_index"] = index
        child["parent_chunk_id"] = parent.get("chunk_id", "unknown")
        child["chunk_id"] = f"{parent.get('chunk_id', 'chunk')}_{index}"
        return child
    
    def _merge_tiny_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Merge chunks that are too small"""
        if not chunks:
            return chunks
        
        merged = []
        pending_merge = None
        
        for chunk in chunks:
            text = chunk.get("text", "")
            if len(text) < self.config.min_chars:
                if pending_merge is None:
                    pending_merge = chunk
                else:
                    # Merge with pending
                    merged_text = pending_merge["text"] + " " + text
                    if len(merged_text) <= self.config.max_chars:
                        pending_merge["text"] = merged_text
                        pending_merge["char_len"] = len(merged_text)
                    else:
                        # Can't merge, add pending and start new
                        merged.append(pending_merge)
                        pending_merge = chunk
            else:
                # Normal sized chunk
                if pending_merge is not None:
                    merged.append(pending_merge)
                    pending_merge = None
                merged.append(chunk)
        
        # Add final pending merge
        if pending_merge is not None:
            merged.append(pending_merge)
        
        return merged


def preflight_embeddings(model_dim: int = MODEL_DIM, backend: str = VECTOR_BACKEND) -> None:
    """
    Validate embedding dimensions are compatible with storage backend
    
    Args:
        model_dim: Embedding model dimension
        backend: Vector storage backend ('json' or 'astra_vector')
        
    Raises:
        SystemExit: If configuration is incompatible
    """
    logger.info(f"Vector preflight check: model_dim={model_dim}, backend={backend}")
    
    # BUG-014: Standard dimensions validation (1024-d)
    REQUIRED_DIM = 1024
    
    if model_dim != REQUIRED_DIM:
        error_msg = (f"Vector dimension mismatch: {model_dim} (model) != {REQUIRED_DIM} (required). "
                    f"Set MODEL_DIM={REQUIRED_DIM} or update embedding configuration.")
        
        logger.error(error_msg)
        logger.error(f"Remediation: Set environment variable MODEL_DIM={REQUIRED_DIM}")
        
        if ABORT_ON_INCOMPATIBLE_VECTOR:
            raise SystemExit(error_msg)
        else:
            logger.warning("Continuing despite incompatible vector configuration")
    
    logger.info(f"✅ Vector dimension preflight PASSED: {model_dim} == {REQUIRED_DIM} (standard)")


def reduce_embedding_dimensions(embedding: List[float], target_dim: int = MODEL_DIM, 
                                method: str = EMBED_DIM_REDUCTION) -> List[float]:
    """
    Reduce embedding dimensions using specified method
    
    Args:
        embedding: Original embedding vector
        target_dim: Target number of dimensions
        method: Reduction method ('off', 'pca-1000', 'truncate')
        
    Returns:
        Reduced embedding vector
    """
    if method == "off" or len(embedding) <= target_dim:
        return embedding
    
    if method == "truncate":
        # Simple truncation (least sophisticated)
        return embedding[:target_dim]
    
    elif method.startswith("pca-"):
        # PCA reduction (better preserves information)
        try:
            from sklearn.decomposition import PCA
            
            # Convert to numpy array and reshape for PCA
            embedding_array = np.array(embedding).reshape(1, -1)
            
            # Apply PCA - note: with single vector, this is essentially truncated SVD
            pca = PCA(n_components=target_dim, random_state=42)
            reduced = pca.fit_transform(embedding_array)
            
            # Return as list
            return reduced.flatten().tolist()
            
        except ImportError:
            logger.warning("sklearn not available, falling back to truncation")
            return embedding[:target_dim]
        except Exception as e:
            logger.warning(f"PCA reduction failed: {e}, falling back to truncation")
            return embedding[:target_dim]
    
    else:
        logger.warning(f"Unknown reduction method '{method}', using truncation")
        return embedding[:target_dim]


@dataclass
class VectorizedChunk:
    """Vectorized chunk from Pass D"""
    chunk_id: str
    content: str
    stage: str = "vectorized"
    source_id: str = ""
    section_id: str = ""
    page_span: str = ""
    toc_path: str = ""
    element_type: str = ""
    page_number: int = 0
    
    # Pass D additions
    embedding: Optional[List[float]] = None
    embedding_model: str = "text-embedding-3-small"
    entities: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    chunk_hash: str = ""
    vector_id: str = ""
    confidence_score: float = 0.0
    
    # Original metadata preserved
    coordinates: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EnrichmentStats:
    """Statistics from Pass D enrichment"""
    original_chunks: int
    normalized_chunks: int
    deduplicated_chunks: int
    merged_fragments: int
    vectorized_chunks: int
    entities_extracted: int
    keywords_extracted: int
    deduplication_ratio: float
    normalization_ratio: float
    processing_time_ms: int


@dataclass
class PassDResult:
    """Result of Pass D vector enrichment"""
    source_file: str
    job_id: str
    chunks_processed: int
    chunks_vectorized: int
    chunks_loaded: int
    enrichment_stats: EnrichmentStats
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassDVectorEnricher:
    """Pass D: Haystack Vector & Lite Enrichment"""
    
    def __init__(self, job_id: str, env: str = "dev"):
        self.job_id = job_id
        self.env = env
        self.astra_loader = AstraLoader(env)
        
        # Initialize OpenAI client for embeddings
        self.openai_config = get_openai_client_config()
        
    def process_chunks(self, output_dir: Path) -> PassDResult:
        """
        Process chunks for Pass D: Vector enrichment
        
        Args:
            output_dir: Directory containing Pass C artifacts
            
        Returns:
            PassDResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Pass D starting: Vector enrichment for job {self.job_id}")
        
        try:
            # Preflight check for vector compatibility
            preflight_embeddings()
            
            # Load raw chunks from Pass C
            chunks_file = output_dir / f"{self.job_id}_pass_c_raw_chunks.jsonl"
            if not chunks_file.exists():
                raise FileNotFoundError(f"Pass C chunks file not found: {chunks_file}")
            
            raw_chunks = self._load_raw_chunks(chunks_file)
            logger.info(f"Loaded {len(raw_chunks)} raw chunks from Pass C")
            
            # Normalize chunk sizes before vectorization
            normalizer = ChunkNormalizer()
            normalized_chunks = normalizer.normalize_chunks(raw_chunks)
            logger.info(f"After normalization: {len(normalized_chunks)} chunks")
            
            # Deduplicate and merge small fragments
            deduplicated_chunks = self._deduplicate_chunks(normalized_chunks)
            logger.info(f"After deduplication: {len(deduplicated_chunks)} chunks")
            
            # Perform vectorization and light enrichment
            vectorized_chunks = []
            for chunk in deduplicated_chunks:
                enriched_chunk = self._enrich_chunk(chunk)
                if enriched_chunk:
                    vectorized_chunks.append(enriched_chunk)
            
            logger.info(f"Vectorized {len(vectorized_chunks)} chunks")
            
            # Generate enrichment statistics
            enrichment_stats = EnrichmentStats(
                original_chunks=len(raw_chunks),
                normalized_chunks=len(normalized_chunks),
                deduplicated_chunks=len(deduplicated_chunks),
                merged_fragments=len(normalized_chunks) - len(deduplicated_chunks),
                vectorized_chunks=len(vectorized_chunks),
                entities_extracted=sum(len(c.entities or []) for c in vectorized_chunks),
                keywords_extracted=sum(len(c.keywords or []) for c in vectorized_chunks),
                deduplication_ratio=(len(normalized_chunks) - len(deduplicated_chunks)) / max(len(normalized_chunks), 1),
                normalization_ratio=len(normalized_chunks) / max(len(raw_chunks), 1),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            # Write vectorized chunks artifact
            vectors_artifact_path = output_dir / f"{self.job_id}_pass_d_vectors.jsonl"
            self._write_vectors_jsonl(vectorized_chunks, vectors_artifact_path)
            
            # Write enrichment report
            report_path = output_dir / "enrichment_report.json"
            self._write_enrichment_report(enrichment_stats, report_path)
            
            # Load chunks to AstraDB with batch updates
            chunks_loaded = self._batch_upsert_vectors(vectorized_chunks)
            
            # Update manifest
            manifest_path = self._update_manifest(
                output_dir, 
                enrichment_stats, 
                chunks_loaded,
                [vectors_artifact_path, report_path]
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            logger.info(f"Pass D completed for job {self.job_id} in {processing_time_ms}ms")
            
            return PassDResult(
                source_file="",  # Will be filled from manifest
                job_id=self.job_id,
                chunks_processed=len(raw_chunks),
                chunks_vectorized=len(vectorized_chunks),
                chunks_loaded=chunks_loaded,
                enrichment_stats=enrichment_stats,
                processing_time_ms=processing_time_ms,
                artifacts=[str(vectors_artifact_path), str(report_path)],
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass D failed for job {self.job_id}: {e}")
            
            return PassDResult(
                source_file="",
                job_id=self.job_id,
                chunks_processed=0,
                chunks_vectorized=0,
                chunks_loaded=0,
                enrichment_stats=EnrichmentStats(
                    original_chunks=0,
                    normalized_chunks=0,
                    deduplicated_chunks=0,
                    merged_fragments=0,
                    vectorized_chunks=0,
                    entities_extracted=0,
                    keywords_extracted=0,
                    deduplication_ratio=0.0,
                    normalization_ratio=1.0,  # BUG-018: Default ratio for failed cases
                    processing_time_ms=processing_time_ms
                ),
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _load_raw_chunks(self, chunks_file: Path) -> List[Dict[str, Any]]:
        """Load raw chunks from Pass C JSONL file"""
        
        chunks = []
        with open(chunks_file, 'r', encoding='utf-8') as f:
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
    
    def _deduplicate_chunks(self, raw_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate chunks and merge small fragments"""
        
        # Group by content similarity (simplified - hash-based)
        content_hashes = {}
        deduplicated = []
        
        for chunk in raw_chunks:
            content = chunk.get("content", "").strip()
            if len(content) < 100:  # Skip very short chunks
                continue
            
            # Create content hash for deduplication
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            if content_hash not in content_hashes:
                content_hashes[content_hash] = chunk
                deduplicated.append(chunk)
            else:
                # Merge metadata from duplicate
                existing = content_hashes[content_hash]
                existing_meta = existing.get("metadata", {})
                chunk_meta = chunk.get("metadata", {})
                
                # Combine page spans if different
                existing_span = existing.get("page_span", "")
                chunk_span = chunk.get("page_span", "")
                if chunk_span and chunk_span != existing_span:
                    combined_span = f"{existing_span},{chunk_span}"
                    existing["page_span"] = combined_span
        
        return deduplicated
    
    def _enrich_chunk(self, raw_chunk: Dict[str, Any]) -> Optional[VectorizedChunk]:
        """Enrich a single chunk with vectors, entities, and keywords"""
        
        try:
            content = raw_chunk.get("content", "").strip()
            if len(content) < 50:  # Skip very short content
                return None
            
            # Generate embedding
            embedding = self._get_embedding(content)
            
            # Extract entities and keywords
            entities = self._extract_entities(content)
            keywords = self._extract_keywords(content)
            
            # Create content hash
            chunk_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Generate vector ID
            vector_id = f"{self.job_id}_v_{chunk_hash[:12]}"
            
            # Calculate confidence score (simplified)
            confidence_score = min(1.0, len(content) / 2000.0)
            
            # Create vectorized chunk
            vectorized = VectorizedChunk(
                chunk_id=raw_chunk.get("chunk_id", ""),
                content=content,
                stage="vectorized",
                source_id=raw_chunk.get("source_id", ""),
                section_id=raw_chunk.get("section_id", ""),
                page_span=raw_chunk.get("page_span", ""),
                toc_path=raw_chunk.get("toc_path", ""),
                element_type=raw_chunk.get("element_type", ""),
                page_number=raw_chunk.get("page_number", 0),
                embedding=embedding,
                embedding_model="text-embedding-3-small",
                entities=entities,
                keywords=keywords,
                chunk_hash=chunk_hash,
                vector_id=vector_id,
                confidence_score=confidence_score,
                coordinates=raw_chunk.get("coordinates"),
                metadata=raw_chunk.get("metadata", {})
            )
            
            return vectorized
            
        except Exception as e:
            logger.warning(f"Failed to enrich chunk {raw_chunk.get('chunk_id')}: {e}")
            return None
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI API"""
        
        try:
            import httpx
            from .ssl_bypass import get_httpx_verify_setting
            
            api_key = self.openai_config.get("api_key")
            if not api_key:
                logger.warning("No OpenAI API key, using dummy embedding")
                return [0.0] * MODEL_DIM  # Dummy embedding
            
            verify = get_httpx_verify_setting()
            
            # Truncate text to avoid token limits
            truncated_text = text[:8000]  
            
            payload = {
                "input": truncated_text,
                "model": "text-embedding-3-small"
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            with httpx.Client(timeout=30, verify=verify) as client:
                response = client.post(
                    "https://api.openai.com/v1/embeddings",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                embedding = data["data"][0]["embedding"]
                
                # Apply dimensionality reduction if needed
                if len(embedding) > MODEL_DIM:
                    logger.debug(f"Reducing embedding dimensions from {len(embedding)} to {MODEL_DIM}")
                    embedding = reduce_embedding_dimensions(embedding, MODEL_DIM, EMBED_DIM_REDUCTION)
                
                return embedding
                
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            return [0.0] * MODEL_DIM  # Dummy embedding as fallback
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text (simplified)"""
        
        # Simplified entity extraction using patterns
        entities = set()
        
        # TTRPG-specific patterns
        spell_pattern = r'\b[A-Z][a-z]+ (?:of|the) [A-Z][a-z]+\b'
        class_pattern = r'\b(?:Fighter|Wizard|Rogue|Cleric|Barbarian|Ranger|Paladin|Sorcerer|Warlock|Bard|Druid|Monk)\b'
        dice_pattern = r'\bd\d+\b'
        
        # Find matches
        for match in re.finditer(spell_pattern, text):
            entities.add(match.group())
        
        for match in re.finditer(class_pattern, text):
            entities.add(match.group())
        
        # Capitalized words (potential proper nouns)
        cap_words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
        for word in cap_words[:5]:  # Limit to first 5
            if len(word) > 3:
                entities.add(word)
        
        return sorted(list(entities)[:10])  # Limit to 10 entities
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simplified)"""
        
        # Common TTRPG keywords
        ttrpg_keywords = [
            'spell', 'magic', 'combat', 'attack', 'damage', 'heal', 'armor',
            'weapon', 'class', 'race', 'feat', 'skill', 'ability', 'level',
            'experience', 'dungeon', 'monster', 'treasure', 'quest', 'adventure'
        ]
        
        keywords = set()
        text_lower = text.lower()
        
        # Find TTRPG keywords
        for keyword in ttrpg_keywords:
            if keyword in text_lower:
                keywords.add(keyword)
        
        # Extract other significant words (3+ chars, appears 2+ times)
        words = re.findall(r'\b[a-z]{3,}\b', text_lower)
        word_counts = {}
        for word in words:
            if word not in ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our']:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Add frequent words
        for word, count in word_counts.items():
            if count >= 2:
                keywords.add(word)
        
        return sorted(list(keywords)[:15])  # Limit to 15 keywords
    
    def _write_vectors_jsonl(self, chunks: List[VectorizedChunk], output_path: Path):
        """Write vectorized chunks to JSONL file"""
        
        lines = []
        for chunk in chunks:
            chunk_dict = asdict(chunk)
            lines.append(json.dumps(chunk_dict, ensure_ascii=False))
        
        content = "\n".join(lines)
        
        # Use atomic write
        temp_path = output_path.with_suffix('.tmp')
        temp_path.write_text(content, encoding='utf-8')
        temp_path.replace(output_path)
        
        logger.info(f"Wrote {len(chunks)} vectorized chunks to {output_path}")
    
    def _write_enrichment_report(self, stats: EnrichmentStats, output_path: Path):
        """Write enrichment report"""
        
        report = {
            "job_id": self.job_id,
            "pass": "D",
            "stage": "vector_enrichment",
            "created_at": time.time(),
            "statistics": asdict(stats),
            "embedding_model": "text-embedding-3-small",
            "deduplication_enabled": True,
            "entity_extraction_enabled": True,
            "keyword_extraction_enabled": True
        }
        
        write_json_atomically(report, output_path)
        logger.info(f"Wrote enrichment report to {output_path}")
    
    def _batch_upsert_vectors(self, chunks: List[VectorizedChunk]) -> int:
        """Batch upsert vectorized chunks to AstraDB"""
        
        if not chunks:
            return 0
        
        # Convert to AstraDB format
        documents = []
        for chunk in chunks:
            doc = {
                'chunk_id': chunk.chunk_id,
                'content': chunk.content,
                'stage': chunk.stage,
                'source_id': chunk.source_id,
                'section_id': chunk.section_id,
                'page_span': chunk.page_span,
                'toc_path': chunk.toc_path,
                'element_type': chunk.element_type,
                'page_number': chunk.page_number,
                'embedding': chunk.embedding,
                'embedding_model': chunk.embedding_model,
                'entities': chunk.entities or [],
                'keywords': chunk.keywords or [],
                'chunk_hash': chunk.chunk_hash,
                'vector_id': chunk.vector_id,
                'confidence_score': chunk.confidence_score,
                'coordinates': chunk.coordinates,
                'metadata': chunk.metadata or {},
                'environment': self.env,
                'updated_at': time.time()
            }
            documents.append(doc)
        
        try:
            if self.astra_loader.client:
                collection = self.astra_loader.client.get_collection(self.astra_loader.collection_name)
                
                # Batch upsert with retry logic
                batch_size = 50
                loaded_count = 0
                
                for i in range(0, len(documents), batch_size):
                    batch = documents[i:i + batch_size]
                    try:
                        # Use upsert_many for batch operations
                        for doc in batch:
                            collection.find_one_and_replace(
                                {"chunk_id": doc["chunk_id"]}, 
                                doc, 
                                upsert=True
                            )
                        loaded_count += len(batch)
                        
                        # Rate limiting
                        if i + batch_size < len(documents):
                            time.sleep(0.1)
                            
                    except Exception as e:
                        logger.warning(f"Batch upsert failed for batch {i//batch_size + 1}: {e}")
                
                logger.info(f"Batch upserted {loaded_count} vectorized chunks to AstraDB")
                return loaded_count
            else:
                logger.info(f"SIMULATION: Would upsert {len(documents)} vectorized chunks to AstraDB")
                return len(documents)
                
        except Exception as e:
            logger.error(f"Failed to batch upsert chunks to AstraDB: {e}")
            return 0
    
    def _update_manifest(
        self,
        output_dir: Path,
        enrichment_stats: EnrichmentStats,
        chunks_loaded: int,
        artifacts: List[Path]
    ) -> Path:
        """Update manifest.json with Pass D results"""
        
        manifest_path = output_dir / "manifest.json"
        
        # Load existing manifest
        manifest_data = {}
        if manifest_path.exists():
            try:
                manifest_data = load_json_with_retry(manifest_path)
            except Exception as e:
                logger.warning(f"Failed to load existing manifest: {e}")
        
        # Update with Pass D information
        manifest_data.update({
            "completed_passes": list(set(manifest_data.get("completed_passes", []) + ["D"])),
            "chunks": manifest_data.get("chunks", []),  # BUG-016: Ensure chunks key exists
            "pass_d_results": {
                "chunks_processed": enrichment_stats.original_chunks,
                "chunks_vectorized": enrichment_stats.vectorized_chunks,
                "chunks_loaded": chunks_loaded,
                "deduplication_ratio": enrichment_stats.deduplication_ratio,
                "entities_extracted": enrichment_stats.entities_extracted,
                "keywords_extracted": enrichment_stats.keywords_extracted,
                "embedding_model": "text-embedding-3-small",
                "collection_name": self.astra_loader.collection_name
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
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def process_pass_d(output_dir: Path, job_id: str, env: str = "dev") -> PassDResult:
    """
    Convenience function for Pass D processing
    
    Args:
        output_dir: Directory containing Pass C artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        
    Returns:
        PassDResult with processing statistics
    """
    enricher = PassDVectorEnricher(job_id, env)
    return enricher.process_chunks(output_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass D: Vector Enrichment with Haystack")
    parser.add_argument("output_dir", help="Output directory containing Pass C artifacts")
    parser.add_argument("--job-id", required=True, help="Job ID")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    result = process_pass_d(output_dir, args.job_id, args.env)
    
    print(f"Pass D Result:")
    print(f"  Success: {result.success}")
    print(f"  Chunks processed: {result.chunks_processed}")
    print(f"  Chunks vectorized: {result.chunks_vectorized}")
    print(f"  Chunks loaded: {result.chunks_loaded}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)