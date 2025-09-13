# Security Scanning Script for TTRPG Center
# Comprehensive security scanning for code, dependencies, and container images

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("code", "dependencies", "container", "all")]
    [string]$ScanType = "all",
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerImage = "",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputFormat = "json",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "security-reports",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("LOW", "MEDIUM", "HIGH", "CRITICAL")]
    [string]$MinSeverity = "MEDIUM",
    
    [Parameter(Mandatory=$false)]
    [switch]$FailOnHigh,
    
    [Parameter(Mandatory=$false)]
    [switch]$FailOnCritical,
    
    [Parameter(Mandatory=$false)]
    [switch]$Verbose,
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

function Show-Help {
    Write-Host @"
Security Scanning Script for TTRPG Center

USAGE:
    .\security-scan.ps1 [OPTIONS]

OPTIONS:
    -ScanType         Type of scan: code, dependencies, container, all (default: all)
    -ContainerImage   Container image to scan (required for container scan)
    -OutputFormat     Output format: json, table, sarif (default: json)
    -OutputDir        Directory for output reports (default: security-reports)
    -MinSeverity      Minimum severity to report: LOW, MEDIUM, HIGH, CRITICAL (default: MEDIUM)
    -FailOnHigh       Exit with error code if HIGH severity issues found
    -FailOnCritical   Exit with error code if CRITICAL severity issues found
    -Verbose          Enable verbose output
    -Help             Show this help message

EXAMPLES:
    .\security-scan.ps1                                    # Run all scans
    .\security-scan.ps1 -ScanType code                     # Code scan only
    .\security-scan.ps1 -ScanType container -ContainerImage "myapp:latest"
    .\security-scan.ps1 -FailOnCritical -MinSeverity HIGH  # Fail on critical issues

SCAN TYPES:
    code            Static code analysis with Bandit
    dependencies    Dependency vulnerability scan with Safety
    container       Container image scan with Trivy
    all             Run all scan types

OUTPUT:
    Reports are saved to the specified output directory with timestamps.
    Supported formats: JSON, table (console), SARIF (for GitHub integration).
"@
}

function Initialize-OutputDirectory {
    param([string]$OutputDir)
    
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        Write-Host "Created output directory: $OutputDir" -ForegroundColor Green
    }
    
    return (Resolve-Path $OutputDir).Path
}

function Test-ScanningTools {
    Write-Host "Checking security scanning tools..." -ForegroundColor Cyan
    
    $missingTools = @()
    
    # Check Python and pip for Bandit and Safety
    try {
        python --version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Python not found" }
    }
    catch {
        $missingTools += "Python"
    }
    
    try {
        pip --version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "pip not found" }
    }
    catch {
        $missingTools += "pip"
    }
    
    # Check Docker for Trivy
    if ($ScanType -eq "container" -or $ScanType -eq "all") {
        try {
            docker --version | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Docker not found" }
        }
        catch {
            $missingTools += "Docker"
        }
    }
    
    if ($missingTools.Count -gt 0) {
        throw "Missing required tools: $($missingTools -join ', ')"
    }
    
    Write-Host "✓ All required tools available" -ForegroundColor Green
}

function Install-SecurityTools {
    Write-Host "Installing/updating security scanning tools..." -ForegroundColor Cyan
    
    try {
        # Install/update Bandit for code scanning
        Write-Host "Installing Bandit..." -ForegroundColor Gray
        pip install --upgrade bandit[toml] | Out-Null
        
        # Install/update Safety for dependency scanning
        Write-Host "Installing Safety..." -ForegroundColor Gray
        pip install --upgrade safety | Out-Null
        
        Write-Host "✓ Security tools installed/updated" -ForegroundColor Green
    }
    catch {
        Write-Warning "Failed to install security tools: $_"
        Write-Warning "Some scans may not be available"
    }
}

