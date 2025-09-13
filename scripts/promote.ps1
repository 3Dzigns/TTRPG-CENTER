# Environment Promotion Script for TTRPG Center CI/CD Pipeline
# Promotes builds from DEV to TEST with validation and approval gates

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-to-test", "test-to-prod")]
    [string]$PromotionType,
    
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$Registry = "ghcr.io",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "ttrpg/app",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipValidation,
    
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
Environment Promotion Script for TTRPG Center CI/CD Pipeline

USAGE:
    .\promote.ps1 -PromotionType <type> -Version <version> [OPTIONS]

REQUIRED PARAMETERS:
    -PromotionType    Type of promotion: dev-to-test, test-to-prod
    -Version          Version to promote (e.g., 1.2.3 or git SHA)

OPTIONS:
    -Registry         Container registry URL (default: ghcr.io)
    -ImageName        Image name without registry (default: ttrpg/app)
    -SkipValidation   Skip pre-promotion validation checks
    -DryRun           Show what would be done without executing
    -Help             Show this help message

EXAMPLES:
    .\promote.ps1 -PromotionType dev-to-test -Version 1.2.3
    .\promote.ps1 -PromotionType dev-to-test -Version a1b2c3d4 -DryRun
    .\promote.ps1 -PromotionType test-to-prod -Version 1.2.3 -SkipValidation

PROMOTION PROCESS:
    1. Validate promotion request and prerequisites
    2. Verify source environment deployment status
    3. Check target image availability in registry
    4. Run pre-promotion validation tests
    5. Deploy to target environment
    6. Run post-promotion validation tests
    7. Generate promotion report and audit log

PREREQUISITES:
    - Source environment must be healthy and stable
    - Target version must exist in container registry
    - Required approval for production promotions
    - Valid environment configuration files
"@
}

function Test-PromotionPrerequisites {
    param(
        [string]$PromotionType,
        [string]$Version
    )
    
    Write-Host "Validating promotion prerequisites..." -ForegroundColor Cyan
    
    # Validate promotion type
    $sourceEnv = ""
    $targetEnv = ""
    
    switch ($PromotionType) {
        "dev-to-test" {
            $sourceEnv = "dev"
            $targetEnv = "test"
        }
        "test-to-prod" {
            $sourceEnv = "test"
            $targetEnv = "prod"
            Write-Host "⚠️  PRODUCTION PROMOTION DETECTED" -ForegroundColor Yellow
            Write-Host "Additional validation and approval required" -ForegroundColor Yellow
        }
        default {
            throw "Invalid promotion type: $PromotionType"
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
    
    # Check required scripts
    if (-not (Test-Path $DeployScript)) {
        throw "Deploy script not found: $DeployScript"
    }
    
    if (-not (Test-Path $TestScript)) {
        Write-Warning "Test script not found: $TestScript"
        Write-Warning "Post-promotion validation will be limited"
    }
    
    # Check environment configurations
    $sourceCompose = Join-Path $ProjectRoot "docker-compose.$sourceEnv.yml"
    $targetCompose = Join-Path $ProjectRoot "docker-compose.$targetEnv.yml"
    
    if (-not (Test-Path $sourceCompose)) {
        throw "Source environment compose file not found: $sourceCompose"
    }
    
    if (-not (Test-Path $targetCompose)) {
        throw "Target environment compose file not found: $targetCompose"
    }
    
    Write-Host "✓ Prerequisites validated" -ForegroundColor Green
    return @{
        SourceEnv = $sourceEnv
        TargetEnv = $targetEnv
        SourceCompose = $sourceCompose
        TargetCompose = $targetCompose
    }
}

function Test-ImageAvailability {
    param(
        [string]$Registry,
        [string]$ImageName,
        [string]$Version
    )
    
    $fullImageName = "$Registry/$ImageName"
    
    Write-Host "Checking image availability..." -ForegroundColor Cyan
    Write-Host "Image: $fullImageName`:$Version" -ForegroundColor Gray
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would check image availability for $fullImageName`:$Version" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Use docker manifest to check if image exists
        docker manifest inspect "$fullImageName`:$Version" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Image available: $fullImageName`:$Version" -ForegroundColor Green
            return $true
        } else {
            throw "Image not found in registry"
        }
    }
    catch {
        Write-Host "❌ Image not available: $fullImageName`:$Version" -ForegroundColor Red
        Write-Host "Error: $_" -ForegroundColor Red
        return $false
    }
}

