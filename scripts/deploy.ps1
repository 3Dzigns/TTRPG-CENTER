# deploy.ps1
# FR-006: Docker Stack Deployment Script
# Manages Docker Compose stack for TTRPG Center DEV environment

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("up", "down", "restart", "logs", "status", "ps")]
    [string]$Action = "up",
    
    [Parameter(Mandatory=$false)]
    [switch]$Build,
    
    [Parameter(Mandatory=$false)]
    [switch]$Purge,
    
    [Parameter(Mandatory=$false)]
    [switch]$Follow,
    
    [Parameter(Mandatory=$false)]
    [string]$Service = $null,
    
    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ComposeFile = "docker-compose.$Env.yml"
$EnvFile = "env/$Env/config/.env"

# Functions
function Write-Status {
    param([string]$Message, [string]$Level = "Info")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Level) {
        "Info" { Write-Host "[$timestamp] INFO: $Message" -ForegroundColor Green }
        "Warning" { Write-Host "[$timestamp] WARN: $Message" -ForegroundColor Yellow }
        "Error" { Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red }
        "Success" { Write-Host "[$timestamp] SUCCESS: $Message" -ForegroundColor Cyan }
    }
}

function Test-Prerequisites {
    # Check Docker
    try {
        docker info 2>$null | Out-Null
    }
    catch {
        throw "Docker is not running. Please start Docker Desktop."
    }
    
    # Check Docker Compose
    try {
        docker compose version 2>$null | Out-Null
    }
    catch {
        throw "Docker Compose is not available."
    }
    
    # Check compose file
    if (-not (Test-Path $ComposeFile)) {
        throw "Compose file not found: $ComposeFile"
    }
    
    # Check environment file
    if (-not (Test-Path $EnvFile)) {
        Write-Status "Environment file not found: $EnvFile" -Level "Warning"
        Write-Status "Using environment variables from system/shell" -Level "Warning"
    }
}

function Get-ComposeCommand {
    param([array]$ExtraArgs = @())
    
    $cmd = @("docker", "compose", "-f", $ComposeFile)
    
    if (Test-Path $EnvFile) {
        $cmd += "--env-file"
        $cmd += $EnvFile
    }
    
    $cmd += $ExtraArgs
    return $cmd
}

function Start-Stack {
    Write-Status "Starting Docker stack for environment: $Env"

    # Always perform some cleanup before starting to ensure fresh deployment
    Write-Status "Performing pre-deployment cleanup..."
    try {
        # Remove any stopped containers for this environment
        $containers = docker ps -a --filter "name=ttrpg-.*-$Env" --format "{{.Names}}" 2>$null
        if ($containers) {
            foreach ($container in $containers) {
                try {
                    docker rm -f $container 2>$null | Out-Null
                    Write-Status "  Removed old container: $container"
                } catch {
                    # Ignore errors
                }
            }
        }

        # Clean dangling images
        docker image prune -f 2>$null | Out-Null
        Write-Status "Pre-deployment cleanup completed"
    } catch {
        Write-Status "Pre-deployment cleanup had issues (non-critical)" -Level "Warning"
    }

    $composeArgs = @("up", "-d", "--force-recreate")

    if ($Build) {
        $composeArgs += "--build"
    }

    if ($Service) {
        $composeArgs += $Service
    }

    $cmd = Get-ComposeCommand -ExtraArgs $composeArgs

    if ($VerboseOutput) {
        Write-Status "Execute: $($cmd -join ' ')"
    }

    & $cmd[0] $cmd[1..($cmd.Length-1)]

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start stack (exit code: $LASTEXITCODE)"
    }

    Write-Status "Waiting for services to become healthy..."
    Start-Sleep -Seconds 10

    Show-Status
    Test-HealthEndpoint
}

function Stop-Stack {
    Write-Status "Stopping Docker stack for environment: $Env"

    $composeArgs = @("down", "--remove-orphans")

    if ($Purge) {
        Write-Status "Purging volumes and all related resources..." -Level "Warning"
        $composeArgs += "-v"
        $composeArgs += "--rmi"
        $composeArgs += "local"
    }

    if ($Service) {
        $composeArgs = @("stop")
        $composeArgs += $Service
    }

    $cmd = Get-ComposeCommand -ExtraArgs $composeArgs

    if ($VerboseOutput) {
        Write-Status "Execute: $($cmd -join ' ')"
    }

    & $cmd[0] $cmd[1..($cmd.Length-1)]

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop stack (exit code: $LASTEXITCODE)"
    }

    # Additional cleanup for better deployment reliability
    if (-not $Service) {
        Write-Status "Performing post-stop cleanup..."
        try {
            # Clean up any remaining containers for this environment
            $containers = docker ps -a --filter "name=ttrpg-.*-$Env" --format "{{.Names}}" 2>$null
            if ($containers) {
                foreach ($container in $containers) {
                    try {
                        docker rm -f $container 2>$null | Out-Null
                        Write-Status "  Cleaned remaining container: $container"
                    } catch {
                        # Ignore errors
                    }
                }
            }
            Write-Status "Post-stop cleanup completed"
        } catch {
            Write-Status "Post-stop cleanup had issues (non-critical)" -Level "Warning"
        }
    }

    Write-Status "Stack stopped successfully" -Level "Success"
}

