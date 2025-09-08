# scripts/run-local.ps1
param(
    [ValidateSet('dev','test','prod')]
    [string]$Env='dev',
    [switch]$Background
)

# Get paths
$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$Env"
$configDir = Join-Path $envRoot "config"

# Check if environment is initialized
if (!(Test-Path $configDir)) {
    Write-Error "Environment '$Env' not initialized. Run: .\scripts\init-environments.ps1 -EnvName $Env"
    exit 1
}

# Ensure .env exists
if (!(Test-Path (Join-Path $configDir ".env"))) {
    Write-Warning "No .env file found. Using .env.template..."
    if (Test-Path (Join-Path $configDir ".env.template")) {
        Copy-Item (Join-Path $configDir ".env.template") (Join-Path $configDir ".env")
    } else {
        Write-Error "No .env.template found either. Please run init-environments.ps1 first."
        exit 1
    }
}

# Read ports configuration
$portsPath = Join-Path $configDir "ports.json"
if (!(Test-Path $portsPath)) {
    Write-Error "ports.json not found. Environment may not be properly initialized."
    exit 1
}
$ports = Get-Content $portsPath | ConvertFrom-Json

# Set environment variables
$env:APP_ENV = $Env
$env:PORT = $ports.http_port
$env:WEBSOCKET_PORT = $ports.websocket_port

# Load .env file into process env
Get-Content (Join-Path $configDir ".env") | ForEach-Object {
    if ($_ -and !$_.StartsWith('#') -and $_.Contains('=')) {
        $key, $value = $_.Split('=', 2)
        [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
    }
}

Write-Host "Starting TTRPG Center in $Env environment..." -ForegroundColor Green
Write-Host ("HTTP Port: {0}" -f $ports.http_port) -ForegroundColor Cyan
Write-Host ("WebSocket Port: {0}" -f $ports.websocket_port) -ForegroundColor Cyan
Write-Host ("Environment Root: {0}" -f $envRoot) -ForegroundColor Cyan
Write-Host ""

# Change to environment-specific code directory
$codeDir = Join-Path $envRoot "code"
Set-Location $codeDir
Write-Host "Working directory: $codeDir" -ForegroundColor Cyan

# Check Python availability
try {
    $pythonVersion = python --version 2>$null
    Write-Host "Using: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "Python not found. Please install Python 3.10+."
    exit 1
}

# Prefer venv Python if available
$pythonExe = Join-Path $root ".venv/Scripts/python.exe"
if (!(Test-Path $pythonExe)) { $pythonExe = "python" }

# Helper to free a TCP port
function Stop-PortListeners {
    param([int]$Port)
    try {
        $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -Expand OwningProcess -Unique
        foreach ($id in $pids) {
            if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
}

# Best-effort dependency ensure
Write-Host "Checking Python dependencies..." -ForegroundColor Yellow
try { pip --version 1>$null 2>$null } catch { }
try { pip install -r requirements.txt 1>$null } catch { Write-Host "pip install skipped/failed (continuing)" -ForegroundColor DarkYellow }

# Start the correct app per environment
if ($Env -eq 'dev') {
    # Ensure self-signed certs exist for Dev
    Write-Host "Ensuring Dev TLS certs present..." -ForegroundColor Yellow
    try { python scripts/gen-dev-cert.py 1>$null } catch { Write-Host "Cert generation failed (continuing)" -ForegroundColor DarkYellow }

    # Free port 8000 (Dev contract)
    Stop-PortListeners -Port $ports.http_port

    Write-Host "Starting Consolidated TTRPG Center on port $($ports.http_port)..." -ForegroundColor Green
    try {
        $args = @('-m','uvicorn','app_main:app','--host','0.0.0.0','--port',"$($ports.http_port)",'--ssl-keyfile','certs/dev/key.pem','--ssl-certfile','certs/dev/cert.pem','--reload')
        if ($Background) {
            $p = Start-Process -FilePath $pythonExe -ArgumentList $args -PassThru -WindowStyle Hidden
            Write-Host ("Dev UI started in background. PID: {0}" -f $p.Id) -ForegroundColor Green
        } else {
            & $pythonExe @args
        }
    } catch {
        Write-Error "Failed to start Consolidated TTRPG Center with TLS."
        exit 1
    }
} elseif ($Env -eq 'test') {
    # Free port 8181 (Test contract)
    Stop-PortListeners -Port $ports.http_port
    Write-Host "Starting API on port $($ports.http_port) for test..." -ForegroundColor Green
    try {
        $args = @('-m','uvicorn','src_common.app:app','--host','0.0.0.0','--port',"$($ports.http_port)",'--reload')
        if ($Background) {
            $p = Start-Process -FilePath $pythonExe -ArgumentList $args -PassThru -WindowStyle Hidden
            Write-Host ("Test API started in background. PID: {0}" -f $p.Id) -ForegroundColor Green
        } else {
            & $pythonExe @args
        }
    } catch {
        Write-Error "Failed to start API for test environment."
        exit 1
    }
} else {
    # prod fallback
    Stop-PortListeners -Port $ports.http_port
    Write-Host "Starting API (prod mode) on port $($ports.http_port)..." -ForegroundColor Green
    try {
        $args = @('-m','uvicorn','src_common.app:app','--host','0.0.0.0','--port',"$($ports.http_port)")
        if ($Background) {
            $p = Start-Process -FilePath $pythonExe -ArgumentList $args -PassThru -WindowStyle Hidden
            Write-Host ("Prod API started in background. PID: {0}" -f $p.Id) -ForegroundColor Green
        } else {
            & $pythonExe @args
        }
    } catch {
        Write-Error "Failed to start API in prod mode."
        exit 1
    }
}
