# Local Environment Rollback Script for TTRPG Center
# Complements the GitHub Actions rollback workflow for local rollback operations

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "test")]
    [string]$Environment,
    
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$Registry = "ghcr.io",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "ttrpg/app",
    
    [Parameter(Mandatory=$false)]
    [string]$Reason = "Manual rollback",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipHealthCheck,
    
    [Parameter(Mandatory=$false)]
    [switch]$Force,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$DeployScript = Join-Path $PSScriptRoot "deploy.ps1"
$TestScript = Join-Path $PSScriptRoot "test.ps1"

function Show-Help {
    Write-Host @"
Local Environment Rollback Script for TTRPG Center

USAGE:
    .\rollback.ps1 -Environment <env> -Version <version> [OPTIONS]

REQUIRED PARAMETERS:
    -Environment      Target environment: dev, test
    -Version          Version to rollback to (e.g., 1.2.3 or git SHA)

OPTIONS:
    -Registry         Container registry URL (default: ghcr.io)
    -ImageName        Image name without registry (default: ttrpg/app)
    -Reason           Reason for rollback (default: "Manual rollback")
    -SkipHealthCheck  Skip post-rollback health checks
    -Force            Skip confirmation prompts
    -DryRun           Show what would be done without executing
    -Help             Show this help message

EXAMPLES:
    .\rollback.ps1 -Environment dev -Version 1.2.3
    .\rollback.ps1 -Environment test -Version a1b2c3d4 -Reason "Critical bug fix"
    .\rollback.ps1 -Environment dev -Version 1.1.0 -DryRun

ROLLBACK PROCESS:
    1. Validate rollback request and image availability
    2. Create backup of current deployment state
    3. Stop current services
    4. Deploy target version
    5. Run health checks and validation tests
    6. Generate rollback audit log

NOTE:
    This script is for local environment rollbacks only.
    For production rollbacks, use the GitHub Actions workflow.
"@
}

function Get-CurrentDeploymentInfo {
    param([string]$Environment)
    
    Write-Host "Gathering current deployment information..." -ForegroundColor Cyan
    
    try {
        $containerName = "ttrpg-app-$Environment"
        
        # Get current container info
        $containerInfo = docker inspect $containerName 2>$null | ConvertFrom-Json
        
        if ($containerInfo) {
            $currentImage = $containerInfo[0].Config.Image
            $currentLabels = $containerInfo[0].Config.Labels
            
            # Extract version from labels or image tag
            $currentVersion = "unknown"
            if ($currentLabels -and $currentLabels."ttrpg.version") {
                $currentVersion = $currentLabels."ttrpg.version"
            } elseif ($currentImage -match ":(.+)$") {
                $currentVersion = $matches[1]
            }
            
            return @{
                Image = $currentImage
                Version = $currentVersion
                ContainerName = $containerName
                IsRunning = $containerInfo[0].State.Running
            }
        } else {
            Write-Host "No current deployment found for $Environment environment" -ForegroundColor Yellow
            return $null
        }
    }
    catch {
        Write-Host "Failed to get current deployment info: $_" -ForegroundColor Yellow
        return $null
    }
}

function Test-RollbackTarget {
    param(
        [string]$Registry,
        [string]$ImageName,
        [string]$Version
    )
    
    $fullImageName = "$Registry/$ImageName"
    
    Write-Host "Validating rollback target..." -ForegroundColor Cyan
    Write-Host "Target: $fullImageName`:$Version" -ForegroundColor Gray
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would validate $fullImageName`:$Version" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Check if target image exists
        docker manifest inspect "$fullImageName`:$Version" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Target image available: $fullImageName`:$Version" -ForegroundColor Green
            return $true
        } else {
            throw "Target image not found in registry"
        }
    }
    catch {
        Write-Host "❌ Target image validation failed: $_" -ForegroundColor Red
        return $false
    }
}