function Test-SourceEnvironmentHealth {
    param(
        [string]$SourceEnv
    )
    
    Write-Host "Checking source environment health..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would check $SourceEnv environment health" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Check if source environment is running
        $sourcePort = switch ($SourceEnv) {
            "dev" { "8000" }
            "test" { "8181" }
            default { throw "Unknown source environment: $SourceEnv" }
        }
        
        Write-Host "Testing health endpoint: http://localhost:$sourcePort/healthz" -ForegroundColor Gray
        
        $response = Invoke-RestMethod -Uri "http://localhost:$sourcePort/healthz" -TimeoutSec 30 -ErrorAction Stop
        
        if ($response -and $response.status -eq "healthy") {
            Write-Host "✓ Source environment ($SourceEnv) is healthy" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Source environment ($SourceEnv) health check failed" -ForegroundColor Red
            Write-Host "Response: $($response | ConvertTo-Json -Depth 2)" -ForegroundColor Gray
            return $false
        }
    }
    catch {
        Write-Host "❌ Source environment ($SourceEnv) health check error: $_" -ForegroundColor Red
        return $false
    }
}

function Invoke-PrePromotionValidation {
    param(
        [string]$SourceEnv,
        [string]$Version
    )
    
    if ($SkipValidation) {
        Write-Host "⏭️  Skipping pre-promotion validation" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host "Running pre-promotion validation..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would run pre-promotion validation for $SourceEnv" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Run tests against source environment
        if (Test-Path $TestScript) {
            Write-Host "Running test suite against $SourceEnv environment..." -ForegroundColor Gray
            
            & $TestScript -Env $SourceEnv -Type "pre-promotion"
            if ($LASTEXITCODE -ne 0) {
                throw "Pre-promotion tests failed for $SourceEnv environment"
            }
            
            Write-Host "✓ Pre-promotion validation passed" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Test script not available, skipping validation" -ForegroundColor Yellow
        }
        
        return $true
    }
    catch {
        Write-Host "❌ Pre-promotion validation failed: $_" -ForegroundColor Red
        return $false
    }
}

function Request-PromotionApproval {
    param(
        [string]$PromotionType,
        [string]$SourceEnv,
        [string]$TargetEnv,
        [string]$Version
    )
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would request approval for $PromotionType promotion" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "                    PROMOTION APPROVAL REQUIRED" -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Promotion Type:    $PromotionType" -ForegroundColor White
    Write-Host "Source:           $SourceEnv environment" -ForegroundColor White
    Write-Host "Target:           $TargetEnv environment" -ForegroundColor White
    Write-Host "Version:          $Version" -ForegroundColor White
    Write-Host "Initiated By:     $env:USERNAME" -ForegroundColor White
    Write-Host "Timestamp:        $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss UTC')" -ForegroundColor White
    Write-Host ""
    
    if ($TargetEnv -eq "prod") {
        Write-Host "⚠️  WARNING: This is a PRODUCTION deployment!" -ForegroundColor Red
        Write-Host "Please ensure all change management procedures have been followed." -ForegroundColor Red
        Write-Host ""
    }
    
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    
    do {
        $approval = Read-Host "Do you approve this promotion? (yes/no/cancel)"
        $approval = $approval.Trim().ToLower()
        
        switch ($approval) {
            "yes" {
                Write-Host "✓ Promotion approved, proceeding..." -ForegroundColor Green
                return $true
            }
            "no" {
                Write-Host "❌ Promotion denied" -ForegroundColor Red
                return $false
            }
            "cancel" {
                Write-Host "🚫 Promotion cancelled" -ForegroundColor Yellow
                return $false
            }
            default {
                Write-Host "Please enter 'yes', 'no', or 'cancel'" -ForegroundColor Yellow
            }
        }
    } while ($true)
}

