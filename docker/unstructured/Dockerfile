FROM downloads.unstructured.io/unstructured-io/unstructured-api:latest

ENV INGESTION_HOME=/opt/ingestion
WORKDIR ${INGESTION_HOME}

# Copy ingestion tooling into the container image
COPY ingestion ${INGESTION_HOME}

# Install minimal dependencies required for Pass A/B/C orchestration
RUN pip install --no-cache-dir \
    pypdf==3.17.0 \
    python-docx==1.1.0 \
    requests==2.31.0 \
    psutil==5.9.5

# Runtime scripts for entrypoint and healthcheck
#  Copy with execute permissions (base image runs as non-root)
COPY --chmod=755 docker/unstructured/entrypoint.sh /usr/local/bin/unstructured-entrypoint.sh
COPY --chmod=755 docker/unstructured/healthcheck.sh /usr/local/bin/unstructured-healthcheck.sh

ENV PYTHONPATH="${INGESTION_HOME}:${PYTHONPATH}"

ENTRYPOINT ["/usr/local/bin/unstructured-entrypoint.sh"]
