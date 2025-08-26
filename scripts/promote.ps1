param([Parameter(Mandatory=$true)][string]$BuildId,
      [Parameter(Mandatory=$true)][ValidateSet("test","prod")]$Env)

$buildPath = Join-Path ".\builds" $BuildId
if (-not (Test-Path $buildPath)) { throw "Build not found: $BuildId" }

# Ensure releases directory exists
New-Item -ItemType Directory -Path ".\releases" -ErrorAction SilentlyContinue | Out-Null

$pointer = if ($Env -eq "test") { ".\releases\test_current.txt" } else { ".\releases\prod_current.txt" }
Set-Content $pointer $BuildId

$logLine = @{ ts = (Get-Date).ToString("s"); env = $Env; build_id = $BuildId; by = "$env:USERNAME" } | ConvertTo-Json -Compress
New-Item -ItemType Directory -Path ".\logs\$Env" -ErrorAction SilentlyContinue | Out-Null
Add-Content ".\logs\$Env\promotions.jsonl" $logLine

Write-Host "Promoted $BuildId to $Env"