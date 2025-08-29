#!/usr/bin/env python3
"""
Phase 1: Fast Chunking & AstraDB Storage
=======================================

FOCUS: SPEED - Minimal processing, basic concept identification only
- Extract concept chunks with basic metadata
- Store directly in AstraDB  
- Create metadata dictionary/manifest
- NO rich metadata extraction (that's Phase 2)

This phase should be as fast as possible to get content into the vector store.
"""

import logging
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_astradb import AstraDBVectorStore
from langchain_core.documents import Document
import os

from app.ingestion.concept_chunker import concept_chunk_document

logger = logging.getLogger(__name__)

class Phase1FastChunking:
    """Phase 1: Fast concept chunking and direct AstraDB storage"""
    
    def __init__(self, collection_name: str = "ttrpg_chunks_dev", 
                 progress_callback: Optional[Callable] = None):
        self.collection_name = collection_name
        self.progress_callback = progress_callback
        self.session_id = None
        self.metadata_dict = {}
        
    def _progress_update(self, phase: str, message: str, progress: float, details: Dict = None):
        """Send progress update"""
        if self.progress_callback:
            self.progress_callback(phase, message, progress, details)
    
    def _create_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = int(time.time())
        hash_input = f"{timestamp}_{self.collection_name}"
        hash_obj = hashlib.md5(hash_input.encode())
        return hash_obj.hexdigest()[:8]
    
    def _init_vector_store(self) -> AstraDBVectorStore:
        """Initialize AstraDB vector store"""
        emb = OpenAIEmbeddings(model="text-embedding-3-small")
        
        vs = AstraDBVectorStore(
            collection_name=self.collection_name,
            embedding=emb,
            api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
            token=os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
            namespace=os.getenv("ASTRA_DB_KEYSPACE")
        )
        return vs
    
    def process_document(self, file_path: str, book_title: str, system: str = "Pathfinder",
                        edition: str = "1e", output_dir: str = "phase1_sessions") -> Dict[str, Any]:
        """
        Phase 1: Fast chunking and storage
        
        Returns:
            Dict with session_id, chunks_stored, metadata_dict_path, and statistics
        """
        start_time = time.time()
        
        try:
            # Initialize session
            self.session_id = self._create_session_id()
            session_dir = Path(output_dir) / f"session_{self.session_id}"
            session_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Phase 1 starting: {book_title} -> {self.collection_name}")
            self._progress_update("Phase1-Loading", "Loading PDF document", 5.0)
            
            # Load PDF
            docs = PyMuPDFLoader(file_path).load()
            total_pages = len(docs)
            
            logger.info(f"Loaded {total_pages} pages")
            self._progress_update("Phase1-Loading", f"Loaded {total_pages} pages", 10.0)
            
            # Initialize vector store
            self._progress_update("Phase1-Setup", "Initializing vector store", 15.0)
            vector_store = self._init_vector_store()
            
            # Initialize metadata dictionary
            self.metadata_dict = {
                "session_id": self.session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "phase": 1,
                "book_title": book_title,
                "system": system,
                "edition": edition,
                "source_file": file_path,
                "collection_name": self.collection_name,
                "total_pages": total_pages,
                "chunks": [],
                "statistics": {
                    "pages_processed": 0,
                    "chunks_created": 0,
                    "chunks_stored": 0,
                    "concept_types": {}
                }
            }
            
            all_langchain_docs = []
            chunk_count = 0
            
            # Process pages and create chunks
            for i, doc in enumerate(docs):
                page_num = i + 1
                progress = 20.0 + (i / total_pages) * 60.0  # 20% to 80%
                
                self._progress_update("Phase1-Chunking", 
                                    f"Processing page {page_num}/{total_pages}", 
                                    progress, 
                                    {"chunks_so_far": chunk_count})
                
                # Fast concept chunking (basic metadata only)
                concepts = concept_chunk_document(
                    text=doc.page_content,
                    page_num=page_num,
                    section_title="",  # Could extract from headers if needed
                    system=system,
                    edition=edition,
                    book=book_title
                )
                
                # Convert to LangChain documents with minimal metadata
                for concept in concepts:
                    # Basic metadata only - NO rich extraction
                    basic_metadata = {
                        "session_id": self.session_id,
                        "concept_type": concept.concept_type,
                        "concept_name": concept.concept_name,
                        "concept_id": concept.concept_id,
                        "page": page_num,
                        "system": system,
                        "edition": edition,
                        "book": book_title,
                        "char_count": concept.char_count,
                        "phase1_processed": True,
                        "enrichment_status": "pending"
                    }
                    
                    # Create LangChain document
                    langchain_doc = Document(
                        page_content=concept.content,
                        metadata=basic_metadata
                    )
                    all_langchain_docs.append(langchain_doc)
                    
                    # Add to metadata dictionary
                    self.metadata_dict["chunks"].append({
                        "chunk_index": chunk_count,
                        "concept_id": concept.concept_id,
                        "concept_name": concept.concept_name,
                        "concept_type": concept.concept_type,
                        "page": page_num,
                        "char_count": concept.char_count
                    })
                    
                    chunk_count += 1
                    
                    # Update concept type statistics
                    concept_type = concept.concept_type
                    if concept_type not in self.metadata_dict["statistics"]["concept_types"]:
                        self.metadata_dict["statistics"]["concept_types"][concept_type] = 0
                    self.metadata_dict["statistics"]["concept_types"][concept_type] += 1
                
                self.metadata_dict["statistics"]["pages_processed"] = page_num
                self.metadata_dict["statistics"]["chunks_created"] = chunk_count
            
            # Store all chunks in AstraDB (batch processing)
            self._progress_update("Phase1-Storage", "Storing chunks in AstraDB", 85.0, 
                                {"total_chunks": len(all_langchain_docs)})
            
            logger.info(f"Storing {len(all_langchain_docs)} chunks in AstraDB")
            
            # Batch store with size limits
            BATCH_SIZE = 50
            stored_ids = []
            
            for i in range(0, len(all_langchain_docs), BATCH_SIZE):
                batch = all_langchain_docs[i:i + BATCH_SIZE]
                batch_progress = 85.0 + (i / len(all_langchain_docs)) * 10.0
                
                self._progress_update("Phase1-Storage", 
                                    f"Storing batch {i//BATCH_SIZE + 1}", 
                                    batch_progress)
                
                batch_ids = vector_store.add_documents(batch)
                stored_ids.extend(batch_ids)
            
            self.metadata_dict["statistics"]["chunks_stored"] = len(stored_ids)
            
            # Save metadata dictionary
            metadata_path = session_dir / "metadata_dict.json"
            self._progress_update("Phase1-Finalize", "Saving metadata dictionary", 95.0)
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata_dict, f, indent=2, ensure_ascii=False)
            
            total_duration = time.time() - start_time
            
            # Final statistics
            final_stats = {
                "session_id": self.session_id,
                "success": True,
                "chunks_stored": len(stored_ids),
                "pages_processed": total_pages,
                "duration_seconds": total_duration,
                "chunks_per_second": len(stored_ids) / total_duration if total_duration > 0 else 0,
                "metadata_dict_path": str(metadata_path),
                "collection_name": self.collection_name,
                "concept_distribution": self.metadata_dict["statistics"]["concept_types"]
            }
            
            self._progress_update("Phase1-Complete", "Phase 1 complete", 100.0, final_stats)
            
            logger.info(f"Phase 1 complete: {len(stored_ids)} chunks stored in {total_duration:.1f}s")
            
            return final_stats
            
        except Exception as e:
            logger.error(f"Phase 1 failed: {e}")
            return {
                "session_id": self.session_id,
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }

