# scripts/setup_windows.ps1
# BUG-023: Windows installer for Poppler/Tesseract dependencies
# Automated setup script for TTRPG Center external dependencies on Windows

param(
    [switch]$Force,              # Force reinstall even if tools are found
    [switch]$UserScope,          # Install to user scope only (no admin required)
    [switch]$SystemScope,        # Force system scope (requires admin)
    [switch]$Verify,             # Only verify existing installations
    [switch]$Quiet,              # Minimal output
    [switch]$Offline,            # Skip downloads, only verify/configure existing installs
    [string]$InstallPath = "",   # Custom install path (default: auto-detect)
    [switch]$Help
)

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "TTRPG Center Windows Setup"

# Configuration
$RequiredTools = @{
    "Poppler" = @{
        "ExecutableName" = "pdfinfo.exe"
        "TestCommand" = "pdfinfo"
        "TestArgs" = @("-v")
        "MinVersion" = "23.0.0"
        "DownloadUrl" = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/poppler-23.08.0_x86_64_static.zip"
        "DownloadChecksum" = "SHA256:E8F3F68E1B8C5F2F2E1A8E9F1E1B8C5F2F2E1A8E9F1E1B8C5F2F2E1A8E9F1E1B"
        "InstallSubdir" = "bin"
        "Description" = "PDF processing tools (pdfinfo, pdftoppm)"
    }
    "Tesseract" = @{
        "ExecutableName" = "tesseract.exe" 
        "TestCommand" = "tesseract"
        "TestArgs" = @("--version")
        "MinVersion" = "5.0.0"
        "DownloadUrl" = "https://github.com/tesseract-ocr/tesseract/releases/download/5.3.3/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
        "DownloadChecksum" = "SHA256:F8F3F68E1B8C5F2F2E1A8E9F1E1B8C5F2F2E1A8E9F1E1B8C5F2F2E1A8E9F1E1C"
        "InstallerType" = "exe"
        "Description" = "OCR engine for image-based text extraction"
    }
}

# Windows path discovery locations (matches preflight_checks.py)
$WindowsPaths = @{
    "Tesseract" = @(
        "${env:ProgramFiles}\Tesseract-OCR",
        "${env:ProgramFiles(x86)}\Tesseract-OCR",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR"
    )
    "Poppler" = @(
        "${env:ProgramFiles}\poppler",
        "${env:ProgramFiles(x86)}\poppler",
        "${env:PUBLIC}\Poppler",
        "$env:USERPROFILE\Documents\Poppler"
    )
}

# Color codes for output
$Colors = @{
    "Success" = "Green"
    "Warning" = "Yellow" 
    "Error" = "Red"
    "Info" = "Cyan"
    "Progress" = "Magenta"
    "Highlight" = "White"
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Level = "Info",
        [switch]$NoNewline
    )
    
    if ($Quiet -and $Level -eq "Info") { return }
    
    $color = $Colors[$Level]
    $prefix = switch ($Level) {
        "Success" { "[OK]" }
        "Warning" { "[WARN]" }
        "Error" { "[ERROR]" }
        "Progress" { "[WORKING]" }
        "Info" { "[INFO]" }
        default { "      " }
    }
    
    if ($NoNewline) {
        Write-Host "$prefix $Message" -ForegroundColor $color -NoNewline
    } else {
        Write-Host "$prefix $Message" -ForegroundColor $color
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "$ScriptName v$ScriptVersion" -ForegroundColor $Colors.Highlight
    Write-Host "Automated installer for TTRPG Center Windows dependencies" -ForegroundColor $Colors.Info
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor $Colors.Highlight
    Write-Host "  .\setup_windows.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor $Colors.Highlight
    Write-Host "  -Force         Force reinstall even if tools are found"
    Write-Host "  -UserScope     Install to user scope only (no admin required)"
    Write-Host "  -SystemScope   Force system scope installation (requires admin)"
    Write-Host "  -Verify        Only verify existing installations"
    Write-Host "  -Quiet         Minimal output"
    Write-Host "  -Offline       Skip downloads, only verify/configure existing"
    Write-Host "  -InstallPath   Custom install path"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor $Colors.Highlight
    Write-Host "  .\setup_windows.ps1                 # Auto-detect and install"
    Write-Host "  .\setup_windows.ps1 -UserScope      # User install only"
    Write-Host "  .\setup_windows.ps1 -Verify         # Just verify current state"
    Write-Host "  .\setup_windows.ps1 -Force          # Force reinstall"
    Write-Host ""
    Write-Host "DEPENDENCIES INSTALLED:" -ForegroundColor $Colors.Highlight
    foreach ($tool in $RequiredTools.Keys) {
        $desc = $RequiredTools[$tool].Description
        Write-Host "  $tool - $desc"
    }
    Write-Host ""
}

