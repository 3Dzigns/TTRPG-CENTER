FROM python:3.11-slim

# Install system dependencies and supervisor
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set working directories
ENV SCRIPTS_DIR=/Transfer_Station/scripts
ENV INGESTION_DIR=/app/ingestion
WORKDIR ${SCRIPTS_DIR}

# Install Python dependencies
RUN pip install --no-cache-dir \
    cassandra-driver==3.28.0 \
    pymongo==4.6.1 \
    neo4j==5.24.0 \
    requests==2.31.0 \
    psutil==5.9.5 \
    openai==1.10.0 \
    pypdf==3.17.0 \
    python-docx==1.1.0

# Create necessary directories
RUN mkdir -p \
    ${SCRIPTS_DIR} \
    /Transfer_Station/Logs/source_monitor \
    /Transfer_Station/Logs/gate_0_hash \
    /Transfer_Station/Logs/gate_0_validate \
    /Transfer_Station/Logs/doc_splitter \
    /Transfer_Station/Logs/pass_a_metadata \
    /var/log/supervisor

# Copy base infrastructure
COPY ingestion/async_worker_base.py ${SCRIPTS_DIR}/
COPY ingestion/async_job_utils.py ${SCRIPTS_DIR}/
COPY ingestion/path_utils.py ${SCRIPTS_DIR}/
COPY ingestion/dictionary_store.py ${SCRIPTS_DIR}/
COPY ingestion/pipeline_routes.json ${SCRIPTS_DIR}/

# Copy workers
COPY ingestion/source_monitor_worker.py ${SCRIPTS_DIR}/
COPY ingestion/gate_0_hash_worker.py ${SCRIPTS_DIR}/
COPY ingestion/gate_0_validate_worker.py ${SCRIPTS_DIR}/
COPY ingestion/doc_splitter_worker.py ${SCRIPTS_DIR}/
COPY ingestion/pass_a_metadata_worker.py ${SCRIPTS_DIR}/

# Copy synchronous scripts these workers call
COPY ingestion/cleanup_document.py ${SCRIPTS_DIR}/
COPY ingestion/ingestion_wrapper_async.py ${SCRIPTS_DIR}/
COPY ingestion/gate_0_hash.py ${SCRIPTS_DIR}/
COPY ingestion/gate_0_validate.py ${SCRIPTS_DIR}/
COPY ingestion/doc_splitter.py ${SCRIPTS_DIR}/
COPY ingestion/pass_a_metadata.py ${SCRIPTS_DIR}/

# Copy supervisor configuration
COPY docker/ingestion_engine/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${SCRIPTS_DIR}:${PYTHONPATH}"
ENV TRANSFER_STATION=/Transfer_Station

# Health check - verify all workers are running
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD supervisorctl status | grep -E "(gate_0_hash|gate_0_validate|doc_splitter|pass_a_metadata):RUNNING" | wc -l | grep -q "4"

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
