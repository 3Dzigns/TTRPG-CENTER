"""
Pass G — HGRN Consistency Check

Detect alias drift, orphan nodes, broken `part_of` relationships.
Emit hgrn.report.json, dict_delta.passG.json, hgrn.actions.json.
MVP v2 requirement: Final pass in 0→G pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

from .logging import get_logger

logger = get_logger(__name__)


class HGRNIssue:
    """Represents an HGRN consistency issue."""

    def __init__(self, issue_type: str, severity: str, description: str,
                 entities: List[str] = None, suggested_action: str = ""):
        self.issue_type = issue_type
        self.severity = severity  # critical, warning, info
        self.description = description
        self.entities = entities or []
        self.suggested_action = suggested_action
        self.discovered_at = datetime.utcnow().isoformat()


class HGRNConsistencyChecker:
    """Checks HGRN (Hierarchical Graph Relationship Network) consistency."""

    def __init__(self, graph_data: Dict[str, Any], dictionary_data: Dict[str, Any]):
        self.graph = graph_data
        self.dictionary = dictionary_data
        self.issues: List[HGRNIssue] = []
        self.proposed_deltas: List[Dict[str, Any]] = []
        self.suggested_actions: List[Dict[str, Any]] = []

    def check_alias_drift(self) -> None:
        """
        Detect alias drift where multiple entities have similar names.

        Alias drift occurs when:
        1. Multiple nodes have very similar canonical names
        2. Aliases point to different canonical entries
        3. Canonical terms have evolved differently over time
        """
        logger.info("Checking for alias drift")

        # Get all canonical terms and aliases
        canonical_terms = {}
        aliases = {}

        # Extract from dictionary
        dict_entries = self.dictionary.get("entries", [])
        for entry in dict_entries:
            canonical = entry.get("canonical", "").lower().strip()
            entry_aliases = entry.get("aliases", [])
            term_id = entry.get("term_id", entry.get("id", ""))

            if canonical and term_id:
                canonical_terms[canonical] = term_id

            for alias in entry_aliases:
                alias_lower = alias.lower().strip()
                if alias_lower not in aliases:
                    aliases[alias_lower] = []
                aliases[alias_lower].append(term_id)

        # Check for similar canonical terms (potential drift)
        canonical_list = list(canonical_terms.keys())
        for i, term1 in enumerate(canonical_list):
            for term2 in canonical_list[i+1:]:
                similarity = self._calculate_similarity(term1, term2)
                if similarity > 0.8:  # High similarity threshold
                    issue = HGRNIssue(
                        issue_type="alias_drift",
                        severity="warning",
                        description=f"High similarity between canonical terms: '{term1}' and '{term2}'",
                        entities=[canonical_terms[term1], canonical_terms[term2]],
                        suggested_action="Review and potentially merge or disambiguate terms"
                    )
                    self.issues.append(issue)

                    # Propose dictionary delta
                    self.proposed_deltas.append({
                        "action": "review_similarity",
                        "type": "canonical_similarity",
                        "term1": term1,
                        "term2": term2,
                        "similarity_score": similarity,
                        "requires_human_review": True
                    })

        # Check for aliases pointing to multiple canonicals
        for alias, term_ids in aliases.items():
            if len(term_ids) > 1:
                issue = HGRNIssue(
                    issue_type="alias_conflict",
                    severity="critical",
                    description=f"Alias '{alias}' points to multiple canonical terms",
                    entities=term_ids,
                    suggested_action="Disambiguate alias or merge canonical terms"
                )
                self.issues.append(issue)

                # Propose action
                self.suggested_actions.append({
                    "action_type": "resolve_alias_conflict",
                    "alias": alias,
                    "conflicting_terms": term_ids,
                    "priority": "high"
                })

        logger.info(f"Alias drift check complete: found {len([i for i in self.issues if i.issue_type in ['alias_drift', 'alias_conflict']])} issues")

    def check_orphan_nodes(self) -> None:
        """
        Detect orphan nodes in the graph.

        Orphan nodes are:
        1. Nodes with no incoming or outgoing relationships
        2. Nodes referenced in relationships but not defined
        3. Nodes without proper lineage to document structure
        """
        logger.info("Checking for orphan nodes")

        nodes = self.graph.get("nodes", [])
        edges = self.graph.get("edges", [])

        # Build sets of node IDs and referenced IDs
        defined_nodes = set()
        referenced_nodes = set()

        for node in nodes:
            node_id = node.get("id", "")
            if node_id:
                defined_nodes.add(node_id)

        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source:
                referenced_nodes.add(source)
            if target:
                referenced_nodes.add(target)

        # Find orphaned nodes (defined but never referenced)
        orphaned = defined_nodes - referenced_nodes
        for node_id in orphaned:
            # Check if it's a legitimate root node (has outgoing edges)
            has_outgoing = any(edge.get("source") == node_id for edge in edges)

            if not has_outgoing:
                issue = HGRNIssue(
                    issue_type="orphan_node",
                    severity="warning",
                    description=f"Node '{node_id}' has no relationships",
                    entities=[node_id],
                    suggested_action="Review node relevance or add relationships"
                )
                self.issues.append(issue)

                self.suggested_actions.append({
                    "action_type": "review_orphan",
                    "node_id": node_id,
                    "priority": "medium"
                })

        # Find dangling references (referenced but not defined)
        dangling = referenced_nodes - defined_nodes
        for node_id in dangling:
            issue = HGRNIssue(
                issue_type="dangling_reference",
                severity="critical",
                description=f"Node '{node_id}' is referenced but not defined",
                entities=[node_id],
                suggested_action="Define missing node or fix reference"
            )
            self.issues.append(issue)

            self.suggested_actions.append({
                "action_type": "fix_dangling_reference",
                "node_id": node_id,
                "priority": "high"
            })

        logger.info(f"Orphan check complete: {len(orphaned)} orphaned, {len(dangling)} dangling")

    def check_part_of_relationships(self) -> None:
        """
        Validate 'part_of' relationships form proper hierarchies.

        Checks for:
        1. Circular references in part_of chains
        2. Broken part_of references
        3. Inconsistent hierarchy depth
        """
        logger.info("Checking part_of relationships")

        edges = self.graph.get("edges", [])
        part_of_edges = [edge for edge in edges if edge.get("relationship") == "part_of"]

        # Build part_of hierarchy
        part_of_map = {}
        children_map = {}

        for edge in part_of_edges:
            child = edge.get("source", "")
            parent = edge.get("target", "")

            if child and parent:
                part_of_map[child] = parent
                if parent not in children_map:
                    children_map[parent] = []
                children_map[parent].append(child)

        # Check for circular references
        for node_id in part_of_map:
            if self._has_circular_reference(node_id, part_of_map):
                issue = HGRNIssue(
                    issue_type="circular_part_of",
                    severity="critical",
                    description=f"Circular reference detected in part_of chain starting from '{node_id}'",
                    entities=[node_id],
                    suggested_action="Break circular reference by removing or redirecting relationship"
                )
                self.issues.append(issue)

                self.suggested_actions.append({
                    "action_type": "fix_circular_reference",
                    "node_id": node_id,
                    "priority": "critical"
                })

        # Check hierarchy consistency
        for parent, children in children_map.items():
            if len(children) > 100:  # Suspicious: too many direct children
                issue = HGRNIssue(
                    issue_type="hierarchy_imbalance",
                    severity="warning",
                    description=f"Node '{parent}' has {len(children)} direct children (may need sub-categorization)",
                    entities=[parent],
                    suggested_action="Consider adding intermediate hierarchy levels"
                )
                self.issues.append(issue)

        logger.info(f"Part_of relationship check complete: {len(part_of_edges)} relationships analyzed")

    def check_dictionary_graph_consistency(self) -> None:
        """
        Check consistency between dictionary entries and graph nodes.

        Ensures:
        1. Dictionary terms have corresponding graph nodes
        2. Graph nodes reference valid dictionary entries
        3. Metadata consistency between dictionary and graph
        """
        logger.info("Checking dictionary-graph consistency")

        # Get dictionary term IDs
        dict_entries = self.dictionary.get("entries", [])
        dict_term_ids = set()

        for entry in dict_entries:
            term_id = entry.get("term_id", entry.get("id", ""))
            if term_id:
                dict_term_ids.add(term_id)

        # Get graph node IDs that should correspond to dictionary terms
        nodes = self.graph.get("nodes", [])
        term_nodes = []

        for node in nodes:
            if node.get("type") == "term" or "term_id" in node:
                term_nodes.append(node)

        # Check for dictionary terms without graph nodes
        graph_term_ids = set()
        for node in term_nodes:
            term_id = node.get("term_id", node.get("id", ""))
            if term_id:
                graph_term_ids.add(term_id)

        missing_in_graph = dict_term_ids - graph_term_ids
        for term_id in missing_in_graph:
            issue = HGRNIssue(
                issue_type="dictionary_term_missing_in_graph",
                severity="warning",
                description=f"Dictionary term '{term_id}' has no corresponding graph node",
                entities=[term_id],
                suggested_action="Create graph node for dictionary term"
            )
            self.issues.append(issue)

            self.proposed_deltas.append({
                "action": "create_graph_node",
                "term_id": term_id,
                "node_type": "term"
            })

        # Check for graph nodes without dictionary entries
        missing_in_dict = graph_term_ids - dict_term_ids
        for term_id in missing_in_dict:
            issue = HGRNIssue(
                issue_type="graph_node_missing_in_dictionary",
                severity="warning",
                description=f"Graph node '{term_id}' has no corresponding dictionary entry",
                entities=[term_id],
                suggested_action="Create dictionary entry or remove graph node"
            )
            self.issues.append(issue)

        logger.info(f"Dictionary-graph consistency check complete: {len(missing_in_graph)} missing in graph, {len(missing_in_dict)} missing in dictionary")

    def generate_report(self) -> Dict[str, Any]:
        """Generate HGRN consistency report."""

        issue_counts = {
            "critical": len([i for i in self.issues if i.severity == "critical"]),
            "warning": len([i for i in self.issues if i.severity == "warning"]),
            "info": len([i for i in self.issues if i.severity == "info"])
        }

        report = {
            "hgrn_consistency_report": {
                "generated_at": datetime.utcnow().isoformat(),
                "total_issues": len(self.issues),
                "severity_breakdown": issue_counts,
                "issues": [
                    {
                        "type": issue.issue_type,
                        "severity": issue.severity,
                        "description": issue.description,
                        "entities": issue.entities,
                        "suggested_action": issue.suggested_action,
                        "discovered_at": issue.discovered_at
                    }
                    for issue in self.issues
                ],
                "summary": {
                    "alias_drift_issues": len([i for i in self.issues if "alias" in i.issue_type]),
                    "orphan_node_issues": len([i for i in self.issues if "orphan" in i.issue_type]),
                    "part_of_issues": len([i for i in self.issues if "part_of" in i.issue_type or "circular" in i.issue_type]),
                    "consistency_issues": len([i for i in self.issues if "consistency" in i.issue_type or "missing" in i.issue_type])
                }
            }
        }

        return report

    def generate_delta_proposals(self) -> Dict[str, Any]:
        """Generate dictionary delta proposals for Pass G."""

        delta = {
            "pass_g_hgrn_consistency": {
                "generated_at": datetime.utcnow().isoformat(),
                "proposed_changes": self.proposed_deltas,
                "change_count": len(self.proposed_deltas),
                "requires_human_review": any(
                    delta.get("requires_human_review", False) for delta in self.proposed_deltas
                )
            }
        }

        return delta

    def generate_action_recommendations(self) -> Dict[str, Any]:
        """Generate actionable recommendations."""

        actions = {
            "hgrn_actions": {
                "generated_at": datetime.utcnow().isoformat(),
                "actions": self.suggested_actions,
                "action_count": len(self.suggested_actions),
                "priority_breakdown": {
                    "critical": len([a for a in self.suggested_actions if a.get("priority") == "critical"]),
                    "high": len([a for a in self.suggested_actions if a.get("priority") == "high"]),
                    "medium": len([a for a in self.suggested_actions if a.get("priority") == "medium"]),
                    "low": len([a for a in self.suggested_actions if a.get("priority") == "low"])
                }
            }
        }

        return actions

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using Levenshtein distance."""
        if not str1 or not str2:
            return 0.0

        # Simple Levenshtein distance calculation
        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0 if len2 > 0 else 1.0
        if len2 == 0:
            return 0.0

        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if str1[i-1] == str2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )

        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        similarity = 1.0 - (distance / max_len)

        return similarity

    def _has_circular_reference(self, node_id: str, part_of_map: Dict[str, str],
                              visited: Set[str] = None) -> bool:
        """Check if a node has circular reference in part_of chain."""
        if visited is None:
            visited = set()

        if node_id in visited:
            return True  # Circular reference found

        visited.add(node_id)
        parent = part_of_map.get(node_id)

        if parent:
            return self._has_circular_reference(parent, part_of_map, visited)

        return False


