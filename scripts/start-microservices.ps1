#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start all microservices for development
.DESCRIPTION
    This script starts all MVP v2 microservices in development mode
.PARAMETER Environment
    Target environment (dev, test, prod)
.PARAMETER Service
    Specific service to start (optional)
#>

param(
    [string]$Environment = "dev",
    [string]$Service = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting TTRPG Center Microservices (MVP v2)" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Blue

# Set environment variable
$env:TARGET_ENV = $Environment

# Port configuration
$portMap = @{
    "ingest" = @{ "dev" = 8003; "test" = 8184; "prod" = 8285 }
    "orchestrator" = @{ "dev" = 8004; "test" = 8185; "prod" = 8286 }
    "admin_api" = @{ "dev" = 8001; "test" = 8182; "prod" = 8283 }
    "user_api" = @{ "dev" = 8002; "test" = 8183; "prod" = 8284 }
}

function Start-MicroService {
    param(
        [string]$ServiceName,
        [int]$Port
    )

    Write-Host "🔧 Starting $ServiceName service on port $Port..." -ForegroundColor Yellow

    $modulePath = "services.$ServiceName.api:app"

    Start-Process -NoNewWindow -FilePath "python" -ArgumentList @(
        "-m", "uvicorn",
        $modulePath,
        "--host", "0.0.0.0",
        "--port", $Port,
        "--reload"
    )

    Write-Host "✅ $ServiceName service started on http://localhost:$Port" -ForegroundColor Green
}

# Start specific service or all services
if ($Service) {
    if ($portMap.ContainsKey($Service)) {
        $port = $portMap[$Service][$Environment]
        Start-MicroService -ServiceName $Service -Port $port
    } else {
        Write-Host "❌ Unknown service: $Service" -ForegroundColor Red
        Write-Host "Available services: $($portMap.Keys -join ', ')" -ForegroundColor Yellow
        exit 1
    }
} else {
    # Start all services
    foreach ($serviceName in $portMap.Keys) {
        $port = $portMap[$serviceName][$Environment]
        Start-MicroService -ServiceName $serviceName -Port $port
        Start-Sleep -Seconds 2  # Brief delay between service starts
    }

    Write-Host ""
    Write-Host "🎉 All microservices started!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Service URLs ($Environment environment):" -ForegroundColor Blue
    foreach ($serviceName in $portMap.Keys) {
        $port = $portMap[$serviceName][$Environment]
        Write-Host "  • $serviceName`: http://localhost:$port" -ForegroundColor Gray
        Write-Host "    - Health: http://localhost:$port/healthz" -ForegroundColor Gray
        Write-Host "    - Docs: http://localhost:$port/docs" -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "To stop services, use Ctrl+C or close terminal windows" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Microservices ready for MVP v2 development! 🎮" -ForegroundColor Green