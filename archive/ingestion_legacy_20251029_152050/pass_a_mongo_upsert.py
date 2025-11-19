#!/usr/bin/env python3
"""
pass_a_mongo_upsert.py (Postgres edition)
=========================================

Historic filename retained for compatibility, but the implementation now
persists Pass A dictionary artifacts into Postgres via dictionary_store.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dictionary_store import DictionaryStore, DictionaryStoreError

__version__ = "3.0.0"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def detect_document_id(metadata: Dict[str, Any], elements_path: Path) -> str:
    doc = metadata.get("document") or {}
    if doc.get("document_id"):
        return doc["document_id"]
    if metadata.get("document_id"):
        return metadata["document_id"]
    # Fall back to filename-derived ID for backward compatibility
    return elements_path.stem.replace("_elements", "").replace("_toc", "")


def extract_gate_info(metadata: Dict[str, Any], gate_marker: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    gate = gate_marker or metadata.get("document") or {}
    info = {
        "source_path": gate.get("original_path") or metadata.get("source_file"),
        "sha256": gate.get("sha256_hash") or metadata.get("sha256_hash"),
        "file_size_bytes": gate.get("file_size_bytes"),
        "computed_at": gate.get("computed_at"),
    }
    # Remove None entries
    return {k: v for k, v in info.items() if v is not None}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist Pass A dictionary artifacts into Postgres.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("elements_json", type=Path, help="Path to Pass A elements JSON")
    parser.add_argument("metadata_json", type=Path, help="Path to Pass A metadata JSON")
    parser.add_argument(
        "--stage",
        choices=["pass_a", "pass_c"],
        default="pass_a",
        help="Logical stage label stored alongside the document",
    )
    parser.add_argument(
        "--gate-marker",
        type=Path,
        help="Optional Gate 0 marker file for richer document metadata",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse inputs and print summary without writing to Postgres",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{__version__}")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        metadata = load_json(args.metadata_json)
        elements = load_json(args.elements_json)
        gate_marker = load_json(args.gate_marker) if args.gate_marker else None

        document_id = detect_document_id(metadata, args.elements_json)
        gate_info = extract_gate_info(metadata, gate_marker)

        # Summaries for logging
        term_count = len(metadata.get("terms") or [])
        toc_count = len(metadata.get("toc_structure") or [])
        cat_count = len((metadata.get("categories") or {}).get("by_system", [])) if isinstance(
            metadata.get("categories"), dict
        ) else len(metadata.get("categories") or [])

        print(f"[Pass A] Preparing dictionary upsert for document_id={document_id}")
        print(f"         terms={term_count}, toc_entries={toc_count}, categories={cat_count}")

        if args.dry_run:
            print("Dry run enabled - skipping Postgres write")
            return 0

        store = DictionaryStore()
        summary = store.upsert_document(
            document_id=document_id,
            stage=args.stage,
            metadata=metadata,
            elements=elements,
            toc=metadata.get("toc_structure"),
            categories=metadata.get("categories"),
            terms=metadata.get("terms"),
            statistics=metadata.get("statistics"),
            warnings=metadata.get("warnings"),
            gate_metadata=gate_marker,
            source_path=gate_info.get("source_path"),
            sha256=gate_info.get("sha256"),
            file_size_bytes=gate_info.get("file_size_bytes"),
            computed_at=gate_info.get("computed_at"),
        )
        store.close()

        print(
            f"[Pass A] Dictionary stored in Postgres (stage={summary.stage}, "
            f"terms={summary.term_count}, toc_entries={summary.toc_count})"
        )
        return 0

    except (json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except DictionaryStoreError as exc:
        print(f"Dictionary store error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected failure
        print(f"Unexpected failure: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
