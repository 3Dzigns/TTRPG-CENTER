"""Answer composition pipeline for the orchestrator service."""

from __future__ import annotations

import textwrap
import time
from typing import Dict, Iterable, List, Optional, Tuple

from src_common.logging import get_logger
from src_common.orchestrator.classifier import Classification
from src_common.orchestrator.retriever import DocChunk
from src_common.orchestrator.plan_models import QueryPlan

from .llm import LLMClient
from .prompt_registry import PromptRegistry

logger = get_logger(__name__)


class AnswerComposer:
    """Compose answers with prompt templates, LLM execution, and citations."""

    def __init__(
        self,
        environment: str,
        prompt_registry: PromptRegistry,
        llm_client: LLMClient,
    ) -> None:
        self.environment = environment
        self.prompt_registry = prompt_registry
        self.llm_client = llm_client

    def compose(
        self,
        query: str,
        plan: QueryPlan,
        classification: Classification,
        chunks: List[DocChunk],
        *,
        include_citations: bool = True,
    ) -> Tuple[str, List[Dict[str, str]], Dict[str, str], float]:
        start_time = time.perf_counter()

        prompt = self._build_prompt(query, classification, chunks)
        stub_answer = self._build_stub_answer(query, chunks)
        llm_result = self.llm_client.generate(
            prompt,
            model_config=plan.model_config,
            stub_answers={"stub": stub_answer},
        )

        selected_answer = llm_result.answers.get(llm_result.selected) or stub_answer
        citations = self._build_citations(chunks) if include_citations else []
        metadata = {
            "model_used": plan.model_config.get("model", "stub") if isinstance(plan.model_config, dict) else "stub",
            "provider": llm_result.provider or "stub",
            "used_stub": str(llm_result.used_stub_llm).lower(),
        }

        latency_ms = (time.perf_counter() - start_time) * 1000
        return selected_answer, citations, metadata, latency_ms

    # ------------------------------------------------------------------
    # Helpers

    def _build_prompt(self, query: str, classification: Classification, chunks: List[DocChunk]) -> str:
        bundle = self.prompt_registry.get_prompt_bundle("answer_generation")
        system_prompt = bundle.get("systemPrompt") or self.prompt_registry.get_prompt("fact_lookup_ttrpg_rules") or (
            "You are the TTRPG Center Assistant. Answer accurately using the provided context."
        )
        user_template = bundle.get("userTemplate") or "Question: {question}\n\nContext:\n{context}\n\nAnswer concisely with citations."
        context_text = self._format_context(chunks)
        rendered_user_prompt = user_template.format(question=query, context=context_text)
        prompt = f"{system_prompt.strip()}\n\n{rendered_user_prompt.strip()}"
        intent = classification.get("intent", "unknown") if isinstance(classification, dict) else getattr(classification, "intent", "unknown")
        domain = classification.get("domain", "unknown") if isinstance(classification, dict) else getattr(classification, "domain", "unknown")
        prompt += f"\n\nIntent: {intent} | Domain: {domain}"
        return prompt

    @staticmethod
    def _format_context(chunks: Iterable[DocChunk]) -> str:
        lines: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            excerpt = textwrap.shorten(chunk.text.strip(), width=600, placeholder="...")
            lines.append(f"[{idx}] {excerpt}\nSource: {chunk.source}")
        return "\n\n".join(lines) or "No relevant context available."

    @staticmethod
    def _build_stub_answer(query: str, chunks: List[DocChunk]) -> str:
        if not chunks:
            return (
                "I could not find relevant context in the current knowledge base. "
                "Consider refining the question or ingesting additional materials."
            )
        top_chunk = chunks[0]
        excerpt = textwrap.shorten(top_chunk.text.strip(), width=400, placeholder="...")
        return (
            f"Based on the retrieved context, here is a concise summary for '{query}':\n\n"
            f"{excerpt}\n\n"
            "Citations: [1]"
        )

    @staticmethod
    def _build_citations(chunks: List[DocChunk]) -> List[Dict[str, str]]:
        citations: List[Dict[str, str]] = []
        for idx, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata or {}
            page = metadata.get("page") or metadata.get("page_number") or metadata.get("pageNumber")
            section = metadata.get("section") or metadata.get("section_id") or metadata.get("toc_path")
            label_parts = [f"Source {idx}"]
            if section:
                label_parts.append(str(section))
            if page:
                label_parts.append(f"p.{page}")
            label = " ".join(label_parts)
            citations.append(
                {
                    "source": chunk.source,
                    "label": f"[{label}]",
                    "passage": textwrap.shorten(chunk.text.strip(), width=200, placeholder="..."),
                }
            )
        return citations
