# Build a lightweight Haystack 1.x REST API image (CPU)
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HAYSTACK_TELEMETRY=False

# System deps for tokenizers, faiss-cpu wheels, PDF/OCR, and runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl wget ca-certificates \
    libsndfile1 \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

# Pre-pin CPU torch wheel to avoid building from source
RUN python -m pip install "torch==2.2.2" --index-url https://download.pytorch.org/whl/cpu

# Haystack 1.x + useful extras for REST API; avoid [all] to reduce size/conflicts
RUN python -m pip install \
    "farm-haystack[faiss,ocr,pdf,elasticsearch]==1.25.2" \
    "uvicorn[standard]==0.30.6" \
    "gunicorn==22.0.0"

EXPOSE 8000

# Healthcheck probes Haystack's liveness endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
  CMD python - << 'PY' || exit 1
import urllib.request, sys
try:
    urllib.request.urlopen("http://127.0.0.1:8000/livez", timeout=5)
except Exception:
    sys.exit(1)
PY

# Start the REST API (Haystack 1.x)
CMD ["gunicorn", "rest_api.application:app", "-b", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
