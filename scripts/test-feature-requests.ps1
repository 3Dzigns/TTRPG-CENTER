# test-feature-requests.ps1
# Comprehensive Feature Request Test Runner
# Runs all feature request regression tests for TTRPG Center

param(
    [Parameter(Mandatory=$false)]
    [string]$FeatureRequest = "all", # e.g., "FR-020" or "all"

    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",

    [Parameter(Mandatory=$false)]
    [switch]$Verbose,

    [Parameter(Mandatory=$false)]
    [switch]$StopOnFailure,

    [Parameter(Mandatory=$false)]
    [string]$TestPattern = $null,

    [Parameter(Mandatory=$false)]
    [ValidateSet("console", "json", "html")]
    [string]$OutputFormat = "console",

    [Parameter(Mandatory=$false)]
    [string]$OutputPath = $null
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StartTime = Get-Date

# Colors for output
$Colors = @{
    "INFO" = "Green"
    "TEST" = "Magenta"
    "FR" = "Blue"
    "PASS" = "Green"
    "FAIL" = "Red"
    "SKIP" = "Yellow"
    "ERROR" = "Red"
    "SUCCESS" = "Cyan"
}

function Write-TestLog {
    param(
        [string]$Message,
        [ValidateSet("INFO", "TEST", "FR", "PASS", "FAIL", "SKIP", "ERROR", "SUCCESS")]
        [string]$Level = "INFO",
        [int]$Indent = 0
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $indentStr = "  " * $Indent
    $color = $Colors[$Level]

    $logLine = "[$timestamp] $Level: $indentStr$Message"
    Write-Host $logLine -ForegroundColor $color
}

function Test-ContainerPrerequisites {
    Write-TestLog "Checking Docker container prerequisites..." -Level "INFO"

    # Check if Docker is available
    try {
        $dockerVersion = docker --version
        Write-TestLog "Docker version: $dockerVersion" -Level "INFO" -Indent 1
    }
    catch {
        throw "Docker is not available. Please ensure Docker Desktop is running."
    }

    # Check if dev containers are running
    try {
        $runningContainers = docker ps --filter "name=ttrpg" --format "{{.Names}}"
        if (-not $runningContainers) {
            throw "No TTRPG containers are running. Please start the dev environment first with: .\scripts\deploy.ps1 -Action up"
        }
        Write-TestLog "Found running containers: $($runningContainers -join ', ')" -Level "INFO" -Indent 1
    }
    catch {
        throw "Failed to check running containers: $($_.Exception.Message)"
    }

    # Test dev container health
    Write-TestLog "Testing dev container health..." -Level "TEST" -Indent 1
    try {
        $healthCheck = docker exec ttrpg-app-dev-local python -c "print('Container ready')"
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "Dev container health check: PASS" -Level "PASS" -Indent 2
        } else {
            throw "Dev container health check failed"
        }
    }
    catch {
        throw "Dev container is not responding: $($_.Exception.Message)"
    }
}

function Get-FeatureRequestTests {
    # Define all available feature request tests
    $allFeatureTests = @(
        # Gating and validation tests
        @{ Pattern = "Passed D-G"; TestFile = "tests/regression/feature_requests/test_passed_dg_validation.py"; Description = "Pass D-G Pipeline Validation" },
        @{ Pattern = "Initial Gating"; TestFile = "tests/regression/feature_requests/test_initial_gating.py"; Description = "Initial Gating Mechanisms" },

        # Infrastructure and pipeline tests
        @{ Pattern = "FR-002"; TestFile = "tests/regression/feature_requests/test_fr002_nightly_ingestion.py"; Description = "Nightly Ingestion Workflow" },
        @{ Pattern = "FR-005"; TestFile = "tests/regression/feature_requests/test_fr005_modular_ingestion.py"; Description = "Modular Ingestion Pipeline" },
        @{ Pattern = "FR-028"; TestFile = "tests/regression/feature_requests/test_fr028_eval_gates.py"; Description = "Evaluation Gates" },

        # Search and data feature tests
        @{ Pattern = "FR-009"; TestFile = "tests/regression/feature_requests/test_fr009_semantic_search.py"; Description = "Semantic Search Capabilities" },
        @{ Pattern = "FR-010"; TestFile = "tests/regression/feature_requests/test_fr010_advanced_filters.py"; Description = "Advanced Filtering and Faceted Search" },
        @{ Pattern = "FR-011"; TestFile = "tests/regression/feature_requests/test_fr011_content_recommendations.py"; Description = "Content Recommendation Engine" },
        @{ Pattern = "FR-012"; TestFile = "tests/regression/feature_requests/test_fr012_export_sharing.py"; Description = "Export and Sharing Capabilities" },
        @{ Pattern = "FR-013"; TestFile = "tests/regression/feature_requests/test_fr013_offline_capabilities.py"; Description = "Offline Access and Sync" },
        @{ Pattern = "FR-014"; TestFile = "tests/regression/feature_requests/test_fr014_mobile_responsive.py"; Description = "Mobile-Responsive Design" },

        # UI/UX feature tests
        @{ Pattern = "FR-016"; TestFile = "tests/regression/feature_requests/test_fr016_admin_dashboard.py"; Description = "Admin Dashboard and Management" },
        @{ Pattern = "FR-017"; TestFile = "tests/regression/feature_requests/test_fr017_user_preferences.py"; Description = "User Preferences and Personalization" },
        @{ Pattern = "FR-018"; TestFile = "tests/regression/feature_requests/test_fr018_accessibility_features.py"; Description = "Accessibility Features and Compliance" },
        @{ Pattern = "FR-019"; TestFile = "tests/regression/feature_requests/test_fr019_multi_language.py"; Description = "Multi-language Support and Localization" },

        # AI and analytics tests
        @{ Pattern = "FR-020"; TestFile = "tests/regression/feature_requests/test_fr020_ai_chatbot.py"; Description = "AI-Powered Chatbot Integration" }
    )

    if ($FeatureRequest -eq "all") {
        return $allFeatureTests
    } else {
        return $allFeatureTests | Where-Object { $_.Pattern -eq $FeatureRequest }
    }
}

function Invoke-FeatureRequestTest {
    param($TestDefinition)

    Write-TestLog "Testing $($TestDefinition.Pattern): $($TestDefinition.Description)..." -Level "FR" -Indent 1

    try {
        # Check if test file exists
        $testFile = $TestDefinition.TestFile
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "test", "-f", "/app/$testFile")
        & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            # Run the test
            $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", $testFile, "-v")
            if ($TestPattern) {
                $testCmd += "-k"
                $testCmd += $TestPattern
            }
            if ($Verbose) {
                $testCmd += "--tb=short"
            } else {
                $testCmd += "--tb=line"
            }

            Write-TestLog "Running: pytest $testFile" -Level "TEST" -Indent 2
            $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1

            if ($LASTEXITCODE -eq 0) {
                Write-TestLog "$($TestDefinition.Pattern): PASS" -Level "PASS" -Indent 2
                return @{
                    Test = "$($TestDefinition.Pattern): $($TestDefinition.Description)"
                    Status = "PASS"
                    Details = "Feature request test completed successfully"
                    Output = $output -join "`n"
                    Duration = 0
                }
            } else {
                Write-TestLog "$($TestDefinition.Pattern): FAIL" -Level "FAIL" -Indent 2
                if ($Verbose) {
                    Write-TestLog "Test output:" -Level "INFO" -Indent 3
                    $output | ForEach-Object { Write-TestLog $_ -Level "INFO" -Indent 4 }
                }
                return @{
                    Test = "$($TestDefinition.Pattern): $($TestDefinition.Description)"
                    Status = "FAIL"
                    Details = "Exit code: $LASTEXITCODE"
                    Output = $output -join "`n"
                    Duration = 0
                }
            }
        } else {
            Write-TestLog "$($TestDefinition.Pattern): SKIP - Test file not found: $testFile" -Level "SKIP" -Indent 2
            return @{
                Test = "$($TestDefinition.Pattern): $($TestDefinition.Description)"
                Status = "SKIP"
                Details = "Test file not found: $testFile"
                Output = ""
                Duration = 0
            }
        }
    }
    catch {
        Write-TestLog "$($TestDefinition.Pattern): ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 2
        return @{
            Test = "$($TestDefinition.Pattern): $($TestDefinition.Description)"
            Status = "ERROR"
            Details = $_.Exception.Message
            Output = ""
            Duration = 0
        }
    }
}

