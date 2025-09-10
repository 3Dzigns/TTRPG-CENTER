# Windows Setup Guide for TTRPG Center

> **Complete guide for setting up Poppler and Tesseract dependencies on Windows**

This guide provides step-by-step instructions for installing the external dependencies required by TTRPG Center's document processing pipeline on Windows systems.

## 🚀 Quick Start (Automated)

**Recommended approach** - Use our automated installer:

```powershell
# Run automated setup (requires internet connection)
.\scripts\setup_windows.ps1

# Or for user-scope only (no admin privileges required)
.\scripts\setup_windows.ps1 -UserScope

# Verify after installation
python scripts/bulk_ingest.py --verify-deps
```

## 📋 Prerequisites

- **Windows 10 or later** (Windows 11 recommended)
- **PowerShell 5.1 or later** (included with Windows)
- **Internet connection** (for automated downloads)
- **Administrative privileges** (recommended but not required)

## 🛠️ Option 1: Automated Installation (Recommended)

### Basic Setup

1. **Open PowerShell as Administrator** (recommended)
   ```
   Right-click Start button → Windows PowerShell (Admin)
   ```

2. **Navigate to TTRPG Center directory**
   ```powershell
   cd "C:\path\to\TTRPG_Center"
   ```

3. **Run automated setup**
   ```powershell
   .\scripts\setup_windows.ps1
   ```

### Setup Options

| Command | Description | Admin Required |
|---------|-------------|----------------|
| `.\scripts\setup_windows.ps1` | Auto-detect scope, system-wide if admin | Recommended |
| `.\scripts\setup_windows.ps1 -UserScope` | User-only install, no admin needed | No |
| `.\scripts\setup_windows.ps1 -Force` | Force reinstall existing tools | Yes/No |
| `.\scripts\setup_windows.ps1 -Verify` | Only verify, no installation | No |
| `.\scripts\setup_windows.ps1 -Offline` | Skip downloads, configure existing | No |

### Installation Process

The automated installer will:

1. **Detect existing installations** - Check common install locations
2. **Determine installation scope** - System-wide (admin) or user-scope
3. **Download dependencies** - From official sources with checksum verification
4. **Install tools** - Poppler (extract) and Tesseract (silent install)
5. **Update PATH** - Add tools to system or user PATH permanently
6. **Verify installation** - Test that tools work correctly

### Expected Output

```
🚀 TTRPG Center Windows Setup v1.0.0
Setting up Windows dependencies for TTRPG Center...

✅ Checking for Poppler... Not found
✅ Checking for Tesseract... Not found
ℹ️  Admin privileges detected - using system-wide installation

Installation plan:
ℹ️  Scope: System
ℹ️  Tools to install: Poppler, Tesseract

🔄 Installing Poppler PDF tools...
🔄 Downloading Poppler from official source...
✅ Download completed
🔄 Extracting Poppler archive...
✅ Extraction completed
✅ Successfully added to System PATH

🔄 Installing Tesseract OCR engine...
🔄 Downloading Tesseract from official GitHub...
✅ Download completed
🔄 Running Tesseract installer...
✅ Tesseract installation completed
✅ Successfully added to System PATH

🔄 Performing final verification...
✅ Poppler v23.08.0 - ✅ Working
ℹ️    Location: C:\Program Files\poppler\bin\pdfinfo.exe
✅ Tesseract v5.3.3 - ✅ Working
ℹ️    Location: C:\Program Files\Tesseract-OCR\tesseract.exe

🎉 Windows setup completed successfully!

NEXT STEPS:
ℹ️  1. Restart your terminal/PowerShell session to ensure PATH changes take effect
ℹ️  2. Verify dependencies with:
   python scripts/bulk_ingest.py --verify-deps
ℹ️  3. Run a test ingestion:
   python scripts/bulk_ingest.py --env dev --upload-dir test_data
ℹ️  4. If issues persist, see: docs/setup/WINDOWS_SETUP.md
```

## 🔧 Option 2: Manual Installation

### Installing Poppler

1. **Download Poppler for Windows**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases
   - Download latest `poppler-XX.XX.X_x86_64_static.zip`

2. **Extract and install**
   ```powershell
   # Create directory
   mkdir "C:\Program Files\poppler"
   
   # Extract downloaded zip to this directory
   # Ensure bin/ folder contains pdfinfo.exe, pdftoppm.exe, etc.
   ```

3. **Add to PATH**
   ```powershell
   # Add to system PATH (as Administrator)
   $path = [Environment]::GetEnvironmentVariable("PATH", "Machine")
   $newPath = "$path;C:\Program Files\poppler\bin"
   [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
   ```

### Installing Tesseract

1. **Download Tesseract for Windows**
   - Go to: https://github.com/UB-Mannheim/tesseract/wiki
   - Download latest `tesseract-ocr-w64-setup-X.X.X.XXXXXXXX.exe`

2. **Run installer**
   - Run as Administrator
   - Use default installation directory: `C:\Program Files\Tesseract-OCR`
   - Installer automatically adds to PATH

3. **Verify installation**
   ```cmd
   tesseract --version
   ```

### Alternative: User-scope Installation

For restricted environments without admin privileges:

```powershell
# Poppler - Extract to user directory
mkdir "$env:LOCALAPPDATA\Programs\poppler"
# Extract zip contents here

# Tesseract - Use portable version or request admin install
# Some Tesseract installers support user-scope with /S /D=path

# Add to user PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$newUserPath = "$userPath;$env:LOCALAPPDATA\Programs\poppler\bin;$env:LOCALAPPDATA\Programs\Tesseract-OCR"
[Environment]::SetEnvironmentVariable("PATH", $newUserPath, "User")
```

## ✅ Verification

### Using TTRPG Center Verification

```powershell
# Comprehensive verification
python scripts/bulk_ingest.py --verify-deps
```

**Expected success output:**
```
🎉 Dependency Verification PASSED
All required tools (Poppler, Tesseract) are installed and functional.

Next steps:
  1. Run ingestion: python scripts/bulk_ingest.py --env dev --upload-dir <path>
  2. For setup help: .\scripts\setup_windows.ps1 --help
```

### Manual Verification

```cmd
# Test Poppler tools
pdfinfo -v
pdftoppm -v

# Test Tesseract
tesseract --version
```

**Expected output examples:**
```
C:\>pdfinfo -v
pdfinfo version 23.08.0

C:\>tesseract --version
tesseract 5.3.3
 leptonica-1.82.0
  libgif 5.2.1 : libjpeg 8d (libjpeg-turbo 2.1.3) : libpng 1.6.39 : libtiff 4.4.0 : zlib 1.2.11 : libwebp 1.2.4 : libopenjp2 2.4.0
```

## 🚨 Troubleshooting

### Common Issues

#### "Command not found" errors after installation

**Problem**: Tools installed but not in PATH
```
'pdfinfo' is not recognized as an internal or external command
```

**Solutions**:
1. **Restart terminal** - New PATH entries require session restart
2. **Check PATH manually**:
   ```cmd
   echo %PATH%
   ```
3. **Re-run setup**:
   ```powershell
   .\scripts\setup_windows.ps1 -Force
   ```

#### Permission denied during installation

**Problem**: Need admin privileges for system-wide install
```
Access to the path 'C:\Program Files\...' is denied
```

**Solutions**:
1. **Run as Administrator**: Right-click PowerShell → Run as Administrator
2. **Use user-scope**:
   ```powershell
   .\scripts\setup_windows.ps1 -UserScope
   ```

#### Network/download failures

**Problem**: Corporate firewall or network restrictions
```
Invoke-WebRequest : Unable to connect to the remote server
```

**Solutions**:
1. **Configure proxy** (if needed):
   ```powershell
   $env:https_proxy = "http://proxy.company.com:8080"
   ```
2. **Use offline mode** with manual downloads:
   ```powershell
   .\scripts\setup_windows.ps1 -Offline
   ```
3. **Manual installation** - Follow Option 2 above

#### Execution policy restrictions

**Problem**: PowerShell execution policy blocks scripts
```
.\scripts\setup_windows.ps1 : cannot be loaded because running scripts is disabled
```

**Solutions**:
1. **Temporary bypass**:
   ```powershell
   PowerShell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
   ```
2. **Enable for current user**:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

#### Tools exist but don't work

**Problem**: Old/corrupted installations
```
Preflight check failed: tesseract found but not functional
```

**Solutions**:
1. **Force reinstall**:
   ```powershell
   .\scripts\setup_windows.ps1 -Force
   ```
2. **Manual cleanup** and reinstall:
   ```powershell
   # Remove old installations
   Remove-Item "C:\Program Files\poppler" -Recurse -Force
   # Then reinstall
   ```

### Getting Help

1. **Check setup script help**:
   ```powershell
   .\scripts\setup_windows.ps1 -Help
   ```

2. **Run diagnostic verification**:
   ```powershell
   python scripts/bulk_ingest.py --verify-deps
   ```

3. **Check logs** for detailed error information in `env/dev/logs/`

4. **Report issues** with:
   - Windows version: `Get-ComputerInfo | Select WindowsProductName, WindowsVersion`
   - PowerShell version: `$PSVersionTable.PSVersion`
   - Error messages and logs

## 🎯 Post-Installation

### Test Your Setup

1. **Run verification**:
   ```powershell
   python scripts/bulk_ingest.py --verify-deps
   ```

2. **Process a test document**:
   ```powershell
   # Create test directory with a PDF
   mkdir test_uploads
   # Copy a PDF file to test_uploads/
   
   # Run test ingestion
   python scripts/bulk_ingest.py --env dev --upload-dir test_uploads --no-cleanup
   ```

3. **Check results** - Should see successful 6-pass processing without dependency errors

### Integration with CI/CD

For **GitHub Actions** or other CI systems:

```yaml
# In your workflow
- name: Setup Windows Dependencies
  shell: powershell
  run: |
    .\scripts\setup_windows.ps1 -SystemScope
    python scripts\bulk_ingest.py --verify-deps
```

For **self-hosted runners**, ensure the setup script runs during runner initialization.

## 📚 Additional Resources

- **Poppler Documentation**: https://poppler.freedesktop.org/
- **Tesseract Documentation**: https://tesseract-ocr.github.io/
- **TTRPG Center Architecture**: [docs/PROJECT_ARCHITECTURE.md](../PROJECT_ARCHITECTURE.md)
- **Troubleshooting Guide**: [docs/TROUBLESHOOTING_REPORT.md](../TROUBLESHOOTING_REPORT.md)

---

**Last Updated**: December 2024  
**Script Version**: v1.0.0  
**Windows Compatibility**: Windows 10+, Windows 11