def run_phase1_chunking(file_path: str, book_title: str, system: str = "Pathfinder",
                       edition: str = "1e", collection_name: str = "ttrpg_chunks_dev",
                       progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to run Phase 1 chunking
    
    Args:
        file_path: Path to PDF file
        book_title: Title of the book
        system: TTRPG system name
        edition: System edition
        collection_name: AstraDB collection name
        progress_callback: Progress callback function
        
    Returns:
        Phase 1 results dictionary
    """
    phase1 = Phase1FastChunking(collection_name, progress_callback)
    return phase1.process_document(file_path, book_title, system, edition)

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(phase, message, progress, details=None):
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details:
            print(f"         Details: {details}")
    
    pdf_path = "E:/Downloads/A_TTRPG_Tool/Source_Books/Paizo/Pathfinder/Core/Pathfinder RPG - Core Rulebook (6th Printing).pdf"
    
    result = run_phase1_chunking(
        file_path=pdf_path,
        book_title="Pathfinder Core Rulebook",
        system="Pathfinder",
        edition="1e",
        progress_callback=progress_callback
    )
    
    print(f"\nPhase 1 Results:")
    print(f"Success: {result['success']}")
    print(f"Chunks stored: {result.get('chunks_stored', 0)}")
    print(f"Session ID: {result.get('session_id', 'N/A')}")
    print(f"Metadata dictionary: {result.get('metadata_dict_path', 'N/A')}")