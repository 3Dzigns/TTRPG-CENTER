$buildId = Get-Content ".\releases\prod_current.txt" -ErrorAction SilentlyContinue
if (-not $buildId) { 
  Write-Host "No PROD release pointer found. Running in dev mode."
  $buildId = "dev"
}
$env:DOTENV_PATH = ".\config\.env.prod"
$env:APP_RELEASE_BUILD = $buildId

# Start ngrok if enabled
if ([Environment]::GetEnvironmentVariable("NGROK_ENABLED") -eq "true") {
    Write-Host "Starting ngrok tunnel..."
    Start-Process -NoNewWindow ngrok "http 8282"
    Start-Sleep 3
}

.\scripts\_run.ps1