function Confirm-RollbackOperation {
    param(
        [string]$Environment,
        [string]$CurrentVersion,
        [string]$TargetVersion,
        [string]$Reason
    )
    
    if ($Force -or $DryRun) {
        if ($Force) {
            Write-Host "⚡ Force mode enabled, skipping confirmation" -ForegroundColor Yellow
        }
        return $true
    }
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "                        ROLLBACK CONFIRMATION" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host ""
    Write-Host "Environment:      $Environment" -ForegroundColor White
    Write-Host "Current Version:  $CurrentVersion" -ForegroundColor White
    Write-Host "Target Version:   $TargetVersion" -ForegroundColor White
    Write-Host "Reason:          $Reason" -ForegroundColor White
    Write-Host "Initiated By:    $env:USERNAME" -ForegroundColor White
    Write-Host "Timestamp:       $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss UTC')" -ForegroundColor White
    Write-Host ""
    Write-Host "⚠️  WARNING: This will replace the current deployment!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Red
    
    do {
        $response = Read-Host "Are you sure you want to proceed with rollback? (yes/no)"
        $response = $response.Trim().ToLower()
        
        switch ($response) {
            "yes" {
                Write-Host "✓ Rollback confirmed, proceeding..." -ForegroundColor Green
                return $true
            }
            "no" {
                Write-Host "❌ Rollback cancelled" -ForegroundColor Red
                return $false
            }
            default {
                Write-Host "Please enter 'yes' or 'no'" -ForegroundColor Yellow
            }
        }
    } while ($true)
}

function New-DeploymentBackup {
    param(
        [string]$Environment,
        [hashtable]$CurrentInfo
    )
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmssZ"
    $backupFile = "rollback-backup-$Environment-$timestamp.json"
    
    Write-Host "Creating deployment backup..." -ForegroundColor Cyan
    
    $backupData = @{
        timestamp = $timestamp
        environment = $Environment
        backup_reason = "pre-rollback"
        current_deployment = $CurrentInfo
        initiated_by = $env:USERNAME
        machine = $env:COMPUTERNAME
    }
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would create backup file $backupFile" -ForegroundColor Yellow
    } else {
        $backupData | ConvertTo-Json -Depth 3 | Set-Content -Path $backupFile
        Write-Host "✓ Backup created: $backupFile" -ForegroundColor Green
    }
    
    return $backupFile
}

function Invoke-RollbackDeployment {
    param(
        [string]$Environment,
        [string]$Version,
        [string]$Registry,
        [string]$ImageName
    )
    
    Write-Host "Executing rollback deployment..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would deploy $Registry/$ImageName`:$Version to $Environment" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Stop current services
        Write-Host "Stopping current services..." -ForegroundColor Gray
        & $DeployScript -Env $Environment -Action down
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to stop services gracefully, continuing..."
        }
        
        # Set the target image
        $env:CONTAINER_IMAGE = "$Registry/$ImageName`:$Version"
        $env:VERSION = $Version
        
        # Deploy target version
        Write-Host "Deploying target version $Version..." -ForegroundColor Gray
        & $DeployScript -Env $Environment -Action up
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to deploy target version"
        }
        
        Write-Host "✓ Rollback deployment completed" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Rollback deployment failed: $_" -ForegroundColor Red
        return $false
    }
}

function Test-PostRollbackHealth {
    param(
        [string]$Environment
    )
    
    if ($SkipHealthCheck) {
        Write-Host "⏭️  Skipping post-rollback health checks" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host "Running post-rollback health checks..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would run health checks for $Environment" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Wait for services to stabilize
        Write-Host "Waiting for services to stabilize..." -ForegroundColor Gray
        Start-Sleep -Seconds 30
        
        # Determine port for environment
        $port = switch ($Environment) {
            "dev" { "8000" }
            "test" { "8181" }
            default { throw "Unknown environment port for $Environment" }
        }
        
        # Health check with retries
        $maxRetries = 6
        $retryDelay = 10
        
        for ($i = 1; $i -le $maxRetries; $i++) {
            try {
                Write-Host "Health check attempt $i of $maxRetries..." -ForegroundColor Gray
                $response = Invoke-RestMethod -Uri "http://localhost:$port/healthz" -TimeoutSec 30 -ErrorAction Stop
                
                if ($response -and $response.status -eq "healthy") {
                    Write-Host "✓ Health check passed" -ForegroundColor Green
                    break
                } else {
                    throw "Unhealthy response: $($response | ConvertTo-Json -Compress)"
                }
            }
            catch {
                if ($i -eq $maxRetries) {
                    throw "Health check failed after $maxRetries attempts: $_"
                }
                Write-Host "Attempt $i failed, retrying in $retryDelay seconds..." -ForegroundColor Yellow
                Start-Sleep -Seconds $retryDelay
            }
        }
        
        # Run basic validation tests if test script exists
        if (Test-Path $TestScript) {
            Write-Host "Running rollback validation tests..." -ForegroundColor Gray
            
            & $TestScript -Env $Environment -Type "rollback-validation"
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Rollback validation tests failed, but deployment appears healthy"
                return $false
            }
            
            Write-Host "✓ Rollback validation tests passed" -ForegroundColor Green
        }
        
        return $true
    }
    catch {
        Write-Host "❌ Post-rollback health checks failed: $_" -ForegroundColor Red
        return $false
    }
}

