"""
AEHRL Correction Manager

Manages correction recommendations and their application to the knowledge base.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import CorrectionRecommendation, CorrectionType
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class CorrectionManager:
    """
    Manages AEHRL correction recommendations.

    Handles storage, retrieval, and application of correction recommendations
    generated during ingestion and query evaluation.
    """

    def __init__(
        self,
        environment: str = "dev",
        corrections_storage_path: Optional[Path] = None
    ):
        """
        Initialize correction manager.

        Args:
            environment: Environment name
            corrections_storage_path: Path to store correction data
        """
        self.environment = environment

        if corrections_storage_path:
            self.corrections_storage_path = corrections_storage_path
        else:
            self.corrections_storage_path = Path(f"artifacts/{environment}/aehrl_corrections")

        self.corrections_storage_path.mkdir(parents=True, exist_ok=True)

        # Load pending corrections
        self.pending_corrections = self._load_pending_corrections()

        logger.info(f"AEHRL Correction Manager initialized for {environment}")

    def store_recommendations(
        self,
        recommendations: List[CorrectionRecommendation],
        job_id: Optional[str] = None
    ) -> None:
        """
        Store correction recommendations.

        Args:
            recommendations: List of correction recommendations
            job_id: Associated job ID for ingestion-time corrections
        """
        try:
            for recommendation in recommendations:
                self._store_recommendation(recommendation, job_id)

            # Update pending corrections cache
            self.pending_corrections = self._load_pending_corrections()

            logger.info(f"Stored {len(recommendations)} correction recommendations")

        except Exception as e:
            logger.error(f"Error storing recommendations: {str(e)}")

    def _store_recommendation(
        self,
        recommendation: CorrectionRecommendation,
        job_id: Optional[str] = None
    ) -> None:
        """Store individual correction recommendation."""
        try:
            # Create storage path based on type and date
            date_str = recommendation.created_at.strftime("%Y-%m-%d")
            type_dir = self.corrections_storage_path / recommendation.type.value / date_str
            type_dir.mkdir(parents=True, exist_ok=True)

            # Store recommendation
            rec_file = type_dir / f"{recommendation.id}.json"
            with open(rec_file, 'w', encoding='utf-8') as f:
                json.dump(recommendation.to_dict(), f, indent=2)

            # Add to pending index
            self._update_pending_index(recommendation)

            # Store audit entry
            self._log_recommendation_audit(recommendation, "created", job_id)

        except Exception as e:
            logger.error(f"Error storing recommendation {recommendation.id}: {str(e)}")

    def get_pending_recommendations(
        self,
        correction_type: Optional[CorrectionType] = None,
        job_id: Optional[str] = None
    ) -> List[CorrectionRecommendation]:
        """
        Get pending correction recommendations.

        Args:
            correction_type: Filter by correction type
            job_id: Filter by job ID

        Returns:
            List of pending recommendations
        """
        try:
            filtered_recommendations = []

            for rec in self.pending_corrections:
                # Apply filters
                if correction_type and rec.type != correction_type:
                    continue

                if job_id and rec.job_id != job_id:
                    continue

                filtered_recommendations.append(rec)

            # Sort by confidence (highest first) then by created date
            filtered_recommendations.sort(
                key=lambda x: (-x.confidence, x.created_at),
                reverse=False
            )

            return filtered_recommendations

        except Exception as e:
            logger.error(f"Error getting pending recommendations: {str(e)}")
            return []

    def accept_recommendation(
        self,
        recommendation_id: str,
        admin_user: str = "admin"
    ) -> bool:
        """
        Accept and apply a correction recommendation.

        Args:
            recommendation_id: ID of recommendation to accept
            admin_user: Username of admin accepting the recommendation

        Returns:
            True if successfully accepted and applied
        """
        try:
            # Find recommendation
            recommendation = self._find_recommendation(recommendation_id)
            if not recommendation:
                logger.warning(f"Recommendation {recommendation_id} not found")
                return False

            if recommendation.accepted or recommendation.rejected:
                logger.warning(f"Recommendation {recommendation_id} already processed")
                return False

            # Apply the correction
            success = self._apply_correction(recommendation)

            if success:
                # Mark as accepted
                recommendation.accepted = True
                recommendation.applied_at = datetime.now()
                recommendation.metadata["accepted_by"] = admin_user

                # Update stored recommendation
                self._update_stored_recommendation(recommendation)

                # Log audit entry
                self._log_recommendation_audit(
                    recommendation,
                    "accepted",
                    admin_user=admin_user
                )

                # Remove from pending cache
                self.pending_corrections = [
                    r for r in self.pending_corrections
                    if r.id != recommendation_id
                ]

                logger.info(f"Accepted recommendation {recommendation_id}")
                return True
            else:
                logger.error(f"Failed to apply correction for {recommendation_id}")
                return False

        except Exception as e:
            logger.error(f"Error accepting recommendation {recommendation_id}: {str(e)}")
            return False

    def reject_recommendation(
        self,
        recommendation_id: str,
        reason: str = "",
        admin_user: str = "admin"
    ) -> bool:
        """
        Reject a correction recommendation.

        Args:
            recommendation_id: ID of recommendation to reject
            reason: Reason for rejection
            admin_user: Username of admin rejecting the recommendation

        Returns:
            True if successfully rejected
        """
        try:
            # Find recommendation
            recommendation = self._find_recommendation(recommendation_id)
            if not recommendation:
                logger.warning(f"Recommendation {recommendation_id} not found")
                return False

            if recommendation.accepted or recommendation.rejected:
                logger.warning(f"Recommendation {recommendation_id} already processed")
                return False

            # Mark as rejected
            recommendation.rejected = True
            recommendation.metadata["rejected_by"] = admin_user
            recommendation.metadata["rejection_reason"] = reason

            # Update stored recommendation
            self._update_stored_recommendation(recommendation)

            # Log audit entry
            self._log_recommendation_audit(
                recommendation,
                "rejected",
                admin_user=admin_user,
                reason=reason
            )

            # Remove from pending cache
            self.pending_corrections = [
                r for r in self.pending_corrections
                if r.id != recommendation_id
            ]

            logger.info(f"Rejected recommendation {recommendation_id}")
            return True

        except Exception as e:
            logger.error(f"Error rejecting recommendation {recommendation_id}: {str(e)}")
            return False

    def _find_recommendation(self, recommendation_id: str) -> Optional[CorrectionRecommendation]:
        """Find a recommendation by ID."""
        # First check pending cache
        for rec in self.pending_corrections:
            if rec.id == recommendation_id:
                return rec

        # Search in storage
        for type_dir in self.corrections_storage_path.iterdir():
            if not type_dir.is_dir():
                continue

            for date_dir in type_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                rec_file = date_dir / f"{recommendation_id}.json"
                if rec_file.exists():
                    try:
                        with open(rec_file, 'r', encoding='utf-8') as f:
                            rec_data = json.load(f)
                        return CorrectionRecommendation.from_dict(rec_data)
                    except Exception as e:
                        logger.warning(f"Error loading recommendation {recommendation_id}: {str(e)}")

        return None

    def _apply_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """
        Apply a correction recommendation to the knowledge base.

        Args:
            recommendation: Correction to apply

        Returns:
            True if successfully applied
        """
        try:
            if recommendation.type == CorrectionType.DICTIONARY_UPDATE:
                return self._apply_dictionary_correction(recommendation)
            elif recommendation.type == CorrectionType.GRAPH_EDGE_FIX:
                return self._apply_graph_edge_correction(recommendation)
            elif recommendation.type == CorrectionType.GRAPH_NODE_FIX:
                return self._apply_graph_node_correction(recommendation)
            elif recommendation.type == CorrectionType.METADATA_CORRECTION:
                return self._apply_metadata_correction(recommendation)
            elif recommendation.type == CorrectionType.CHUNK_REVISION:
                return self._apply_chunk_correction(recommendation)
            else:
                logger.warning(f"Unknown correction type: {recommendation.type}")
                return False

        except Exception as e:
            logger.error(f"Error applying correction: {str(e)}")
            return False

    def _apply_dictionary_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """Apply dictionary correction."""
        try:
            # This would integrate with the dictionary service
            # For now, just log the action
            logger.info(
                f"Would apply dictionary correction: "
                f"Target={recommendation.target}, "
                f"Current={recommendation.current_value}, "
                f"Suggested={recommendation.suggested_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error applying dictionary correction: {str(e)}")
            return False

    def _apply_graph_edge_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """Apply graph edge correction."""
        try:
            # This would integrate with the graph service
            logger.info(
                f"Would apply graph edge correction: "
                f"Target={recommendation.target}, "
                f"Current={recommendation.current_value}, "
                f"Suggested={recommendation.suggested_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error applying graph edge correction: {str(e)}")
            return False

    def _apply_graph_node_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """Apply graph node correction."""
        try:
            # This would integrate with the graph service
            logger.info(
                f"Would apply graph node correction: "
                f"Target={recommendation.target}, "
                f"Current={recommendation.current_value}, "
                f"Suggested={recommendation.suggested_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error applying graph node correction: {str(e)}")
            return False

    def _apply_metadata_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """Apply metadata correction."""
        try:
            # This would update metadata in the appropriate service
            logger.info(
                f"Would apply metadata correction: "
                f"Target={recommendation.target}, "
                f"Current={recommendation.current_value}, "
                f"Suggested={recommendation.suggested_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error applying metadata correction: {str(e)}")
            return False

    def _apply_chunk_correction(self, recommendation: CorrectionRecommendation) -> bool:
        """Apply chunk revision correction."""
        try:
            # This would update the chunk content
            logger.info(
                f"Would apply chunk correction: "
                f"Target={recommendation.target}, "
                f"Current={recommendation.current_value}, "
                f"Suggested={recommendation.suggested_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error applying chunk correction: {str(e)}")
            return False

    def _load_pending_corrections(self) -> List[CorrectionRecommendation]:
        """Load all pending corrections from storage."""
        pending = []

        try:
            # Load from pending index if it exists
            index_file = self.corrections_storage_path / "pending_index.json"

            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)

                for rec_data in index_data.get("pending", []):
                    try:
                        rec = CorrectionRecommendation.from_dict(rec_data)
                        if not rec.accepted and not rec.rejected:
                            pending.append(rec)
                    except Exception as e:
                        logger.warning(f"Error loading pending recommendation: {str(e)}")
            else:
                # Rebuild index from stored files
                pending = self._rebuild_pending_index()

        except Exception as e:
            logger.error(f"Error loading pending corrections: {str(e)}")

        return pending

    def _rebuild_pending_index(self) -> List[CorrectionRecommendation]:
        """Rebuild pending index by scanning all stored corrections."""
        pending = []

        try:
            for type_dir in self.corrections_storage_path.iterdir():
                if not type_dir.is_dir() or type_dir.name == "audit":
                    continue

                for date_dir in type_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    for rec_file in date_dir.glob("*.json"):
                        try:
                            with open(rec_file, 'r', encoding='utf-8') as f:
                                rec_data = json.load(f)

                            rec = CorrectionRecommendation.from_dict(rec_data)
                            if not rec.accepted and not rec.rejected:
                                pending.append(rec)

                        except Exception as e:
                            logger.warning(f"Error loading recommendation {rec_file}: {str(e)}")

            # Save rebuilt index
            self._save_pending_index(pending)

        except Exception as e:
            logger.error(f"Error rebuilding pending index: {str(e)}")

        return pending

    def _update_pending_index(self, recommendation: CorrectionRecommendation) -> None:
        """Update pending index with new recommendation."""
        try:
            index_file = self.corrections_storage_path / "pending_index.json"

            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            else:
                index_data = {"pending": []}

            # Add new recommendation
            index_data["pending"].append(recommendation.to_dict())

            # Save updated index
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating pending index: {str(e)}")

    def _save_pending_index(self, pending: List[CorrectionRecommendation]) -> None:
        """Save pending index to disk."""
        try:
            index_file = self.corrections_storage_path / "pending_index.json"
            index_data = {
                "pending": [rec.to_dict() for rec in pending],
                "last_updated": datetime.now().isoformat()
            }

            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving pending index: {str(e)}")

    def _update_stored_recommendation(self, recommendation: CorrectionRecommendation) -> None:
        """Update stored recommendation file."""
        try:
            # Find and update the stored file
            date_str = recommendation.created_at.strftime("%Y-%m-%d")
            type_dir = self.corrections_storage_path / recommendation.type.value / date_str
            rec_file = type_dir / f"{recommendation.id}.json"

            if rec_file.exists():
                with open(rec_file, 'w', encoding='utf-8') as f:
                    json.dump(recommendation.to_dict(), f, indent=2)

        except Exception as e:
            logger.error(f"Error updating stored recommendation: {str(e)}")

    def _log_recommendation_audit(
        self,
        recommendation: CorrectionRecommendation,
        action: str,
        job_id: Optional[str] = None,
        admin_user: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log recommendation action to audit trail."""
        try:
            audit_dir = self.corrections_storage_path / "audit"
            audit_dir.mkdir(exist_ok=True)

            # Create daily audit file
            date_str = datetime.now().strftime("%Y-%m-%d")
            audit_file = audit_dir / f"audit_{date_str}.jsonl"

            audit_entry = {
                "timestamp": datetime.now().isoformat(),
                "recommendation_id": recommendation.id,
                "action": action,
                "correction_type": recommendation.type.value,
                "target": recommendation.target,
                "confidence": recommendation.confidence,
                "job_id": job_id or recommendation.job_id,
                "admin_user": admin_user,
                "reason": reason,
                "environment": self.environment
            }

            with open(audit_file, 'a', encoding='utf-8') as f:
                json.dump(audit_entry, f)
                f.write('\n')

        except Exception as e:
            logger.error(f"Error logging audit entry: {str(e)}")

    def get_correction_statistics(self) -> Dict[str, Any]:
        """Get statistics about corrections."""
        try:
            stats = {
                "pending_count": len(self.pending_corrections),
                "pending_by_type": {},
                "pending_by_confidence": {"high": 0, "medium": 0, "low": 0},
                "total_processed": 0,
                "acceptance_rate": 0.0
            }

            # Count pending by type
            for rec in self.pending_corrections:
                type_name = rec.type.value
                stats["pending_by_type"][type_name] = stats["pending_by_type"].get(type_name, 0) + 1

                # Count by confidence level
                if rec.confidence >= 0.8:
                    stats["pending_by_confidence"]["high"] += 1
                elif rec.confidence >= 0.6:
                    stats["pending_by_confidence"]["medium"] += 1
                else:
                    stats["pending_by_confidence"]["low"] += 1

            # TODO: Calculate acceptance rate from audit logs

            return stats

        except Exception as e:
            logger.error(f"Error getting correction statistics: {str(e)}")
            return {
                "error": str(e),
                "pending_count": 0,
                "pending_by_type": {},
                "pending_by_confidence": {"high": 0, "medium": 0, "low": 0}
            }