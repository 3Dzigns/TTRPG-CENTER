"""Pass G HGRN consistency checks producing reports and actions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from src_common.logging import get_logger

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

    def __init__(self, job_id: str, env: str) -> None:
        self.job_id = job_id
        self.env = env

    def process(self, job_dir: Path) -> PassGResult:
        started_at = time.perf_counter()
        pass_dir = job_dir / "pass_g"
        pass_dir.mkdir(parents=True, exist_ok=True)

        graph_path = job_dir / "pass_e" / "graph.json"
        if not graph_path.exists():
            raise FileNotFoundError(f"Graph artifact missing: {graph_path}")

        with graph_path.open("r", encoding="utf-8") as handle:
            graph = json.load(handle)

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        issues = self._detect_issues(nodes, edges)
        actions = self._recommend_actions(issues)

        report_path = pass_dir / "hgrn.report.json"
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "issues": issues,
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
                    "issues": issues,
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

        critical_count = sum(1 for item in issues if item.get("severity") == "critical")
        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "pass_g_complete",
            extra={
                "job_id": self.job_id,
                "issue_count": len(issues),
                "critical": critical_count,
                "duration_ms": processing_time_ms,
            },
        )

        return PassGResult(
            job_id=self.job_id,
            issues_found=len(issues),
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


def run_hgrn_consistency_check(job_dir: Path, env: str) -> PassGResult:
    job_id = job_dir.name
    checker = HGRNChecker(job_id=job_id, env=env)
    return checker.process(job_dir)


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
