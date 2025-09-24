#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Set up development environment with Python 3.12+ and linting tools
.DESCRIPTION
    This script sets up the development environment according to MVP v2 coding standards:
    - Verifies Python 3.12+ installation
    - Installs development dependencies
    - Sets up pre-commit hooks
    - Validates tool configuration
.PARAMETER Force
    Force reinstallation of all dependencies
#>

param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "🚀 Setting up TTRPG Center development environment..." -ForegroundColor Green

# Check Python version
Write-Host "📋 Checking Python version..." -ForegroundColor Blue
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found in PATH"
    }

    if ($pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]

        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 12)) {
            throw "Python 3.12+ required, found: $pythonVersion"
        }

        Write-Host "✅ Python version: $pythonVersion" -ForegroundColor Green
    } else {
        throw "Could not parse Python version: $pythonVersion"
    }
} catch {
    Write-Host "❌ $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please install Python 3.12+ from https://python.org" -ForegroundColor Yellow
    exit 1
}

# Check for virtual environment
Write-Host "📋 Checking virtual environment..." -ForegroundColor Blue
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠️  No virtual environment detected" -ForegroundColor Yellow
    Write-Host "Recommended: Create and activate a virtual environment:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Gray
    Write-Host "  .venv\Scripts\Activate.ps1  # Windows" -ForegroundColor Gray
    Write-Host "  source .venv/bin/activate   # Linux/macOS" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "✅ Virtual environment: $env:VIRTUAL_ENV" -ForegroundColor Green
}

# Install development dependencies
Write-Host "📦 Installing development dependencies..." -ForegroundColor Blue
try {
    if ($Force) {
        python -m pip install --upgrade pip --force-reinstall
        python -m pip install -e .[dev] --force-reinstall
    } else {
        python -m pip install --upgrade pip
        python -m pip install -e .[dev]
    }
    Write-Host "✅ Development dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install dependencies: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Install pre-commit hooks
Write-Host "🔧 Setting up pre-commit hooks..." -ForegroundColor Blue
try {
    pre-commit install
    Write-Host "✅ Pre-commit hooks installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install pre-commit hooks: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Validate tool configuration
Write-Host "🔍 Validating tool configuration..." -ForegroundColor Blue

# Test Black
try {
    black --check --diff --quiet . 2>$null
    Write-Host "✅ Black configuration valid" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Black found formatting issues (run 'black .' to fix)" -ForegroundColor Yellow
}

# Test Ruff
try {
    ruff check . --quiet 2>$null
    Write-Host "✅ Ruff configuration valid" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ruff found linting issues (run 'ruff check . --fix' to fix)" -ForegroundColor Yellow
}

# Test isort
try {
    isort --check-only --quiet . 2>$null
    Write-Host "✅ isort configuration valid" -ForegroundColor Green
} catch {
    Write-Host "⚠️  isort found import sorting issues (run 'isort .' to fix)" -ForegroundColor Yellow
}

# Test mypy
try {
    mypy --version >$null 2>&1
    Write-Host "✅ mypy available" -ForegroundColor Green
} catch {
    Write-Host "⚠️  mypy not properly configured" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Development environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Blue
Write-Host "  • Run tests: pytest tests/unit" -ForegroundColor Gray
Write-Host "  • Format code: black ." -ForegroundColor Gray
Write-Host "  • Lint code: ruff check . --fix" -ForegroundColor Gray
Write-Host "  • Type check: mypy src_common/" -ForegroundColor Gray
Write-Host "  • Run all checks: pre-commit run --all-files" -ForegroundColor Gray