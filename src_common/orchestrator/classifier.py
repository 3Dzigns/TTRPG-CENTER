from typing import Literal, TypedDict

Intent = Literal[
    "fact_lookup",
    "procedural_howto",
    "creative_write",
    "code_help",
    "summarize",
    "multi_hop_reasoning",
]
Domain = Literal["ttrpg_rules", "ttrpg_lore", "admin", "system", "unknown"]


class Classification(TypedDict):
    intent: Intent
    domain: Domain
    complexity: Literal["low", "medium", "high"]
    needs_tools: bool
    confidence: float


def classify_query(q: str) -> Classification:
    """
    Heuristic-first classifier. Fast, local, no network.
    Returns a coarse classification used by policy/model routing.
    """
    q_low = (q or "").lower()

    if any(k in q_low for k in ["spell", "feat", "rule", " dc ", "action", "damage"]):
        domain: Domain = "ttrpg_rules"
    elif any(k in q_low for k in ["lore", "kingdom", "pantheon", "deity", "myth"]):
        domain = "ttrpg_lore"
    elif any(k in q_low for k in ["admin", "status", "healthz", "logs", "ingestion"]):
        domain = "admin"
    else:
        domain = "unknown"

    if len(q_low) < 120 and ("what is" in q_low or q_low.strip().startswith("what")):
        intent: Intent = "fact_lookup"
    elif any(k in q_low for k in ["how do i", "steps", "procedure", "guide", "walkthrough"]):
        intent = "procedural_howto"
    elif any(k in q_low for k in ["write", "story", "flavor", "npc", "dialogue"]):
        intent = "creative_write"
    elif "summarize" in q_low or "tl;dr" in q_low or "summary" in q_low:
        intent = "summarize"
    elif any(k in q_low for k in ["code", "python", "stacktrace", "error:"]):
        intent = "code_help"
    else:
        intent = "multi_hop_reasoning"

    complexity = (
        "high"
        if len(q_low) > 500 or "compare" in q_low or "versus" in q_low or "vs" in q_low
        else ("medium" if len(q_low) > 200 else "low")
    )
    needs_tools = intent in {
        "fact_lookup",
        "multi_hop_reasoning",
        "summarize",
        "code_help",
    }

    return {
        "intent": intent,
        "domain": domain,
        "complexity": complexity,
        "needs_tools": needs_tools,
        "confidence": 0.72,
    }

