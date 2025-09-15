# build.ps1
# FR-006: Docker Image Build Script
# Builds container images for TTRPG Center with proper tagging and metadata

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",
    
    [Parameter(Mandatory=$false)]
    [switch]$Clean,
    
    [Parameter(Mandatory=$false)]
    [switch]$NoCache,
    
    [Parameter(Mandatory=$false)]
    [string]$Tag = $null,
    
    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ImageName = "ttrpg/app"
$DockerfileDir = "services/app"

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

function Get-GitInfo {
    try {
        $gitSha = git rev-parse --short HEAD 2>$null
        $gitBranch = git rev-parse --abbrev-ref HEAD 2>$null
        $gitDirty = git diff --quiet 2>$null; $LASTEXITCODE -ne 0
        
        return @{
            Sha = if ($gitSha) { $gitSha } else { "unknown" }
            Branch = if ($gitBranch) { $gitBranch } else { "unknown" }
            Dirty = $gitDirty
        }
    }
    catch {
        return @{
            Sha = "unknown"
            Branch = "unknown"
            Dirty = $false
        }
    }
}

function Test-DockerRunning {
    try {
        docker info 2>$null | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Build-Image {
    param(
        [string]$ImageTag,
        [hashtable]$BuildArgs,
        [bool]$UseCache = $true
    )
    
    Write-Status "Building image: $ImageTag"
    
    # Build Docker build command
    $buildCmd = @("docker", "build")
    
    if (-not $UseCache) {
        $buildCmd += "--no-cache"
    }
    
    # Add build args
    foreach ($key in $BuildArgs.Keys) {
        $buildCmd += "--build-arg"
        $buildCmd += "$key=$($BuildArgs[$key])"
    }
    
    # Add labels
    $buildCmd += "--label"
    $buildCmd += "org.opencontainers.image.title=TTRPG Center App"
    $buildCmd += "--label"
    $buildCmd += "org.opencontainers.image.description=AI-powered TTRPG content management platform"
    $buildCmd += "--label"
    $buildCmd += "org.opencontainers.image.version=$($BuildArgs.VERSION)"
    $buildCmd += "--label"
    $buildCmd += "org.opencontainers.image.revision=$($BuildArgs.GIT_SHA)"
    $buildCmd += "--label"
    $buildCmd += "org.opencontainers.image.created=$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')"
    
    # Add tag and context
    $buildCmd += "-t"
    $buildCmd += $ImageTag
    $buildCmd += "-f"
    $buildCmd += "$DockerfileDir/Dockerfile"
    $buildCmd += "."
    
    # Execute build
    if ($Verbose) {
        Write-Status "Build command: $($buildCmd -join ' ')"
    }
    
    & $buildCmd[0] $buildCmd[1..($buildCmd.Length-1)]
    
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }
    
    Write-Status "Successfully built image: $ImageTag" -Level "Success"
}

function Clean-Images {
    Write-Status "Cleaning up old images..."
    
    try {
        # Remove dangling images
        $danglingImages = docker images -f "dangling=true" -q
        if ($danglingImages) {
            docker rmi $danglingImages 2>$null
        }
        
        # Remove old TTRPG images (keep last 3)
        $oldImages = docker images "$ImageName" --format "{{.Repository}}:{{.Tag}}" | Select-Object -Skip 3
        if ($oldImages) {
            docker rmi $oldImages 2>$null
        }
        
        Write-Status "Image cleanup completed"
    }
    catch {
        Write-Status "Image cleanup encountered issues: $($_.Exception.Message)" -Level "Warning"
    }
}

function Test-Image {
    param([string]$ImageTag)
    
    Write-Status "Testing built image: $ImageTag"
    
    try {
        # Test that image exists
        $imageExists = docker images $ImageTag --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -eq $ImageTag }
        if (-not $imageExists) {
            throw "Image not found: $ImageTag"
        }
        
        # Test that image can start
        Write-Status "Testing image startup..."
        $containerId = docker run -d --rm $ImageTag python --version
        $exitCode = docker wait $containerId
        
        if ($exitCode -ne "0") {
            throw "Image test failed with exit code $exitCode"
        }
        
        Write-Status "Image test passed" -Level "Success"
        return $true
    }
    catch {
        Write-Status "Image test failed: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

# Main execution
try {
    Write-Status "TTRPG Center Docker Build Script"
    Write-Status "Environment: $Env"
    
    # Change to project root
    Set-Location $ProjectRoot
    Write-Status "Working directory: $ProjectRoot"
    
    # Check prerequisites
    if (-not (Test-DockerRunning)) {
        throw "Docker is not running. Please start Docker Desktop."
    }
    
    # Get git information
    $gitInfo = Get-GitInfo
    Write-Status "Git info - Branch: $($gitInfo.Branch), SHA: $($gitInfo.Sha), Dirty: $($gitInfo.Dirty)"
    
    # Determine image tag
    if ($Tag) {
        $imageTag = "${ImageName}:${Tag}"
    } else {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $imageTag = "${ImageName}:${Env}-${gitInfo.Sha}-${timestamp}"
    }
    
    # Additional tags
    $envTag = "${ImageName}:${Env}"
    $latestTag = "${ImageName}:latest"
    
    Write-Status "Image tags: $imageTag, $envTag"
    
    # Prepare build arguments
    $buildArgs = @{
        "APP_ENV" = $Env
        "GIT_SHA" = $gitInfo.Sha
        "GIT_BRANCH" = $gitInfo.Branch
        "BUILD_DATE" = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
        "VERSION" = "$Env-$($gitInfo.Sha)"
    }
    
    # Clean old images if requested
    if ($Clean) {
        Clean-Images
    }
    
    # Build main image
    Build-Image -ImageTag $imageTag -BuildArgs $buildArgs -UseCache (-not $NoCache)
    
    # Tag with environment and latest
    Write-Status "Tagging image with additional tags..."
    docker tag $imageTag $envTag
    if ($Env -eq "dev") {
        docker tag $imageTag $latestTag
    }
    
    # Test the built image
    if (-not (Test-Image -ImageTag $imageTag)) {
        throw "Image testing failed"
    }
    
    # Display build summary
    Write-Status "Build Summary:" -Level "Success"
    Write-Status "  Image: $imageTag" -Level "Success"
    Write-Status "  Environment: $Env" -Level "Success"
    Write-Status "  Git SHA: $($gitInfo.Sha)" -Level "Success"
    Write-Status "  Git Branch: $($gitInfo.Branch)" -Level "Success"
    Write-Status "  Build Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Level "Success"
    
    # Show image size
    $imageInfo = docker images $imageTag --format "{{.Size}}"
    Write-Status "  Image Size: $imageInfo" -Level "Success"

    # Comprehensive cleanup to save space and ensure fresh deployments
    Write-Status "Performing comprehensive cleanup..." -Level "Info"
    try {
        # Clean Docker images (more aggressive)
        Write-Status "  Pruning dangling images..." -Level "Info"
        docker image prune -f | Out-Null

        # Clean build cache
        Write-Status "  Cleaning Docker build cache..." -Level "Info"
        docker builder prune -f | Out-Null

        # Clean old TTRPG images (keep only last 2 versions)
        Write-Status "  Removing old TTRPG images..." -Level "Info"
        $oldImages = docker images "$ImageName" --format "{{.Repository}}:{{.Tag}}" | Select-Object -Skip 2
        if ($oldImages) {
            foreach ($image in $oldImages) {
                try {
                    docker rmi $image 2>$null
                    Write-Status "    Removed: $image" -Level "Info"
                } catch {
                    # Ignore errors for images in use
                }
            }
        }

        # Clean artifacts directory for current environment
        $artifactsPath = "artifacts/$Env"
        if (Test-Path $artifactsPath) {
            Write-Status "  Cleaning artifacts directory: $artifactsPath..." -Level "Info"
            $oldArtifacts = Get-ChildItem $artifactsPath -Directory | Sort-Object LastWriteTime -Descending | Select-Object -Skip 5
            foreach ($artifact in $oldArtifacts) {
                try {
                    Remove-Item $artifact.FullName -Recurse -Force
                    Write-Status "    Removed artifact: $($artifact.Name)" -Level "Info"
                } catch {
                    Write-Status "    Failed to remove artifact: $($artifact.Name)" -Level "Warning"
                }
            }
        }

        Write-Status "Comprehensive cleanup completed" -Level "Success"
    }
    catch {
        Write-Status "Cleanup failed (non-critical): $($_.Exception.Message)" -Level "Warning"
    }

    Write-Status "Build completed successfully!" -Level "Success"
    
    # Output final image tag for use in other scripts
    Write-Output $imageTag
}
catch {
    Write-Status "Build failed: $($_.Exception.Message)" -Level "Error"
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}