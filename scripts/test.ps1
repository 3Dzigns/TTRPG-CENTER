# test.ps1
# FR-006: Container Testing Script
# Runs comprehensive tests against containerized services

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("unit", "functional", "integration", "all")]
    [string]$TestType = "all",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,
    
    [Parameter(Mandatory=$false)]
    [switch]$StopOnFailure,
    
    [Parameter(Mandatory=$false)]
    [switch]$Verbose,
    
    [Parameter(Mandatory=$false)]
    [string]$TestPattern = $null
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ComposeFile = "docker-compose.$Env.yml"
$TestResults = @()

# Functions
function Write-Status {
    param([string]$Message, [string]$Level = "Info")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Level) {
        "Info" { Write-Host "[$timestamp] INFO: $Message" -ForegroundColor Green }
        "Warning" { Write-Host "[$timestamp] WARN: $Message" -ForegroundColor Yellow }
        "Error" { Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red }
        "Success" { Write-Host "[$timestamp] SUCCESS: $Message" -ForegroundColor Cyan }
        "Test" { Write-Host "[$timestamp] TEST: $Message" -ForegroundColor Magenta }
    }
}

function Test-Prerequisites {
    # Check if stack is running
    try {
        $runningContainers = docker ps --filter "name=ttrpg" --format "{{.Names}}"
        if (-not $runningContainers) {
            throw "No TTRPG containers are running. Please start the stack first with: .\scripts\deploy.ps1 -Action up"
        }
        Write-Status "Found running containers: $($runningContainers -join ', ')"
    }
    catch {
        throw "Failed to check running containers: $($_.Exception.Message)"
    }
    
    # Check Python test environment
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python is not available. Please ensure Python is installed and in PATH."
    }
}

function Test-StackHealth {
    Write-Status "Testing stack health..." -Level "Test"
    
    $healthUrl = "http://localhost:8000/healthz"
    $maxAttempts = 10
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                $health = $response.Content | ConvertFrom-Json
                
                Write-Status "Health check passed - Overall status: $($health.status)" -Level "Success"
                
                # Check individual services
                $failedServices = @()
                foreach ($service in $health.services.PSObject.Properties) {
                    $serviceStatus = $service.Value.status
                    if ($serviceStatus -notin @("healthy", "disabled", "configured")) {
                        $failedServices += "$($service.Name): $serviceStatus"
                    }
                    if ($Verbose) {
                        Write-Status "  $($service.Name): $serviceStatus"
                    }
                }
                
                if ($failedServices.Count -gt 0) {
                    Write-Status "Some services are not healthy: $($failedServices -join ', ')" -Level "Warning"
                    return $false
                }
                
                return $true
            }
        }
        catch {
            Write-Status "Health check attempt $($attempt + 1)/$maxAttempts failed: $($_.Exception.Message)"
        }
        
        $attempt++
        Start-Sleep -Seconds 3
    }
    
    Write-Status "Health check failed after $maxAttempts attempts" -Level "Error"
    return $false
}

