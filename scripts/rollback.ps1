param([Parameter(Mandatory=$true)][ValidateSet("test","prod")]$Env)

$pointer = if ($Env -eq "test") { ".\releases\test_current.txt" } else { ".\releases\prod_current.txt" }
$logFile = ".\logs\$Env\promotions.jsonl"

if (-not (Test-Path $logFile)) {
    throw "No promotion history found for $Env"
}

# Get last two promotions
$history = Get-Content $logFile | ForEach-Object { ConvertFrom-Json $_ } | Sort-Object ts -Descending
if ($history.Count -lt 2) {
    throw "Not enough promotion history to rollback"
}

$currentBuild = $history[0].build_id
$previousBuild = $history[1].build_id

Write-Host "Rolling back from $currentBuild to $previousBuild"

Set-Content $pointer $previousBuild

$logLine = @{ ts = (Get-Date).ToString("s"); env = $Env; build_id = $previousBuild; by = "$env:USERNAME"; action = "rollback"; from = $currentBuild } | ConvertTo-Json -Compress
Add-Content $logFile $logLine

Write-Host "Rolled back $Env to $previousBuild"