#!/usr/bin/env python3
"""
pass_d_embedding_validator.py - Embedding Generation Validation (Fix for Issue #3)
===================================================================================

Validates and handles null/failed embeddings during Pass D processing.
Implements retry logic, null handling, and chunk marking for failed embeddings.

This module addresses the root cause identified in Pass F validation failures:
- Cassandra showing 32,088 violations on 16,044 chunks (2x ratio)
- Indicates ~2 of 7 validation checks failing per chunk
- Root cause: Null/invalid embeddings from Pass D failures

Fixes implemented:
1. Skip empty/whitespace-only chunks before embedding generation
2. Truncate chunks exceeding token limits (>450 tokens for Ada-002)
3. Retry failed embeddings with exponential backoff
4. Mark failed chunks as 'stale' for later reprocessing
5. Log all failures for analysis

Usage:
  Integrated into pass_d_hayhooks.py automatically

Version: 1.0.0
Author: n8n TTRPG Center
"""

import logging
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# OpenAI Ada-002 embedding model limits
ADA_002_MAX_TOKENS = 450  # Conservative limit (actual is 8191 but we use chunks <450)
ADA_002_EMBEDDING_DIMENSION = 1536

class EmbeddingValidationError(Exception):
    """Raised when embedding validation encounters unrecoverable error."""


