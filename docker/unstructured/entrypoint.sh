#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/opt/ingestion:${PYTHONPATH:-}"

JOBS_DIR="${UNSTRUCTURED_JOBS_DIR:-/Transfer_Station/jobs/unstructured}"
LOG_DIR="${UNSTRUCTURED_LOG_DIR:-/Transfer_Station/Logs/unstructured}"

mkdir -p "${JOBS_DIR}" "${LOG_DIR}"

# Start async job worker in background
# Disable error exit for worker startup to prevent zombie processes
echo "Starting unstructured_job_worker.py..."
set +e
(
  python3 /opt/ingestion/unstructured_job_worker.py \
    --jobs-dir "${JOBS_DIR}" \
    --log-dir "${LOG_DIR}" \
    --poll-interval 5 \
    >> "${LOG_DIR}/worker.log" 2>&1
) &
WORKER_PID=$!
set -e

echo "Started unstructured_job_worker.py (PID: ${WORKER_PID})"

# Give worker a moment to initialize and verify it's running
sleep 2
if kill -0 "${WORKER_PID}" 2>/dev/null; then
  echo "Worker process verified running (PID: ${WORKER_PID})"
else
  echo "WARNING: Worker process may have died (PID: ${WORKER_PID})"
fi

# Start the unstructured API server (from base image)
exec uvicorn prepline_general.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info