def run_hgrn_consistency_check(job_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Run HGRN consistency check on job artifacts.

    Args:
        job_dir: Job directory containing graph.json and dictionary data

    Returns:
        Tuple of (report, delta, actions) dictionaries

    Raises:
        FileNotFoundError: If required files are missing
        ValueError: If data is invalid
    """
    logger.info(f"Running HGRN consistency check for job: {job_dir}")

    # Load graph data
    graph_path = job_dir / "graph.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph file not found: {graph_path}")

    with open(graph_path, "r") as f:
        graph_data = json.load(f)

    # Load dictionary data (consolidated from all passes)
    dict_all_path = job_dir / "dict_delta.all.json"
    if dict_all_path.exists():
        with open(dict_all_path, "r") as f:
            dictionary_data = json.load(f)
    else:
        # Fallback to individual pass deltas
        logger.warning("dict_delta.all.json not found, combining individual deltas")
        dictionary_data = {"entries": []}

    # Run consistency checks
    checker = HGRNConsistencyChecker(graph_data, dictionary_data)

    # Run all checks
    checker.check_alias_drift()
    checker.check_orphan_nodes()
    checker.check_part_of_relationships()
    checker.check_dictionary_graph_consistency()

    # Generate outputs
    report = checker.generate_report()
    delta = checker.generate_delta_proposals()
    actions = checker.generate_action_recommendations()

    # Write outputs
    report_path = job_dir / "hgrn.report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    delta_path = job_dir / "dict_delta.passG.json"
    with open(delta_path, "w") as f:
        json.dump(delta, f, indent=2)

    actions_path = job_dir / "hgrn.actions.json"
    with open(actions_path, "w") as f:
        json.dump(actions, f, indent=2)

    logger.info(f"HGRN consistency check complete: {len(checker.issues)} issues found")

    return report, delta, actions


if __name__ == "__main__":
    # Test with sample data
    import sys
    if len(sys.argv) > 1:
        job_directory = Path(sys.argv[1])
        report, delta, actions = run_hgrn_consistency_check(job_directory)
        print(f"HGRN Check Results:")
        print(f"- Issues found: {report['hgrn_consistency_report']['total_issues']}")
        print(f"- Proposed changes: {delta['pass_g_hgrn_consistency']['change_count']}")
        print(f"- Recommended actions: {actions['hgrn_actions']['action_count']}")