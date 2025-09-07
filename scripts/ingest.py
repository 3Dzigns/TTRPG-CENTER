#!/usr/bin/env python3
"""
Ingestion runner using existing Pass A/B and Astra loader.

Usage:
  python scripts/ingest.py --env dev --empty-first --pdf "E:/path/Core Rulebook.pdf" --pdf "E:/path/Ultimate Magic.pdf"

Notes:
- Writes artifacts under artifacts/ingest/{ENV}/{JOB_ID}/
- Loads Pass B enriched (or Pass A) into Astra collection ttrpg_chunks_{ENV}
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))  # ensure repo root on path

from src_common.pass_a_parser import PassAParser
from src_common.pass_b_enricher import PassBEnricher
from src_common.astra_loader import AstraLoader
from src_common.logging import get_logger, setup_logging


def _job_id_for(pdf: Path) -> str:
    base = pdf.stem.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"job_{base}_{ts}"


def run(pdf_paths: list[Path], env: str, empty_first: bool) -> int:
    setup_logging()
    logger = get_logger("ingest_runner")
    os.environ["APP_ENV"] = env

    loader = AstraLoader(env)
    if empty_first:
        logger.info(f"Emptying Astra collection ttrpg_chunks_{env}")
        ok = loader.empty_collection()
        if not ok:
            logger.warning("Failed to empty collection or running in simulation mode")

    for pdf in pdf_paths:
        if not pdf.exists():
            logger.error(f"PDF not found: {pdf}")
            continue
        job_id = _job_id_for(pdf)
        out_dir = Path(f"artifacts/ingest/{env}/{job_id}")
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Pass A: parsing {pdf}", extra={"job_id": job_id})
        parser = PassAParser(job_id, env)
        pa_out = parser.parse_pdf(pdf, out_dir)
        pa_file = out_dir / f"{job_id}_pass_a_chunks.json"
        if not pa_file.exists():
            logger.error(f"Pass A output not found: {pa_file}")
            continue

        logger.info(f"Pass B: enriching {pa_file}", extra={"job_id": job_id})
        enricher = PassBEnricher(job_id)
        pb_out = enricher.enrich_chunks(pa_file, out_dir)
        pb_file = out_dir / f"{job_id}_pass_b_enriched.json"
        if pb_file.exists():
            load_file = pb_file
        else:
            load_file = pa_file
        
        logger.info(f"Loading into Astra from {load_file}")
        result = loader.load_chunks_from_file(load_file)
        if not result.success:
            logger.error(f"Load failed for {load_file}: {result.error_message}")
        else:
            logger.info(f"Loaded {result.chunks_loaded} chunks into {result.collection_name}")

    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("APP_ENV", "dev"), choices=["dev", "test", "prod"])
    ap.add_argument("--empty-first", action="store_true")
    ap.add_argument("--pdf", action="append", default=[], help="PDF file to ingest (can be specified multiple times)")
    args = ap.parse_args(argv)

    pdfs = [Path(p) for p in args.pdf]
    if not pdfs:
        print("No --pdf provided", file=sys.stderr)
        return 2
    return run(pdfs, args.env, args.empty_first)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
