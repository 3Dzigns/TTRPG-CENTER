"""
HGRN Runner

Main execution interface for HGRN validation as Pass D in the ingestion pipeline.
Coordinates validation execution and report generation.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .models import HGRNReport
from .validator import HGRNValidator
from ..ttrpg_logging import get_logger
from ..aehrl.evaluator import AEHRLEvaluator
from ..aehrl.correction_manager import CorrectionManager

logger = get_logger(__name__)


class HGRNRunner:
    """
    Main HGRN execution interface.

    Coordinates HGRN validation as Pass D in the ingestion pipeline,
    managing configuration, execution, and report persistence.
    """

    def __init__(self, environment: str = "dev"):
        """
        Initialize HGRN runner.

        Args:
            environment: Environment (dev/test/prod)
        """
        self.environment = environment
        self.hgrn_enabled = self._get_hgrn_config()

        # Configuration from environment
        self.confidence_threshold = float(os.getenv("HGRN_CONFIDENCE_THRESHOLD", "0.7"))
        self.timeout_seconds = int(os.getenv("HGRN_TIMEOUT_SECONDS", "300"))
        self.package_version = os.getenv("HGRN_PACKAGE_VERSION", "1.2.3")

        logger.info(
            f"HGRN Runner initialized for {environment} environment. "
            f"Enabled: {self.hgrn_enabled}, "
            f"Confidence threshold: {self.confidence_threshold}, "
            f"Timeout: {self.timeout_seconds}s"
        )

    def _get_hgrn_config(self) -> bool:
        """Get HGRN enabled status from environment configuration."""
        hgrn_enabled_str = os.getenv("HGRN_ENABLED", "false").lower()
        return hgrn_enabled_str == "true"

    def run_pass_d_validation(
        self,
        job_id: str,
        artifacts_path: Path,
        output_path: Optional[Path] = None
    ) -> HGRNReport:
        """
        Execute HGRN validation as Pass D.

        Args:
            job_id: Ingestion job identifier
            artifacts_path: Path to job artifacts directory
            output_path: Optional path for report output (defaults to artifacts_path)

        Returns:
            HGRN validation report
        """
        logger.info(f"Starting Pass D HGRN validation for job {job_id}")

        if not self.hgrn_enabled:
            logger.info(f"HGRN disabled for environment {self.environment}, skipping validation")
            return self._create_disabled_report(job_id)

        try:
            # Validate artifacts path exists
            if not artifacts_path.exists():
                raise FileNotFoundError(f"Artifacts path not found: {artifacts_path}")

            # Initialize validator
            validator = HGRNValidator(
                confidence_threshold=self.confidence_threshold,
                timeout_seconds=self.timeout_seconds
            )

            # Run validation
            report = validator.validate_artifacts(
                job_id=job_id,
                environment=self.environment,
                artifacts_path=artifacts_path
            )

            # Run AEHRL evaluation on ingestion artifacts (if enabled)
            aehrl_enabled = os.getenv("AEHRL_ENABLED", "true").lower() == "true"
            if aehrl_enabled:
                try:
                    logger.info(f"Running AEHRL evaluation for ingestion job {job_id}")

                    aehrl_evaluator = AEHRLEvaluator(environment=self.environment)
                    aehrl_report = aehrl_evaluator.evaluate_ingestion_artifacts(
                        job_id=job_id,
                        artifacts_path=artifacts_path,
                        hgrn_report=report.to_dict() if report else None
                    )

                    # Store correction recommendations
                    if aehrl_report.correction_recommendations:
                        correction_manager = CorrectionManager(environment=self.environment)
                        correction_manager.store_recommendations(
                            recommendations=aehrl_report.correction_recommendations,
                            job_id=job_id
                        )

                    # Save AEHRL report
                    aehrl_report_file = output_path / "aehrl_report.json" if output_path else artifacts_path / "aehrl_report.json"
                    with open(aehrl_report_file, 'w', encoding='utf-8') as f:
                        json.dump(aehrl_report.to_dict(), f, indent=2)

                    logger.info(
                        f"AEHRL evaluation completed for job {job_id}. "
                        f"Generated {len(aehrl_report.correction_recommendations)} correction recommendations"
                    )

                except Exception as e:
                    logger.warning(f"AEHRL evaluation failed for job {job_id}: {str(e)}")

            # Save report
            if output_path is None:
                output_path = artifacts_path

            report_file = output_path / "hgrn_report.json"
            self._save_report(report, report_file)

            logger.info(
                f"Pass D HGRN validation completed for job {job_id}. "
                f"Status: {report.status}, "
                f"Recommendations: {len(report.recommendations)}, "
                f"Report saved to: {report_file}"
            )

            return report

        except Exception as e:
            logger.error(f"Pass D HGRN validation failed for job {job_id}: {str(e)}")
            error_report = HGRNReport(
                job_id=job_id,
                environment=self.environment,
                status="failed",
                error_message=str(e),
                hgrn_enabled=self.hgrn_enabled
            )

            # Still save error report for debugging
            if output_path is None:
                output_path = artifacts_path

            report_file = output_path / "hgrn_report.json"
            self._save_report(error_report, report_file)

            return error_report

    def _create_disabled_report(self, job_id: str) -> HGRNReport:
        """Create a report indicating HGRN was disabled."""
        return HGRNReport(
            job_id=job_id,
            environment=self.environment,
            status="disabled",
            hgrn_enabled=False,
            error_message="HGRN validation disabled for this environment"
        )

    def _save_report(self, report: HGRNReport, report_file: Path) -> None:
        """Save HGRN report to JSON file."""
        try:
            # Ensure output directory exists
            report_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert report to dict and save
            report_data = report.to_dict()

            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"HGRN report saved to {report_file}")

        except Exception as e:
            logger.error(f"Failed to save HGRN report to {report_file}: {str(e)}")
            raise

    def load_report(self, report_file: Path) -> Optional[HGRNReport]:
        """
        Load HGRN report from JSON file.

        Args:
            report_file: Path to hgrn_report.json file

        Returns:
            HGRN report or None if file doesn't exist or is invalid
        """
        try:
            if not report_file.exists():
                logger.warning(f"HGRN report file not found: {report_file}")
                return None

            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)

            report = HGRNReport.from_dict(report_data)
            logger.debug(f"HGRN report loaded from {report_file}")
            return report

        except Exception as e:
            logger.error(f"Failed to load HGRN report from {report_file}: {str(e)}")
            return None

    def get_job_recommendations(
        self,
        job_id: str,
        artifacts_path: Path
    ) -> Optional[HGRNReport]:
        """
        Get HGRN recommendations for a specific job.

        Args:
            job_id: Ingestion job identifier
            artifacts_path: Path to job artifacts directory

        Returns:
            HGRN report with recommendations or None if not found
        """
        report_file = artifacts_path / "hgrn_report.json"
        return self.load_report(report_file)

    def update_recommendation_status(
        self,
        job_id: str,
        artifacts_path: Path,
        recommendation_id: str,
        accepted: bool,
        rejected: bool = False
    ) -> bool:
        """
        Update the status of a specific recommendation.

        Args:
            job_id: Ingestion job identifier
            artifacts_path: Path to job artifacts directory
            recommendation_id: ID of recommendation to update
            accepted: Whether recommendation was accepted
            rejected: Whether recommendation was rejected

        Returns:
            True if update successful, False otherwise
        """
        try:
            report_file = artifacts_path / "hgrn_report.json"
            report = self.load_report(report_file)

            if not report:
                logger.error(f"Could not load HGRN report for job {job_id}")
                return False

            # Find and update recommendation
            updated = False
            for rec in report.recommendations:
                if rec.id == recommendation_id:
                    rec.accepted = accepted
                    rec.rejected = rejected
                    updated = True
                    break

            if not updated:
                logger.warning(f"Recommendation {recommendation_id} not found in job {job_id}")
                return False

            # Save updated report
            self._save_report(report, report_file)

            logger.info(
                f"Updated recommendation {recommendation_id} for job {job_id}: "
                f"accepted={accepted}, rejected={rejected}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to update recommendation {recommendation_id} for job {job_id}: {str(e)}"
            )
            return False

    def get_environment_stats(self) -> Dict[str, Any]:
        """
        Get HGRN environment statistics.

        Returns:
            Dictionary with HGRN configuration and status
        """
        return {
            "environment": self.environment,
            "hgrn_enabled": self.hgrn_enabled,
            "confidence_threshold": self.confidence_threshold,
            "timeout_seconds": self.timeout_seconds,
            "package_version": self.package_version,
            "config_source": {
                "HGRN_ENABLED": os.getenv("HGRN_ENABLED", "not_set"),
                "HGRN_CONFIDENCE_THRESHOLD": os.getenv("HGRN_CONFIDENCE_THRESHOLD", "not_set"),
                "HGRN_TIMEOUT_SECONDS": os.getenv("HGRN_TIMEOUT_SECONDS", "not_set"),
                "HGRN_PACKAGE_VERSION": os.getenv("HGRN_PACKAGE_VERSION", "not_set")
            }
        }