import pathlib, json

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "ci" / "context.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

INCLUDE = [
  "CLAUDE.md",
  ".claude/memory",
  ".claude/commands",
  "README.md",
  "API_TESTING.md",
  "LAUNCH_GUIDE.md",
  "STATUS.md",
  "docs/requirements"
]
MAX_FILE_BYTES = 120_000

def summarize(txt, limit=4000):
    out, total = [], 0
    for ln in txt.splitlines():
        if total + len(ln) > limit: break
        out.append(ln); total += len(ln)
    return "\n".join(out)

def collect_files():
    for item in INCLUDE:
        p = ROOT / item
        if not p.exists(): continue
        if p.is_file(): yield p
        else:
            for f in p.rglob("*"):
                if f.is_file(): yield f

files = sorted(set(str(p.relative_to(ROOT)).replace("\\","/") for p in collect_files()))

with OUT.open("w", encoding="utf-8") as w:
    w.write(json.dumps({"kind":"repo_map","files":files}) + "\n")
    for rel in files:
        p = ROOT / rel
        try:
            data = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        kind = "context_file"
        if p.stat().st_size > MAX_FILE_BYTES:
            data = summarize(data); kind = "context_summary"
        w.write(json.dumps({"kind":kind, "path":rel, "text":data}) + "\n")

print(f"Wrote {OUT}")
