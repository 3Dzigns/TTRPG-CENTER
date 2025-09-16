# mongo_dictionary_service.py
"""
FR-006: MongoDB Dictionary Service
Replaces AstraDB-based dictionary storage with containerized MongoDB
"""

import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Union
from collections import defaultdict
from pymongo import MongoClient, IndexModel, ASCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

try:
    from .ttrpg_logging import get_logger
except ImportError:
    # Fallback for direct script execution
    try:
        from ttrpg_logging import get_logger
    except ImportError:
        # Simple fallback logger
        import logging
        def get_logger(name):
            return logging.getLogger(name)

logger = get_logger(__name__)


@dataclass
class DictEntry:
    """Dictionary entry data structure (compatible with existing DictEntry)"""
    term: str
    definition: str
    category: str
    sources: List[Dict[str, Any]]
    
    def to_mongo_doc(self) -> Dict[str, Any]:
        """Convert to MongoDB document format"""
        doc = asdict(self)
        doc['_id'] = self.term.lower()  # Use lowercase term as ID for uniqueness
        doc['term_original'] = self.term  # Preserve original casing
        doc['term_normalized'] = self.term.lower()
        doc['created_at'] = time.time()
        doc['updated_at'] = time.time()
        return doc
    
    @classmethod
    def from_mongo_doc(cls, doc: Dict[str, Any]) -> 'DictEntry':
        """Create DictEntry from MongoDB document"""
        return cls(
            term=doc.get('term_original', doc.get('term', '')),
            definition=doc.get('definition', ''),
            category=doc.get('category', ''),
            sources=doc.get('sources', [])
        )


