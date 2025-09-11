# src_common/pass_a_toc_parser.py
"""
Pass A: Initial ToC Parse (Prime Dictionary)

Parse Table of Contents and high-confidence headings to build a seed dictionary 
of section names, page ranges, and canonical spell/feat/class names.

Responsibilities:
- Parse ToC and extract section structure
- Identify high-confidence game terms (spells, feats, classes)
- Build seed dictionary entries
- Write dictionary terms only (no chunk upserts)
- Generate manifest with checksums/mtime

Artifacts:
- *_pass_a_dict.json: Dictionary entries extracted from ToC
- manifest.json: Checksums, metadata, validation info
"""

import json
import time
import hashlib
from pathlib import Path
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .logging import get_logger
from .toc_parser import TocParser
from .dictionary_loader import DictionaryLoader, DictEntry
from .artifact_validator import write_json_atomically
from .ttrpg_secrets import _load_env_file

logger = get_logger(__name__)


@dataclass
class PassAResult:
    """Result of Pass A ToC parsing and dictionary seeding"""
    source_file: str
    job_id: str
    dictionary_entries: int
    sections_parsed: int
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassATocParser:
    """Pass A: Initial ToC Parse and Dictionary Seeding"""
    
    def __init__(self, job_id: str, env: str = "dev"):
        self.job_id = job_id
        self.env = env
        self.toc_parser = TocParser()
        self.dict_loader = DictionaryLoader(env)
        
    def process_pdf(self, pdf_path: Path, output_dir: Path, force_dict_init: bool = False) -> PassAResult:
        """
        Process PDF for Pass A: ToC parsing and dictionary seeding
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output artifacts
            force_dict_init: Force dictionary initialization even if exists
            
        Returns:
            PassAResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Pass A starting: ToC parse for {pdf_path.name}")
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Parse document structure and ToC
            logger.info("Parsing document structure and ToC...")
            outline = self.toc_parser.parse_document_structure(pdf_path)
            sections_count = len(outline.entries)

            # Extract dictionary entries from ToC structure (if any)
            dict_entries: List[DictEntry] = []
            upserted_count = 0
            if sections_count == 0:
                logger.info(f"No ToC entries found in {pdf_path.name}; proceeding without dictionary seeding")
            else:
                dict_entries = self._extract_dictionary_from_toc(outline, pdf_path.name)
                logger.info(f"Extracted {len(dict_entries)} dictionary entries from {sections_count} ToC sections")

                # Try to upsert dictionary entries to database; do not fail Pass A if this step fails
                if dict_entries:
                    try:
                        upserted_count = self.dict_loader.upsert_entries(dict_entries)
                        logger.info(f"Upserted {upserted_count} dictionary entries to database")
                    except Exception as e:
                        logger.warning(f"Dictionary upsert failed (non-fatal for Pass A): {e}")
            
            # Write Pass A artifact
            dict_artifact_path = output_dir / f"{self.job_id}_pass_a_dict.json"
            dict_data = {
                "source": pdf_path.name,
                "job_id": self.job_id,
                "pass": "A",
                "stage": "toc_dictionary_seed",
                "entries_count": len(dict_entries),
                "upserted_count": upserted_count,
                "sections_parsed": sections_count,
                "dictionary_entries": [
                    {
                        "term": entry.term,
                        "definition": entry.definition,
                        "category": entry.category,
                        "sources": entry.sources
                    }
                    for entry in dict_entries
                ],
                "created_at": time.time()
            }
            
            write_json_atomically(dict_data, dict_artifact_path)
            logger.info(f"Wrote Pass A dictionary artifact: {dict_artifact_path}")
            
            # Generate manifest
            manifest_path = self._generate_manifest(
                output_dir, 
                pdf_path, 
                [dict_artifact_path],
                dict_entries,
                sections_count
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            logger.info(f"Pass A completed for {pdf_path.name} in {processing_time_ms}ms")
            
            return PassAResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                dictionary_entries=upserted_count,
                sections_parsed=sections_count,
                processing_time_ms=processing_time_ms,
                artifacts=[str(dict_artifact_path)],
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass A failed for {pdf_path.name}: {e}")
            
            return PassAResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                dictionary_entries=0,
                sections_parsed=0,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _extract_dictionary_from_toc(self, outline, source_name: str) -> List[DictEntry]:
        """Extract dictionary entries from ToC structure"""
        entries = []
        
        # Game term patterns for high-confidence identification
        spell_patterns = ["spell", "magic", "incantation", "enchantment"]
        feat_patterns = ["feat", "ability", "talent", "skill"]
        class_patterns = ["class", "archetype", "prestige", "profession"]
        equipment_patterns = ["weapon", "armor", "item", "equipment", "gear"]
        rule_patterns = ["rule", "mechanic", "system", "combat", "action"]
        
        for entry in outline.entries:
            title = entry.title.strip()
            if not title or len(title) < 3:
                continue
                
            title_lower = title.lower()
            category = "general"
            definition = f"Section from {source_name}, page {entry.page}"
            
            # Categorize based on title content
            if any(pattern in title_lower for pattern in spell_patterns):
                category = "spells"
                definition = f"Spell or magical ability described in {source_name}, page {entry.page}"
            elif any(pattern in title_lower for pattern in feat_patterns):
                category = "feats"
                definition = f"Character feat or ability from {source_name}, page {entry.page}"
            elif any(pattern in title_lower for pattern in class_patterns):
                category = "classes"
                definition = f"Character class or archetype from {source_name}, page {entry.page}"
            elif any(pattern in title_lower for pattern in equipment_patterns):
                category = "equipment"
                definition = f"Equipment or gear from {source_name}, page {entry.page}"
            elif any(pattern in title_lower for pattern in rule_patterns):
                category = "mechanics"
                definition = f"Game rule or mechanic from {source_name}, page {entry.page}"
            elif entry.level <= 2:  # High-level sections
                category = "general"
                definition = f"Major section from {source_name}, page {entry.page}"
            else:
                # Skip very low-level entries to avoid noise
                continue
            
            # Create dictionary entry
            dict_entry = DictEntry(
                term=title,
                definition=definition[:400],  # Limit definition length
                category=category,
                sources=[{
                    "source": source_name,
                    "method": "toc_parse",
                    "page": entry.page,
                    "section_id": entry.section_id,
                    "level": entry.level
                }]
            )
            entries.append(dict_entry)
        
        return entries
    
    def _generate_manifest(
        self, 
        output_dir: Path, 
        pdf_path: Path, 
        artifacts: List[Path],
        dict_entries: List[DictEntry],
        sections_count: int
    ) -> Path:
        """Generate manifest.json with checksums and metadata"""
        
        manifest_data = {
            "job_id": self.job_id,
            "source_file": pdf_path.name,
            "source_path": str(pdf_path),
            "pass": "A",
            "stage": "toc_dictionary_seed",
            "completed_passes": ["A"],
            "environment": self.env,
            "created_at": time.time(),
            "chunks": [],  # BUG-016: Always include chunks key for schema validation
            "source_info": {
                "file_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
                "file_mtime": pdf_path.stat().st_mtime if pdf_path.exists() else 0,
                "source_hash": self._compute_file_hash(pdf_path) if pdf_path.exists() else ""
            },
            "pass_a_results": {
                "dictionary_entries_extracted": len(dict_entries),
                "sections_parsed": sections_count,
                "categories": list(set(entry.category for entry in dict_entries))
            },
            "artifacts": []
        }
        
        # Add artifact checksums
        for artifact_path in artifacts:
            if artifact_path.exists():
                manifest_data["artifacts"].append({
                    "file": artifact_path.name,
                    "path": str(artifact_path),
                    "size": artifact_path.stat().st_size,
                    "mtime": artifact_path.stat().st_mtime,
                    "checksum": self._compute_file_hash(artifact_path)
                })
        
        # Write manifest
        manifest_path = output_dir / "manifest.json"
        write_json_atomically(manifest_data, manifest_path)
        
        return manifest_path
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def process_pass_a(pdf_path: Path, output_dir: Path, job_id: str, env: str = "dev", force_dict_init: bool = False) -> PassAResult:
    """
    Convenience function for Pass A processing
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Directory for output artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        force_dict_init: Force dictionary initialization even if exists
        
    Returns:
        PassAResult with processing statistics
    """
    parser = PassATocParser(job_id, env)
    return parser.process_pdf(pdf_path, output_dir, force_dict_init=force_dict_init)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass A: ToC Parse and Dictionary Seeding")
    parser.add_argument("pdf_path", help="Path to source PDF")
    parser.add_argument("output_dir", help="Output directory for artifacts")
    parser.add_argument("--job-id", help="Job ID (default: auto-generated)")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    job_id = args.job_id or f"job_{int(time.time())}"
    
    result = process_pass_a(pdf_path, output_dir, job_id, args.env)
    
    print(f"Pass A Result:")
    print(f"  Success: {result.success}")
    print(f"  Dictionary entries: {result.dictionary_entries}")
    print(f"  Sections parsed: {result.sections_parsed}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)
