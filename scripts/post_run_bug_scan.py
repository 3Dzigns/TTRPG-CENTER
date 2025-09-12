#!/usr/bin/env python3
"""
Generate BUG-xxx markdown reports by scanning a nightly log.

Usage:
  python scripts/post_run_bug_scan.py --log-file env/dev/logs/nightly_YYYYMMDD_HHMMSS.log \
      [--out-dir docs/bugs] [--env dev] [--dry-run]

Per-run consolidation (single report):
  Add --single-report to generate ONE consolidated report per run instead of
  individual BUG-### files. Optionally set --single-out to control the output path,
  otherwise a default like docs/bugs/RUN-YYYYMMDD_HHMMSS.md is used. Combine with
  --ai-enrich to ask OpenAI to draft a single consolidated bug report.

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
    re.compile(r"path not found", re.IGNORECASE),
    re.compile(r"not configured.*None", re.IGNORECASE),
    re.compile(r"not available.*functionality limited", re.IGNORECASE),
    re.compile(r"ERROR.*poppler.*PATH", re.IGNORECASE),
    re.compile(r"WARNING.*tessdata.*not found", re.IGNORECASE),
    # TLS/SSL related environment issues
    re.compile(r"SSL:\s*CERTIFICATE_VERIFY_FAILED", re.IGNORECASE),
    re.compile(r"certificate verify failed", re.IGNORECASE),
    re.compile(r"SSLError", re.IGNORECASE),
]

# Ignore successful configuration messages that contain keywords but are actually good
SUCCESSFUL_CONFIG_PATTERNS = [
    re.compile(r"INFO.*Configuring.*with absolute path", re.IGNORECASE),
    re.compile(r"INFO.*OCR Configuration.*✓", re.IGNORECASE),
    re.compile(r"INFO.*Setting TESSDATA_PREFIX", re.IGNORECASE),
]


def line_has_ignored_reason(msg: str) -> bool:
    return any(p.search(msg) for p in IGNORED_PATTERNS)


def normalize_message(msg: str) -> str:
    # Strip volatile tokens like job ids and elapsed times
    m = re.sub(r"adapter_job_\d+", "adapter_job", msg)
    m = re.sub(r"\b\d+\.\d+s\b", "{secs}", m)
    m = re.sub(r"C:.*?TTRPG_Center\\", "<REPO>/", m)
    return m.strip()


def extract_failures(text: str) -> List[Tuple[str, str, str, str]]:
    """Return list of (source, pass_or_scope, message, timestamp) failure tuples."""
    failures: List[Tuple[str, str, str, str]] = []

    for line in text.splitlines():
        # Extract timestamp from line (format: YYYY-MM-DD HH:MM:SS)
        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        timestamp = timestamp_match.group(1) if timestamp_match else ""
        m = PASS_FAIL_RE.search(line)
        if m:
            p, msg = m.group(1), m.group(2)
            if not line_has_ignored_reason(msg):
                failures.append(("pass", p, msg.strip(), timestamp))
            continue

        m = PIPELINE_FAIL_RE.search(line)
        if m:
            msg = m.group(1)
            if not line_has_ignored_reason(msg):
                failures.append(("pipeline", "pipeline", msg.strip(), timestamp))
            continue

        m = JOB_FAIL_RE.search(line)
        if m:
            msg = m.group(1)
            if not line_has_ignored_reason(msg):
                failures.append(("runner", "job", msg.strip(), timestamp))

        # Dependency/path issues (collect even if not marked ERROR)
        else:
            # Skip successful configuration messages
            if any(p.search(line) for p in SUCCESSFUL_CONFIG_PATTERNS):
                continue
                
            for pat in PATH_ISSUE_PATTERNS:
                if pat.search(line):
                    if not line_has_ignored_reason(line):
                        failures.append(("env", "path_dependency", line.strip(), timestamp))
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
    if "certificate" in msg and "verify" in msg:
        return ("tls", "P1")
    if "no module named" in msg or "importerror" in msg or "unstructured" in msg:
        return ("dependency", "P1")
    if "credentials" in msg or "astra" in msg or "token" in msg:
        return ("configuration", "P1")
    if "takes" in msg and "positional arguments" in msg:
        return ("code", "P0")
    if "logical split" in msg:
        return ("algorithm", "P2")
    return ("runtime", "P2")


def render_bug_md(bug_id: int, env: str, log_path: Path, scope: str, message: str, excerpts: List[str], count: int = 1, timestamps: List[str] = None) -> str:
    cat, sev = classify(message)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sig = signature(scope, message)
    if count > 1:
        title = f"BUG-{bug_id:03d}: {scope.upper()} failure - {message[:72]} (CONSOLIDATED)".rstrip()
    else:
        title = f"BUG-{bug_id:03d}: {scope.upper()} failure - {message[:72]}".rstrip()
    
    lines = [
        f"# {title}",
        "",
        "## Summary",
        f"- **Instance Count:** {count} occurrence{'s' if count != 1 else ''}",
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
    
    # Add temporal distribution section for multiple instances
    if count > 1 and timestamps:
        lines.extend([
            "",
            "## Temporal Distribution",
            f"- **Total Occurrences:** {count}",
        ])
        if len(timestamps) > 1:
            first_time = min(timestamps)
            last_time = max(timestamps)
            lines.append(f"- **Time Range:** {first_time} to {last_time}")
        if len(timestamps) <= 10:
            lines.append("- **All Timestamps:**")
            for ts in sorted(set(timestamps)):
                lines.append(f"  - {ts}")
        else:
            lines.append(f"- **Sample Timestamps:** (showing first 5 of {len(timestamps)})")
            for ts in sorted(set(timestamps))[:5]:
                lines.append(f"  - {ts}")
    
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


def render_run_report_md(env: str, log_path: Path, groups: Dict[str, Dict], max_excerpts_per_group: int = 8) -> str:
    ts_match = re.search(r"nightly[_ps]*_(\d{8}_\d{6})", log_path.name)
    run_id = ts_match.group(1) if ts_match else datetime.now().strftime("%Y%m%d_%H%M%S")
    total_instances = sum(d["count"] for d in groups.values())
    unique_groups = len(groups)

    # Aggregate simple stats
    by_scope: Dict[str, int] = {}
    for d in groups.values():
        by_scope[d["scope"]] = by_scope.get(d["scope"], 0) + d["count"]

    lines: List[str] = []
    lines.append(f"# Nightly Run Failure Report — {run_id}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- **Env:** {env}")
    lines.append(f"- **Log:** `{log_path.as_posix()}`")
    lines.append(f"- **Unique Failure Groups:** {unique_groups}")
    lines.append(f"- **Total Failure Instances:** {total_instances}")
    if by_scope:
        scope_bits = ", ".join(f"{k}: {v}" for k, v in sorted(by_scope.items()))
        lines.append(f"- **Instances by Scope:** {scope_bits}")

    # Group list
    lines.append("")
    lines.append("## Failure Groups")
    for sig, d in groups.items():
        cat, sev = classify(d["message"])
        lines.append(f"- `{sig}` — {d['scope'].upper()} — {cat}/{sev} — {d['count']} instance(s) — {d['message'][:140]}")

    # Details per group
    for sig, d in groups.items():
        cat, sev = classify(d["message"])
        lines.append("")
        lines.append(f"### [{sig}] {d['scope'].upper()} — {cat}/{sev}")
        lines.append(f"- **Message:** {d['message']}")
        lines.append(f"- **Instances:** {d['count']}")
        if d.get("timestamps"):
            first_time = min(d["timestamps"]) if d["timestamps"] else ""
            last_time = max(d["timestamps"]) if d["timestamps"] else ""
            lines.append(f"- **Time Range:** {first_time} — {last_time}")
        # Sample excerpts
        lines.append("- **Excerpts:**")
        for ex in d["lines"][:max_excerpts_per_group]:
            lines.append("  - " + ex.strip())

    # Pointers
    lines.append("")
    lines.append("## References")
    lines.append("- Consider `docs/bugs/BUG-020_Poppler_Tesseract_Preflight_Failfast.md` for dependency preflight.")
    lines.append("- Consider `docs/bugs/BUG-021_Zero_Output_Hard_Stop.md` for guardrail policies.")
    return "\n".join(lines) + "\n"


def maybe_enrich_run_with_openai(env: str, log_path: Path, groups: Dict[str, Dict], model: str | None = None, max_groups: int = 12, max_excerpts_per_group: int = 5) -> str | None:
    enabled = os.getenv("BUG_AI_ENRICH", "false").strip().lower() in ("1", "true", "yes") or False
    if not enabled:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    # Build a compact aggregated prompt
    ts_match = re.search(r"nightly[_ps]*_(\d{8}_\d{6})", log_path.name)
    run_id = ts_match.group(1) if ts_match else datetime.now().strftime("%Y%m%d_%H%M%S")
    header = [
        f"Compose a single consolidated bug report for nightly run {run_id}.",
        "Synthesize the failures into one report with:",
        "- Executive Summary",
        "- Root Cause Hypotheses (grouped if related)",
        "- Impact", 
        "- Acceptance Criteria",
        "- Proposed Fixes (prioritized)",
        "- Risks & Rollback",
        "- Observability improvements",
        "Be concise but specific. Use structured bullets.",
        f"Environment: {env}",
        f"Log: {log_path.as_posix()}",
        "",
        "Failure groups:",
    ]
    # Include top N groups by count
    sorted_groups = sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)[:max_groups]
    for sig, d in sorted_groups:
        cat, sev = classify(d["message"]) 
        header.append(f"- [{sig}] {d['scope']} — {cat}/{sev} — {d['count']} instance(s) — {d['message']}")
        for ex in d["lines"][:max_excerpts_per_group]:
            header.append(f"  • {ex.strip()}")

    def _call(client_factory):
        client = client_factory()
        use_model = model or os.getenv("BUG_AI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": "You write precise, structured engineering reports."},
                {"role": "user", "content": "\n".join(header)},
            ],
            temperature=0.2,
            max_tokens=int(os.getenv("BUG_AI_MAX_TOKENS", "1200")),
        )
        enriched = resp.choices[0].message.content or ""
        return enriched.strip() or None

    try:
        # Try default TLS first
        enriched = _call(lambda: OpenAI())
        if enriched:
            return "\n".join(["", "## AI Consolidated Report", enriched, ""])    
    except Exception as e:
        if any(t in str(e) for t in ("CERTIFICATE_VERIFY_FAILED", "certificate verify failed", "SSLError")):
            # Retry with verify=False
            try:
                import httpx  # type: ignore
                enriched2 = _call(lambda: OpenAI(http_client=httpx.Client(verify=False)))
                if enriched2:
                    return "\n".join(["", "## AI Consolidated Report", enriched2, ""]) 
            except Exception:
                return None
        # Other errors: do not escalate
        return None
    return None

def maybe_enrich_run_with_openai(env: str, log_path: Path, groups: Dict[str, Dict], model: str | None = None, max_groups: int = 12, max_excerpts_per_group: int = 5) -> str | None:
    """Fallback-aware OpenAI enrichment for consolidated run reports."""
    enabled = os.getenv("BUG_AI_ENRICH", "false").strip().lower() in ("1", "true", "yes") or False
    if not enabled:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    # Build concise header first
    header = [
        f"Env: {env}",
        f"Log: {log_path.as_posix()}",
        f"Unique failures: {len(groups)}",
        "",
    ]
    # Keep group list compact
    sorted_groups = sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)[:max_groups]
    for sig, d in sorted_groups:
        header.append(f"- [{sig}] {d['scope']} — {d['count']} instance(s) — {d['message']}")
        for ex in d["lines"][:max_excerpts_per_group]:
            header.append(f"  * {ex.strip()}")

    def _call(client_factory):
        client = client_factory()
        use_model = model or os.getenv("BUG_AI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": "You write precise, structured engineering reports."},
                {"role": "user", "content": "\n".join(header)},
            ],
            temperature=0.2,
            max_tokens=int(os.getenv("BUG_AI_MAX_TOKENS", "1200")),
        )
        body = resp.choices[0].message.content or ""
        return body.strip() or None

    # Try default TLS first, then fallback to verify=False
    try:
        enriched = _call(lambda: OpenAI())
        if enriched:
            return "\n".join(["", "## AI Consolidated Report", enriched, ""]) 
    except Exception as e:
        if any(t in str(e) for t in ("CERTIFICATE_VERIFY_FAILED", "certificate verify failed", "SSLError")):
            try:
                import httpx  # type: ignore
                enriched2 = _call(lambda: OpenAI(http_client=httpx.Client(verify=False)))
                if enriched2:
                    return "\n".join(["", "## AI Consolidated Report", enriched2, ""]) 
            except Exception:
                return None
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-file", required=True)
    ap.add_argument("--out-dir", default="docs/bugs")
    ap.add_argument("--env", default=os.getenv("APP_ENV", "dev"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ai-enrich", action="store_true", help="Enable OpenAI enrichment if OPENAI_API_KEY is set")
    ap.add_argument("--model", default=None, help="OpenAI model for enrichment")
    ap.add_argument("--single-report", action="store_true", help="Generate one consolidated report per run")
    ap.add_argument("--single-out", default=None, help="Output path for consolidated report (default: docs/bugs/RUN-YYYYMMDD_HHMMSS.md)")
    ap.add_argument("--max-excerpts-per-group", type=int, default=8)
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

    # Group by signature with instance counting
    groups: Dict[str, Dict] = {}
    for scope, scope_name, msg, timestamp in fails:
        sig = signature(scope_name, msg)
        if sig not in groups:
            groups[sig] = {
                "scope": scope_name, 
                "message": msg, 
                "lines": [], 
                "count": 0,
                "timestamps": []
            }
        groups[sig]["count"] += 1
        groups[sig]["lines"].append(f"[{scope}] {scope_name}: {msg}")
        if timestamp:
            groups[sig]["timestamps"].append(timestamp)

    if args.dry_run:
        print(f"Detected {len(groups)} unique failure signature(s):")
        total_instances = sum(data['count'] for data in groups.values())
        print(f"Total failure instances: {total_instances}")
        for sig, data in groups.items():
            count_info = f" ({data['count']} instance{'s' if data['count'] != 1 else ''})" if data['count'] > 1 else ""
            print(f"- {data['scope']}: {data['message'][:80]}...{count_info}  (sig={sig})")
        return 0

    # Single consolidated report mode
    if args.single_report:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Derive default output filename if not specified
        ts_match = re.search(r"nightly[_ps]*_(\d{8}_\d{6})", log_path.name)
        run_id = ts_match.group(1) if ts_match else datetime.now().strftime("%Y%m%d_%H%M%S")
        single_out = Path(args.single_out) if args.single_out else (out_dir / f"RUN-{run_id}.md")
        md = render_run_report_md(args.env, log_path, groups, max_excerpts_per_group=args.max_excerpts_per_group)
        if args.ai_enrich:
            os.environ.setdefault("BUG_AI_ENRICH", "true")
            extra = maybe_enrich_run_with_openai(args.env, log_path, groups, model=args.model, max_excerpts_per_group=min(5, args.max_excerpts_per_group))
            if extra:
                md = md + "\n" + extra
        single_out.write_text(md, encoding="utf-8")
        print(f"Created consolidated run report: {single_out}")
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
        md = render_bug_md(bug_id, args.env, log_path, data["scope"], data["message"], data["lines"], data["count"], data["timestamps"])
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
