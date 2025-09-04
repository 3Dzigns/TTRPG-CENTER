# scripts/init-environments.ps1
param(
    [ValidateSet('dev','test','prod')]
    [string]$EnvName='dev'
)

# Get script root directory
$root = Join-Path $PSScriptRoot ".."
$envRoot = Join-Path $root "env/$EnvName"

# Create directory structure if it doesn't exist
$paths = @('code','config','data','logs') | ForEach-Object { Join-Path $envRoot $_ }
$paths | ForEach-Object { 
    if (!(Test-Path $_)) { 
        New-Item -ItemType Directory -Path $_ -Force | Out-Null 
    } 
}

# Port assignments
$ports = @{ 
    dev = 8000
    test = 8181 
    prod = 8282 
}

# Create ports.json configuration
$portConfig = @{
    http_port = $ports[$EnvName]
    name = $EnvName
    websocket_port = $ports[$EnvName] + 1000  # WebSocket on +1000
} | ConvertTo-Json -Depth 10

$portConfig | Set-Content (Join-Path $envRoot 'config/ports.json') -Encoding UTF8

# Create environment-specific .env template (not the real .env with secrets)
$envTemplate = @"
# Environment: $EnvName
APP_ENV=$EnvName
PORT=$($ports[$EnvName])
LOG_LEVEL=INFO
ARTIFACTS_PATH=./artifacts/$EnvName

# Database Configuration (fill in actual values)
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
CACHE_TTL_SECONDS=$( if ($EnvName -eq 'dev') { 0 } elseif ($EnvName -eq 'test') { 5 } else { 300 } )
"@

$envTemplate | Set-Content (Join-Path $envRoot 'config/.env.template') -Encoding UTF8

# Create logging configuration
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
            maxBytes = 10485760  # 10MB
            backupCount = 5
        }
    }
    root = @{
        level = "INFO"
        handlers = @("console", "file")
    }
} | ConvertTo-Json -Depth 10

$loggingConfig | Set-Content (Join-Path $envRoot 'config/logging.json') -Encoding UTF8

Write-Host "✅ Initialized $EnvName environment at $envRoot" -ForegroundColor Green
Write-Host "📁 Created directories: code, config, data, logs" -ForegroundColor Cyan
Write-Host "🔧 Port configured: $($ports[$EnvName])" -ForegroundColor Cyan
Write-Host "⚠️  Remember to copy .env.template to .env and fill in actual secrets" -ForegroundColor Yellow