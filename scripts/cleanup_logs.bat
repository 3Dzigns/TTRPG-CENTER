@echo off
REM scripts/cleanup_logs.bat
REM Windows Batch wrapper for log cleanup utility
REM
REM Usage examples:
REM   cleanup_logs.bat 30 dev
REM   cleanup_logs.bat 7 all
REM   cleanup_logs.bat 14 prod
REM
REM Parameters:
REM   %1 = Retain days (required)
REM   %2 = Environment: dev/test/prod/all (default: dev)

setlocal enabledelayedexpansion

REM Get script directory and project root
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Change to project root
pushd "%PROJECT_ROOT%"

echo TTRPG Center Log Cleanup Utility
echo ==================================
echo Project Root: %PROJECT_ROOT%
echo.

REM Validate arguments
if "%1"=="" (
    echo Error: Retention days parameter required
    echo Usage: cleanup_logs.bat ^<retain_days^> [environment]
    echo Example: cleanup_logs.bat 30 dev
    exit /b 1
)

set "RETAIN_DAYS=%1"
set "ENVIRONMENT=%2"
if "%ENVIRONMENT%"=="" set "ENVIRONMENT=dev"

echo Retention Period: %RETAIN_DAYS% days
echo Environment: %ENVIRONMENT%
echo.

REM Check if retention days is a valid number
echo %RETAIN_DAYS%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    echo Error: Retention days must be a positive number
    exit /b 1
)

REM Check if virtual environment exists
set "VENV_PATH=%PROJECT_ROOT%\.venv"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Error: Virtual environment not found at: %VENV_PATH%
    echo Please run the setup scripts first to create the virtual environment
    exit /b 1
)

echo Using Python: %PYTHON_EXE%

REM Build cleanup script path
set "CLEANUP_SCRIPT=%SCRIPT_DIR%cleanup_logs.py"

if not exist "%CLEANUP_SCRIPT%" (
    echo Error: Cleanup script not found at: %CLEANUP_SCRIPT%
    exit /b 1
)

echo Using Cleanup Script: %CLEANUP_SCRIPT%
echo.

REM Execute Python cleanup script
echo Executing log cleanup...
"%PYTHON_EXE%" "%CLEANUP_SCRIPT%" --retain %RETAIN_DAYS% --env %ENVIRONMENT% --log-level INFO

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Python script completed with exit code: %EXIT_CODE%

REM Interpret exit codes
if %EXIT_CODE%==0 (
    echo ✓ Log cleanup completed successfully
) else if %EXIT_CODE%==1 (
    echo ⚠ Log cleanup completed with errors
) else if %EXIT_CODE%==2 (
    echo ⚠ Log cleanup completed with partial failures  
) else if %EXIT_CODE%==130 (
    echo ⚠ Log cleanup was interrupted by user
) else (
    echo ✗ Log cleanup failed with exit code: %EXIT_CODE%
)

REM Return to original directory
popd

echo.
echo Log cleanup operation finished at: %date% %time%

exit /b %EXIT_CODE%