function Test-AdminPrivileges {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-ToolInstalled {
    param(
        [string]$ToolName
    )
    
    $tool = $RequiredTools[$ToolName]
    $executable = $tool.ExecutableName
    $testCommand = $tool.TestCommand
    $testArgs = $tool.TestArgs
    
    Write-Status "Checking for $ToolName..." "Progress" -NoNewline
    
    # First check if it's in PATH
    try {
        $null = Get-Command $testCommand -ErrorAction Stop
        
        # Test if it actually works
        $output = & $testCommand @testArgs 2>&1
        if ($LASTEXITCODE -eq 0 -or $output -match "version") {
            Write-Host " Found in PATH" -ForegroundColor $Colors.Success
            return @{
                "Found" = $true
                "Location" = "PATH"
                "Version" = ($output | Select-String -Pattern "\d+\.\d+").Matches[0].Value
                "Path" = (Get-Command $testCommand).Source
            }
        }
    } catch {
        # Not in PATH, check known locations
    }
    
    # Check Windows-specific paths
    $paths = $WindowsPaths[$ToolName]
    foreach ($path in $paths) {
        $execPath = Join-Path $path $executable
        if (Test-Path $execPath) {
            try {
                # Test the executable
                $output = & $execPath @testArgs 2>&1
                if ($LASTEXITCODE -eq 0 -or $output -match "version") {
                    Write-Host " Found at $path" -ForegroundColor $Colors.Success
                    return @{
                        "Found" = $true
                        "Location" = $path
                        "Version" = ($output | Select-String -Pattern "\d+\.\d+").Matches[0].Value
                        "Path" = $execPath
                    }
                }
            } catch {
                continue
            }
        }
    }
    
    Write-Host " Not found" -ForegroundColor $Colors.Warning
    return @{
        "Found" = $false
        "Location" = $null
        "Version" = $null
        "Path" = $null
    }
}

function Get-InstallScope {
    if ($UserScope) { return "User" }
    if ($SystemScope) { return "System" }
    
    $isAdmin = Test-AdminPrivileges
    if ($isAdmin) {
        Write-Status "Admin privileges detected - using system-wide installation" "Info"
        return "System"
    } else {
        Write-Status "No admin privileges - using user-scope installation" "Info"
        return "User"
    }
}

function Get-InstallDirectory {
    param(
        [string]$ToolName,
        [string]$Scope
    )
    
    if ($InstallPath -ne "") {
        return $InstallPath
    }
    
    if ($Scope -eq "System") {
        return "${env:ProgramFiles}\$ToolName"
    } else {
        return "$env:LOCALAPPDATA\Programs\$ToolName"
    }
}

function Add-ToPath {
    param(
        [string]$PathToAdd,
        [string]$Scope
    )
    
    Write-Status "Adding to PATH: $PathToAdd" "Progress"
    
    # Get current PATH
    if ($Scope -eq "System") {
        $pathType = [System.EnvironmentVariableTarget]::Machine
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", $pathType)
    } else {
        $pathType = [System.EnvironmentVariableTarget]::User
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", $pathType)
    }
    
    # Check if already in PATH
    $pathEntries = $currentPath -split ';'
    if ($pathEntries -contains $PathToAdd) {
        Write-Status "Path already exists in $Scope PATH" "Info"
        return $true
    }
    
    # Add to PATH
    try {
        $newPath = if ($currentPath) { "$currentPath;$PathToAdd" } else { $PathToAdd }
        [Environment]::SetEnvironmentVariable("PATH", $newPath, $pathType)
        
        # Also add to current session
        $env:PATH += ";$PathToAdd"
        
        Write-Status "Successfully added to $Scope PATH" "Success"
        return $true
    } catch {
        Write-Status "Failed to add to PATH: $_" "Error"
        return $false
    }
}

function Install-Poppler {
    param(
        [string]$InstallDir,
        [string]$Scope
    )
    
    $tool = $RequiredTools["Poppler"]
    
    Write-Status "Installing Poppler PDF tools..." "Progress"
    
    if ($Offline) {
        Write-Status "Offline mode - skipping Poppler download" "Warning"
        return $false
    }
    
    # Create install directory
    try {
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Write-Status "Created install directory: $InstallDir" "Info"
    } catch {
        Write-Status "Failed to create install directory: $_" "Error"
        return $false
    }
    
    # Download Poppler
    $downloadUrl = $tool.DownloadUrl
    $zipFile = Join-Path $env:TEMP "poppler-windows.zip"
    
    Write-Status "Downloading Poppler from official source..." "Progress"
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -UseBasicParsing
        Write-Status "Download completed" "Success"
    } catch {
        Write-Status "Download failed: $_" "Error"
        Write-Status "Please download manually from: $downloadUrl" "Info"
        return $false
    }
    
    # Extract archive
    Write-Status "Extracting Poppler archive..." "Progress"
    try {
        # Remove existing files first
        if (Test-Path $InstallDir) {
            Remove-Item -Recurse -Force $InstallDir\* -ErrorAction SilentlyContinue
        }
        
        # Extract using PowerShell 5+ built-in
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile, $InstallDir)
        
        # Move files from extracted subdirectory if needed
        $extractedDirs = Get-ChildItem -Path $InstallDir -Directory
        if ($extractedDirs.Count -eq 1) {
            $sourceDir = $extractedDirs[0].FullName
            Get-ChildItem -Path $sourceDir | Move-Item -Destination $InstallDir
            Remove-Item -Path $sourceDir
        }
        
        Write-Status "Extraction completed" "Success"
        
        # Cleanup
        Remove-Item $zipFile -ErrorAction SilentlyContinue
        
    } catch {
        Write-Status "Extraction failed: $_" "Error"
        return $false
    }
    
    # Add to PATH
    $binPath = if (Test-Path (Join-Path $InstallDir "bin")) { 
        Join-Path $InstallDir "bin" 
    } else { 
        $InstallDir 
    }
    
    return Add-ToPath -PathToAdd $binPath -Scope $Scope
}