function Generate-TestReport {
    param($Results)

    $totalDuration = (Get-Date) - $StartTime
    $totalPassed = ($Results | Where-Object { $_.Status -eq "PASS" }).Count
    $totalFailed = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
    $totalErrors = ($Results | Where-Object { $_.Status -eq "ERROR" }).Count
    $totalSkipped = ($Results | Where-Object { $_.Status -eq "SKIP" }).Count
    $totalTests = $Results.Count

    # Console report
    Write-TestLog "=" * 100 -Level "SUCCESS"
    Write-TestLog "FEATURE REQUEST TEST SUITE FINAL REPORT" -Level "SUCCESS"
    Write-TestLog "=" * 100 -Level "SUCCESS"
    Write-TestLog "Total Execution Time: $('{0:F1}' -f $totalDuration.TotalMinutes) minutes" -Level "INFO"
    Write-TestLog "Total Tests: $totalTests" -Level "INFO"
    Write-TestLog "Passed: $totalPassed" -Level "PASS"
    if ($totalFailed -gt 0) { Write-TestLog "Failed: $totalFailed" -Level "FAIL" }
    if ($totalErrors -gt 0) { Write-TestLog "Errors: $totalErrors" -Level "ERROR" }
    if ($totalSkipped -gt 0) { Write-TestLog "Skipped: $totalSkipped" -Level "SKIP" }

    # Detailed results
    Write-TestLog "`nDetailed Results:" -Level "INFO"
    $Results | ForEach-Object {
        $status = $_.Status
        $levelColor = switch ($status) {
            "PASS" { "PASS" }
            "FAIL" { "FAIL" }
            "ERROR" { "ERROR" }
            "SKIP" { "SKIP" }
            default { "INFO" }
        }
        Write-TestLog "$($_.Test): $status" -Level $levelColor -Indent 1
        if ($Verbose -and $_.Details) {
            Write-TestLog "Details: $($_.Details)" -Level "INFO" -Indent 2
        }
    }

    # Generate structured output if requested
    if ($OutputFormat -eq "json" -or $OutputPath) {
        $reportData = @{
            "Summary" = @{
                "TotalTests" = $totalTests
                "Passed" = $totalPassed
                "Failed" = $totalFailed
                "Errors" = $totalErrors
                "Skipped" = $totalSkipped
                "Duration" = $totalDuration.TotalMinutes
                "StartTime" = $StartTime
                "EndTime" = Get-Date
            }
            "Results" = $Results
        }

        if ($OutputFormat -eq "json") {
            $reportJson = $reportData | ConvertTo-Json -Depth 10
            if ($OutputPath) {
                $reportJson | Set-Content -Path $OutputPath
                Write-TestLog "JSON report saved to: $OutputPath" -Level "INFO"
            } else {
                Write-Host $reportJson
            }
        }

        if ($OutputFormat -eq "html") {
            if (-not $OutputPath) {
                $OutputPath = Join-Path $ProjectRoot "test_results" "fr_test_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').html"
            }
            Generate-HtmlReport -ReportData $reportData -OutputPath $OutputPath
            Write-TestLog "HTML report generated: $OutputPath" -Level "INFO"
        }
    }

    return ($totalFailed + $totalErrors) -eq 0
}

