FROM python:3.11-slim

# Install system dependencies including supervisor
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install LlamaIndex and related dependencies
# Note: Let pip resolve compatible versions for llama-index plugins
RUN pip install --no-cache-dir \
    llama-index \
    llama-index-vector-stores-cassandra \
    llama-index-graph-stores-neo4j \
    cassandra-driver==3.28.0 \
    neo4j==5.24.0 \
    pymongo==4.6.1 \
    pypdf==3.17.0 \
    python-docx==1.1.0 \
    requests==2.31.0 \
    psutil==5.9.5 \
    openai==1.10.0

# Create working directory
ENV WORKERS_DIR=/opt/workers
WORKDIR ${WORKERS_DIR}

# Create log directories
RUN mkdir -p \
    /Transfer_Station/Logs/pass_e_graph_builder \
    /Transfer_Station/Logs/pass_e_neo4j_upsert \
    /var/log/supervisor

# Copy base infrastructure
COPY ingestion/async_worker_base.py ${WORKERS_DIR}/
COPY ingestion/async_job_utils.py ${WORKERS_DIR}/
COPY ingestion/path_utils.py ${WORKERS_DIR}/
COPY ingestion/pipeline_routes.json ${WORKERS_DIR}/

# Copy workers and synchronous scripts
COPY ingestion/pass_e_graph_builder_worker.py ${WORKERS_DIR}/
COPY ingestion/pass_e_graph_builder.py ${WORKERS_DIR}/
COPY ingestion/pass_e_neo4j_upsert_worker.py ${WORKERS_DIR}/
COPY ingestion/pass_e_neo4j_upsert.py ${WORKERS_DIR}/

# Copy supervisor configuration
COPY docker/llamaindex/supervisord.conf /etc/supervisor/conf.d/worker.conf

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${WORKERS_DIR}:${PYTHONPATH}"
ENV TRANSFER_STATION=/Transfer_Station

# Health check - verify both workers are running
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD supervisorctl status | grep -E "(pass_e_graph_builder|pass_e_neo4j_upsert):RUNNING" | wc -l | grep -q "2"

# Start supervisor to manage workers
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/worker.conf"]