function Invoke-EnvironmentPromotion {
    param(
        [string]$TargetEnv,
        [string]$Version,
        [string]$Registry,
        [string]$ImageName
    )
    
    Write-Host "Deploying to $TargetEnv environment..." -ForegroundColor Cyan
    
    $fullImageName = "$Registry/$ImageName`:$Version"
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would deploy $fullImageName to $TargetEnv environment" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Use deploy script to handle the actual deployment
        $deployArgs = @(
            "-Env", $TargetEnv,
            "-Version", $Version,
            "-Registry", $Registry,
            "-ImageName", $ImageName
        )
        
        Write-Host "Executing: .\deploy.ps1 $($deployArgs -join ' ')" -ForegroundColor Gray
        
        & $DeployScript @deployArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Deployment to $TargetEnv failed"
        }
        
        Write-Host "✓ Deployment to $TargetEnv completed" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Deployment to $TargetEnv failed: $_" -ForegroundColor Red
        return $false
    }
}

function Invoke-PostPromotionValidation {
    param(
        [string]$TargetEnv,
        [string]$Version
    )
    
    Write-Host "Running post-promotion validation..." -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Host "DRY RUN: Would run post-promotion validation for $TargetEnv" -ForegroundColor Yellow
        return $true
    }
    
    try {
        # Wait for environment to stabilize
        Write-Host "Waiting for environment to stabilize..." -ForegroundColor Gray
        Start-Sleep -Seconds 30
        
        # Check health endpoint
        $targetPort = switch ($TargetEnv) {
            "test" { "8181" }
            "prod" { "8282" }
            default { throw "Unknown target environment: $TargetEnv" }
        }
        
        Write-Host "Testing health endpoint: http://localhost:$targetPort/healthz" -ForegroundColor Gray
        
        $maxRetries = 6
        $retryDelay = 10
        
        for ($i = 1; $i -le $maxRetries; $i++) {
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:$targetPort/healthz" -TimeoutSec 30 -ErrorAction Stop
                
                if ($response -and $response.status -eq "healthy") {
                    Write-Host "✓ Target environment ($TargetEnv) is healthy" -ForegroundColor Green
                    break
                }
            }
            catch {
                if ($i -eq $maxRetries) {
                    throw "Health check failed after $maxRetries attempts: $_"
                }
                Write-Host "Health check attempt $i failed, retrying in $retryDelay seconds..." -ForegroundColor Yellow
                Start-Sleep -Seconds $retryDelay
            }
        }
        
        # Run post-deployment tests
        if (Test-Path $TestScript) {
            Write-Host "Running test suite against $TargetEnv environment..." -ForegroundColor Gray
            
            & $TestScript -Env $TargetEnv -Type "post-promotion"
            if ($LASTEXITCODE -ne 0) {
                throw "Post-promotion tests failed for $TargetEnv environment"
            }
            
            Write-Host "✓ Post-promotion validation passed" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Test script not available, skipping detailed validation" -ForegroundColor Yellow
        }
        
        return $true
    }
    catch {
        Write-Host "❌ Post-promotion validation failed: $_" -ForegroundColor Red
        return $false
    }
}

