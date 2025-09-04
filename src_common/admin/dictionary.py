# src_common/admin/dictionary.py
"""
Dictionary Management Service - ADM-003
CRUD operations for term definitions with environment-specific scoping
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from ..logging import get_logger
from ..graph.store import GraphStore


logger = get_logger(__name__)


@dataclass
class DictionaryTerm:
    """Dictionary term definition"""
    term: str
    definition: str
    category: str  # 'rule', 'concept', 'procedure', 'entity'
    environment: str
    source: str
    page_reference: Optional[str] = None
    created_at: float = None
    updated_at: float = None
    version: int = 1
    tags: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.tags is None:
            self.tags = []


@dataclass
class DictionaryStats:
    """Dictionary statistics"""
    total_terms: int
    categories: Dict[str, int]
    sources: Dict[str, int]
    recent_updates: int
    environment: str


class AdminDictionaryService:
    """
    Dictionary Management Service
    
    Provides CRUD operations for managing dictionary terms with
    environment-specific scoping and version tracking.
    """
    
    def __init__(self, graph_store: Optional[GraphStore] = None):
        self.graph_store = graph_store or GraphStore()
        self.environments = ['dev', 'test', 'prod']
        logger.info("Admin Dictionary Service initialized")
    
    async def get_dictionary_overview(self) -> Dict[str, Any]:
        """
        Get overview of dictionary content across all environments
        
        Returns:
            Dictionary statistics and summaries per environment
        """
        try:
            overview = {
                "timestamp": time.time(),
                "environments": {}
            }
            
            for env in self.environments:
                stats = await self.get_environment_stats(env)
                recent_terms = await self.list_terms(env, limit=5)
                
                overview["environments"][env] = {
                    "stats": asdict(stats),
                    "recent_terms": [asdict(term) for term in recent_terms]
                }
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting dictionary overview: {e}")
            raise
    
    async def get_environment_stats(self, environment: str) -> DictionaryStats:
        """
        Get statistics for dictionary terms in a specific environment
        
        Args:
            environment: Environment name (dev/test/prod)
            
        Returns:
            DictionaryStats with counts and breakdowns
        """
        try:
            terms = await self.list_terms(environment)
            
            # Calculate statistics
            categories = {}
            sources = {}
            recent_cutoff = time.time() - (7 * 24 * 3600)  # 7 days
            recent_updates = 0
            
            for term in terms:
                # Category breakdown
                categories[term.category] = categories.get(term.category, 0) + 1
                
                # Source breakdown
                sources[term.source] = sources.get(term.source, 0) + 1
                
                # Recent updates count
                if term.updated_at and term.updated_at > recent_cutoff:
                    recent_updates += 1
            
            return DictionaryStats(
                total_terms=len(terms),
                categories=categories,
                sources=sources,
                recent_updates=recent_updates,
                environment=environment
            )
            
        except Exception as e:
            logger.error(f"Error getting stats for {environment}: {e}")
            return DictionaryStats(
                total_terms=0,
                categories={},
                sources={},
                recent_updates=0,
                environment=environment
            )
    
    async def list_terms(self, environment: str, category: Optional[str] = None, 
                        search: Optional[str] = None, limit: int = 100) -> List[DictionaryTerm]:
        """
        List dictionary terms for a specific environment
        
        Args:
            environment: Environment name
            category: Optional category filter
            search: Optional search term
            limit: Maximum number of terms to return
            
        Returns:
            List of DictionaryTerm objects
        """
        try:
            # Load terms from environment-specific storage
            terms = await self._load_environment_terms(environment)
            
            # Apply filters
            if category:
                terms = [term for term in terms if term.category == category]
            
            if search:
                search_lower = search.lower()
                terms = [term for term in terms 
                        if search_lower in term.term.lower() 
                        or search_lower in term.definition.lower()]
            
            # Sort by update time (newest first) and apply limit
            terms.sort(key=lambda x: x.updated_at or 0, reverse=True)
            return terms[:limit]
            
        except Exception as e:
            logger.error(f"Error listing terms for {environment}: {e}")
            return []
    
    async def get_term(self, environment: str, term: str) -> Optional[DictionaryTerm]:
        """
        Get a specific term definition
        
        Args:
            environment: Environment name
            term: Term to look up
            
        Returns:
            DictionaryTerm object or None if not found
        """
        try:
            terms = await self._load_environment_terms(environment)
            
            for dict_term in terms:
                if dict_term.term.lower() == term.lower():
                    return dict_term
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting term {term} from {environment}: {e}")
            return None
    
    async def create_term(self, environment: str, term_data: Dict[str, Any]) -> DictionaryTerm:
        """
        Create a new dictionary term
        
        Args:
            environment: Environment name
            term_data: Term data dictionary
            
        Returns:
            Created DictionaryTerm object
        """
        try:
            # Validate required fields
            required_fields = ['term', 'definition', 'category', 'source']
            for field in required_fields:
                if field not in term_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Check if term already exists
            existing = await self.get_term(environment, term_data['term'])
            if existing:
                raise ValueError(f"Term '{term_data['term']}' already exists in {environment}")
            
            # Create term object
            term = DictionaryTerm(
                term=term_data['term'],
                definition=term_data['definition'],
                category=term_data['category'],
                environment=environment,
                source=term_data['source'],
                page_reference=term_data.get('page_reference'),
                tags=term_data.get('tags', []),
                created_at=time.time(),
                updated_at=time.time(),
                version=1
            )
            
            # Save to storage
            await self._save_term(term)
            
            # Add to graph store as Concept node
            await self._sync_to_graph_store(term)
            
            logger.info(f"Created term '{term.term}' in {environment}")
            return term
            
        except Exception as e:
            logger.error(f"Error creating term in {environment}: {e}")
            raise
    
    async def update_term(self, environment: str, term_name: str, updates: Dict[str, Any]) -> DictionaryTerm:
        """
        Update an existing dictionary term
        
        Args:
            environment: Environment name
            term_name: Name of term to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated DictionaryTerm object
        """
        try:
            # Get existing term
            term = await self.get_term(environment, term_name)
            if not term:
                raise ValueError(f"Term '{term_name}' not found in {environment}")
            
            # Apply updates
            if 'definition' in updates:
                term.definition = updates['definition']
            if 'category' in updates:
                term.category = updates['category']
            if 'source' in updates:
                term.source = updates['source']
            if 'page_reference' in updates:
                term.page_reference = updates['page_reference']
            if 'tags' in updates:
                term.tags = updates['tags']
            
            # Update metadata
            term.updated_at = time.time()
            term.version += 1
            
            # Save to storage
            await self._save_term(term)
            
            # Update in graph store
            await self._sync_to_graph_store(term)
            
            logger.info(f"Updated term '{term_name}' in {environment}")
            return term
            
        except Exception as e:
            logger.error(f"Error updating term {term_name} in {environment}: {e}")
            raise
    
    async def delete_term(self, environment: str, term_name: str) -> bool:
        """
        Delete a dictionary term
        
        Args:
            environment: Environment name
            term_name: Name of term to delete
            
        Returns:
            True if deletion successful
        """
        try:
            # Get existing term
            term = await self.get_term(environment, term_name)
            if not term:
                return False
            
            # Remove from storage
            await self._delete_term(term)
            
            # Remove from graph store
            node_id = f"concept:{environment}:{term_name.lower()}"
            # Note: GraphStore doesn't have delete method in current implementation
            # This would need to be added to the GraphStore class
            
            logger.info(f"Deleted term '{term_name}' from {environment}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting term {term_name} from {environment}: {e}")
            return False
    
    async def bulk_import(self, environment: str, terms_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk import dictionary terms
        
        Args:
            environment: Environment name
            terms_data: List of term data dictionaries
            
        Returns:
            Import results with success/failure counts
        """
        try:
            results = {
                "total": len(terms_data),
                "created": 0,
                "updated": 0,
                "failed": 0,
                "errors": []
            }
            
            for term_data in terms_data:
                try:
                    existing = await self.get_term(environment, term_data['term'])
                    
                    if existing:
                        # Update existing term
                        await self.update_term(environment, term_data['term'], term_data)
                        results["updated"] += 1
                    else:
                        # Create new term
                        await self.create_term(environment, term_data)
                        results["created"] += 1
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "term": term_data.get('term', 'unknown'),
                        "error": str(e)
                    })
            
            logger.info(f"Bulk import to {environment}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in bulk import to {environment}: {e}")
            raise
    
    async def export_terms(self, environment: str, format: str = 'json') -> str:
        """
        Export dictionary terms from an environment
        
        Args:
            environment: Environment name
            format: Export format ('json' or 'csv')
            
        Returns:
            Exported data as string
        """
        try:
            terms = await self.list_terms(environment, limit=None)  # Get all terms
            
            if format == 'json':
                export_data = {
                    "environment": environment,
                    "exported_at": time.time(),
                    "terms": [asdict(term) for term in terms]
                }
                return json.dumps(export_data, indent=2)
            
            elif format == 'csv':
                import csv
                from io import StringIO
                
                output = StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(['term', 'definition', 'category', 'source', 'page_reference', 'tags'])
                
                # Write data
                for term in terms:
                    writer.writerow([
                        term.term,
                        term.definition,
                        term.category,
                        term.source,
                        term.page_reference or '',
                        ','.join(term.tags) if term.tags else ''
                    ])
                
                return output.getvalue()
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting terms from {environment}: {e}")
            raise
    
    async def search_terms(self, environment: str, query: str, category: Optional[str] = None) -> List[DictionaryTerm]:
        """
        Search dictionary terms with full-text search
        
        Args:
            environment: Environment name
            query: Search query
            category: Optional category filter
            
        Returns:
            List of matching DictionaryTerm objects
        """
        try:
            # Simple text search implementation
            terms = await self.list_terms(environment, category=category, limit=None)
            
            query_lower = query.lower()
            matching_terms = []
            
            for term in terms:
                # Search in term name, definition, and tags
                search_text = f"{term.term} {term.definition} {' '.join(term.tags)}".lower()
                
                if query_lower in search_text:
                    matching_terms.append(term)
            
            return matching_terms
            
        except Exception as e:
            logger.error(f"Error searching terms in {environment}: {e}")
            return []
    
    async def _load_environment_terms(self, environment: str) -> List[DictionaryTerm]:
        """Load all terms for an environment from storage"""
        try:
            terms_file = Path(f"env/{environment}/data/dictionary.json")
            
            if not terms_file.exists():
                return []
            
            with open(terms_file, 'r', encoding='utf-8') as f:
                terms_data = json.load(f)
            
            terms = []
            for term_dict in terms_data.get('terms', []):
                term = DictionaryTerm(**term_dict)
                terms.append(term)
            
            return terms
            
        except Exception as e:
            logger.warning(f"Could not load terms for {environment}: {e}")
            return []
    
    async def _save_term(self, term: DictionaryTerm):
        """Save a term to environment-specific storage"""
        try:
            # Load existing terms
            terms = await self._load_environment_terms(term.environment)
            
            # Update or add term
            updated = False
            for i, existing_term in enumerate(terms):
                if existing_term.term.lower() == term.term.lower():
                    terms[i] = term
                    updated = True
                    break
            
            if not updated:
                terms.append(term)
            
            # Save back to file
            terms_file = Path(f"env/{term.environment}/data/dictionary.json")
            terms_file.parent.mkdir(parents=True, exist_ok=True)
            
            export_data = {
                "environment": term.environment,
                "updated_at": time.time(),
                "terms": [asdict(t) for t in terms]
            }
            
            with open(terms_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving term {term.term}: {e}")
            raise
    
    async def _delete_term(self, term: DictionaryTerm):
        """Delete a term from storage"""
        try:
            terms = await self._load_environment_terms(term.environment)
            
            # Remove term
            terms = [t for t in terms if t.term.lower() != term.term.lower()]
            
            # Save back to file
            terms_file = Path(f"env/{term.environment}/data/dictionary.json")
            
            export_data = {
                "environment": term.environment,
                "updated_at": time.time(),
                "terms": [asdict(t) for t in terms]
            }
            
            with open(terms_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error deleting term {term.term}: {e}")
            raise
    
    async def _sync_to_graph_store(self, term: DictionaryTerm):
        """Sync dictionary term to graph store"""
        try:
            node_id = f"concept:{term.environment}:{term.term.lower()}"
            
            properties = {
                "name": term.term,
                "definition": term.definition,
                "source": term.source,
                "page_reference": term.page_reference,
                "tags": term.tags,
                "environment": term.environment,
                "version": term.version
            }
            
            self.graph_store.upsert_node(node_id, "Concept", properties)
            
        except Exception as e:
            logger.warning(f"Could not sync term to graph store: {e}")
            # Don't fail the operation if graph sync fails