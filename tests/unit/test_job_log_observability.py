#!/usr/bin/env python3
"""
Test script to demonstrate dual logging (container + job log) observability
"""

import sys
import time
import logging
from pathlib import Path

# Add src_common to Python path
sys.path.insert(0, str(Path(__file__).parent / "src_common"))

from src_common.pass_b_logical_splitter import PassBLogicalSplitter

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_job_log_observability():
    """Test that Pass B observability appears in job log files"""

    # Setup paths
    pdf_path = Path("/data/uploads/Pathfinder RPG - Core Rulebook (6th Printing).pdf")
    output_dir = Path("/app/artifacts/dev/test_job_log_observability")
    job_log_file = Path("/app/env/dev/logs/test_observability_demo.log")
    job_id = f"test_job_log_{int(time.time())}"

    logger.info(f"Testing dual logging observability")
    logger.info(f"PDF file: {pdf_path}")
    logger.info(f"Job log file: {job_log_file}")
    logger.info(f"Job ID: {job_id}")

    # Check if file exists
    if not pdf_path.exists():
        logger.error(f"Test file not found: {pdf_path}")
        return False

    # Create job log file with initial entry
    job_log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(job_log_file, 'w', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] Job started: {job_id}\n")

    # Initialize Pass B splitter with job log file
    splitter = PassBLogicalSplitter(job_id, env="dev", job_log_file=job_log_file)

    # Process the file (this should create dual logging)
    logger.info("Starting Pass B processing with dual logging...")
    start_time = time.time()
    result = splitter.process_pdf(pdf_path, output_dir)
    end_time = time.time()

    # Report results
    processing_time = end_time - start_time
    logger.info(f"Pass B completed in {processing_time:.1f} seconds")
    logger.info(f"Success: {result.success}")
    logger.info(f"Split performed: {result.split_performed}")
    logger.info(f"Parts created: {result.parts_created}")

    # Check job log file contents
    if job_log_file.exists():
        logger.info(f"\n=== JOB LOG FILE CONTENTS ===")
        with open(job_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logger.info(f"Job log has {len(lines)} lines of observability data")
            # Show first 10 and last 10 lines
            for i, line in enumerate(lines[:10]):
                logger.info(f"Line {i+1}: {line.strip()}")
            if len(lines) > 20:
                logger.info("... (middle lines omitted) ...")
                for i, line in enumerate(lines[-10:], len(lines)-9):
                    logger.info(f"Line {i}: {line.strip()}")
            elif len(lines) > 10:
                for i, line in enumerate(lines[10:], 11):
                    logger.info(f"Line {i}: {line.strip()}")

    return result.success

if __name__ == "__main__":
    success = test_job_log_observability()
    sys.exit(0 if success else 1)