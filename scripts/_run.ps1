param()

# Load env without echoing values
Get-Content $env:DOTENV_PATH | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k,$v = $_.Split('=',2)
  if ($k -and $v) { [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim()) }
}

# Validate required keys (names only)
$req = @("ASTRA_DB_API_ENDPOINT","ASTRA_DB_APPLICATION_TOKEN","ASTRA_DB_ID","ASTRA_DB_KEYSPACE","ASTRA_DB_REGION","OPENAI_API_KEY","PORT","APP_ENV")
$missing = @()
foreach ($k in $req) { if (-not [Environment]::GetEnvironmentVariable($k)) { $missing += $k } }
if ($missing.Count -gt 0) { throw "Missing required env keys: $($missing -join ', ')" }

# Start your app (replace this with real entry point)
python .\app\server.py