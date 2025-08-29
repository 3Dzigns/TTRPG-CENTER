#!/usr/bin/env python3
"""
Phase 2: Multi-threaded Enrichment Process
==========================================

FOCUS: QUALITY - Add rich metadata to existing chunks in AstraDB
- Read from Phase 1 metadata dictionary
- Multi-threaded processing for speed
- Extract rich metadata (level, school, components, etc.)
- Update chunks in AstraDB in place
- Can be re-run when rules change

This phase enriches the basic chunks from Phase 1 with detailed metadata.
"""

import logging
import json
import time
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from astrapy import DataAPIClient
import os

logger = logging.getLogger(__name__)

class Phase2Enrichment:
    """Phase 2: Multi-threaded enrichment of stored chunks"""
    
    def __init__(self, max_workers: int = 4, progress_callback: Optional[Callable] = None):
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.lock = threading.Lock()
        self.processed_count = 0
        self.total_chunks = 0
        self.errors = []
        
        # Initialize AstraDB client
        self.client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
        endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.database = self.client.get_database_by_api_endpoint(endpoint)
        
    def _progress_update(self, phase: str, message: str, progress: float, details: Dict = None):
        """Send progress update"""
        if self.progress_callback:
            self.progress_callback(phase, message, progress, details)
    
    def _extract_spell_metadata(self, content: str) -> Dict[str, Any]:
        """Extract rich spell metadata from content"""
        metadata = {}
        
        def get_field(field_name: str) -> Optional[str]:
            pattern = rf"{re.escape(field_name)}\s*:?\s*(.+?)(?:\n|$)"
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            return match.group(1).strip() if match else None
        
        # School and level parsing
        school_line = get_field("School")
        if school_line:
            # Parse "School evocation [fire]; Level sorcerer/wizard 3"
            school_match = re.search(r"School\s+(\w+)(?:\s*\[([^\]]+)\])?\s*;?\s*Level\s+(.+)", 
                                   school_line, re.I)
            if school_match:
                metadata["school"] = school_match.group(1)
                if school_match.group(2):
                    metadata["descriptors"] = [d.strip() for d in school_match.group(2).split(',')]
                metadata["level_text"] = school_match.group(3)
                
                # Extract numeric level
                level_match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", metadata["level_text"])
                if level_match:
                    metadata["level"] = int(level_match.group(1))
        
        # Other spell fields
        fields_to_extract = {
            "casting_time": "Casting Time",
            "components": "Components", 
            "range": "Range",
            "area": "Area",
            "effect": "Effect",
            "targets": "Targets",
            "duration": "Duration",
            "saving_throw": "Saving Throw",
            "spell_resistance": "Spell Resistance"
        }
        
        for key, field_name in fields_to_extract.items():
            value = get_field(field_name)
            if value:
                metadata[key] = value
        
        return metadata
    
    def _extract_feat_metadata(self, content: str) -> Dict[str, Any]:
        """Extract rich feat metadata from content"""
        metadata = {}
        
        def get_field(field_name: str) -> Optional[str]:
            pattern = rf"{re.escape(field_name)}\s*:?\s*(.+?)(?:\n|$)"
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            return match.group(1).strip() if match else None
        
        # Extract feat fields
        fields_to_extract = {
            "prerequisites": "Prerequisites",
            "benefit": "Benefit",
            "normal": "Normal", 
            "special": "Special"
        }
        
        for key, field_name in fields_to_extract.items():
            value = get_field(field_name)
            if value:
                metadata[key] = value
        
        # Extract feat type from parentheses in first line
        first_line = content.split('\n')[0] if content else ""
        type_match = re.search(r'\(([^)]+)\)', first_line)
        if type_match:
            metadata["feat_type"] = type_match.group(1)
        
        return metadata
    
    def _extract_monster_metadata(self, content: str) -> Dict[str, Any]:
        """Extract rich monster metadata from content"""
        metadata = {}
        
        def get_field(field_name: str) -> Optional[str]:
            pattern = rf"{re.escape(field_name)}\s*:?\s*(.+?)(?:\n|$)"
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            return match.group(1).strip() if match else None
        
        # Extract CR from first line
        first_line = content.split('\n')[0] if content else ""
        cr_match = re.search(r'CR\s+([\d/]+)', first_line, re.I)
        if cr_match:
            metadata["challenge_rating"] = cr_match.group(1)
        
        # Other monster fields
        fields_to_extract = {
            "alignment": "Alignment",
            "size": "Size",
            "type": "Type",
            "init": "Init",
            "senses": "Senses",
            "ac": "AC",
            "hp": "hp",
            "speed": "Speed"
        }
        
        for key, field_name in fields_to_extract.items():
            value = get_field(field_name)
            if value:
                metadata[key] = value
        
        return metadata
    
    def _enrich_chunk(self, chunk_data: Dict[str, Any], collection) -> Dict[str, Any]:
        """Enrich a single chunk with rich metadata"""
        try:
            concept_id = chunk_data["concept_id"]
            concept_type = chunk_data["concept_type"]
            
            # Find the chunk in AstraDB
            docs = list(collection.find({"metadata.concept_id": concept_id}, limit=1))
            if not docs:
                return {"success": False, "error": f"Chunk {concept_id} not found in database"}
            
            doc = docs[0]
            content = doc.get("content", "")
            current_metadata = doc.get("metadata", {})
            
            # Extract rich metadata based on concept type
            rich_metadata = {}
            if concept_type == "spell":
                rich_metadata = self._extract_spell_metadata(content)
            elif concept_type == "feat":
                rich_metadata = self._extract_feat_metadata(content)
            elif concept_type == "monster":
                rich_metadata = self._extract_monster_metadata(content)
            
            # Merge with existing metadata
            enriched_metadata = {**current_metadata, **rich_metadata}
            enriched_metadata["enrichment_status"] = "completed"
            enriched_metadata["enriched_at"] = datetime.now(timezone.utc).isoformat()
            enriched_metadata["phase2_processed"] = True
            
            # Update chunk in AstraDB
            update_result = collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"metadata": enriched_metadata}}
            )
            
            if update_result.modified_count > 0:
                return {"success": True, "concept_id": concept_id, "fields_added": len(rich_metadata)}
            else:
                return {"success": False, "error": f"Failed to update {concept_id}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error enriching {chunk_data.get('concept_id', 'unknown')}: {str(e)}"}
    
    def _worker_thread(self, chunk_batch: List[Dict], collection, thread_id: int):
        """Worker thread for processing chunks"""
        results = []
        
        for chunk_data in chunk_batch:
            result = self._enrich_chunk(chunk_data, collection)
            results.append(result)
            
            # Update progress
            with self.lock:
                self.processed_count += 1
                progress = (self.processed_count / self.total_chunks) * 100
                
                if result["success"]:
                    self._progress_update("Phase2-Enriching", 
                                        f"Enriched {chunk_data['concept_name'][:30]}...", 
                                        progress,
                                        {"thread": thread_id, "processed": self.processed_count, "total": self.total_chunks})
                else:
                    self.errors.append(result["error"])
                    self._progress_update("Phase2-Enriching", 
                                        f"Error: {result['error'][:50]}...", 
                                        progress,
                                        {"errors": len(self.errors)})
        
        return results
    
    def process_session(self, metadata_dict_path: str, collection_name: str = None) -> Dict[str, Any]:
        """
        Process Phase 1 session for enrichment
        
        Args:
            metadata_dict_path: Path to Phase 1 metadata dictionary
            collection_name: Override collection name if needed
            
        Returns:
            Phase 2 results dictionary
        """
        start_time = time.time()
        
        try:
            # Load metadata dictionary
            self._progress_update("Phase2-Loading", "Loading metadata dictionary", 5.0)
            
            with open(metadata_dict_path, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
            
            session_id = metadata_dict["session_id"]
            collection_name = collection_name or metadata_dict["collection_name"]
            chunks_data = metadata_dict["chunks"]
            self.total_chunks = len(chunks_data)
            
            logger.info(f"Phase 2 starting: Session {session_id}, {self.total_chunks} chunks")
            
            # Get collection
            collection = self.database.get_collection(collection_name)
            
            # Divide chunks into batches for workers
            self._progress_update("Phase2-Setup", "Preparing worker threads", 10.0)
            
            batch_size = max(1, self.total_chunks // self.max_workers)
            chunk_batches = [chunks_data[i:i + batch_size] for i in range(0, self.total_chunks, batch_size)]
            
            # Start multi-threaded processing
            self._progress_update("Phase2-Enriching", "Starting enrichment workers", 15.0)
            
            all_results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit worker tasks
                future_to_thread = {
                    executor.submit(self._worker_thread, batch, collection, i): i 
                    for i, batch in enumerate(chunk_batches)
                }
                
                # Collect results
                for future in as_completed(future_to_thread):
                    thread_results = future.result()
                    all_results.extend(thread_results)
            
            # Calculate statistics
            successful_enrichments = sum(1 for r in all_results if r["success"])
            total_fields_added = sum(r.get("fields_added", 0) for r in all_results if r["success"])
            
            total_duration = time.time() - start_time
            
            # Final results
            results = {
                "session_id": session_id,
                "success": len(self.errors) == 0,
                "chunks_processed": len(all_results),
                "chunks_enriched": successful_enrichments,
                "total_fields_added": total_fields_added,
                "errors": self.errors,
                "duration_seconds": total_duration,
                "chunks_per_second": len(all_results) / total_duration if total_duration > 0 else 0,
                "collection_name": collection_name
            }
            
            self._progress_update("Phase2-Complete", "Phase 2 enrichment complete", 100.0, results)
            
            logger.info(f"Phase 2 complete: {successful_enrichments}/{self.total_chunks} chunks enriched in {total_duration:.1f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - start_time,
                "errors": self.errors
            }

def run_phase2_enrichment(metadata_dict_path: str, collection_name: str = None,
                         max_workers: int = 4, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to run Phase 2 enrichment
    
    Args:
        metadata_dict_path: Path to Phase 1 metadata dictionary
        collection_name: Override collection name if needed  
        max_workers: Number of worker threads
        progress_callback: Progress callback function
        
    Returns:
        Phase 2 results dictionary
    """
    phase2 = Phase2Enrichment(max_workers, progress_callback)
    return phase2.process_session(metadata_dict_path, collection_name)

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(phase, message, progress, details=None):
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details:
            print(f"         Details: {details}")
    
    if len(sys.argv) < 2:
        print("Usage: python phase2_enrichment.py <metadata_dict_path>")
        sys.exit(1)
    
    metadata_dict_path = sys.argv[1]
    
    result = run_phase2_enrichment(
        metadata_dict_path=metadata_dict_path,
        max_workers=4,
        progress_callback=progress_callback
    )
    
    print(f"\nPhase 2 Results:")
    print(f"Success: {result['success']}")
    print(f"Chunks enriched: {result.get('chunks_enriched', 0)}/{result.get('chunks_processed', 0)}")
    print(f"Total fields added: {result.get('total_fields_added', 0)}")
    print(f"Duration: {result.get('duration_seconds', 0):.1f}s")
    if result.get('errors'):
        print(f"Errors: {len(result['errors'])}")
        for error in result['errors'][:3]:
            print(f"  - {error}")