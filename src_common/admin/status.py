# src_common/admin/status.py
"""
System Status Dashboard Service - ADM-001
Environment-aware monitoring and health checks for DEV/TEST/PROD environments
"""

import os
import json
import time
import psutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from ..logging import get_logger
from ..secrets import get_all_config


logger = get_logger(__name__)


@dataclass
class EnvironmentStatus:
    """Status information for a single environment"""
    name: str
    port: int
    websocket_port: int
    is_active: bool
    uptime_seconds: Optional[float]
    process_id: Optional[int]
    memory_mb: Optional[float]
    cpu_percent: Optional[float]
    last_health_check: Optional[float]
    error_message: Optional[str] = None


@dataclass
class SystemMetrics:
    """Overall system resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: List[float]
    timestamp: float


class AdminStatusService:
    """
    System Status Dashboard Service
    
    Provides environment-aware monitoring, health checks, and resource metrics
    for all three environments (DEV/TEST/PROD) with proper isolation.
    """
    
    def __init__(self):
        self.environment_configs = {
            'dev': {'port': 8000, 'websocket_port': 9000},
            'test': {'port': 8181, 'websocket_port': 9181}, 
            'prod': {'port': 8282, 'websocket_port': 9282}
        }
        self.start_time = time.time()
        
        logger.info("Admin Status Service initialized")
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """
        Get complete system status overview
        
        Returns:
            Dictionary with environment statuses and system metrics
        """
        try:
            environments = []
            for env_name in ['dev', 'test', 'prod']:
                env_status = await self.check_environment_health(env_name)
                environments.append(asdict(env_status))
            
            system_metrics = self.get_system_metrics()
            
            return {
                "timestamp": time.time(),
                "service_uptime_seconds": time.time() - self.start_time,
                "environments": environments,
                "system_metrics": asdict(system_metrics),
                "overall_status": self._calculate_overall_status(environments)
            }
            
        except Exception as e:
            logger.error(f"Error getting system overview: {e}")
            raise
    
    async def check_environment_health(self, env_name: str) -> EnvironmentStatus:
        """
        Check health status of a specific environment
        
        Args:
            env_name: Environment name (dev/test/prod)
            
        Returns:
            EnvironmentStatus with current health information
        """
        try:
            config = self.environment_configs.get(env_name, {})
            port = config.get('port', 0)
            websocket_port = config.get('websocket_port', 0)
            
            # Check environment directory structure
            env_path = Path(f"env/{env_name}")
            has_structure = all(
                (env_path / subdir).exists() 
                for subdir in ['code', 'config', 'data', 'logs']
            )
            
            if not has_structure:
                return EnvironmentStatus(
                    name=env_name,
                    port=port,
                    websocket_port=websocket_port,
                    is_active=False,
                    uptime_seconds=None,
                    process_id=None,
                    memory_mb=None,
                    cpu_percent=None,
                    last_health_check=time.time(),
                    error_message=f"Environment directory structure missing: {env_path}"
                )
            
            # Check port configuration
            ports_file = env_path / "config" / "ports.json"
            if ports_file.exists():
                try:
                    ports_config = json.loads(ports_file.read_text())
                    port = ports_config.get('http_port', port)
                    websocket_port = ports_config.get('websocket_port', websocket_port)
                except Exception as e:
                    logger.warning(f"Could not read ports config for {env_name}: {e}")
            
            # Check if service is running (simplified check)
            is_active = self._check_port_in_use(port)
            
            # Get process information if running
            process_id = None
            memory_mb = None
            cpu_percent = None
            uptime_seconds = None
            
            if is_active:
                # In a real implementation, you'd get actual process stats
                # For now, we'll use placeholder values
                process_id = os.getpid()  # Placeholder
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                cpu_percent = psutil.Process().cpu_percent()
                uptime_seconds = time.time() - self.start_time
            
            return EnvironmentStatus(
                name=env_name,
                port=port,
                websocket_port=websocket_port,
                is_active=is_active,
                uptime_seconds=uptime_seconds,
                process_id=process_id,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                last_health_check=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error checking environment {env_name} health: {e}")
            return EnvironmentStatus(
                name=env_name,
                port=config.get('port', 0),
                websocket_port=config.get('websocket_port', 0),
                is_active=False,
                uptime_seconds=None,
                process_id=None,
                memory_mb=None,
                cpu_percent=None,
                last_health_check=time.time(),
                error_message=str(e)
            )
    
    def get_system_metrics(self) -> SystemMetrics:
        """
        Get current system resource metrics
        
        Returns:
            SystemMetrics with CPU, memory, disk usage
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Load average (Unix only)
            try:
                load_avg = list(os.getloadavg())
            except (OSError, AttributeError):
                # Windows doesn't have getloadavg
                load_avg = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                load_average=load_avg,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                load_average=[0.0, 0.0, 0.0],
                timestamp=time.time()
            )
    
    async def get_environment_logs(self, env_name: str, lines: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent log entries for an environment
        
        Args:
            env_name: Environment name
            lines: Number of recent lines to retrieve
            
        Returns:
            List of log entries with timestamps and messages
        """
        try:
            log_file = Path(f"env/{env_name}/logs/app.log")
            
            if not log_file.exists():
                return []
            
            # Read last N lines from log file
            log_entries = []
            with open(log_file, 'r', encoding='utf-8') as f:
                # Simple tail implementation
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                for line in recent_lines:
                    try:
                        # Try to parse as JSON log entry
                        log_data = json.loads(line.strip())
                        log_entries.append(log_data)
                    except json.JSONDecodeError:
                        # Fall back to plain text
                        log_entries.append({
                            "timestamp": time.time(),
                            "level": "INFO",
                            "message": line.strip(),
                            "environment": env_name
                        })
            
            return log_entries
            
        except Exception as e:
            logger.error(f"Error getting logs for {env_name}: {e}")
            return []
    
    async def get_environment_artifacts(self, env_name: str) -> List[Dict[str, Any]]:
        """
        Get artifact information for an environment
        
        Args:
            env_name: Environment name
            
        Returns:
            List of artifacts with metadata
        """
        try:
            artifacts_path = Path(f"artifacts/{env_name}")
            
            if not artifacts_path.exists():
                return []
            
            artifacts = []
            for item in artifacts_path.rglob('*'):
                if item.is_file() and item.name.endswith('.json'):
                    try:
                        stat = item.stat()
                        artifacts.append({
                            "path": str(item.relative_to(artifacts_path)),
                            "name": item.name,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                            "type": "artifact"
                        })
                    except Exception as e:
                        logger.warning(f"Could not read artifact {item}: {e}")
            
            return sorted(artifacts, key=lambda x: x['modified_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting artifacts for {env_name}: {e}")
            return []
    
    def _check_port_in_use(self, port: int) -> bool:
        """
        Check if a port is currently in use
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is in use, False otherwise
        """
        try:
            connections = psutil.net_connections(kind='inet')
            for conn in connections:
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Could not check port {port}: {e}")
            return False
    
    def _calculate_overall_status(self, environments: List[Dict[str, Any]]) -> str:
        """
        Calculate overall system status from environment statuses
        
        Args:
            environments: List of environment status dictionaries
            
        Returns:
            Overall status string: 'healthy', 'degraded', or 'critical'
        """
        active_count = sum(1 for env in environments if env.get('is_active', False))
        total_count = len(environments)
        
        if active_count == total_count:
            return 'healthy'
        elif active_count > 0:
            return 'degraded' 
        else:
            return 'critical'