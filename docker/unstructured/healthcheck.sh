#!/usr/bin/env bash
set -euo pipefail

curl -sf http://localhost:8000/health >/dev/null 2>&1 || \
curl -sf http://localhost:8000/docs >/dev/null 2>&1 || exit 1

pgrep -f "unstructured_job_worker.py" >/dev/null 2>&1 || exit 1

exit 0
