#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Admin UI with Test Console
.DESCRIPTION
    Starts the TTRPG Center Admin UI with Test Console for external test execution.
    MVP v2 requirement implementation.
.PARAMETER Environment
    Target environment (dev, test, prod)
.PARAMETER Port
    Port to run the UI on (default: 3000)
#>

param(
    [string]$Environment = "dev",
    [int]$Port = 3000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting TTRPG Center Admin UI with Test Console" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Blue

# Navigate to admin-ui directory
$adminUiPath = Join-Path $PSScriptRoot ".." "web" "admin-ui"

if (-not (Test-Path $adminUiPath)) {
    Write-Host "❌ Admin UI directory not found: $adminUiPath" -ForegroundColor Red
    exit 1
}

Set-Location $adminUiPath

# Set environment variables
$env:NODE_ENV = if ($Environment -eq "prod") { "production" } else { "development" }
$env:VITE_ENVIRONMENT = $Environment

# Set Admin API URL based on environment
$adminApiUrls = @{
    "dev" = "http://localhost:8001"
    "test" = "http://localhost:8182"
    "prod" = "http://localhost:8283"
}
$env:ADMIN_API_BASE_URL = $adminApiUrls[$Environment]

Write-Host "Admin API URL: $($env:ADMIN_API_BASE_URL)" -ForegroundColor Blue

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Dependencies installed" -ForegroundColor Green
}

# Start development server
Write-Host "🔧 Starting Admin UI on port $Port..." -ForegroundColor Yellow

if ($Environment -eq "prod") {
    # Build and serve production version
    Write-Host "Building production version..." -ForegroundColor Yellow
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Build failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Starting production server..." -ForegroundColor Yellow
    npm run preview -- --port $Port
} else {
    # Start development server
    npm run dev -- --port $Port
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start Admin UI" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Admin UI with Test Console is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Blue
Write-Host "  • Admin UI: http://localhost:$Port" -ForegroundColor Gray
Write-Host "  • Test Console: http://localhost:$Port (main feature)" -ForegroundColor Gray
Write-Host "  • Admin API: $($env:ADMIN_API_BASE_URL)" -ForegroundColor Gray
Write-Host ""
Write-Host "Features:" -ForegroundColor Blue
Write-Host "  ✅ External test execution (Unit/Functional/Security/Regression/Perf)" -ForegroundColor Gray
Write-Host "  ✅ Real-time test output streaming" -ForegroundColor Gray
Write-Host "  ✅ Multi-environment targeting (dev/test/prod)" -ForegroundColor Gray
Write-Host "  ✅ Test result downloads" -ForegroundColor Gray
Write-Host "  ✅ Execution history tracking" -ForegroundColor Gray
Write-Host ""
Write-Host "MVP v2 Test Console ready for external test execution! 🧪" -ForegroundColor Green