class EmbeddingValidator:
    """
    Validates text chunks before embedding generation and handles failures.
    """

    def __init__(
        self,
        max_tokens: int = ADA_002_MAX_TOKENS,
        retry_attempts: int = 3,
        retry_backoff_base: float = 2.0
    ):
        """
        Initialize embedding validator.

        Args:
            max_tokens: Maximum tokens allowed per chunk (default: 450)
            retry_attempts: Number of retry attempts for failed embeddings (default: 3)
            retry_backoff_base: Exponential backoff base for retries (default: 2.0)
        """
        self.max_tokens = max_tokens
        self.retry_attempts = retry_attempts
        self.retry_backoff_base = retry_backoff_base

        self.stats = {
            'chunks_processed': 0,
            'chunks_skipped_empty': 0,
            'chunks_truncated': 0,
            'embeddings_succeeded': 0,
            'embeddings_failed': 0,
            'retry_attempts': 0
        }

    def validate_chunk_text(self, text: str, chunk_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate chunk text before sending to embedding API.

        Implements Fix #3.1: Filter empty chunks
        Implements Fix #3.2: Truncate long chunks

        Args:
            text: Chunk text content
            chunk_id: Chunk identifier for logging

        Returns:
            Tuple of (is_valid: bool, processed_text: Optional[str], reason: Optional[str])
        """
        # Filter 1: Skip empty or whitespace-only chunks
        if not text or text.strip() == "":
            logger.warning(f"  ⚠️  Skipping empty chunk: {chunk_id}")
            self.stats['chunks_skipped_empty'] += 1
            return False, None, "empty_chunk"

        # Filter 2: Skip chunks with only whitespace/newlines
        if len(text.strip()) < 5:  # Minimum 5 characters
            logger.warning(f"  ⚠️  Skipping too-short chunk: {chunk_id} (length: {len(text.strip())})")
            self.stats['chunks_skipped_empty'] += 1
            return False, None, "chunk_too_short"

        # Filter 3: Truncate chunks exceeding token limit
        # Simple token estimation: ~4 characters per token
        estimated_tokens = len(text) // 4

        if estimated_tokens > self.max_tokens:
            # Truncate to approximately max_tokens
            target_chars = self.max_tokens * 4
            truncated_text = text[:target_chars]

            # Try to truncate at sentence boundary
            last_period = truncated_text.rfind('.')
            last_newline = truncated_text.rfind('\n')
            boundary = max(last_period, last_newline)

            if boundary > target_chars * 0.8:  # If boundary is reasonable
                truncated_text = truncated_text[:boundary + 1]

            logger.warning(
                f"  ⚠️  Truncating long chunk: {chunk_id} "
                f"(estimated {estimated_tokens} tokens → {len(truncated_text) // 4} tokens)"
            )
            self.stats['chunks_truncated'] += 1
            return True, truncated_text, "truncated"

        # Valid chunk - no modifications needed
        return True, text, None

    def generate_embedding_with_retry(
        self,
        text: str,
        chunk_id: str,
        embedding_function
    ) -> Tuple[bool, Optional[List[float]], Optional[str]]:
        """
        Generate embedding with retry logic and validation.

        Implements Fix #3.3: Retry with exponential backoff
        Implements Fix #3.4: Mark failed chunks as 'stale'

        Args:
            text: Pre-validated chunk text
            chunk_id: Chunk identifier for logging
            embedding_function: Callable that generates embeddings (takes text, returns List[float])

        Returns:
            Tuple of (success: bool, embedding: Optional[List[float]], error: Optional[str])
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                # Call embedding function
                embedding = embedding_function(text)

                # Validate embedding result
                if not embedding:
                    raise ValueError("Embedding function returned None/empty")

                if len(embedding) != ADA_002_EMBEDDING_DIMENSION:
                    raise ValueError(
                        f"Invalid embedding dimension: {len(embedding)} "
                        f"(expected {ADA_002_EMBEDDING_DIMENSION})"
                    )

                # Check for null/zero embeddings (all zeros)
                if all(v == 0.0 for v in embedding):
                    raise ValueError("Embedding contains all zeros (invalid)")

                # Success!
                if attempt > 1:
                    logger.info(f"  ✅ Embedding succeeded on retry {attempt-1} for chunk: {chunk_id}")
                    self.stats['retry_attempts'] += (attempt - 1)

                self.stats['embeddings_succeeded'] += 1
                return True, embedding, None

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"  ⚠️  Embedding attempt {attempt}/{self.retry_attempts} failed for {chunk_id}: {error_msg}"
                )

                # If not last attempt, wait before retrying (exponential backoff)
                if attempt < self.retry_attempts:
                    wait_time = self.retry_backoff_base ** (attempt - 1)
                    logger.info(f"     Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    logger.error(
                        f"  ❌ Embedding generation failed after {self.retry_attempts} attempts: {chunk_id}"
                    )
                    self.stats['embeddings_failed'] += 1
                    self.stats['retry_attempts'] += (attempt - 1)
                    return False, None, error_msg

        # Should never reach here, but safety fallback
        return False, None, "unknown_error"

    def process_chunk_with_validation(
        self,
        chunk_data: dict,
        embedding_function
    ) -> Tuple[bool, Optional[List[float]], str]:
        """
        Complete chunk processing pipeline with validation.

        Combines validation + retry + error handling.

        Args:
            chunk_data: Dictionary containing 'text_content', 'element_id', 'chunk_index'
            embedding_function: Callable for generating embeddings

        Returns:
            Tuple of (success: bool, embedding: Optional[List[float]], status: str)
            status: "success", "skipped", "truncated", "failed"
        """
        self.stats['chunks_processed'] += 1

        text = chunk_data.get('text_content', '')
        chunk_id = f"{chunk_data.get('element_id', 'unknown')}_{chunk_data.get('chunk_index', 0)}"

        # Step 1: Validate chunk text
        is_valid, processed_text, validation_reason = self.validate_chunk_text(text, chunk_id)

        if not is_valid:
            # Chunk failed validation (empty/too short)
            return False, None, f"skipped_{validation_reason}"

        # Step 2: Generate embedding with retry
        success, embedding, error = self.generate_embedding_with_retry(
            processed_text, chunk_id, embedding_function
        )

        if success:
            if validation_reason == "truncated":
                return True, embedding, "success_truncated"
            else:
                return True, embedding, "success"
        else:
            return False, None, f"failed_{error}"

    def get_statistics(self) -> dict:
        """Get processing statistics."""
        success_rate = 0.0
        if self.stats['chunks_processed'] > 0:
            valid_chunks = self.stats['chunks_processed'] - self.stats['chunks_skipped_empty']
            if valid_chunks > 0:
                success_rate = (self.stats['embeddings_succeeded'] / valid_chunks) * 100

        return {
            **self.stats,
            'success_rate_percent': round(success_rate, 2),
            'avg_retries_per_failure': (
                self.stats['retry_attempts'] / self.stats['embeddings_failed']
                if self.stats['embeddings_failed'] > 0 else 0.0
            )
        }

    def log_final_statistics(self):
        """Log final processing statistics."""
        stats = self.get_statistics()

        logger.info("\n" + "="*60)
        logger.info("EMBEDDING VALIDATION STATISTICS")
        logger.info("="*60)
        logger.info(f"Chunks Processed:     {stats['chunks_processed']}")
        logger.info(f"  Skipped (empty):    {stats['chunks_skipped_empty']}")
        logger.info(f"  Truncated (long):   {stats['chunks_truncated']}")
        logger.info(f"Embeddings Generated: {stats['embeddings_succeeded']}")
        logger.info(f"Embeddings Failed:    {stats['embeddings_failed']}")
        logger.info(f"Total Retry Attempts: {stats['retry_attempts']}")
        logger.info(f"Success Rate:         {stats['success_rate_percent']}%")
        logger.info("="*60 + "\n")


