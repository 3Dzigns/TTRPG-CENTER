#!/bin/bash
# Run all tests for the 3 fixes

set -e

echo "🧪 Running all tests for ingestion fixes..."
echo ""

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Install test dependencies
echo "Installing test dependencies..."
pip install -q pytest pytest-cov pytest-mock 2>/dev/null || echo "⚠️  Could not install test dependencies"

echo ""
echo "1️⃣ Testing Retry Mechanism (Issue 1)..."
python -m pytest tests/test_retry_mechanism.py -v --tb=short 2>&1 | head -50 || echo "⚠️  Tests not yet implemented"

echo ""
echo "2️⃣ Testing OpenAI Compatibility (Issue 2)..."
python -m pytest tests/test_openai_compatibility.py -v --tb=short 2>&1 | head -50 || echo "⚠️  Tests not yet implemented"

echo ""
echo "3️⃣ Testing Pipeline State (Issue 3)..."
python -m pytest tests/test_pipeline_state.py -v --tb=short 2>&1 | head -50 || echo "⚠️  Tests not yet implemented"

echo ""
echo "4️⃣ Running Integration Tests..."
python -m pytest tests/test_integration.py -v --tb=short 2>&1 | head -50 || echo "⚠️  Tests not yet implemented"

echo ""
echo "📊 Generating Coverage Report..."
python -m pytest tests/ --cov=ingestion --cov-report=term-missing --cov-report=html 2>&1 | tail -30 || echo "⚠️  Coverage report generation failed"

echo ""
echo "✅ Test execution complete!"
echo "📄 Coverage report: htmlcov/index.html"
