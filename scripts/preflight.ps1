# scripts/preflight.ps1
# Phase 0 preflight validation script for Windows
param(
    [switch]$Verbose,
    [string]$Environment = "dev",
    [switch]$SkipTests
)

Write-Host "🚀 Running Phase 0 preflight validation..." -ForegroundColor Green
Write-Host ""

$ErrorCount = 0

function Test-Component {
    param(
        [string]$Name,
        [scriptblock]$Test
    )
    
    Write-Host "🔍 Testing $Name..." -NoNewline
    
    try {
        $result = & $Test
        if ($result -eq $false) {
            Write-Host " ❌ FAILED" -ForegroundColor Red
            $script:ErrorCount++
        } else {
            Write-Host " ✅ PASSED" -ForegroundColor Green
        }
    } catch {
        Write-Host " ❌ ERROR: $_" -ForegroundColor Red
        $script:ErrorCount++
        if ($Verbose) {
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        }
    }
}

# Test 1: Environment initialization
Test-Component "Environment initialization" {
    & "$PSScriptRoot\init-environments.ps1" -EnvName $Environment | Out-Null
    $envRoot = Join-Path $PSScriptRoot "..\env\$Environment"
    
    $requiredDirs = @('code', 'config', 'data', 'logs')
    foreach ($dir in $requiredDirs) {
        $path = Join-Path $envRoot $dir
        if (!(Test-Path $path)) {
            throw "Missing directory: $dir"
        }
    }
    
    # Check config files
    $portsFile = Join-Path $envRoot "config\ports.json"
    if (!(Test-Path $portsFile)) {
        throw "Missing ports.json configuration"
    }
    
    $envFile = Join-Path $envRoot "config\.env.template"
    if (!(Test-Path $envFile)) {
        throw "Missing .env.template"
    }
    
    return $true
}

# Test 2: Python availability
Test-Component "Python availability" {
    try {
        $pythonVersion = python --version 2>$null
        if (!$pythonVersion) {
            throw "Python not found in PATH"
        }
        
        if ($Verbose) {
            Write-Host "    Found: $pythonVersion" -ForegroundColor Cyan
        }
        
        return $true
    } catch {
        throw "Python is not available"
    }
}

# Test 3: Required Python packages
Test-Component "Python package dependencies" {
    $requiredPackages = @('fastapi', 'uvicorn', 'pytest')
    
    foreach ($package in $requiredPackages) {
        try {
            python -c "import $package" 2>$null
            if ($LASTEXITCODE -ne 0) {
                if ($Verbose) {
                    Write-Host "    Installing $package..." -ForegroundColor Yellow
                }
                pip install $package --quiet
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to install $package"
                }
            }
        } catch {
            throw "Package $package is not available and could not be installed"
        }
    }
    
    return $true
}

# Test 4: Application health check
Test-Component "Application health check" {
    $env:APP_ENV = $Environment
    $env:PORT = "8000"
    $env:LOG_LEVEL = "ERROR"
    
    try {
        # Import and test core modules
        python -c @"
import sys
sys.path.insert(0, 'src_common')

from logging import jlog, setup_logging
from app import app
from mock_ingest import run_mock_sync

# Test logging
jlog('INFO', 'Preflight test', component='preflight')

# Test mock ingestion
result = run_mock_sync('preflight-test')
assert result['status'] == 'completed'
assert result['phases_completed'] == 3

print('✓ Core modules working')
"@
        
        if ($LASTEXITCODE -ne 0) {
            throw "Core module validation failed"
        }
        
        return $true
    } catch {
        throw "Application health check failed: $_"
    }
}

# Test 5: Port availability
Test-Component "Port availability" {
    $envRoot = Join-Path $PSScriptRoot "..\env\$Environment"
    $portsFile = Join-Path $envRoot "config\ports.json"
    
    if (Test-Path $portsFile) {
        $portsConfig = Get-Content $portsFile | ConvertFrom-Json
        $httpPort = $portsConfig.http_port
        $wsPort = $portsConfig.websocket_port
        
        # Test if ports are available
        try {
            $listener1 = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $httpPort)
            $listener1.Start()
            $listener1.Stop()
            
            $listener2 = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $wsPort)  
            $listener2.Start()
            $listener2.Stop()
            
            if ($Verbose) {
                Write-Host "    HTTP Port $httpPort available" -ForegroundColor Cyan
                Write-Host "    WebSocket Port $wsPort available" -ForegroundColor Cyan
            }
            
            return $true
        } catch {
            throw "Ports $httpPort or $wsPort are not available"
        }
    } else {
        throw "Ports configuration file not found"
    }
}

# Test 6: Unit tests (if not skipped)
if (!$SkipTests) {
    Test-Component "Unit tests" {
        $testResult = python -m pytest tests/unit -q --tb=no 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Unit tests failed"
        }
        return $true
    }
    
    Test-Component "Functional tests" {
        $testResult = python -m pytest tests/functional -q --tb=no 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Functional tests failed"
        }
        return $true
    }
}

# Test 7: Security basics
Test-Component "Security configuration" {
    # Check that .env files are not in git
    if (Test-Path ".git") {
        $gitignoreFile = ".gitignore"
        if (Test-Path $gitignoreFile) {
            $gitignoreContent = Get-Content $gitignoreFile -Raw
            if ($gitignoreContent -notmatch "\.env" -and $gitignoreContent -notmatch "env/\*/config/\.env") {
                throw ".env files are not properly gitignored"
            }
        } else {
            throw ".gitignore file is missing"
        }
    }
    
    # Check that no secrets are in environment variables for this test
    $suspiciousVars = @('SECRET_KEY', 'JWT_SECRET', 'API_KEY', 'PASSWORD')
    foreach ($var in $suspiciousVars) {
        if ([Environment]::GetEnvironmentVariable($var)) {
            Write-Host "    Warning: $var is set in environment" -ForegroundColor Yellow
        }
    }
    
    return $true
}

# Summary
Write-Host ""
if ($ErrorCount -eq 0) {
    Write-Host "✅ Preflight validation PASSED! All $($script:ErrorCount + 7) checks successful." -ForegroundColor Green
    Write-Host ""
    Write-Host "🎯 Ready for Phase 0 development!" -ForegroundColor Cyan
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Run: .\scripts\run-local.ps1 -Env $Environment" -ForegroundColor Gray
    Write-Host "  2. Open: http://localhost:$(if($Environment -eq 'dev'){8000} elseif($Environment -eq 'test'){8181} else {8282})/healthz" -ForegroundColor Gray
    Write-Host "  3. Test: curl http://localhost:$(if($Environment -eq 'dev'){8000} elseif($Environment -eq 'test'){8181} else {8282})/mock-ingest/test-job-001" -ForegroundColor Gray
    exit 0
} else {
    Write-Host "❌ Preflight validation FAILED! $ErrorCount error(s) found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please fix the issues above before proceeding." -ForegroundColor Yellow
    Write-Host "Run with -Verbose flag for more details." -ForegroundColor Gray
    exit 1
}