function Test-DatabaseConnectivity {
    Write-Status "Testing database connectivity..." -Level "Test"
    
    try {
        # Test PostgreSQL
        $pgTestCmd = @("docker", "exec", "ttrpg-app-dev", "python", "-c", 
                      "from src_common.database_config import test_database_connection; print('PostgreSQL:', test_database_connection())")
        $pgResult = & $pgTestCmd[0] $pgTestCmd[1..($pgTestCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0 -and $pgResult -like "*True*") {
            Write-Status "PostgreSQL connectivity test passed" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "PostgreSQL Connectivity"; Status = "PASS"; Details = $pgResult }
        } else {
            Write-Status "PostgreSQL connectivity test failed" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "PostgreSQL Connectivity"; Status = "FAIL"; Details = $pgResult }
            return $false
        }
        
        # Test MongoDB
        $mongoTestCmd = @("docker", "exec", "ttrpg-app-dev", "python", "-c",
                         "from src_common.mongo_dictionary_service import get_dictionary_service; print('MongoDB:', get_dictionary_service().health_check())")
        $mongoResult = & $mongoTestCmd[0] $mongoTestCmd[1..($mongoTestCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "MongoDB connectivity test passed" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "MongoDB Connectivity"; Status = "PASS"; Details = $mongoResult }
        } else {
            Write-Status "MongoDB connectivity test failed" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "MongoDB Connectivity"; Status = "FAIL"; Details = $mongoResult }
            return $false
        }
        
        # Test Neo4j
        $neo4jTestCmd = @("docker", "exec", "ttrpg-app-dev", "python", "-c",
                         "from src_common.neo4j_graph_service import get_graph_service; print('Neo4j:', get_graph_service().health_check())")
        $neo4jResult = & $neo4jTestCmd[0] $neo4jTestCmd[1..($neo4jTestCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Neo4j connectivity test passed" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "Neo4j Connectivity"; Status = "PASS"; Details = $neo4jResult }
        } else {
            Write-Status "Neo4j connectivity test failed" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "Neo4j Connectivity"; Status = "FAIL"; Details = $neo4jResult }
            return $false
        }
        
        return $true
    }
    catch {
        Write-Status "Database connectivity tests failed: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Test-ApiEndpoints {
    Write-Status "Testing API endpoints..." -Level "Test"
    
    $endpoints = @(
        @{ Path = "/healthz"; Method = "GET"; ExpectedStatus = 200 },
        @{ Path = "/"; Method = "GET"; ExpectedStatus = 200 }
    )
    
    $allPassed = $true
    
    foreach ($endpoint in $endpoints) {
        try {
            $url = "http://localhost:8000$($endpoint.Path)"
            $response = Invoke-WebRequest -Uri $url -Method $endpoint.Method -TimeoutSec 10 -UseBasicParsing
            
            if ($response.StatusCode -eq $endpoint.ExpectedStatus) {
                Write-Status "Endpoint test passed: $($endpoint.Method) $($endpoint.Path)" -Level "Success"
                $TestResults += [PSCustomObject]@{ Test = "API $($endpoint.Method) $($endpoint.Path)"; Status = "PASS"; Details = "Status: $($response.StatusCode)" }
            } else {
                Write-Status "Endpoint test failed: $($endpoint.Method) $($endpoint.Path) - Expected $($endpoint.ExpectedStatus), got $($response.StatusCode)" -Level "Error"
                $TestResults += [PSCustomObject]@{ Test = "API $($endpoint.Method) $($endpoint.Path)"; Status = "FAIL"; Details = "Status: $($response.StatusCode)" }
                $allPassed = $false
            }
        }
        catch {
            Write-Status "Endpoint test error: $($endpoint.Method) $($endpoint.Path) - $($_.Exception.Message)" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "API $($endpoint.Method) $($endpoint.Path)"; Status = "ERROR"; Details = $_.Exception.Message }
            $allPassed = $false
        }
    }
    
    return $allPassed
}

