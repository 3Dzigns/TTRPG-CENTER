FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WORKDIR=/app

WORKDIR ${WORKDIR}

RUN apt-get update && apt-get install -y \
    supervisor \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    "celery[redis]==5.4.0" \
    "psycopg[binary]==3.2.1" \
    "unstructured[pdf]==0.17.2" \
    "pydantic==2.10.6" \
    "openai==1.59.7" \
    "cassandra-driver==3.29.2" \
    "neo4j==5.28.0"

COPY docker/workers/entrypoint.sh /usr/local/bin/worker-entrypoint.sh
RUN chmod +x /usr/local/bin/worker-entrypoint.sh

COPY ingestion ./ingestion

ENTRYPOINT ["/usr/local/bin/worker-entrypoint.sh"]