function Invoke-CodeScan {
    param(
        [string]$OutputDir,
        [string]$OutputFormat,
        [string]$MinSeverity
    )
    
    Write-Host "Running code security scan with Bandit..." -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
    $reportFile = Join-Path $OutputDir "bandit-report-$timestamp.$OutputFormat"
    
    try {
        $banditArgs = @(
            "-r", "src_common/",
            "--severity-level", $MinSeverity.ToLower(),
            "--confidence-level", "medium"
        )
        
        # Add format-specific arguments
        switch ($OutputFormat) {
            "json" {
                $banditArgs += @("-f", "json", "-o", $reportFile)
            }
            "sarif" {
                $banditArgs += @("-f", "sarif", "-o", $reportFile)
            }
            "table" {
                # For table format, output to console and save summary
                $banditArgs += @("-f", "txt")
            }
        }
        
        if ($Verbose) {
            $banditArgs += @("-v")
        }
        
        Write-Host "Executing: bandit $($banditArgs -join ' ')" -ForegroundColor Gray
        
        Push-Location $ProjectRoot
        try {
            if ($OutputFormat -eq "table") {
                bandit @banditArgs | Tee-Object -FilePath (Join-Path $OutputDir "bandit-summary-$timestamp.txt")
            } else {
                bandit @banditArgs
            }
            
            $banditExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
        
        # Analyze results
        $issueCount = 0
        $highCount = 0
        $criticalCount = 0
        
        if ($OutputFormat -eq "json" -and (Test-Path $reportFile)) {
            $results = Get-Content $reportFile | ConvertFrom-Json
            $issueCount = $results.results.Count
            
            if ($results.results) {
                $highCount = ($results.results | Where-Object { $_.issue_severity -eq "HIGH" }).Count
                $criticalCount = ($results.results | Where-Object { $_.issue_severity -eq "CRITICAL" }).Count
            }
        }
        
        Write-Host "Code scan completed:" -ForegroundColor Green
        Write-Host "  Total issues: $issueCount" -ForegroundColor Gray
        Write-Host "  High severity: $highCount" -ForegroundColor Gray
        Write-Host "  Critical severity: $criticalCount" -ForegroundColor Gray
        Write-Host "  Report: $reportFile" -ForegroundColor Gray
        
        return @{
            Type = "code"
            Success = $true
            IssueCount = $issueCount
            HighCount = $highCount
            CriticalCount = $criticalCount
            ReportFile = $reportFile
            ExitCode = $banditExitCode
        }
    }
    catch {
        Write-Host "❌ Code scan failed: $_" -ForegroundColor Red
        return @{
            Type = "code"
            Success = $false
            Error = $_.Exception.Message
        }
    }
}

function Invoke-DependencyScan {
    param(
        [string]$OutputDir,
        [string]$OutputFormat,
        [string]$MinSeverity
    )
    
    Write-Host "Running dependency vulnerability scan with Safety..." -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
    $reportFile = Join-Path $OutputDir "safety-report-$timestamp.$OutputFormat"
    
    try {
        $safetyArgs = @("check")
        
        # Add format-specific arguments
        switch ($OutputFormat) {
            "json" {
                $safetyArgs += @("--json", "--output", $reportFile)
            }
            "table" {
                # For table format, output to console and save
                $safetyArgs += @("--output", (Join-Path $OutputDir "safety-summary-$timestamp.txt"))
            }
        }
        
        Write-Host "Executing: safety $($safetyArgs -join ' ')" -ForegroundColor Gray
        
        Push-Location $ProjectRoot
        try {
            if ($OutputFormat -eq "table") {
                safety @safetyArgs | Tee-Object -FilePath (Join-Path $OutputDir "safety-output-$timestamp.txt")
            } else {
                safety @safetyArgs
            }
            
            $safetyExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
        
        # Analyze results
        $vulnerabilityCount = 0
        $highCount = 0
        $criticalCount = 0
        
        if ($OutputFormat -eq "json" -and (Test-Path $reportFile)) {
            $results = Get-Content $reportFile | ConvertFrom-Json
            $vulnerabilityCount = $results.Count
            
            # Safety doesn't provide severity levels in the same way as other tools
            # Assume all vulnerabilities are at least medium severity
            $highCount = $vulnerabilityCount
        }
        
        Write-Host "Dependency scan completed:" -ForegroundColor Green
        Write-Host "  Vulnerabilities found: $vulnerabilityCount" -ForegroundColor Gray
        Write-Host "  Report: $reportFile" -ForegroundColor Gray
        
        return @{
            Type = "dependencies"
            Success = $true
            VulnerabilityCount = $vulnerabilityCount
            HighCount = $highCount
            CriticalCount = $criticalCount
            ReportFile = $reportFile
            ExitCode = $safetyExitCode
        }
    }
    catch {
        Write-Host "❌ Dependency scan failed: $_" -ForegroundColor Red
        return @{
            Type = "dependencies"
            Success = $false
            Error = $_.Exception.Message
        }
    }
}

function Invoke-ContainerScan {
    param(
        [string]$ContainerImage,
        [string]$OutputDir,
        [string]$OutputFormat,
        [string]$MinSeverity
    )
    
    if (-not $ContainerImage) {
        throw "Container image must be specified for container scan"
    }
    
    Write-Host "Running container security scan with Trivy..." -ForegroundColor Cyan
    Write-Host "Image: $ContainerImage" -ForegroundColor Gray
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
    $reportFile = Join-Path $OutputDir "trivy-report-$timestamp.$OutputFormat"
    
    try {
        # Pull Trivy if not available
        Write-Host "Ensuring Trivy is available..." -ForegroundColor Gray
        docker pull aquasec/trivy:latest | Out-Null
        
        $trivyArgs = @(
            "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", "${OutputDir}:/output",
            "aquasec/trivy:latest",
            "image",
            "--severity", $MinSeverity,
            "--format", $OutputFormat,
            "--output", "/output/trivy-report-$timestamp.$OutputFormat",
            $ContainerImage
        )
        
        Write-Host "Executing: docker $($trivyArgs -join ' ')" -ForegroundColor Gray
        
        docker @trivyArgs
        $trivyExitCode = $LASTEXITCODE
        
        # Analyze results
        $vulnerabilityCount = 0
        $highCount = 0
        $criticalCount = 0
        
        if ($OutputFormat -eq "json" -and (Test-Path $reportFile)) {
            $results = Get-Content $reportFile | ConvertFrom-Json
            
            if ($results.Results) {
                foreach ($result in $results.Results) {
                    if ($result.Vulnerabilities) {
                        $vulnerabilityCount += $result.Vulnerabilities.Count
                        $highCount += ($result.Vulnerabilities | Where-Object { $_.Severity -eq "HIGH" }).Count
                        $criticalCount += ($result.Vulnerabilities | Where-Object { $_.Severity -eq "CRITICAL" }).Count
                    }
                }
            }
        }
        
        Write-Host "Container scan completed:" -ForegroundColor Green
        Write-Host "  Total vulnerabilities: $vulnerabilityCount" -ForegroundColor Gray
        Write-Host "  High severity: $highCount" -ForegroundColor Gray
        Write-Host "  Critical severity: $criticalCount" -ForegroundColor Gray
        Write-Host "  Report: $reportFile" -ForegroundColor Gray
        
        return @{
            Type = "container"
            Success = $true
            VulnerabilityCount = $vulnerabilityCount
            HighCount = $highCount
            CriticalCount = $criticalCount
            ReportFile = $reportFile
            ExitCode = $trivyExitCode
        }
    }
    catch {
        Write-Host "❌ Container scan failed: $_" -ForegroundColor Red
        return @{
            Type = "container"
            Success = $false
            Error = $_.Exception.Message
        }
    }
}

function New-ScanSummary {
    param(
        [array]$ScanResults,
        [string]$OutputDir
    )
    
    $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
    $summaryFile = Join-Path $OutputDir "security-summary-$timestamp.json"
    
    $summary = @{
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
        scan_configuration = @{
            scan_type = $ScanType
            min_severity = $MinSeverity
            output_format = $OutputFormat
            fail_on_high = $FailOnHigh.IsPresent
            fail_on_critical = $FailOnCritical.IsPresent
        }
        results = $ScanResults
        overall_status = "success"
        recommendations = @()
    }
    
    # Calculate overall status and recommendations
    $totalHigh = ($ScanResults | ForEach-Object { $_.HighCount } | Measure-Object -Sum).Sum
    $totalCritical = ($ScanResults | ForEach-Object { $_.CriticalCount } | Measure-Object -Sum).Sum
    
    if ($totalCritical -gt 0) {
        $summary.overall_status = "critical"
        $summary.recommendations += "Address $totalCritical critical security issues immediately"
    } elseif ($totalHigh -gt 0) {
        $summary.overall_status = "warning"
        $summary.recommendations += "Review and address $totalHigh high-severity security issues"
    }
    
    # Add specific recommendations
    foreach ($result in $ScanResults) {
        if (-not $result.Success) {
            $summary.recommendations += "Fix $($result.Type) scan failure: $($result.Error)"
        }
    }
    
    $summary | ConvertTo-Json -Depth 4 | Set-Content -Path $summaryFile
    
    Write-Host ""
    Write-Host "Security Scan Summary:" -ForegroundColor Cyan
    Write-Host "  Overall Status: $($summary.overall_status.ToUpper())" -ForegroundColor $(
        switch ($summary.overall_status) {
            "success" { "Green" }
            "warning" { "Yellow" }
            "critical" { "Red" }
            default { "Gray" }
        }
    )
    Write-Host "  Total High Issues: $totalHigh" -ForegroundColor Gray
    Write-Host "  Total Critical Issues: $totalCritical" -ForegroundColor Gray
    Write-Host "  Summary Report: $summaryFile" -ForegroundColor Gray
    
    return $summary
}

# Main execution
try {
    if ($Help) {
        Show-Help
        exit 0
    }
    
    Write-Host ""
    Write-Host "TTRPG Center Security Scanning" -ForegroundColor Cyan
    Write-Host "==============================" -ForegroundColor Cyan
    Write-Host "Scan Type: $ScanType" -ForegroundColor White
    Write-Host "Min Severity: $MinSeverity" -ForegroundColor White
    Write-Host "Output Format: $OutputFormat" -ForegroundColor White
    Write-Host ""
    
    # Initialize
    $outputDir = Initialize-OutputDirectory -OutputDir $OutputDir
    Test-ScanningTools
    Install-SecurityTools
    
    $scanResults = @()
    
    # Run scans based on type
    switch ($ScanType) {
        "code" {
            $scanResults += Invoke-CodeScan -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
        }
        "dependencies" {
            $scanResults += Invoke-DependencyScan -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
        }
        "container" {
            $scanResults += Invoke-ContainerScan -ContainerImage $ContainerImage -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
        }
        "all" {
            $scanResults += Invoke-CodeScan -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
            $scanResults += Invoke-DependencyScan -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
            
            if ($ContainerImage) {
                $scanResults += Invoke-ContainerScan -ContainerImage $ContainerImage -OutputDir $outputDir -OutputFormat $OutputFormat -MinSeverity $MinSeverity
            } else {
                Write-Host "⚠️  Skipping container scan (no image specified)" -ForegroundColor Yellow
            }
        }
    }
    
    # Generate summary
    $summary = New-ScanSummary -ScanResults $scanResults -OutputDir $outputDir
    
    # Determine exit code based on findings and flags
    $exitCode = 0
    
    $totalHigh = ($scanResults | ForEach-Object { $_.HighCount } | Measure-Object -Sum).Sum
    $totalCritical = ($scanResults | ForEach-Object { $_.CriticalCount } | Measure-Object -Sum).Sum
    
    if ($FailOnCritical -and $totalCritical -gt 0) {
        Write-Host ""
        Write-Host "❌ Critical security issues found, failing as requested" -ForegroundColor Red
        $exitCode = 1
    } elseif ($FailOnHigh -and $totalHigh -gt 0) {
        Write-Host ""
        Write-Host "❌ High severity security issues found, failing as requested" -ForegroundColor Red
        $exitCode = 1
    } else {
        Write-Host ""
        Write-Host "✅ Security scanning completed successfully" -ForegroundColor Green
    }
    
    if ($summary.recommendations.Count -gt 0) {
        Write-Host ""
        Write-Host "Recommendations:" -ForegroundColor Yellow
        foreach ($rec in $summary.recommendations) {
            Write-Host "  • $rec" -ForegroundColor Gray
        }
    }
    
    exit $exitCode
}
catch {
    Write-Host ""
    Write-Host "❌ Security scanning failed: $_" -ForegroundColor Red
    exit 1
}