function Test-ContainerSecurity {
    Write-Status "Testing container security..." -Level "Test"
    
    try {
        # Check if containers are running as non-root
        $containerSecurityCmd = @("docker", "exec", "ttrpg-app-dev", "whoami")
        $userResult = & $containerSecurityCmd[0] $containerSecurityCmd[1..($containerSecurityCmd.Length-1)]
        
        if ($userResult -eq "ttrpg") {
            Write-Status "Container security test passed: Running as non-root user" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "Container Security"; Status = "PASS"; Details = "User: $userResult" }
        } else {
            Write-Status "Container security test failed: Running as $userResult" -Level "Warning"
            $TestResults += [PSCustomObject]@{ Test = "Container Security"; Status = "WARN"; Details = "User: $userResult" }
        }
        
        # Check for no privileged containers
        $privilegedCheck = docker ps --filter "name=ttrpg" --format "{{.Names}}" | ForEach-Object {
            $inspect = docker inspect $_ | ConvertFrom-Json
            $privileged = $inspect[0].HostConfig.Privileged
            if ($privileged) {
                return "$_"
            }
        }
        
        if (-not $privilegedCheck) {
            Write-Status "Privilege check passed: No privileged containers" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "Privilege Check"; Status = "PASS"; Details = "No privileged containers" }
        } else {
            Write-Status "Privilege check failed: Privileged containers found: $($privilegedCheck -join ', ')" -Level "Warning"
            $TestResults += [PSCustomObject]@{ Test = "Privilege Check"; Status = "FAIL"; Details = "Privileged: $($privilegedCheck -join ', ')" }
        }
        
        return $true
    }
    catch {
        Write-Status "Container security tests failed: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Run-UnitTests {
    Write-Status "Running unit tests..." -Level "Test"
    
    try {
        $testCmd = @("docker", "exec", "ttrpg-app-dev", "python", "-m", "pytest", "tests/unit", "-v")
        
        if ($TestPattern) {
            $testCmd += "-k"
            $testCmd += $TestPattern
        }
        
        if ($Verbose) {
            $testCmd += "--tb=short"
        } else {
            $testCmd += "--tb=line"
        }
        
        & $testCmd[0] $testCmd[1..($testCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Unit tests passed" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "Unit Tests"; Status = "PASS"; Details = "All unit tests passed" }
            return $true
        } else {
            Write-Status "Unit tests failed" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "Unit Tests"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE" }
            return $false
        }
    }
    catch {
        Write-Status "Unit tests error: $($_.Exception.Message)" -Level "Error"
        $TestResults += [PSCustomObject]@{ Test = "Unit Tests"; Status = "ERROR"; Details = $_.Exception.Message }
        return $false
    }
}

function Run-FunctionalTests {
    Write-Status "Running functional tests..." -Level "Test"
    
    try {
        $testCmd = @("docker", "exec", "ttrpg-app-dev", "python", "-m", "pytest", "tests/functional", "-v")
        
        if ($TestPattern) {
            $testCmd += "-k"
            $testCmd += $TestPattern
        }
        
        if ($Verbose) {
            $testCmd += "--tb=short"
        } else {
            $testCmd += "--tb=line"
        }
        
        & $testCmd[0] $testCmd[1..($testCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Functional tests passed" -Level "Success"
            $TestResults += [PSCustomObject]@{ Test = "Functional Tests"; Status = "PASS"; Details = "All functional tests passed" }
            return $true
        } else {
            Write-Status "Functional tests failed" -Level "Error"
            $TestResults += [PSCustomObject]@{ Test = "Functional Tests"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE" }
            return $false
        }
    }
    catch {
        Write-Status "Functional tests error: $($_.Exception.Message)" -Level "Error"
        $TestResults += [PSCustomObject]@{ Test = "Functional Tests"; Status = "ERROR"; Details = $_.Exception.Message }
        return $false
    }
}

function Show-TestSummary {
    Write-Status "`nTest Summary:" -Level "Success"
    Write-Status "=" * 80 -Level "Success"
    
    $passed = ($TestResults | Where-Object { $_.Status -eq "PASS" }).Count
    $failed = ($TestResults | Where-Object { $_.Status -eq "FAIL" }).Count
    $errors = ($TestResults | Where-Object { $_.Status -eq "ERROR" }).Count
    $warnings = ($TestResults | Where-Object { $_.Status -eq "WARN" }).Count
    
    Write-Status "Total Tests: $($TestResults.Count)" -Level "Success"
    Write-Status "Passed: $passed" -Level "Success"
    if ($failed -gt 0) { Write-Status "Failed: $failed" -Level "Error" }
    if ($errors -gt 0) { Write-Status "Errors: $errors" -Level "Error" }
    if ($warnings -gt 0) { Write-Status "Warnings: $warnings" -Level "Warning" }
    
    Write-Status "`nDetailed Results:" -Level "Info"
    $TestResults | Format-Table -Property Test, Status, Details -AutoSize
    
    return ($failed + $errors) -eq 0
}

# Main execution
try {
    Write-Status "TTRPG Center Container Testing Script"
    Write-Status "Environment: $Env, Test Type: $TestType"
    
    # Change to project root
    Set-Location $ProjectRoot
    Write-Status "Working directory: $ProjectRoot"
    
    # Check prerequisites
    Test-Prerequisites
    
    # Initialize test results
    $TestResults = @()
    $allTestsPassed = $true
    
    # Always start with health checks
    if (-not (Test-StackHealth)) {
        if ($StopOnFailure) {
            throw "Stack health check failed"
        } else {
            $allTestsPassed = $false
        }
    }
    
    # Run integration tests (basic connectivity and security)
    if ($TestType -in @("integration", "all")) {
        Write-Status "`nRunning integration tests..." -Level "Test"
        
        if (-not (Test-DatabaseConnectivity)) {
            if ($StopOnFailure) {
                throw "Database connectivity tests failed"
            } else {
                $allTestsPassed = $false
            }
        }
        
        if (-not (Test-ApiEndpoints)) {
            if ($StopOnFailure) {
                throw "API endpoint tests failed"
            } else {
                $allTestsPassed = $false
            }
        }
        
        if (-not (Test-ContainerSecurity)) {
            if ($StopOnFailure) {
                throw "Container security tests failed"
            } else {
                $allTestsPassed = $false
            }
        }
    }
    
    # Run unit tests
    if ($TestType -in @("unit", "all")) {
        Write-Status "`nRunning unit tests..." -Level "Test"
        
        if (-not (Run-UnitTests)) {
            if ($StopOnFailure) {
                throw "Unit tests failed"
            } else {
                $allTestsPassed = $false
            }
        }
    }
    
    # Run functional tests
    if ($TestType -in @("functional", "all")) {
        Write-Status "`nRunning functional tests..." -Level "Test"
        
        if (-not (Run-FunctionalTests)) {
            if ($StopOnFailure) {
                throw "Functional tests failed"
            } else {
                $allTestsPassed = $false
            }
        }
    }
    
    # Show test summary
    $summaryPassed = Show-TestSummary
    
    if ($allTestsPassed -and $summaryPassed) {
        Write-Status "`nAll tests completed successfully!" -Level "Success"
        exit 0
    } else {
        Write-Status "`nSome tests failed. Check the summary above for details." -Level "Error"
        exit 1
    }
}
catch {
    Write-Status "Testing failed: $($_.Exception.Message)" -Level "Error"
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}