# Claude Prompt — **Comprehensive Codebase Cleanup & Reachability Map** (TTRPG Center)

> **Role**: Act as a senior **Automated Repo Custodian** for the TTRPG Center project.  
> **Objective**: Perform a **safe, scripted cleanup** of the repository, archive completed items, produce a **Markdown reachability map** of all executable code paths, relocate stray files to standard locations, and **update `claude.md`** with enforced code standards derived from `MVP-Version-2`, including **strict path conventions**.

---

## Operating Constraints

1. **Run inside the Docker *DEV* container** for this repo. Use only container paths and container tools.  
2. All actions must be **idempotent** and **scripted** (no manual editor steps). Commit scripts into `scripts/maintenance/` as part of the PR.  
3. **Never delete** anything on first pass. Instead, move or archive with clear provenance and a reversible plan.
4. Respect the project’s phase requirements and environment isolation rules (DEV/TEST/PROD) when touching paths and configs.
5. Produce **one PR** with atomic commits grouped by task (inventory → reachability → archiving → moves → standards update).

---

## Deliverables (must be present in the PR)

1. **`docs/reachability/Reachable-Code-Paths.md`** — a complete list of *reachable* entry points and call paths, grouped by service/module, with the file(s) that implement each path. Include how reachability was determined (static + runtime coverage) and the exact command lines used.
2. **`archives/bugs/YYYYMMDD/`** & **`archives/features/YYYYMMDD/`** — archived JSON/MD bundles for completed BUG and FR items, preserving IDs, status, and audit metadata.
3. **`docs/cleanup/Cleanup-Report.md`** — rationale for each removal/move/archive, including grep evidence, dependency graph snippets, and test coverage signals.
4. **Updated `claude.md`** — standards codified from `MVP-Version-2` folder and enforced path policy. Add a short “Style Guide → Enforced by CI” section and a “Repo Paths Policy” section.
5. **Automation scripts** under `scripts/maintenance/`:  
   - `inventory.sh` / `.ps1`  
   - `reachability.sh` / `.ps1`  
   - `archive_done_items.sh` / `.ps1`  
   - `relocate_strays.sh` / `.ps1`  
   - `standards_lint.sh` / `.ps1`  
   Each script logs to `env/dev/logs/maintenance/*.ndjson` and **never** writes outside `env/<env>` sandboxes.

---

## High-Level Plan

### A) Preflight & Environment Guardrails
1. Verify container context: print `uname -a`, `python --version`, `node --version`, working dir.  
2. Load **DEV** ports and environment from `env/dev/config/ports.json` and `.env` and assert isolation (no references to `env/test` or `env/prod`).  
3. Create `env/dev/logs/maintenance/` if missing; start a run log with a timestamp.

### B) Repo Inventory (Source of Truth)
Generate a full manifest `docs/cleanup/repo-inventory.json` capturing:
- All files with size, path, modified time, git status (tracked/untracked/ignored).
- Language buckets (py, ts/tsx/js, sh/ps1, yml, json, md, others).
- Known roots and **allowed** top-level items (README, LICENSE, `/env`, `/src_common`, `/services`, `/tests`, `/docs`, `/scripts`, `/.github`, `/config`, `/requirements`, `/features`, `/bugs`, `/artifacts`, `/archives`).

### C) Reachability Analysis (Static + Dynamic)
1. **Static graphing**
   - Python: `pyan` or `pycg` for call graphs; `pyflakes`/`vulture` for unused code.
   - JS/TS: `tsc --noEmit`, `eslint --ext .ts,.tsx,.js`, optionally `madge` for dependency graphs.
   - Grep for canonical **entry points**: FastAPI apps (`app = FastAPI()`), CLI `if __name__ == "__main__":`, Docker CMD targets, GitHub Actions entry scripts, test runners, and any `uvicorn`/`gunicorn`/`python -m` references.
2. **Runtime coverage (DEV)**
   - Run unit + functional tests with coverage: `pytest -q --cov --cov-report=xml` and `coverage json`.
   - For Node services (if present), run test scripts and produce `coverage-final.json`.
3. **Synthesize paths**
   - Merge static entry points + dynamic covered call trees → enumerate “**Reachable Paths**” with: *entry → module → functions/classes*.
   - Mark each path with **evidence**: (Static|Runtime|Both) and coverage % if available.
4. Emit to **`docs/reachability/Reachable-Code-Paths.md`** with a TOC per service/module. Include an **“Unreferenced/Dead Candidates”** appendix.

### D) Completed Bugs & Features → Archive
1. Detect **BUG-*** and **FR-*** items in `/bugs` and `/features` (or repo paths historically used).  
2. Parse their status (from JSON/MD frontmatter or standardized fields).  
3. For **completed** or **rejected** items, move to:
   - `archives/bugs/YYYYMMDD/BUG-xxx/` or `archives/features/YYYYMMDD/FR-xxx/`
   - Preserve original files + append a generated `archive.json` snapshot (timestamp, commit, reason, links).  
4. Leave a **stub pointer file** in the old location with `moved_to: <new_path>`.

### E) Stray Root Files → Relocation
1. Using the inventory and the project’s **Phase 0 isolation & directory contract**, build a ruleset to classify **misplaced** root files (logs, artifacts, orphan scripts).  
2. Move each item to its canonical location (e.g., `/env/<env>/logs`, `/scripts`, `/docs`, `/artifacts/<env>/<job_id>`, etc.).  
3. Record every move in `docs/cleanup/Cleanup-Report.md` with before/after tables and justification.  
4. Add `.gitignore` entries as needed to prevent future drift.

