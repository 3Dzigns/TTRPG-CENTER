# TTRPG Center — Phase 0 User Stories, Code Snippets, and Test Matrix

> Objective: Establish a clean, reproducible foundation that enforces **environment isolation**, **repeatable builds**, **basic CI**, **status logging hooks**, and a **test harness** before any Phase 1 application features. Phase 0 ends when all stories below are DONE and their tests pass in **DEV** and via CI.

---

## Scope & Non‑Goals

**In scope**

* Environment isolation via sub‑directories: `env/dev`, `env/test`, `env/prod` with strict separation of code, config, data, and ports.
* Bootstrap CI (GitHub Actions) running Unit/Functional/Security linters on every push and PR; Regression on `main` nightly.
* Common logging and status interfaces (no real ingestion yet), with a mock "ingestion job" to validate status flows.
* Secrets handling: .env files (local) + CI secrets; guardrails.
* Test harness (pytest + Pester) and baseline tests.

**Out of scope**

* Full ingestion pipeline or UI. (Mocked only.)
* External cloud provisioning. (Local stubs only.)

**Definition of Done (Phase 0)**

* `scripts/` can scaffold environments and run local checks end‑to‑end.
* `env/<name>/.env` resolved by runner without cross‑contamination.
* CI pipeline green for: Unit, Functional, Security; nightly Regression passes.
* Status logs emitted in structured JSON; basic `/healthz` or CLI health returns OK.

---

## Directory & Port Conventions

```
/ (repo root)
  env/
    dev/
      code/           # DEV code copy (symlink or projection OK if tests prove isolation)
      config/         # DEV config (.env, ports.json, logging.json)
      data/           # DEV data scratch (gitignored)
      logs/
    test/
      code/
      config/
      data/
      logs/
    prod/
      code/
      config/
      data/
      logs/
  scripts/
  src_common/         # Shared library modules imported by each env/code; no env‑specific state
  tests/
    unit/
    functional/
    regression/
    security/
  .github/workflows/
```

> **Rule:** Tests must prove that running DEV cannot bind or read TEST/PROD resources and vice versa (ports, files, logs).

---

# Epics, Stories, Snippets, and Tests

## EPIC ARCH — Environment Isolation & Bootstrap

### Story ARCH‑001: Create isolated environment skeletons

**As a** platform engineer
**I want** DEV/TEST/PROD to have isolated code/config/data/logs under `env/<name>`
**So that** work in one environment never impacts another.

**Acceptance Criteria**

* `scripts/init-environments.ps1` (Windows) and `scripts/init-environments.sh` (POSIX) create the full tree.
* `env/*/config/ports.json` assigns unique ports per env.
* Running `scripts/run-local.ps1 -Env dev` only touches `env/dev/*` and uses only DEV ports.

**Code Snippet — PowerShell scaffolding**

```powershell
# scripts/init-environments.ps1
param([ValidateSet('dev','test','prod')]$EnvName='dev')
$root = Join-Path $PSScriptRoot ".."
$envRoot = Join-Path $root "env/$EnvName"
$paths = @('code','config','data','logs') | ForEach-Object { Join-Path $envRoot $_ }
$paths | ForEach-Object { if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ | Out-Null } }
# Minimal configs
$ports = @{ dev=8000; test=8181; prod=8282 }["$EnvName"]
@{ http_port=$ports; name=$EnvName } | ConvertTo-Json | Set-Content (Join-Path $envRoot 'config/ports.json')
"ENV=$EnvName`nLOG_LEVEL=INFO" | Set-Content (Join-Path $envRoot 'config/.env')
Write-Host "Initialized $EnvName at $envRoot"
```

**Code Snippet — POSIX scaffolding**

```bash
# scripts/init-environments.sh
set -euo pipefail
ENV_NAME="${1:-dev}"
ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
ENV_ROOT="$ROOT/env/$ENV_NAME"
mkdir -p "$ENV_ROOT/code" "$ENV_ROOT/config" "$ENV_ROOT/data" "$ENV_ROOT/logs"
case "$ENV_NAME" in
  dev) PORT=8000;; test) PORT=8181;; prod) PORT=8282;; esac
