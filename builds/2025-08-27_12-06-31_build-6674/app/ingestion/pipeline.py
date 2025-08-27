import logging
import time
import json
import os
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on Windows
    HAS_FCNTL = False
    fcntl = None
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor
import uuid
from contextlib import contextmanager
from enum import Enum

from .pdf_parser import PDFParser
from .dictionary import get_dictionary
from app.common.embeddings import get_embedding_service
from app.common.astra_client import get_vector_store

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Classification of ingestion errors"""
    CRITICAL = "critical"  # Halt all processing, rollback required
    RECOVERABLE = "recoverable"  # Log and continue with other files
    WARNING = "warning"  # Log but continue processing

class IngestionError(Exception):
    """Custom exception for ingestion pipeline errors"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.CRITICAL, rollback_needed: bool = True):
        self.message = message
        self.severity = severity
        self.rollback_needed = rollback_needed
        super().__init__(message)

@contextmanager
def ingestion_lock(env: str = "dev"):
    """Context manager for ingestion concurrency control"""
    lock_dir = Path("./locks")
    lock_dir.mkdir(exist_ok=True)
    lock_file = lock_dir / f"ingestion_{env}.lock"
    
    try:
        with open(lock_file, 'w') as f:
            if os.name == 'nt':  # Windows
                # Use file locking on Windows
                import msvcrt
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    logger.info(f"Acquired ingestion lock for environment: {env}")
                    yield f
                finally:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            elif HAS_FCNTL:  # Unix-like systems
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.info(f"Acquired ingestion lock for environment: {env}")
                    yield f
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:
                # No locking available, proceed with caution
                logger.warning(f"File locking not available on this platform for environment: {env}")
                yield f
    except (IOError, OSError) as e:
        logger.error(f"Could not acquire ingestion lock for {env}: {e}")
        raise RuntimeError(f"Another ingestion process is running for environment {env}")
    finally:
        # Clean up lock file
        try:
            if lock_file.exists():
                lock_file.unlink()
        except:
            pass  # Best effort cleanup

