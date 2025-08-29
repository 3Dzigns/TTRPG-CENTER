#!/usr/bin/env python3
"""
Master 3-Phase TTRPG Ingestion Pipeline
=======================================

Orchestrates the complete 3-phase pipeline following battle-tested architecture:
- Phase 1: Fast chunking & AstraDB storage (SPEED)
- Phase 2: Multi-threaded enrichment (QUALITY) 
- Phase 3: Knowledge graph creation (RELATIONSHIPS)

Each phase is properly separated and can be run independently.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from app.ingestion.phase1_fast_chunking import run_phase1_chunking
from app.ingestion.phase2_enrichment import run_phase2_enrichment  
from app.ingestion.phase3_graph_creation import run_phase3_graph_creation

logger = logging.getLogger(__name__)

class MasterPipeline:
    """Master pipeline controller for all 3 phases"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.results = {
            "phase1": {},
            "phase2": {},
            "phase3": {},
            "overall": {}
        }
    
    def _progress_update(self, phase: str, message: str, progress: float, details: Dict = None):
        """Send progress update"""
        if self.progress_callback:
            self.progress_callback(phase, message, progress, details)
    
    def run_complete_pipeline(self, file_path: str, book_title: str, 
                             system: str = "Pathfinder", edition: str = "1e",
                             collection_name: str = "ttrpg_chunks_dev",
                             enrichment_workers: int = 4,
                             run_phase3: bool = True) -> Dict[str, Any]:
        """
        Run the complete 3-phase pipeline
        
        Args:
            file_path: Path to PDF file
            book_title: Title of the book
            system: TTRPG system name
            edition: System edition  
            collection_name: AstraDB collection name
            enrichment_workers: Number of Phase 2 worker threads
            run_phase3: Whether to run Phase 3 graph creation
            
        Returns:
            Complete pipeline results
        """
        overall_start = time.time()
        
        try:
            logger.info(f"Starting complete 3-phase pipeline for: {book_title}")
            self._progress_update("Master-Start", "Initializing 3-phase pipeline", 0.0, 
                                {"book": book_title, "system": f"{system} {edition}"})
            
            # ===================
            # PHASE 1: Fast Chunking & Storage
            # ===================
            self._progress_update("Master-Phase1", "Starting Phase 1: Fast Chunking", 5.0)
            
            phase1_result = run_phase1_chunking(
                file_path=file_path,
                book_title=book_title,
                system=system,
                edition=edition,
                collection_name=collection_name,
                progress_callback=self._phase1_progress
            )
            
            self.results["phase1"] = phase1_result
            
            if not phase1_result.get("success", False):
                logger.error("Phase 1 failed, aborting pipeline")
                return self._build_final_results(overall_start, "Phase 1 failed")
            
            logger.info(f"Phase 1 complete: {phase1_result['chunks_stored']} chunks stored")
            
            # ===================
            # PHASE 2: Multi-threaded Enrichment  
            # ===================
            self._progress_update("Master-Phase2", "Starting Phase 2: Enrichment", 35.0)
            
            metadata_dict_path = phase1_result["metadata_dict_path"]
            
            phase2_result = run_phase2_enrichment(
                metadata_dict_path=metadata_dict_path,
                collection_name=collection_name,
                max_workers=enrichment_workers,
                progress_callback=self._phase2_progress
            )
            
            self.results["phase2"] = phase2_result
            
            if not phase2_result.get("success", False):
                logger.warning("Phase 2 failed, but Phase 1 data is still available")
                # Continue to Phase 3 with basic chunks if desired
            else:
                logger.info(f"Phase 2 complete: {phase2_result['chunks_enriched']} chunks enriched")
            
            # ===================
            # PHASE 3: Knowledge Graph Creation
            # ===================
            if run_phase3:
                self._progress_update("Master-Phase3", "Starting Phase 3: Graph Creation", 70.0)
                
                session_id = phase1_result.get("session_id")
                
                phase3_result = run_phase3_graph_creation(
                    collection_name=collection_name,
                    session_id=session_id,
                    progress_callback=self._phase3_progress
                )
                
                self.results["phase3"] = phase3_result
                
                if phase3_result.get("success", False):
                    logger.info(f"Phase 3 complete: {phase3_result['relationships_created']} relationships created")
                else:
                    logger.warning("Phase 3 failed, but Phases 1-2 data is available")
            else:
                logger.info("Skipping Phase 3 as requested")
                self.results["phase3"] = {"success": True, "skipped": True}
            
            # ===================
            # Final Results
            # ===================
            return self._build_final_results(overall_start, "success")
            
        except Exception as e:
            logger.error(f"Master pipeline failed: {e}")
            return self._build_final_results(overall_start, f"Pipeline error: {str(e)}")
    
    def _phase1_progress(self, phase: str, message: str, progress: float, details: Dict = None):
        """Forward Phase 1 progress (0-30%)"""
        adjusted_progress = (progress / 100) * 30  # Phase 1 gets 0-30% of total
        self._progress_update(phase, message, adjusted_progress, details)
    
    def _phase2_progress(self, phase: str, message: str, progress: float, details: Dict = None):
        """Forward Phase 2 progress (35-65%)"""
        adjusted_progress = 35 + (progress / 100) * 30  # Phase 2 gets 35-65% of total
        self._progress_update(phase, message, adjusted_progress, details)
    
    def _phase3_progress(self, phase: str, message: str, progress: float, details: Dict = None):
        """Forward Phase 3 progress (70-95%)"""
        adjusted_progress = 70 + (progress / 100) * 25  # Phase 3 gets 70-95% of total
        self._progress_update(phase, message, adjusted_progress, details)
    
    def _build_final_results(self, start_time: float, status: str) -> Dict[str, Any]:
        """Build final pipeline results"""
        total_duration = time.time() - start_time
        
        # Aggregate statistics
        phase1 = self.results.get("phase1", {})
        phase2 = self.results.get("phase2", {})
        phase3 = self.results.get("phase3", {})
        
        overall_success = (
            phase1.get("success", False) and
            phase2.get("success", True) and  # Phase 2 is optional
            phase3.get("success", True)      # Phase 3 is optional
        )
        
        final_results = {
            "pipeline_success": overall_success,
            "status": status,
            "total_duration_seconds": total_duration,
            "session_id": phase1.get("session_id"),
            "collection_name": phase1.get("collection_name"),
            
            # Phase results
            "phase1": phase1,
            "phase2": phase2, 
            "phase3": phase3,
            
            # Aggregated statistics
            "overall": {
                "chunks_stored": phase1.get("chunks_stored", 0),
                "chunks_enriched": phase2.get("chunks_enriched", 0),
                "relationships_created": phase3.get("relationships_created", 0),
                "total_duration": total_duration,
                "phase_durations": {
                    "phase1": phase1.get("duration_seconds", 0),
                    "phase2": phase2.get("duration_seconds", 0),
                    "phase3": phase3.get("duration_seconds", 0)
                }
            }
        }
        
        self._progress_update("Master-Complete", "3-phase pipeline complete", 100.0, 
                            {"success": overall_success, "total_time": f"{total_duration:.1f}s"})
        
        return final_results
    
    def run_phase_individually(self, phase: int, **kwargs) -> Dict[str, Any]:
        """Run an individual phase (for debugging or re-runs)"""
        
        if phase == 1:
            return run_phase1_chunking(progress_callback=self.progress_callback, **kwargs)
        elif phase == 2:
            return run_phase2_enrichment(progress_callback=self.progress_callback, **kwargs)
        elif phase == 3:
            return run_phase3_graph_creation(progress_callback=self.progress_callback, **kwargs)
        else:
            raise ValueError(f"Invalid phase: {phase}. Must be 1, 2, or 3")

