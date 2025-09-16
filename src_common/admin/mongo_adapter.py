# src_common/admin/mongo_adapter.py
"""
MongoDB Adapter for AdminDictionaryService - FR-015
Bridges AdminDictionaryService and MongoDictionaryService for seamless MongoDB integration
with circuit breaker pattern for resilient error handling.
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import asdict

from .dictionary_models import DictionaryTerm, DictionaryStats
from ..mongo_dictionary_service import MongoDictionaryService, DictEntry
from ..models.unified_dictionary import UnifiedDictionaryTerm, UnifiedDictionaryStats
from ..patterns.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerError, get_circuit_breaker
)
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class MongoDictionaryAdapter:
    """
    Adapter to bridge AdminDictionaryService and MongoDictionaryService

    Provides MongoDB-backed storage while maintaining compatibility with
    existing AdminDictionaryService interfaces and data structures.
    Features circuit breaker pattern for resilient error handling.
    """

    def __init__(self,
                 environment: str,
                 fallback_handler: Optional[Callable] = None,
                 circuit_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize MongoDB adapter with circuit breaker protection

        Args:
            environment: Environment identifier (dev, test, prod)
            fallback_handler: Optional fallback function when MongoDB unavailable
            circuit_config: Circuit breaker configuration
        """
        self.environment = environment
        self.mongo_service = MongoDictionaryService(env=environment)
        self.fallback_handler = fallback_handler

        # Initialize circuit breaker with MongoDB-specific configuration
        if circuit_config is None:
            circuit_config = CircuitBreakerConfig(
                failure_threshold=3,  # Open after 3 failures
                recovery_timeout=30,  # Try recovery after 30 seconds
                timeout=5.0,         # 5 second operation timeout
                max_retry_attempts=2  # 2 retry attempts in half-open
            )

        self.circuit_breaker = get_circuit_breaker(
            name=f"mongodb_dictionary_{environment}",
            config=circuit_config,
            fallback_handler=self._fallback_empty_response
        )

        # Health check configuration
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds

        logger.info(f"MongoDB Dictionary Adapter initialized for {environment} with circuit breaker")

    def _fallback_empty_response(self, *args, **kwargs):
        """Default fallback that returns empty responses when MongoDB is unavailable"""
        method_name = kwargs.get('method_name', 'unknown')

        fallback_responses = {
            'get_environment_stats': DictionaryStats(
                total_terms=0,
                categories={},
                sources={},
                recent_updates=0,
                environment=self.environment
            ),
            'list_terms': [],
            'search_terms': [],
            'get_term': None,
            'delete_term': False
        }

        response = fallback_responses.get(method_name, None)
        logger.warning(f"MongoDB circuit breaker fallback for {method_name} in {self.environment}")
        return response

    def _perform_health_check(self) -> bool:
        """Perform health check on MongoDB service"""
        try:
            current_time = time.time()
            if current_time - self._last_health_check < self._health_check_interval:
                return True  # Skip frequent health checks

            self._last_health_check = current_time
            health = self.mongo_service.health_check()
            is_healthy = health.get("status") == "healthy"

            if not is_healthy:
                logger.warning(f"MongoDB health check failed for {self.environment}: {health}")

            return is_healthy

        except Exception as e:
            logger.error(f"MongoDB health check error for {self.environment}: {e}")
            return False

    def _execute_with_circuit_breaker(self, func: Callable, method_name: str, *args, **kwargs):
        """Execute a function through the circuit breaker with proper error handling"""
        try:
            return self.circuit_breaker.call(func)
        except CircuitBreakerError:
            # Circuit is open, use fallback if available
            if self.fallback_handler:
                return self.fallback_handler(method_name=method_name, **kwargs)
            else:
                return self._fallback_empty_response(method_name=method_name, **kwargs)
        except Exception as e:
            logger.error(f"Error in {method_name} for {self.environment}: {e}")
            raise

    async def get_environment_stats(self) -> DictionaryStats:
        """Get statistics for dictionary terms in environment from MongoDB"""
        def _get_stats_from_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB health check failed")

            stats = self.mongo_service.get_stats()
            if "error" in stats:
                raise Exception(stats["error"])

            return stats

        try:
            # Execute through circuit breaker
            mongo_stats = self._execute_with_circuit_breaker(
                _get_stats_from_mongo,
                "get_environment_stats"
            )

            # Convert MongoDB stats to AdminDictionaryService format using unified model
            unified_stats = UnifiedDictionaryStats(
                total_terms=mongo_stats.get("total_entries", 0),
                categories=mongo_stats.get("category_distribution", {}),
                sources=self._get_source_distribution(),
                recent_updates=self._get_recent_updates_count(),
                environment=self.environment,
                backend_type="mongodb",
                backend_health="healthy"
            )

            return unified_stats.to_dictionary_stats()

        except Exception as e:
            logger.error(f"Error getting MongoDB stats for {self.environment}: {e}")
            # Circuit breaker will handle fallback automatically
            return self._fallback_empty_response(method_name="get_environment_stats")

    async def list_terms(self, category: Optional[str] = None,
                        search: Optional[str] = None, limit: int = 100) -> List[DictionaryTerm]:
        """List dictionary terms from MongoDB"""
        def _list_terms_from_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB health check failed")

            # Use MongoDB search if query provided, otherwise get entries by category
            if search:
                mongo_entries = self.mongo_service.search_entries(
                    query=search,
                    category=category,
                    limit=limit
                )
            else:
                # Get entries by category or all if no category
                if category:
                    mongo_entries = self.mongo_service.search_entries(
                        query="",
                        category=category,
                        limit=limit
                    )
                else:
                    # Get all entries (limited) - use empty search to get all
                    mongo_entries = self.mongo_service.search_entries(
                        query="",
                        limit=limit
                    )
            return mongo_entries

        try:
            # Execute through circuit breaker
            mongo_entries = self._execute_with_circuit_breaker(
                _list_terms_from_mongo,
                "list_terms"
            )

            # Convert DictEntry objects to UnifiedDictionaryTerm then to DictionaryTerm
            terms = []
            for entry in mongo_entries:
                unified_term = UnifiedDictionaryTerm.from_dict_entry(entry, self.environment)
                dictionary_term = unified_term.to_dictionary_term()
                terms.append(dictionary_term)

            # Sort by update time (newest first)
            terms.sort(key=lambda x: x.updated_at or 0, reverse=True)

            logger.debug(f"Retrieved {len(terms)} terms from MongoDB for {self.environment}")
            return terms

        except Exception as e:
            logger.error(f"Error listing terms from MongoDB: {e}")
            return self._fallback_empty_response(method_name="list_terms")

    async def get_term(self, term: str) -> Optional[DictionaryTerm]:
        """Get a specific term from MongoDB"""
        def _get_term_from_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB health check failed")

            return self.mongo_service.get_entry(term)

        try:
            # Execute through circuit breaker
            mongo_entry = self._execute_with_circuit_breaker(
                _get_term_from_mongo,
                "get_term"
            )

            if mongo_entry:
                # Convert through unified model
                unified_term = UnifiedDictionaryTerm.from_dict_entry(mongo_entry, self.environment)
                return unified_term.to_dictionary_term()

            return None

        except Exception as e:
            logger.error(f"Error getting term '{term}' from MongoDB: {e}")
            return self._fallback_empty_response(method_name="get_term")

    async def create_term(self, term_data: Dict[str, Any]) -> DictionaryTerm:
        """Create a new term in MongoDB"""
        def _create_term_in_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB unavailable for term creation")

            # Validate required fields
            required_fields = ['term', 'definition', 'category', 'source']
            for field in required_fields:
                if field not in term_data:
                    raise ValueError(f"Missing required field: {field}")

            # Check if term already exists (this will go through circuit breaker too)
            existing_entry = self.mongo_service.get_entry(term_data['term'])
            if existing_entry:
                raise ValueError(f"Term '{term_data['term']}' already exists in {self.environment}")

            # Create unified term from input data
            unified_term = UnifiedDictionaryTerm(
                term=term_data['term'],
                definition=term_data['definition'],
                category=term_data['category'],
                environment=self.environment,
                sources=[],  # Will be set by post_init from legacy fields
                created_at=time.time(),
                updated_at=time.time(),
                version=1,
                tags=term_data.get('tags', []),
                source=term_data['source'],
                page_reference=term_data.get('page_reference')
            )

            # Convert to DictEntry for MongoDB storage
            dict_entry = unified_term.to_dict_entry()

            # Insert into MongoDB
            result = self.mongo_service.upsert_entries([dict_entry])
            if result == 0:
                raise Exception("Failed to insert term into MongoDB")

            return unified_term

        try:
            # Execute through circuit breaker
            unified_term = self._execute_with_circuit_breaker(
                _create_term_in_mongo,
                "create_term"
            )

            logger.info(f"Created term '{unified_term.term}' in MongoDB for {self.environment}")
            return unified_term.to_dictionary_term()

        except Exception as e:
            logger.error(f"Error creating term in MongoDB: {e}")
            raise

    async def update_term(self, term_name: str, updates: Dict[str, Any]) -> DictionaryTerm:
        """Update an existing term in MongoDB"""
        def _update_term_in_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB unavailable for term update")

            # Get existing term directly from MongoDB to avoid recursive circuit breaker calls
            existing_entry = self.mongo_service.get_entry(term_name)
            if not existing_entry:
                raise ValueError(f"Term '{term_name}' not found in {self.environment}")

            # Convert to unified term for easier manipulation
            unified_term = UnifiedDictionaryTerm.from_dict_entry(existing_entry, self.environment)

            # Apply updates
            if 'definition' in updates:
                unified_term.definition = updates['definition']
            if 'category' in updates:
                unified_term.category = updates['category']
            if 'tags' in updates:
                unified_term.tags = updates['tags']
            if 'source' in updates or 'page_reference' in updates:
                # Update primary source
                primary_source = unified_term.get_primary_source()
                if primary_source:
                    if 'source' in updates:
                        primary_source.system = updates['source']
                        unified_term.source = updates['source']
                    if 'page_reference' in updates:
                        primary_source.page_reference = updates['page_reference']
                        unified_term.page_reference = updates['page_reference']

            # Update timestamp and version
            unified_term.update_timestamp()

            # Convert back to DictEntry and update MongoDB
            dict_entry = unified_term.to_dict_entry()
            result = self.mongo_service.upsert_entries([dict_entry])
            if result == 0:
                raise Exception("Failed to update term in MongoDB")

            return unified_term

        try:
            # Execute through circuit breaker
            unified_term = self._execute_with_circuit_breaker(
                _update_term_in_mongo,
                "update_term"
            )

            logger.info(f"Updated term '{term_name}' in MongoDB for {self.environment}")
            return unified_term.to_dictionary_term()

        except Exception as e:
            logger.error(f"Error updating term '{term_name}' in MongoDB: {e}")
            raise

    async def delete_term(self, term_name: str) -> bool:
        """Delete a term from MongoDB"""
        def _delete_term_from_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB unavailable for term deletion")

            success = self.mongo_service.delete_entry(term_name)
            if not success:
                raise Exception(f"Failed to delete term '{term_name}' from MongoDB")

            return success

        try:
            # Execute through circuit breaker
            success = self._execute_with_circuit_breaker(
                _delete_term_from_mongo,
                "delete_term"
            )

            if success:
                logger.info(f"Deleted term '{term_name}' from MongoDB for {self.environment}")

            return success

        except Exception as e:
            logger.error(f"Error deleting term '{term_name}' from MongoDB: {e}")
            return self._fallback_empty_response(method_name="delete_term")

    async def search_terms(self, query: str, category: Optional[str] = None) -> List[DictionaryTerm]:
        """Search terms in MongoDB with full-text search"""
        def _search_terms_in_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB unavailable for search")

            # Use MongoDB's search capabilities
            return self.mongo_service.search_entries(
                query=query,
                category=category,
                limit=100  # Reasonable limit for search results
            )

        try:
            # Execute through circuit breaker
            mongo_entries = self._execute_with_circuit_breaker(
                _search_terms_in_mongo,
                "search_terms"
            )

            # Convert to DictionaryTerm objects using unified model
            terms = []
            for entry in mongo_entries:
                unified_term = UnifiedDictionaryTerm.from_dict_entry(entry, self.environment)
                dictionary_term = unified_term.to_dictionary_term()
                terms.append(dictionary_term)

            logger.debug(f"Found {len(terms)} terms matching '{query}' in MongoDB")
            return terms

        except Exception as e:
            logger.error(f"Error searching terms in MongoDB: {e}")
            return self._fallback_empty_response(method_name="search_terms")

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring"""
        return self.circuit_breaker.get_stats()

    def reset_circuit_breaker(self):
        """Reset circuit breaker to initial state"""
        self.circuit_breaker.reset()
        logger.info(f"MongoDB circuit breaker reset for {self.environment}")

    def force_health_check(self) -> bool:
        """Force a health check regardless of interval"""
        old_interval = self._last_health_check
        self._last_health_check = 0  # Force health check
        result = self._perform_health_check()
        if not result:
            self._last_health_check = old_interval  # Restore if failed
        return result

    async def bulk_import(self, terms_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk import terms using MongoDB backend with circuit breaker protection"""
        def _bulk_import_to_mongo():
            # Perform health check
            if not self._perform_health_check():
                raise Exception("MongoDB unavailable for bulk import")

            # Convert input data to UnifiedDictionaryTerm objects
            unified_terms = []
            for term_data in terms_data:
                try:
                    unified_term = UnifiedDictionaryTerm(
                        term=term_data['term'],
                        definition=term_data['definition'],
                        category=term_data['category'],
                        environment=self.environment,
                        sources=[],  # Will be set by post_init from legacy fields
                        created_at=time.time(),
                        updated_at=time.time(),
                        version=1,
                        tags=term_data.get('tags', []),
                        source=term_data.get('source', 'bulk_import'),
                        page_reference=term_data.get('page_reference')
                    )
                    unified_terms.append(unified_term)
                except Exception as e:
                    logger.warning(f"Skipping invalid term data: {e}")

            # Convert to DictEntry objects for MongoDB
            dict_entries = [term.to_dict_entry() for term in unified_terms]

            # Bulk insert into MongoDB
            result = self.mongo_service.upsert_entries(dict_entries)

            return {
                "total": len(terms_data),
                "created": result,
                "failed": len(terms_data) - result,
                "unified_terms": unified_terms
            }

        try:
            # Execute through circuit breaker
            result = self._execute_with_circuit_breaker(
                _bulk_import_to_mongo,
                "bulk_import"
            )

            logger.info(f"Bulk imported {result['created']}/{result['total']} terms to MongoDB for {self.environment}")

            # Remove unified_terms from return value (not needed externally)
            return {
                "total": result["total"],
                "created": result["created"],
                "failed": result["failed"]
            }

        except Exception as e:
            logger.error(f"Error in bulk import to MongoDB: {e}")
            return {
                "total": len(terms_data),
                "created": 0,
                "failed": len(terms_data)
            }

    def _get_source_distribution(self) -> Dict[str, int]:
        """Get distribution of terms by source from MongoDB using aggregation"""
        try:
            if self.mongo_service.collection is None:
                return {}

            # Use MongoDB aggregation to get source distribution
            pipeline = [
                {"$unwind": "$sources"},
                {"$group": {
                    "_id": "$sources.system",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]

            result = list(self.mongo_service.collection.aggregate(pipeline))
            distribution = {}
            for item in result:
                source_name = item.get("_id", "unknown")
                count = item.get("count", 0)
                distribution[source_name] = count

            return distribution

        except Exception as e:
            logger.warning(f"Error getting source distribution: {e}")
            return {"mongodb": 1}  # Fallback

    def _get_recent_updates_count(self) -> int:
        """Get count of recent updates from MongoDB (last 24 hours)"""
        try:
            if self.mongo_service.collection is None:
                return 0

            # Get entries updated in the last 24 hours
            twenty_four_hours_ago = time.time() - (24 * 60 * 60)
            count = self.mongo_service.collection.count_documents({
                "updated_at": {"$gte": twenty_four_hours_ago}
            })
            return count

        except Exception as e:
            logger.warning(f"Error getting recent updates count: {e}")
            return 0  # Fallback