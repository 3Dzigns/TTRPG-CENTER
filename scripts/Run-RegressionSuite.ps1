# Run-RegressionSuite.ps1
# Full Regression Test Suite for TTRPG Center
# Tests all 7 Phases and Feature Requests against the Dev Docker container instance

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("0", "1", "2", "3", "4", "5", "6", "7", "all")]
    [string]$Phase = "all",

    [Parameter(Mandatory=$false)]
    [string]$FeatureRequest = "all", # e.g., "FR-001" or "all"

    [Parameter(Mandatory=$false)]
    [switch]$DetailedLogging,

    [Parameter(Mandatory=$false)]
    [switch]$StopOnFailure,

    [Parameter(Mandatory=$false)]
    [ValidateSet("console", "json", "xml", "html")]
    [string]$OutputFormat = "console",

    [Parameter(Mandatory=$false)]
    [switch]$GenerateReport,

    [Parameter(Mandatory=$false)]
    [string]$TestPattern = $null,

    [Parameter(Mandatory=$false)]
    [string]$OutputPath = $null
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$TestResults = @()
$StartTime = Get-Date

# Color coding for different log levels
$Colors = @{
    "INFO" = "Green"
    "TEST" = "Magenta"
    "PHASE" = "Cyan"
    "FR" = "Blue"
    "PASS" = "Green"
    "FAIL" = "Red"
    "SKIP" = "Yellow"
    "PERF" = "DarkCyan"
    "VALIDATE" = "DarkGreen"
    "ERROR" = "Red"
    "WARNING" = "Yellow"
    "SUCCESS" = "Cyan"
}

# Functions
function Write-TestLog {
    param(
        [string]$Message,
        [ValidateSet("INFO", "TEST", "PHASE", "FR", "PASS", "FAIL", "SKIP", "PERF", "VALIDATE", "ERROR", "WARNING", "SUCCESS")]
        [string]$Level = "INFO",
        [int]$Indent = 0
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $indentStr = "  " * $Indent
    $color = $Colors[$Level]

    $logLine = "[$timestamp] ${Level}: $indentStr$Message"
    Write-Host $logLine -ForegroundColor $color

    # Also log to file if detailed logging enabled
    if ($DetailedLogging -and $script:LogFile) {
        Add-Content -Path $script:LogFile -Value $logLine
    }
}

function Initialize-TestEnvironment {
    Write-TestLog "Initializing TTRPG Center Regression Test Suite" -Level "SUCCESS"
    Write-TestLog "Phase: $Phase, Feature Request: $FeatureRequest" -Level "INFO"
    Write-TestLog "Working Directory: $ProjectRoot" -Level "INFO"

    # Set up logging
    if ($DetailedLogging) {
        $script:LogFile = Join-Path $ProjectRoot "test_results" "regression_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
        $logDir = Split-Path $script:LogFile -Parent
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        Write-TestLog "Detailed logging enabled: $script:LogFile" -Level "INFO"
    }

    # Change to project root
    Set-Location $ProjectRoot

    # Initialize test results
    $script:TestResults = @()
    $script:PhaseResults = @{}
    $script:FeatureResults = @{}
}

function Test-ContainerPrerequisites {
    Write-TestLog "Validating Docker container prerequisites..." -Level "INFO"

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
            throw "No TTRPG containers are running. Please start the dev environment first."
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

    # Test application health endpoint
    Write-TestLog "Testing application health endpoint..." -Level "TEST" -Indent 1
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-TestLog "Application health endpoint: PASS" -Level "PASS" -Indent 2
        } else {
            Write-TestLog "Application health endpoint returned: $($response.StatusCode)" -Level "WARNING" -Indent 2
        }
    }
    catch {
        Write-TestLog "Application health endpoint: FAIL - $($_.Exception.Message)" -Level "WARNING" -Indent 2
    }
}

