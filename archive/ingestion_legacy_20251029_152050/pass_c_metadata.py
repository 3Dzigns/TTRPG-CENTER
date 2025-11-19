#!/usr/bin/env python3
"""
pass_c_metadata.py - Full Document Metadata Extraction (Pass C)
================================================================

Extracts comprehensive metadata from all Pass C element files (all document parts).
Takes Pass B manifest as input, auto-discovers element files, combines data, and
generates complete metadata including structure, categories, and term index.

Similar to Pass A metadata extraction but operates on full multi-part documents.

Usage:
  pass_c_metadata.py <pass_b_manifest> [options]
  pass_c_metadata.py -v | --version
  pass_c_metadata.py -? | --help

Arguments:
  pass_b_manifest    Path to Pass B manifest JSON

Options:
  -o, --output DIR       Output directory (default: same as Pass B output)
  --pass-c-dir DIR       Pass C elements directory (default: /Transfer_Station/Pass_C_Out)
  -s, --system STR       Game system (PF1E|PF2E|DND5E|auto) (default: auto)
  -p, --publisher STR    Publisher name (default: auto-detect)
  --gate-marker FILE     Gate 0 marker file for document metadata linkage
  -v, --version          Show version
  -?, --help             Show this help

Examples:
  # Basic extraction from Pass B manifest
  pass_c_metadata.py /Transfer_Station/Pass_B_Out/document_manifest.json

  # With Gate 0 marker integration
  pass_c_metadata.py /Transfer_Station/Pass_B_Out/document_manifest.json \
    --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json

  # Custom Pass C directory
  pass_c_metadata.py /Transfer_Station/Pass_B_Out/document_manifest.json \
    --pass-c-dir /custom/path

Output:
  {document_id}_pass_c_metadata.json in Pass C output directory

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from path_utils import resolve_transfer_path


__version__ = "1.0.0"

DEFAULT_PASS_C_DIR = resolve_transfer_path("Pass_C_Out")


class PassCMetadataError(Exception):
    """Base exception for Pass C metadata extraction errors."""
    pass


def load_pass_b_manifest(manifest_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Load Pass B manifest and extract document_id and parts.

    Args:
        manifest_path: Path to Pass B manifest JSON

    Returns:
        Tuple of (document_id, parts list)

    Raises:
        PassCMetadataError: If manifest cannot be loaded or is invalid
    """
    if not manifest_path.exists():
        raise PassCMetadataError(f"Pass B manifest not found: {manifest_path}")

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        raise PassCMetadataError(f"Invalid JSON in manifest: {e}")
    except IOError as e:
        raise PassCMetadataError(f"Failed to read manifest: {e}")

    # Extract required fields
    document_id = manifest.get('document_id')
    parts = manifest.get('parts', [])

    if not document_id:
        raise PassCMetadataError("Pass B manifest missing 'document_id' field")
    if not parts:
        raise PassCMetadataError("Pass B manifest missing or empty 'parts' field")

    return document_id, parts


def discover_element_files(
    document_id: str,
    parts: List[Dict[str, Any]],
    pass_c_dir: Path
) -> List[Path]:
    """
    Discover all Pass C element files based on Pass B manifest parts.

    Args:
        document_id: Document identifier
        parts: List of part dictionaries from Pass B manifest
        pass_c_dir: Directory containing Pass C element files

    Returns:
        List of paths to element files (sorted by part number)

    Raises:
        PassCMetadataError: If element files cannot be found
    """
    element_files = []

    for part_info in parts:
        part_num = part_info.get('part')
        if part_num is None:
            continue

        # Pattern: {document_id}_part##_elements.json
        element_filename = f"{document_id}_part{part_num:02d}_elements.json"
        element_path = pass_c_dir / element_filename

        if not element_path.exists():
            raise PassCMetadataError(
                f"Element file not found: {element_filename}\n"
                f"Expected at: {element_path}"
            )

        element_files.append(element_path)

    if not element_files:
        raise PassCMetadataError(f"No element files discovered for document: {document_id}")

    return sorted(element_files)


def load_all_elements(element_files: List[Path]) -> List[Dict[str, Any]]:
    """
    Load and combine all element files.

    Args:
        element_files: List of paths to element JSON files

    Returns:
        Combined list of all elements from all parts

    Raises:
        PassCMetadataError: If element files cannot be loaded
    """
    all_elements = []

    for file_path in element_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                elements = json.load(f)

            if not isinstance(elements, list):
                raise PassCMetadataError(
                    f"Invalid format in {file_path.name}: expected list, got {type(elements)}"
                )

            all_elements.extend(elements)

        except json.JSONDecodeError as e:
            raise PassCMetadataError(f"Invalid JSON in {file_path.name}: {e}")
        except IOError as e:
            raise PassCMetadataError(f"Failed to read {file_path.name}: {e}")

    return all_elements


