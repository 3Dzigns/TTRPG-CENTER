#!/usr/bin/env python3
"""
Generate BUG-xxx markdown reports by scanning a nightly log.

Usage:
  python scripts/post_run_bug_scan.py --log-file env/dev/logs/nightly_YYYYMMDD_HHMMSS.log \
      [--out-dir docs/bugs] [--env dev] [--dry-run]

Behavior:
- Parses the log for pass failures and pipeline errors.
- Groups identical failures by a stable signature.
- Creates one BUG-###.md per unique failure signature (or prints in dry-run).

Safe defaults:
- Skips known non-bug signals (e.g., "No ToC entries found").
- Does not contact any external services.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


PASS_FAIL_RE = re.compile(
    r"progress_callback\s+-\s+ERROR\s+-\s+Job\s+[^\s]+\s+(pass_[a-z_]+)\s+FAILED.*?:\s+(.*)",
    re.IGNORECASE,
)

PIPELINE_FAIL_RE = re.compile(
    r"pipeline_adapter\s+-\s+ERROR\s+-\s+Pipeline execution failed.*?error:\s+(.*)",
    re.IGNORECASE,
)

JOB_FAIL_RE = re.compile(
    r"nightly_runner\s+-\s+ERROR\s+-\s+Job\s+[^\s]+\s+FAILED.*?Error:\s+(.*)",
    re.IGNORECASE,
)

IGNORED_PATTERNS = (
    # Non-bugs by policy
    re.compile(r"No ToC entries found", re.IGNORECASE),
)

# Dependency/path issues (even if INFO/WARNING) to flag as bugs
PATH_ISSUE_PATTERNS = [
    re.compile(r"No such file or directory", re.IGNORECASE),
    re.compile(r"The system cannot find the (file|path) specified", re.IGNORECASE),
    re.compile(r"is not recognized as an (internal|external) command", re.IGNORECASE),
    re.compile(r"CommandNotFoundException", re.IGNORECASE),
    re.compile(r"not found:\s*(pdfinfo|pdftoppm|tesseract)", re.IGNORECASE),
    re.compile(r"Error opening data file.*tessdata", re.IGNORECASE),
    re.compile(r"TESSDATA_PREFIX", re.IGNORECASE),
    re.compile(r"POPPLER_PATH|TESSERACT_PATH|tessdata", re.IGNORECASE),
]


def line_has_ignored_reason(msg: str) -> bool:
    return any(p.search(msg) for p in IGNORED_PATTERNS)


def normalize_message(msg: str) -> str:
    # Strip volatile tokens like job ids and elapsed times
    m = re.sub(r"adapter_job_\d+", "adapter_job", msg)
    m = re.sub(r"\b\d+\.\d+s\b", "{secs}", m)
    m = re.sub(r"C:.*?TTRPG_Center\\", "<REPO>/", m)
    return m.strip()


def extract_failures(text: str) -> List[Tuple[str, str, str]]:
    """Return list of (source, pass_or_scope, message) failure tuples."""
    failures: List[Tuple[str, str, str]] = []

    for line in text.splitlines():
        m = PASS_FAIL_RE.search(line)
        if m:
            p, msg = m.group(1), m.group(2)
            if not line_has_ignored_reason(msg):
                failures.append(("pass", p, msg.strip()))
            continue

        m = PIPELINE_FAIL_RE.search(line)
        if m:
            msg = m.group(1)
            if not line_has_ignored_reason(msg):
                failures.append(("pipeline", "pipeline", msg.strip()))
            continue

        m = JOB_FAIL_RE.search(line)
        if m:
            msg = m.group(1)
            if not line_has_ignored_reason(msg):
                failures.append(("runner", "job", msg.strip()))

        # Dependency/path issues (collect even if not marked ERROR)
        else:
            for pat in PATH_ISSUE_PATTERNS:
                if pat.search(line):
                    if not line_has_ignored_reason(line):
                        failures.append(("env", "path_dependency", line.strip()))
                    break

    return failures


def signature(scope: str, message: str) -> str:
    base = f"{scope}|{normalize_message(message)}".encode("utf-8")
    return hashlib.sha1(base).hexdigest()[:12]


def next_bug_id(out_dir: Path) -> int:
    max_id = 0
    if out_dir.exists():
        for p in out_dir.glob("BUG-*.md"):
            try:
                n = int(p.stem.split("-")[1])
                if n > max_id:
                    max_id = n
            except Exception:
                continue
    return max_id + 1


def classify(message: str) -> Tuple[str, str]:
    """Return (category, severity) from the message."""
    msg = message.lower()
    if "no module named" in msg or "importerror" in msg or "unstructured" in msg:
        return ("dependency", "P1")
    if "credentials" in msg or "astra" in msg or "token" in msg:
        return ("configuration", "P1")
    if "takes" in msg and "positional arguments" in msg:
        return ("code", "P0")
    if "logical split" in msg:
        return ("algorithm", "P2")
    return ("runtime", "P2")


def render_bug_md(bug_id: int, env: str, log_path: Path, scope: str, message: str, excerpts: List[str]) -> str:
    cat, sev = classify(message)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sig = signature(scope, message)
    title = f"BUG-{bug_id:03d}: {scope.upper()} failure - {message[:72]}".rstrip()
    lines = [
        f"# {title}",
        "",
        "## Summary",
        f"- **When:** {ts}",
        f"- **Env:** {env}",
        f"- **Category:** {cat}",
        f"- **Severity:** {sev}",
        f"- **Signature:** `{sig}`",
        "",
        "## Primary Error",
        f"```",
        message,
        f"```",
        "",
        "## Reproduction",
        "- Trigger nightly ingestion via Task Scheduler or:",
        f"  `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\run_nightly_ingestion.ps1 -Env {env} -Uploads <path>`",
        "- Inspect the log for errors.",
        "",
        "## Log Excerpts",
    ]
    for ex in excerpts[:8]:
        lines.extend(["```", ex.strip(), "```"])
    lines.extend([
        "",
        "## Affected",
        f"- Log: `{log_path.as_posix()}`",
        "",
        "## Hypothesis",
        "- Fill in likely root cause and context.",
        "",
        "## Proposed Fix",
        "- Fill actionable steps and owners.",
    ])
    return "\n".join(lines) + "\n"


def maybe_enrich_with_openai(content_md: str, env: str, scope: str, message: str, log_path: Path, lines: List[str], model: str | None = None) -> str | None:
    """Optionally enrich BUG content using OpenAI if configured.

    Requires OPENAI_API_KEY and --ai-enrich flag (or BUG_AI_ENRICH=true).
    """
    enabled = os.getenv("BUG_AI_ENRICH", "false").strip().lower() in ("1", "true", "yes") or False
    if not enabled:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    try:
        client = OpenAI()
        use_model = model or os.getenv("BUG_AI_MODEL", "gpt-4o-mini")
        # Build a compact prompt with context and desired sections
        prompt = (
            "You are a senior software engineer writing a detailed bug report.\n"
            "Given the failure context below, produce an enriched report with sections:\n"
            "- Summary (2-3 lines)\n"
            "- Root Cause Hypothesis\n"
            "- User Stories (bullet points, role-feature-benefit)\n"
            "- Acceptance Criteria (numbered, testable)\n"
            "- Test Cases (unit, functional, e2e)\n"
            "- Proposed Fix (specific code areas, steps)\n"
            "- Risks & Rollback\n"
            "- Observability (logs/metrics to add)\n\n"
            f"Environment: {env}\n"
            f"Scope: {scope}\n"
            f"Primary Error: {message}\n"
            f"Log: {log_path.as_posix()}\n"
            "Excerpts:\n" + "\n".join(lines[:10])
        )

        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": "You write precise, structured engineering reports."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=int(os.getenv("BUG_AI_MAX_TOKENS", "800")),
        )
        enriched = resp.choices[0].message.content or ""
        if not enriched.strip():
            return None
        return "\n".join([
            "",
            "## AI Enrichment",
            enriched.strip(),
            "",
        ])
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-file", required=True)
    ap.add_argument("--out-dir", default="docs/bugs")
    ap.add_argument("--env", default=os.getenv("APP_ENV", "dev"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ai-enrich", action="store_true", help="Enable OpenAI enrichment if OPENAI_API_KEY is set")
    ap.add_argument("--model", default=None, help="OpenAI model for enrichment")
    args = ap.parse_args()

    log_path = Path(args.log_file)
    out_dir = Path(args.out_dir)
    text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    if not text:
        print(f"No log text found at {log_path}")
        return 1

    fails = extract_failures(text)
    if not fails:
        print("No failures detected in log.")
        return 0

    # Group by signature
    groups: Dict[str, Dict] = {}
    for scope, scope_name, msg in fails:
        sig = signature(scope_name, msg)
        groups.setdefault(sig, {"scope": scope_name, "message": msg, "lines": []})
        groups[sig]["lines"].append(f"[{scope}] {scope_name}: {msg}")

    if args.dry_run:
        print(f"Detected {len(groups)} unique failure(s):")
        for sig, data in groups.items():
            print(f"- {data['scope']}: {data['message']}  (sig={sig})")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    # Build a quick map of existing file contents to avoid dupes by signature
    existing_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in out_dir.glob("BUG-*.md"))

    bug_id = next_bug_id(out_dir)
    for sig, data in groups.items():
        if sig in existing_text:
            # Already tracked
            continue
        md = render_bug_md(bug_id, args.env, log_path, data["scope"], data["message"], data["lines"])
        # Optional AI enrichment
        # Gate by CLI flag and environment variable (both must allow)
        if args.ai_enrich:
            # Temporarily set toggle so maybe_enrich can read it
            os.environ.setdefault("BUG_AI_ENRICH", "true")
            extra = maybe_enrich_with_openai(md, args.env, data["scope"], data["message"], log_path, data["lines"], model=args.model)
            if extra:
                md = md + "\n" + extra
        bug_path = out_dir / f"BUG-{bug_id:03d}.md"
        bug_path.write_text(md, encoding="utf-8")
        print(f"Created {bug_path}")
        created += 1
        bug_id += 1

    if created == 0:
        print("No new BUG docs created (all signatures already tracked)")
    else:
        print(f"Created {created} BUG doc(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
