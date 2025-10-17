#!/usr/bin/env python3
"""
gate_1_log_analyzer.py - Gate 1 Log Analysis with OpenAI
==========================================================

Analyzes ingestion log files using OpenAI GPT-4o to identify issues and generate
remediation prompts for human review. Acts as a senior QA manager to detect
problems across the ingestion pipeline.

Usage:
  gate_1_log_analyzer.py <log_file> [options]
  gate_1_log_analyzer.py -v | --version
  gate_1_log_analyzer.py -? | --help

Arguments:
  log_file              Path to ingestion log file

Options:
  -o, --output DIR      Output directory for prompts (default: /Transfer_Station/Prompt_Lib/log_analysis)
  --model NAME          OpenAI model (default: gpt-4o, configurable)
  --project NAME        OpenAI project ID (default: ingestion_log_analysis)
  --dry-run             Analyze without calling OpenAI API
  -v, --version         Show version
  -?, --help            Show this help

Examples:
  gate_1_log_analyzer.py /Transfer_Station/ingestion_logs/run_20251009_120000.log
  gate_1_log_analyzer.py log.txt --model gpt-4o --dry-run

Output:
  Creates individual prompt files in Prompt_Lib for each detected issue.
  Format: {timestamp}_{issue_type}_{severity}.md

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from path_utils import resolve_transfer_path
from secrets_utils import read_secret

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed, using system environment only", file=sys.stderr)


__version__ = "1.0.0"

DEFAULT_OUTPUT_DIR = str(resolve_transfer_path("Prompt_Lib", "log_analysis"))
DEFAULT_MODEL = "gpt-4o"  # Configurable: can change to gpt-4o, o1-preview, etc.
DEFAULT_PROJECT = "ingestion_log_analysis"

# Core function descriptions for each pass
PASS_DESCRIPTIONS = """
## Ingestion Pipeline Pass Descriptions

### Gate 0: File Validation
- **gate_0_hash.py**: Computes SHA-256 hash, generates unique document_id, creates marker file with rebuild flags
- **gate_0_validate.py**: Compares checksum with Cassandra to detect early exit conditions

### Pass A: TOC Extraction & Initial Metadata
- **pass_a_unstructured.py**: Extracts TOC elements (first 8 pages) using Unstructured.io API with hi_res OCR
- **pass_a_metadata.py**: Generates hierarchical TOC structure, categories, and term index from elements
- **pass_a_mongo_upsert.py**: Uploads TOC metadata and elements to MongoDB (initial stage)

### Pass B: Document Splitting
- **pass_b_splitter.py**: Splits large documents into logical parts (10-20 pages) based on TOC structure
- Creates manifest tracking all parts for distributed processing

### Pass C: Full Document Processing
- **pass_c_parsing.py**: Processes all document parts through Unstructured.io API
- **pass_c_metadata.py**: Aggregates metadata across all parts, generates comprehensive term index
- **pass_a_mongo_upsert.py**: Uploads full document metadata to MongoDB (final stage)

### Pass D: Vector Embeddings
- **pass_d_hayhooks.py**: Generates OpenAI embeddings for 500-600 character chunks with 50-char overlap
- Stores embeddings in Cassandra (ttrpg_vectors.embeddings table)
- **pass_d_checksum.py**: Records embedded chunk count for validation

### Pass E: Knowledge Graph
- **pass_e_graph_builder.py**: Builds graph artifacts (nodes: Document, Chunk, Term, Category; edges: CONTAINS, PART_OF, MENTIONS)
- **pass_e_neo4j_upsert.py**: Upserts graph data into Neo4j with batched MERGE operations

### Pass F: Validation & Consistency
- **pass_f_consistency_check.py**: Cross-store integrity checks (MongoDB ↔ Cassandra ↔ Neo4j)
- Generates hgrn_db_remediations.json and hgrn_pipeline_suggestions.md
- Validates source grounding, chunk quality, term normalization, graph invariants
"""

QA_SYSTEM_PROMPT = """You are a senior QA manager reviewing an ingestion pipeline log file.

Your responsibilities:
1. Identify issues, errors, warnings, and performance bottlenecks
2. Classify issues by severity (critical, high, medium, low)
3. Generate single-issue remediation prompts for AI developers
4. Focus on actionable, specific problems with clear reproduction steps

