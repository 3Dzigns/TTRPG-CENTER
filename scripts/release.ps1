# Release Automation Script for TTRPG Center CI/CD Pipeline
# Handles version bumping, tagging, building, and publishing immutable artifacts

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("patch", "minor", "major")]
    [string]$BumpType = "patch",
    
    [Parameter(Mandatory=$false)]
    [string]$Registry = "ghcr.io",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "ttrpg/app",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBump,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipPush,
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$VersionScript = Join-Path $PSScriptRoot "version.ps1"
$BuildScript = Join-Path $PSScriptRoot "build.ps1"

function Show-Help {
    Write-Host @"
Release Automation Script for TTRPG Center CI/CD Pipeline

USAGE:
    .\release.ps1 [OPTIONS]

OPTIONS:
    -BumpType     Version bump type: major, minor, patch (default: patch)
    -Registry     Container registry URL (default: ghcr.io)
    -ImageName    Image name without registry (default: ttrpg/app)
    -DryRun       Show what would be done without executing
    -SkipBump     Skip version bumping (use current version)
    -SkipBuild    Skip Docker image building
    -SkipPush     Skip pushing images to registry
    -Help         Show this help message

EXAMPLES:
    .\release.ps1                          # Standard patch release
    .\release.ps1 -BumpType minor          # Minor version release
    .\release.ps1 -DryRun                  # Preview release actions
    .\release.ps1 -SkipBump -SkipBuild     # Only push existing images

RELEASE PROCESS:
    1. Validate current state (git status, tests)
    2. Bump version (unless -SkipBump)
    3. Create git tag
    4. Build Docker image with metadata
    5. Tag image with multiple tags:
       - {registry}/{image}:{version}     (immutable)
       - {registry}/{image}:{gitSHA}      (content-addressed)
       - {registry}/{image}:latest        (floating)
    6. Push all tags to registry
    7. Display release summary

PREREQUISITES:
    - Clean git working directory
    - All tests passing
    - Docker running and authenticated to registry
    - Proper permissions for git tagging and registry push
"@
}

function Test-Prerequisites {
    Write-Host "Checking prerequisites..." -ForegroundColor Cyan
    
    # Check if git repository
    try {
        git rev-parse --git-dir 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Not in a git repository"
        }
    }
    catch {
        throw "Git repository validation failed: $_"
    }
    
    # Check git status
    $gitStatus = git status --porcelain 2>$null
    if ($gitStatus) {
        Write-Warning "Git working directory is not clean:"
        Write-Host $gitStatus -ForegroundColor Yellow
        
        if (-not $DryRun) {
            $confirm = Read-Host "Continue with uncommitted changes? (y/N)"
            if ($confirm -ne "y" -and $confirm -ne "Y") {
                throw "Release cancelled due to uncommitted changes"
            }
        }
    }
    
    # Check Docker
    try {
        docker version | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker is not running or not accessible"
        }
    }
    catch {
        throw "Docker validation failed: $_"
    }
    
    # Check version script
    if (-not (Test-Path $VersionScript)) {
        throw "Version script not found: $VersionScript"
    }
    
    # Check build script
    if (-not (Test-Path $BuildScript)) {
        throw "Build script not found: $BuildScript"
    }
    
    Write-Host "✓ Prerequisites validated" -ForegroundColor Green
}

function Get-ReleaseVersion {
    param([string]$BumpType, [switch]$SkipBump)
    
    if ($SkipBump) {
        $version = & $VersionScript get
        Write-Host "Using current version: $version" -ForegroundColor Cyan
    } else {
        Write-Host "Bumping $BumpType version..." -ForegroundColor Cyan
        
        if ($DryRun) {
            $currentVersion = & $VersionScript get
            Write-Host "DRY RUN: Would bump $BumpType version from $currentVersion" -ForegroundColor Yellow
            return $currentVersion
        } else {
            $version = & $VersionScript bump $BumpType
            if ($LASTEXITCODE -ne 0) {
                throw "Version bump failed"
            }
        }
    }
    
    return $version
}

function New-ReleaseTag {
    param([string]$Version)
    
    Write-Host "Creating git tag..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would create git tag v$Version" -ForegroundColor Yellow
        return
    }
    
    # Check if tag already exists
    $existingTag = git tag -l "v$Version" 2>$null
    if ($existingTag) {
        Write-Warning "Tag v$Version already exists, skipping tag creation"
        return
    }
    
    try {
        & $VersionScript tag
        if ($LASTEXITCODE -ne 0) {
            throw "Git tag creation failed"
        }
        Write-Host "✓ Created tag: v$Version" -ForegroundColor Green
    }
    catch {
        throw "Failed to create git tag: $_"
    }
}