class IngestionPipeline:
    """Three-pass ingestion pipeline for TTRPG materials"""
    
    def __init__(self):
        self.pdf_parser = PDFParser()
        self.dictionary = get_dictionary()
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()
        
    def ingest_file(self, 
                   file_path: str, 
                   metadata: Dict[str, Any],
                   progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Complete three-pass ingestion of a single file
        Returns ingestion manifest
        """
        ingestion_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"Starting ingestion {ingestion_id} for {Path(file_path).name}")
        
        def update_progress(phase: str, step: str, progress: float = 0.0):
            if progress_callback:
                progress_callback({
                    "ingestion_id": ingestion_id,
                    "phase": phase,
                    "step": step,
                    "progress": progress,
                    "timestamp": time.time()
                })
        
        try:
            # PASS A: Parse and Structure
            update_progress("A", "Starting PDF parsing", 0.0)
            pass_a_result = self._pass_a_structure(file_path, metadata, update_progress)
            
            if "error" in pass_a_result:
                return {
                    "ingestion_id": ingestion_id,
                    "status": "failed",
                    "error": pass_a_result["error"],
                    "phase_failed": "A",
                    "duration_seconds": time.time() - start_time
                }
            
            # PASS B: Enrich and Store
            update_progress("B", "Starting enrichment", 33.0)
            pass_b_result = self._pass_b_enrich(pass_a_result["chunks_data"], update_progress)
            
            if "error" in pass_b_result:
                return {
                    "ingestion_id": ingestion_id,
                    "status": "failed", 
                    "error": pass_b_result["error"],
                    "phase_failed": "B",
                    "pass_a_chunks": len(pass_a_result.get("chunks_data", [])),
                    "duration_seconds": time.time() - start_time
                }
            
            # PASS C: Graph Compilation (placeholder)
            update_progress("C", "Starting graph compilation", 66.0)
            pass_c_result = self._pass_c_graph_compile(pass_a_result, pass_b_result, update_progress)
            
            # Final manifest
            update_progress("Complete", "Ingestion finished", 100.0)
            
            manifest = {
                "ingestion_id": ingestion_id,
                "status": "completed",
                "source_id": pass_a_result["source_id"],
                "file_path": file_path,
                "metadata": metadata,
                "pass_a": {
                    "pages_detected": pass_a_result["pages_detected"],
                    "pages_with_text": pass_a_result["pages_with_text"],
                    "chunks_created": len(pass_a_result["chunks_data"])
                },
                "pass_b": {
                    "chunks_enriched": pass_b_result["enriched_count"],
                    "chunks_stored": pass_b_result["stored_count"],
                    "normalized_terms": pass_b_result["total_terms"]
                },
                "pass_c": pass_c_result,
                "duration_seconds": time.time() - start_time,
                "completed_at": time.time()
            }
            
            logger.info(f"Ingestion {ingestion_id} completed in {manifest['duration_seconds']:.2f}s")
            return manifest
            
        except Exception as e:
            logger.error(f"Ingestion {ingestion_id} failed: {e}")
            return {
                "ingestion_id": ingestion_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }
    
    def _pass_a_structure(self, 
                         file_path: str, 
                         metadata: Dict[str, Any],
                         progress_callback: callable) -> Dict[str, Any]:
        """Pass A: Parse PDF to chunks with primary metadata"""
        try:
            progress_callback("A", "Parsing PDF structure", 5.0)
            
            # Parse PDF
            result = self.pdf_parser.parse_pdf(file_path, metadata)
            
            if "error" in result:
                return result
            
            progress_callback("A", "Creating structured chunks", 25.0)
            
            # Add primary metadata to each chunk
            for chunk in result["chunks_data"]:
                chunk["metadata"].update({
                    "title": metadata.get("title", "Unknown"),
                    "publisher": metadata.get("publisher", "Unknown"),
                    "system": metadata.get("system", "Generic"),
                    "copyright_date": metadata.get("copyright_date", "Unknown"),
                    "setting": metadata.get("setting", "Generic"),
                    "isbn": metadata.get("isbn", ""),
                    "ingestion_timestamp": time.time()
                })
            
            progress_callback("A", "Pass A complete", 33.0)
            logger.info(f"Pass A: Created {len(result['chunks_data'])} chunks from {result['pages_detected']} pages")
            
            return result
            
        except Exception as e:
            logger.error(f"Pass A failed: {e}")
            return {"error": str(e)}
    
    def _pass_b_enrich(self, 
                      chunks: List[Dict[str, Any]], 
                      progress_callback: callable) -> Dict[str, Any]:
        """Pass B: Dictionary normalization and secondary metadata"""
        try:
            progress_callback("B", "Enriching with dictionary", 35.0)
            
            # Enrich chunks with normalized terms
            enriched_chunks = self.dictionary.enrich_chunks(chunks)
            
            progress_callback("B", "Generating embeddings", 45.0)
            
            # Generate embeddings in batches
            texts = [chunk["text"] for chunk in enriched_chunks]
            embeddings = self.embedding_service.get_embeddings_batch(texts, batch_size=50)
            
            # Add embeddings to chunks
            for chunk, embedding in zip(enriched_chunks, embeddings):
                chunk["embedding"] = embedding
            
            progress_callback("B", "Storing in vector database", 55.0)
            
            # Store in vector database
            storage_result = self.vector_store.insert_chunks(enriched_chunks)
            
            progress_callback("B", "Pass B complete", 66.0)
            
            # Calculate stats
            total_terms = sum(len(chunk["metadata"].get("normalized_terms", [])) 
                            for chunk in enriched_chunks)
            
            logger.info(f"Pass B: Enriched {len(enriched_chunks)} chunks, stored {storage_result['inserted']}")
            
            return {
                "enriched_count": len(enriched_chunks),
                "stored_count": storage_result["inserted"],
                "total_terms": total_terms,
                "storage_errors": storage_result["errors"]
            }
            
        except Exception as e:
            logger.error(f"Pass B failed: {e}")
            return {"error": str(e)}
    
    def _pass_c_graph_compile(self, 
                             pass_a_result: Dict[str, Any],
                             pass_b_result: Dict[str, Any], 
                             progress_callback: callable) -> Dict[str, Any]:
        """Pass C: Compile/update workflow graphs (placeholder implementation)"""
        try:
            progress_callback("C", "Analyzing content for workflows", 70.0)
            
            # Extract system/edition info
            system = pass_a_result.get("metadata", {}).get("system", "Generic")
            source_id = pass_a_result["source_id"]
            
            progress_callback("C", "Updating workflow graphs", 85.0)
            
            # Placeholder for graph compilation
            # In full implementation, this would:
            # 1. Analyze chunks for workflow-relevant content
            # 2. Update graph nodes with new references
            # 3. Compile workflow definitions
            
            workflows_updated = []
            if "character" in source_id.lower() or "class" in source_id.lower():
                workflows_updated.append("character_creation")
            
            if "combat" in source_id.lower() or "spell" in source_id.lower():
                workflows_updated.append("combat_resolution")
            
            progress_callback("C", "Pass C complete", 100.0)
            
            logger.info(f"Pass C: Updated {len(workflows_updated)} workflow graphs for {system}")
            
            return {
                "system": system,
                "workflows_updated": workflows_updated,
                "graph_nodes_added": len(workflows_updated) * 5,  # Placeholder
                "references_updated": pass_b_result["stored_count"]
            }
            
        except Exception as e:
            logger.error(f"Pass C failed: {e}")
            return {"error": str(e)}
    
    def bulk_ingest(self, 
                   file_list: List[Dict[str, Any]],
                   env: str = "dev",
                   progress_callback: Optional[callable] = None) -> List[Dict[str, Any]]:
        """Ingest multiple files with concurrency control and error handling"""
        results = []
        total_files = len(file_list)
        successful_ingestions = []
        
        try:
            # Acquire ingestion lock for the environment
            with ingestion_lock(env):
                logger.info(f"Starting bulk ingestion of {total_files} files for environment: {env}")
                
                for i, file_info in enumerate(file_list):
                    file_path = file_info["path"]
                    metadata = file_info["metadata"]
                    
                    logger.info(f"Processing file {i+1}/{total_files}: {Path(file_path).name}")
                    
                    # Create per-file progress callback
                    def file_progress_callback(progress_data):
                        progress_data["file_index"] = i
                        progress_data["total_files"] = total_files
                        progress_data["overall_progress"] = ((i + progress_data["progress"]/100.0) / total_files) * 100
                        if progress_callback:
                            progress_callback(progress_data)
                    
                    try:
                        # Ingest file
                        result = self.ingest_file(file_path, metadata, file_progress_callback)
                        results.append(result)
                        
                        # Track successful ingestions for potential rollback
                        if result.get("status") == "completed":
                            successful_ingestions.append(result.get("source_id"))
                        elif result.get("status") == "failed":
                            # Check if this is a critical error that should halt processing
                            error_msg = result.get("error", "Unknown error")
                            if "critical" in error_msg.lower() or "database" in error_msg.lower():
                                raise IngestionError(
                                    f"Critical error in file {file_path}: {error_msg}",
                                    ErrorSeverity.CRITICAL,
                                    rollback_needed=True
                                )
                            else:
                                # Log recoverable error and continue
                                logger.warning(f"Recoverable error in file {file_path}: {error_msg}")
                        
                        # Brief pause between files
                        time.sleep(0.1)
                        
                    except IngestionError as e:
                        if e.severity == ErrorSeverity.CRITICAL:
                            logger.error(f"Critical ingestion error: {e.message}")
                            if e.rollback_needed and successful_ingestions:
                                logger.info(f"Rolling back {len(successful_ingestions)} successful ingestions")
                                self._rollback_ingestions(successful_ingestions)
                            # Add error result and halt processing
                            results.append({
                                "status": "failed",
                                "error": e.message,
                                "severity": e.severity.value,
                                "file_path": file_path
                            })
                            break
                        else:
                            # Log recoverable error and continue
                            logger.warning(f"Recoverable ingestion error: {e.message}")
                            results.append({
                                "status": "failed",
                                "error": e.message,
                                "severity": e.severity.value,
                                "file_path": file_path
                            })
                    
                    except Exception as e:
                        # Unexpected error - treat as recoverable by default
                        logger.error(f"Unexpected error processing {file_path}: {e}")
                        results.append({
                            "status": "failed",
                            "error": str(e),
                            "severity": ErrorSeverity.RECOVERABLE.value,
                            "file_path": file_path
                        })
                
                logger.info(f"Bulk ingestion completed. Processed: {len(results)}, Successful: {len(successful_ingestions)}")
                return results
                
        except RuntimeError as e:
            # Lock acquisition failed
            logger.error(f"Bulk ingestion failed: {e}")
            return [{
                "status": "failed",
                "error": str(e),
                "severity": ErrorSeverity.CRITICAL.value
            }]
    
    def _rollback_ingestions(self, source_ids: List[str]) -> Dict[str, Any]:
        """Rollback multiple ingested sources for error recovery"""
        rollback_results = []
        
        for source_id in source_ids:
            try:
                result = self.remove_source(source_id)
                rollback_results.append(result)
                if result.get("status") != "removed":
                    logger.warning(f"Failed to rollback source {source_id}: {result.get('error')}")
            except Exception as e:
                logger.error(f"Error during rollback of source {source_id}: {e}")
                rollback_results.append({
                    "source_id": source_id,
                    "status": "rollback_failed",
                    "error": str(e)
                })
        
        successful_rollbacks = sum(1 for r in rollback_results if r.get("status") == "removed")
        logger.info(f"Rollback completed: {successful_rollbacks}/{len(source_ids)} sources removed")
        
        return {
            "rollback_attempted": len(source_ids),
            "rollback_successful": successful_rollbacks,
            "results": rollback_results
        }
    
    def remove_source(self, source_id: str) -> Dict[str, Any]:
        """Remove all chunks and references for a source"""
        try:
            # Remove from vector store
            vector_result = self.vector_store.remove_source(source_id)
            
            # TODO: Remove from graph workflows
            
            logger.info(f"Removed source {source_id}: {vector_result['deleted']} chunks deleted")
            
            return {
                "source_id": source_id,
                "status": "removed",
                "chunks_deleted": vector_result.get("deleted", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to remove source {source_id}: {e}")
            return {
                "source_id": source_id,
                "status": "error",
                "error": str(e)
            }

# Global instance
_pipeline = None

def get_pipeline() -> IngestionPipeline:
    """Get global pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestionPipeline()
    return _pipeline