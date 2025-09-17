# src_common/pass_c_bypass_validator.py
"""
Pass C Bypass Validator - SHA-based content validation for bypassing Pass C

Implements SHA-based chunk validation to determine if Pass C processing can be
safely bypassed for sources that have already been processed with identical content.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, Session

from .ttrpg_logging import get_logger
from .models import SourceIngestionHistory
from .ttrpg_secrets import get_all_config

logger = get_logger(__name__)


@dataclass
class ProcessingRecord:
    """Record of previous source processing"""
    source_hash: str
    source_path: str
    chunk_count: int
    last_processed_at: datetime
    environment: str
    pass_c_artifacts_path: Optional[str]


@dataclass
class BypassValidationResult:
    """Result of bypass validation check"""
    can_bypass: bool
    reason: str
    processing_record: Optional[ProcessingRecord] = None
    astra_chunk_count: Optional[int] = None
    expected_chunk_count: Optional[int] = None


class PassCBypassValidator:
    """Validates if Pass C can be bypassed based on SHA and chunk count matching"""
    
    def __init__(self, environment: str):
        self.env = environment
        self.logger = get_logger(__name__)
        
        # Initialize database connection
        config = get_all_config()
        db_url = config.get('DATABASE_URL', 'sqlite:///./app.db')
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Initialize AstraDB connection
        self._vector_store = None
        self._init_astra_client()
    
    def _init_astra_client(self):
        """Initialize vector store client for chunk counting."""
        try:
            from .astra_loader import AstraLoader

            loader = AstraLoader(env=self.env)
            self._vector_store = loader.store
            self._collection_name = loader.collection_name
            if self._vector_store is None:
                self.logger.warning("Vector store not available; bypass validation will use simulation mode")
            else:
                self.logger.info(
                    "PassC bypass validator initialized with vector backend %s (collection=%s)",
                    loader.backend,
                    self._collection_name,
                )
        except Exception as e:  # pragma: no cover - initialization failure
            self.logger.error(f"Failed to initialize vector store for bypass validation: {e}")
            self._vector_store = None
    def check_source_processed(self, source_hash: str) -> Optional[ProcessingRecord]:
        """
        Check if a source with given hash has been processed before
        
        Args:
            source_hash: SHA-256 hash of the source file
            
        Returns:
            ProcessingRecord if found, None otherwise
        """
        try:
            with self.SessionLocal() as session:
                stmt = select(SourceIngestionHistory).where(
                    SourceIngestionHistory.source_hash == source_hash,
                    SourceIngestionHistory.environment == self.env
                )
                result = session.execute(stmt).scalar_one_or_none()
                
                if result:
                    return ProcessingRecord(
                        source_hash=result.source_hash,
                        source_path=result.source_path,
                        chunk_count=result.chunk_count,
                        last_processed_at=result.last_processed_at,
                        environment=result.environment,
                        pass_c_artifacts_path=result.pass_c_artifacts_path
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Error checking source processing history for hash {source_hash}: {e}")
            return None
    
    def get_astra_chunk_count_by_source(self, source_hash: str) -> int:
        """Get chunk count from the vector store for a specific source hash."""
        if self._vector_store is None:
            self.logger.warning("Vector store not available - returning 0 chunk count")
            return 0
        try:
            count = self._vector_store.count_documents_for_source(source_hash)
            self.logger.debug("Found %s chunks in vector store for source hash %s", count, source_hash)
            return count
        except Exception as e:
            self.logger.error(f"Error querying vector store chunk count for hash {source_hash}: {e}")
            return 0
    def validate_chunk_count_match(self, source_hash: str, expected_count: int) -> bool:
        """
        Validate that expected chunk count matches actual AstraDB chunk count
        
        Args:
            source_hash: SHA-256 hash of the source file
            expected_count: Expected chunk count from processing history
            
        Returns:
            True if counts match, False otherwise
        """
        actual_count = self.get_astra_chunk_count_by_source(source_hash)
        match = actual_count == expected_count
        
        if match:
            self.logger.info(f"Chunk count validation PASSED for {source_hash}: {actual_count} == {expected_count}")
        else:
            self.logger.warning(f"Chunk count validation FAILED for {source_hash}: {actual_count} != {expected_count}")
        
        return match
    
    def can_bypass_pass_c(self, source_hash: str, source_path: Path) -> BypassValidationResult:
        """
        Determine if Pass C can be safely bypassed for a source
        
        Args:
            source_hash: SHA-256 hash of the source file
            source_path: Path to the source file (for logging)
            
        Returns:
            BypassValidationResult with bypass decision and details
        """
        self.logger.info(f"Evaluating Pass C bypass for {source_path} (hash: {source_hash[:12]}...)")
        
        # Check if source has been processed before
        processing_record = self.check_source_processed(source_hash)
        
        if processing_record is None:
            return BypassValidationResult(
                can_bypass=False,
                reason="Source not found in processing history - first time processing",
                processing_record=None
            )
        
        # Get current AstraDB chunk count
        astra_chunk_count = self.get_astra_chunk_count_by_source(source_hash)
        expected_count = processing_record.chunk_count
        
        # Validate chunk count match
        counts_match = self.validate_chunk_count_match(source_hash, expected_count)
        
        if not counts_match:
            return BypassValidationResult(
                can_bypass=False,
                reason=f"Chunk count mismatch - expected {expected_count}, found {astra_chunk_count}",
                processing_record=processing_record,
                astra_chunk_count=astra_chunk_count,
                expected_chunk_count=expected_count
            )
        
        # Check if artifacts still exist (if path is stored)
        if processing_record.pass_c_artifacts_path:
            artifacts_path = Path(processing_record.pass_c_artifacts_path)
            if not artifacts_path.exists():
                return BypassValidationResult(
                    can_bypass=False,
                    reason=f"Pass C artifacts not found at {artifacts_path}",
                    processing_record=processing_record,
                    astra_chunk_count=astra_chunk_count,
                    expected_chunk_count=expected_count
                )
        
        # All validations passed
        self.logger.info(f"Pass C bypass APPROVED for {source_path} (chunk count: {expected_count})")
        return BypassValidationResult(
            can_bypass=True,
            reason=f"SHA and chunk count match - can bypass Pass C (processed: {processing_record.last_processed_at})",
            processing_record=processing_record,
            astra_chunk_count=astra_chunk_count,
            expected_chunk_count=expected_count
        )
    
    def record_successful_processing(self, source_hash: str, source_path: Path, 
                                   chunk_count: int, pass_c_artifacts_path: Optional[Path] = None) -> bool:
        """
        Record successful Pass C processing for future bypass validation
        
        Args:
            source_hash: SHA-256 hash of the source file
            source_path: Path to the source file
            chunk_count: Number of chunks created by Pass C
            pass_c_artifacts_path: Path to Pass C artifacts directory
            
        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            with self.SessionLocal() as session:
                # Check if record already exists
                existing = session.execute(
                    select(SourceIngestionHistory).where(
                        SourceIngestionHistory.source_hash == source_hash,
                        SourceIngestionHistory.environment == self.env
                    )
                ).scalar_one_or_none()
                
                artifacts_path_str = str(pass_c_artifacts_path) if pass_c_artifacts_path else None
                
                if existing:
                    # Update existing record
                    existing.source_path = str(source_path)
                    existing.chunk_count = chunk_count
                    existing.last_processed_at = datetime.now(timezone.utc)
                    existing.pass_c_artifacts_path = artifacts_path_str
                    action = "Updated"
                else:
                    # Create new record
                    record = SourceIngestionHistory(
                        source_hash=source_hash,
                        source_path=str(source_path),
                        chunk_count=chunk_count,
                        last_processed_at=datetime.now(timezone.utc),
                        environment=self.env,
                        pass_c_artifacts_path=artifacts_path_str
                    )
                    session.add(record)
                    action = "Created"
                
                session.commit()
                self.logger.info(f"{action} processing record for {source_path} (hash: {source_hash[:12]}..., chunks: {chunk_count})")
                return True
                
        except Exception as e:
            self.logger.error(f"Error recording processing result for {source_path}: {e}")
            return False
    
    def remove_chunks_for_source(self, source_hash: str) -> int:
        """Remove all chunks for a specific source hash from the vector store."""
        if self._vector_store is None:
            self.logger.warning("Vector store not available - cannot remove chunks")
            return -1
        try:
            removed = self._vector_store.delete_by_source_hash(source_hash)
            self.logger.info(
                "Removed %s chunks for source hash %s", removed, source_hash[:12]
            )
            return removed
        except Exception as e:
            self.logger.error(f"Error removing chunks for source hash {source_hash}: {e}")
            return -1