For each issue you identify, create a remediation prompt with:
- **Issue Type**: (error, performance, data_quality, configuration)
- **Severity**: (critical, high, medium, low)
- **Pass**: Which pipeline pass is affected
- **Summary**: One-sentence description
- **Details**: Specific error messages, line numbers, or metrics
- **Reproduction**: Steps to reproduce the issue
- **Suggested Fix**: Technical approach to resolve

Output Format:
Return a JSON object with an "issues" key containing an array of issue objects:
{
  "issues": [
    {
      "issue_type": "error|performance|data_quality|configuration",
      "severity": "critical|high|medium|low",
      "pass": "gate_0|pass_a|pass_b|pass_c|pass_d|pass_e|pass_f",
      "summary": "Brief description",
      "details": "Specific information from logs",
      "reproduction_steps": ["step 1", "step 2"],
      "suggested_fix": "Technical solution approach",
      "log_excerpt": "Relevant log lines"
    }
  ]
}

If no issues are found, return: {"issues": []}

Focus on real problems. Do not create issues for expected warnings or normal operations.
"""


class Gate1LogAnalyzerError(Exception):
    """Base exception for Gate 1 log analyzer errors."""
    pass


def load_log_file(log_path: Path) -> str:
    """
    Load log file content.

    Args:
        log_path: Path to log file

    Returns:
        Log file content as string

    Raises:
        Gate1LogAnalyzerError: If file cannot be read
    """
    if not log_path.exists():
        raise Gate1LogAnalyzerError(f"Log file not found: {log_path}")

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            raise Gate1LogAnalyzerError(f"Log file is empty: {log_path}")

        return content
    except IOError as e:
        raise Gate1LogAnalyzerError(f"Failed to read log file: {e}")


def analyze_log_with_openai(
    log_content: str,
    model: str,
    project: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Analyze log content using OpenAI API.

    Args:
        log_content: Log file content
        model: OpenAI model name
        project: OpenAI project ID (optional)

    Returns:
        List of issue dictionaries

    Raises:
        Gate1LogAnalyzerError: If API call fails
    """
    api_key = read_secret("openai_api_key", "OPENAI_API_KEY")
    if not api_key:
        raise Gate1LogAnalyzerError(
            "OPENAI_API_KEY not found in Docker secrets or environment.\n"
            "Create Docker secret: echo 'sk-...' | docker secret create openai_api_key -"
        )

    try:
        client = OpenAI(api_key=api_key)

        # Construct user message with log content and pass descriptions
        user_message = f"{PASS_DESCRIPTIONS}\n\n## Log Content\n\n{log_content}"

        # Prepare API call parameters
        api_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "response_format": {"type": "json_object"}
        }

        # Add project if specified
        if project:
            # Note: Project parameter may vary based on OpenAI API version
            # Adjust this if needed for your API configuration
            pass

        print(f"Calling OpenAI API with model: {model}")
        response = client.chat.completions.create(**api_params)

        # Parse response
        response_content = response.choices[0].message.content
        result = json.loads(response_content)

        # Handle multiple possible response formats robustly
        if isinstance(result, list):
            # Direct array format
            issues = result
        elif isinstance(result, dict):
            # Try multiple possible keys that might contain the issues array
            for key in ["issues", "problems", "findings", "errors", "analysis", "results"]:
                if key in result and isinstance(result[key], list):
                    issues = result[key]
                    break
            else:
                # No known key with array found, try to extract array values
                array_values = [v for v in result.values() if isinstance(v, list)]
                if array_values:
                    # Take first array found in the response
                    issues = array_values[0]
                elif all(k in result for k in ["issue_type", "severity", "summary"]):
                    # Single issue object, wrap in array
                    issues = [result]
                else:
                    # Cannot extract issues from response structure
                    raise Gate1LogAnalyzerError(
                        f"Cannot extract issues array from response. "
                        f"Response keys: {list(result.keys())}, "
                        f"Expected 'issues' key or array value."
                    )
        else:
            raise Gate1LogAnalyzerError(f"Unexpected response type: {type(result)}")

        return issues

    except json.JSONDecodeError as e:
        raise Gate1LogAnalyzerError(f"Failed to parse OpenAI response as JSON: {e}")
    except Exception as e:
        raise Gate1LogAnalyzerError(f"OpenAI API error: {e}")


