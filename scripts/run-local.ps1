# scripts/run-local.ps1
param(
    [ValidateSet('dev','test','prod')]
    [string]$Env='dev'
)

# Get paths
$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$Env"
$configDir = Join-Path $envRoot "config"

# Check if environment is initialized
if (!(Test-Path $configDir)) {
    Write-Error "❌ Environment '$Env' not initialized. Run: .\scripts\init-environments.ps1 -EnvName $Env"
    exit 1
}

# Load environment configuration
if (!(Test-Path (Join-Path $configDir ".env"))) {
    Write-Warning "⚠️  No .env file found. Using .env.template..."
    if (Test-Path (Join-Path $configDir ".env.template")) {
        Copy-Item (Join-Path $configDir ".env.template") (Join-Path $configDir ".env")
    } else {
        Write-Error "❌ No .env.template found either. Please run init-environments.ps1 first."
        exit 1
    }
}

# Read ports configuration
$portsPath = Join-Path $configDir "ports.json"
if (!(Test-Path $portsPath)) {
    Write-Error "❌ ports.json not found. Environment may not be properly initialized."
    exit 1
}

$ports = Get-Content $portsPath | ConvertFrom-Json

# Set environment variables
$env:APP_ENV = $Env
$env:PORT = $ports.http_port
$env:WEBSOCKET_PORT = $ports.websocket_port

# Load .env file into environment variables
Get-Content (Join-Path $configDir ".env") | ForEach-Object {
    if ($_ -and !$_.StartsWith('#') -and $_.Contains('=')) {
        $key, $value = $_.Split('=', 2)
        [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
    }
}

Write-Host "🚀 Starting TTRPG Center in $Env environment..." -ForegroundColor Green
Write-Host "📡 HTTP Port: $($ports.http_port)" -ForegroundColor Cyan
Write-Host "🔌 WebSocket Port: $($ports.websocket_port)" -ForegroundColor Cyan
Write-Host "📂 Environment Root: $envRoot" -ForegroundColor Cyan
Write-Host ""

# Change to project root and start the application
Set-Location $root

# Check if Python is available
try {
    $pythonVersion = python --version 2>$null
    Write-Host "🐍 Using: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "❌ Python not found. Please install Python 3.10+."
    exit 1
}

# Install requirements if they don't exist
if (!(Test-Path "venv") -and !(Get-Command "pip" -ErrorAction SilentlyContinue)) {
    Write-Host "📦 Installing requirements..." -ForegroundColor Yellow
    try {
        pip install -r requirements.txt
    } catch {
        Write-Warning "⚠️  Failed to install requirements. You may need to install them manually."
    }
}

# Start the application
Write-Host "🎯 Starting application..." -ForegroundColor Green
try {
    python -m uvicorn src_common.app:app --host 0.0.0.0 --port $ports.http_port --reload
} catch {
    Write-Error "❌ Failed to start application. Make sure src_common/app.py exists."
    exit 1
}