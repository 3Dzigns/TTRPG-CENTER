# container_health_service.py
"""
FR-006: Container Health Service
Comprehensive health monitoring for all containerized services
"""

import os
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import psutil
import logging

from .logging import get_logger
from .database_config import test_database_connection, get_database_info, get_engine
from .mongo_dictionary_service import get_dictionary_service
from .neo4j_graph_service import get_graph_service
from .redis_service import get_redis_service
from .container_scheduler_service import get_scheduler_service

logger = get_logger(__name__)


class ContainerHealthService:
    """Comprehensive health monitoring for all containerized services"""
    
    def __init__(self):
        self.app_env = os.getenv("APP_ENV", "dev")
        self.app_version = os.getenv("APP_VERSION", "dev")
        self.startup_time = time.time()
    
    async def get_health_status(self, include_details: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive health status of all services
        
        Args:
            include_details: Whether to include detailed service information
            
        Returns:
            Dictionary with health status information
        """
        start_time = time.time()
        
        # Base health info
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "environment": self.app_env,
            "version": self.app_version,
            "uptime_seconds": round(time.time() - self.startup_time, 2),
            "services": {}
        }
        
        # Check all services
        services_health = await self._check_all_services(include_details)
        health_status["services"] = services_health
        
        # Determine overall status
        overall_status = self._determine_overall_status(services_health)
        health_status["status"] = overall_status
        
        # Add response time
        health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        # Add system metrics if details requested
        if include_details:
            health_status["system"] = await self._get_system_metrics()
        
        return health_status
    
    async def _check_all_services(self, include_details: bool) -> Dict[str, Dict[str, Any]]:
        """Check health of all services"""
        services = {}
        
        # Check services concurrently
        service_checks = [
            ("database", self._check_database_health(include_details)),
            ("mongodb", self._check_mongodb_health(include_details)),
            ("neo4j", self._check_neo4j_health(include_details)),
            ("redis", self._check_redis_health(include_details)),
            ("scheduler", self._check_scheduler_health(include_details)),
            ("astradb", self._check_astradb_health(include_details)),
            ("openai", self._check_openai_health(include_details))
        ]
        
        # Execute all checks
        for service_name, check_coro in service_checks:
            try:
                services[service_name] = await check_coro
            except Exception as e:
                services[service_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return services
    
    async def _check_database_health(self, include_details: bool) -> Dict[str, Any]:
        """Check PostgreSQL/SQLite database health"""
        try:
            # Test connection
            is_connected = test_database_connection()
            
            if not is_connected:
                return {"status": "error", "error": "Database connection failed"}
            
            result = {"status": "healthy"}
            
            if include_details:
                db_info = get_database_info(get_engine())
                result.update(db_info)
            
            return result
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_mongodb_health(self, include_details: bool) -> Dict[str, Any]:
        """Check MongoDB health"""
        try:
            mongo_service = get_dictionary_service()
            health = mongo_service.health_check()
            
            if include_details and health.get("status") == "healthy":
                stats = mongo_service.get_stats()
                if "error" not in stats:
                    health.update(stats)
            
            return health
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_neo4j_health(self, include_details: bool) -> Dict[str, Any]:
        """Check Neo4j health"""
        try:
            graph_service = get_graph_service()
            health = graph_service.health_check()
            
            if include_details and health.get("status") == "healthy":
                stats = graph_service.get_graph_stats()
                if "error" not in stats:
                    health.update(stats)
            
            return health
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_redis_health(self, include_details: bool) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            redis_service = get_redis_service()
            health = redis_service.health_check()
            
            if include_details and health.get("status") in ["healthy", "disabled"]:
                info = redis_service.get_info()
                if "error" not in info:
                    health.update(info)
            
            return health
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_scheduler_health(self, include_details: bool) -> Dict[str, Any]:
        """Check APScheduler health"""
        try:
            scheduler_service = get_scheduler_service()
            status = scheduler_service.get_status()
            
            health = {
                "status": "healthy" if status["running"] else "disabled",
                "enabled": status["enabled"],
                "running": status["running"]
            }
            
            if include_details:
                health.update(status)
                jobs = scheduler_service.get_jobs()
                health["jobs"] = jobs
            
            return health
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_astradb_health(self, include_details: bool) -> Dict[str, Any]:
        """Check AstraDB connectivity"""
        try:
            # Check if AstraDB configuration is available
            astra_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
            astra_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
            
            if not astra_endpoint or not astra_token:
                return {
                    "status": "disabled",
                    "reason": "AstraDB credentials not configured"
                }
            
            # Basic connectivity check (import here to avoid circular dependencies)
            try:
                from .astra_loader import AstraLoader
                astra = AstraLoader()
                
                if astra.collection:
                    # Try a simple operation
                    # This is a basic check - in production you might want a dedicated health check endpoint
                    return {"status": "healthy", "configured": True}
                else:
                    return {"status": "error", "error": "AstraDB collection not available"}
                    
            except ImportError:
                return {"status": "error", "error": "AstraDB client not available"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_openai_health(self, include_details: bool) -> Dict[str, Any]:
        """Check OpenAI API connectivity"""
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            
            if not openai_key:
                return {
                    "status": "disabled",
                    "reason": "OpenAI API key not configured"
                }
            
            # Basic check - we don't want to make actual API calls in health checks
            # Just verify the key is present and has the expected format
            if openai_key.startswith("sk-") and len(openai_key) > 20:
                return {"status": "configured", "key_format": "valid"}
            else:
                return {"status": "error", "error": "Invalid API key format"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _determine_overall_status(self, services_health: Dict[str, Dict[str, Any]]) -> str:
        """Determine overall health status based on service statuses"""
        critical_services = ["database"]  # Services that must be healthy
        important_services = ["mongodb", "neo4j"]  # Services that should be healthy
        
        # Check critical services
        for service in critical_services:
            service_status = services_health.get(service, {}).get("status", "unknown")
            if service_status not in ["healthy"]:
                return "unhealthy"
        
        # Check important services
        unhealthy_important = 0
        for service in important_services:
            service_status = services_health.get(service, {}).get("status", "unknown")
            if service_status not in ["healthy", "disabled"]:
                unhealthy_important += 1
        
        # If more than half of important services are down, mark as degraded
        if unhealthy_important > len(important_services) // 2:
            return "degraded"
        
        return "healthy"
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage for log directory
            log_directory = os.getenv("LOG_DIRECTORY", "/var/log/ttrpg")
            try:
                disk_usage = psutil.disk_usage(log_directory)
            except:
                disk_usage = None
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "percent": memory.percent
                },
                "process": {
                    "pid": os.getpid(),
                    "memory_rss_bytes": psutil.Process().memory_info().rss,
                    "memory_vms_bytes": psutil.Process().memory_info().vms,
                    "cpu_percent": psutil.Process().cpu_percent()
                }
            }
            
            if disk_usage:
                metrics["disk"] = {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free,
                    "percent": (disk_usage.used / disk_usage.total) * 100
                }
            
            return metrics
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """
        Get readiness status (lighter check for Kubernetes readiness probes)
        
        Returns:
            Basic readiness information
        """
        # Quick check of critical services only
        database_ok = test_database_connection()
        
        return {
            "status": "ready" if database_ok else "not_ready",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {
                "database": "healthy" if database_ok else "error"
            }
        }
    
    async def get_liveness_status(self) -> Dict[str, Any]:
        """
        Get liveness status (basic app health for Kubernetes liveness probes)
        
        Returns:
            Basic liveness information
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": round(time.time() - self.startup_time, 2),
            "environment": self.app_env
        }


# Global health service instance
_health_service: Optional[ContainerHealthService] = None


def get_health_service() -> ContainerHealthService:
    """Get or create the global health service instance"""
    global _health_service
    if _health_service is None:
        _health_service = ContainerHealthService()
    return _health_service