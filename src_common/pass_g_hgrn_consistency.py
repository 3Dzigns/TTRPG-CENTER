"""Pass G HGRN consistency checks producing reports and actions."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from src_common.logging import get_logger
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete

logger = get_logger(__name__)


@dataclass
class PassGResult:
    """Structured Pass G result."""

    job_id: str
    issues_found: int
    critical_issues: int
    artifacts: List[str]
    processing_time_ms: int
    success: bool = True
    error_message: Optional[str] = None


class HGRNChecker:
    """Runs graph consistency checks and emits reports."""

    def __init__(self, job_id: str, env: str, log_file_path: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = log_file_path

    def process(self, job_dir: Path) -> PassGResult:
        started_at = time.perf_counter()

        # Pass start logging
        log_pass_start("G", "HGRN Validation & Quality Gates", self.job_log_file)

        pass_dir = job_dir / "pass_g"
        pass_dir.mkdir(parents=True, exist_ok=True)

        # Validate artifact integrity first
        log_to_job("Validating artifact integrity...", self.job_log_file, "info", "G")
        integrity_issues = self._validate_artifact_integrity(job_dir)

        graph_path = job_dir / "pass_e" / "graph.json"
        if not graph_path.exists():
            raise FileNotFoundError(f"Graph artifact missing: {graph_path}")

        logger.info(f"Pass G: Loading graph from {graph_path.name}")
        with graph_path.open("r", encoding="utf-8") as handle:
            graph = json.load(handle)

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        logger.info(f"Pass G: Loaded graph with {len(nodes)} nodes and {len(edges)} edges")
        log_to_job(f"Loaded graph: {len(nodes)} nodes, {len(edges)} edges", self.job_log_file, "info", "G")

        logger.info(f"Pass G: Starting HGRN consistency analysis (this may take 10-30s)")
        log_to_job("Starting HGRN consistency analysis (10-30s operation)", self.job_log_file, "info", "G")
        analysis_started = time.perf_counter()

        graph_issues = self._detect_issues(nodes, edges)
        all_issues = integrity_issues + graph_issues
        actions = self._recommend_actions(all_issues)

        analysis_duration = time.perf_counter() - analysis_started
        logger.info(f"Pass G: HGRN analysis completed in {analysis_duration:.1f}s ({len(all_issues)} issues found)")
        log_to_job(f"HGRN analysis completed in {analysis_duration:.1f}s ({len(all_issues)} issues found)", self.job_log_file, "info", "G")

        report_path = pass_dir / "hgrn.report.json"
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "issues": all_issues,
                    "integrity_issues_count": len(integrity_issues),
                    "graph_issues_count": len(graph_issues),
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )

        delta_path = pass_dir / "dict_delta.passG.json"
        with delta_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "issues": all_issues,
                    "actions": actions,
                },
                handle,
                indent=2,
            )

        actions_path = pass_dir / "hgrn.actions.json"
        with actions_path.open("w", encoding="utf-8") as handle:
            json.dump(actions, handle, indent=2)

        artifacts = [
            report_path.relative_to(job_dir).as_posix(),
            delta_path.relative_to(job_dir).as_posix(),
            actions_path.relative_to(job_dir).as_posix(),
        ]

        critical_count = sum(1 for item in all_issues if item.get("severity") == "critical")
        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        duration_seconds = processing_time_ms / 1000

        logger.info(
            "pass_g_complete",
            extra={
                "job_id": self.job_id,
                "issue_count": len(all_issues),
                "critical": critical_count,
                "integrity_issues": len(integrity_issues),
                "graph_issues": len(graph_issues),
                "duration_ms": processing_time_ms,
            },
        )

        # Pass complete logging
        stats = {
            "issues_found": len(all_issues),
            "critical_issues": critical_count,
            "integrity_issues": len(integrity_issues),
            "graph_issues": len(graph_issues),
            "artifacts_generated": len(artifacts)
        }
        log_pass_complete("G", duration_seconds, stats, self.job_log_file)

        return PassGResult(
            job_id=self.job_id,
            issues_found=len(all_issues),
            critical_issues=critical_count,
            artifacts=artifacts,
            processing_time_ms=processing_time_ms,
        )

    def _detect_issues(self, nodes: List[Dict[str, object]], edges: List[Dict[str, object]]) -> List[Dict[str, object]]:
        issues: List[Dict[str, object]] = []
        node_ids: Set[str] = {str(node.get("id")) for node in nodes if node.get("id")}
        referenced: Set[str] = set()
        for edge in edges:
            source = str(edge.get("source")) if edge.get("source") else None
            target = str(edge.get("target")) if edge.get("target") else None
            if source:
                referenced.add(source)
            if target:
                referenced.add(target)
            if source == target and source:
                issues.append(
                    {
                        "issue_type": "self_loop",
                        "severity": "warning",
                        "description": f"Node {source} has a self referencing edge",
                    }
                )
        orphaned = node_ids - referenced
        for node_id in sorted(orphaned):
            issues.append(
                {
                    "issue_type": "orphan_node",
                    "severity": "warning",
                    "description": f"Node {node_id} is not linked",
                }
            )
        dangling = referenced - node_ids
        for node_id in sorted(dangling):
            issues.append(
                {
                    "issue_type": "dangling_reference",
                    "severity": "critical",
                    "description": f"Edge references missing node {node_id}",
                }
            )
        if not edges:
            issues.append(
                {
                    "issue_type": "empty_graph",
                    "severity": "critical",
                    "description": "Graph contains no relationships",
                }
            )
        return issues

    def _recommend_actions(self, issues: List[Dict[str, object]]) -> List[Dict[str, object]]:
        actions: List[Dict[str, object]] = []
        for issue in issues:
            issue_type = issue.get("issue_type")
            if issue_type == "dangling_reference":
                actions.append(
                    {
                        "action": "rebuild_relationship",
                        "priority": "high",
                        "details": issue.get("description"),
                    }
                )
            elif issue_type == "orphan_node":
                actions.append(
                    {
                        "action": "attach_orphan",
                        "priority": "medium",
                        "details": issue.get("description"),
                    }
                )
            elif issue_type == "empty_graph":
                actions.append(
                    {
                        "action": "trigger_reingest",
                        "priority": "high",
                        "details": issue.get("description"),
                    }
                )
        if not actions:
            actions.append({"action": "noop", "priority": "low", "details": "Graph healthy"})
        return actions

    def _validate_artifact_integrity(self, job_dir: Path) -> List[Dict[str, object]]:
        """
        Validate artifact integrity across all passes.

        Checks:
        - All expected artifacts exist
        - Checksums match (if available)
        - File sizes are reasonable
        """
        issues: List[Dict[str, object]] = []

        # Define expected artifacts per pass
        expected_artifacts = {
            "pass_a": ["_pass_a_dict.json", "_pass_a_manifest.json"],
            "pass_b": ["split_index.json"],  # Optional - only for large files
            "pass_c": ["_pass_c_chunks.jsonl", "chunk_summary.json", "dict_delta.passC.json"],
            "pass_d": ["_pass_d_vectors.jsonl", "vector_summary.json", "dict_delta.passD.json"],
            "pass_e": ["graph.json", "graph_summary.json", "dict_delta.passE.json"],
            "pass_f": ["finalization.json", "dict_delta.passF.json"],
        }

        for pass_name, artifacts in expected_artifacts.items():
            pass_dir = job_dir / pass_name

            if not pass_dir.exists():
                if pass_name == "pass_b":
                    # Pass B is optional (only for large files)
                    continue
                issues.append({
                    "issue_type": "missing_pass_directory",
                    "severity": "critical",
                    "description": f"Pass directory missing: {pass_name}",
                    "pass": pass_name
                })
                continue

            for artifact_pattern in artifacts:
                # Find files matching pattern (handles job_id prefix)
                matching_files = list(pass_dir.glob(f"*{artifact_pattern}"))

                if not matching_files:
                    if pass_name == "pass_b" or artifact_pattern == "split_index.json":
                        # Pass B artifacts are optional
                        continue

                    issues.append({
                        "issue_type": "missing_artifact",
                        "severity": "critical",
                        "description": f"Missing artifact: {pass_name}/{artifact_pattern}",
                        "pass": pass_name,
                        "artifact": artifact_pattern
                    })
                    continue

                # Validate file size (must be non-empty)
                artifact_file = matching_files[0]
                file_size = artifact_file.stat().st_size

                if file_size == 0:
                    issues.append({
                        "issue_type": "empty_artifact",
                        "severity": "critical",
                        "description": f"Empty artifact file: {artifact_file.name}",
                        "pass": pass_name,
                        "artifact": artifact_file.name
                    })

                # Log artifact found
                log_to_job(f"✓ Verified: {pass_name}/{artifact_file.name} ({file_size} bytes)", self.job_log_file, "debug", "G")

        # Validate manifest checksums if available
        manifest_file = job_dir / "manifest.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text())

                # Check if manifest has artifact checksums
                artifacts_in_manifest = manifest.get("artifacts", [])
                for artifact_info in artifacts_in_manifest:
                    artifact_path = Path(artifact_info.get("path", ""))
                    expected_checksum = artifact_info.get("checksum")

                    if artifact_path.exists() and expected_checksum:
                        actual_checksum = self._compute_file_hash(artifact_path)
                        if actual_checksum != expected_checksum:
                            issues.append({
                                "issue_type": "checksum_mismatch",
                                "severity": "critical",
                                "description": f"Checksum mismatch: {artifact_path.name}",
                                "expected": expected_checksum[:12],
                                "actual": actual_checksum[:12]
                            })
            except Exception as e:
                logger.warning(f"Failed to validate manifest checksums: {e}")

        return issues

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def run_hgrn_consistency_check(job_dir: Path, env: str, log_file_path: Optional[Path] = None) -> PassGResult:
    job_id = job_dir.name
    checker = HGRNChecker(job_id=job_id, env=env, log_file_path=log_file_path)
    return checker.process(job_dir)


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
