import argparse, json, os, pathlib, requests

PROMPT = """You are a senior code reviewer for the TTRPG Center project.
Use the JSON schema below for your output. Be strict and concise.

Rubric:
- Correctness & safety (errors, cleanup, race conditions)
- Security (secrets, injection, unsafe subprocess, path traversal)
- Performance (hot paths, N+1)
- Readability & style
- Tests: unit + integration for new logic?
- Requirements trace: cite IDs like ARCH-001, RAG-001, ADM-002, TEST-003
- Enforce ingestion phases + status schema + env isolation + Admin UI progress + RAG QA expectations

Output JSON ONLY:
{
  "ok": true|false,
  "issues": [
    {
      "id": "CR-001",
      "severity": "high|medium|low",
      "title": "short title",
      "details": "why; file:line if possible; suggested fix",
      "files": ["path:line-range?"],
      "requirements": ["RAG-001","ADM-002"]
    }
  ],
  "summary": "short paragraph",
  "go_no_go": "GO|NO-GO"
}
"""

def read(path):
    p = pathlib.Path(path)
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def load_context(path, max_chars=12000):
    p = pathlib.Path(path)
    if not p.exists(): return []
    out, total = [], 0
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if total + len(line) > max_chars: break
        out.append(line); total += len(line)
    return out

def openai_review(diff_text, context_lines):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ctx = "\n".join(context_lines[:12])
    body = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "messages": [
            {"role":"user","content":PROMPT},
            {"role":"user","content":"Context Pack (JSONL snippets):\n" + ctx},
            {"role":"user","content":"Unified Diff or Repo Snapshot:\n" + diff_text}
        ]
    }
    r = requests.post(url, headers=headers, json=body, timeout=180)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"].strip()
    return json.loads(text)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", required=False, default="pr.diff")
    ap.add_argument("--context", required=False, default="artifacts/ci/context.jsonl")
    ap.add_argument("--mode", choices=["diff","full"], default="diff")
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--out_md", required=True)
    args = ap.parse_args()

    if args.mode == "diff":
        diff_text = read(args.diff) or "NO CHANGES"
    else:
        diff_text = "Full repository context supplied. Review overall code quality and policy alignment."

    ctx_lines = load_context(args.context)
    result = openai_review(diff_text, ctx_lines)

    sha = os.environ.get("GIT_COMMIT_SHA","")
    result.setdefault("metadata", {})["sha"] = sha
    result.setdefault("metadata", {})["provider"] = "openai"
    result["ok"] = bool(result.get("ok", False))

    oj = pathlib.Path(args.out_json); oj.parent.mkdir(parents=True, exist_ok=True)
    om = pathlib.Path(args.out_md);   om.parent.mkdir(parents=True, exist_ok=True)
    oj.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Pretty MD
    lines = [f"# AI Review Results",
             f"", f"**GO/NO-GO:** {result.get('go_no_go','')}",
             f"**Summary:** {result.get('summary','')}",
             f"**Provider:** openai",
             f"**SHA:** {sha}", f"",
             f"## Issues ({len(result.get('issues',[]))})"]
    sev = {"high":0,"medium":1,"low":2}
    for it in sorted(result.get("issues",[]), key=lambda x: sev.get(x.get("severity","low"),9)):
        lines.append(f"- [{it.get('id','')}] **{it.get('severity','').upper()}** — {it.get('title','')}")
        if it.get("requirements"): lines.append(f"  - Req: {', '.join(it['requirements'])}")
        if it.get("files"):        lines.append(f"  - Files: {', '.join(it['files'])}")
        if it.get("details"):      lines.append(f"  - Details: {it['details']}")
    om.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main()