function Restart-Stack {
    Write-Status "Restarting Docker stack for environment: $Env"
    
    Stop-Stack
    Start-Sleep -Seconds 5
    Start-Stack
}

function Show-Logs {
    Write-Status "Showing logs for environment: $Env"
    
    $composeArgs = @("logs")
    
    if ($Follow) {
        $composeArgs += "-f"
    }
    
    $composeArgs += "--tail=100"
    
    if ($Service) {
        $composeArgs += $Service
    }
    
    $cmd = Get-ComposeCommand -ExtraArgs $composeArgs
    
    & $cmd[0] $cmd[1..($cmd.Length-1)]
}

function Show-Status {
    Write-Status "Stack status for environment: $Env"
    
    $cmd = Get-ComposeCommand -ExtraArgs @("ps")
    
    & $cmd[0] $cmd[1..($cmd.Length-1)]
    
    # Show resource usage
    Write-Status "`nResource Usage:"
    try {
        $stats = docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.PIDs}}"
        Write-Host $stats
    }
    catch {
        Write-Status "Could not retrieve resource stats" -Level "Warning"
    }
}

function Show-ProcessList {
    Write-Status "Container processes for environment: $Env"
    
    $cmd = Get-ComposeCommand -ExtraArgs @("ps", "--format", "table")
    
    & $cmd[0] $cmd[1..($cmd.Length-1)]
}

function Test-HealthEndpoint {
    Write-Status "Testing health endpoint..."
    
    $maxAttempts = 30
    $attempt = 0
    $healthUrl = "http://localhost:8000/healthz"
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                $health = $response.Content | ConvertFrom-Json
                Write-Status "Health check passed - Status: $($health.status)" -Level "Success"
                
                if ($VerboseOutput -and $health.services) {
                    Write-Status "Service Status:"
                    foreach ($service in $health.services.PSObject.Properties) {
                        Write-Status "  $($service.Name): $($service.Value.status)"
                    }
                }
                return $true
            }
        }
        catch {
            # Ignore connection errors during startup
        }
        
        $attempt++
        Write-Status "Health check attempt $attempt/$maxAttempts..."
        Start-Sleep -Seconds 2
    }
    
    Write-Status "Health check failed after $maxAttempts attempts" -Level "Warning"
    Write-Status "Stack may still be starting up. Check logs with: .\scripts\deploy.ps1 -Action logs" -Level "Warning"
    return $false
}

function Show-ComposeInfo {
    Write-Status "Docker Compose Configuration:"
    Write-Status "  Compose File: $ComposeFile"
    Write-Status "  Environment File: $EnvFile"
    Write-Status "  Environment: $Env"
    Write-Status "  Project Root: $ProjectRoot"
    
    if (Test-Path $EnvFile) {
        Write-Status "  Environment Variables: Loaded from $EnvFile"
    } else {
        Write-Status "  Environment Variables: Using system defaults"
    }
}

# Main execution
try {
    Write-Status "TTRPG Center Docker Deployment Script"
    Write-Status "Action: $Action, Environment: $Env"
    
    # Change to project root
    Set-Location $ProjectRoot
    Write-Status "Working directory: $ProjectRoot"
    
    # Check prerequisites
    Test-Prerequisites
    
    if ($VerboseOutput) {
        Show-ComposeInfo
    }
    
    # Execute requested action
    switch ($Action) {
        "up" {
            Start-Stack
            Write-Status "Stack deployment completed successfully!" -Level "Success"
            Write-Status "Application available at: http://localhost:8000" -Level "Success"
            Write-Status "Health endpoint: http://localhost:8000/healthz" -Level "Success"
        }
        "down" {
            Stop-Stack
        }
        "restart" {
            Restart-Stack
            Write-Status "Stack restart completed successfully!" -Level "Success"
        }
        "logs" {
            Show-Logs
        }
        "status" {
            Show-Status
            Test-HealthEndpoint
        }
        "ps" {
            Show-ProcessList
        }
        default {
            throw "Unknown action: $Action"
        }
    }
}
catch {
    Write-Status "Deployment failed: $($_.Exception.Message)" -Level "Error"
    
    if ($Action -eq "up" -or $Action -eq "restart") {
        Write-Status "Troubleshooting tips:" -Level "Info"
        Write-Status "1. Check logs: .\scripts\deploy.ps1 -Action logs" -Level "Info"
        Write-Status "2. Check status: .\scripts\deploy.ps1 -Action status" -Level "Info"
        Write-Status "3. Restart stack: .\scripts\deploy.ps1 -Action restart" -Level "Info"
        Write-Status "4. Clean restart: .\scripts\deploy.ps1 -Action down -Purge; .\scripts\deploy.ps1 -Action up" -Level "Info"
    }
    
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}
