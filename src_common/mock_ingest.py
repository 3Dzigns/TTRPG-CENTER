# src_common/mock_ingest.py
"""
Mock ingestion job for Phase 0 testing.
Simulates the three-pass ingestion pipeline with status updates.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from ttrpg_logging import get_logger, jlog


logger = get_logger(__name__)


async def run_mock_job(job_id: str, websocket_broadcast: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Run a mock ingestion job that simulates the three-pass pipeline.
    
    Args:
        job_id: Unique identifier for the job
        websocket_broadcast: Optional function to broadcast status updates
        
    Returns:
        Job result summary
    """
    env = os.getenv('APP_ENV', 'dev')
    artifacts_dir = Path(f"./artifacts/{env}/{job_id}")
    
    # Create artifacts directory
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize job manifest
    manifest = {
        "job_id": job_id,
        "environment": env,
        "status": "running",
        "started_at": time.time(),
        "phases": {
            "parse_chunk": {"status": "pending", "started_at": None, "completed_at": None},
            "enrich": {"status": "pending", "started_at": None, "completed_at": None},
            "graph_compile": {"status": "pending", "started_at": None, "completed_at": None}
        },
        "artifacts": {},
        "logs": []
    }
    
    def log_and_broadcast(message: str, phase: str, status: str):
        """Log message and broadcast to WebSocket clients."""
        log_entry = {
            "timestamp": time.time(),
            "job_id": job_id,
            "phase": phase,
            "status": status,
            "message": message
        }
        
        manifest["logs"].append(log_entry)
        
        # Structured logging
        logger.info(message, extra={
            'job_id': job_id,
            'phase': phase,
            'status': status,
            'component': 'mock_ingest'
        })
        
        # Legacy jlog for compatibility
        jlog('INFO', message, job_id=job_id, phase=phase, status=status)
        
        # WebSocket broadcast
        if websocket_broadcast:
            asyncio.create_task(websocket_broadcast({
                "type": "ingestion_update",
                "job_id": job_id,
                "phase": phase,
                "status": status,
                "message": message,
                "timestamp": time.time()
            }))
    
    try:
        log_and_broadcast("Starting mock ingestion job", "init", "started")
        
        # Phase 1: Parse/Chunk (Mock unstructured.io)
        phase_name = "parse_chunk"
        manifest["phases"][phase_name]["started_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "running"
        
        log_and_broadcast("Starting PDF parse and chunk phase", phase_name, "running")
        await asyncio.sleep(0.5)  # Simulate processing time
        
        # Create mock output
        chunks_data = {
            "job_id": job_id,
            "phase": "parse_chunk",
            "tool": "unstructured.io",
            "chunks": [
                {
                    "id": "chunk_001",
                    "content": "Character Creation: The first step in any TTRPG adventure...",
                    "metadata": {"page": 1, "section": "Character Creation", "type": "text"}
                },
                {
                    "id": "chunk_002", 
                    "content": "Dice Rolling: The foundation of randomness in tabletop games...",
                    "metadata": {"page": 2, "section": "Game Mechanics", "type": "text"}
                },
                {
                    "id": "chunk_003",
                    "content": "Combat System: Initiative order determines action sequence...",
                    "metadata": {"page": 5, "section": "Combat", "type": "text"}
                }
            ],
            "statistics": {
                "total_chunks": 3,
                "total_pages": 10,
                "processing_time_ms": 500
            }
        }
        
        chunks_file = artifacts_dir / "passA_chunks.json"
        with open(chunks_file, 'w') as f:
            json.dump(chunks_data, f, indent=2)
        
        manifest["artifacts"]["passA_chunks"] = str(chunks_file)
        manifest["phases"][phase_name]["completed_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "completed"
        
        log_and_broadcast(f"Parse/chunk phase completed: {len(chunks_data['chunks'])} chunks created", 
                         phase_name, "completed")
        
        # Phase 2: Enrich (Mock Haystack)
        phase_name = "enrich"
        manifest["phases"][phase_name]["started_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "running"
        
        log_and_broadcast("Starting content enrichment phase", phase_name, "running")
        await asyncio.sleep(0.7)  # Simulate processing time
        
        # Create mock enriched data
        enriched_data = {
            "job_id": job_id,
            "phase": "enrich",
            "tool": "haystack",
            "enriched_chunks": [
                {
                    "chunk_id": "chunk_001",
                    "enhanced_content": "Character Creation: The first step in any TTRPG adventure involves creating a player character (PC) with stats, background, and abilities.",
                    "entities": ["Character Creation", "Player Character", "PC", "stats", "background", "abilities"],
                    "categories": ["gameplay", "character-development"],
                    "complexity": "basic"
                },
                {
                    "chunk_id": "chunk_002",
                    "enhanced_content": "Dice Rolling: The foundation of randomness in tabletop games uses polyhedral dice (d4, d6, d8, d10, d12, d20) for probability distribution.",
                    "entities": ["Dice Rolling", "polyhedral dice", "d20", "probability"],
                    "categories": ["mechanics", "randomness"],
                    "complexity": "intermediate"
                },
                {
                    "chunk_id": "chunk_003", 
                    "enhanced_content": "Combat System: Initiative order determines action sequence in turn-based combat encounters.",
                    "entities": ["Combat System", "Initiative", "turn-based", "encounters"],
                    "categories": ["combat", "mechanics"],
                    "complexity": "advanced"
                }
            ],
            "dictionary_updates": [
                {"term": "Player Character (PC)", "definition": "The character controlled by a player in a TTRPG"},
                {"term": "Initiative", "definition": "The order in which participants act during combat"},
                {"term": "Polyhedral Dice", "definition": "Multi-sided dice used for random number generation"}
            ]
        }
        
        enriched_file = artifacts_dir / "passB_enriched.json"
        with open(enriched_file, 'w') as f:
            json.dump(enriched_data, f, indent=2)
        
        dictionary_file = artifacts_dir / "passB_dictionary_delta.json"
        with open(dictionary_file, 'w') as f:
            json.dump({"updates": enriched_data["dictionary_updates"]}, f, indent=2)
        
        manifest["artifacts"]["passB_enriched"] = str(enriched_file)
        manifest["artifacts"]["passB_dictionary_delta"] = str(dictionary_file)
        manifest["phases"][phase_name]["completed_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "completed"
        
        log_and_broadcast(f"Enrichment phase completed: {len(enriched_data['dictionary_updates'])} dictionary entries added",
                         phase_name, "completed")
        
        # Phase 3: Graph Compile (Mock LlamaIndex)
        phase_name = "graph_compile"
        manifest["phases"][phase_name]["started_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "running"
        
        log_and_broadcast("Starting graph compilation phase", phase_name, "running")
        await asyncio.sleep(0.3)  # Simulate processing time
        
        # Create mock graph data
        graph_data = {
            "job_id": job_id,
            "phase": "graph_compile",
            "tool": "llama_index",
            "nodes": [
                {
                    "id": "node_char_creation",
                    "type": "Concept", 
                    "content": "Character Creation",
                    "chunk_refs": ["chunk_001"]
                },
                {
                    "id": "node_dice_rolling",
                    "type": "Rule",
                    "content": "Dice Rolling Mechanics", 
                    "chunk_refs": ["chunk_002"]
                },
                {
                    "id": "node_combat",
                    "type": "Procedure",
                    "content": "Combat System",
                    "chunk_refs": ["chunk_003"]
                }
            ],
            "edges": [
                {
                    "from": "node_char_creation",
                    "to": "node_dice_rolling", 
                    "type": "depends_on",
                    "weight": 0.8
                },
                {
                    "from": "node_dice_rolling",
                    "to": "node_combat",
                    "type": "part_of",
                    "weight": 0.9
                }
            ],
            "statistics": {
                "total_nodes": 3,
                "total_edges": 2,
                "graph_density": 0.33
            }
        }
        
        graph_file = artifacts_dir / "passC_graph.json"
        with open(graph_file, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        manifest["artifacts"]["passC_graph"] = str(graph_file)
        manifest["phases"][phase_name]["completed_at"] = time.time()
        manifest["phases"][phase_name]["status"] = "completed"
        
        log_and_broadcast(f"Graph compilation completed: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges",
                         phase_name, "completed")
        
        # Finalize job
        manifest["status"] = "completed"
        manifest["completed_at"] = time.time()
        manifest["total_duration_s"] = manifest["completed_at"] - manifest["started_at"]
        
        # Save final manifest
        manifest_file = artifacts_dir / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        log_and_broadcast("Mock ingestion job completed successfully", "finalize", "completed")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "duration_s": manifest["total_duration_s"],
            "artifacts_path": str(artifacts_dir),
            "phases_completed": 3,
            "chunks_created": len(chunks_data["chunks"]),
            "dictionary_entries": len(enriched_data["dictionary_updates"]),
            "graph_nodes": len(graph_data["nodes"])
        }
        
    except Exception as e:
        # Handle job failure
        manifest["status"] = "failed"
        manifest["error"] = str(e)
        manifest["failed_at"] = time.time()
        
        manifest_file = artifacts_dir / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        log_and_broadcast(f"Mock ingestion job failed: {str(e)}", "error", "failed")
        
        logger.error(f"Mock ingestion job {job_id} failed", extra={
            'job_id': job_id,
            'error': str(e),
            'component': 'mock_ingest'
        })
        
        raise


def run_mock_sync(job_id: str = "mock-001") -> Dict[str, Any]:
    """
    Synchronous version of mock job for testing.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job result
    """
    logger.info(f"Starting synchronous mock job: {job_id}")
    
    # Simulate the phases with simple logging
    phases = ["parse_chunk", "enrich", "graph_compile"]
    
    for phase in phases:
        jlog('INFO', f'Mock phase started: {phase}', job_id=job_id, phase=phase, status='running')
        time.sleep(0.1)  # Brief pause
        jlog('INFO', f'Mock phase completed: {phase}', job_id=job_id, phase=phase, status='completed')
    
    result = {
        "job_id": job_id,
        "status": "completed",
        "phases_completed": len(phases),
        "message": "Synchronous mock job completed"
    }
    
    jlog('INFO', 'Mock job completed', job_id=job_id, result=result)
    return result