class MongoDictionaryService:
    """MongoDB-based dictionary service for containerized deployment"""
    
    def __init__(self, env: str = "dev"):
        self.env = env
        self.database_name = f"ttrpg_{env}"
        self.collection_name = "dictionary"
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.collection: Optional[Collection] = None
        
        # Initialize connection
        self._connect()
        
        # Ensure indexes are created
        if self.collection is not None:
            self._ensure_indexes()
    
    def _connect(self) -> None:
        """Establish MongoDB connection"""
        try:
            mongo_uri = os.getenv("MONGO_URI")
            if not mongo_uri:
                logger.warning("MONGO_URI not configured, dictionary service disabled")
                return
            
            # Create MongoDB client with timeout settings
            self.client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                maxPoolSize=10,
                retryWrites=True
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database and collection
            self.database = self.client[self.database_name]
            self.collection = self.database[self.collection_name]
            
            logger.info(f"MongoDB dictionary service connected: {mongo_uri}")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.database = None
            self.collection = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            self.client = None
            self.database = None
            self.collection = None
    
    def _ensure_indexes(self) -> None:
        """Create performance-optimized indexes for ≤1.5s search requirement (FR-015 AC2)"""
        if self.collection is None:
            return

        try:
            indexes = [
                # Primary term lookup index (exact matches) - highest priority
                IndexModel([("_id", ASCENDING)], name="primary_term_lookup"),

                # Normalized term index for case-insensitive prefix matching
                IndexModel([("term_normalized", ASCENDING)], name="term_normalized_index"),

                # Compound text search index with weights for relevance scoring
                IndexModel([
                    ("term_normalized", TEXT),
                    ("definition", TEXT),
                    ("category", TEXT),
                    ("sources.system", TEXT)
                ],
                name="weighted_text_search",
                weights={
                    "term_normalized": 10,  # Highest weight for term matches
                    "definition": 5,        # Medium weight for definition matches
                    "category": 3,          # Lower weight for category matches
                    "sources.system": 2     # Lowest weight for source matches
                }),

                # High-performance category filtering
                IndexModel([("category", ASCENDING)], name="category_index"),

                # Compound index for category + term queries (common pattern)
                IndexModel([
                    ("category", ASCENDING),
                    ("term_normalized", ASCENDING)
                ], name="category_term_compound"),

                # Source system index for source-specific queries
                IndexModel([("sources.system", ASCENDING)], name="source_system_index"),

                # Confidence scoring index for quality-based retrieval
                IndexModel([("confidence_score", -1)], name="confidence_score_index"),

                # Search priority index for ranking
                IndexModel([("search_priority", -1)], name="search_priority_index"),

                # Compound index for search priority + category (performance optimization)
                IndexModel([
                    ("search_priority", -1),
                    ("category", ASCENDING)
                ], name="priority_category_compound"),

                # Updated timestamp for freshness queries and recent updates
                IndexModel([("updated_at", -1)], name="updated_at_desc_index"),

                # Created timestamp for chronological ordering
                IndexModel([("created_at", -1)], name="created_at_desc_index"),

                # Environment-specific index for multi-environment support
                IndexModel([("environment", ASCENDING)], name="environment_index"),

                # Compound index for environment + category (common admin query)
                IndexModel([
                    ("environment", ASCENDING),
                    ("category", ASCENDING)
                ], name="env_category_compound"),

                # Tags array index for tag-based searching
                IndexModel([("tags", ASCENDING)], name="tags_index"),

                # Sparse index for entries with custom cache TTL
                IndexModel([("cache_ttl", ASCENDING)],
                          name="cache_ttl_index", sparse=True),

                # Compound index for complex admin queries (environment + updated + category)
                IndexModel([
                    ("environment", ASCENDING),
                    ("updated_at", -1),
                    ("category", ASCENDING)
                ], name="admin_query_compound")
            ]

            # Create indexes if they don't exist
            self.collection.create_indexes(indexes)
            logger.info("MongoDB dictionary performance indexes created for ≤1.5s search requirement")

            # Verify index creation and log statistics
            index_info = self.collection.list_indexes()
            index_names = [idx.get('name', 'unnamed') for idx in index_info]
            logger.info(f"Active MongoDB indexes: {', '.join(index_names)}")

        except Exception as e:
            logger.error(f"Failed to create MongoDB performance indexes: {e}")
            # Fallback to basic indexes if advanced indexing fails
            try:
                basic_indexes = [
                    IndexModel([("term_normalized", ASCENDING)], name="basic_term_index"),
                    IndexModel([("category", ASCENDING)], name="basic_category_index"),
                    IndexModel([("term_normalized", TEXT), ("definition", TEXT)], name="basic_text_search")
                ]
                self.collection.create_indexes(basic_indexes)
                logger.warning("Created basic MongoDB indexes as fallback")
            except Exception as fallback_error:
                logger.error(f"Failed to create even basic indexes: {fallback_error}")
    
    def upsert_entries(self, entries: List[DictEntry]) -> int:
        """
        Insert or update dictionary entries
        
        Args:
            entries: List of dictionary entries to upsert
            
        Returns:
            Number of entries processed
        """
        if not entries or self.collection is None:
            return 0
        
        try:
            # Deduplicate entries by term (keep last occurrence)
            entries_by_term = {}
            for entry in entries:
                entries_by_term[entry.term.lower()] = entry
            
            upserted_count = 0
            for entry in entries_by_term.values():
                doc = entry.to_mongo_doc()
                
                # Update existing or insert new
                result = self.collection.replace_one(
                    {"_id": doc["_id"]},
                    doc,
                    upsert=True
                )
                
                if result.upserted_id or result.modified_count > 0:
                    upserted_count += 1
            
            logger.info(f"Upserted {upserted_count} dictionary entries to MongoDB")
            return upserted_count
            
        except Exception as e:
            logger.error(f"Failed to upsert dictionary entries: {e}")
            return 0
    
    def search_entries(
        self, 
        query: str, 
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[DictEntry]:
        """
        Search dictionary entries
        
        Args:
            query: Search term
            category: Optional category filter
            limit: Maximum number of results
            
        Returns:
            List of matching dictionary entries
        """
        if self.collection is None:
            return []
        
        try:
            # Build search filter
            search_filter = {}
            
            if query:
                # Use text search for full-text queries
                if len(query.split()) > 1 or not query.isalnum():
                    search_filter["$text"] = {"$search": query}
                else:
                    # Use regex for simple term matching
                    search_filter["term_normalized"] = {
                        "$regex": query.lower(),
                        "$options": "i"
                    }
            
            if category:
                search_filter["category"] = category
            
            # Execute search
            cursor = self.collection.find(search_filter).limit(limit)
            
            # If using text search, sort by score
            if "$text" in search_filter:
                cursor = cursor.sort([("score", {"$meta": "textScore"})])
            else:
                cursor = cursor.sort("term_normalized")
            
            # Convert to DictEntry objects
            entries = []
            for doc in cursor:
                try:
                    entry = DictEntry.from_mongo_doc(doc)
                    entries.append(entry)
                except Exception as e:
                    logger.warning(f"Failed to parse dictionary entry: {e}")
            
            logger.debug(f"Found {len(entries)} dictionary entries for query: {query}")
            return entries
            
        except Exception as e:
            logger.error(f"Failed to search dictionary entries: {e}")
            return []
    
    def get_entry(self, term: str) -> Optional[DictEntry]:
        """
        Get a specific dictionary entry by term
        
        Args:
            term: The term to look up
            
        Returns:
            Dictionary entry if found, None otherwise
        """
        if self.collection is None:
            return None
        
        try:
            doc = self.collection.find_one({"_id": term.lower()})
            if doc:
                return DictEntry.from_mongo_doc(doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get dictionary entry '{term}': {e}")
            return None
    
    def delete_entry(self, term: str) -> bool:
        """
        Delete a dictionary entry
        
        Args:
            term: The term to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if self.collection is None:
            return False
        
        try:
            result = self.collection.delete_one({"_id": term.lower()})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Deleted dictionary entry: {term}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete dictionary entry '{term}': {e}")
            return False
    
    def get_categories(self) -> List[str]:
        """
        Get all available categories
        
        Returns:
            List of category names
        """
        if self.collection is None:
            return []
        
        try:
            categories = self.collection.distinct("category")
            return sorted([cat for cat in categories if cat])
            
        except Exception as e:
            logger.error(f"Failed to get dictionary categories: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get dictionary statistics
        
        Returns:
            Dictionary with statistics
        """
        if self.collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            total_entries = self.collection.count_documents({})
            categories = self.get_categories()
            
            # Category distribution
            category_counts = {}
            for category in categories:
                count = self.collection.count_documents({"category": category})
                category_counts[category] = count
            
            return {
                "total_entries": total_entries,
                "categories": len(categories),
                "category_distribution": category_counts,
                "database": self.database_name,
                "collection": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get dictionary stats: {e}")
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check MongoDB connection health
        
        Returns:
            Health status information
        """
        try:
            if not self.client:
                return {"status": "disconnected", "error": "No MongoDB client"}
            
            # Test connection
            self.client.admin.command('ping')
            
            # Test collection access
            if self.collection is not None:
                count = self.collection.estimated_document_count()
                return {
                    "status": "healthy",
                    "database": self.database_name,
                    "collection": self.collection_name,
                    "estimated_documents": count
                }
            else:
                return {"status": "no_collection", "error": "Collection not available"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def close(self) -> None:
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self.collection = None
            logger.info("MongoDB dictionary service connection closed")


# Global instance for compatibility with existing code
_mongo_dictionary_service: Optional[MongoDictionaryService] = None


def get_dictionary_service() -> MongoDictionaryService:
    """Get or create the global MongoDB dictionary service instance"""
    global _mongo_dictionary_service
    if _mongo_dictionary_service is None:
        env = os.getenv("APP_ENV", "dev")
        _mongo_dictionary_service = MongoDictionaryService(env)
    return _mongo_dictionary_service


def close_dictionary_service():
    """Close the global dictionary service connection"""
    global _mongo_dictionary_service
    if _mongo_dictionary_service:
        _mongo_dictionary_service.close()
        _mongo_dictionary_service = None