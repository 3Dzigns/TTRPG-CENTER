# scripts/init-environments.ps1
param(
    [ValidateSet('dev','test','prod')]
    [string]$EnvName = 'dev'
)

$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$EnvName"

$requiredDirs = @('code','config','data','logs','artifacts','cache','uploads','ssl')
foreach ($dir in $requiredDirs) {
    $target = Join-Path $envRoot $dir
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}

$basePorts = @{ dev = 8000; test = 8181; prod = 8282 }
$portValue = $basePorts[$EnvName]
$servicePorts = [ordered]@{
    main_app_port = $portValue
    admin_api_port = $portValue + 1
    user_api_port = $portValue + 2
    ingest_service_port = $portValue + 3
    orchestrator_service_port = $portValue + 4
}
$testRunnerPort = switch ($EnvName) {
    'dev' { 8095 }
    'test' { 8195 }
    'prod' { 8295 }
}

$portsJson = [ordered]@{
    name = $EnvName
    base_http_port = $portValue
    websocket_port = $portValue + 1000
    main_app_port = $servicePorts.main_app_port
    admin_api_port = $servicePorts.admin_api_port
    user_api_port = $servicePorts.user_api_port
    ingest_service_port = $servicePorts.ingest_service_port
    orchestrator_service_port = $servicePorts.orchestrator_service_port
    test_runner_port = $testRunnerPort
} | ConvertTo-Json -Depth 4
$portsJson | Set-Content (Join-Path $envRoot 'config/ports.json') -Encoding UTF8

$cacheTtl = switch ($EnvName) {
    'dev' { 0 }
    'test' { 5 }
    'prod' { 300 }
}

$envTemplate = @"
# Environment: $EnvName
TARGET_ENV=$EnvName
APP_ENV=$EnvName
PORT=$portValue
MAIN_APP_PORT=$($servicePorts.main_app_port)
ADMIN_API_PORT=$($servicePorts.admin_api_port)
USER_API_PORT=$($servicePorts.user_api_port)
INGEST_SERVICE_PORT=$($servicePorts.ingest_service_port)
ORCHESTRATOR_SERVICE_PORT=$($servicePorts.orchestrator_service_port)
TEST_RUNNER_PORT=$testRunnerPort
LOG_LEVEL=INFO
CODE_ROOT=./code
DATA_PATH=./data
LOGS_PATH=./logs
ARTIFACTS_PATH=./artifacts
UPLOADS_PATH=./uploads
CACHE_PATH=./cache
SSL_PATH=./ssl

# Vector store configuration (DEV defaults to Cassandra)
VECTOR_STORE_BACKEND=cassandra
CASSANDRA_CONTACT_POINTS=cassandra-$EnvName
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ttrpg_$EnvName
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
JWT_SECRET_KEY=
ALLOWED_SOURCES=

# Observability
OTLP_ENDPOINT=

# Cache settings
CACHE_TTL_SECONDS=$cacheTtl
"@
$envTemplatePath = Join-Path $envRoot 'config/.env.template'
$envTemplate | Set-Content $envTemplatePath -Encoding UTF8

$envFilePath = Join-Path $envRoot 'config/.env'
if (-not (Test-Path $envFilePath)) {
    Copy-Item $envTemplatePath $envFilePath
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
Write-Host "Ensured directories: $($requiredDirs -join ', ')" -ForegroundColor Cyan
Write-Host "Ports JSON written with base port $portValue" -ForegroundColor Cyan
Write-Host "Generated config/.env.template (and config/.env if missing)" -ForegroundColor Yellow