function Invoke-PhaseTests {
    param([string]$PhaseNumber)

    $separator = "=" * 80
    Write-TestLog $separator -Level "PHASE"
    Write-TestLog "PHASE $PhaseNumber REGRESSION TESTS" -Level "PHASE"
    Write-TestLog $separator -Level "PHASE"

    $phaseStartTime = Get-Date
    $phasePassed = 0
    $phaseFailed = 0
    $phaseSkipped = 0

    switch ($PhaseNumber) {
        "0" {
            Write-TestLog "Testing Phase 0: Environment Isolation & Bootstrap" -Level "PHASE" -Indent 1
            $results = Test-Phase0
        }
        "1" {
            Write-TestLog "Testing Phase 1: Seven-Pass Ingestion Pipeline (Lane A)" -Level "PHASE" -Indent 1
            $results = Test-Phase1
        }
        "2" {
            Write-TestLog "Testing Phase 2: RAG Retrieval & Model Routing" -Level "PHASE" -Indent 1
            $results = Test-Phase2
        }
        "3" {
            Write-TestLog "Testing Phase 3: Graph Workflows & Reasoning" -Level "PHASE" -Indent 1
            $results = Test-Phase3
        }
        "4" {
            Write-TestLog "Testing Phase 4: Admin UI & Operational Tools" -Level "PHASE" -Indent 1
            $results = Test-Phase4
        }
        "5" {
            Write-TestLog "Testing Phase 5: User UI with LCARS Design" -Level "PHASE" -Indent 1
            $results = Test-Phase5
        }
        "6" {
            Write-TestLog "Testing Phase 6: Testing & Feedback Automation" -Level "PHASE" -Indent 1
            $results = Test-Phase6
        }
        "7" {
            Write-TestLog "Testing Phase 7: Requirements Management" -Level "PHASE" -Indent 1
            $results = Test-Phase7
        }
        default {
            throw "Invalid phase number: $PhaseNumber"
        }
    }

    # Calculate phase summary
    $phaseDuration = (Get-Date) - $phaseStartTime
    $phasePassed = ($results | Where-Object { $_.Status -eq "PASS" }).Count
    $phaseFailed = ($results | Where-Object { $_.Status -eq "FAIL" }).Count
    $phaseSkipped = ($results | Where-Object { $_.Status -eq "SKIP" }).Count

    # Store phase results
    $script:PhaseResults["Phase$($PhaseNumber.ToString())"] = @{
        "Passed" = $phasePassed
        "Failed" = $phaseFailed
        "Skipped" = $phaseSkipped
        "Duration" = $phaseDuration
        "Tests" = $results
    }

    Write-TestLog "Phase $PhaseNumber Summary: $phasePassed passed, $phaseFailed failed, $phaseSkipped skipped ($('{0:F1}' -f $phaseDuration.TotalSeconds)s)" -Level "INFO" -Indent 1

    if ($phaseFailed -gt 0 -and $StopOnFailure) {
        throw "Phase $PhaseNumber failed with $phaseFailed failures. Stopping due to -StopOnFailure flag."
    }

    return $results
}

