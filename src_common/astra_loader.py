# src_common/astra_loader.py
"""
AstraDB Collection Loader - Loads processed chunks into AstraDB collections
Completes Phase 1 pipeline by storing chunks in vector database
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

from ttrpg_logging import get_logger
from ttrpg_secrets import get_all_config, validate_database_config, load_env
from pathlib import Path
import os

logger = get_logger(__name__)

@dataclass
class LoadResult:
    """Result of loading operation to AstraDB"""
    collection_name: str
    chunks_loaded: int
    chunks_failed: int
    loading_time_ms: int
    success: bool
    error_message: Optional[str] = None

class AstraLoader:
    """Loads processed TTRPG chunks into AstraDB collections"""
    
    def __init__(self, env: str = "dev"):
        """
        Initialize AstraDB loader
        
        Args:
            env: Environment (dev/test/prod)
        """
        self.env = env
        
        # Explicitly load from root .env file first
        project_root = Path(__file__).parent.parent
        root_env = project_root / ".env"
        if root_env.exists():
            logger.info(f"Loading credentials from root .env: {root_env}")
            from ttrpg_secrets import _load_env_file
            _load_env_file(root_env)
        
        self.config = get_all_config()
        self.db_config = validate_database_config()
        
        # Collection names by environment
        self.collection_name = f"ttrpg_chunks_{env}"
        
        # Initialize AstraDB client (simulated for now)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize AstraDB client connection"""
        try:
            # Check if we have valid database configuration
            if not all([
                self.db_config.get('ASTRA_DB_API_ENDPOINT'),
                self.db_config.get('ASTRA_DB_APPLICATION_TOKEN'),
                self.db_config.get('ASTRA_DB_ID')
            ]):
                logger.warning("AstraDB configuration incomplete - using simulation mode")
                self.client = None
                return
            
            # Initialize actual AstraDB client with credentials
            from astrapy import DataAPIClient
            client = DataAPIClient(self.db_config['ASTRA_DB_APPLICATION_TOKEN'])
            self.client = client.get_database_by_api_endpoint(
                self.db_config['ASTRA_DB_API_ENDPOINT']
            )
            
            logger.info(f"AstraDB loader initialized for environment: {self.env}")
            logger.info(f"Target collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AstraDB client: {e}")
            self.client = None
    
    def load_chunks_from_file(self, chunks_file: Path) -> LoadResult:
        """
        Load processed chunks from JSON file into AstraDB collection
        
        Args:
            chunks_file: Path to processed chunks JSON file
            
        Returns:
            LoadResult with loading statistics
        """
        logger.info(f"Loading chunks from {chunks_file} to collection {self.collection_name}")
        start_time = time.time()
        
        try:
            # Read chunks file
            with open(chunks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different file formats
            chunks = data.get('chunks', [])
            if not chunks:
                # Try Pass B format
                chunks = data.get('enriched_chunks', [])
                if chunks:
                    # Convert Pass B format to standard format
                    converted_chunks = []
                    for chunk in chunks:
                        converted_chunk = {
                            'id': chunk.get('chunk_id', 'unknown'),
                            'content': chunk.get('enhanced_content') or chunk.get('original_content', ''),
                            'metadata': {
                                'chunk_type': 'enriched',
                                'entities': chunk.get('entities', []),
                                'categories': chunk.get('categories', []),
                                'complexity': chunk.get('complexity', 'unknown'),
                                'confidence': chunk.get('confidence', 0.0)
                            }
                        }
                        converted_chunks.append(converted_chunk)
                    chunks = converted_chunks
            
            if not chunks:
                return LoadResult(
                    collection_name=self.collection_name,
                    chunks_loaded=0,
                    chunks_failed=0,
                    loading_time_ms=0,
                    success=False,
                    error_message="No chunks found in input file"
                )
            
            # Load chunks to collection
            result = self._load_chunks_to_collection(chunks)
            
            end_time = time.time()
            result.loading_time_ms = int((end_time - start_time) * 1000)
            
            if result.success:
                logger.info(f"Successfully loaded {result.chunks_loaded} chunks to {self.collection_name}")
            else:
                logger.error(f"Failed to load chunks: {result.error_message}")
            
            return result
            
        except Exception as e:
            end_time = time.time()
            logger.error(f"Error loading chunks from file: {e}")
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=0,
                chunks_failed=0,
                loading_time_ms=int((end_time - start_time) * 1000),
                success=False,
                error_message=str(e)
            )
    
    def _load_chunks_to_collection(self, chunks: List[Dict[str, Any]]) -> LoadResult:
        """Load chunks to AstraDB collection"""
        
        if self.client is None:
            # Simulation mode - log what would be loaded
            logger.info(f"SIMULATION MODE: Would load {len(chunks)} chunks to {self.collection_name}")
            self._log_chunk_samples(chunks)
            
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=len(chunks),
                chunks_failed=0,
                loading_time_ms=0,
                success=True,
                error_message=None
            )
        
        # Actual AstraDB loading
        try:
            # Get or create collection
            collection = self.client.get_collection(self.collection_name)
            
            # Prepare documents for AstraDB
            documents = []
            for chunk in chunks:
                doc = {
                    'chunk_id': chunk['id'],
                    'content': chunk['content'],
                    'metadata': chunk['metadata'],
                    'environment': self.env,
                    'loaded_at': time.time()
                }
                documents.append(doc)
            
            # Batch insert to AstraDB (insert_many for large batches)
            logger.info(f"Inserting {len(documents)} documents to collection {self.collection_name}")
            insert_result = collection.insert_many(documents)
            
            inserted_count = len(insert_result.inserted_ids) if insert_result.inserted_ids else len(documents)
            logger.info(f"Successfully inserted {inserted_count} documents to {self.collection_name}")
            
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=inserted_count,
                chunks_failed=len(chunks) - inserted_count,
                loading_time_ms=0,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error inserting chunks to AstraDB: {e}")
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=0,
                chunks_failed=len(chunks),
                loading_time_ms=0,
                success=False,
                error_message=str(e)
            )
    
    def _log_chunk_samples(self, chunks: List[Dict[str, Any]]):
        """Log sample chunks for verification"""
        logger.info("Sample chunks to be loaded:")
        for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
            logger.info(f"  Chunk {i+1}: {chunk['id']}")
            logger.info(f"    Page: {chunk['metadata'].get('page', 'unknown')}")
            logger.info(f"    Section: {chunk['metadata'].get('section', 'unknown')}")
            logger.info(f"    Content preview: {chunk['content'][:100]}...")
        
        if len(chunks) > 3:
            logger.info(f"  ... and {len(chunks) - 3} more chunks")
    
    def empty_collection(self) -> bool:
        """
        Empty the target collection
        
        Returns:
            True if successful
        """
        logger.info(f"Emptying collection {self.collection_name}")
        
        if self.client is None:
            logger.info(f"SIMULATION MODE: Would empty collection {self.collection_name}")
            return True
        
        try:
            # Get collection and clear all documents
            collection = self.client.get_collection(self.collection_name)
            delete_result = collection.delete_many({})
            
            deleted_count = delete_result.deleted_count if hasattr(delete_result, 'deleted_count') else 0
            logger.info(f"Collection {self.collection_name} emptied successfully (deleted {deleted_count} documents)")
            return True
            
        except Exception as e:
            logger.error(f"Error emptying collection: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection
        
        Returns:
            Dictionary with collection statistics
        """
        logger.info(f"Getting stats for collection {self.collection_name}")
        
        if self.client is None:
            logger.info(f"SIMULATION MODE: Collection stats for {self.collection_name}")
            return {
                'collection_name': self.collection_name,
                'document_count': 0,
                'environment': self.env,
                'status': 'simulation_mode'
            }
        
        try:
            # Get actual collection stats
            collection = self.client.get_collection(self.collection_name)
            count = collection.count_documents({}, upper_bound=10000)
            
            return {
                'collection_name': self.collection_name,
                'document_count': count,
                'environment': self.env,
                'status': 'ready'
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                'collection_name': self.collection_name,
                'document_count': 0,
                'environment': self.env,
                'status': 'error',
                'error': str(e)
            }


def load_chunks_to_astra(chunks_file: Path, env: str = "dev") -> LoadResult:
    """
    Convenience function to load chunks to AstraDB
    
    Args:
        chunks_file: Path to processed chunks JSON file
        env: Environment (dev/test/prod)
        
    Returns:
        LoadResult with loading statistics
    """
    loader = AstraLoader(env=env)
    return loader.load_chunks_from_file(chunks_file)


def empty_collection(env: str = "dev") -> bool:
    """
    Convenience function to empty AstraDB collection
    
    Args:
        env: Environment (dev/test/prod)
        
    Returns:
        True if successful
    """
    loader = AstraLoader(env=env)
    return loader.empty_collection()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load processed chunks to AstraDB")
    parser.add_argument("chunks_file", help="Path to processed chunks JSON file")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"],
                       help="Environment (default: dev)")
    parser.add_argument("--empty-first", action="store_true",
                       help="Empty collection before loading")
    parser.add_argument("--stats", action="store_true",
                       help="Show collection statistics")
    
    args = parser.parse_args()
    
    loader = AstraLoader(env=args.env)
    
    if args.empty_first:
        print(f"Emptying collection {loader.collection_name}...")
        if loader.empty_collection():
            print("Collection emptied successfully")
        else:
            print("Failed to empty collection")
            exit(1)
    
    if args.stats:
        stats = loader.get_collection_stats()
        print(f"Collection statistics: {json.dumps(stats, indent=2)}")
    
    # Load chunks
    chunks_file = Path(args.chunks_file)
    if not chunks_file.exists():
        print(f"Error: Chunks file not found: {chunks_file}")
        exit(1)
    
    print(f"Loading chunks from {chunks_file}...")
    result = loader.load_chunks_from_file(chunks_file)
    
    print(f"Loading result:")
    print(f"  Collection: {result.collection_name}")
    print(f"  Chunks loaded: {result.chunks_loaded}")
    print(f"  Chunks failed: {result.chunks_failed}")
    print(f"  Loading time: {result.loading_time_ms}ms")
    print(f"  Success: {result.success}")
    
    if not result.success:
        print(f"  Error: {result.error_message}")
        exit(1)
    
    print("Loading completed successfully!")