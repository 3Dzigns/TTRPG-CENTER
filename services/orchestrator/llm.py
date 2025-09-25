"""LLM orchestration helpers for the orchestrator service."""

from __future__ import annotations

from typing import Dict, Mapping, Optional

from src_common.orchestrator.llm_runtime import LLMResult, generate_rag_answers, resolve_llm_mode


class LLMClient:
    """Thin wrapper around shared LLM runtime utilities."""

    def __init__(self, environment: str) -> None:
        self.environment = environment

    def generate(
        self,
        prompt: str,
        *,
        model_config: Optional[Mapping[str, object]] = None,
        stub_answers: Optional[Dict[str, str]] = None,
        llm_mode: Optional[str] = None,
    ) -> LLMResult:
        mode = llm_mode or resolve_llm_mode(self.environment)
        return generate_rag_answers(prompt, model_config, stub_answers or {}, llm_mode=mode)