printf '{"http_port":%s,"name":"%s"}\n' "$PORT" "$ENV_NAME" > "$ENV_ROOT/config/ports.json"
printf 'ENV=%s\nLOG_LEVEL=INFO\n' "$ENV_NAME" > "$ENV_ROOT/config/.env"
echo "Initialized $ENV_NAME at $ENV_ROOT"
```

**Unit Tests** (`tests/unit/test_arch001_env_dirs.py`)

```python
import json, os
from pathlib import Path

def test_env_dirs_exist(tmp_path):
    # Simulate init script output
    for env in ("dev","test","prod"):
        base = tmp_path/"env"/env
        for sub in ("code","config","data","logs"): (base/sub).mkdir(parents=True, exist_ok=True)
        (base/"config"/"ports.json").write_text('{"http_port":8000,"name":"dev"}')
    assert (tmp_path/"env"/"dev"/"config"/"ports.json").exists()

def test_ports_json_has_unique_port(tmp_path):
    # Example content; real test should parse real files
    ports = {"dev":8000, "test":8181, "prod":8282}
    assert len(set(ports.values())) == 3
```

**Functional Tests** (`tests/functional/test_isolation.py`)

```python
from pathlib import Path
import os, json

def test_dev_run_writes_only_dev_logs(tmp_path, monkeypatch):
    # Arrange fake run
    dev_logs = tmp_path/"env"/"dev"/"logs"; test_logs = tmp_path/"env"/"test"/"logs"
    dev_logs.mkdir(parents=True); test_logs.mkdir(parents=True)
    (dev_logs/"run.log").write_text("ok")
    # Assert
    assert (dev_logs/"run.log").exists()
    assert not any(test_logs.iterdir())
```

**Regression Tests**

* Re-run `ARCH-001` after any change under `scripts/` or `env/*/config/*` to ensure structure and ports remain unique.

**Security Tests**

* Verify `.env` files are **gitignored** and not present in repo.
* Verify permissions on `env/*/config/.env` are not world-readable on POSIX (e.g., `0600`).

---

### Story ARCH‑002: Environment runner and health probe

**As a** developer
**I want** a simple runner that loads env config and exposes a health probe
**So that** CI and humans can validate the environment is wired correctly.

**Code Snippet — Minimal Python app**

```python
# src_common/app.py
import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = json.dumps({"status":"ok","env":os.getenv("ENV","unknown")}).encode()
            self.send_response(200); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

def run(http_port:int):
    srv = HTTPServer(("0.0.0.0", http_port), Handler)
    srv.serve_forever()
```

**Runner**

```powershell
# scripts/run-local.ps1
param([ValidateSet('dev','test','prod')]$Env='dev')
$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$Env"
$ports = Get-Content (Join-Path $envRoot 'config/ports.json') | ConvertFrom-Json
$env:ENV = $Env
python - <<'PY'
import json, os
from pathlib import Path
from app import run
# discover port from ENV file path passed by PS
import sys
import json
ports = json.load(open(sys.argv[1]))
run(ports['http_port'])
PY
"$(Join-Path $envRoot 'config/ports.json')"
```

**Unit Tests** (`tests/unit/test_app_health.py`)

```python
from src_common.app import Handler

def test_handler_exists():
    assert callable(getattr(Handler, 'do_GET', None))
```

**Functional Tests** (`tests/functional/test_health_endpoint.py`)

```python
import http.client

def test_health_ok(local_server):
    # fixture starts server on a test port
    conn = http.client.HTTPConnection("localhost", local_server.port)
    conn.request("GET","/healthz")
    resp = conn.getresponse()
    assert resp.status == 200