function Generate-HtmlReport {
    param($ReportData, $OutputPath)

    $htmlContent = @"
<!DOCTYPE html>
<html>
<head>
    <title>TTRPG Center Feature Request Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; border-radius: 8px; }
        .summary { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .results { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .test-item { padding: 15px; border-bottom: 1px solid #ecf0f1; display: flex; justify-content: space-between; align-items: center; }
        .test-item:last-child { border-bottom: none; }
        .test-name { font-weight: bold; flex-grow: 1; }
        .test-status { padding: 4px 12px; border-radius: 4px; color: white; font-weight: bold; }
        .pass { background-color: #27ae60; }
        .fail { background-color: #e74c3c; }
        .error { background-color: #8e44ad; }
        .skip { background-color: #f39c12; }
        .summary-stats { display: flex; justify-content: space-around; margin: 20px 0; }
        .stat-item { text-align: center; }
        .stat-number { font-size: 24px; font-weight: bold; }
        .stat-label { color: #7f8c8d; }
    </style>
</head>
<body>
    <div class="header">
        <h1>TTRPG Center Feature Request Test Report</h1>
        <p>Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')</p>
    </div>

    <div class="summary">
        <h2>Test Summary</h2>
        <div class="summary-stats">
            <div class="stat-item">
                <div class="stat-number">$($ReportData.Summary.TotalTests)</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" style="color: #27ae60;">$($ReportData.Summary.Passed)</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" style="color: #e74c3c;">$($ReportData.Summary.Failed)</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" style="color: #8e44ad;">$($ReportData.Summary.Errors)</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" style="color: #f39c12;">$($ReportData.Summary.Skipped)</div>
                <div class="stat-label">Skipped</div>
            </div>
        </div>
        <p><strong>Duration:</strong> $('{0:F1}' -f $ReportData.Summary.Duration) minutes</p>
    </div>

    <div class="results">
        <h2>Test Results</h2>
"@

    # Add test results
    foreach ($result in $ReportData.Results) {
        $statusClass = $result.Status.ToLower()
        $htmlContent += @"
        <div class="test-item">
            <div class="test-name">$($result.Test)</div>
            <div class="test-status $statusClass">$($result.Status)</div>
        </div>
"@
    }

    $htmlContent += @"
    </div>
</body>
</html>
"@

    # Ensure directory exists
    $reportDir = Split-Path $OutputPath -Parent
    if (-not (Test-Path $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }

    $htmlContent | Set-Content -Path $OutputPath
}

# Main execution
try {
    Write-TestLog "TTRPG Center Feature Request Test Runner" -Level "SUCCESS"
    Write-TestLog "Feature Request: $FeatureRequest, Environment: $Env" -Level "INFO"

    # Change to project root
    Set-Location $ProjectRoot
    Write-TestLog "Working directory: $ProjectRoot" -Level "INFO"

    # Check prerequisites
    Test-ContainerPrerequisites

    # Get tests to run
    $testsToRun = Get-FeatureRequestTests
    if (-not $testsToRun) {
        throw "No tests found for feature request pattern: $FeatureRequest"
    }

    Write-TestLog "Found $($testsToRun.Count) feature request tests to run" -Level "INFO"

    # Run tests
    $allResults = @()
    foreach ($test in $testsToRun) {
        $result = Invoke-FeatureRequestTest -TestDefinition $test
        $allResults += $result

        if ($result.Status -eq "FAIL" -and $StopOnFailure) {
            throw "Test failed and -StopOnFailure specified: $($result.Test)"
        }
    }

    # Generate report
    $success = Generate-TestReport -Results $allResults

    if ($success) {
        Write-TestLog "`nAll feature request tests completed successfully!" -Level "SUCCESS"
        exit 0
    } else {
        Write-TestLog "`nSome tests failed. Check the detailed report above." -Level "ERROR"
        exit 1
    }
}
catch {
    Write-TestLog "Feature request testing failed: $($_.Exception.Message)" -Level "ERROR"
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}