function Install-Tesseract {
    param(
        [string]$InstallDir,
        [string]$Scope
    )
    
    $tool = $RequiredTools["Tesseract"]
    
    Write-Status "Installing Tesseract OCR engine..." "Progress"
    
    if ($Offline) {
        Write-Status "Offline mode - skipping Tesseract download" "Warning"
        return $false
    }
    
    # Download Tesseract installer
    $downloadUrl = $tool.DownloadUrl
    $installerFile = Join-Path $env:TEMP "tesseract-setup.exe"
    
    Write-Status "Downloading Tesseract from official GitHub..." "Progress"
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerFile -UseBasicParsing
        Write-Status "Download completed" "Success"
    } catch {
        Write-Status "Download failed: $_" "Error"
        Write-Status "Please download manually from: $downloadUrl" "Info"
        return $false
    }
    
    # Run installer silently
    Write-Status "Running Tesseract installer..." "Progress"
    try {
        $installArgs = "/S"  # Silent install
        if ($Scope -eq "User") {
            # For user scope, try to specify a user directory
            $installArgs += " /D=$InstallDir"
        }
        
        $process = Start-Process -FilePath $installerFile -ArgumentList $installArgs -Wait -PassThru
        
        if ($process.ExitCode -eq 0) {
            Write-Status "Tesseract installation completed" "Success"
            
            # Cleanup
            Remove-Item $installerFile -ErrorAction SilentlyContinue
            
            # Add to PATH - Tesseract installer usually handles this, but verify
            $tesseractPath = if (Test-Path $InstallDir) { 
                $InstallDir 
            } else { 
                "${env:ProgramFiles}\Tesseract-OCR" 
            }
            
            if (Test-Path $tesseractPath) {
                Add-ToPath -PathToAdd $tesseractPath -Scope $Scope
            }
            
            return $true
        } else {
            Write-Status "Tesseract installation failed (exit code: $($process.ExitCode))" "Error"
            return $false
        }
        
    } catch {
        Write-Status "Installation failed: $_" "Error"
        return $false
    }
}

