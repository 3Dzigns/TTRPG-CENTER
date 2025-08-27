$buildId = (Get-Content ".\releases\test_current.txt" -ErrorAction SilentlyContinue).Trim()
if (-not $buildId) { 
  Write-Host "No TEST release pointer found. Running in dev mode."
  $buildId = "dev"
}

Write-Host "Starting TTRPG Center TEST environment with build: $buildId"

# Load TEST environment variables
Get-Content ".\config\.env.test" | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k,$v = $_.Split('=',2)
  if ($k -and $v) { [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim()) }
}

# Set build ID (ensure it's properly trimmed)
$buildId = $buildId.Trim()
Write-Host "Setting APP_RELEASE_BUILD to: $buildId"
[Environment]::SetEnvironmentVariable("APP_RELEASE_BUILD", $buildId)

# Start server using our working runner approach
python run_server.py