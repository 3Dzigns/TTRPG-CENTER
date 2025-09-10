# BUG-020 — Preflight dependency check for Poppler & Tesseract (fail-fast)

**Severity:** High  
**Component:** bulk_ingest runner (Pass bootstrap)  
**Status:** Open  
**Detected in run:** bulk_ingest_20250910_073323.log fileciteturn3file0

## Summary
Bulk ingestion proceeds to Pass C without verifying **Poppler** and **Tesseract** are on PATH and functional. When either is missing/misconfigured, extraction silently degrades to **0 chunks**, cascading to empty vectors/graphs later while the job superficially reports OK.

## Environment
- OS: Windows Server (build used for TTRPG Center dev)
- Python: 3.12.x
- Ingestion mode: 6-pass, threads: 4
- DB: AstraDB dev (SSL bypass enabled — acknowledged as acceptable for now)

## Evidence
- The run shows normal startup and heavy ToC dictionary updates, but later extractions yield no chunks. (See referenced log). fileciteturn3file0

## Impact
- All downstream work in Pass D/E is wasted; user perceives success but data is missing.
- Time and compute costs increase; regression risk for future runs.

## Steps to Reproduce
1. Remove Poppler from PATH or install location.
2. Run `bulk_ingest.py` on any image-heavy/scanned PDF.
3. Observe Pass C creates 0 chunks; pipeline keeps going.

## Expected
- At process start, runner **validates** `pdfinfo`, `pdftoppm` (Poppler) and `tesseract` presence **and** basic function.
- If any validation fails → **abort the source** before Pass A→F, returning **FAIL** with actionable error.

## Actual
- No preflight; failures manifest later as 0-chunk pipelines that appear “OK”.

## Proposed Fix
- Add a **preflight()** hook at the very start of `bulk_ingest`:
  - Locate executables with `shutil.which`.
  - Run health checks: `pdfinfo -v`/`-version`, `tesseract --list-langs`.
  - Validate expected outputs; log versions.
  - On failure → raise `SystemExit(2)` (or custom `PreflightError`) and mark **job FAILED**.
- Windows convenience:
  - If common install paths exist (e.g., `C:\Program Files\Tesseract-OCR`, `C:\Users\<user>\Documents\Poppler\...\bin`), temporarily extend `os.environ["PATH"]` for the current process and re-check.

### Example (Python preflight)
```python
import shutil, subprocess, sys

def _ok(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return out.stdout + out.stderr
    except Exception as e:
        return ""

def preflight_or_die():
    pdfinfo = shutil.which("pdfinfo")
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")

    missing = [name for name, path in [("pdfinfo", pdfinfo), ("pdftoppm", pdftoppm), ("tesseract", tesseract)] if not path]
    if missing:
        print(f"[FATAL] Missing dependencies: {', '.join(missing)}")
        sys.exit(2)

    if "PDF" not in _ok([pdfinfo, "-v"]):
        print("[FATAL] Poppler pdfinfo failed sanity check")
        sys.exit(2)
    if "--list-langs" not in _ok([tesseract, "-h"]) and not _ok([tesseract, "--list-langs"]).strip():
        print("[FATAL] Tesseract failed language listing")
        sys.exit(2)
```

### Example (PowerShell PATH helper for Windows runners)
```powershell
# Add common install locations to PATH for current session
$poppler = 'C:\Users\Public\Poppler\poppler-25.07.0\Library\bin','C:\Program Files\poppler\bin' | Where-Object { Test-Path $_ } | Select-Object -First 1
$tess    = 'C:\Program Files\Tesseract-OCR' | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($poppler) { $env:PATH = "$poppler;$env:PATH" }
if ($tess)    { $env:PATH = "$tess;$env:PATH" }
# Sanity checks
& pdfinfo -v | Out-Null
& tesseract --list-langs | Out-Null
```

## Acceptance Criteria
- Runner logs Poppler & Tesseract versions at start.
- Missing/invalid tools cause **immediate job failure** before any pass.
- Pipeline summary shows **FAILED**, not OK, with a clear preflight error.

## Testing
### Unit
- Mock `shutil.which` to simulate missing tools → expect `SystemExit(2)`.
- Mock subprocess returns to simulate corrupted binaries → expect failure.

### Functional
- On a clean machine without Poppler: runner exits with FATAL and no passes run.
- With valid installs: runner proceeds; versions appear in the first 20 log lines.

### Regression
- Existing runs with correctly installed tools remain unaffected; timings ±2%.
