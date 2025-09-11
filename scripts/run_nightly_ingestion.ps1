param(
  [string]$Env = "dev",
  [string[]]$Uploads = @(),
  [string]$ArtifactsBase = ""
)

# Avoid terminating on non-critical stderr output from child processes.
# We'll rely on the Python process exit code instead.
$ErrorActionPreference = "Continue"

# Resolve repo root and Python
$repo = (Split-Path -Parent $PSScriptRoot)

function Get-Python {
  param([string]$RepoRoot)
  $venv = Join-Path $RepoRoot ".venv"
  $venvPy = Join-Path $venv "Scripts\python.exe"
  if (Test-Path $venvPy) {
    # Activate venv context for child process
    $env:VIRTUAL_ENV = $venv
    $env:PATH = (Join-Path $venv "Scripts") + ";" + $env:PATH
    return @($venvPy)
  }
  $pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
  if ($pyCmd) { return @($pyCmd.Source, "-3") }
  $pyExe = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($pyExe) { return @($pyExe.Source) }
  else { throw "Python interpreter not found (venv, py.exe, or python.exe)" }
}

$py = @(Get-Python -RepoRoot $repo)
$pythonExe = $py[0]
$pythonArgs = @()
if ($py.Length -gt 1) { $pythonArgs += $py[1] }

# Ensure environment and logs
$env:APP_ENV = $Env
$env:PYTHONUNBUFFERED = "1"
$logsDir = Join-Path $repo "env\$Env\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logsDir "nightly_ps_$ts.log"
$pyLogFile = Join-Path $logsDir "nightly_$ts.log"

# Build command
$scriptPath = Join-Path $repo "scripts\run_nightly_ingestion.py"
$argList = @()
$argList += $pythonArgs
$argList += @($scriptPath, '--env', $Env)
foreach ($u in $Uploads) { $argList += @('--uploads', $u) }
if ($ArtifactsBase -and $ArtifactsBase.Trim() -ne "") { $argList += @('--artifacts-base', $ArtifactsBase) }
$argList += @('--log-file', $pyLogFile)

# Quote args for Start-Process
$quotedArgs = $argList | ForEach-Object {
  if ($_ -match '^[A-Za-z0-9_\-\.\\:]+$') { $_ } else { '"{0}"' -f $_ }
}
$argsString = ($quotedArgs -join ' ')

# Run via Start-Process and redirect outputs to temp files, then append to log
Add-Content -Path $logFile -Value ("Python log: {0}" -f $pyLogFile)
Add-Content -Path $logFile -Value ("Starting nightly ingestion: {0} {1}" -f $pythonExe, $argsString)

$tmpOut = Join-Path $env:TEMP ("nightly_out_" + $ts + "_" + [Guid]::NewGuid().ToString() + ".log")
$tmpErr = Join-Path $env:TEMP ("nightly_err_" + $ts + "_" + [Guid]::NewGuid().ToString() + ".log")

try {
  $p = Start-Process -FilePath $pythonExe -ArgumentList $argsString -Wait -NoNewWindow -PassThru -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
} catch {
  Add-Content -Path $logFile -Value ("ERROR: Failed to start process '{0}': {1}" -f $pythonExe, $_.Exception.Message)
  $p = $null
}

if (Test-Path $tmpOut) { Get-Content -Path $tmpOut | Add-Content -Path $logFile; Remove-Item $tmpOut -ErrorAction SilentlyContinue }
if (Test-Path $tmpErr) { Get-Content -Path $tmpErr | Add-Content -Path $logFile; Remove-Item $tmpErr -ErrorAction SilentlyContinue }

$code = if ($p) { $p.ExitCode } else { 1 }
Add-Content -Path $logFile -Value ("Nightly ingestion finished with exit code {0}" -f $code)

# Optional: Generate BUG docs from Python log when failures occur
try {
  if (Test-Path $pyLogFile) {
    $bugArgs = @('scripts\post_run_bug_scan.py', '--log-file', $pyLogFile, '--env', $Env)
    if ($env:OPENAI_API_KEY -and $code -ne 0) { $bugArgs += '--ai-enrich' }
    $bugOut = Join-Path $env:TEMP ("bugscan_" + $ts + "_" + [Guid]::NewGuid().ToString() + ".log")
    $bugErr = Join-Path $env:TEMP ("bugscan_err_" + $ts + "_" + [Guid]::NewGuid().ToString() + ".log")
    $bp = Start-Process -FilePath $pythonExe -ArgumentList ($bugArgs -join ' ') -Wait -NoNewWindow -PassThru -RedirectStandardOutput $bugOut -RedirectStandardError $bugErr
    if (Test-Path $bugOut) { Get-Content -Path $bugOut | Add-Content -Path $logFile; Remove-Item $bugOut -ErrorAction SilentlyContinue }
    if (Test-Path $bugErr) { Get-Content -Path $bugErr | Add-Content -Path $logFile; Remove-Item $bugErr -ErrorAction SilentlyContinue }
  }
} catch {}

exit $code
