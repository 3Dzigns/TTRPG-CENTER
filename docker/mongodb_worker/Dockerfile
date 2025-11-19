FROM mongo:6.0

# Install Python 3 and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    pymongo==4.6.1 \
    cassandra-driver==3.28.0 \
    neo4j==5.24.0 \
    requests==2.31.0 \
    psutil==5.9.5 \
    openai==1.10.0

# Create working directory
ENV WORKERS_DIR=/opt/workers
WORKDIR ${WORKERS_DIR}

# Create log directories
RUN mkdir -p \
    /Transfer_Station/Logs/pass_a_mongo_upsert \
    /var/log/supervisor

# Create log directories
RUN mkdir -p \
    /Transfer_Station/Logs/pass_a_mongo_upsert \
    /var/log/supervisor

# Copy base infrastructure
COPY ingestion/async_worker_base.py ${WORKERS_DIR}/
COPY ingestion/async_job_utils.py ${WORKERS_DIR}/
COPY ingestion/path_utils.py ${WORKERS_DIR}/
COPY ingestion/pipeline_routes.json ${WORKERS_DIR}/

# Copy worker and synchronous script
COPY ingestion/pass_a_mongo_upsert_worker.py ${WORKERS_DIR}/
COPY ingestion/pass_a_mongo_upsert.py ${WORKERS_DIR}/

# Copy supervisor configuration
COPY docker/mongodb_worker/supervisord.conf /etc/supervisor/conf.d/worker.conf

# Copy entrypoint script
COPY docker/mongodb_worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${WORKERS_DIR}:${PYTHONPATH}"
ENV TRANSFER_STATION=/Transfer_Station

# Health check - verify MongoDB and worker are running
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD mongosh --eval "db.adminCommand('ping')" && supervisorctl status pass_a_mongo_upsert | grep -q RUNNING

# Use custom entrypoint to start MongoDB + supervisor
ENTRYPOINT ["/entrypoint.sh"]
