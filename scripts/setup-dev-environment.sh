#!/bin/bash
set -euo pipefail

# Setup development environment with Python 3.12+ and linting tools
# This script sets up the development environment according to MVP v2 coding standards

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

FORCE=${1:-""}

echo -e "${GREEN}🚀 Setting up TTRPG Center development environment...${NC}"

# Check Python version
echo -e "${BLUE}📋 Checking Python version...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python not found in PATH${NC}"
    echo -e "${YELLOW}Please install Python 3.12+ from https://python.org${NC}"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1)
if [[ $PYTHON_VERSION =~ Python\ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    MAJOR=${BASH_REMATCH[1]}
    MINOR=${BASH_REMATCH[2]}

    if [[ $MAJOR -lt 3 ]] || [[ $MAJOR -eq 3 && $MINOR -lt 12 ]]; then
        echo -e "${RED}❌ Python 3.12+ required, found: $PYTHON_VERSION${NC}"
        echo -e "${YELLOW}Please install Python 3.12+ from https://python.org${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Python version: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}❌ Could not parse Python version: $PYTHON_VERSION${NC}"
    exit 1
fi

# Check for virtual environment
echo -e "${BLUE}📋 Checking virtual environment...${NC}"
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${YELLOW}⚠️  No virtual environment detected${NC}"
    echo -e "${YELLOW}Recommended: Create and activate a virtual environment:${NC}"
    echo -e "${GRAY}  python -m venv .venv${NC}"
    echo -e "${GRAY}  source .venv/bin/activate   # Linux/macOS${NC}"
    echo ""
else
    echo -e "${GREEN}✅ Virtual environment: $VIRTUAL_ENV${NC}"
fi

# Install development dependencies
echo -e "${BLUE}📦 Installing development dependencies...${NC}"
if [[ "$FORCE" == "--force" ]]; then
    python -m pip install --upgrade pip --force-reinstall
    python -m pip install -e .[dev] --force-reinstall
else
    python -m pip install --upgrade pip
    python -m pip install -e .[dev]
fi
echo -e "${GREEN}✅ Development dependencies installed${NC}"

# Install pre-commit hooks
echo -e "${BLUE}🔧 Setting up pre-commit hooks...${NC}"
pre-commit install
echo -e "${GREEN}✅ Pre-commit hooks installed${NC}"

# Validate tool configuration
echo -e "${BLUE}🔍 Validating tool configuration...${NC}"

# Test Black
if black --check --diff --quiet . 2>/dev/null; then
    echo -e "${GREEN}✅ Black configuration valid${NC}"
else
    echo -e "${YELLOW}⚠️  Black found formatting issues (run 'black .' to fix)${NC}"
fi

# Test Ruff
if ruff check . --quiet 2>/dev/null; then
    echo -e "${GREEN}✅ Ruff configuration valid${NC}"
else
    echo -e "${YELLOW}⚠️  Ruff found linting issues (run 'ruff check . --fix' to fix)${NC}"
fi

# Test isort
if isort --check-only --quiet . 2>/dev/null; then
    echo -e "${GREEN}✅ isort configuration valid${NC}"
else
    echo -e "${YELLOW}⚠️  isort found import sorting issues (run 'isort .' to fix)${NC}"
fi

# Test mypy
if mypy --version >/dev/null 2>&1; then
    echo -e "${GREEN}✅ mypy available${NC}"
else
    echo -e "${YELLOW}⚠️  mypy not properly configured${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Development environment setup complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "${GRAY}  • Run tests: pytest tests/unit${NC}"
echo -e "${GRAY}  • Format code: black .${NC}"
echo -e "${GRAY}  • Lint code: ruff check . --fix${NC}"
echo -e "${GRAY}  • Type check: mypy src_common/${NC}"
echo -e "${GRAY}  • Run all checks: pre-commit run --all-files${NC}"