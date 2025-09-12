# Log Cleanup System

Automated log file cleanup system for maintaining disk space by removing old log files based on configurable retention periods.

## Overview

The log cleanup system provides three ways to clean up old log files:

1. **Python Script** (`scripts/cleanup_logs.py`) - Core functionality with detailed options
2. **PowerShell Wrapper** (`scripts/cleanup_logs_simple.ps1`) - Windows-friendly wrapper
3. **Batch File** (`scripts/cleanup_logs.bat`) - Simple batch execution for Windows Scheduler

## Features

- **Date-based cleanup**: Removes files older than specified days based on file modification time
- **Multi-environment support**: Clean dev, test, prod, or all environments
- **Safe deletion**: Dry-run mode to preview changes before actual deletion
- **Comprehensive logging**: Detailed statistics and error reporting
- **Windows Scheduler compatible**: Designed for automated execution
- **Multiple file pattern support**: Handles various log file naming conventions

## Usage

### Python Script (Most Flexible)

```bash
# Basic usage - remove logs older than 30 days in dev
python scripts/cleanup_logs.py --retain 30 --env dev

# Dry run to see what would be deleted
python scripts/cleanup_logs.py --retain 7 --dry-run --verbose

# Clean all environments
python scripts/cleanup_logs.py --retain 14 --env all

# With custom log level
python scripts/cleanup_logs.py --retain 30 --env prod --log-level WARNING
```

### PowerShell Wrapper (Windows Recommended)

```powershell
# Basic cleanup
.\scripts\cleanup_logs_simple.ps1 -Retain 30 -Environment dev

# Dry run with verbose output
.\scripts\cleanup_logs_simple.ps1 -Retain 7 -DryRun -VerboseOutput

# Clean all environments
.\scripts\cleanup_logs_simple.ps1 -Retain 14 -Environment all
```

### Batch File (Windows Scheduler)

```cmd
REM Basic cleanup
scripts\cleanup_logs.bat 30 dev

REM Clean all environments with 14 day retention
scripts\cleanup_logs.bat 14 all
```

## Log File Patterns

The system automatically detects and processes these log file patterns:

- `*.log` - Standard log files
- `*.log.*` - Rotated log files (e.g., `app.log.1`)
- `*_*.log` - Date/time stamped logs
- `nightly_*.log` - Nightly run logs
- `bulk_ingest_*.log` - Bulk ingestion logs
- `scheduler_*.log` - Scheduler logs
- `pipeline_*.log` - Pipeline execution logs

## Directory Structure

The system scans these directories for log files:

```
env/
├── dev/logs/           # Development environment logs
├── test/logs/          # Test environment logs
├── prod/logs/          # Production environment logs
└── */                  # Subdirectories (scanned one level deep)

artifacts/logs/         # Additional artifact logs (if exists)
logs/                   # Root-level logs (if exists)
```

## Windows Task Scheduler Setup

### Method 1: Using Batch File (Simplest)

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Set trigger (e.g., weekly)
4. Action: Start a program
5. Program: `C:\path\to\TTRPG_Center\scripts\cleanup_logs.bat`
6. Arguments: `30 all` (30 days retention, all environments)
7. Start in: `C:\path\to\TTRPG_Center`

### Method 2: Using PowerShell

1. Open Task Scheduler
2. Create Basic Task
3. Action: Start a program
4. Program: `powershell.exe`
5. Arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\scripts\cleanup_logs_simple.ps1" -Retain 30 -Environment all`
6. Start in: `C:\path\to\TTRPG_Center`

### Method 3: Direct Python (Advanced)

1. Program: `C:\path\to\TTRPG_Center\.venv\Scripts\python.exe`
2. Arguments: `scripts/cleanup_logs.py --retain 30 --env all`
3. Start in: `C:\path\to\TTRPG_Center`

## Exit Codes

The scripts return these exit codes for monitoring:

- `0` - Success
- `1` - Errors occurred during cleanup
- `2` - Partial failures (some files couldn't be deleted)
- `130` - User interruption (Ctrl+C)

## Configuration Examples

### Conservative (Keep more logs)
```bash
# Keep 60 days of logs, clean weekly
python scripts/cleanup_logs.py --retain 60 --env all
```

### Aggressive (Save space)
```bash
# Keep only 7 days of logs, clean daily
python scripts/cleanup_logs.py --retain 7 --env all
```

### Production Safe
```bash
# Keep 90 days in production, 30 in dev/test
python scripts/cleanup_logs.py --retain 90 --env prod
python scripts/cleanup_logs.py --retain 30 --env dev
python scripts/cleanup_logs.py --retain 30 --env test
```

## Safety Features

1. **Dry Run Mode**: Always test with `--dry-run` first
2. **Verbose Output**: See exactly which files will be affected
3. **Error Handling**: Graceful handling of locked or inaccessible files
4. **Path Validation**: Verifies all paths before execution
5. **Environment Isolation**: Respects environment boundaries

## Monitoring and Alerting

### Log Output Analysis

The cleanup script provides detailed statistics:

```
Cleanup Summary:
  Files scanned: 150
  Files deleted: 45
  Files failed: 2
  Space freed: 12.5 MB
  Errors: 2
```

### Integration with Monitoring

For production monitoring, parse the exit codes and output:

```bash
# Example monitoring script
if ! python scripts/cleanup_logs.py --retain 30 --env prod; then
    echo "ALERT: Log cleanup failed" | mail -s "Log Cleanup Alert" admin@company.com
fi
```

## Troubleshooting

### Common Issues

1. **Permission Errors**
   - Ensure script runs with appropriate privileges
   - Check file permissions on log directories
   - Consider running Task Scheduler task as system account

2. **Path Issues**
   - Use absolute paths in Windows Scheduler
   - Verify virtual environment exists at expected location
   - Check "Start in" directory is set correctly

3. **Files Won't Delete**
   - Some files may be locked by running processes
   - Check if services need to be restarted
   - Review failed files in verbose output

### Debug Mode

For troubleshooting, use maximum verbosity:

```bash
python scripts/cleanup_logs.py --retain 30 --env dev --dry-run --verbose --log-level DEBUG
```

## Best Practices

1. **Start with Dry Run**: Always test retention policies with `--dry-run`
2. **Monitor Disk Usage**: Set appropriate retention based on available space
3. **Stagger Environments**: Clean different environments at different times
4. **Regular Schedule**: Run cleanup weekly or daily depending on log volume
5. **Backup Critical Logs**: Ensure important logs are backed up before cleanup
6. **Test Scheduling**: Verify scheduled tasks work correctly before production use

## File Safety

The cleanup system includes several safety measures:

- **Timestamp-based**: Uses file modification time, not filename parsing
- **Pattern Matching**: Only processes recognized log file patterns
- **Error Recovery**: Continues processing even if individual files fail
- **Atomic Operations**: Each file deletion is independent
- **Logging**: Records all actions for audit purposes

This ensures reliable cleanup while minimizing risk to critical system files.