# Multi-stage Dockerfile for TTRPG Center FastAPI Application
# Target: Python 3.12, FastAPI + APScheduler + CLI tools

# Build stage
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libev-dev \
    pkg-config \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Create virtual environment and install Python dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip wheel setuptools
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim AS production

# Install runtime system dependencies including OCR tools
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl \
    ca-certificates \
    # PDF processing (Poppler utilities)
    poppler-utils \
    # OCR (Tesseract)
    tesseract-ocr \
    tesseract-ocr-eng \
    # Cassandra runtime
    libev4 \
    # Image processing
    libmagic1 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r ttrpg && useradd -r -g ttrpg -u 1001 ttrpg

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /var/log/ttrpg /data/uploads /app/artifacts \
    && chown -R ttrpg:ttrpg /var/log/ttrpg /data/uploads /app/artifacts /app \
    && chmod 755 /var/log/ttrpg /data/uploads /app/artifacts

# Create application entry points
COPY services/app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown ttrpg:ttrpg /entrypoint.sh

# Switch to non-root user
USER ttrpg

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/healthz || exit 1

# Environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_ENV=dev

# Expose port
EXPOSE 8000

# Labels for metadata
LABEL org.opencontainers.image.title="TTRPG Center App" \
      org.opencontainers.image.description="AI-powered TTRPG content management platform" \
      org.opencontainers.image.version="dev" \
      org.opencontainers.image.vendor="TTRPG Center"

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src_common.app:app", "--host", "0.0.0.0", "--port", "8000"]
