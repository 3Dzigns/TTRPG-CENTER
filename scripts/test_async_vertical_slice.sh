#!/bin/bash
# test_async_vertical_slice.sh - Test async pipeline vertical slice
# ==================================================================
#
# Tests the async pipeline implementation with a simple end-to-end flow.
# This validates the architecture before scaling to all workers.
#
# Usage:
#   bash scripts/test_async_vertical_slice.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Async Pipeline Vertical Slice Testing${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Configuration
TRANSFER_STATION="/e/n8n_TTRPG_Transfer_Station"
JOBS_ROOT="${TRANSFER_STATION}/jobs"
LOGS_ROOT="${TRANSFER_STATION}/Logs"
SOURCES_DIR="${TRANSFER_STATION}/sources"
CONTAINER_NAME="ttrpg_ingestion_engine_1"  # Adjust if different

# Find ingestion container
echo -e "${YELLOW}[1/8]${NC} Finding ingestion container..."
CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "ingestion" | head -1 || echo "")

if [ -z "$CONTAINER" ]; then
    echo -e "${RED}❌ No ingestion container found${NC}"
    echo "Available containers:"
    docker ps --format "  - {{.Names}}"
    exit 1
fi

echo -e "${GREEN}✅ Using container: ${CONTAINER}${NC}"
echo ""

# Check if workers exist in container
echo -e "${YELLOW}[2/8]${NC} Verifying worker files in container..."
WORKERS=(
    "gate_0_hash_worker.py"
    "gate_0_validate_worker.py"
    "doc_splitter_worker.py"
    "ingestion_wrapper_async.py"
    "async_worker_base.py"
    "async_job_utils.py"
    "pipeline_routes.json"
)

MISSING_FILES=()
for worker in "${WORKERS[@]}"; do
    if ! docker exec "$CONTAINER" test -f "/opt/ingestion/${worker}" 2>/dev/null; then
        MISSING_FILES+=("$worker")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}❌ Missing files in container:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    echo ""
    echo "Run: docker cp ingestion/. ${CONTAINER}:/opt/ingestion/"
    exit 1
fi

echo -e "${GREEN}✅ All worker files present${NC}"
echo ""

# Create directory structure
echo -e "${YELLOW}[3/8]${NC} Setting up directory structure..."
mkdir -p "${JOBS_ROOT}"/{gate_0_hash,gate_0_validate,doc_splitter,complete,failed}
mkdir -p "${LOGS_ROOT}"/{gate_0_hash,gate_0_validate,doc_splitter}
mkdir -p "${TRANSFER_STATION}"/{Gate_0_Out,Gate_0_Check,Pass_A_Out}

echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Select test file
echo -e "${YELLOW}[4/8]${NC} Selecting test file..."
TEST_FILE=$(ls "${SOURCES_DIR}"/*.pdf 2>/dev/null | head -1 || echo "")

if [ -z "$TEST_FILE" ]; then
    echo -e "${RED}❌ No PDF files found in ${SOURCES_DIR}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Test file: $(basename "$TEST_FILE")${NC}"
echo ""

# Clean previous test jobs
echo -e "${YELLOW}[5/8]${NC} Cleaning previous test runs..."
rm -rf "${JOBS_ROOT}"/gate_0_hash/* 2>/dev/null || true
rm -rf "${JOBS_ROOT}"/gate_0_validate/* 2>/dev/null || true
rm -rf "${JOBS_ROOT}"/doc_splitter/* 2>/dev/null || true
rm -rf "${JOBS_ROOT}"/complete/* 2>/dev/null || true
rm -rf "${LOGS_ROOT}"/*/worker.log 2>/dev/null || true

echo -e "${GREEN}✅ Cleaned previous runs${NC}"
echo ""

# Queue test job
echo -e "${YELLOW}[6/8]${NC} Queueing test job..."
docker exec "$CONTAINER" bash -c "cd /opt/ingestion && python3 ingestion_wrapper_async.py --source '${TEST_FILE}'"

JOB_ID=$(ls "${JOBS_ROOT}/gate_0_hash/" 2>/dev/null | head -1)

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ Failed to create job${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Job queued: ${JOB_ID}${NC}"
echo ""

# Start workers in background
echo -e "${YELLOW}[7/8]${NC} Starting workers..."

echo "  Starting gate_0_hash_worker..."
docker exec -d "$CONTAINER" bash -c "cd /opt/ingestion && python3 gate_0_hash_worker.py --log-level INFO > /dev/null 2>&1"

echo "  Starting gate_0_validate_worker..."
docker exec -d "$CONTAINER" bash -c "cd /opt/ingestion && python3 gate_0_validate_worker.py --log-level INFO > /dev/null 2>&1"

echo "  Starting doc_splitter_worker..."
docker exec -d "$CONTAINER" bash -c "cd /opt/ingestion && python3 doc_splitter_worker.py --log-level INFO > /dev/null 2>&1"

sleep 2
echo -e "${GREEN}✅ Workers started${NC}"
echo ""

# Monitor job progress
echo -e "${YELLOW}[8/8]${NC} Monitoring job progress..."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

MAX_WAIT=60  # seconds
ELAPSED=0
FOUND=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check all possible locations
    for stage in gate_0_hash gate_0_validate doc_splitter complete failed; do
        if [ -d "${JOBS_ROOT}/${stage}/${JOB_ID}" ]; then
            STATUS_FILE="${JOBS_ROOT}/${stage}/${JOB_ID}/status.json"

            if [ -f "$STATUS_FILE" ]; then
                CURRENT_STAGE=$(grep -o '"current_stage": *"[^"]*"' "$STATUS_FILE" | sed 's/"current_stage": *"\([^"]*\)"/\1/')
                JOB_STATUS=$(grep -o '"status": *"[^"]*"' "$STATUS_FILE" | head -1 | sed 's/"status": *"\([^"]*\)"/\1/')

                echo -ne "\r${BLUE}Time: ${ELAPSED}s${NC} | Stage: ${YELLOW}${CURRENT_STAGE}${NC} | Status: ${YELLOW}${JOB_STATUS}${NC}    "

                if [ "$CURRENT_STAGE" = "complete" ] || [ "$CURRENT_STAGE" = "failed" ]; then
                    FOUND=true
                    echo ""
                    break 2
                fi
            fi
        fi
    done

    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Report results
if [ "$FOUND" = true ]; then
    echo ""
    echo -e "${GREEN}✅ Job completed successfully!${NC}"
    echo ""

    # Find final location
    for stage in complete doc_splitter pass_a_unstructured; do
        FINAL_STATUS="${JOBS_ROOT}/${stage}/${JOB_ID}/status.json"
        if [ -f "$FINAL_STATUS" ]; then
            echo -e "${BLUE}Final Status:${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            # Extract key fields
            VALIDATION_STATUS=$(grep -o '"validation_status": *"[^"]*"' "$FINAL_STATUS" | sed 's/"validation_status": *"\([^"]*\)"/\1/' || echo "N/A")
            DOCUMENT_ID=$(grep -o '"document_id": *"[^"]*"' "$FINAL_STATUS" | sed 's/"document_id": *"\([^"]*\)"/\1/' || echo "N/A")
            STAGES_COMPLETED=$(grep -o '"stages_completed": *\[[^]]*\]' "$FINAL_STATUS" || echo "[]")

            echo "  Current Stage: ${CURRENT_STAGE}"
            echo "  Job Status: ${JOB_STATUS}"
            echo "  Validation Status: ${VALIDATION_STATUS}"
            echo "  Document ID: ${DOCUMENT_ID}"
            echo "  Stages Completed: ${STAGES_COMPLETED}"
            echo ""
            echo "  Full Status: ${FINAL_STATUS}"
            break
        fi
    done

    # Show worker logs
    echo ""
    echo -e "${BLUE}Worker Logs:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    for worker_log in "${LOGS_ROOT}"/*/worker.log; do
        if [ -f "$worker_log" ]; then
            echo ""
            echo "$(dirname "$worker_log" | xargs basename):"
            tail -5 "$worker_log" | sed 's/^/  /'
        fi
    done

else
    echo ""
    echo -e "${RED}❌ Timeout after ${MAX_WAIT}s${NC}"
    echo ""
    echo "Check logs:"
    echo "  ${LOGS_ROOT}/gate_0_hash/worker.log"
    echo "  ${LOGS_ROOT}/gate_0_validate/worker.log"
    echo "  ${LOGS_ROOT}/doc_splitter/worker.log"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Test Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
