#!/usr/bin/env python3
"""
pass_a_unstructured.py - Unstructured.io Document Processing (Pass A)
======================================================================

Processes documents through Unstructured.io API for structured element extraction.
Supports both full document OCR and TOC-only extraction modes.

Usage:
  pass_a_unstructured.py <document> [options]
  pass_a_unstructured.py -v | --version
  pass_a_unstructured.py -? | --help

Arguments:
  document           Path to input document (PDF, DOCX, TXT, etc.)

Options:
  -o, --output DIR   Output directory (default: /Transfer_Station/Pass_A_Out)
  -l, --language LNG OCR language code (default: eng)
  -t, --toc-only     Extract TOC only (fast, first 8 pages)
  -s, --strategy STR Processing strategy: hi_res|toc_pages|fast (default: hi_res)
  -m, --max-pages N  Maximum pages for TOC extraction (default: 8)
  -v, --version      Show version
  -?, --help         Show this help

Examples:
  # Full document with hi_res OCR
  pass_a_unstructured.py /Transfer_Station/sources/manual.pdf

  # TOC only (fast extraction)
  pass_a_unstructured.py --toc-only /Transfer_Station/sources/manual.pdf

  # Custom strategy and language
  pass_a_unstructured.py -s fast -l spa /path/to/doc.pdf

  # TOC with custom page limit
  pass_a_unstructured.py --toc-only --max-pages 12 /path/to/doc.pdf

Version: 2.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from path_utils import resolve_transfer_path
from config import IngestionConfig

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


__version__ = "2.0.0"

# Unstructured API configuration
UNSTRUCTURED_API_URL = "http://ttrpg_unstructured:8000/general/v0/general"

# Global container index counter for round-robin load balancing
_container_index = 0
_container_lock = threading.Lock()
DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_A_Out")

# Processing strategies
STRATEGY_HI_RES = "hi_res"      # High-resolution OCR with layout detection
STRATEGY_TOC = "toc_pages"      # TOC extraction (fast)
STRATEGY_FAST = "fast"          # Fast processing without OCR


class UnstructuredProcessorError(Exception):
    """Base exception for Unstructured processor errors."""
    pass


def check_unstructured_health(base_url: str) -> bool:
    """Check if Unstructured service is reachable."""
    try:
        # Unstructured API doesn't have /health, use /general/docs instead
        health_url = base_url.rsplit('/', 2)[0] + "/docs"
        response = requests.get(health_url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def process_document_with_retry(
    document_path: Path,
    output_dir: Path,
    strategy: str = STRATEGY_HI_RES,
    ocr_language: str = "eng",
    max_pages: int = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None
) -> Dict[str, Any]:
    """
    Process document through Unstructured pipeline with retry logic and exponential backoff.

    Args:
        document_path: Path to input document
        output_dir: Directory for output files
        strategy: Processing strategy (hi_res, toc_pages, fast)
        ocr_language: Language code for OCR (default: eng)
        max_pages: Maximum pages to process (for toc_pages strategy)
        timeout: Override default timeout (seconds)
        max_retries: Override default max retries

    Returns:
        Dict with processing results

    Raises:
        UnstructuredProcessorError: If all retries exhausted or other error
    """
    if not document_path.exists():
        raise UnstructuredProcessorError(f"Document not found: {document_path}")

    if IngestionConfig.UNSTRUCTURED_USE_LOCAL_PIPELINE:
        return process_document_locally(
            document_path=document_path,
            output_dir=output_dir,
            strategy=strategy,
            ocr_language=ocr_language,
            max_pages=max_pages
        )

    # Select API URL using round-robin load balancing
    global _container_index
    with _container_lock:
        api_url = IngestionConfig.get_api_url(_container_index)
        _container_index += 1

    # Check if Unstructured service is reachable
    if not check_unstructured_health(api_url):
        raise UnstructuredProcessorError(
            f"Unstructured service not reachable at {api_url}\n"
            f"Ensure Unstructured containers are running"
        )

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use config values or overrides
    timeout = timeout or IngestionConfig.UNSTRUCTURED_TIMEOUT
    max_retries = max_retries or IngestionConfig.UNSTRUCTURED_MAX_RETRIES

    # Prepare API request parameters based on strategy
    data = {
        'strategy': strategy,
        'encoding': 'utf-8'
    }

    # Strategy-specific parameters
    if strategy == STRATEGY_HI_RES:
        data.update({
            'ocr_languages': ocr_language,
            'hi_res_model_name': 'yolox',
            'coordinates': 'true',
        })
    elif strategy == STRATEGY_TOC:
        if max_pages:
            data['max_pages'] = max_pages
        data['return_format'] = 'elements'
    elif strategy == STRATEGY_FAST:
        # Fast strategy uses minimal processing
        pass

    last_exception = None

    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        try:
            print(f"Processing {document_path.name} (attempt {attempt + 1}/{max_retries})")

            # Prepare multipart request
            with open(document_path, 'rb') as f:
                files = {
                    'files': (document_path.name, f, 'application/octet-stream')
                }

                # Make API request
                response = requests.post(
                    api_url,
                    files=files,
                    data=data,
                    timeout=timeout
                )

                response.raise_for_status()

                # Success - parse response
                elements = response.json()
                if not isinstance(elements, list):
                    raise UnstructuredProcessorError(f"Unexpected response format: {type(elements)}")

                # Generate output filename with strategy suffix
                strategy_suffix = "_toc" if strategy == STRATEGY_TOC else ""
                output_filename = f"{document_path.stem}{strategy_suffix}_elements.json"
                output_path = output_dir / output_filename

                # Save elements to JSON file
                with open(output_path, 'w', encoding='utf-8') as out_f:
                    json.dump(elements, out_f, indent=2, ensure_ascii=False)

                print(f"[SUCCESS] Processed {document_path.name}")

                return {
                    'input_file': str(document_path),
                    'output_file': str(output_path),
                    'strategy': strategy,
                    'element_count': len(elements),
                    'elements': elements
                }

        except requests.Timeout as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = IngestionConfig.UNSTRUCTURED_INITIAL_WAIT * (IngestionConfig.UNSTRUCTURED_RETRY_BACKOFF ** attempt)
                print(f"[RETRY] Timeout on attempt {attempt + 1}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[ERROR] All {max_retries} attempts exhausted for {document_path.name}")
                raise UnstructuredProcessorError(f"API timeout after {max_retries} attempts: {e}")

        except requests.HTTPError as e:
            print(f"[ERROR] HTTP error: {e.response.status_code} - {e.response.text}")
            raise UnstructuredProcessorError(f"API request failed: {e}")

        except (IOError, json.JSONDecodeError) as e:
            raise UnstructuredProcessorError(f"File I/O or JSON error: {e}")

    # Should not reach here, but just in case
    raise UnstructuredProcessorError(f"Failed after {max_retries} attempts: {last_exception}")


def process_document(
    document_path: Path,
    output_dir: Path,
    strategy: str = STRATEGY_HI_RES,
    ocr_language: str = "eng",
    max_pages: int = None
) -> Dict[str, Any]:
    """
    Process document through Unstructured pipeline.

    Args:
        document_path: Path to input document
        output_dir: Directory for output files
        strategy: Processing strategy (hi_res, toc_pages, fast)
        ocr_language: Language code for OCR (default: eng)
        max_pages: Maximum pages to process (for toc_pages strategy)

    Returns:
        Dict with processing results

    Raises:
        UnstructuredProcessorError: If processing fails
    """
    if not document_path.exists():
        raise UnstructuredProcessorError(f"Document not found: {document_path}")

    if IngestionConfig.UNSTRUCTURED_USE_LOCAL_PIPELINE:
        return process_document_locally(
            document_path=document_path,
            output_dir=output_dir,
            strategy=strategy,
            ocr_language=ocr_language,
            max_pages=max_pages
        )

    # Check if Unstructured service is reachable
    if not check_unstructured_health(UNSTRUCTURED_API_URL):
        raise UnstructuredProcessorError(
            f"Unstructured service not reachable at {UNSTRUCTURED_API_URL}\n"
            f"Ensure n8n_TTRPG_unstructured container is running"
        )

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare API request parameters based on strategy
    data = {
        'strategy': strategy,
        'encoding': 'utf-8'
    }

    # Strategy-specific parameters
    if strategy == STRATEGY_HI_RES:
        data.update({
            'ocr_languages': ocr_language,
            'hi_res_model_name': 'yolox',
            'coordinates': 'true',
        })
    elif strategy == STRATEGY_TOC:
        if max_pages:
            data['max_pages'] = max_pages
        data['return_format'] = 'elements'
    elif strategy == STRATEGY_FAST:
        # Fast strategy uses minimal processing
        pass

    # Prepare multipart request
    try:
        with open(document_path, 'rb') as f:
            files = {
                'files': (document_path.name, f, 'application/octet-stream')
            }

            # Make API request
            response = requests.post(
                UNSTRUCTURED_API_URL,
                files=files,
                data=data,
                timeout=300  # 5 minute timeout for large documents
            )

            response.raise_for_status()

    except requests.RequestException as e:
        raise UnstructuredProcessorError(f"API request failed: {e}")
    except IOError as e:
        raise UnstructuredProcessorError(f"File I/O error: {e}")

    # Parse response
    try:
        elements = response.json()
        if not isinstance(elements, list):
            raise UnstructuredProcessorError(f"Unexpected response format: {type(elements)}")
    except json.JSONDecodeError as e:
        raise UnstructuredProcessorError(f"Failed to parse JSON response: {e}")

    # Generate output filename with strategy suffix
    strategy_suffix = "_toc" if strategy == STRATEGY_TOC else ""
    output_filename = f"{document_path.stem}{strategy_suffix}_elements.json"
    output_path = output_dir / output_filename

    # Save elements to JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(elements, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise UnstructuredProcessorError(f"Failed to write output file: {e}")

    return {
        'input_file': str(document_path),
        'output_file': str(output_path),
        'strategy': strategy,
        'element_count': len(elements),
        'elements': elements
    }


def process_document_locally(
    document_path: Path,
    output_dir: Path,
    strategy: str = STRATEGY_HI_RES,
    ocr_language: str = "eng",
    max_pages: Optional[int] = None
) -> Dict[str, Any]:
    """
    Process document using the in-container Unstructured library (no HTTP).
    """
    try:
        from unstructured.partition.auto import partition
    except ImportError as exc:
        raise UnstructuredProcessorError(
            "Local Unstructured pipeline unavailable (missing unstructured package)."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    partition_kwargs: Dict[str, Any] = {
        "filename": str(document_path),
    }

    if ocr_language:
        partition_kwargs["languages"] = [ocr_language]

    if strategy == STRATEGY_FAST:
        partition_kwargs["strategy"] = "fast"
    else:
        partition_kwargs["strategy"] = "hi_res"
        partition_kwargs["hi_res_model_name"] = "yolox"
        partition_kwargs["infer_table_structure"] = True

    try:
        elements = partition(**partition_kwargs)
    except Exception as exc:
        raise UnstructuredProcessorError(f"Local partition failed: {exc}") from exc

    if strategy == STRATEGY_TOC and max_pages:
        filtered = []
        for element in elements:
            page_number = getattr(getattr(element, "metadata", None), "page_number", None)
            if page_number and page_number > max_pages:
                continue
            filtered.append(element)
        elements = filtered

    elements_payload: List[Dict[str, Any]] = []
    for element in elements:
        if hasattr(element, "to_dict"):
            elements_payload.append(element.to_dict())
        else:
            elements_payload.append(
                {
                    "type": element.__class__.__name__,
                    "text": getattr(element, "text", ""),
                }
            )

    strategy_suffix = "_toc" if strategy == STRATEGY_TOC else ""
    output_filename = f"{document_path.stem}{strategy_suffix}_elements.json"
    output_path = output_dir / output_filename

    try:
        with open(output_path, 'w', encoding='utf-8') as out_f:
            json.dump(elements_payload, out_f, indent=2, ensure_ascii=False)
    except IOError as exc:
        raise UnstructuredProcessorError(f"Failed to write output file: {exc}") from exc

    return {
        'input_file': str(document_path),
        'output_file': str(output_path),
        'strategy': strategy,
        'element_count': len(elements_payload),
        'elements': elements_payload
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Process documents through Unstructured.io API',
        add_help=False
    )

    parser.add_argument(
        'document',
        nargs='?',
        type=Path,
        help='Path to input document'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '-l', '--language',
        type=str,
        default='eng',
        help='OCR language code (default: eng)'
    )
    parser.add_argument(
        '-t', '--toc-only',
        action='store_true',
        help='Extract TOC only (fast, first 8 pages)'
    )
    parser.add_argument(
        '-s', '--strategy',
        type=str,
        choices=[STRATEGY_HI_RES, STRATEGY_TOC, STRATEGY_FAST],
        help=f'Processing strategy (default: {STRATEGY_HI_RES})'
    )
    parser.add_argument(
        '-m', '--max-pages',
        type=int,
        default=8,
        help='Maximum pages for TOC extraction (default: 8)'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'pass_a_unstructured v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.document:
        parser.print_help()
        sys.exit(1)

    # Determine strategy
    if args.toc_only:
        args.strategy = STRATEGY_TOC
    elif not args.strategy:
        args.strategy = STRATEGY_HI_RES

    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # Process document with retry logic and exponential backoff
        result = process_document_with_retry(
            document_path=args.document,
            output_dir=args.output,
            strategy=args.strategy,
            ocr_language=args.language,
            max_pages=args.max_pages if args.strategy == STRATEGY_TOC else None,
            timeout=None,  # Use config default (900s = 15 minutes)
            max_retries=None  # Use config default (3 retries)
        )

        # Success message
        strategy_desc = {
            STRATEGY_HI_RES: "high-resolution OCR",
            STRATEGY_TOC: "TOC extraction",
            STRATEGY_FAST: "fast processing"
        }.get(result['strategy'], result['strategy'])

        print(
            f"Processed {Path(result['input_file']).name} ({strategy_desc}): "
            f"{result['element_count']} elements extracted to "
            f"{Path(result['output_file']).name}"
        )

        return 0

    except UnstructuredProcessorError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def process_document_async(
    document_path: Path,
    output_dir: Path,
    strategy: str = STRATEGY_HI_RES,
    ocr_language: str = "eng",
    max_pages: Optional[int] = None,
    timeout: int = 3600
) -> Dict[str, Any]:
    """
    Process document using async job queue (eliminates HTTP timeouts).

    Creates a job in Transfer_Station that the unstructured_job_worker.py
    (running in the unstructured container) will claim and process locally.

    This eliminates:
    - HTTP network overhead
    - Serialization overhead
    - Timeout issues with large documents

    Args:
        document_path: Path to document to process
        output_dir: Directory for output JSON files
        strategy: Processing strategy (hi_res, toc_pages, fast)
        ocr_language: OCR language code (default: eng)
        max_pages: Maximum pages to process (None = all pages)
        timeout: Maximum seconds to wait for completion (default: 3600)

    Returns:
        result: Dictionary with:
            - job_id: Job UUID
            - output_path: Path to output JSON file
            - statistics: Processing statistics
            - duration: Total processing time

    Raises:
        JobTimeoutError: If job doesn't complete within timeout
        JobFailedError: If job fails with errors
    """
    from submit_unstructured_job import create_job
    from wait_for_job import wait_for_completion, JobTimeoutError, JobFailedError

    # Log async processing start
    print(f"[ASYNC] Submitting job for: {document_path}")
    print(f"[ASYNC] Strategy: {strategy}, OCR: {ocr_language}, Max pages: {max_pages or 'all'}")

    try:
        # Create job in Transfer Station
        job_id = create_job(
            document_path=str(document_path),
            output_dir=str(output_dir),
            strategy=strategy,
            ocr_languages=[ocr_language],
            max_pages=max_pages
        )

        print(f"[ASYNC] Job created: {job_id}")
        print(f"[ASYNC] Waiting for worker to claim and process (timeout: {timeout}s)...")

        # Poll for completion
        result = wait_for_completion(
            job_id=job_id,
            timeout=timeout,
            poll_interval=5
        )

        print(f"[ASYNC] Job {job_id} completed successfully")
        print(f"[ASYNC] Output: {result['output_path']}")
        print(f"[ASYNC] Duration: {result['duration']:.1f}s")

        return result

    except JobTimeoutError as e:
        print(f"[ASYNC] ERROR: Job timeout: {e}", file=sys.stderr)
        raise UnstructuredProcessorError(f"Async job timeout: {e}") from e

    except JobFailedError as e:
        print(f"[ASYNC] ERROR: Job failed: {e}", file=sys.stderr)
        raise UnstructuredProcessorError(f"Async job failed: {e}") from e

    except Exception as e:
        print(f"[ASYNC] ERROR: Unexpected error: {e}", file=sys.stderr)
        raise UnstructuredProcessorError(f"Async job error: {e}") from e


if __name__ == '__main__':
    sys.exit(main())
