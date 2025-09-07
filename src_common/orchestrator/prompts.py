from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


class PromptError(Exception):
    pass


def _load_prompt_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_prompt(intent: str, domain: str) -> str:
    """Load prompt template for given intent/domain with fallbacks."""
    env = os.getenv("APP_ENV", "dev")
    name = f"{intent}_{domain}.txt"
    candidates = [
        Path(f"env/{env}/config/prompts/{name}"),
        Path(f"config/prompts/{name}"),
    ]
    for p in candidates:
        if p.exists():
            return _load_prompt_file(p)
    # Fallback minimal template
    return (
        "You are the TTRPG Center Assistant.\n"
        "Use only retrieved passages. Cite sources compactly.\n"
        "Style: {STYLE}\n"
        "Task: {TASK_BRIEF}\n"
        "Policy: {POLICY_SNIPPET}\n"
    )


def render_prompt(template: str, context: Dict[str, str]) -> str:
    required = ["TASK_BRIEF", "STYLE", "POLICY_SNIPPET"]
    for k in required:
        if k not in context:
            raise PromptError(f"Missing prompt token: {k}")
    out = template
    for k, v in context.items():
        out = out.replace("{" + k + "}", v)
    return out