# Convenience functions
def run_complete_pipeline(file_path: str, book_title: str, **kwargs) -> Dict[str, Any]:
    """Run the complete 3-phase pipeline with default settings"""
    progress_callback = kwargs.pop("progress_callback", None)
    pipeline = MasterPipeline(progress_callback)
    return pipeline.run_complete_pipeline(file_path, book_title, **kwargs)

def run_phases_1_and_2(file_path: str, book_title: str, **kwargs) -> Dict[str, Any]:
    """Run only Phases 1 and 2 (no graph creation)"""
    kwargs["run_phase3"] = False
    return run_complete_pipeline(file_path, book_title, **kwargs)

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(phase, message, progress, details=None):
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details:
            # Show key details
            if "chunks_so_far" in str(details):
                print(f"         Progress: {details}")
            elif "success" in str(details):
                print(f"         Final: {details}")
    
    pdf_path = "E:/Downloads/A_TTRPG_Tool/Source_Books/Paizo/Pathfinder/Core/Pathfinder RPG - Core Rulebook (6th Printing).pdf"
    
    print("Starting complete 3-phase TTRPG ingestion pipeline...")
    print("=" * 80)
    
    result = run_complete_pipeline(
        file_path=pdf_path,
        book_title="Pathfinder Core Rulebook",
        system="Pathfinder",
        edition="1e",
        collection_name="ttrpg_chunks_dev",
        enrichment_workers=4,
        run_phase3=True,
        progress_callback=progress_callback
    )
    
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print(f"Overall Success: {result['pipeline_success']}")
    print(f"Session ID: {result.get('session_id', 'N/A')}")
    print(f"Total Duration: {result['total_duration_seconds']:.1f}s")
    print()
    print("Phase Results:")
    print(f"  Phase 1 (Chunking): {result['phase1'].get('chunks_stored', 0)} chunks stored")
    print(f"  Phase 2 (Enrichment): {result['phase2'].get('chunks_enriched', 0)} chunks enriched")
    print(f"  Phase 3 (Graphs): {result['phase3'].get('relationships_created', 0)} relationships created")
    
    if result.get('phase1', {}).get('metadata_dict_path'):
        print(f"\nMetadata Dictionary: {result['phase1']['metadata_dict_path']}")
    
    if result.get('phase3', {}).get('graph_file'):
        print(f"Knowledge Graph: {result['phase3']['graph_file']}")