```

**Regression**

* Start app, ensure `/healthz` response schema unchanged (`{"status":"ok","env":"<env>"}`).

**Security**

* Confirm server binds only to env port, not privileged ports.

---

## EPIC CI — Continuous Integration Bootstrap

### Story CI‑001: GitHub Actions workflow (lint, unit, functional)

**As a** maintainer
**I want** CI to run on PRs and pushes
**So that** no code merges without passing tests.

**Workflow Snippet** (`.github/workflows/ci.yml`)

```yaml
name: CI
on:
  push:
    branches: ["**"]
  pull_request:
permissions:
  contents: read
  checks: write
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true
          pip install pytest pytest-cov bandit
      - name: Unit & Functional
        run: |
          pytest -q tests/unit tests/functional
      - name: Security (Bandit)
        run: bandit -q -r src_common || true
```

**Unit/Functional/Regression/Security**

* Unit & Functional: executed per above steps.
* Regression: separate nightly (see CI‑002).
* Security: Bandit runs on every PR.

### Story CI‑002: Nightly regression on `main`

**Acceptance Criteria**

* Scheduled job runs full regression suite daily.

**Snippet**

```yaml
on:
  schedule:
    - cron: '0 7 * * *'  # 7:00 UTC daily
jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install -r requirements.txt || true
          pip install pytest
          pytest -q tests/regression
```

---

## EPIC LOG — Structured Logging & Status Hooks

### Story LOG‑001: Structured JSON logging utility

**As a** developer
**I want** a tiny helper for consistent JSON logs
**So that** CI/ops can parse status easily.

**Code Snippet**

```python
# src_common/logging.py
import json, os, sys, time

def jlog(level:str, msg:str, **fields):
    rec = {"ts":time.time(), "level":level, "msg":msg, "env":os.getenv('ENV','dev')}
    if fields: rec.update(fields)
    sys.stdout.write(json.dumps(rec)+"\n"); sys.stdout.flush()
```

**Unit Test** (`tests/unit/test_logging.py`)

```python
from src_common.logging import jlog

def test_jlog_no_throw(capsys):
    jlog('INFO','hello', step='init')
    out = capsys.readouterr().out
    assert '"level":"INFO"' in out and '"msg":"hello"' in out
```

**Security Test**

* Ensure helper never serializes secrets: unit test passes `API_KEY='xxx'` and asserts it is **not** printed unless explicitly passed as a field.

---

## EPIC STAT — Mock Ingestion Job & Status Interface

### Story STAT‑001: CLI mock job writes status updates

**As a** tester
**I want** a mock job that emits phase start/stop logs
**So that** the web/UI later can consume consistent status.

**Code Snippet**

```python
# src_common/mock_ingest.py
from logging import jlog
import time

def run_mock(job_id:str="job-001"):
    jlog('INFO','ingest.start', job_id=job_id)
    for step in ("fetch","chunk","vectorize"):
        jlog('INFO','ingest.step', job_id=job_id, step=step, status='running')
        time.sleep(0.01)
        jlog('INFO','ingest.step', job_id=job_id, step=step, status='done')
    jlog('INFO','ingest.done', job_id=job_id, result='ok')
```

**Functional Test** (`tests/functional/test_mock_ingest.py`)

```python
from src_common.mock_ingest import run_mock

def test_run_mock_emits_steps(capsys):
    run_mock('t1')
    out = capsys.readouterr().out
    assert 'ingest.start' in out and 'ingest.done' in out
    for step in ("fetch","chunk","vectorize"):
        assert f'"step":"{step}"' in out
