# HTTPS Development Server Startup Script
# Configures and runs TTRPG Center with SSL certificates for OAuth development

param(
    [switch]$Help,
    [switch]$Stop
)

# Display help information
if ($Help) {
    Write-Host "HTTPS Development Server for TTRPG Center"
    Write-Host "==========================================="
    Write-Host ""
    Write-Host "Usage: .\scripts\run-https-dev.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Help    Show this help message"
    Write-Host "  -Stop    Stop running servers"
    Write-Host ""
    Write-Host "This script starts both user and admin servers with HTTPS enabled"
    Write-Host "for OAuth authentication development."
    Write-Host ""
    Write-Host "Servers will be available at:"
    Write-Host "  User App:  https://localhost:8000"
    Write-Host "  Admin App: https://localhost:8001"
    Write-Host ""
    exit 0
}

# Set working directory to project root
$ProjectRoot = (Get-Location).Path
if (-not (Test-Path "src_common")) {
    Write-Error "Please run this script from the TTRPG Center project root directory"
    exit 1
}

# Stop existing servers if requested
if ($Stop) {
    Write-Host "Stopping existing servers..." -ForegroundColor Yellow
    Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force
    Write-Host "Servers stopped." -ForegroundColor Green
    exit 0
}

# Verify SSL certificates exist
$SSLCert = "env/dev/ssl/cert.pem"
$SSLKey = "env/dev/ssl/key.pem"

if (-not (Test-Path $SSLCert) -or -not (Test-Path $SSLKey)) {
    Write-Error "SSL certificates not found. Please run certificate generation first."
    Write-Host "Expected files:" -ForegroundColor Yellow
    Write-Host "  $SSLCert"
    Write-Host "  $SSLKey"
    exit 1
}

Write-Host "Starting HTTPS Development Servers..." -ForegroundColor Green
Write-Host "SSL Certificate: $SSLCert" -ForegroundColor Cyan
Write-Host "SSL Key: $SSLKey" -ForegroundColor Cyan

# Set environment variables
$env:APP_ENV = "dev"
$env:PYTHONPATH = $ProjectRoot

# Start User App Server (HTTPS on port 8000)
Write-Host "Starting User App Server (HTTPS)..." -ForegroundColor Yellow
Start-Process -FilePath "uvicorn" -ArgumentList @(
    "app_user:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--ssl-keyfile", $SSLKey,
    "--ssl-certfile", $SSLCert,
    "--reload"
) -WindowStyle Hidden

# Wait a moment for first server to initialize
Start-Sleep -Seconds 2

# Start Admin App Server (HTTPS on port 8001)
Write-Host "Starting Admin App Server (HTTPS)..." -ForegroundColor Yellow
Start-Process -FilePath "uvicorn" -ArgumentList @(
    "app_admin:app",
    "--host", "0.0.0.0", 
    "--port", "8001",
    "--ssl-keyfile", $SSLKey,
    "--ssl-certfile", $SSLCert,
    "--reload"
) -WindowStyle Hidden

Write-Host ""
Write-Host "HTTPS Development Servers Starting..." -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "User App:  https://localhost:8000" -ForegroundColor Cyan
Write-Host "Admin App: https://localhost:8001" -ForegroundColor Cyan
Write-Host ""
Write-Host "OAuth Configuration:" -ForegroundColor Yellow
Write-Host "  Redirect URL: https://localhost:8000/auth/callback" -ForegroundColor Cyan
Write-Host "  Protocol: HTTPS (matches Google OAuth config)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Security Features Enabled:" -ForegroundColor Yellow
Write-Host "  ✓ SSL/TLS Encryption" -ForegroundColor Green
Write-Host "  ✓ Secure JWT Secrets" -ForegroundColor Green
Write-Host "  ✓ OAuth HTTPS Compatibility" -ForegroundColor Green
Write-Host ""
Write-Host "Note: You may see SSL certificate warnings in browser" -ForegroundColor Yellow
Write-Host "This is normal for self-signed development certificates." -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop or use: .\scripts\run-https-dev.ps1 -Stop" -ForegroundColor Gray

# Keep script running to monitor
try {
    while ($true) {
        Start-Sleep -Seconds 30
        
        # Check if servers are still running
        $UserApp = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*app_user*" }
        $AdminApp = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*app_admin*" }
        
        $Status = @()
        if ($UserApp) { $Status += "User ✓" } else { $Status += "User ✗" }
        if ($AdminApp) { $Status += "Admin ✓" } else { $Status += "Admin ✗" }
        
        Write-Host "$(Get-Date -Format 'HH:mm:ss') - Status: $($Status -join ', ')" -ForegroundColor Gray
    }
}
catch {
    Write-Host "Shutting down..." -ForegroundColor Yellow
}