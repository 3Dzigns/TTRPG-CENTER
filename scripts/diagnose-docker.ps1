# diagnose-docker.ps1
# Quick diagnostic script to understand Docker build context issues

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Level = "Info")
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Level) {
        "Info" { Write-Host "[$timestamp] $Message" -ForegroundColor Green }
        "Warning" { Write-Host "[$timestamp] WARN: $Message" -ForegroundColor Yellow }
        "Error" { Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red }
        "Success" { Write-Host "[$timestamp] SUCCESS: $Message" -ForegroundColor Cyan }
    }
}

Write-Status "Docker Build Context Diagnostic"
Write-Status "=============================="

# Check current location
Write-Status "Current directory: $(Get-Location)"

# Check git state
Write-Status "Git status:"
git status --porcelain

Write-Status "Git HEAD: $(git rev-parse --short HEAD)"
Write-Status "Git branch: $(git rev-parse --abbrev-ref HEAD)"

# Create test marker
$testMarker = "DIAGNOSTIC_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$testMarker | Out-File -FilePath "diagnostic_marker.txt" -Encoding UTF8
Write-Status "Created diagnostic marker: $testMarker"

# Check critical source files
Write-Status "Checking critical source files:"

# Check admin_routes.py
$adminContent = Get-Content "src_common/admin_routes.py" -Raw
if ($adminContent -match '@admin_router\.get\("/"') {
    Write-Status "  admin_routes.py: Contains root route (OLD VERSION)" -Level "Error"
} else {
    Write-Status "  admin_routes.py: No root route (CORRECT)" -Level "Success"
}

# Check user_routes.py
$userContent = Get-Content "src_common/user_routes.py" -Raw
if ($userContent -match '@user_router\.get\("/"') {
    Write-Status "  user_routes.py: Has root route (CORRECT)" -Level "Success"
} else {
    Write-Status "  user_routes.py: Missing root route (OLD VERSION)" -Level "Error"
}

# Test simple Docker operation
Write-Status "Testing Docker build context..."
try {
    # Create minimal Dockerfile for testing
    @"
FROM alpine:latest
COPY diagnostic_marker.txt /test_marker.txt
COPY src_common/admin_routes.py /test_admin.py
RUN echo "Build context test successful"
"@ | Out-File -FilePath "Dockerfile.test" -Encoding UTF8

    Write-Status "Building test image..."
    docker build -f Dockerfile.test -t context-test . --no-cache

    if ($LASTEXITCODE -eq 0) {
        Write-Status "Docker build succeeded" -Level "Success"

        # Test what made it into the image
        $markerInImage = docker run --rm context-test cat /test_marker.txt
        Write-Status "Marker in image: $markerInImage"

        $adminInImage = docker run --rm context-test grep -c "Root route removed" /test_admin.py 2>$null
        if ($adminInImage -eq "1") {
            Write-Status "admin_routes.py in image: CORRECT VERSION" -Level "Success"
        } else {
            Write-Status "admin_routes.py in image: OLD VERSION" -Level "Error"
        }

        # Clean up test image
        docker rmi context-test 2>$null
    } else {
        Write-Status "Docker build failed" -Level "Error"
    }

    # Clean up test files
    Remove-Item "Dockerfile.test" -ErrorAction SilentlyContinue
    Remove-Item "diagnostic_marker.txt" -ErrorAction SilentlyContinue

} catch {
    Write-Status "Docker test failed: $($_.Exception.Message)" -Level "Error"
}

Write-Status "Diagnostic complete"