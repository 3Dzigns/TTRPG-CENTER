#!/usr/bin/env python3
"""
pass_c_mongo_upsert.py (Postgres edition)
=========================================

Legacy entrypoint name preserved so existing worker/job tooling keeps
working. The script now hydrates full-document metadata (Pass C) into
Postgres via dictionary_store.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dictionary_store import DictionaryStore, DictionaryStoreError

__version__ = "3.0.0"

DEFAULT_PASS_C_DIR = Path("/Transfer_Station/Pass_C_Out")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist Pass C (full document) dictionary artifacts into Postgres.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("pass_b_manifest", type=Path, help="Path to Pass B manifest JSON")
    parser.add_argument(
        "--pass-c-dir",
        type=Path,
        default=DEFAULT_PASS_C_DIR,
        help="Directory containing Pass C outputs",
    )
    parser.add_argument(
        "--gate-marker",
        type=Path,
        help="Optional Gate 0 marker file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse inputs and print summary without writing to Postgres",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{__version__}")
    return parser


def resolve_metadata_path(manifest: Dict[str, Any], pass_c_dir: Path) -> Path:
    document_id = manifest.get("document_id")
    if not document_id:
        raise ValueError("Pass B manifest is missing document_id")
    return pass_c_dir / f"{document_id}_pass_c_metadata.json"


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        manifest = load_json(args.pass_b_manifest)
        metadata_path = resolve_metadata_path(manifest, args.pass_c_dir)
        metadata = load_json(metadata_path)
        gate_marker = load_json(args.gate_marker) if args.gate_marker else None

        document_id = metadata.get("document_id") or metadata.get("document", {}).get("document_id")
        if not document_id:
            raise ValueError("Metadata file does not contain document_id")

        print(f"[Pass C] Preparing dictionary upsert for document_id={document_id}")
        print(
            f"         manifest parts={len(manifest.get('parts', []))}, "
            f"terms={len(metadata.get('terms') or [])}"
        )

        if args.dry_run:
            print("Dry run enabled - skipping Postgres write")
            return 0

        store = DictionaryStore()
        summary = store.upsert_document(
            document_id=document_id,
            stage="pass_c",
            metadata=metadata,
            elements=None,  # Pass C metadata already aggregates document-wide details
            toc=metadata.get("toc_structure"),
            categories=metadata.get("categories"),
            terms=metadata.get("terms"),
            statistics=metadata.get("statistics"),
            warnings=metadata.get("warnings"),
            gate_metadata=gate_marker,
            source_path=metadata.get("document", {}).get("original_path"),
            sha256=metadata.get("document", {}).get("sha256_hash"),
            file_size_bytes=metadata.get("document", {}).get("file_size_bytes"),
            computed_at=metadata.get("document", {}).get("computed_at"),
        )
        store.close()

        print(
            f"[Pass C] Dictionary stored in Postgres (stage={summary.stage}, "
            f"terms={summary.term_count}, toc_entries={summary.toc_count})"
        )
        return 0

    except (json.JSONDecodeError, FileNotFoundError, ValueError) as exc:
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
