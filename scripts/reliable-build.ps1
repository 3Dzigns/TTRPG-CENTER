# reliable-build.ps1
# Simple, reliable build script with source verification

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev"
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

function Test-SourceFiles {
    Write-Status "Verifying source files..."

    # Check admin_routes.py does NOT have root route (our fix)
    $adminContent = Get-Content "src_common/admin_routes.py" -Raw
    if ($adminContent -match '@admin_router\.get\("/"') {
        throw "ERROR: admin_routes.py still contains root route - fixes not applied!"
    }
    Write-Status "  ✓ admin_routes.py: No root route (CORRECT)"

    # Check user_routes.py HAS root route (our fix)
    $userContent = Get-Content "src_common/user_routes.py" -Raw
    if ($userContent -notmatch '@user_router\.get\("/"') {
        throw "ERROR: user_routes.py missing root route - fixes not applied!"
    }
    Write-Status "  ✓ user_routes.py: Has root route (CORRECT)"

    Write-Status "Source verification passed" -Level "Success"
}

try {
    Write-Status "TTRPG Center Reliable Build Script" -Level "Success"
    Write-Status "Environment: $Env"

    # Verify source files
    Test-SourceFiles

    # Get git info
    $gitSha = git rev-parse --short HEAD 2>$null
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $imageTag = "ttrpg/app:$Env-$gitSha-$timestamp"

    Write-Status "Building image: $imageTag"

    # Build with no cache to ensure fresh build
    docker build -f services/app/Dockerfile -t $imageTag --no-cache .

    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed"
    }

    # Tag for deployment
    docker tag $imageTag "ttrpg/app:$Env"
    docker tag $imageTag "ttrpg/app:latest"

    Write-Status "Build completed successfully!" -Level "Success"
    Write-Status "Image: $imageTag" -Level "Success"

    # Test the image quickly
    Write-Status "Testing built image..."
    $adminTest = docker run --rm $imageTag grep -c "Root route removed" /app/src_common/admin_routes.py 2>$null
    if ($adminTest -eq "1") {
        Write-Status "✓ Image contains correct admin_routes.py" -Level "Success"
    } else {
        Write-Status "⚠ Could not verify admin_routes.py in image" -Level "Warning"
    }

    Write-Output $imageTag

} catch {
    Write-Status "Build failed: $($_.Exception.Message)" -Level "Error"
    exit 1
}