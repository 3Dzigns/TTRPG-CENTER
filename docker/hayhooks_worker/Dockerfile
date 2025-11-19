FROM deepset/hayhooks:v0.4.0

# Install supervisor
USER root
RUN apt-get update && apt-get install -y \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
ENV WORKERS_DIR=/opt/workers
WORKDIR ${WORKERS_DIR}

# Create log directories
RUN mkdir -p \
    /Transfer_Station/Logs/pass_d_hayhooks \
    /var/log/supervisor

# Create log directories
RUN mkdir -p \
    /Transfer_Station/Logs/pass_d_hayhooks \
    /var/log/supervisor

# Copy base infrastructure
COPY ingestion/async_worker_base.py ${WORKERS_DIR}/
COPY ingestion/async_job_utils.py ${WORKERS_DIR}/
COPY ingestion/path_utils.py ${WORKERS_DIR}/
COPY ingestion/pipeline_routes.json ${WORKERS_DIR}/

# Copy worker and synchronous script
COPY ingestion/pass_d_hayhooks_worker.py ${WORKERS_DIR}/
COPY ingestion/pass_d_hayhooks.py ${WORKERS_DIR}/

# Copy supervisor configuration
COPY docker/hayhooks_worker/supervisord.conf /etc/supervisor/conf.d/worker.conf

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${WORKERS_DIR}:${PYTHONPATH}"
ENV TRANSFER_STATION=/Transfer_Station

# Health check - verify hayhooks and worker are running
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:1416/status && supervisorctl status pass_d_hayhooks | grep -q RUNNING

# Start hayhooks in background, then supervisor
CMD ["sh", "-c", "hayhooks run --host 0.0.0.0 --port 1416 & sleep 10 && exec /usr/bin/supervisord -c /etc/supervisor/conf.d/worker.conf"]