def create_remediation_prompt(issue: Dict[str, Any], output_dir: Path) -> Path:
    """
    Create a remediation prompt file for a detected issue.

    Args:
        issue: Issue dictionary from OpenAI analysis
        output_dir: Output directory for prompt files

    Returns:
        Path to created prompt file
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    issue_type = issue.get("issue_type", "unknown")
    severity = issue.get("severity", "unknown")
    filename = f"{timestamp}_{issue_type}_{severity}.md"
    filepath = output_dir / filename

    # Generate prompt content
    prompt_content = f"""# Ingestion Pipeline Issue Remediation

**Generated**: {datetime.utcnow().isoformat()}Z
**Issue Type**: {issue.get('issue_type', 'N/A')}
**Severity**: {issue.get('severity', 'N/A')}
**Pass**: {issue.get('pass', 'N/A')}

## Summary

{issue.get('summary', 'No summary provided')}

## Details

{issue.get('details', 'No details provided')}

## Log Excerpt

```
{issue.get('log_excerpt', 'No log excerpt provided')}
```

## Reproduction Steps

"""

    # Add reproduction steps
    repro_steps = issue.get('reproduction_steps', [])
    if repro_steps:
        for i, step in enumerate(repro_steps, 1):
            prompt_content += f"{i}. {step}\n"
    else:
        prompt_content += "No reproduction steps provided.\n"

    prompt_content += f"""
## Suggested Fix

{issue.get('suggested_fix', 'No suggested fix provided')}

## Action Required

This prompt is for human review. Please:
1. Verify the issue is real and not a false positive
2. Assign priority based on impact
3. Create a task for an AI developer to implement the fix
4. Test the fix in a non-production environment first

---

*Generated by gate_1_log_analyzer.py v{__version__}*
"""

    # Write prompt file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(prompt_content)

    return filepath


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Analyze ingestion logs with OpenAI for QA',
        add_help=False
    )

    parser.add_argument(
        'log_file',
        nargs='?',
        type=Path,
        help='Path to ingestion log file'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f'Output directory for prompts (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=DEFAULT_MODEL,
        help=f'OpenAI model (default: {DEFAULT_MODEL})'
    )
    parser.add_argument(
        '--project',
        type=str,
        default=DEFAULT_PROJECT,
        help=f'OpenAI project ID (default: {DEFAULT_PROJECT})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze without calling OpenAI API'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'gate_1_log_analyzer v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    if not args.log_file:
        parser.print_help()
        sys.exit(1)

    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        print(f"Gate 1 Log Analyzer v{__version__}")
        print(f"Log file: {args.log_file}")
        print(f"Model: {args.model}")
        print(f"Output directory: {args.output}")
        print()

        # Load log file
        print("Loading log file...")
        log_content = load_log_file(args.log_file)
        print(f"[OK] Loaded {len(log_content):,} characters")

        if args.dry_run:
            print("\n--dry-run mode: Skipping OpenAI API call")
            print("Log file loaded successfully. Analysis would be performed here.")
            return 0

        # Analyze with OpenAI
        print("\nAnalyzing log with OpenAI...")
        issues = analyze_log_with_openai(log_content, args.model, args.project)
        print(f"[OK] Identified {len(issues)} issues")

        if not issues:
            print("\n[OK] No issues detected in log file")
            return 0

        # Create remediation prompts
        print(f"\nCreating remediation prompts in {args.output}...")
        created_files = []

        for i, issue in enumerate(issues, 1):
            prompt_file = create_remediation_prompt(issue, args.output)
            created_files.append(prompt_file)

            severity = issue.get('severity', 'unknown')
            summary = issue.get('summary', 'No summary')
            print(f"  [{i}/{len(issues)}] {severity.upper()}: {summary[:60]}...")

        print(f"\n[OK] Created {len(created_files)} remediation prompt(s)")
        print(f"\nPrompts saved to: {args.output}")
        print("\n[WARNING] IMPORTANT: Review prompts manually before executing fixes!")

        return 0

    except Gate1LogAnalyzerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
