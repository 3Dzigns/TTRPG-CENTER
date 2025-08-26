param([string]$Env = "dev")

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$snapshotDir = ".\runtime\$Env\snapshots\$ts"
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null

Write-Host "Creating snapshot of $Env environment..."

# Copy runtime state
if (Test-Path ".\runtime\$Env\data") {
    Copy-Item ".\runtime\$Env\data" "$snapshotDir\data" -Recurse -Force
}

# Copy logs
if (Test-Path ".\logs\$Env") {
    Copy-Item ".\logs\$Env" "$snapshotDir\logs" -Recurse -Force
}

# Current config snapshot
Copy-Item ".\config\.env.$Env" "$snapshotDir\.env"

$manifest = @{
    env = $Env
    timestamp = (Get-Date).ToString("s")
    build_id = if (Test-Path ".\releases\${Env}_current.txt") { Get-Content ".\releases\${Env}_current.txt" } else { "dev" }
}
($manifest | ConvertTo-Json -Depth 3) | Set-Content "$snapshotDir\snapshot-manifest.json"

Write-Host "Snapshot created at $snapshotDir"