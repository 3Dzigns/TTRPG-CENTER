"""
AEHRL Metrics Tracker

Tracks hallucination metrics over time and provides alerting capabilities.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import asdict

from .models import AEHRLMetrics, AEHRLReport
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class MetricsTracker:
    """
    Tracks AEHRL metrics over time and provides alerting.

    Maintains metrics history, calculates trends, and triggers alerts
    when hallucination rates exceed configured thresholds.
    """

    def __init__(
        self,
        environment: str = "dev",
        metrics_storage_path: Optional[Path] = None,
        hallucination_alert_threshold: float = 0.05
    ):
        """
        Initialize metrics tracker.

        Args:
            environment: Environment name
            metrics_storage_path: Path to store metrics history
            hallucination_alert_threshold: Threshold for hallucination alerts (5%)
        """
        self.environment = environment
        self.hallucination_alert_threshold = hallucination_alert_threshold

        if metrics_storage_path:
            self.metrics_storage_path = metrics_storage_path
        else:
            self.metrics_storage_path = Path(f"artifacts/{environment}/aehrl_metrics")

        self.metrics_storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"AEHRL Metrics Tracker initialized for {environment}")

    def record_metrics(self, report: AEHRLReport) -> None:
        """
        Record metrics from an AEHRL report.

        Args:
            report: AEHRL evaluation report containing metrics
        """
        try:
            if not report.metrics:
                logger.warning(f"No metrics found in report for {report.query_id or report.job_id}")
                return

            # Store individual metric record
            self._store_metric_record(report.metrics)

            # Check for alert conditions
            self._check_alert_conditions(report.metrics)

            # Update aggregated metrics
            self._update_aggregated_metrics(report.metrics)

            logger.debug(f"Recorded metrics for {report.metrics.query_id}")

        except Exception as e:
            logger.error(f"Error recording metrics: {str(e)}")

    def _store_metric_record(self, metrics: AEHRLMetrics) -> None:
        """Store individual metric record to disk."""
        try:
            # Create daily metrics file
            date_str = metrics.timestamp.strftime("%Y-%m-%d")
            metrics_file = self.metrics_storage_path / f"metrics_{date_str}.jsonl"

            # Convert metrics to dict for storage
            metrics_dict = {
                "query_id": metrics.query_id,
                "support_rate": metrics.support_rate,
                "hallucination_rate": metrics.hallucination_rate,
                "citation_accuracy": metrics.citation_accuracy,
                "total_claims": metrics.total_claims,
                "flagged_claims": metrics.flagged_claims,
                "processing_time_ms": metrics.processing_time_ms,
                "confidence_threshold": metrics.confidence_threshold,
                "timestamp": metrics.timestamp.isoformat(),
                "environment": self.environment,
                "metadata": metrics.metadata
            }

            # Append to JSONL file
            with open(metrics_file, 'a', encoding='utf-8') as f:
                json.dump(metrics_dict, f)
                f.write('\n')

        except Exception as e:
            logger.error(f"Error storing metric record: {str(e)}")

    def _check_alert_conditions(self, metrics: AEHRLMetrics) -> None:
        """Check if metrics trigger any alert conditions."""
        try:
            alerts = []

            # Check hallucination rate threshold
            if metrics.hallucination_rate > self.hallucination_alert_threshold:
                alerts.append({
                    "type": "hallucination_rate_exceeded",
                    "message": f"Hallucination rate {metrics.hallucination_rate:.2%} exceeds threshold {self.hallucination_alert_threshold:.2%}",
                    "severity": "high" if metrics.hallucination_rate > 0.1 else "medium",
                    "query_id": metrics.query_id,
                    "metrics": asdict(metrics)
                })

            # Check for low support rate
            if metrics.support_rate < 0.5:
                alerts.append({
                    "type": "low_support_rate",
                    "message": f"Support rate {metrics.support_rate:.2%} is critically low",
                    "severity": "high",
                    "query_id": metrics.query_id,
                    "metrics": asdict(metrics)
                })

            # Check for high processing time
            if metrics.processing_time_ms > 5000:  # 5 seconds
                alerts.append({
                    "type": "high_processing_time",
                    "message": f"Processing time {metrics.processing_time_ms:.0f}ms exceeds performance target",
                    "severity": "medium",
                    "query_id": metrics.query_id,
                    "metrics": asdict(metrics)
                })

            # Store alerts
            if alerts:
                self._store_alerts(alerts)

        except Exception as e:
            logger.error(f"Error checking alert conditions: {str(e)}")

    def _store_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Store alerts to disk and log them."""
        try:
            alert_file = self.metrics_storage_path / "alerts.jsonl"

            for alert in alerts:
                alert["timestamp"] = datetime.now().isoformat()
                alert["environment"] = self.environment

                # Log alert
                severity = alert["severity"]
                message = alert["message"]
                if severity == "high":
                    logger.warning(f"AEHRL Alert: {message}")
                else:
                    logger.info(f"AEHRL Alert: {message}")

                # Store to file
                with open(alert_file, 'a', encoding='utf-8') as f:
                    json.dump(alert, f)
                    f.write('\n')

        except Exception as e:
            logger.error(f"Error storing alerts: {str(e)}")

    def _update_aggregated_metrics(self, metrics: AEHRLMetrics) -> None:
        """Update aggregated metrics for dashboard display."""
        try:
            # Load existing aggregated metrics
            agg_file = self.metrics_storage_path / "aggregated_metrics.json"

            if agg_file.exists():
                with open(agg_file, 'r', encoding='utf-8') as f:
                    agg_data = json.load(f)
            else:
                agg_data = {
                    "daily": {},
                    "hourly": {},
                    "overall": {
                        "total_queries": 0,
                        "total_claims": 0,
                        "total_flagged": 0,
                        "avg_hallucination_rate": 0.0,
                        "avg_support_rate": 0.0,
                        "avg_processing_time": 0.0
                    }
                }

            # Update daily aggregation
            date_key = metrics.timestamp.strftime("%Y-%m-%d")
            if date_key not in agg_data["daily"]:
                agg_data["daily"][date_key] = {
                    "queries": 0,
                    "total_claims": 0,
                    "flagged_claims": 0,
                    "total_processing_time": 0.0,
                    "hallucination_rates": [],
                    "support_rates": []
                }

            daily = agg_data["daily"][date_key]
            daily["queries"] += 1
            daily["total_claims"] += metrics.total_claims
            daily["flagged_claims"] += metrics.flagged_claims
            daily["total_processing_time"] += metrics.processing_time_ms
            daily["hallucination_rates"].append(metrics.hallucination_rate)
            daily["support_rates"].append(metrics.support_rate)

            # Calculate daily averages
            daily["avg_hallucination_rate"] = sum(daily["hallucination_rates"]) / len(daily["hallucination_rates"])
            daily["avg_support_rate"] = sum(daily["support_rates"]) / len(daily["support_rates"])
            daily["avg_processing_time"] = daily["total_processing_time"] / daily["queries"]

            # Update hourly aggregation
            hour_key = metrics.timestamp.strftime("%Y-%m-%d-%H")
            if hour_key not in agg_data["hourly"]:
                agg_data["hourly"][hour_key] = {
                    "queries": 0,
                    "avg_hallucination_rate": 0.0,
                    "avg_support_rate": 0.0
                }

            # Update overall statistics
            overall = agg_data["overall"]
            total_queries = overall["total_queries"] + 1

            # Running averages
            overall["avg_hallucination_rate"] = (
                (overall["avg_hallucination_rate"] * overall["total_queries"]) + metrics.hallucination_rate
            ) / total_queries

            overall["avg_support_rate"] = (
                (overall["avg_support_rate"] * overall["total_queries"]) + metrics.support_rate
            ) / total_queries

            overall["avg_processing_time"] = (
                (overall["avg_processing_time"] * overall["total_queries"]) + metrics.processing_time_ms
            ) / total_queries

            overall["total_queries"] = total_queries
            overall["total_claims"] += metrics.total_claims
            overall["total_flagged"] += metrics.flagged_claims

            # Save updated aggregated metrics
            with open(agg_file, 'w', encoding='utf-8') as f:
                json.dump(agg_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating aggregated metrics: {str(e)}")

    def get_metrics_summary(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Get metrics summary for the specified time period.

        Args:
            days_back: Number of days to include in summary

        Returns:
            Dictionary containing metrics summary
        """
        try:
            # Load aggregated metrics
            agg_file = self.metrics_storage_path / "aggregated_metrics.json"

            if not agg_file.exists():
                return {
                    "error": "No metrics data available",
                    "total_queries": 0,
                    "avg_hallucination_rate": 0.0,
                    "avg_support_rate": 0.0
                }

            with open(agg_file, 'r', encoding='utf-8') as f:
                agg_data = json.load(f)

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Filter daily data for time period
            period_data = {}
            for date_str, data in agg_data["daily"].items():
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if start_date <= date_obj <= end_date:
                    period_data[date_str] = data

            # Calculate period summary
            if not period_data:
                return {
                    "error": f"No data available for last {days_back} days",
                    "total_queries": 0,
                    "avg_hallucination_rate": 0.0,
                    "avg_support_rate": 0.0
                }

            total_queries = sum(data["queries"] for data in period_data.values())
            total_claims = sum(data["total_claims"] for data in period_data.values())
            total_flagged = sum(data["flagged_claims"] for data in period_data.values())

            # Calculate weighted averages
            weighted_hall_rate = sum(
                data["avg_hallucination_rate"] * data["queries"]
                for data in period_data.values()
            ) / total_queries if total_queries > 0 else 0.0

            weighted_support_rate = sum(
                data["avg_support_rate"] * data["queries"]
                for data in period_data.values()
            ) / total_queries if total_queries > 0 else 0.0

            avg_processing_time = sum(
                data["avg_processing_time"] * data["queries"]
                for data in period_data.values()
            ) / total_queries if total_queries > 0 else 0.0

            return {
                "period_days": days_back,
                "total_queries": total_queries,
                "total_claims": total_claims,
                "total_flagged": total_flagged,
                "avg_hallucination_rate": weighted_hall_rate,
                "avg_support_rate": weighted_support_rate,
                "avg_processing_time": avg_processing_time,
                "daily_breakdown": period_data,
                "overall_stats": agg_data["overall"],
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            return {
                "error": str(e),
                "total_queries": 0,
                "avg_hallucination_rate": 0.0,
                "avg_support_rate": 0.0
            }

    def get_recent_alerts(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent alerts within the specified time period.

        Args:
            hours_back: Number of hours to look back for alerts

        Returns:
            List of recent alerts
        """
        try:
            alert_file = self.metrics_storage_path / "alerts.jsonl"

            if not alert_file.exists():
                return []

            # Calculate cutoff time
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            recent_alerts = []
            with open(alert_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        alert = json.loads(line.strip())
                        alert_time = datetime.fromisoformat(alert["timestamp"])

                        if alert_time >= cutoff_time:
                            recent_alerts.append(alert)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            # Sort by timestamp (newest first)
            recent_alerts.sort(key=lambda x: x["timestamp"], reverse=True)

            return recent_alerts

        except Exception as e:
            logger.error(f"Error getting recent alerts: {str(e)}")
            return []

    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """
        Clean up old metrics data to manage storage.

        Args:
            days_to_keep: Number of days of data to keep
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")

            # Clean up daily metrics files
            for metrics_file in self.metrics_storage_path.glob("metrics_*.jsonl"):
                try:
                    # Extract date from filename
                    date_part = metrics_file.stem.replace("metrics_", "")
                    if date_part < cutoff_str:
                        metrics_file.unlink()
                        logger.info(f"Removed old metrics file: {metrics_file}")
                except Exception as e:
                    logger.warning(f"Error removing old file {metrics_file}: {str(e)}")

            # Clean up aggregated data
            agg_file = self.metrics_storage_path / "aggregated_metrics.json"
            if agg_file.exists():
                with open(agg_file, 'r', encoding='utf-8') as f:
                    agg_data = json.load(f)

                # Remove old daily data
                for date_str in list(agg_data["daily"].keys()):
                    if date_str < cutoff_str:
                        del agg_data["daily"][date_str]

                # Remove old hourly data
                cutoff_hour = cutoff_date.strftime("%Y-%m-%d-%H")
                for hour_str in list(agg_data["hourly"].keys()):
                    if hour_str < cutoff_hour:
                        del agg_data["hourly"][hour_str]

                # Save cleaned data
                with open(agg_file, 'w', encoding='utf-8') as f:
                    json.dump(agg_data, f, indent=2)

            logger.info(f"Cleaned up metrics data older than {days_to_keep} days")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}")