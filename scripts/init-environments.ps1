# scripts/init-environments.ps1
param(
    [ValidateSet('dev','test','prod')]
    [string]$EnvName='dev'
)

$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$EnvName"

$requiredDirs = 'code','config','data','logs'
foreach ($dir in $requiredDirs) {
    $target = Join-Path $envRoot $dir
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}

$ports = @{ dev = 8000; test = 8181; prod = 8282 }
$portValue = $ports[$EnvName]

$portsJson = @{
    http_port = $portValue
    name = $EnvName
    websocket_port = $portValue + 1000
} | ConvertTo-Json -Depth 10
$portsJson | Set-Content (Join-Path $envRoot 'config/ports.json') -Encoding UTF8

$cacheTtl = switch ($EnvName) {
    'dev' { 0 }
    'test' { 5 }
    'prod' { 300 }
}

$envTemplate = @"
# Environment: $EnvName
APP_ENV=$EnvName
PORT=$portValue
LOG_LEVEL=INFO
ARTIFACTS_PATH=./artifacts/$EnvName

# Vector store configuration (DEV defaults to Cassandra)
VECTOR_STORE_BACKEND=cassandra
CASSANDRA_CONTACT_POINTS=cassandra-dev
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ttrpg
CASSANDRA_TABLE=chunks
CASSANDRA_USERNAME=
CASSANDRA_PASSWORD=

# Legacy AstraDB configuration (optional)
ASTRA_DB_API_ENDPOINT=
ASTRA_DB_APPLICATION_TOKEN=
ASTRA_DB_ID=
ASTRA_DB_KEYSPACE=default_keyspace
ASTRA_DB_REGION=us-east-2

# AI Model API Keys (fill in actual values)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Security
SECRET_KEY=
JWT_SECRET=

# Cache settings
CACHE_TTL_SECONDS=$cacheTtl
"@
$envTemplate | Set-Content (Join-Path $envRoot 'config/.env.template') -Encoding UTF8

$envFilePath = Join-Path $envRoot 'config/.env'
if (-not (Test-Path $envFilePath)) {
    $envTemplate | Set-Content $envFilePath -Encoding UTF8
}

$loggingConfig = @{
    version = 1
    formatters = @{
        json = @{
            format = "%(asctime)s %(name)s %(levelname)s %(message)s"
            class = "pythonjsonlogger.jsonlogger.JsonFormatter"
        }
    }
    handlers = @{
        console = @{
            class = "logging.StreamHandler"
            formatter = "json"
            level = "INFO"
        }
        file = @{
            class = "logging.handlers.RotatingFileHandler"
            filename = "env/$EnvName/logs/app.log"
            formatter = "json"
            level = "INFO"
            maxBytes = 10485760
            backupCount = 5
        }
    }
    root = @{
        level = "INFO"
        handlers = @('console','file')
    }
} | ConvertTo-Json -Depth 10
$loggingConfig | Set-Content (Join-Path $envRoot 'config/logging.json') -Encoding UTF8

Write-Host "Initialized $EnvName environment at $envRoot" -ForegroundColor Green
Write-Host "Created directories: $($requiredDirs -join ', ')" -ForegroundColor Cyan
Write-Host "Ports JSON written with HTTP port $portValue" -ForegroundColor Cyan
Write-Host "Generated config/.env.template (and config/.env if missing)" -ForegroundColor Yellow

