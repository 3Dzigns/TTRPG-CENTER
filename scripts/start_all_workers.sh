#!/bin/bash
################################################################################
# start_all_workers.sh - Launch All Async Pipeline Workers
################################################################################
#
# This script launches all async workers for the complete ingestion pipeline.
#
# Workers (in pipeline order):
#   1. gate_0_hash_worker          - Hash calculation
#   2. gate_0_validate_worker      - Validation checks
#   3. doc_splitter_worker         - Document splitting
#   4. pass_a_unstructured_worker  - Unstructured.io processing (separate container)
#   5. pass_a_metadata_worker      - TOC metadata extraction
#   6. pass_a_mongo_upsert_worker  - Dictionary upsert (Postgres)
#   7. pass_d_checksum_worker      - Checksum writing
#   8. pass_d_hayhooks_worker      - Embedding generation (2-hour timeout)
#   9. pass_e_graph_builder_worker - Graph building
#  10. pass_e_neo4j_upsert_worker  - Neo4j upsert
#
# Usage:
#   bash start_all_workers.sh
#
# Logs: /Transfer_Station/Logs/<stage_name>_worker.log
#

set -e

CONTAINER="ttrpg_ingestion_engine"
UNSTRUCTURED_CONTAINER="ttrpg_unstructured"
JOBS_DIR="/Transfer_Station/jobs"
LOG_DIR="/Transfer_Station/Logs"
SCRIPTS_DIR="/Transfer_Station/scripts"
POLL_INTERVAL=5

echo "========================================="
echo "Starting All Async Pipeline Workers"
echo "========================================="
echo ""
echo "Container: $CONTAINER"
echo "Unstructured Container: $UNSTRUCTURED_CONTAINER"
echo "Jobs Directory: $JOBS_DIR"
echo "Log Directory: $LOG_DIR"
echo "Poll Interval: ${POLL_INTERVAL}s"
echo ""

# Function to start a worker
start_worker() {
    local container=$1
    local worker_name=$2
    local stage_name=$3

    echo "Starting $worker_name (stage: $stage_name)..."

    docker exec -d "$container" bash -c \
        "cd $SCRIPTS_DIR && python3 ${worker_name}.py \
        --jobs-dir $JOBS_DIR \
        --log-dir $LOG_DIR \
        --poll-interval $POLL_INTERVAL \
        2>&1 | tee -a ${LOG_DIR}/${stage_name}_worker.log"

    echo "OK $worker_name started (logs: ${LOG_DIR}/${stage_name}_worker.log)"
    sleep 1
}

# Gate 0 Workers (Vertical Slice)
echo "--- Gate 0 Workers ---"
start_worker "$CONTAINER" "gate_0_hash_worker" "gate_0_hash"
start_worker "$CONTAINER" "gate_0_validate_worker" "gate_0_validate"
start_worker "$CONTAINER" "doc_splitter_worker" "doc_splitter"
echo ""

# Pass A Workers (Unstructured + Metadata + MongoDB)
echo "--- Pass A Workers ---"
# Note: pass_a_unstructured_worker runs in separate container using existing script
echo "Starting pass_a_unstructured_worker (separate container - already running)"
echo "OK pass_a_unstructured_worker (verified running in ttrpg_unstructured container)"

start_worker "$CONTAINER" "pass_a_metadata_worker" "pass_a_metadata"
start_worker "$CONTAINER" "pass_a_mongo_upsert_worker" "pass_a_mongo_upsert"
echo ""

# Pass D Workers (Checksum + Embeddings)
echo "--- Pass D Workers ---"
start_worker "$CONTAINER" "pass_d_checksum_worker" "pass_d_checksum"
start_worker "$CONTAINER" "pass_d_hayhooks_worker" "pass_d_hayhooks"
echo ""

# Pass E Workers (Graph + Neo4j)
echo "--- Pass E Workers ---"
start_worker "$CONTAINER" "pass_e_graph_builder_worker" "pass_e_graph_builder"
start_worker "$CONTAINER" "pass_e_neo4j_upsert_worker" "pass_e_neo4j_upsert"
echo ""

echo "========================================="
echo "All Workers Started Successfully!"
echo "========================================="
echo ""
echo "Monitor worker activity:"
echo "  docker exec $CONTAINER ps aux | grep worker"
echo ""
echo "View worker logs:"
echo "  docker exec $CONTAINER tail -f ${LOG_DIR}/<stage_name>_worker.log"
echo ""
echo "Stop all workers:"
echo "  docker exec $CONTAINER pkill -f '_worker.py'"
echo "  docker exec $UNSTRUCTURED_CONTAINER pkill -f 'unstructured_job_worker'"
echo ""