function New-RollbackAuditLog {
    param(
        [string]$Environment,
        [string]$CurrentVersion,
        [string]$TargetVersion,
        [string]$Status,
        [string]$Reason,
        [string]$StartTime,
        [string]$EndTime,
        [string]$BackupFile
    )
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmssZ"
    $auditFile = "rollback-audit-$Environment-$timestamp.json"
    
    $auditData = @{
        event = "local_rollback"
        environment = $Environment
        previous_version = $CurrentVersion
        target_version = $TargetVersion
        reason = $Reason
        status = $Status
        start_time = $StartTime
        end_time = $EndTime
        initiated_by = $env:USERNAME
        machine = $env:COMPUTERNAME
        backup_file = $BackupFile
        dry_run = $DryRun.IsPresent
        force = $Force.IsPresent
        skip_health_check = $SkipHealthCheck.IsPresent
        registry = $Registry
        image_name = $ImageName
    }
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would create audit log $auditFile" -ForegroundColor Yellow
    } else {
        $auditData | ConvertTo-Json -Depth 3 | Set-Content -Path $auditFile
        Write-Host "📋 Audit log created: $auditFile" -ForegroundColor Gray
    }
    
    return $auditFile
}

# Main execution
try {
    if ($Help) {
        Show-Help
        exit 0
    }
    
    $startTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    
    Write-Host ""
    Write-Host "TTRPG Center Local Environment Rollback" -ForegroundColor Red
    Write-Host "=======================================" -ForegroundColor Red
    Write-Host "Environment: $Environment" -ForegroundColor White
    Write-Host "Target Version: $Version" -ForegroundColor White
    Write-Host "Reason: $Reason" -ForegroundColor White
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Yellow
        Write-Host ""
    }
    
    # Step 1: Get current deployment info
    $currentInfo = Get-CurrentDeploymentInfo -Environment $Environment
    $currentVersion = if ($currentInfo) { $currentInfo.Version } else { "none" }
    
    # Step 2: Validate rollback target
    $targetValid = Test-RollbackTarget -Registry $Registry -ImageName $ImageName -Version $Version
    if (-not $targetValid) {
        throw "Rollback target validation failed"
    }
    
    # Step 3: Confirm rollback operation
    $confirmed = Confirm-RollbackOperation -Environment $Environment -CurrentVersion $currentVersion -TargetVersion $Version -Reason $Reason
    if (-not $confirmed) {
        throw "Rollback operation cancelled"
    }
    
    # Step 4: Create backup
    $backupFile = New-DeploymentBackup -Environment $Environment -CurrentInfo $currentInfo
    
    # Step 5: Execute rollback
    $rollbackSuccess = Invoke-RollbackDeployment -Environment $Environment -Version $Version -Registry $Registry -ImageName $ImageName
    if (-not $rollbackSuccess) {
        throw "Rollback deployment failed"
    }
    
    # Step 6: Health checks and validation
    $healthCheckPassed = Test-PostRollbackHealth -Environment $Environment
    
    $endTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    $status = if ($healthCheckPassed) { "success" } else { "success_with_warnings" }
    
    # Step 7: Create audit log
    New-RollbackAuditLog -Environment $Environment -CurrentVersion $currentVersion -TargetVersion $Version -Status $status -Reason $Reason -StartTime $startTime -EndTime $endTime -BackupFile $backupFile
    
    Write-Host ""
    if ($healthCheckPassed) {
        Write-Host "✅ Rollback completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Rollback completed with warnings" -ForegroundColor Yellow
        Write-Host "Manual verification recommended" -ForegroundColor Yellow
    }
    
    Write-Host "Environment: $Environment" -ForegroundColor White
    Write-Host "Rolled back: $currentVersion → $Version" -ForegroundColor White
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "Run without -DryRun to execute the rollback" -ForegroundColor Yellow
    }
}
catch {
    $endTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    
    # Create failure audit log
    New-RollbackAuditLog -Environment $Environment -CurrentVersion $currentVersion -TargetVersion $Version -Status "failed" -Reason $Reason -StartTime $startTime -EndTime $endTime -BackupFile $backupFile
    
    Write-Host ""
    Write-Host "❌ Rollback failed: $_" -ForegroundColor Red
    
    if ($currentInfo) {
        Write-Host ""
        Write-Host "Recovery suggestion:" -ForegroundColor Yellow
        Write-Host "Try restoring to previous state: $($currentInfo.Version)" -ForegroundColor Yellow
    }
    
    exit 1
}