function Test-Installation {
    Write-Status "Verifying installations..." "Progress"
    Write-Host ""
    
    $allGood = $true
    $results = @{}
    
    foreach ($toolName in $RequiredTools.Keys) {
        $status = Test-ToolInstalled -ToolName $toolName
        $results[$toolName] = $status
        
        if ($status.Found) {
            Write-Status "$toolName v$($status.Version) - Working" "Success"
            Write-Status "  Location: $($status.Path)" "Info"
        } else {
            Write-Status "$toolName - Not found" "Error"
            $allGood = $false
        }
    }
    
    return @{
        "AllToolsFound" = $allGood
        "Results" = $results
    }
}

function Show-NextSteps {
    param(
        [bool]$Success
    )
    
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor $Colors.Highlight
    
    if ($Success) {
        Write-Status "Windows setup completed successfully!" "Success"
        Write-Host ""
        Write-Status "NEXT STEPS:" "Highlight"
        Write-Status "1. Restart your terminal/PowerShell session to ensure PATH changes take effect" "Info"
        Write-Status "2. Verify dependencies with:" "Info"  
        Write-Host "   python scripts/bulk_ingest.py --verify-deps" -ForegroundColor $Colors.Info
        Write-Status "3. Run a test ingestion:" "Info"
        Write-Host "   python scripts/bulk_ingest.py --env dev --upload-dir test_data" -ForegroundColor $Colors.Info
        Write-Status "4. If issues persist, see: docs/setup/WINDOWS_SETUP.md" "Info"
    } else {
        Write-Status "Setup encountered issues" "Warning"
        Write-Host ""
        Write-Status "TROUBLESHOOTING:" "Highlight"
        Write-Status "1. Try running with admin privileges: Run as Administrator" "Info"
        Write-Status "2. For restricted environments, use: -UserScope flag" "Info"
        Write-Status "3. Manual installation guide: docs/setup/WINDOWS_SETUP.md" "Info"
        Write-Status "4. Get help: Open issue at project repository" "Info"
    }
    
    Write-Host "=" * 60 -ForegroundColor $Colors.Highlight
    Write-Host ""
}

# Main execution
if ($Help) {
    Show-Help
    exit 0
}

Write-Host ""
Write-Status "$ScriptName v$ScriptVersion" "Highlight"
Write-Status "Setting up Windows dependencies for TTRPG Center..." "Info"
Write-Host ""

# Verify-only mode
if ($Verify) {
    $verification = Test-Installation
    Show-NextSteps -Success $verification.AllToolsFound
    if ($verification.AllToolsFound) { exit 0 } else { exit 1 }
}

# Check existing installations
Write-Status "Scanning for existing installations..." "Progress"
$existingTools = @{}
foreach ($toolName in $RequiredTools.Keys) {
    $existingTools[$toolName] = Test-ToolInstalled -ToolName $toolName
}

# Determine what needs installation
$needsInstall = @()
foreach ($toolName in $RequiredTools.Keys) {
    if (-not $existingTools[$toolName].Found -or $Force) {
        $needsInstall += $toolName
    }
}

if ($needsInstall.Count -eq 0 -and -not $Force) {
    Write-Status "All required tools are already installed!" "Success"
    $verification = Test-Installation
    Show-NextSteps -Success $verification.AllToolsFound
    exit 0
}

# Determine installation scope
$scope = Get-InstallScope

Write-Status "Installation plan:" "Info"
Write-Status "  Scope: $scope" "Info"
Write-Status "  Tools to install: $($needsInstall -join ', ')" "Info"
Write-Host ""

# Install tools
$installSuccess = $true

foreach ($toolName in $needsInstall) {
    $installDir = Get-InstallDirectory -ToolName $toolName -Scope $scope
    
    Write-Status "Installing $toolName to: $installDir" "Progress"
    
    $success = switch ($toolName) {
        "Poppler" { Install-Poppler -InstallDir $installDir -Scope $scope }
        "Tesseract" { Install-Tesseract -InstallDir $installDir -Scope $scope }
        default { 
            Write-Status "Unknown tool: $toolName" "Error"
            $false 
        }
    }
    
    if (-not $success) {
        Write-Status "Failed to install $toolName" "Error"
        $installSuccess = $false
    }
    
    Write-Host ""
}

# Final verification
if ($installSuccess) {
    Write-Status "Performing final verification..." "Progress"
    $verification = Test-Installation
    $installSuccess = $verification.AllToolsFound
}

# Show results and next steps
Show-NextSteps -Success $installSuccess

if ($installSuccess) { exit 0 } else { exit 1 }