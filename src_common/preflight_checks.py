# src_common/preflight_checks.py
"""
Preflight Dependency Checks for TTRPG Center Ingestion Pipeline

Validates that all required external tools are available before starting
the bulk ingestion process. Implements fail-fast behavior to prevent
silent failures that result in 0-chunk extractions.

Key Features:
- Platform-aware dependency checking
- Windows path auto-discovery for common install locations
- Structured logging with actionable error messages
- Custom PreflightError exception for clear error handling
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import logging using absolute import to avoid conflicts with local logging.py
import logging as _logging

logger = _logging.getLogger(__name__)


class PreflightError(Exception):
    """
    Custom exception raised when preflight dependency checks fail.
    
    This exception indicates that required external tools (Poppler, Tesseract)
    are missing or non-functional, and the ingestion process should not proceed.
    """
    pass


class PreflightValidator:
    """
    Validates external dependencies required for TTRPG Center ingestion pipeline.
    
    Provides comprehensive checking for:
    - Poppler utilities (pdfinfo, pdftoppm) for PDF processing
    - Tesseract OCR for image-based text extraction
    - Platform-specific path auto-discovery on Windows
    """
    
    def __init__(self):
        self.tools_status: Dict[str, str] = {}
        self.original_path = os.environ.get("PATH", "")
        self.path_extensions: List[str] = []
    
    def _run_tool_command(self, cmd: List[str], timeout: int = 5) -> Tuple[bool, str]:
        """
        Safely execute a tool command and capture output.
        
        Args:
            cmd: Command and arguments to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Tuple of (success, output_text)
        """
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )
            # Some tools (like pdfinfo -v) write to stderr
            output = result.stderr.strip() if result.stderr else result.stdout.strip()
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s"
        except Exception as e:
            return False, f"Command failed: {e}"
    
    def _discover_windows_paths(self) -> List[Path]:
        """
        Discover common installation paths for Poppler and Tesseract on Windows.
        
        Returns:
            List of paths to add to environment PATH
        """
        if sys.platform != "win32":
            return []
        
        candidate_paths = []
        
        # Common Tesseract installation paths
        tesseract_paths = [
            Path("C:/Program Files/Tesseract-OCR"),
            Path("C:/Program Files (x86)/Tesseract-OCR"),
            Path(os.path.expanduser("~/AppData/Local/Programs/Tesseract-OCR")),
        ]
        
        # Common Poppler installation paths
        poppler_base_paths = [
            Path("C:/Program Files/poppler"),
            Path("C:/Program Files (x86)/poppler"), 
            Path("C:/Users/Public/Poppler"),
            Path(os.path.expanduser("~/Documents/Poppler")),
        ]
        
        # Check for Tesseract
        for path in tesseract_paths:
            if path.exists() and (path / "tesseract.exe").exists():
                candidate_paths.append(path)
                logger.info(f"Found Tesseract at: {path}")
                break
        
        # Check for Poppler (look in bin subdirectories)
        for base_path in poppler_base_paths:
            if base_path.exists():
                # Look for version-specific directories
                for subdir in base_path.iterdir():
                    if subdir.is_dir():
                        bin_path = subdir / "Library" / "bin"
                        if bin_path.exists() and (bin_path / "pdfinfo.exe").exists():
                            candidate_paths.append(bin_path)
                            logger.info(f"Found Poppler at: {bin_path}")
                            break
                        
                        bin_path = subdir / "bin"
                        if bin_path.exists() and (bin_path / "pdfinfo.exe").exists():
                            candidate_paths.append(bin_path)
                            logger.info(f"Found Poppler at: {bin_path}")
                            break
                
                # Also check direct bin directory
                bin_path = base_path / "bin"
                if bin_path.exists() and (bin_path / "pdfinfo.exe").exists():
                    candidate_paths.append(bin_path)
                    logger.info(f"Found Poppler at: {bin_path}")
        
        return candidate_paths
    
    def _extend_path_temporarily(self, additional_paths: List[Path]) -> None:
        """
        Temporarily extend the system PATH for the current process.
        
        Args:
            additional_paths: Paths to add to the beginning of PATH
        """
        if not additional_paths:
            return
        
        path_strings = [str(path) for path in additional_paths]
        self.path_extensions.extend(path_strings)
        
        current_path = os.environ.get("PATH", "")
        new_path = os.pathsep.join(path_strings + [current_path])
        os.environ["PATH"] = new_path
        
        logger.info(f"Extended PATH with: {', '.join(path_strings)}")
    
    def _validate_poppler_tools(self) -> bool:
        """
        Validate that Poppler utilities (pdfinfo, pdftoppm) are available and functional.
        
        Returns:
            True if all Poppler tools are available and working
        """
        poppler_tools = ["pdfinfo", "pdftoppm"]
        all_ok = True
        
        for tool in poppler_tools:
            if not shutil.which(tool):
                self.tools_status[tool] = "Not found in PATH"
                all_ok = False
                logger.error(f"Poppler {tool} not found in PATH")
                continue
            
            # Test tool functionality
            success, output = self._run_tool_command([tool, "-v"])
            if success and output:
                # Extract version info (pdfinfo -v output format varies)
                version_info = output.split()[0] if output.split() else "unknown"
                self.tools_status[tool] = f"Available: {version_info}"
                logger.info(f"Poppler {tool}: {output.split('\\n')[0] if output else 'working'}")
            else:
                self.tools_status[tool] = f"Not functional: {output}"
                all_ok = False
                logger.error(f"Poppler {tool} found but not functional: {output}")
        
        return all_ok
    
    def _validate_tesseract(self) -> bool:
        """
        Validate that Tesseract OCR is available and functional.
        
        Returns:
            True if Tesseract is available and working
        """
        if not shutil.which("tesseract"):
            self.tools_status["tesseract"] = "Not found in PATH"
            logger.error("Tesseract not found in PATH")
            return False
        
        # Test Tesseract functionality
        success, output = self._run_tool_command(["tesseract", "--version"])
        if success and output:
            version_line = output.split('\\n')[0] if output else "unknown version"
            self.tools_status["tesseract"] = f"Available: {version_line}"
            logger.info(f"Tesseract: {version_line}")
            return True
        else:
            self.tools_status["tesseract"] = f"Not functional: {output}"
            logger.error(f"Tesseract found but not functional: {output}")
            return False
    
    def _log_failure_guidance(self) -> None:
        """Log actionable guidance for resolving missing dependencies."""
        logger.error("PREFLIGHT CHECK FAILED - Missing required OCR tools")
        logger.error("")
        logger.error("Required tools for PDF processing:")
        logger.error("  • Poppler utilities (pdfinfo, pdftoppm)")
        logger.error("  • Tesseract OCR")
        logger.error("")
        logger.error("Installation instructions:")
        logger.error("  Windows:")
        logger.error("    - Poppler: https://github.com/oschwartz10612/poppler-windows/releases")
        logger.error("    - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        logger.error("  Linux:")
        logger.error("    - sudo apt-get install poppler-utils tesseract-ocr")
        logger.error("  macOS:")
        logger.error("    - brew install poppler tesseract")
        logger.error("")
        logger.error("After installation, ensure tools are in system PATH or set:")
        logger.error("  POPPLER_PATH=<path to poppler bin directory>")
        logger.error("  TESSERACT_PATH=<path to tesseract executable>")
    
    def validate_dependencies(self) -> None:
        """
        Perform comprehensive validation of all required dependencies.
        
        Raises:
            PreflightError: If any required dependencies are missing or non-functional
        """
        logger.info("Starting preflight dependency validation...")
        
        # Auto-discover paths on Windows
        if sys.platform == "win32":
            discovered_paths = self._discover_windows_paths()
            if discovered_paths:
                self._extend_path_temporarily(discovered_paths)
        
        # Validate each tool category
        poppler_ok = self._validate_poppler_tools()
        tesseract_ok = self._validate_tesseract()
        
        # Summary and result
        if poppler_ok and tesseract_ok:
            logger.info("PREFLIGHT CHECK PASSED - All required tools available")
            for tool, status in self.tools_status.items():
                logger.info(f"  {tool}: {status}")
        else:
            self._log_failure_guidance()
            
            # List specific failures
            failed_tools = [
                tool for tool, status in self.tools_status.items() 
                if "Not found" in status or "Not functional" in status
            ]
            
            raise PreflightError(
                f"Required OCR tools not available: {', '.join(failed_tools)}. "
                "See log above for installation instructions."
            )
    
    def cleanup(self) -> None:
        """Restore original PATH environment variable."""
        if self.path_extensions:
            os.environ["PATH"] = self.original_path
            logger.debug("Restored original PATH")


def run_preflight_checks() -> None:
    """
    Run all preflight dependency checks.
    
    This is the main entry point for preflight validation. It checks all
    required external tools and raises PreflightError if any are missing.
    
    Raises:
        PreflightError: If required dependencies are missing or non-functional
    """
    validator = PreflightValidator()
    try:
        validator.validate_dependencies()
    finally:
        validator.cleanup()


if __name__ == "__main__":
    # Allow running preflight checks standalone for testing
    try:
        run_preflight_checks()
        print("All preflight checks passed")
        sys.exit(0)
    except PreflightError as e:
        print(f"Preflight check failed: {e}")
        sys.exit(2)