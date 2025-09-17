"""
General MongoDB Service
Provides common MongoDB operations for wireframe editor and other services.
"""

import os
from typing import Any, Dict, List, Optional, Tuple
from pymongo import MongoClient, IndexModel, ASCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
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


class MongoDBService:
    """General MongoDB service for common database operations."""

    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """Initialize MongoDB service."""
        # Use same environment variable as mongo_dictionary_service for consistency
        self.connection_string = connection_string or os.getenv('MONGO_URI') or os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017')
        self.database_name = database_name or os.getenv('MONGODB_DATABASE', 'ttrpg_center')
        self.client = None
        self.db = None

    async def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            if not self.connection_string or self.connection_string == 'mongodb://localhost:27017':
                # Check if we have MONGO_URI set (same as other services)
                if not os.getenv('MONGO_URI'):
                    logger.warning("MONGO_URI not configured, MongoDB service disabled")
                    return False

            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                maxPoolSize=10,
                retryWrites=True
            )
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def _ensure_connected(self):
        """Ensure MongoDB connection is active."""
        if self.db is None:
            success = await self.connect()
            if not success:
                raise RuntimeError("MongoDB connection failed")

    async def list_collections(self) -> List[str]:
        """List all collections in the database."""
        if self.db is None:
            success = await self.connect()
            if not success:
                return []
        return self.db.list_collection_names()

    async def create_index(self, collection_name: str, index_spec: List[Tuple[str, int]], **kwargs) -> str:
        """Create an index on a collection."""
        if self.db is None:
            success = await self.connect()
            if not success:
                raise RuntimeError("MongoDB connection failed")
        collection = self.db[collection_name]
        return collection.create_index(index_spec, **kwargs)

    async def insert_one(self, collection_name: str, document: Dict[str, Any]) -> str:
        """Insert a single document."""
        await self._ensure_connected()
        collection = self.db[collection_name]
        result = collection.insert_one(document)
        return str(result.inserted_id)

    async def insert_document(self, collection_name: str, document: Dict[str, Any]) -> str:
        """Insert a single document (alias for compatibility)."""
        return await self.insert_one(collection_name, document)

    async def insert_many(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple documents."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        result = collection.insert_many(documents)
        return [str(id) for id in result.inserted_ids]

    async def find_one(self, collection_name: str, filter_dict: Dict[str, Any] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Find a single document."""
        await self._ensure_connected()
        collection = self.db[collection_name]
        result = collection.find_one(filter_dict or {}, **kwargs)
        if result and '_id' in result:
            result['_id'] = str(result['_id'])
        return result

    async def find_many(self, collection_name: str, filter_dict: Dict[str, Any] = None,
                       limit: Optional[int] = None, sort: Optional[List[Tuple[str, int]]] = None) -> List[Dict[str, Any]]:
        """Find multiple documents."""
        await self._ensure_connected()
        collection = self.db[collection_name]
        cursor = collection.find(filter_dict or {})

        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)

        results = []
        for doc in cursor:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results

    async def find_documents(self, collection_name: str, filter_dict: Dict[str, Any] = None,
                            limit: Optional[int] = None, sort: Optional[List[Tuple[str, int]]] = None,
                            skip: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find multiple documents with pagination support."""
        await self._ensure_connected()
        collection = self.db[collection_name]
        cursor = collection.find(filter_dict or {})

        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)

        results = []
        for doc in cursor:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results

    async def update_one(self, collection_name: str, filter_dict: Dict[str, Any],
                        update_dict: Dict[str, Any], upsert: bool = False) -> bool:
        """Update a single document."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        result = collection.update_one(filter_dict, {'$set': update_dict}, upsert=upsert)
        return result.modified_count > 0 or result.upserted_id is not None

    async def update_many(self, collection_name: str, filter_dict: Dict[str, Any],
                         update_dict: Dict[str, Any]) -> int:
        """Update multiple documents."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        result = collection.update_many(filter_dict, {'$set': update_dict})
        return result.modified_count

    async def update_document(self, collection_name: str, filter_dict: Dict[str, Any],
                             update_dict: Dict[str, Any], upsert: bool = False) -> bool:
        """Update a single document (alias for compatibility)."""
        return await self.update_one(collection_name, filter_dict, update_dict, upsert)

    async def delete_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> bool:
        """Delete a single document."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        result = collection.delete_one(filter_dict)
        return result.deleted_count > 0

    async def delete_many(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """Delete multiple documents."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        result = collection.delete_many(filter_dict)
        return result.deleted_count

    async def delete_document(self, collection_name: str, filter_dict: Dict[str, Any]) -> bool:
        """Delete a single document (alias for compatibility)."""
        return await self.delete_one(collection_name, filter_dict)

    async def count_documents(self, collection_name: str, filter_dict: Dict[str, Any] = None) -> int:
        """Count documents in a collection."""
        await self._ensure_connected()
        collection = self.db[collection_name]
        return collection.count_documents(filter_dict or {})

    async def aggregate(self, collection_name: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute an aggregation pipeline."""
        if self.db is None:
            await self.connect()
        collection = self.db[collection_name]
        results = []
        for doc in collection.aggregate(pipeline):
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results

    def get_collection(self, collection_name: str) -> Collection:
        """Get a collection object for direct operations."""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]


# Global instance for easy import
mongodb_service = MongoDBService()