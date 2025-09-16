# pipeline.ps1
# Single-command development pipeline: changes → commit → build → deploy → test
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",

    [Parameter(Mandatory=$false)]
    [string]$CommitMessage = "Pipeline update",

    [Parameter(Mandatory=$false)]
    [switch]$SkipCommit,

    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

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

function Stop-ExistingContainers {
    Write-Status "Stopping existing containers..."

    $containers = docker ps -q --filter "name=ttrpg-*"
    if ($containers) {
        docker stop $containers 2>$null
        docker rm $containers 2>$null
        Write-Status "  Stopped and removed existing containers"
    } else {
        Write-Status "  No existing containers to stop"
    }
}

function Test-Routes {
    param([string]$Port)

    Write-Status "Testing application routes on port $Port..."

    # Wait for app to start
    $maxWait = 30
    $waited = 0
    do {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$Port" -TimeoutSec 2 -ErrorAction SilentlyContinue -MaximumRedirection 0
            if ($response.StatusCode -eq 302) {
                break
            }
        } catch {
            # Continue waiting
        }
        Start-Sleep 1
        $waited++
    } while ($waited -lt $maxWait)

    if ($waited -ge $maxWait) {
        throw "Application failed to start within $maxWait seconds"
    }

    # Test root route redirects to /ui
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port" -MaximumRedirection 0 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 302) {
            Write-Status "  Root route correctly redirects" -Level "Success"
        } else {
            throw "Root route redirect failed"
        }
    } catch [System.Net.WebException] {
        if ($_.Exception.Response.StatusCode -eq 302) {
            Write-Status "  Root route correctly redirects" -Level "Success"
        } else {
            throw "Root route test failed"
        }
    }

    # Test /ui loads User interface
    try {
        $uiResponse = Invoke-WebRequest -Uri "http://localhost:$Port/ui" -TimeoutSec 5
        if ($uiResponse.Content -match "TTRPG CENTER") {
            Write-Status "  User UI loads correctly" -Level "Success"
        } else {
            throw "User UI content validation failed"
        }
    } catch {
        throw "User UI test failed"
    }

    # Test /admin loads Admin interface
    try {
        $adminResponse = Invoke-WebRequest -Uri "http://localhost:$Port/admin" -TimeoutSec 5
        if ($adminResponse.Content -match "Admin Console") {
            Write-Status "  Admin UI loads correctly" -Level "Success"
        } else {
            throw "Admin UI content validation failed"
        }
    } catch {
        throw "Admin UI test failed"
    }

    Write-Status "All route tests passed!" -Level "Success"
}

try {
    Write-Status "TTRPG Center Development Pipeline" -Level "Success"
    Write-Status "Environment: $Env"
    Write-Status "========================================="

    # Step 1: Check git status
    Write-Status "Step 1: Checking git status..."
    $gitStatus = git status --porcelain
    if ($gitStatus -and -not $SkipCommit) {
        Write-Status "  Changes detected, committing..."
        git add .
        git commit -m $CommitMessage
        Write-Status "  Changes committed" -Level "Success"
    } elseif ($SkipCommit) {
        Write-Status "  Skipping commit (--SkipCommit specified)" -Level "Success"
    } else {
        Write-Status "  No changes to commit" -Level "Success"
    }

    # Step 2: Stop existing containers
    Stop-ExistingContainers

    # Step 3: Build with verification
    Write-Status "Step 3: Building application..."
    $buildResult = & ".\scripts\build.ps1" -Env $Env
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE"
    }
    $imageTag = $buildResult | Select-Object -Last 1
    Write-Status "  Build completed: $imageTag" -Level "Success"

    # Step 4: Deploy container
    Write-Status "Step 4: Deploying container..."
    $portMap = @{
        "dev" = 8000
        "test" = 8181
        "prod" = 8282
    }
    $port = $portMap[$Env]

    $containerId = docker run -d -p "${port}:${port}" --name "ttrpg-$Env" "ttrpg/app:$Env"
    if ($LASTEXITCODE -ne 0) {
        throw "Container deployment failed"
    }
    Write-Status "  Container deployed: $containerId" -Level "Success"

    # Step 5: Test routes
    Write-Status "Step 5: Testing application routes..."
    Test-Routes -Port $port

    # Step 6: Cleanup old images
    Write-Status "Step 6: Cleaning up old images..."
    $oldImages = docker images --filter "dangling=true" -q
    if ($oldImages) {
        docker rmi $oldImages 2>$null
        Write-Status "  Removed dangling images" -Level "Success"
    } else {
        Write-Status "  No dangling images to remove" -Level "Success"
    }

    Write-Status "=========================================" -Level "Success"
    Write-Status "Pipeline completed successfully!" -Level "Success"
    Write-Status "Application: http://localhost:$port" -Level "Success"
    Write-Status "Admin Panel: http://localhost:$port/admin" -Level "Success"
    Write-Status "Container: ttrpg-$Env" -Level "Success"

} catch {
    Write-Status "Pipeline failed: $($_.Exception.Message)" -Level "Error"

    # Show container logs if deployment failed
    $container = docker ps -q --filter "name=ttrpg-$Env"
    if ($container) {
        Write-Status "Container logs for debugging:" -Level "Error"
        docker logs $container | Select-Object -Last 20
    }

    exit 1
}