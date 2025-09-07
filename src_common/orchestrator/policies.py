from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_POLICIES: Dict[str, Any] = {
    "ttrpg_rules": {
        "fact_lookup": {
            "low": {
                "vector_top_k": 5,
                "filters": {"system": "PF2E"},
                "types": ["spell", "feat"],
                "rerank": "mmr",
                "expand": ["ruleset_aliases"],
            },
            "medium": {
                "vector_top_k": 8,
                "filters": {"system": "PF2E"},
                "rerank": "sbert",
                "graph_depth": 1,
            },
            "high": {
                "vector_top_k": 12,
                "filters": {"system": "PF2E"},
                "rerank": "sbert",
                "graph_depth": 2,
            },
        }
    },
    "unknown": {
        "multi_hop_reasoning": {
            "low": {"vector_top_k": 8, "rerank": "mmr"},
            "medium": {"vector_top_k": 10, "rerank": "sbert", "graph_depth": 1},
            "high": {
                "vector_top_k": 12,
                "rerank": "sbert",
                "graph_depth": 2,
                "self_consistency": 3,
            },
        }
    },
}


def _safe_load_yaml(path: Path) -> Dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_policies() -> Dict[str, Any]:
    """Load retrieval policies from env-specific path or fallback defaults."""
    env = os.getenv("APP_ENV", "dev")
    candidates = [
        Path(f"env/{env}/config/retrieval_policies.yaml"),
        Path("config/retrieval_policies.yaml"),
    ]
    for p in candidates:
        if p.exists():
            data = _safe_load_yaml(p)
            if data:
                return data
    return DEFAULT_POLICIES


def choose_plan(policies: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
    d = classification.get("domain", "unknown")
    i = classification.get("intent", "multi_hop_reasoning")
    c = classification.get("complexity", "low")
    # Guardrails
    plan = (
        policies.get(d, {}).get(i, {}).get(c)
        or policies.get("unknown", {}).get(i, {}).get(c)
        or {"vector_top_k": 8, "rerank": "mmr"}
    )
    # Cost guards
    if plan.get("graph_depth", 0) and int(plan["graph_depth"]) > 3:
        plan["graph_depth"] = 3
    if plan.get("vector_top_k", 0) and int(plan["vector_top_k"]) > 50:
        plan["vector_top_k"] = 50
    return plan

