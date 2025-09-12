# scripts/cleanup_logs_simple.ps1
# Simple PowerShell wrapper for log cleanup utility

param(
    [Parameter(Mandatory=$true)]
    [int]$Retain,
    
    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

# Get paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$CleanupScript = Join-Path $ScriptDir "cleanup_logs.py"

Write-Host "TTRPG Center Log Cleanup"
Write-Host "Retain: $Retain days, Environment: $Environment"

# Check paths
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found: $PythonExe"
    exit 1
}

if (-not (Test-Path $CleanupScript)) {
    Write-Error "Script not found: $CleanupScript" 
    exit 1
}

# Build arguments
$Args = @("$CleanupScript", "--retain", "$Retain", "--env", "$Environment")
if ($DryRun) { $Args += "--dry-run" }
if ($VerboseOutput) { $Args += "--verbose" }

# Change to project root and run
Push-Location $ProjectRoot
try {
    & $PythonExe @Args
    $ExitCode = $LASTEXITCODE
    
    if ($ExitCode -eq 0) {
        Write-Host "Success" -ForegroundColor Green
    } else {
        Write-Warning "Completed with exit code: $ExitCode"
    }
    
    exit $ExitCode
    
} finally {
    Pop-Location
}