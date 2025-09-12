param(
  [ValidateSet('dev','test','prod')]
  [string]$Env='dev'
)

Write-Host "Stopping TTRPG Center ($Env) servers..." -ForegroundColor Yellow

function Stop-PortListeners {
  param([int]$Port)
  try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $pids = $conns | Select-Object -Expand OwningProcess -Unique
    foreach ($id in $pids) {
      if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    }
    if ($pids) { Write-Host "Stopped listeners on port $Port (PIDs: $($pids -join ', '))" -ForegroundColor Green }
  } catch { }
}

$root = Join-Path $PSScriptRoot '..'
$envRoot = Join-Path $root "env/$Env"
$configDir = Join-Path $envRoot "config"
$portsPath = Join-Path $configDir "ports.json"

$http = 8000; $ws = 9000
if (Test-Path $portsPath) {
  try { $ports = Get-Content $portsPath | ConvertFrom-Json; $http = $ports.http_port; $ws = $ports.websocket_port } catch {}
}

Stop-PortListeners -Port $http
Stop-PortListeners -Port $ws

# Also stop any uvicorn instances referencing our app modules
try {
  Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -eq 'python' -and ($_.CommandLine -like '*uvicorn*app_main:app*' -or $_.CommandLine -like '*uvicorn*src_common.app:app*')
  } | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
} catch {}

Write-Host "Stop command complete." -ForegroundColor Green

