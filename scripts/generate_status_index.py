#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BUGS_DIR = DOCS / "bugs"
REQS_DIR = DOCS / "requirements"


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return path.read_text(errors="replace")


def parse_title(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def parse_status(md: str) -> str:
    # Look for lines like "Status: ...", "**Status:** ...", or "- **Status**: ..."
    status_re = re.compile(r"status(?:\*\*)?\s*[:：]\s*(.+)$", re.IGNORECASE)
    for line in md.splitlines()[:80]:
        m = status_re.search(line)
        if m:
            val = m.group(1).strip()
            val = re.sub(r"^[*\s]+", "", val)
            return val
    return "Unknown"


def file_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def bug_id_from_filename(name: str) -> str:
    # Accept patterns: BUG-123-..., BUG-123-REPORT-..., etc.
    m = re.match(r"^(BUG-\d{3})\b", name)
    return m.group(1) if m else ""


def fr_id_from_filename(name: str) -> str:
    # Accept patterns: FR-AREA-123-...
    m = re.match(r"^(FR-[A-Z]+-\d{3})\b", name)
    return m.group(1) if m else ""


def relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def build_bugs_index():
    rows = []
    for path in sorted(BUGS_DIR.glob("BUG-*.md")):
        md = read_text_safe(path)
        title = parse_title(md)
        status = parse_status(md)
        bid = bug_id_from_filename(path.name)
        rows.append((bid, title, status, file_mtime(path), relpath(path)))

    lines = []
    lines.append("# Bugs Index")
    lines.append("")
    lines.append("| ID | Title | Status | Updated | File |")
    lines.append("|----|-------|--------|---------|------|")
    for bid, title, status, updated, rp in rows:
        lines.append(f"| {bid} | {title} | {status} | {updated} | [{Path(rp).name}]({rp}) |")
    (BUGS_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_reqs_index():
    rows = []
    for path in sorted(REQS_DIR.glob("FR-*.md")):
        md = read_text_safe(path)
        title = parse_title(md)
        status = parse_status(md)
        fid = fr_id_from_filename(path.name)
        rows.append((fid, title, status, file_mtime(path), relpath(path)))

    lines = []
    lines.append("# Feature Requests Index")
    lines.append("")
    lines.append("| ID | Title | Status | Updated | File |")
    lines.append("|----|-------|--------|---------|------|")
    for fid, title, status, updated, rp in rows:
        lines.append(f"| {fid} | {title} | {status} | {updated} | [{Path(rp).name}]({rp}) |")
    (REQS_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_master_index():
    bugs = read_text_safe(BUGS_DIR / "INDEX.md")
    reqs = read_text_safe(REQS_DIR / "INDEX.md")
    lines = []
    lines.append("# Status Index")
    lines.append("")
    lines.append("Quick links to bugs and feature requests with their statuses.")
    lines.append("")
    lines.append("## Bugs")
    lines.append("")
    lines.append("See: [docs/bugs/INDEX.md](bugs/INDEX.md)")
    lines.append("")
    lines.append("## Features")
    lines.append("")
    lines.append("See: [docs/requirements/INDEX.md](requirements/INDEX.md)")
    (DOCS / "STATUS_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    build_bugs_index()
    build_reqs_index()
    build_master_index()
    print("Generated docs/bugs/INDEX.md, docs/requirements/INDEX.md, docs/STATUS_INDEX.md")


if __name__ == "__main__":
    sys.exit(main())
