#!/bin/bash
#
# monitor_unstructured_jobs.sh - Monitor async job queue status
#
# Displays current state of the unstructured job queue including:
# - Job counts by state (queued, in_progress, completed, failed)
# - Active worker information
# - Recent job details
#
# Usage:
#   ./scripts/monitor_unstructured_jobs.sh
#   ./scripts/monitor_unstructured_jobs.sh --watch  # Continuous monitoring

set -euo pipefail

JOBS_DIR="${UNSTRUCTURED_JOBS_DIR:-/Transfer_Station/jobs/unstructured}"
WATCH_MODE=false

# Parse arguments
if [[ "${1:-}" == "--watch" ]]; then
    WATCH_MODE=true
fi

monitor_jobs() {
    clear
    echo "==================================================================="
    echo "  Unstructured Async Job Queue Status"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "==================================================================="
    echo

    # Check if jobs directory exists
    if [[ ! -d "$JOBS_DIR" ]]; then
        echo "❌ Jobs directory not found: $JOBS_DIR"
        echo "   Check Transfer_Station mount and UNSTRUCTURED_JOBS_DIR"
        return 1
    fi

    # Count jobs by state
    echo "📊 Job Queue Statistics:"
    echo "-------------------------------------------------------------------"

    QUEUED=$(find "$JOBS_DIR" -maxdepth 2 -name "queued.marker" 2>/dev/null | wc -l)
    IN_PROGRESS=$(find "$JOBS_DIR" -maxdepth 2 -name "in_progress.*.marker" 2>/dev/null | wc -l)

    # Count completed and failed from status.json
    COMPLETED=0
    FAILED=0
    TOTAL=0

    for status_file in "$JOBS_DIR"/*/status.json; do
        if [[ -f "$status_file" ]]; then
            TOTAL=$((TOTAL + 1))
            state=$(jq -r '.state // "unknown"' "$status_file" 2>/dev/null)
            case "$state" in
                completed) COMPLETED=$((COMPLETED + 1)) ;;
                failed) FAILED=$((FAILED + 1)) ;;
            esac
        fi
    done

    echo "  Queued:      $QUEUED jobs"
    echo "  In Progress: $IN_PROGRESS jobs"
    echo "  Completed:   $COMPLETED jobs"
    echo "  Failed:      $FAILED jobs"
    echo "  Total:       $TOTAL jobs"
    echo

    # Show active workers
    echo "🤖 Active Workers:"
    echo "-------------------------------------------------------------------"

    WORKERS=$(find "$JOBS_DIR" -maxdepth 2 -name "in_progress.*.marker" 2>/dev/null | \
              sed 's/.*in_progress\.\(.*\)\.marker/\1/' | sort -u)

    if [[ -n "$WORKERS" ]]; then
        echo "$WORKERS" | while read -r worker; do
            echo "  ✅ $worker"
        done
    else
        echo "  (No active workers)"
    fi
    echo

    # Show recent jobs
    echo "📋 Recent Jobs (last 5):"
    echo "-------------------------------------------------------------------"

    find "$JOBS_DIR" -maxdepth 1 -type d -name "job_*" 2>/dev/null | \
        sort -r | head -5 | while read -r job_dir; do

        job_id=$(basename "$job_dir")
        status_file="$job_dir/status.json"

        if [[ -f "$status_file" ]]; then
            state=$(jq -r '.state // "unknown"' "$status_file" 2>/dev/null)
            worker=$(jq -r '.worker // "none"' "$status_file" 2>/dev/null)
            created=$(jq -r '.created_at // "unknown"' "$status_file" 2>/dev/null)

            case "$state" in
                queued) icon="⏳" ;;
                in_progress) icon="🔄" ;;
                completed) icon="✅" ;;
                failed) icon="❌" ;;
                *) icon="❓" ;;
            esac

            echo "  $icon $job_id"
            echo "     State: $state | Worker: $worker | Created: $created"
        fi
    done
    echo

    # Show failed jobs if any
    if [[ $FAILED -gt 0 ]]; then
        echo "⚠️  Failed Jobs:"
        echo "-------------------------------------------------------------------"

        find "$JOBS_DIR" -maxdepth 1 -type d -name "job_*" 2>/dev/null | while read -r job_dir; do
            status_file="$job_dir/status.json"

            if [[ -f "$status_file" ]]; then
                state=$(jq -r '.state // "unknown"' "$status_file" 2>/dev/null)

                if [[ "$state" == "failed" ]]; then
                    job_id=$(basename "$job_dir")
                    errors=$(jq -r '.errors // [] | join("; ")' "$status_file" 2>/dev/null)

                    echo "  ❌ $job_id"
                    echo "     Error: $errors"
                fi
            fi
        done
        echo
    fi

    # Check worker health in container
    echo "🏥 Worker Health Check:"
    echo "-------------------------------------------------------------------"

    if command -v docker &> /dev/null; then
        CONTAINER="ttrpg_unstructured"

        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
            # Check if worker process is running
            if docker exec "$CONTAINER" pgrep -f "unstructured_job_worker.py" > /dev/null 2>&1; then
                WORKER_PID=$(docker exec "$CONTAINER" pgrep -f "unstructured_job_worker.py" 2>/dev/null | head -1)
                echo "  ✅ Worker process running (PID: $WORKER_PID)"

                # Check worker log
                LOG_PATH="/Transfer_Station/Logs/unstructured/worker.log"
                if docker exec "$CONTAINER" test -f "$LOG_PATH" 2>/dev/null; then
                    LAST_LOG=$(docker exec "$CONTAINER" tail -1 "$LOG_PATH" 2>/dev/null || echo "")
                    if [[ -n "$LAST_LOG" ]]; then
                        echo "  📝 Last log: ${LAST_LOG:0:80}..."
                    fi
                fi
            else
                echo "  ❌ Worker process NOT running"
                echo "     Container may need restart"
            fi
        else
            echo "  ⚠️  Container '$CONTAINER' not running"
        fi
    else
        echo "  ℹ️  Docker not available for health check"
    fi
    echo

    echo "==================================================================="
    echo "  Commands:"
    echo "    View worker log:  docker exec ttrpg_unstructured tail -f /Transfer_Station/Logs/unstructured/worker.log"
    echo "    Inspect job:      python ingestion/unstructured_job_cli.py --status <job_id>"
    echo "    Restart worker:   docker compose -f docker-compose-ttrpg.yml restart unstructured"
    echo "==================================================================="
}

# Main execution
if $WATCH_MODE; then
    echo "Starting watch mode (Ctrl+C to exit)..."
    sleep 2

    while true; do
        monitor_jobs
        sleep 5
    done
else
    monitor_jobs
fi
