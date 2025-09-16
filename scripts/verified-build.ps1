# verified-build.ps1
# Enhanced build script with source verification and validation
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",

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

function Test-SourceFiles {
    Write-Status "Verifying source files before build..."

    # Check critical files exist
    $criticalFiles = @(
        "src_common/admin_routes.py",
        "src_common/user_routes.py",
        "src_common/app.py",
        "requirements.txt",
        "services/app/Dockerfile"
    )

    foreach ($file in $criticalFiles) {
        if (-not (Test-Path $file)) {
            throw "Critical file missing: $file"
        }
        Write-Status "  ✓ Found: $file"
    }

    # Verify our specific fixes are in place
    Write-Status "Verifying routing fixes..."

    # Check admin_routes.py does NOT have root route
    $adminContent = Get-Content "src_common/admin_routes.py" -Raw
    if ($adminContent -match '@admin_router\.get\("/"') {
        throw "ERROR: admin_routes.py still contains root route - fixes not applied!"
    }
    Write-Status "  ✓ admin_routes.py: No root route (correct)"

    # Check user_routes.py HAS root route
    $userContent = Get-Content "src_common/user_routes.py" -Raw
    if ($userContent -notmatch '@user_router\.get\("/"') {
        throw "ERROR: user_routes.py missing root route - fixes not applied!"
    }
    Write-Status "  ✓ user_routes.py: Has root route (correct)"

    # Check JavaScript fixes are in place
    $templateContent = Get-Content "templates/admin_dashboard.html" -Raw
    if ($templateContent -match 'AdminUtils\.showToast') {
        Write-Status "  ⚠ templates/admin_dashboard.html: Still contains AdminUtils.showToast (may cause JS errors)" -Level "Warning"
    } else {
        Write-Status "  ✓ templates/admin_dashboard.html: AdminUtils.showToast fixed"
    }

    Write-Status "Source file verification completed successfully" -Level "Success"
}

function Add-BuildMarkers {
    Write-Status "Adding build verification markers..."

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $gitSha = git rev-parse --short HEAD 2>$null
    $gitBranch = git rev-parse --abbrev-ref HEAD 2>$null

    $buildInfo = @{
        timestamp = $timestamp
        git_sha = $gitSha
        git_branch = $gitBranch
        environment = $Env
        build_marker = "VERIFIED_BUILD_$timestamp"
    }

    # Create build info file
    $buildInfo | ConvertTo-Json | Out-File -FilePath "build_verification.json" -Encoding UTF8
    Write-Status "  ✓ Created build_verification.json"

    # Create simple marker file
    "VERIFIED_BUILD_$timestamp" | Out-File -FilePath "verified_build_marker.txt" -Encoding UTF8
    Write-Status "  ✓ Created verified_build_marker.txt"

    return $buildInfo
}

function Build-VerifiedImage {
    param([hashtable]$BuildInfo)

    Write-Status "Building verified image with markers..."

    $imageTag = "ttrpg/app:verified-$($BuildInfo.timestamp)"

    # Build the image
    $buildCmd = @(
        "docker", "build",
        "-f", "services/app/Dockerfile",
        "-t", $imageTag,
        "--build-arg", "BUILD_TIMESTAMP=$($BuildInfo.timestamp)",
        "--build-arg", "GIT_SHA=$($BuildInfo.git_sha)",
        "--build-arg", "GIT_BRANCH=$($BuildInfo.git_branch)",
        "--label", "build.verified=true",
        "--label", "build.timestamp=$($BuildInfo.timestamp)",
        "--label", "build.git_sha=$($BuildInfo.git_sha)",
        "."
    )

    if ($VerboseOutput) {
        Write-Status "Build command: $($buildCmd -join ' ')"
    }

    & $buildCmd[0] $buildCmd[1..($buildCmd.Length-1)]

    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }

    Write-Status "Successfully built verified image: $imageTag" -Level "Success"
    return $imageTag
}

function Test-BuiltImage {
    param([string]$ImageTag)

    Write-Status "Testing built image for verification markers..."

    # Test that our markers made it into the image
    try {
        $markerTest = docker run --rm $ImageTag cat /app/verified_build_marker.txt
        Write-Status "  ✓ Build marker found in image: $markerTest"

        $buildInfoTest = docker run --rm $ImageTag cat /app/build_verification.json | ConvertFrom-Json
        Write-Status "  ✓ Build info found in image: $($buildInfoTest.build_marker)"

        # Test that the source files have our fixes
        $adminTest = docker run --rm $ImageTag grep -c "Root route removed" /app/src_common/admin_routes.py
        if ($adminTest -eq "1") {
            Write-Status "  ✓ admin_routes.py fix verified in image"
        } else {
            throw "admin_routes.py fix NOT found in image!"
        }

        $userTest = docker run --rm $ImageTag grep -c '@user_router.get("/"' /app/src_common/user_routes.py
        if ($userTest -eq "1") {
            Write-Status "  ✓ user_routes.py fix verified in image"
        } else {
            throw "user_routes.py fix NOT found in image!"
        }

        Write-Status "Image verification completed successfully" -Level "Success"
        return $true

    } catch {
        Write-Status "Image verification failed: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Cleanup-BuildFiles {
    Write-Status "Cleaning up build verification files..."

    if (Test-Path "build_verification.json") {
        Remove-Item "build_verification.json"
        Write-Status "  ✓ Removed build_verification.json"
    }

    if (Test-Path "verified_build_marker.txt") {
        Remove-Item "verified_build_marker.txt"
        Write-Status "  ✓ Removed verified_build_marker.txt"
    }

    if (Test-Path "docker_test_marker.txt") {
        Remove-Item "docker_test_marker.txt"
        Write-Status "  ✓ Removed docker_test_marker.txt"
    }
}

# Main execution
try {
    Write-Status "TTRPG Center Verified Build Script" -Level "Success"
    Write-Status "Environment: $Env"

    # Step 1: Verify source files
    Test-SourceFiles

    # Step 2: Add build markers
    $buildInfo = Add-BuildMarkers

    # Step 3: Build image with verification
    $imageTag = Build-VerifiedImage -BuildInfo $buildInfo

    # Step 4: Test the built image
    $verified = Test-BuiltImage -ImageTag $imageTag

    if (-not $verified) {
        throw "Image verification failed - build may not have picked up source changes"
    }

    # Step 5: Tag for deployment
    Write-Status "Tagging verified image for deployment..."
    docker tag $imageTag "ttrpg/app:$Env"
    docker tag $imageTag "ttrpg/app:latest"

    Write-Status "Verified build completed successfully!" -Level "Success"
    Write-Status "Image ready for deployment: ttrpg/app:$Env" -Level "Success"

    # Output the verified image tag
    Write-Output $imageTag

} catch {
    Write-Status "Verified build failed: $($_.Exception.Message)" -Level "Error"
    exit 1
} finally {
    Cleanup-BuildFiles
}