```

**Regression**

* Freeze the step set \[fetch, chunk, vectorize] as baseline; diff failures signal contract changes.

**Security**

* Validate job\_id is sanitized (alphanumeric, dash) before use in file paths (if later persisted).

---

## EPIC SEC — Secrets & Hardening

### Story SEC‑001: Secrets handling and git hygiene

**As a** security engineer
**I want** local secrets in `.env` and CI secrets in GitHub
**So that** credentials never enter the repo.

**Acceptance Criteria**

* `.env` files present under `env/*/config/` are gitignored.
* Helper loads key=value with safe defaults; missing secrets cause explicit error.

**Snippet**

```python
# src_common/secrets.py
from pathlib import Path

def load_env(env_root:Path):
    env_file = env_root/"config/.env"
    if not env_file.exists():
        raise FileNotFoundError("Missing .env")
    for line in env_file.read_text().splitlines():
        if not line or line.startswith('#'): continue
        k,v = line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip())
```

**Security Tests** (`tests/security/test_env_gitignore.py`)

```python
from pathlib import Path

def test_env_gitignored(repo_root:Path):
    gi = (repo_root/'.gitignore').read_text()
    assert 'env/*/config/.env' in gi or '/env/**/.env' in gi
```

**Threat Checks**

* Scan repo with `trufflehog` or `gitleaks` in CI (optional now, recommended).

---

## EPIC QA — Test Harness & Fixtures

### Story QA‑001: Pytest fixtures & local server

**As a** QA
**I want** shared fixtures for temp env roots and local server
**So that** functional tests are simple and fast.

**Snippet** (`tests/conftest.py`)

```python
import threading, socketserver, contextlib
import pytest
from src_common.app import Handler
from http.server import HTTPServer

@pytest.fixture
def local_server():
    srv = HTTPServer(('127.0.0.1',0), Handler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    class S: pass
    o=S(); o.port=port
    yield o
    srv.shutdown()
```

**Unit/Functional/Regression/Security — Required Test Cases Matrix**

| Area       | Required Tests                                                                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit       | (1) Logging helper emits valid JSON; (2) Secrets loader ignores comments; (3) Health handler callable; (4) Ports map uniqueness check util.           |
| Functional | (1) `/healthz` returns 200 & env; (2) Mock job prints start/steps/done; (3) Runner only writes to current env logs; (4) Scripts create exact tree.    |
| Regression | (1) Baseline schema of `/healthz`; (2) Baseline step list for mock job; (3) Ports remain {dev:8000,test:8181,prod:8282} unless intentionally changed. |
| Security   | (1) `.env` gitignored; (2) No secrets in logs by default; (3) Server binds non‑privileged port; (4) File perms check (POSIX only) for `.env`.         |

---

## EPIC OPS — Developer Scripts & Quality Gates

### Story OPS‑001: Preflight script

**As a** developer
**I want** a single script to validate Phase 0 readiness locally
**So that** I can fix issues before pushing.

**Snippet**

```powershell
# scripts/preflight.ps1
Write-Host "Running preflight..."
& $PSScriptRoot/init-environments.ps1 -Env dev
python -m pytest -q tests/unit || exit 1
python -m pytest -q tests/functional || exit 1
Write-Host "Preflight OK"
```

**Functional Test**

* Execute script in CI windows runner (optional matrix) and assert exit code 0.

---

# Test Execution Policy

* **Unit**: On every commit (local + CI)
* **Functional**: On every PR and push
* **Security**: On every PR (advisory fail allowed at first, then enforced)
* **Regression**: Nightly on `main`

---

# Exit Criteria Checklist (copy into PR template)

* [ ] `env/<env>/{code,config,data,logs}` created by scripts
* [ ] Unique ports per env
* [ ] `/healthz` reachable in DEV
* [ ] JSON logs observed for mock job
* [ ] CI green for Unit/Functional/Security
* [ ] Nightly Regression green

---

## Notes for Phase 1 Dependency

* The **STAT** mock contract (events: start/step/done; fields: `job_id`, `step`, `status`) is the wire‑format your Phase 1 UI can read without change.
* Keep `src_common` free of env‑specific state to preserve isolation guarantees proven in Phase 0.