def load_gate_marker(marker_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load and validate Gate 0 marker file.

    Args:
        marker_path: Path to Gate 0 marker file

    Returns:
        Parsed marker data or None if invalid

    Raises:
        PassCMetadataError: If marker file cannot be read or is invalid
    """
    if not marker_path.exists():
        raise PassCMetadataError(f"Gate marker file not found: {marker_path}")

    try:
        with open(marker_path, 'r', encoding='utf-8') as f:
            marker_data = json.load(f)
    except json.JSONDecodeError as e:
        raise PassCMetadataError(f"Invalid JSON in gate marker: {e}")
    except IOError as e:
        raise PassCMetadataError(f"Failed to read gate marker: {e}")

    # Validate required fields
    required_fields = ['document_id', 'original_filename', 'sha256_hash']
    missing_fields = [field for field in required_fields if field not in marker_data]

    if missing_fields:
        raise PassCMetadataError(
            f"Gate marker missing required fields: {', '.join(missing_fields)}\n"
            f"This file was not created by gate_0_hash.py"
        )

    return marker_data


class FullDocumentMetadataExtractor:
    """Extract structured metadata from full document elements."""

    # Game system detection patterns (same as Pass A)
    SYSTEM_PATTERNS = {
        'PF1E': [r'pathfinder\s+(?:roleplaying\s+game|rpg)', r'paizo\s+publishing', r'3\.5\s+compatible'],
        'PF2E': [r'pathfinder\s+(?:second\s+edition|2e)', r'pathfinder\s+core\s+rulebook\s+(?:2nd|second)'],
        'DND5E': [r'd&d\s+5(?:th|e)', r'dungeons?\s+(?:and|&)\s+dragons?\s+5', r'wizards\s+of\s+the\s+coast'],
        'STARFINDER': [r'starfinder'],
        'CALL_OF_CTHULHU': [r'call\s+of\s+cthulhu', r'chaosium'],
    }

    # Common category patterns
    CATEGORY_PATTERNS = {
        'character_creation': [r'character', r'races?', r'classes?', r'backgrounds?', r'ancestr(?:y|ies)'],
        'combat': [r'combat', r'weapons?', r'armor', r'actions?', r'fighting'],
        'magic': [r'magic', r'spells?', r'rituals?', r'casting', r'arcane'],
        'equipment': [r'equipment', r'gear', r'items?', r'treasure'],
        'rules': [r'rules', r'mechanics', r'gameplay'],
        'setting': [r'setting', r'world', r'lore', r'history'],
        'game_master': [r'(?:game\s+master|gm|dm)', r'running', r'adventures?'],
    }

    def __init__(self, elements: List[Dict[str, Any]]):
        self.elements = elements
        self.titles = [e for e in elements if e.get('type') == 'Title']
        self.text_elements = [e for e in elements if e.get('type') in ('NarrativeText', 'Text')]

    def detect_system(self, explicit_system: Optional[str] = None) -> str:
        """
        Detect game system from document content.

        Args:
            explicit_system: User-specified system (overrides detection)

        Returns:
            Detected system code (e.g., 'PF2E', 'DND5E')
        """
        if explicit_system and explicit_system != 'auto':
            return explicit_system.upper()

        # Sample first 100 elements for detection
        sample_text = ' '.join(
            e.get('text', '') for e in self.elements[:100]
        ).lower()

        # Check patterns
        for system, patterns in self.SYSTEM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, sample_text, re.I):
                    return system

        return 'UNKNOWN'

    def detect_publisher(self, explicit_publisher: Optional[str] = None) -> str:
        """Detect publisher from document content."""
        if explicit_publisher and explicit_publisher != 'auto':
            return explicit_publisher

        sample_text = ' '.join(
            e.get('text', '') for e in self.elements[:50]
        ).lower()

        # Common publishers
        if 'paizo' in sample_text:
            return 'Paizo Publishing'
        if 'wizards of the coast' in sample_text or 'wotc' in sample_text:
            return 'Wizards of the Coast'
        if 'chaosium' in sample_text:
            return 'Chaosium'

        return 'Unknown'

    def categorize_title(self, title_text: str) -> Optional[str]:
        """Categorize a title based on text patterns."""
        title_lower = title_text.lower()

        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title_lower):
                    return category

        return None

    def extract_terms(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Extract important terms with page references.

        Args:
            document_id: Document identifier for term linkage

        Returns:
            List of term dictionaries
        """
        # Extract terms from titles (most important concepts)
        terms = {}

        for title_elem in self.titles:
            text = title_elem.get('text', '').strip()
            if len(text) < 3:  # Skip very short titles
                continue

            # Get page number
            page = title_elem.get('metadata', {}).get('page_number', 'unknown')
            if isinstance(page, (int, float)):
                page = int(page)
            elif isinstance(page, str) and page.isdigit():
                page = int(page)
            else:
                page = None

            # Categorize
            category = self.categorize_title(text)

            # Add or update term
            if text not in terms:
                terms[text] = {
                    'term': text,
                    'category': category,
                    'page_references': [],
                    'document_id': document_id
                }

            if page is not None and page not in terms[text]['page_references']:
                terms[text]['page_references'].append(page)

        # Convert to list and sort by term
        term_list = sorted(terms.values(), key=lambda t: t['term'].lower())

        return term_list

    def build_categories(self) -> Dict[str, List[str]]:
        """Build category hierarchy from titles."""
        categories = defaultdict(list)

        for title_elem in self.titles:
            text = title_elem.get('text', '').strip()
            category = self.categorize_title(text)

            if category and text not in categories[category]:
                categories[category].append(text)

        return dict(categories)

    def extract_metadata(
        self,
        document_id: str,
        explicit_system: Optional[str] = None,
        explicit_publisher: Optional[str] = None,
        gate_marker: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract complete metadata structure.

        Args:
            document_id: Document identifier
            explicit_system: User-specified game system
            explicit_publisher: User-specified publisher
            gate_marker: Gate 0 marker data for document linkage

        Returns:
            Complete metadata dictionary
        """
        system = self.detect_system(explicit_system)
        publisher = self.detect_publisher(explicit_publisher)
        categories = self.build_categories()
        terms = self.extract_terms(document_id)

        metadata = {
            'extraction': {
                'system': system,
                'publisher': publisher,
                'extraction_date': datetime.utcnow().isoformat() + 'Z'
            },
            'categories': categories,
            'terms': terms,
            'statistics': {
                'total_elements': len(self.elements),
                'title_elements': len(self.titles),
                'text_elements': len(self.text_elements),
                'unique_categories': len(categories),
                'unique_terms': len(terms)
            }
        }

        # Add Gate 0 document information if available
        if gate_marker:
            metadata['document'] = gate_marker
        else:
            # Legacy format without Gate 0 integration
            metadata['document_id'] = document_id

        return metadata


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Extract metadata from Pass C elements (Pass C)",
        add_help=False
    )

    parser.add_argument('pass_b_manifest', help="Path to Pass B manifest JSON")
    parser.add_argument('-o', '--output', type=Path, help="Output directory")
    parser.add_argument('--pass-c-dir', type=Path, default=DEFAULT_PASS_C_DIR,
                        help=f"Pass C elements directory (default: {DEFAULT_PASS_C_DIR})")
    parser.add_argument('-s', '--system', default='auto',
                        help="Game system (PF1E|PF2E|DND5E|auto)")
    parser.add_argument('-p', '--publisher', default='auto',
                        help="Publisher name (default: auto-detect)")
    parser.add_argument('--gate-marker', type=Path,
                        help="Gate 0 marker file for document linkage")
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-?', '--help', action='help', help="Show this help message and exit")

    args = parser.parse_args()

    try:
        manifest_path = Path(args.pass_b_manifest)

        print(f"Loading Pass B manifest from {manifest_path.name}...")
        document_id, parts = load_pass_b_manifest(manifest_path)
        print(f"✓ Document: {document_id} ({len(parts)} parts)")

        # Discover element files
        print(f"\nDiscovering element files in {args.pass_c_dir}...")
        element_files = discover_element_files(document_id, parts, args.pass_c_dir)
        print(f"✓ Found {len(element_files)} element files")

        # Load all elements
        print("\nLoading elements from all parts...")
        all_elements = load_all_elements(element_files)
        print(f"✓ Loaded {len(all_elements)} total elements")

        # Load Gate 0 marker if provided
        gate_marker = None
        if args.gate_marker:
            print(f"\nLoading Gate 0 marker...")
            gate_marker = load_gate_marker(args.gate_marker)
            print(f"✓ Loaded marker for: {gate_marker.get('original_filename')}")

        # Extract metadata
        print("\nExtracting metadata...")
        extractor = FullDocumentMetadataExtractor(all_elements)
        metadata = extractor.extract_metadata(
            document_id,
            args.system,
            args.publisher,
            gate_marker
        )

        print(f"✓ System: {metadata['extraction']['system']}")
        print(f"✓ Publisher: {metadata['extraction']['publisher']}")
        print(f"✓ Categories: {metadata['statistics']['unique_categories']}")
        print(f"✓ Terms: {metadata['statistics']['unique_terms']}")

        # Determine output directory and file
        if args.output:
            output_dir = args.output
        else:
            output_dir = manifest_path.parent

        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}_pass_c_metadata.json"

        # Write metadata
        print(f"\nWriting metadata to {output_file.name}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Pass C metadata extraction complete")
        print(f"  Document: {document_id}")
        print(f"  Parts: {len(parts)}")
        print(f"  Elements: {len(all_elements)}")
        print(f"  Terms: {len(metadata['terms'])}")
        print(f"  Output: {output_file.name}")

    except PassCMetadataError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
