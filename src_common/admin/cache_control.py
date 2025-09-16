# src_common/admin/cache_control.py
"""
Cache Control Service - ADM-005
Cache refresh compliance and control for environment-specific testing
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from ..ttrpg_logging import get_logger


logger = get_logger(__name__)


@dataclass
class CachePolicy:
    """Cache policy configuration"""
    environment: str
    cache_enabled: bool
    default_ttl_seconds: int
    no_store_pages: List[str]
    short_ttl_pages: List[str]
    short_ttl_seconds: int
    admin_override: bool
    last_updated: float
    updated_by: str


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    environment: str
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_ratio: float
    average_response_time_ms: float
    last_reset: float
    timestamp: float


class AdminCacheService:
    """
    Cache Control Service
    
    Manages cache policies and provides real-time cache control for admin operations.
    Ensures fast retest behavior and compliance with Phase 0 cache requirements.
    """
    
    def __init__(self):
        self.environments = ['dev', 'test', 'prod']
        self.default_policies = {
            'dev': {
                'cache_enabled': False,  # No-store by default
                'default_ttl_seconds': 0,
                'short_ttl_seconds': 5,
                'no_store_pages': ['*'],  # All pages no-store in dev
                'short_ttl_pages': []
            },
            'test': {
                'cache_enabled': True,
                'default_ttl_seconds': 5,  # Very short TTL
                'short_ttl_seconds': 5,
                'no_store_pages': ['/admin/*', '/api/feedback/*'],
                'short_ttl_pages': ['*']  # All pages short TTL
            },
            'prod': {
                'cache_enabled': True,
                'default_ttl_seconds': 300,  # 5 minutes
                'short_ttl_seconds': 5,
                'no_store_pages': ['/admin/*', '/api/feedback/*'],
                'short_ttl_pages': ['/api/ask', '/workflow/*']
            }
        }
        logger.info("Admin Cache Control Service initialized")
    
    async def get_cache_overview(self) -> Dict[str, Any]:
        """
        Get cache status overview for all environments
        
        Returns:
            Dictionary with cache policies and metrics per environment
        """
        try:
            overview = {
                "timestamp": time.time(),
                "environments": {}
            }
            
            for env in self.environments:
                policy = await self.get_cache_policy(env)
                metrics = await self.get_cache_metrics(env)
                
                overview["environments"][env] = {
                    "policy": asdict(policy),
                    "metrics": asdict(metrics) if metrics else None,
                    "status": "disabled" if not policy.cache_enabled else "enabled"
                }
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting cache overview: {e}")
            raise
    
    async def get_cache_policy(self, environment: str) -> CachePolicy:
        """
        Get current cache policy for an environment
        
        Args:
            environment: Environment name (dev/test/prod)
            
        Returns:
            CachePolicy object with current settings
        """
        try:
            # Load policy from environment-specific storage or use defaults
            policy_data = self.default_policies.get(environment, self.default_policies['dev'])
            
            return CachePolicy(
                environment=environment,
                cache_enabled=policy_data['cache_enabled'],
                default_ttl_seconds=policy_data['default_ttl_seconds'],
                no_store_pages=policy_data['no_store_pages'],
                short_ttl_pages=policy_data['short_ttl_pages'],
                short_ttl_seconds=policy_data['short_ttl_seconds'],
                admin_override=False,  # Default to no override
                last_updated=time.time(),
                updated_by='system'
            )
            
        except Exception as e:
            logger.error(f"Error getting cache policy for {environment}: {e}")
            raise
    
    async def update_cache_policy(self, environment: str, updates: Dict[str, Any], 
                                 updated_by: str = 'admin') -> CachePolicy:
        """
        Update cache policy for an environment
        
        Args:
            environment: Environment name
            updates: Policy updates to apply
            updated_by: User making the update
            
        Returns:
            Updated CachePolicy object
        """
        try:
            policy = await self.get_cache_policy(environment)
            
            # Apply updates
            if 'cache_enabled' in updates:
                policy.cache_enabled = updates['cache_enabled']
            
            if 'default_ttl_seconds' in updates:
                policy.default_ttl_seconds = updates['default_ttl_seconds']
            
            if 'short_ttl_seconds' in updates:
                policy.short_ttl_seconds = updates['short_ttl_seconds']
            
            if 'no_store_pages' in updates:
                policy.no_store_pages = updates['no_store_pages']
            
            if 'short_ttl_pages' in updates:
                policy.short_ttl_pages = updates['short_ttl_pages']
            
            if 'admin_override' in updates:
                policy.admin_override = updates['admin_override']
            
            policy.last_updated = time.time()
            policy.updated_by = updated_by
            
            # Save policy (in real implementation, this would persist to storage)
            await self._save_cache_policy(policy)
            
            logger.info(f"Updated cache policy for {environment} by {updated_by}")
            return policy
            
        except Exception as e:
            logger.error(f"Error updating cache policy for {environment}: {e}")
            raise
    
    async def disable_cache(self, environment: str, updated_by: str = 'admin') -> bool:
        """
        Disable all caching for an environment (admin override)
        
        Args:
            environment: Environment name
            updated_by: User disabling cache
            
        Returns:
            True if successfully disabled
        """
        try:
            await self.update_cache_policy(
                environment,
                {
                    'cache_enabled': False,
                    'admin_override': True,
                    'no_store_pages': ['*']
                },
                updated_by
            )
            
            logger.info(f"Cache disabled for {environment} by {updated_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling cache for {environment}: {e}")
            return False
    
    async def enable_cache(self, environment: str, updated_by: str = 'admin') -> bool:
        """
        Enable caching with environment defaults
        
        Args:
            environment: Environment name
            updated_by: User enabling cache
            
        Returns:
            True if successfully enabled
        """
        try:
            defaults = self.default_policies.get(environment, self.default_policies['dev'])
            
            await self.update_cache_policy(
                environment,
                {
                    'cache_enabled': defaults['cache_enabled'],
                    'admin_override': False,
                    'default_ttl_seconds': defaults['default_ttl_seconds'],
                    'no_store_pages': defaults['no_store_pages'],
                    'short_ttl_pages': defaults['short_ttl_pages']
                },
                updated_by
            )
            
            logger.info(f"Cache enabled for {environment} by {updated_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling cache for {environment}: {e}")
            return False
    
    async def get_cache_headers(self, environment: str, request_path: str) -> Dict[str, str]:
        """
        Get appropriate cache headers for a request
        
        Args:
            environment: Environment name
            request_path: Request path to check
            
        Returns:
            Dictionary of HTTP cache headers
        """
        try:
            policy = await self.get_cache_policy(environment)
            
            # If admin override is active, disable cache
            if policy.admin_override and not policy.cache_enabled:
                return {
                    'Cache-Control': 'no-store, no-cache, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            
            # If caching is disabled globally
            if not policy.cache_enabled:
                return {
                    'Cache-Control': 'no-store, no-cache, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            
            # Check for no-store pages
            for pattern in policy.no_store_pages:
                if self._match_pattern(pattern, request_path):
                    return {
                        'Cache-Control': 'no-store, no-cache, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
            
            # Check for short TTL pages
            for pattern in policy.short_ttl_pages:
                if self._match_pattern(pattern, request_path):
                    return {
                        'Cache-Control': f'public, max-age={policy.short_ttl_seconds}',
                        'Expires': str(int(time.time() + policy.short_ttl_seconds))
                    }
            
            # Default TTL
            return {
                'Cache-Control': f'public, max-age={policy.default_ttl_seconds}',
                'Expires': str(int(time.time() + policy.default_ttl_seconds))
            }
            
        except Exception as e:
            logger.error(f"Error getting cache headers for {environment}/{request_path}: {e}")
            # Safe fallback - no cache
            return {
                'Cache-Control': 'no-store, no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
    
    async def get_cache_metrics(self, environment: str) -> Optional[CacheMetrics]:
        """
        Get cache performance metrics for an environment
        
        Args:
            environment: Environment name
            
        Returns:
            CacheMetrics object or None if no metrics available
        """
        try:
            # In a real implementation, this would load actual metrics from Redis/monitoring
            # For now, return simulated metrics
            return CacheMetrics(
                environment=environment,
                total_requests=1000,
                cache_hits=750,
                cache_misses=250,
                hit_ratio=0.75,
                average_response_time_ms=125.5,
                last_reset=time.time() - 86400,  # 24 hours ago
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error getting cache metrics for {environment}: {e}")
            return None
    
    async def clear_cache(self, environment: str, pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear cache for an environment or specific pattern
        
        Args:
            environment: Environment name
            pattern: Optional pattern to clear (e.g., '/api/*')
            
        Returns:
            Dictionary with clearing results
        """
        try:
            # In a real implementation, this would clear actual cache entries
            # For now, simulate the operation
            
            cleared_count = 0
            
            if pattern:
                # Clear specific pattern
                cleared_count = 50  # Simulated
                logger.info(f"Cleared cache pattern '{pattern}' for {environment}")
            else:
                # Clear all cache
                cleared_count = 1000  # Simulated
                logger.info(f"Cleared all cache for {environment}")
            
            return {
                "environment": environment,
                "pattern": pattern,
                "cleared_entries": cleared_count,
                "timestamp": time.time(),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error clearing cache for {environment}: {e}")
            return {
                "environment": environment,
                "pattern": pattern,
                "cleared_entries": 0,
                "timestamp": time.time(),
                "success": False,
                "error": str(e)
            }
    
    async def validate_compliance(self, environment: str) -> Dict[str, Any]:
        """
        Validate cache compliance with Phase 0 requirements
        
        Args:
            environment: Environment name
            
        Returns:
            Compliance validation results
        """
        try:
            policy = await self.get_cache_policy(environment)
            compliance_issues = []
            
            # Check environment-specific requirements
            if environment == 'dev':
                if policy.cache_enabled and not policy.admin_override:
                    compliance_issues.append("DEV environment should use no-store by default")
            
            elif environment == 'test':
                if policy.default_ttl_seconds > 5:
                    compliance_issues.append("TEST environment TTL should be ≤5 seconds")
            
            # Check admin override capability
            if not hasattr(policy, 'admin_override'):
                compliance_issues.append("Admin cache override toggle not available")
            
            # Check critical pages have no-store
            critical_pages = ['/admin/*', '/api/feedback/*']
            for page in critical_pages:
                if page not in policy.no_store_pages:
                    compliance_issues.append(f"Critical page pattern '{page}' should be no-store")
            
            return {
                "environment": environment,
                "compliant": len(compliance_issues) == 0,
                "issues": compliance_issues,
                "policy": asdict(policy),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Error validating cache compliance for {environment}: {e}")
            return {
                "environment": environment,
                "compliant": False,
                "issues": [f"Validation error: {str(e)}"],
                "timestamp": time.time()
            }
    
    def _match_pattern(self, pattern: str, path: str) -> bool:
        """
        Check if a path matches a cache pattern
        
        Args:
            pattern: Pattern with wildcards (e.g., '/api/*', '*')
            path: Request path to match
            
        Returns:
            True if path matches pattern
        """
        if pattern == '*':
            return True
        
        if pattern.endswith('/*'):
            prefix = pattern[:-2]
            return path.startswith(prefix)
        
        return pattern == path
    
    async def _save_cache_policy(self, policy: CachePolicy):
        """Save cache policy to storage (stub implementation)"""
        # In a real implementation, this would persist to environment-specific storage
        logger.debug(f"Saved cache policy for {policy.environment}")
        pass