function Test-Phase0 {
    Write-TestLog "Running Phase 0 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # US ARCH-001: Environment isolation validation
    try {
        Write-TestLog "US ARCH-001: Testing environment directory isolation..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase0/test_arch001_isolation.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US ARCH-001: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "US ARCH-001 Environment Isolation"; Status = "PASS"; Details = "Directory isolation validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US ARCH-001: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US ARCH-001 Environment Isolation"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US ARCH-001: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US ARCH-001 Environment Isolation"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US ARCH-002: Health probe validation
    try {
        Write-TestLog "US ARCH-002: Testing health probe functionality..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase0/test_arch002_health.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US ARCH-002: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "US ARCH-002 Health Probe"; Status = "PASS"; Details = "Health probe validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US ARCH-002: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US ARCH-002 Health Probe"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US ARCH-002: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US ARCH-002 Health Probe"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US LOG-001: Structured logging validation
    try {
        Write-TestLog "US LOG-001: Testing structured JSON logging..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase0/test_log001_structured.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US LOG-001: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "US LOG-001 Structured Logging"; Status = "PASS"; Details = "JSON logging validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US LOG-001: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US LOG-001 Structured Logging"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US LOG-001: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US LOG-001 Structured Logging"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase1 {
    Write-TestLog "Running Phase 1 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # US RAG-001A: Pass A with unstructured.io (PDF parsing & ToC extraction) - HARD GATE
    try {
        Write-TestLog "US RAG-001A: Testing Pass A with unstructured.io (PDF parsing)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001a_parse.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001A: PASS - PDF parsing integration validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001A PDF Parse/ToC"; Status = "PASS"; Details = "unstructured.io PDF parsing validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001A: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001A PDF Parse/ToC"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001A: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001A PDF Parse/ToC"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001B: Pass B with PyPDF (logical splitting for large files) - HARD GATE
    try {
        Write-TestLog "US RAG-001B: Testing Pass B with PyPDF (logical splitting)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001b_logical_split.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001B: PASS - Logical splitting integration validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001B Logical Split"; Status = "PASS"; Details = "PyPDF logical splitting validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001B: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001B Logical Split"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001B: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001B Logical Split"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001C: Pass C with unstructured.io (content extraction & chunking) - HARD GATE
    try {
        Write-TestLog "US RAG-001C: Testing Pass C with unstructured.io (content extraction)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001c_extraction.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001C: PASS - Content extraction integration validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001C Content Extract"; Status = "PASS"; Details = "unstructured.io content extraction validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001C: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001C Content Extract"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001C: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001C Content Extract"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001D: Pass D with Haystack (vector enrichment & NER) - HARD GATE
    try {
        Write-TestLog "US RAG-001D: Testing Pass D with Haystack (vector enrichment)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001d_vector_enrichment.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001D: PASS - Vector enrichment integration validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001D Vector Enrich"; Status = "PASS"; Details = "Haystack vector enrichment validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001D: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001D Vector Enrich"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001D: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001D Vector Enrich"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001E: Pass E with LlamaIndex (graph building & cross-references) - HARD GATE
    try {
        Write-TestLog "US RAG-001E: Testing Pass E with LlamaIndex (graph building)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001e_graph_builder.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001E: PASS - Graph building integration validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001E Graph Build"; Status = "PASS"; Details = "LlamaIndex graph building validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001E: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001E Graph Build"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001E: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001E Graph Build"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001F: Pass F (finalization & cleanup) - HARD GATE
    try {
        Write-TestLog "US RAG-001F: Testing Pass F (finalization & cleanup)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001f_finalizer.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001F: PASS - Finalization & cleanup validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001F Finalization"; Status = "PASS"; Details = "Finalization & cleanup validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001F: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001F Finalization"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001F: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001F Finalization"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US RAG-001G: Pass G with HGRN (validation & quality gates) - HARD GATE
    try {
        Write-TestLog "US RAG-001G: Testing Pass G with HGRN (validation & quality gates)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase1/test_rag001g_hgrn_validation.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US RAG-001G: PASS - HGRN validation & quality gates validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US RAG-001G HGRN Validation"; Status = "PASS"; Details = "HGRN validation & quality gates validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US RAG-001G: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US RAG-001G HGRN Validation"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US RAG-001G: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US RAG-001G HGRN Validation"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase2 {
    Write-TestLog "Running Phase 2 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # US-201: Query Intent Classifier with performance requirement
    try {
        Write-TestLog "US-201: Testing Query Intent Classifier (p95 <150ms)..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase2/test_us201_qic.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $perfStart = Get-Date
        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        $perfEnd = Get-Date
        $duration = ($perfEnd - $perfStart).TotalMilliseconds

        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US-201: PASS - Classification accuracy and performance validated" -Level "PASS" -Indent 4
            Write-TestLog "Performance: $($duration)ms (target: <150ms p95)" -Level "PERF" -Indent 5
            $results += @{ Test = "US-201 Query Intent Classifier"; Status = "PASS"; Details = "F1≥0.85, p95<150ms validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US-201: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US-201 Query Intent Classifier"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US-201: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US-201 Query Intent Classifier"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    # US-202: Retrieval Policy Engine
    try {
        Write-TestLog "US-202: Testing Retrieval Policy Engine..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase2/test_us202_rpe.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US-202: PASS - Policy mapping and hot-reload validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US-202 Retrieval Policy Engine"; Status = "PASS"; Details = "YAML hot-reload and policy mapping validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US-202: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US-202 Retrieval Policy Engine"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US-202: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US-202 Retrieval Policy Engine"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase3 {
    Write-TestLog "Running Phase 3 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # US-301: Graph Schema & Store
    try {
        Write-TestLog "US-301: Testing Graph Schema & Store..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase3/test_us301_graph_store.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "US-301: PASS - Graph CRUD operations validated" -Level "PASS" -Indent 4
            $results += @{ Test = "US-301 Graph Schema & Store"; Status = "PASS"; Details = "CRUD operations and schema validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "US-301: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "US-301 Graph Schema & Store"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "US-301: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "US-301 Graph Schema & Store"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase4 {
    Write-TestLog "Running Phase 4 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # Admin UI functionality
    try {
        Write-TestLog "Testing Admin UI functionality..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase4/test_admin_ui.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "Admin UI: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "Phase 4 Admin UI"; Status = "PASS"; Details = "Admin interface validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "Admin UI: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "Phase 4 Admin UI"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "Admin UI: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "Phase 4 Admin UI"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase5 {
    Write-TestLog "Running Phase 5 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # User UI with LCARS design
    try {
        Write-TestLog "Testing User UI with LCARS design..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase5/test_user_ui.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "User UI: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "Phase 5 User UI"; Status = "PASS"; Details = "LCARS interface validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "User UI: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "Phase 5 User UI"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "User UI: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "Phase 5 User UI"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase6 {
    Write-TestLog "Running Phase 6 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # Testing & feedback automation
    try {
        Write-TestLog "Testing feedback automation systems..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase6/test_feedback.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "Feedback Systems: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "Phase 6 Feedback Systems"; Status = "PASS"; Details = "Automation validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "Feedback Systems: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "Phase 6 Feedback Systems"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "Feedback Systems: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "Phase 6 Feedback Systems"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Test-Phase7 {
    Write-TestLog "Running Phase 7 tests in dev container..." -Level "TEST" -Indent 2

    $results = @()

    # Requirements management
    try {
        Write-TestLog "Testing requirements management..." -Level "TEST" -Indent 3
        $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", "tests/regression/phase7/test_requirements.py", "-v")
        if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

        $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-TestLog "Requirements Management: PASS" -Level "PASS" -Indent 4
            $results += @{ Test = "Phase 7 Requirements Management"; Status = "PASS"; Details = "Requirements tracking validated"; Output = $output -join "`n" }
        } else {
            Write-TestLog "Requirements Management: FAIL" -Level "FAIL" -Indent 4
            $results += @{ Test = "Phase 7 Requirements Management"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
        }
    }
    catch {
        Write-TestLog "Requirements Management: ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 4
        $results += @{ Test = "Phase 7 Requirements Management"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
    }

    return $results
}

function Invoke-FeatureRequestTests {
    param([string]$FRPattern)

    $separator = "=" * 80
    Write-TestLog $separator -Level "FR"
    Write-TestLog "FEATURE REQUEST REGRESSION TESTS" -Level "FR"
    Write-TestLog $separator -Level "FR"

    $frStartTime = Get-Date
    $frResults = @()

    if ($FRPattern -eq "all") {
        # Test all comprehensive feature requests from new test suite
        $featureRequestTests = @(
            # Legacy tests (if they exist)
            @{ Pattern = "FR-001"; TestFile = "tests/regression/feature_requests/test_fr001_*.py"; Description = "Platform Architecture" },
            @{ Pattern = "FR-008"; TestFile = "tests/regression/feature_requests/test_fr008_*.py"; Description = "API Framework" },
            @{ Pattern = "FR-015"; TestFile = "tests/regression/feature_requests/test_fr015_*.py"; Description = "User Interface" },

            # Comprehensive new test suite - All FR tests
            @{ Pattern = "FR-002"; TestFile = "tests/regression/feature_requests/test_fr002_nightly_ingestion.py"; Description = "Nightly Ingestion Workflow" },
            @{ Pattern = "FR-003"; TestFile = "tests/regression/feature_requests/test_fr003_distributed_storage.py"; Description = "Distributed Storage Architecture" },
            @{ Pattern = "FR-004"; TestFile = "tests/regression/feature_requests/test_fr004_api_security_framework.py"; Description = "API Security Framework" },
            @{ Pattern = "FR-005"; TestFile = "tests/regression/feature_requests/test_fr005_modular_ingestion.py"; Description = "Modular Ingestion Pipeline" },
            @{ Pattern = "FR-006"; TestFile = "tests/regression/feature_requests/test_fr006_microservices_architecture.py"; Description = "Microservices Architecture" },
            @{ Pattern = "FR-007"; TestFile = "tests/regression/feature_requests/test_fr007_container_orchestration.py"; Description = "Container Orchestration" },
            @{ Pattern = "FR-009"; TestFile = "tests/regression/feature_requests/test_fr009_semantic_search.py"; Description = "Semantic Search Capabilities" },
            @{ Pattern = "FR-010"; TestFile = "tests/regression/feature_requests/test_fr010_advanced_filters.py"; Description = "Advanced Filtering" },
            @{ Pattern = "FR-011"; TestFile = "tests/regression/feature_requests/test_fr011_content_recommendations.py"; Description = "Content Recommendations" },
            @{ Pattern = "FR-012"; TestFile = "tests/regression/feature_requests/test_fr012_export_sharing.py"; Description = "Export and Sharing" },
            @{ Pattern = "FR-013"; TestFile = "tests/regression/feature_requests/test_fr013_offline_capabilities.py"; Description = "Offline Access and Sync" },
            @{ Pattern = "FR-014"; TestFile = "tests/regression/feature_requests/test_fr014_mobile_responsive.py"; Description = "Mobile-Responsive Design" },
            @{ Pattern = "FR-016"; TestFile = "tests/regression/feature_requests/test_fr016_admin_dashboard.py"; Description = "Admin Dashboard" },
            @{ Pattern = "FR-017"; TestFile = "tests/regression/feature_requests/test_fr017_user_preferences.py"; Description = "User Preferences" },
            @{ Pattern = "FR-018"; TestFile = "tests/regression/feature_requests/test_fr018_accessibility_features.py"; Description = "Accessibility Features" },
            @{ Pattern = "FR-019"; TestFile = "tests/regression/feature_requests/test_fr019_multi_language.py"; Description = "Multi-language Support" },
            @{ Pattern = "FR-020"; TestFile = "tests/regression/feature_requests/test_fr020_ai_chatbot.py"; Description = "AI-Powered Chatbot" },
            @{ Pattern = "FR-021"; TestFile = "tests/regression/feature_requests/test_fr021_nlp_processing.py"; Description = "Natural Language Processing" },
            @{ Pattern = "FR-022"; TestFile = "tests/regression/feature_requests/test_fr022_predictive_analytics.py"; Description = "Predictive Analytics" },
            @{ Pattern = "FR-023"; TestFile = "tests/regression/feature_requests/test_fr023_recommendation_system.py"; Description = "Recommendation System" },
            @{ Pattern = "FR-024"; TestFile = "tests/regression/feature_requests/test_fr024_anomaly_detection.py"; Description = "Anomaly Detection" },
            @{ Pattern = "FR-025"; TestFile = "tests/regression/feature_requests/test_fr025_automl_platform.py"; Description = "AutoML Platform" },
            @{ Pattern = "FR-026"; TestFile = "tests/regression/feature_requests/test_fr026_model_governance.py"; Description = "Model Governance" },
            @{ Pattern = "FR-027"; TestFile = "tests/regression/feature_requests/test_fr027_realtime_inference.py"; Description = "Real-time ML Inference" },
            @{ Pattern = "FR-028"; TestFile = "tests/regression/feature_requests/test_fr028_eval_gates.py"; Description = "Evaluation Gates" },
            @{ Pattern = "FR-029"; TestFile = "tests/regression/feature_requests/test_fr029_automated_backup_recovery.py"; Description = "Automated Backup Recovery" },
            @{ Pattern = "FR-030"; TestFile = "tests/regression/feature_requests/test_fr030_performance_optimization.py"; Description = "Performance Optimization" },
            @{ Pattern = "FR-031"; TestFile = "tests/regression/feature_requests/test_fr031_system_monitoring.py"; Description = "System Monitoring" },
            @{ Pattern = "FR-032"; TestFile = "tests/regression/feature_requests/test_fr032_compliance_auditing.py"; Description = "Compliance and Auditing" },
            @{ Pattern = "FR-033"; TestFile = "tests/regression/feature_requests/test_fr033_disaster_recovery.py"; Description = "Disaster Recovery" },
            @{ Pattern = "FR-034"; TestFile = "tests/regression/feature_requests/test_fr034_enterprise_integration.py"; Description = "Enterprise Integration" },

            # Core validation tests
            @{ Pattern = "Passed D-G"; TestFile = "tests/regression/feature_requests/test_passed_dg_validation.py"; Description = "Pass D-G Pipeline Validation" },
            @{ Pattern = "Initial Gating"; TestFile = "tests/regression/feature_requests/test_initial_gating.py"; Description = "Initial Gating Mechanisms" }
        )
    } else {
        # Single feature request pattern
        $featureRequestTests = @(
            @{ Pattern = $FRPattern; TestFile = "tests/regression/feature_requests/test_$($FRPattern.ToLower().Replace('-', '_'))_*.py"; Description = "Single FR Test" }
        )
    }

    foreach ($frTest in $featureRequestTests) {
        Write-TestLog "Testing $($frTest.Pattern): $($frTest.Description)..." -Level "FR" -Indent 1

        try {
            # Check if test file exists first
            $testFile = $frTest.TestFile
            $testExists = $false

            # Handle wildcard patterns
            if ($testFile -like "*`**") {
                $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "find", "/app", "-name", ($testFile -replace "tests/regression/feature_requests/", "").Replace("/", "*"))
                $findOutput = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
                if ($LASTEXITCODE -eq 0 -and $findOutput) {
                    $testExists = $true
                    $actualTestFile = ($findOutput | Select-Object -First 1).Replace("/app/", "")
                    $testFile = $actualTestFile
                }
            } else {
                $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "test", "-f", "/app/$testFile")
                & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $testExists = $true
                }
            }

            if ($testExists) {
                $testCmd = @("docker", "exec", "ttrpg-app-dev-local", "python", "-m", "pytest", $testFile, "-v")
                if ($TestPattern) { $testCmd += "-k"; $testCmd += $TestPattern }

                $output = & $testCmd[0] $testCmd[1..($testCmd.Length-1)] 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-TestLog "$($frTest.Pattern): PASS" -Level "PASS" -Indent 2
                    $frResults += @{ Test = "$($frTest.Pattern): $($frTest.Description)"; Status = "PASS"; Details = "Feature request validated"; Output = $output -join "`n" }
                } else {
                    Write-TestLog "$($frTest.Pattern): FAIL" -Level "FAIL" -Indent 2
                    $frResults += @{ Test = "$($frTest.Pattern): $($frTest.Description)"; Status = "FAIL"; Details = "Exit code: $LASTEXITCODE"; Output = $output -join "`n" }
                }
            } else {
                Write-TestLog "$($frTest.Pattern): SKIP - Test file not found: $testFile" -Level "SKIP" -Indent 2
                $frResults += @{ Test = "$($frTest.Pattern): $($frTest.Description)"; Status = "SKIP"; Details = "Test file not found: $testFile"; Output = "" }
            }
        }
        catch {
            Write-TestLog "$($frTest.Pattern): ERROR - $($_.Exception.Message)" -Level "ERROR" -Indent 2
            $frResults += @{ Test = "$($frTest.Pattern): $($frTest.Description)"; Status = "ERROR"; Details = $_.Exception.Message; Output = "" }
        }
    }

    $frDuration = (Get-Date) - $frStartTime
    $frPassed = ($frResults | Where-Object { $_.Status -eq "PASS" }).Count
    $frFailed = ($frResults | Where-Object { $_.Status -eq "FAIL" }).Count

    $script:FeatureResults = @{
        "Passed" = $frPassed
        "Failed" = $frFailed
        "Duration" = $frDuration
        "Tests" = $frResults
    }

    Write-TestLog "Feature Requests Summary: $frPassed passed, $frFailed failed ($('{0:F1}' -f $frDuration.TotalSeconds)s)" -Level "INFO" -Indent 1

    return $frResults
}

function Generate-TestReport {
    Write-TestLog "Generating comprehensive test report..." -Level "INFO"

    $totalDuration = (Get-Date) - $StartTime
    $allResults = @()

    # Collect all results
    foreach ($phase in $script:PhaseResults.Keys) {
        $allResults += $script:PhaseResults[$phase].Tests
    }
    if ($script:FeatureResults.Tests) {
        $allResults += $script:FeatureResults.Tests
    }

    # Calculate totals
    $totalPassed = ($allResults | Where-Object { $_.Status -eq "PASS" }).Count
    $totalFailed = ($allResults | Where-Object { $_.Status -eq "FAIL" }).Count
    $totalErrors = ($allResults | Where-Object { $_.Status -eq "ERROR" }).Count
    $totalSkipped = ($allResults | Where-Object { $_.Status -eq "SKIP" }).Count
    $totalTests = $allResults.Count

    # Console report
    $reportSeparator = "=" * 100
    Write-TestLog $reportSeparator -Level "SUCCESS"
    Write-TestLog "TTRPG CENTER REGRESSION TEST SUITE FINAL REPORT" -Level "SUCCESS"
    Write-TestLog $reportSeparator -Level "SUCCESS"
    Write-TestLog "Total Execution Time: $('{0:F1}' -f $totalDuration.TotalMinutes) minutes" -Level "INFO"
    Write-TestLog "Total Tests: $totalTests" -Level "INFO"
    Write-TestLog "Passed: $totalPassed" -Level "PASS"
    if ($totalFailed -gt 0) { Write-TestLog "Failed: $totalFailed" -Level "FAIL" }
    if ($totalErrors -gt 0) { Write-TestLog "Errors: $totalErrors" -Level "ERROR" }
    if ($totalSkipped -gt 0) { Write-TestLog "Skipped: $totalSkipped" -Level "SKIP" }

    # Phase breakdown
    if ($script:PhaseResults.Count -gt 0) {
        Write-TestLog "`nPhase Breakdown:" -Level "INFO"
        foreach ($phase in $script:PhaseResults.Keys | Sort-Object) {
            $phaseData = $script:PhaseResults[$phase]
            Write-TestLog "${phase}: $($phaseData.Passed) passed, $($phaseData.Failed) failed ($('{0:F1}' -f $phaseData.Duration.TotalSeconds)s)" -Level "INFO" -Indent 1
        }
    }

    # Feature request breakdown
    if ($script:FeatureResults.Tests) {
        Write-TestLog "`nFeature Requests: $($script:FeatureResults.Passed) passed, $($script:FeatureResults.Failed) failed ($('{0:F1}' -f $script:FeatureResults.Duration.TotalSeconds)s)" -Level "INFO"
    }

    # Generate structured output
    if ($OutputFormat -eq "json" -or $GenerateReport) {
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
            "Phases" = $script:PhaseResults
            "FeatureRequests" = $script:FeatureResults
            "AllResults" = $allResults
        }

        $reportJson = $reportData | ConvertTo-Json -Depth 10

        if ($OutputPath) {
            $reportJson | Set-Content -Path $OutputPath
            Write-TestLog "JSON report saved to: $OutputPath" -Level "INFO"
        }

        if ($GenerateReport) {
            $htmlPath = Join-Path $ProjectRoot "test_results" "regression_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').html"
            Generate-HtmlReport -ReportData $reportData -OutputPath $htmlPath
            Write-TestLog "HTML report generated: $htmlPath" -Level "INFO"
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
    <title>TTRPG Center Regression Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; }
        .summary { background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .phase { margin: 20px 0; border: 1px solid #bdc3c7; border-radius: 5px; }
        .phase-header { background: #3498db; color: white; padding: 10px; }
        .test-result { padding: 10px; border-bottom: 1px solid #ecf0f1; }
        .pass { color: #27ae60; }
        .fail { color: #e74c3c; }
        .error { color: #8e44ad; }
        .skip { color: #f39c12; }
        .details { margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 3px; font-family: monospace; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>TTRPG Center Regression Test Report</h1>
        <p>Generated: $(Get-Date)</p>
    </div>

    <div class="summary">
        <h2>Test Summary</h2>
        <p><strong>Total Tests:</strong> $($ReportData.Summary.TotalTests)</p>
        <p><strong>Passed:</strong> <span class="pass">$($ReportData.Summary.Passed)</span></p>
        <p><strong>Failed:</strong> <span class="fail">$($ReportData.Summary.Failed)</span></p>
        <p><strong>Errors:</strong> <span class="error">$($ReportData.Summary.Errors)</span></p>
        <p><strong>Skipped:</strong> <span class="skip">$($ReportData.Summary.Skipped)</span></p>
        <p><strong>Duration:</strong> $('{0:F1}' -f $ReportData.Summary.Duration) minutes</p>
    </div>
"@

    # Add phase details
    foreach ($phase in $ReportData.Phases.Keys | Sort-Object) {
        $phaseData = $ReportData.Phases[$phase]
        $htmlContent += @"
    <div class="phase">
        <div class="phase-header">
            <h3>$phase - $($phaseData.Passed) passed, $($phaseData.Failed) failed</h3>
        </div>
"@
        foreach ($test in $phaseData.Tests) {
            $statusClass = $test.Status.ToLower()
            $htmlContent += @"
        <div class="test-result">
            <strong>$($test.Test):</strong> <span class="$statusClass">$($test.Status)</span>
            <div class="details">$($test.Details)</div>
        </div>
"@
        }
        $htmlContent += "    </div>"
    }

    $htmlContent += "</body></html>"

    # Ensure directory exists
    $reportDir = Split-Path $OutputPath -Parent
    if (-not (Test-Path $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }

    $htmlContent | Set-Content -Path $OutputPath
}

# Main execution
try {
    Initialize-TestEnvironment
    Test-ContainerPrerequisites

    $allResults = @()

    # Run phase tests
    if ($Phase -eq "all") {
        for ($i = 0; $i -le 7; $i++) {
            $phaseResults = Invoke-PhaseTests -PhaseNumber $i.ToString()
            $allResults += $phaseResults
        }
    } else {
        $phaseResults = Invoke-PhaseTests -PhaseNumber $Phase.ToString()
        $allResults += $phaseResults
    }

    # Run feature request tests
    if ($FeatureRequest -ne "none") {
        $frResults = Invoke-FeatureRequestTests -FRPattern $FeatureRequest
        $allResults += $frResults
    }

    # Generate final report
    $success = Generate-TestReport

    if ($success) {
        Write-TestLog "`nAll regression tests completed successfully!" -Level "SUCCESS"
        exit 0
    } else {
        Write-TestLog "`nSome tests failed. Check the detailed report above." -Level "ERROR"
        exit 1
    }
}
catch {
    Write-TestLog "Regression test suite failed: $($_.Exception.Message)" -Level "ERROR"
    Write-TestLog "Stack trace: $($_.ScriptStackTrace)" -Level "ERROR"
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}