function New-PromotionAuditLog {
    param(
        [string]$PromotionType,
        [string]$SourceEnv,
        [string]$TargetEnv,
        [string]$Version,
        [string]$Status,
        [string]$StartTime,
        [string]$EndTime
    )
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmssZ"
    $auditFile = "promotion-audit-$timestamp.json"
    
    $auditData = @{
        event = "promotion"
        promotion_type = $PromotionType
        source_environment = $SourceEnv
        target_environment = $TargetEnv
        version = $Version
        status = $Status
        start_time = $StartTime
        end_time = $EndTime
        initiated_by = $env:USERNAME
        machine = $env:COMPUTERNAME
        dry_run = $DryRun.IsPresent
        skip_validation = $SkipValidation.IsPresent
        registry = $Registry
        image_name = $ImageName
    }
    
    $auditData | ConvertTo-Json -Depth 3 | Set-Content -Path $auditFile
    
    Write-Host "📋 Audit log created: $auditFile" -ForegroundColor Gray
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
    Write-Host "TTRPG Center Environment Promotion" -ForegroundColor Cyan
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "Promotion: $PromotionType" -ForegroundColor White
    Write-Host "Version: $Version" -ForegroundColor White
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Yellow
        Write-Host ""
    }
    
    # Step 1: Validate prerequisites
    $envInfo = Test-PromotionPrerequisites -PromotionType $PromotionType -Version $Version
    
    # Step 2: Check image availability
    $imageAvailable = Test-ImageAvailability -Registry $Registry -ImageName $ImageName -Version $Version
    if (-not $imageAvailable) {
        throw "Target image not available for promotion"
    }
    
    # Step 3: Check source environment health
    $sourceHealthy = Test-SourceEnvironmentHealth -SourceEnv $envInfo.SourceEnv
    if (-not $sourceHealthy) {
        throw "Source environment is not healthy, cannot proceed with promotion"
    }
    
    # Step 4: Run pre-promotion validation
    $validationPassed = Invoke-PrePromotionValidation -SourceEnv $envInfo.SourceEnv -Version $Version
    if (-not $validationPassed) {
        throw "Pre-promotion validation failed"
    }
    
    # Step 5: Request approval
    $approved = Request-PromotionApproval -PromotionType $PromotionType -SourceEnv $envInfo.SourceEnv -TargetEnv $envInfo.TargetEnv -Version $Version
    if (-not $approved) {
        throw "Promotion not approved"
    }
    
    # Step 6: Execute promotion
    $deploymentSuccess = Invoke-EnvironmentPromotion -TargetEnv $envInfo.TargetEnv -Version $Version -Registry $Registry -ImageName $ImageName
    if (-not $deploymentSuccess) {
        throw "Deployment to target environment failed"
    }
    
    # Step 7: Post-promotion validation
    $postValidationPassed = Invoke-PostPromotionValidation -TargetEnv $envInfo.TargetEnv -Version $Version
    if (-not $postValidationPassed) {
        Write-Warning "Post-promotion validation failed, but deployment was successful"
        Write-Warning "Manual verification recommended"
    }
    
    $endTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    $status = if ($postValidationPassed) { "success" } else { "success_with_warnings" }
    
    # Create audit log
    New-PromotionAuditLog -PromotionType $PromotionType -SourceEnv $envInfo.SourceEnv -TargetEnv $envInfo.TargetEnv -Version $Version -Status $status -StartTime $startTime -EndTime $endTime
    
    Write-Host ""
    Write-Host "✅ Promotion completed successfully!" -ForegroundColor Green
    Write-Host "Environment: $($envInfo.SourceEnv) → $($envInfo.TargetEnv)" -ForegroundColor White
    Write-Host "Version: $Version" -ForegroundColor White
    
    if ($DryRun) {
        Write-Host ""
        Write-Host "Run without -DryRun to execute the promotion" -ForegroundColor Yellow
    }
}
catch {
    $endTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    
    # Create failure audit log
    if ($envInfo) {
        New-PromotionAuditLog -PromotionType $PromotionType -SourceEnv $envInfo.SourceEnv -TargetEnv $envInfo.TargetEnv -Version $Version -Status "failed" -StartTime $startTime -EndTime $endTime
    }
    
    Write-Host ""
    Write-Host "❌ Promotion failed: $_" -ForegroundColor Red
    exit 1
}