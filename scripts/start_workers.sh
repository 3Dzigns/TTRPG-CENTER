#!/bin/bash
# start_workers.sh - Start all async workers for ingestion pipeline
#
# Usage: bash start_workers.sh [--stop] [--status]
#
# This script manages the lifecycle of async worker processes for the
# TTRPG ingestion pipeline. Workers poll their respective job queues
# and process tasks asynchronously.

set -e

JOBS_DIR="/Transfer_Station/jobs/unstructured"
LOG_DIR="/Transfer_Station/Logs/workers"
SCRIPTS_DIR="/app/scripts"

# Ensure directories exist
mkdir -p "$JOBS_DIR" "$LOG_DIR"

# Worker definitions: script_name:log_name
WORKERS=(
    "unstructured_job_worker.py:unstructured_worker"
    "pass_d_hayhooks_worker.py:hayhooks_worker"
    "pass_d_checksum_worker.py:checksum_worker"
    "pass_e_graph_builder_worker.py:graph_builder_worker"
    "pass_e_neo4j_upsert_worker.py:neo4j_upsert_worker"
)

stop_workers() {
    echo "Stopping all workers..."
    for worker_def in "${WORKERS[@]}"; do
        script_name="${worker_def%%:*}"
        pkill -f "$script_name" && echo "  OK Stopped $script_name" || echo "  - $script_name not running"
    done
    echo "All workers stopped."
}

status_workers() {
    echo "Worker Status:"
    echo "============================================"
    for worker_def in "${WORKERS[@]}"; do
        script_name="${worker_def%%:*}"
        if pgrep -f "$script_name" > /dev/null; then
            pid=$(pgrep -f "$script_name")
            echo "  OK $script_name [PID: $pid]"
        else
            echo "  -- $script_name [NOT RUNNING]"
        fi
    done
    echo "============================================"
}

start_workers() {
    echo "Starting all workers..."

    for worker_def in "${WORKERS[@]}"; do
        script_name="${worker_def%%:*}"
        log_name="${worker_def##*:}"
        log_file="$LOG_DIR/${log_name}.log"

        # Check if worker script exists
        if [ ! -f "$SCRIPTS_DIR/$script_name" ]; then
            echo "  !! Warning: $script_name not found, skipping"
            continue
        fi

        # Check if already running
        if pgrep -f "$script_name" > /dev/null; then
            echo "  - $script_name already running"
            continue
        fi

        # Start worker in background
        nohup python3 "$SCRIPTS_DIR/$script_name" \
            --jobs-dir "$JOBS_DIR" \
            --log-dir "$LOG_DIR" \
            --log-level INFO \
            >> "$log_file" 2>&1 &

        echo "  OK Started $script_name [PID: $!]"
        sleep 1
    done

    echo ""
    echo "All workers started. Logs available in: $LOG_DIR"
    echo ""
    status_workers
}

# Parse command line arguments
case "${1:-start}" in
    --stop)
        stop_workers
        ;;
    --status)
        status_workers
        ;;
    --restart)
        stop_workers
        sleep 2
        start_workers
        ;;
    start|--start)
        start_workers
        ;;
    *)
        echo "Usage: $0 [start|--stop|--status|--restart]"
        exit 1
        ;;
esac
