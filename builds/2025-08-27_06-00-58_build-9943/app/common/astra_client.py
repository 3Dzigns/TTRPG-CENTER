import os
import logging
from typing import List, Dict, Any, Optional
from astrapy import DataAPIClient
from astrapy.collection import Collection
import numpy as np

logger = logging.getLogger(__name__)

class AstraVectorStore:
    """AstraDB vector store client for RAG operations"""
    
    def __init__(self):
        self.client = None
        self.database = None
        self.collection = None
        self._initialize()
    
    def _initialize(self):
        """Initialize AstraDB connection"""
        try:
            # Initialize client
            self.client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
            
            # Get database
            endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
            self.database = self.client.get_database_by_api_endpoint(endpoint)
            
            # Get or create environment-specific collection
            env = os.getenv("APP_ENV", "dev").lower()
            collection_name = f"ttrpg_chunks_{env}"
            
            # First, check if collection exists in database
            existing_collections = self.database.list_collection_names()
            
            if collection_name in existing_collections:
                self.collection = self.database.get_collection(collection_name)
                logger.info(f"Found existing collection: {collection_name}")
            else:
                # Create collection if it doesn't exist  
                self.collection = self.database.create_collection(collection_name)
                logger.info(f"Created new collection: {collection_name}")
            
            logger.info(f"AstraDB vector store initialized successfully (collection: {collection_name})")
            
        except Exception as e:
            logger.error(f"Failed to initialize AstraDB: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of AstraDB connection"""
        try:
            if not self.collection:
                return {"status": "error", "message": "Collection not initialized"}
            
            # Test with a simple count operation  
            result = self.collection.count_documents({}, upper_bound=1000)
            logger.info(f"AstraDB health check passed: {result} documents")
            return {
                "status": "connected", 
                "document_count": result,
                "collection_name": self.collection.name
            }
        except Exception as e:
            logger.error(f"AstraDB health check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert document chunks into vector store"""
        try:
            if not chunks:
                return {"inserted": 0, "errors": []}
            
            # Prepare documents for insertion
            documents = []
            for chunk in chunks:
                doc = {
                    "_id": chunk["id"],
                    "text": chunk["text"],
                    "page": chunk["page"],
                    "source_id": chunk["source_id"],
                    "section": chunk.get("section", ""),
                    "subsection": chunk.get("subsection", ""),
                    "$vector": chunk["embedding"]
                }
                # Add all metadata
                doc.update({k: v for k, v in chunk.get("metadata", {}).items()})
                documents.append(doc)
            
            # Insert in batches
            batch_size = 20
            inserted = 0
            errors = []
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                try:
                    result = self.collection.insert_many(batch)
                    inserted += len(result.inserted_ids)
                except Exception as e:
                    errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
            
            logger.info(f"Inserted {inserted} chunks into AstraDB")
            return {"inserted": inserted, "errors": errors}
            
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            return {"inserted": 0, "errors": [str(e)]}
    
    def similarity_search(self, 
                         query_embedding: List[float], 
                         k: int = 6,
                         filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform similarity search"""
        try:
            # Build query
            query = {}
            if filters:
                query.update(filters)
            
            # Perform vector search
            results = self.collection.find(
                query,
                vector=query_embedding,
                limit=k,
                include_similarity=True
            )
            
            # Format results
            formatted_results = []
            for doc in results:
                similarity = doc.get("$similarity", 0.0)
                result = {
                    "id": doc["_id"],
                    "text": doc["text"],
                    "page": doc["page"],
                    "source_id": doc["source_id"],
                    "section": doc.get("section", ""),
                    "subsection": doc.get("subsection", ""),
                    "score": similarity,
                    "metadata": {k: v for k, v in doc.items() 
                               if k not in ["_id", "text", "page", "source_id", "section", "subsection", "$vector", "$similarity"]}
                }
                formatted_results.append(result)
            
            logger.info(f"Retrieved {len(formatted_results)} chunks from similarity search")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    def remove_source(self, source_id: str) -> Dict[str, Any]:
        """Remove all chunks from a specific source"""
        try:
            result = self.collection.delete_many({"source_id": source_id})
            deleted_count = result.deleted_count
            logger.info(f"Removed {deleted_count} chunks for source {source_id}")
            return {"deleted": deleted_count}
        except Exception as e:
            logger.error(f"Failed to remove source {source_id}: {e}")
            return {"deleted": 0, "error": str(e)}
    
    def cleanup_environment_data(self) -> Dict[str, Any]:
        """Clean up all data in current environment's collection"""
        try:
            # Get current environment
            env = os.getenv("APP_ENV", "dev").lower()
            
            # Confirm we're not accidentally cleaning production
            if env == "prod":
                raise ValueError("Cannot cleanup production data without explicit confirmation")
            
            # Delete all documents in the collection
            result = self.collection.delete_many({})
            deleted_count = result.deleted_count
            
            logger.info(f"Cleaned up {deleted_count} chunks from {env} environment")
            return {"deleted": deleted_count, "environment": env}
            
        except Exception as e:
            logger.error(f"Failed to cleanup environment data: {e}")
            return {"deleted": 0, "error": str(e)}
    
    def list_collections(self) -> List[str]:
        """List all collections in the database"""
        try:
            collections = self.database.list_collection_names()
            logger.info(f"Found collections: {collections}")
            return collections
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about current environment's collection"""
        try:
            env = os.getenv("APP_ENV", "dev").lower()
            collection_name = f"ttrpg_chunks_{env}"
            
            # Get document count
            count_result = self.collection.count_documents({}, upper_bound=10000)
            
            return {
                "collection_name": collection_name,
                "environment": env,
                "document_count": count_result,
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"error": str(e)}

# Global instance
_vector_store = None

def get_vector_store() -> AstraVectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = AstraVectorStore()
    return _vector_store