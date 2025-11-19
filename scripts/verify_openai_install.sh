#!/bin/bash
# Verify OpenAI and httpx installation compatibility

echo "🔍 Checking OpenAI and httpx versions..."

OPENAI_VERSION=$(python -c "import openai; print(openai.__version__)" 2>/dev/null || echo "not installed")
HTTPX_VERSION=$(python -c "import httpx; print(httpx.__version__)" 2>/dev/null || echo "not installed")

echo "OpenAI version: $OPENAI_VERSION"
echo "httpx version: $HTTPX_VERSION"

# Check if versions are compatible
if [ "$OPENAI_VERSION" = "not installed" ]; then
    echo "❌ OpenAI library not installed"
    echo "Run: pip install -r ingestion/requirements.txt"
    exit 1
fi

# Extract major.minor version
OPENAI_MAJOR=$(echo $OPENAI_VERSION | cut -d'.' -f1)
OPENAI_MINOR=$(echo $OPENAI_VERSION | cut -d'.' -f2)

if [ "$OPENAI_MAJOR" -eq 1 ] && [ "$OPENAI_MINOR" -ge 50 ]; then
    echo "✅ OpenAI version is compatible (1.50+)"
else
    echo "⚠️  OpenAI version may be incompatible. Recommended: 1.50+"
fi

# Run compatibility test if pytest is available
if command -v pytest &> /dev/null; then
    echo ""
    echo "🧪 Running compatibility tests..."
    python -m pytest tests/test_openai_compatibility.py -v 2>/dev/null || echo "Tests not found or failed"
else
    echo ""
    echo "ℹ️  Install pytest to run compatibility tests: pip install pytest"
fi

echo ""
echo "✅ Verification complete"
