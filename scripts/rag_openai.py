#!/usr/bin/env python3
"""
Run Phase 2 query end-to-end using Astra-backed retrieval and get an OpenAI answer
based only on the retrieved chunks (with citations).

Usage:
  python scripts/rag_openai.py --env dev --q "What level is Fireball?" --q "Explain the Dodge feat" --q "How many spells..."

Requires:
  - ASTRA_* env vars (from .env) for Astra retrieval to return results
  - OPENAI_API_KEY in env (from .env) to call OpenAI API
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from src_common.app import app
from src_common.orchestrator.prompts import load_prompt, render_prompt


def load_dotenv_into_env(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def openai_chat(model: str, system_prompt: str, user_prompt: str, api_key: str) -> str:
    # Map router model names to deployed models with GPT-5 support
    gpt5_enabled = os.getenv("OPENAI_GPT5_ENABLED", "false").lower() == "true"

    model_map = {
        "gpt-5-large": "gpt-5" if gpt5_enabled else "gpt-4o",  # Use GPT-5 when enabled, fallback to gpt-4o
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4o": "gpt-4o",
    }
    model_name = model_map.get(model, model)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    with httpx.Client(timeout=60) as client:
        try:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Log model usage telemetry
            usage = data.get("usage", {})
            print(f"Model usage: {model_name}, prompt_tokens: {usage.get('prompt_tokens', 0)}, completion_tokens: {usage.get('completion_tokens', 0)}, total_tokens: {usage.get('total_tokens', 0)}", file=sys.stderr)

            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            # If GPT-5 is unavailable (404, 400) and we were trying GPT-5, fallback to GPT-4o
            if model_name == "gpt-5" and e.response.status_code in (400, 404):
                print(f"GPT-5 unavailable (status {e.response.status_code}), falling back to GPT-4o", file=sys.stderr)
                fallback_payload = payload.copy()
                fallback_payload["model"] = "gpt-4o"
                resp = client.post(url, headers=headers, json=fallback_payload)
                resp.raise_for_status()
                data = resp.json()

                # Log fallback model usage telemetry
                usage = data.get("usage", {})
                print(f"Fallback model usage: gpt-4o, prompt_tokens: {usage.get('prompt_tokens', 0)}, completion_tokens: {usage.get('completion_tokens', 0)}, total_tokens: {usage.get('total_tokens', 0)}", file=sys.stderr)

                return data["choices"][0]["message"]["content"].strip()
            else:
                raise


def run_query(env: str, query: str) -> Dict[str, Any]:
    os.environ["APP_ENV"] = env
    client = TestClient(app)
    resp = client.post("/rag/ask", json={"query": query})
    resp.raise_for_status()
    data = resp.json()
    cls = data.get("classification", {})
    plan = data.get("plan", {})
    model_cfg = data.get("model", {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.2})
    chunks = data.get("retrieved", [])

    # Build prompt
    tmpl = load_prompt(cls["intent"], cls["domain"])
    system_prompt = render_prompt(
        tmpl,
        {
            "TASK_BRIEF": query,
            "STYLE": "concise, cite sources in [id] format",
            "POLICY_SNIPPET": "Use only the provided context. If insufficient, say so. Include citations [id] for each claim.",
        },
    )
    # Assemble user context
    context_lines: List[str] = []
    for i, c in enumerate(chunks, 1):
        snippet = (c.get("text") or "")
        # Keep each snippet manageable
        if len(snippet) > 1500:
            snippet = snippet[:1500] + "…"
        context_lines.append(f"[{i}] {snippet}\nSource: {c.get('source')}")
    user_prompt = f"Context:\n\n" + "\n\n".join(context_lines) + f"\n\nQuestion: {query}\nAnswer concisely with [n] citations."

    # Call OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; load from .env or environment")
    answer = openai_chat(model_cfg["model"], system_prompt, user_prompt, api_key)

    return {
        "classification": cls,
        "plan": plan,
        "model": model_cfg,
        "retrieved": chunks,
        "answer": answer,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("APP_ENV", "dev"))
    ap.add_argument("--q", action="append", default=[], help="Query to run (repeatable)")
    args = ap.parse_args(argv)

    # Load .env
    load_dotenv_into_env(Path(".env"))

    if not args.q:
        print("No queries provided. Use --q ...", file=sys.stderr)
        return 2

    for q in args.q:
        print(f"=== QUERY: {q}")
        try:
            result = run_query(args.env, q)
            prov = [r["source"] for r in result["retrieved"]]
            print("Provenance:", prov)
            print("Model:", result["model"]) 
            print("Classification:", result["classification"])
            print("\nOpenAI Answer:\n", result["answer"]) 
            print("---\n")
        except Exception as e:
            print("Error:", e)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
