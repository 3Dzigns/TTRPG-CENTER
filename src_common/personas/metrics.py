"""
Persona metrics tracking and reporting system.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from .models import PersonaMetrics, PersonaProfile
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class PersonaMetricsTracker:
    """Tracks and analyzes persona-specific performance metrics."""

    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.metrics_dir = Path("artifacts") / "persona_metrics" / environment
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache for recent metrics
        self.metrics_cache: List[PersonaMetrics] = []
        self.max_cache_size = 1000

        # Alert thresholds
        self.alert_thresholds = {
            "appropriateness_score": 0.7,
            "detail_level_match": 0.6,
            "user_satisfaction_predicted": 0.7,
            "hallucination_rate": 0.1,
            "inappropriate_content_rate": 0.05
        }

    def record_metrics(self, metrics: PersonaMetrics) -> None:
        """Record persona metrics."""
        try:
            # Add to cache
            self.metrics_cache.append(metrics)
            if len(self.metrics_cache) > self.max_cache_size:
                self.metrics_cache.pop(0)

            # Persist to disk
            self._persist_metrics(metrics)

            # Check for alerts
            self._check_alerts(metrics)

            logger.info(f"Recorded persona metrics for {metrics.persona_id}")

        except Exception as e:
            logger.error(f"Failed to record persona metrics: {e}")

    def _persist_metrics(self, metrics: PersonaMetrics) -> None:
        """Persist metrics to JSON file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        metrics_file = self.metrics_dir / f"persona_metrics_{date_str}.json"

        # Load existing metrics for the day
        daily_metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    daily_metrics = json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing metrics: {e}")

        # Add new metrics
        daily_metrics.append(metrics.to_dict())

        # Save back to file
        try:
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(daily_metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving metrics to {metrics_file}: {e}")

    def _check_alerts(self, metrics: PersonaMetrics) -> None:
        """Check metrics against alert thresholds."""
        alerts = []

        if metrics.appropriateness_score < self.alert_thresholds["appropriateness_score"]:
            alerts.append({
                "type": "low_appropriateness",
                "persona_id": metrics.persona_id,
                "value": metrics.appropriateness_score,
                "threshold": self.alert_thresholds["appropriateness_score"],
                "timestamp": datetime.now().isoformat()
            })

        if metrics.detail_level_match < self.alert_thresholds["detail_level_match"]:
            alerts.append({
                "type": "detail_level_mismatch",
                "persona_id": metrics.persona_id,
                "value": metrics.detail_level_match,
                "threshold": self.alert_thresholds["detail_level_match"],
                "timestamp": datetime.now().isoformat()
            })

        if metrics.user_satisfaction_predicted < self.alert_thresholds["user_satisfaction_predicted"]:
            alerts.append({
                "type": "low_satisfaction",
                "persona_id": metrics.persona_id,
                "value": metrics.user_satisfaction_predicted,
                "threshold": self.alert_thresholds["user_satisfaction_predicted"],
                "timestamp": datetime.now().isoformat()
            })

        if metrics.has_hallucinations:
            alerts.append({
                "type": "hallucination_detected",
                "persona_id": metrics.persona_id,
                "timestamp": datetime.now().isoformat()
            })

        if metrics.has_inappropriate_content:
            alerts.append({
                "type": "inappropriate_content",
                "persona_id": metrics.persona_id,
                "timestamp": datetime.now().isoformat()
            })

        # Store alerts if any
        if alerts:
            self._store_alerts(alerts)

    def _store_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Store alerts to file."""
        alerts_file = self.metrics_dir / "alerts.json"

        existing_alerts = []
        if alerts_file.exists():
            try:
                with open(alerts_file, 'r', encoding='utf-8') as f:
                    existing_alerts = json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing alerts: {e}")

        existing_alerts.extend(alerts)

        try:
            with open(alerts_file, 'w', encoding='utf-8') as f:
                json.dump(existing_alerts, f, indent=2, ensure_ascii=False)

            logger.warning(f"Generated {len(alerts)} persona alerts")
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")

    def get_metrics_summary(self, days_back: int = 7) -> Dict[str, Any]:
        """Get aggregated metrics summary for the specified time period."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            metrics = self._load_metrics_since(cutoff_date)

            if not metrics:
                return {
                    "total_queries": 0,
                    "persona_count": 0,
                    "avg_appropriateness_score": 0.0,
                    "avg_satisfaction_score": 0.0,
                    "error": "No metrics data available"
                }

            # Calculate aggregate statistics
            total_queries = len(metrics)
            unique_personas = len(set(m["persona_id"] for m in metrics))

            avg_appropriateness = sum(m["appropriateness_score"] for m in metrics) / total_queries
            avg_satisfaction = sum(m["user_satisfaction_predicted"] for m in metrics) / total_queries
            avg_detail_match = sum(m["detail_level_match"] for m in metrics) / total_queries
            avg_language_appropriateness = sum(m["language_appropriateness"] for m in metrics) / total_queries

            hallucination_count = sum(1 for m in metrics if m["has_hallucinations"])
            inappropriate_count = sum(1 for m in metrics if m["has_inappropriate_content"])

            # Per-persona breakdown
            persona_stats = defaultdict(list)
            for m in metrics:
                persona_stats[m["persona_id"]].append(m)

            persona_summary = {}
            for persona_id, persona_metrics in persona_stats.items():
                persona_summary[persona_id] = {
                    "query_count": len(persona_metrics),
                    "avg_appropriateness": sum(m["appropriateness_score"] for m in persona_metrics) / len(persona_metrics),
                    "avg_satisfaction": sum(m["user_satisfaction_predicted"] for m in persona_metrics) / len(persona_metrics),
                    "hallucination_rate": sum(1 for m in persona_metrics if m["has_hallucinations"]) / len(persona_metrics)
                }

            return {
                "period_days": days_back,
                "total_queries": total_queries,
                "persona_count": unique_personas,
                "avg_appropriateness_score": round(avg_appropriateness, 3),
                "avg_satisfaction_score": round(avg_satisfaction, 3),
                "avg_detail_match": round(avg_detail_match, 3),
                "avg_language_appropriateness": round(avg_language_appropriateness, 3),
                "hallucination_rate": round(hallucination_count / total_queries, 3),
                "inappropriate_content_rate": round(inappropriate_count / total_queries, 3),
                "persona_breakdown": persona_summary,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating metrics summary: {e}")
            return {
                "error": f"Failed to generate metrics summary: {str(e)}",
                "total_queries": 0,
                "persona_count": 0,
                "avg_appropriateness_score": 0.0
            }

    def _load_metrics_since(self, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Load all metrics since the cutoff date."""
        metrics = []

        # Check cache first
        for cached_metric in self.metrics_cache:
            if cached_metric.timestamp and cached_metric.timestamp >= cutoff_date:
                metrics.append(cached_metric.to_dict())

        # Load from disk for older metrics
        current_date = datetime.now()
        check_date = cutoff_date

        while check_date <= current_date:
            date_str = check_date.strftime("%Y-%m-%d")
            metrics_file = self.metrics_dir / f"persona_metrics_{date_str}.json"

            if metrics_file.exists():
                try:
                    with open(metrics_file, 'r', encoding='utf-8') as f:
                        daily_metrics = json.load(f)
                        for metric in daily_metrics:
                            metric_timestamp = datetime.fromisoformat(metric["timestamp"])
                            if metric_timestamp >= cutoff_date:
                                metrics.append(metric)
                except Exception as e:
                    logger.error(f"Error loading metrics from {metrics_file}: {e}")

            check_date += timedelta(days=1)

        return metrics

    def get_recent_alerts(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        try:
            alerts_file = self.metrics_dir / "alerts.json"
            if not alerts_file.exists():
                return []

            with open(alerts_file, 'r', encoding='utf-8') as f:
                all_alerts = json.load(f)

            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            recent_alerts = []

            for alert in all_alerts:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if alert_time >= cutoff_time:
                    recent_alerts.append(alert)

            return recent_alerts

        except Exception as e:
            logger.error(f"Error loading recent alerts: {e}")
            return []

    def get_persona_performance(self, persona_id: str, days_back: int = 7) -> Dict[str, Any]:
        """Get performance metrics for a specific persona."""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        metrics = self._load_metrics_since(cutoff_date)

        persona_metrics = [m for m in metrics if m["persona_id"] == persona_id]

        if not persona_metrics:
            return {
                "persona_id": persona_id,
                "query_count": 0,
                "error": "No metrics found for this persona"
            }

        query_count = len(persona_metrics)
        avg_appropriateness = sum(m["appropriateness_score"] for m in persona_metrics) / query_count
        avg_satisfaction = sum(m["user_satisfaction_predicted"] for m in persona_metrics) / query_count
        avg_response_time = sum(m["response_time_ms"] for m in persona_metrics) / query_count

        return {
            "persona_id": persona_id,
            "query_count": query_count,
            "avg_appropriateness_score": round(avg_appropriateness, 3),
            "avg_satisfaction_score": round(avg_satisfaction, 3),
            "avg_response_time_ms": round(avg_response_time, 1),
            "hallucination_rate": sum(1 for m in persona_metrics if m["has_hallucinations"]) / query_count,
            "inappropriate_content_rate": sum(1 for m in persona_metrics if m["has_inappropriate_content"]) / query_count
        }

    def export_metrics_report(self, days_back: int = 30) -> str:
        """Export comprehensive metrics report."""
        summary = self.get_metrics_summary(days_back)
        alerts = self.get_recent_alerts(hours_back=days_back * 24)

        report = {
            "report_type": "persona_metrics",
            "environment": self.environment,
            "generated_at": datetime.now().isoformat(),
            "period_days": days_back,
            "summary": summary,
            "recent_alerts": alerts,
            "alert_thresholds": self.alert_thresholds
        }

        report_file = self.metrics_dir / f"persona_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported persona metrics report to {report_file}")
            return str(report_file)

        except Exception as e:
            logger.error(f"Error exporting metrics report: {e}")
            return ""

    def clear_old_metrics(self, days_to_keep: int = 90) -> None:
        """Clear old metrics files to manage disk space."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        for metrics_file in self.metrics_dir.glob("persona_metrics_*.json"):
            try:
                # Extract date from filename
                date_str = metrics_file.stem.split("_")[-1]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff_date:
                    metrics_file.unlink()
                    logger.info(f"Deleted old metrics file: {metrics_file}")

            except Exception as e:
                logger.error(f"Error processing metrics file {metrics_file}: {e}")