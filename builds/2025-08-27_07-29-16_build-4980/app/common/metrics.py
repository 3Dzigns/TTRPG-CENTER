import time
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)

@dataclass
class QueryMetrics:
    """Metrics for a single query"""
    query_id: str
    timestamp: float
    query: str
    query_type: str
    model_used: str
    latency_ms: int
    token_usage: Dict[str, int]
    success: bool
    user_id: str = "anonymous"
    session_id: str = ""
    sources_retrieved: int = 0
    error: str = ""

@dataclass
class PerformanceMetrics:
    """System performance metrics"""
    timestamp: float
    queries_per_minute: float
    avg_latency_ms: float
    success_rate: float
    active_sessions: int
    total_tokens_used: int
    vector_store_health: bool
    openai_health: bool

class MetricsCollector:
    """Real-time metrics collection and tracking"""
    
    def __init__(self, max_recent_queries: int = 1000):
        self.max_recent_queries = max_recent_queries
        self.recent_queries = deque(maxlen=max_recent_queries)
        self.session_data = defaultdict(list)
        self.performance_history = deque(maxlen=288)  # 24 hours at 5-min intervals
        self.lock = threading.Lock()
        
        # Metrics directory
        self.metrics_dir = Path("logs") / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Start background metrics calculation
        self._last_performance_calc = time.time()
    
    def record_query(self, 
                    query_id: str,
                    query: str,
                    query_type: str,
                    model_used: str,
                    latency_ms: int,
                    token_usage: Dict[str, int],
                    success: bool,
                    user_id: str = "anonymous",
                    session_id: str = "",
                    sources_retrieved: int = 0,
                    error: str = "") -> None:
        """Record metrics for a single query"""
        
        metrics = QueryMetrics(
            query_id=query_id,
            timestamp=time.time(),
            query=query[:100] + "..." if len(query) > 100 else query,  # Truncate for storage
            query_type=query_type,
            model_used=model_used,
            latency_ms=latency_ms,
            token_usage=token_usage,
            success=success,
            user_id=user_id,
            session_id=session_id,
            sources_retrieved=sources_retrieved,
            error=error
        )
        
        with self.lock:
            self.recent_queries.append(metrics)
            
            # Update session data
            if session_id:
                self.session_data[session_id].append(metrics)
                
                # Limit session history
                if len(self.session_data[session_id]) > 50:
                    self.session_data[session_id] = self.session_data[session_id][-50:]
        
        # Log query metrics
        logger.info(f"Query {query_id}: {latency_ms}ms, {token_usage.get('total', 0)} tokens, "
                   f"{'success' if success else 'failed'}")
        
        # Periodic performance calculation
        if time.time() - self._last_performance_calc > 300:  # Every 5 minutes
            self._calculate_performance_metrics()
            self._last_performance_calc = time.time()
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current real-time statistics"""
        with self.lock:
            if not self.recent_queries:
                return {
                    "total_queries": 0,
                    "queries_last_hour": 0,
                    "avg_latency_ms": 0,
                    "success_rate": 0.0,
                    "active_sessions": 0
                }
            
            now = time.time()
            hour_ago = now - 3600
            
            # Filter queries from last hour
            recent_hour = [q for q in self.recent_queries if q.timestamp > hour_ago]
            
            # Calculate statistics
            total_queries = len(self.recent_queries)
            queries_last_hour = len(recent_hour)
            
            if recent_hour:
                avg_latency = sum(q.latency_ms for q in recent_hour) / len(recent_hour)
                success_count = sum(1 for q in recent_hour if q.success)
                success_rate = success_count / len(recent_hour)
            else:
                avg_latency = 0
                success_rate = 0.0
            
            # Count active sessions (activity in last 30 minutes)
            session_cutoff = now - 1800
            active_sessions = sum(1 for session_queries in self.session_data.values()
                                if session_queries and session_queries[-1].timestamp > session_cutoff)
            
            return {
                "total_queries": total_queries,
                "queries_last_hour": queries_last_hour,
                "avg_latency_ms": round(avg_latency, 1),
                "success_rate": round(success_rate, 3),
                "active_sessions": active_sessions,
                "query_types": self._get_query_type_breakdown(recent_hour),
                "token_usage_last_hour": self._get_token_usage(recent_hour)
            }
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a specific session"""
        with self.lock:
            session_queries = self.session_data.get(session_id, [])
            
            if not session_queries:
                return {
                    "session_id": session_id,
                    "total_queries": 0,
                    "session_duration_minutes": 0,
                    "avg_latency_ms": 0,
                    "success_rate": 0.0
                }
            
            # Calculate session stats
            start_time = session_queries[0].timestamp
            end_time = session_queries[-1].timestamp
            duration_minutes = (end_time - start_time) / 60
            
            total_queries = len(session_queries)
            avg_latency = sum(q.latency_ms for q in session_queries) / total_queries
            success_count = sum(1 for q in session_queries if q.success)
            success_rate = success_count / total_queries
            
            total_tokens = sum(q.token_usage.get('total', 0) for q in session_queries)
            
            return {
                "session_id": session_id,
                "total_queries": total_queries,
                "session_duration_minutes": round(duration_minutes, 1),
                "avg_latency_ms": round(avg_latency, 1),
                "success_rate": round(success_rate, 3),
                "total_tokens": total_tokens,
                "query_types": self._get_query_type_breakdown(session_queries),
                "last_activity": session_queries[-1].timestamp
            }
    
    def get_performance_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get performance metrics history"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            recent_performance = [
                asdict(p) for p in self.performance_history 
                if p.timestamp > cutoff_time
            ]
        
        return recent_performance
    
    def _get_query_type_breakdown(self, queries: List[QueryMetrics]) -> Dict[str, int]:
        """Get breakdown of query types"""
        breakdown = defaultdict(int)
        for query in queries:
            breakdown[query.query_type] += 1
        return dict(breakdown)
    
    def _get_token_usage(self, queries: List[QueryMetrics]) -> Dict[str, int]:
        """Calculate total token usage"""
        total_prompt = sum(q.token_usage.get('prompt', 0) for q in queries)
        total_completion = sum(q.token_usage.get('completion', 0) for q in queries)
        total = sum(q.token_usage.get('total', 0) for q in queries)
        
        return {
            "prompt": total_prompt,
            "completion": total_completion,
            "total": total
        }
    
    def _calculate_performance_metrics(self):
        """Calculate and store performance metrics"""
        try:
            now = time.time()
            minute_ago = now - 60
            
            with self.lock:
                # Get queries from last minute
                recent_queries = [q for q in self.recent_queries if q.timestamp > minute_ago]
                
                # Calculate metrics
                queries_per_minute = len(recent_queries)
                
                if recent_queries:
                    avg_latency = sum(q.latency_ms for q in recent_queries) / len(recent_queries)
                    success_count = sum(1 for q in recent_queries if q.success)
                    success_rate = success_count / len(recent_queries)
                    total_tokens = sum(q.token_usage.get('total', 0) for q in recent_queries)
                else:
                    avg_latency = 0
                    success_rate = 1.0
                    total_tokens = 0
                
                # Count active sessions
                session_cutoff = now - 1800  # 30 minutes
                active_sessions = sum(1 for session_queries in self.session_data.values()
                                    if session_queries and session_queries[-1].timestamp > session_cutoff)
                
                # System health checks (simplified)
                vector_store_health = True  # TODO: Implement actual health check
                openai_health = True        # TODO: Implement actual health check
                
                # Create performance metrics
                perf_metrics = PerformanceMetrics(
                    timestamp=now,
                    queries_per_minute=queries_per_minute,
                    avg_latency_ms=avg_latency,
                    success_rate=success_rate,
                    active_sessions=active_sessions,
                    total_tokens_used=total_tokens,
                    vector_store_health=vector_store_health,
                    openai_health=openai_health
                )
                
                self.performance_history.append(perf_metrics)
            
            # Log performance metrics
            logger.info(f"Performance: {queries_per_minute} q/min, {avg_latency:.1f}ms avg, "
                       f"{success_rate:.1%} success, {active_sessions} active sessions")
            
        except Exception as e:
            logger.error(f"Failed to calculate performance metrics: {e}")
    
    def export_metrics(self, filename: Optional[str] = None) -> str:
        """Export recent metrics to JSON file"""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_export_{timestamp}.json"
        
        export_path = self.metrics_dir / filename
        
        try:
            with self.lock:
                export_data = {
                    "export_timestamp": time.time(),
                    "recent_queries": [asdict(q) for q in list(self.recent_queries)[-100:]],  # Last 100
                    "performance_history": [asdict(p) for p in list(self.performance_history)],
                    "session_summary": {
                        session_id: {
                            "query_count": len(queries),
                            "last_activity": queries[-1].timestamp if queries else 0
                        }
                        for session_id, queries in self.session_data.items()
                    },
                    "summary_stats": self.get_current_stats()
                }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Metrics exported to {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return ""
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove old session data to prevent memory bloat"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self.lock:
            sessions_to_remove = []
            
            for session_id, queries in self.session_data.items():
                if queries and queries[-1].timestamp < cutoff_time:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self.session_data[session_id]
            
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")

class QueryTimer:
    """Context manager for timing query execution"""
    
    def __init__(self, metrics_collector: MetricsCollector, query_id: str):
        self.metrics_collector = metrics_collector
        self.query_id = query_id
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = int((time.time() - self.start_time) * 1000)
            # The actual metrics recording should happen in the calling code
            # This just provides the timing capability
            pass

# Global metrics collector instance
_metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

def create_query_timer(query_id: str) -> QueryTimer:
    """Create a query timer for measuring execution time"""
    return QueryTimer(get_metrics_collector(), query_id)