function Invoke-ImageBuild {
    param([string]$Version, [string]$Registry, [string]$ImageName)
    
    if ($SkipBuild) {
        Write-Host "Skipping image build" -ForegroundColor Yellow
        return
    }
    
    Write-Host "Building Docker image..." -ForegroundColor Cyan
    
    $fullImageName = "$Registry/$ImageName"
    $gitSHA = git rev-parse --short=8 HEAD
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $buildVersion = "$Version+$gitSHA-$timestamp"
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would build image $fullImageName with version $buildVersion" -ForegroundColor Yellow
        return $gitSHA
    }
    
    try {
        # Build image with version metadata
        $buildArgs = @(
            "--build-arg", "VERSION=$buildVersion",
            "--build-arg", "GIT_SHA=$gitSHA",
            "--build-arg", "BUILD_TIMESTAMP=$timestamp",
            "--label", "org.opencontainers.image.version=$Version",
            "--label", "org.opencontainers.image.revision=$gitSHA",
            "--label", "org.opencontainers.image.created=$(Get-Date -Format 'o')",
            "--label", "org.opencontainers.image.source=https://github.com/OWNER/REPO",
            "--tag", "$fullImageName`:$Version",
            "--tag", "$fullImageName`:$gitSHA",
            "--tag", "$fullImageName`:latest",
            "-f", "services/app/Dockerfile",
            "."
        )
        
        Push-Location $ProjectRoot
        try {
            & docker build @buildArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Docker build failed"
            }
            
            Write-Host "✓ Built image with tags:" -ForegroundColor Green
            Write-Host "  - $fullImageName`:$Version (immutable)" -ForegroundColor Gray
            Write-Host "  - $fullImageName`:$gitSHA (content-addressed)" -ForegroundColor Gray
            Write-Host "  - $fullImageName`:latest (floating)" -ForegroundColor Gray
        }
        finally {
            Pop-Location
        }
    }
    catch {
        throw "Docker build failed: $_"
    }
    
    return $gitSHA
}

function Invoke-ImagePush {
    param([string]$Version, [string]$Registry, [string]$ImageName, [string]$GitSHA)
    
    if ($SkipPush) {
        Write-Host "Skipping image push" -ForegroundColor Yellow
        return
    }
    
    Write-Host "Pushing images to registry..." -ForegroundColor Cyan
    
    $fullImageName = "$Registry/$ImageName"
    $tags = @($Version, $GitSHA, "latest")
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would push the following tags:" -ForegroundColor Yellow
        foreach ($tag in $tags) {
            Write-Host "  - $fullImageName`:$tag" -ForegroundColor Gray
        }
        return
    }
    
    try {
        foreach ($tag in $tags) {
            Write-Host "Pushing $fullImageName`:$tag..." -ForegroundColor Gray
            docker push "$fullImageName`:$tag"
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to push $fullImageName`:$tag"
            }
        }
        
        Write-Host "✓ All images pushed successfully" -ForegroundColor Green
    }
    catch {
        throw "Image push failed: $_"
    }
}

function Show-ReleaseSummary {
    param([string]$Version, [string]$Registry, [string]$ImageName, [string]$GitSHA)
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "                        RELEASE SUMMARY" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Version:        $Version" -ForegroundColor White
    Write-Host "Git SHA:        $GitSHA" -ForegroundColor White
    Write-Host "Registry:       $Registry" -ForegroundColor White
    Write-Host "Image:          $ImageName" -ForegroundColor White
    Write-Host "Timestamp:      $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss UTC')" -ForegroundColor White
    Write-Host ""
    Write-Host "Published Images:" -ForegroundColor Yellow
    Write-Host "  • $Registry/$ImageName`:$Version" -ForegroundColor Gray
    Write-Host "  • $Registry/$ImageName`:$GitSHA" -ForegroundColor Gray
    Write-Host "  • $Registry/$ImageName`:latest" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "  1. Push git tag:    git push origin v$Version" -ForegroundColor Gray
    Write-Host "  2. Deploy to DEV:   .\deploy.ps1 -Env dev -Version $Version" -ForegroundColor Gray
    Write-Host "  3. Test deployment: .\test.ps1 -Env dev" -ForegroundColor Gray
    Write-Host "  4. Promote to TEST: Manual approval workflow" -ForegroundColor Gray
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
}

# Main execution
try {
    if ($Help) {
        Show-Help
        exit 0
    }
    
    Write-Host ""
    Write-Host "TTRPG Center Release Automation" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Yellow
        Write-Host ""
    }
    
    # Step 1: Validate prerequisites
    Test-Prerequisites
    
    # Step 2: Get/bump version
    $version = Get-ReleaseVersion -BumpType $BumpType -SkipBump:$SkipBump
    
    # Step 3: Create git tag
    New-ReleaseTag -Version $version
    
    # Step 4: Build image
    $gitSHA = Invoke-ImageBuild -Version $version -Registry $Registry -ImageName $ImageName
    
    # Step 5: Push images
    Invoke-ImagePush -Version $version -Registry $Registry -ImageName $ImageName -GitSHA $gitSHA
    
    # Step 6: Show summary
    if (-not $DryRun) {
        Show-ReleaseSummary -Version $version -Registry $Registry -ImageName $ImageName -GitSHA $gitSHA
    }
    
    Write-Host ""
    Write-Host "✅ Release completed successfully!" -ForegroundColor Green
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "Run without -DryRun to execute the release" -ForegroundColor Yellow
    }
}
catch {
    Write-Host ""
    Write-Host "❌ Release failed: $_" -ForegroundColor Red
    exit 1
}