### F) Standards & Path Policy — Update `claude.md`
1. Extract coding standards from `MVP-Version-2` folder requirements and create a concise **“Code Standards”** section (naming, function length, tests required, docstrings, linting).  
2. Add **Repo Paths Policy** summarizing: allowed top-level folders, env isolation rules, artifact placement, and test locations.  
3. Add **“Enforcement”** subsection: describe CI lint/test jobs and a **path linter** that fails on unknown roots or env-crossing writes.  
4. Commit a small `tools/path_lint.py` with rules and tests in `tests/unit/test_path_lint.py`.

### G) Safe-Removal Proposal (No hard deletes on first pass)
1. Build `docs/cleanup/Removal-Candidates.md` listing files that appear **unused** by both static and dynamic analysis.  
2. For each candidate, include: size, last-modified, import refs, grep hits, and coverage presence.  
3. Tag each as **`quarantine`** or **`keep`** with rationale.  
4. **Do not delete**; instead, move to `quarantine/YYYYMMDD/` with a restore script.

---

## Concrete Commands (put into scripts/maintenance/*.sh)

> Assume **Linux** container with bash; provide `.ps1` siblings for Windows devs.

**inventory.sh**
```bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
out="$root/docs/cleanup"
mkdir -p "$out"
git ls-files --stage > "$out/git-index.txt"
git ls-files --others --exclude-standard > "$out/git-untracked.txt"
python - <<'PY'
import os, json, time, pathlib
root = pathlib.Path(".").resolve()
inv = []
for p in root.rglob("*"):
    if p.is_file():
        try: inv.append({"path": str(p.relative_to(root)), "size": p.stat().st_size, "mtime": p.stat().st_mtime})
        except Exception: pass
pathlib.Path("docs/cleanup/repo-inventory.json").write_text(json.dumps(inv, indent=2))
print(f"Wrote inventory with {len(inv)} files at", time.ctime())
PY
```

**reachability.sh**
```bash
set -euo pipefail
mkdir -p docs/reachability
# Python static checks
python -m pip install --quiet vulture pyflakes
vulture . > docs/reachability/vulture.txt || true
pyflakes $(git ls-files '*.py') > docs/reachability/pyflakes.txt || true
# Graphs (optional)
python -m pip install --quiet pyan3
pyan $(git ls-files '*.py') --uses --no-defines --colored --grouped \
  --dot > docs/reachability/python-callgraph.dot || true
# Runtime coverage
pytest -q --cov --cov-report=xml || true
coverage json || true
python - <<'PY'
# Merge static+runtime signals into Reachable-Code-Paths.md (simple seed; extend as needed)
from pathlib import Path
out = Path("docs/reachability/Reachable-Code-Paths.md")
out.write_text("# Reachable Code Paths\n\n(Report generated; extend with call graphs and coverage summaries.)\n")
PY
```

**archive_done_items.sh**
```bash
set -euo pipefail
stamp="$(date +%Y%m%d)"
dest_b="archives/bugs/$stamp"; dest_f="archives/features/$stamp"
mkdir -p "$dest_b" "$dest_f"
# naive scan; replace with parser as needed
for f in $(git ls-files 'bugs/*'); do
  if grep -qi 'status: *\(done\|closed\|resolved\|rejected\)' "$f"; then
    d="$dest_b/$(basename "${f%.*}")"; mkdir -p "$d"; git mv "$f" "$d/"
    printf '{"archived_at":"%s","source":"%s"}\n' "$stamp" "$f" > "$d/archive.json"
  fi
done
for f in $(git ls-files 'features/*'); do
  if grep -qi 'status: *\(done\|closed\|resolved\|rejected\)' "$f"; then
    d="$dest_f/$(basename "${f%.*}")"; mkdir -p "$d"; git mv "$f" "$d/"
    printf '{"archived_at":"%s","source":"%s"}\n' "$stamp" "$f" > "$d/archive.json"
  fi
done
```

**relocate_strays.sh**
```bash
set -euo pipefail
# Example: move stray logs & artifacts from root to env/dev/*
mkdir -p env/dev/logs env/dev/data
shopt -s nullglob
for f in *.log; do git mv "$f" "env/dev/logs/"; done
for f in artifacts_*; do git mv "$f" "artifacts/dev/"; done || true
```

**standards_lint.sh**
```bash
set -euo pipefail
# linters + path policy
python - <<'PY'
import sys, pathlib, re
root = pathlib.Path(".").resolve()
allowed = {'env','scripts','src_common','services','tests','docs','config','requirements','features','bugs','.github','artifacts','archives'}
bad = [p.name for p in root.iterdir() if p.is_dir() and p.name not in allowed]
if bad:
    print("Disallowed top-level dirs:", bad); sys.exit(2)
print("Path policy OK")
PY
pytest -q tests/unit tests/functional || true
```

---

## Acceptance Criteria (Checklist)

- [ ] All scripts created, executable, and logged under `env/dev/logs/maintenance/`.
- [ ] `docs/reachability/Reachable-Code-Paths.md` lists every **reachable** entry path with evidence tags.
- [ ] Completed BUG/FR items archived under `archives/*/YYYYMMDD/*` with stubs left behind (or index updated).
- [ ] Stray files relocated to canonical paths; **no unknown root entries** remain.
- [ ] `claude.md` updated: standards from `MVP-Version-2`, path policy, enforcement (CI + `tools/path_lint.py`).
- [ ] `docs/cleanup/Cleanup-Report.md` explains every move/archive with evidence.
- [ ] Single PR with logically ordered commits; CI green.

---

## Notes & Guardrails

- Prefer **moves (git mv)** to preserve history.  
- Quarantine suspected dead code instead of deletion; include restore script.  
- Keep environment isolation sacred: **no DEV actions write to TEST/PROD trees**.  
- If a rule conflicts with active tests or Phase requirements, annotate in the report and skip the change pending owner review.
