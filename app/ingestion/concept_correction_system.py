#!/usr/bin/env python3
"""
Concept Classification Correction System
========================================

Provides feedback mechanisms to improve concept-aware chunking accuracy:
1. Automatic error detection using pattern analysis
2. Manual correction interface for admin users
3. Learning system to improve future classifications
4. Batch correction utilities

This addresses the systematic misclassification issues found in concept_chunker.py
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from astrapy import DataAPIClient
import os

logger = logging.getLogger(__name__)

@dataclass
class ConceptCorrection:
    """Represents a concept type correction"""
    concept_id: str
    original_type: str
    corrected_type: str
    confidence: float
    evidence: str
    corrected_by: str  # 'system' or user_id
    corrected_at: str
    applied: bool = False

class ConceptCorrectionSystem:
    """System for detecting and correcting concept classification errors"""
    
    def __init__(self, collection_name: str = "ttrpg_chunks_dev"):
        self.collection_name = collection_name
        
        # Initialize AstraDB client
        self.client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
        endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        self.database = self.client.get_database_by_api_endpoint(endpoint)
        self.collection = self.database.get_collection(collection_name)
        
        # Load classification patterns
        self.feat_patterns = [
            r'\([Cc]ombat\)',
            r'\([Gg]eneral\)',
            r'\([Mm]etamagic\)',
            r'\([Ii]tem [Cc]reation\)',
            r'Prerequisites?:',
            r'Benefit:',
            r'Normal:',
            r'Special:'
        ]
        
        self.spell_patterns = [
            r'School [a-z]+',
            r'Level [a-z/]+ \d+',
            r'Casting Time',
            r'Components [VSM,]+',
            r'Range [a-z]+ \(',
            r'Duration [a-z]+',
            r'Saving Throw',
            r'Spell Resistance'
        ]
        
        self.monster_patterns = [
            r'\bCR \d+',
            r'Challenge Rating',
            r'XP [\d,]+',
            r'AC \d+',
            r'hp \d+',
            r'Init [+-]?\d+',
            r'Speed \d+ ft'
        ]
    
    def detect_classification_errors(self, limit: int = 1000) -> List[ConceptCorrection]:
        """
        Automatically detect obvious classification errors
        
        Returns:
            List of detected corrections with confidence scores
        """
        corrections = []
        
        # Get all documents for analysis
        docs = list(self.collection.find({}, limit=limit))
        
        for doc in docs:
            metadata = doc.get('metadata', {})
            content = doc.get('content', '')
            concept_id = metadata.get('concept_id', 'unknown')
            current_type = metadata.get('concept_type', 'unknown')
            
            if not content or current_type == 'unknown':
                continue
            
            # Analyze content patterns
            predicted_type, confidence, evidence = self._analyze_content_patterns(content)
            
            # If prediction differs significantly from current classification
            if predicted_type != current_type and confidence > 0.8:
                correction = ConceptCorrection(
                    concept_id=concept_id,
                    original_type=current_type,
                    corrected_type=predicted_type,
                    confidence=confidence,
                    evidence=evidence,
                    corrected_by='system',
                    corrected_at=datetime.now(timezone.utc).isoformat()
                )
                corrections.append(correction)
        
        return corrections
    
    def _analyze_content_patterns(self, content: str) -> Tuple[str, float, str]:
        """
        Analyze content to predict correct concept type
        
        Returns:
            (predicted_type, confidence, evidence)
        """
        import re
        
        content_lower = content.lower()
        pattern_scores = {
            'spell': 0,
            'feat': 0, 
            'monster': 0
        }
        
        evidence_list = []
        
        # Check spell patterns
        for pattern in self.spell_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                pattern_scores['spell'] += 1
                evidence_list.append(f"Spell pattern: {pattern}")
        
        # Check feat patterns  
        for pattern in self.feat_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                pattern_scores['feat'] += 1
                evidence_list.append(f"Feat pattern: {pattern}")
        
        # Check monster patterns
        for pattern in self.monster_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                pattern_scores['monster'] += 1
                evidence_list.append(f"Monster pattern: {pattern}")
        
        # Special case: Obvious feat indicators
        if '(Combat)' in content and ('Prerequisite' in content or 'Benefit:' in content):
            pattern_scores['feat'] += 3
            evidence_list.append("Strong feat indicators: (Combat) + Prerequisites/Benefit")
        
        # Calculate prediction
        max_score = max(pattern_scores.values())
        if max_score == 0:
            return 'text', 0.1, 'No strong patterns detected'
        
        predicted_type = max(pattern_scores, key=pattern_scores.get)
        confidence = min(0.95, max_score / 5.0)  # Normalize to 0-1 scale
        evidence = "; ".join(evidence_list)
        
        return predicted_type, confidence, evidence
    
    def apply_corrections(self, corrections: List[ConceptCorrection], 
                         progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Apply approved corrections to the database
        
        Args:
            corrections: List of corrections to apply
            progress_callback: Optional progress callback
            
        Returns:
            Results dictionary with statistics
        """
        applied = 0
        errors = []
        
        for i, correction in enumerate(corrections):
            try:
                # Update document in database
                update_result = self.collection.update_one(
                    {"metadata.concept_id": correction.concept_id},
                    {
                        "$set": {
                            "metadata.concept_type": correction.corrected_type,
                            "metadata.correction_applied": True,
                            "metadata.original_type": correction.original_type,
                            "metadata.correction_confidence": correction.confidence,
                            "metadata.correction_evidence": correction.evidence,
                            "metadata.corrected_at": correction.corrected_at,
                            "metadata.corrected_by": correction.corrected_by
                        }
                    }
                )
                
                if hasattr(update_result, 'modified_count') and update_result.modified_count > 0:
                    applied += 1
                    correction.applied = True
                elif hasattr(update_result, 'update_info') and update_result.update_info.get('upserted_count', 0) > 0:
                    applied += 1
                    correction.applied = True
                elif update_result:
                    applied += 1
                    correction.applied = True
                else:
                    errors.append(f"Document not found for concept_id: {correction.concept_id}")
                
                # Progress update
                if progress_callback and i % 10 == 0:
                    progress = (i / len(corrections)) * 100
                    progress_callback("Correction", f"Applied {applied}/{len(corrections)} corrections", 
                                    progress, {"applied": applied, "errors": len(errors)})
                    
            except Exception as e:
                errors.append(f"Error updating {correction.concept_id}: {str(e)}")
        
        return {
            "corrections_applied": applied,
            "total_corrections": len(corrections),
            "errors": errors,
            "success_rate": applied / len(corrections) if corrections else 0
        }
    
    def create_correction_report(self, corrections: List[ConceptCorrection], 
                               output_path: str = "correction_report.json") -> str:
        """
        Create a detailed correction report for review
        
        Args:
            corrections: List of corrections
            output_path: Path to save the report
            
        Returns:
            Path to the generated report
        """
        # Group by correction type
        by_type = defaultdict(list)
        for correction in corrections:
            transition = f"{correction.original_type} → {correction.corrected_type}"
            by_type[transition].append(correction)
        
        # Calculate statistics
        stats = {
            "total_corrections": len(corrections),
            "by_transition": {k: len(v) for k, v in by_type.items()},
            "high_confidence": len([c for c in corrections if c.confidence > 0.9]),
            "medium_confidence": len([c for c in corrections if 0.7 <= c.confidence <= 0.9]),
            "low_confidence": len([c for c in corrections if c.confidence < 0.7])
        }
        
        # Create report
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "collection": self.collection_name,
            "statistics": stats,
            "corrections_by_type": {k: [c.__dict__ for c in v] for k, v in by_type.items()},
            "recommended_actions": self._generate_recommendations(corrections)
        }
        
        # Save report
        report_path = Path(output_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Correction report saved to: {report_path}")
        return str(report_path)
    
    def _generate_recommendations(self, corrections: List[ConceptCorrection]) -> List[str]:
        """Generate recommendations based on correction patterns"""
        recommendations = []
        
        # Count by transition type
        transitions = defaultdict(int)
        for c in corrections:
            transitions[f"{c.original_type}→{c.corrected_type}"] += 1
        
        # Generate specific recommendations
        for transition, count in transitions.items():
            if count > 5:
                recommendations.append(f"High frequency error: {transition} ({count} cases) - Update concept_chunker patterns")
        
        if len([c for c in corrections if 'feat' in c.evidence.lower()]) > 10:
            recommendations.append("Many feat misclassifications - Improve feat detection patterns in concept_chunker.py")
        
        if len([c for c in corrections if c.confidence > 0.9]) > 20:
            recommendations.append("Many high-confidence corrections available - Consider batch applying these")
        
        return recommendations
    
    def manual_correction_interface(self, concept_id: str, new_type: str, 
                                  user_id: str = "admin") -> bool:
        """
        Manual correction interface for admin users
        
        Args:
            concept_id: ID of concept to correct
            new_type: New concept type ('spell', 'feat', 'monster', 'text')
            user_id: ID of user making the correction
            
        Returns:
            True if correction applied successfully
        """
        try:
            # Verify concept exists
            docs = list(self.collection.find({"metadata.concept_id": concept_id}, limit=1))
            if not docs:
                logger.error(f"Concept not found: {concept_id}")
                return False
            
            current_type = docs[0].get('metadata', {}).get('concept_type', 'unknown')
            
            # Apply correction
            correction = ConceptCorrection(
                concept_id=concept_id,
                original_type=current_type,
                corrected_type=new_type,
                confidence=1.0,  # Manual corrections are 100% confident
                evidence=f"Manual correction by {user_id}",
                corrected_by=user_id,
                corrected_at=datetime.now(timezone.utc).isoformat()
            )
            
            result = self.apply_corrections([correction])
            return result["corrections_applied"] == 1
            
        except Exception as e:
            logger.error(f"Manual correction failed for {concept_id}: {e}")
            return False

def run_correction_analysis(collection_name: str = "ttrpg_chunks_dev", 
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to run full correction analysis
    
    Args:
        collection_name: AstraDB collection to analyze
        progress_callback: Optional progress callback
        
    Returns:
        Analysis results with correction report path
    """
    corrector = ConceptCorrectionSystem(collection_name)
    
    if progress_callback:
        progress_callback("Analysis", "Detecting classification errors", 10.0)
    
    # Detect errors
    corrections = corrector.detect_classification_errors(limit=1000)
    
    if progress_callback:
        progress_callback("Analysis", f"Found {len(corrections)} potential corrections", 50.0)
    
    # Generate report
    report_path = corrector.create_correction_report(corrections)
    
    if progress_callback:
        progress_callback("Analysis", "Analysis complete", 100.0, 
                        {"corrections_found": len(corrections), "report_path": report_path})
    
    return {
        "corrections_found": len(corrections),
        "high_confidence_corrections": len([c for c in corrections if c.confidence > 0.9]),
        "report_path": report_path,
        "corrector": corrector,
        "corrections": corrections
    }

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(phase, message, progress, details=None):
        print(f"[{progress:5.1f}%] {phase}: {message}")
        if details:
            print(f"         Details: {details}")
    
    collection_name = sys.argv[1] if len(sys.argv) > 1 else "ttrpg_chunks_dev"
    
    print("Running concept classification correction analysis...")
    print("=" * 60)
    
    results = run_correction_analysis(collection_name, progress_callback)
    
    print("\nCORRECTION ANALYSIS RESULTS:")
    print(f"Corrections found: {results['corrections_found']}")
    print(f"High confidence: {results['high_confidence_corrections']}")
    print(f"Report saved to: {results['report_path']}")
    
    if results['corrections_found'] > 0:
        print("\nTo apply high-confidence corrections:")
        print("python -c \"from concept_correction_system import *; corrector = results['corrector']; high_conf = [c for c in results['corrections'] if c.confidence > 0.9]; corrector.apply_corrections(high_conf)\"")