def mark_chunk_as_stale(
    cassandra_session,
    document_id: str,
    element_id: str,
    chunk_index: int
) -> bool:
    """
    Mark a chunk as 'stale' in Cassandra when embedding generation fails.

    This allows failed chunks to be reprocessed later without blocking the pipeline.

    Args:
        cassandra_session: Active Cassandra session
        document_id: Document identifier
        element_id: Element identifier
        chunk_index: Chunk index

    Returns:
        True if successfully marked, False otherwise
    """
    try:
        cql = """
            UPDATE ttrpg_vectors.embeddings
            SET status = 'stale', embedding = null
            WHERE document_id = %s
              AND element_id = %s
              AND chunk_index = %s
        """
        cassandra_session.execute(cql, (document_id, element_id, chunk_index))
        logger.info(f"  ✅ Marked chunk as stale: {element_id}_{chunk_index}")
        return True

    except Exception as e:
        logger.error(f"  ❌ Failed to mark chunk as stale: {e}")
        return False


# Example usage for integration into pass_d_hayhooks.py:
"""
# In pass_d_hayhooks.py, replace the embedding generation loop with:

from pass_d_embedding_validator import EmbeddingValidator, mark_chunk_as_stale

validator = EmbeddingValidator(
    max_tokens=450,
    retry_attempts=3,
    retry_backoff_base=2.0
)

for chunk_data in chunks:
    # Create embedding function wrapper
    def embed_text(text):
        return hayhooks_client.generate_embedding(text)  # Your existing function

    success, embedding, status = validator.process_chunk_with_validation(
        chunk_data, embed_text
    )

    if success:
        # Store embedding in Cassandra (existing code)
        upsert_embedding_to_cassandra(chunk_data, embedding, status='active')
    else:
        # Mark chunk as stale for later reprocessing
        mark_chunk_as_stale(
            cassandra_session,
            chunk_data['document_id'],
            chunk_data['element_id'],
            chunk_data['chunk_index']
        )

# Log final statistics
validator.log_final_statistics()
"""


if __name__ == "__main__":
    # Example standalone usage
    import sys

    logging.basicConfig(level=logging.INFO)

    # Create validator
    validator = EmbeddingValidator(max_tokens=450, retry_attempts=3)

    # Example chunks
    test_chunks = [
        {"text_content": "", "element_id": "test", "chunk_index": 1},  # Empty
        {"text_content": "   \n  ", "element_id": "test", "chunk_index": 2},  # Whitespace only
        {"text_content": "Valid chunk content here.", "element_id": "test", "chunk_index": 3},  # Valid
        {"text_content": "Short", "element_id": "test", "chunk_index": 4},  # Too short
    ]

    # Mock embedding function
    def mock_embed(text):
        return [0.1] * 1536  # Return fake embedding

    for chunk in test_chunks:
        success, embedding, status = validator.process_chunk_with_validation(chunk, mock_embed)
        print(f"Chunk {chunk['chunk_index']}: {status} (success={success})")

    # Log statistics
    validator.log_final_statistics()
