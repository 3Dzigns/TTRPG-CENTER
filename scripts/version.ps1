# Version Management Utilities for TTRPG Center
# Supports semantic versioning with build metadata for CI/CD pipeline

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("get", "bump", "validate", "tag")]
    [string]$Action = "get",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("major", "minor", "patch")]
    [string]$BumpType = "patch",
    
    [Parameter(Mandatory=$false)]
    [string]$Version = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$BuildMetadata,
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Script configuration
$ErrorActionPreference = "Stop"
$VersionFile = Join-Path $PSScriptRoot "..\VERSION"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

function Show-Help {
    Write-Host @"
Version Management Utilities for TTRPG Center CI/CD Pipeline

USAGE:
    .\version.ps1 [ACTION] [OPTIONS]

ACTIONS:
    get          Get current version (default)
    bump         Increment version number
    validate     Validate version format
    tag          Create git tag with current version

OPTIONS:
    -BumpType    Specify bump type: major, minor, patch (default: patch)
    -Version     Specify exact version for validation
    -BuildMetadata Include build metadata (+gitSHA-timestamp)
    -Help        Show this help message

EXAMPLES:
    .\version.ps1                          # Get current version
    .\version.ps1 get -BuildMetadata       # Get version with build metadata
    .\version.ps1 bump minor               # Bump minor version
    .\version.ps1 validate -Version "1.2.3" # Validate version format
    .\version.ps1 tag                      # Create git tag

VERSION FORMAT:
    Base: X.Y.Z (semantic versioning)
    With metadata: X.Y.Z+gitSHA-timestamp
    
BUILD METADATA FORMAT:
    +{8-char-git-SHA}-{ISO8601-timestamp}
    Example: +a1b2c3d4-20250912T143052Z
"@
}

function Get-GitCommitSHA {
    try {
        $sha = git rev-parse --short=8 HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $sha) {
            return $sha.Trim()
        }
    }
    catch {
        # Ignore git errors
    }
    return "unknown"
}

function Get-BuildTimestamp {
    return (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
}

function Get-CurrentVersion {
    param([switch]$IncludeBuildMetadata)
    
    if (-not (Test-Path $VersionFile)) {
        throw "VERSION file not found at: $VersionFile"
    }
    
    $version = (Get-Content $VersionFile -Raw).Trim()
    
    if ($IncludeBuildMetadata) {
        $gitSHA = Get-GitCommitSHA
        $timestamp = Get-BuildTimestamp
        $version = "$version+$gitSHA-$timestamp"
    }
    
    return $version
}

function Test-VersionFormat {
    param([string]$Version)
    
    # Semantic versioning regex: X.Y.Z where X, Y, Z are non-negative integers
    $semverPattern = '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$'
    
    if ($Version -match $semverPattern) {
        return $true
    }
    
    return $false
}

function Set-Version {
    param([string]$NewVersion)
    
    if (-not (Test-VersionFormat $NewVersion)) {
        throw "Invalid version format: $NewVersion. Must be X.Y.Z where X, Y, Z are non-negative integers."
    }
    
    Set-Content -Path $VersionFile -Value $NewVersion -NoNewline
    Write-Host "Version updated to: $NewVersion" -ForegroundColor Green
}

function Invoke-BumpVersion {
    param([string]$BumpType)
    
    $currentVersion = Get-CurrentVersion
    
    if (-not (Test-VersionFormat $currentVersion)) {
        throw "Current version in VERSION file is invalid: $currentVersion"
    }
    
    $versionParts = $currentVersion -split '\.'
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    $patch = [int]$versionParts[2]
    
    switch ($BumpType) {
        "major" {
            $major++
            $minor = 0
            $patch = 0
        }
        "minor" {
            $minor++
            $patch = 0
        }
        "patch" {
            $patch++
        }
        default {
            throw "Invalid bump type: $BumpType. Must be major, minor, or patch."
        }
    }
    
    $newVersion = "$major.$minor.$patch"
    Set-Version $newVersion
    
    return $newVersion
}

function New-GitTag {
    param([string]$Version)
    
    try {
        # Check if we're in a git repository
        git rev-parse --git-dir 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Not in a git repository"
        }
        
        # Check if tag already exists
        $existingTag = git tag -l "v$Version" 2>$null
        if ($existingTag) {
            Write-Warning "Tag v$Version already exists"
            return
        }
        
        # Create annotated tag
        git tag -a "v$Version" -m "Release version $Version"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Created git tag: v$Version" -ForegroundColor Green
            Write-Host "Push tag with: git push origin v$Version" -ForegroundColor Yellow
        } else {
            throw "Failed to create git tag"
        }
    }
    catch {
        Write-Error "Git tag creation failed: $_"
    }
}

function Get-VersionInfo {
    param([switch]$IncludeBuildMetadata)
    
    try {
        $version = Get-CurrentVersion -IncludeBuildMetadata:$IncludeBuildMetadata
        
        $info = @{
            Version = $version
            Valid = Test-VersionFormat $version
        }
        
        if ($IncludeBuildMetadata) {
            $info.GitSHA = Get-GitCommitSHA
            $info.Timestamp = Get-BuildTimestamp
        }
        
        return $info
    }
    catch {
        Write-Error "Failed to get version info: $_"
        return $null
    }
}

# Main execution
try {
    if ($Help) {
        Show-Help
        exit 0
    }
    
    switch ($Action) {
        "get" {
            $versionInfo = Get-VersionInfo -IncludeBuildMetadata:$BuildMetadata
            if ($versionInfo) {
                Write-Host $versionInfo.Version
                
                if ($BuildMetadata) {
                    Write-Host "Git SHA: $($versionInfo.GitSHA)" -ForegroundColor Gray
                    Write-Host "Timestamp: $($versionInfo.Timestamp)" -ForegroundColor Gray
                }
            }
        }
        
        "bump" {
            $oldVersion = Get-CurrentVersion
            $newVersion = Invoke-BumpVersion $BumpType
            Write-Host "Bumped version: $oldVersion → $newVersion" -ForegroundColor Cyan
        }
        
        "validate" {
            $versionToValidate = if ($Version) { $Version } else { Get-CurrentVersion }
            $isValid = Test-VersionFormat $versionToValidate
            
            if ($isValid) {
                Write-Host "✓ Version format is valid: $versionToValidate" -ForegroundColor Green
                exit 0
            } else {
                Write-Host "✗ Version format is invalid: $versionToValidate" -ForegroundColor Red
                Write-Host "Expected format: X.Y.Z (e.g., 1.2.3)" -ForegroundColor Yellow
                exit 1
            }
        }
        
        "tag" {
            $currentVersion = Get-CurrentVersion
            New-GitTag $currentVersion
        }
        
        default {
            Write-Error "Unknown action: $Action. Use -Help for usage information."
            exit 1
        }
    }
}
catch {
    Write-Error "Error: $_"
    exit 1
}