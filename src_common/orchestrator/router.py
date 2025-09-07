from typing import Dict, Any


def pick_model(classification: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    intent = classification.get("intent")
    complexity = classification.get("complexity")

    if intent == "code_help":
        return {"model": "gpt-4o-mini", "max_tokens": 2000, "temperature": 0.2}
    if intent in {"multi_hop_reasoning"} and complexity in {"high", "medium"}:
        return {"model": "gpt-5-large", "max_tokens": 8000, "temperature": 0.1}
    if intent in {"creative_write"}:
        return {"model": "gpt-5-large", "max_tokens": 6000, "temperature": 0.9}
    if intent in {"summarize"}:
        return {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.0}
    return {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.2}

