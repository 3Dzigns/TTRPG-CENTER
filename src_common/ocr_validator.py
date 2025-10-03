"""
OCR Dependency Validator

Validates that all required OCR dependencies are available before attempting
to use unstructured.io for PDF processing.

Required dependencies:
1. tesseract-ocr (OCR engine)
2. poppler-utils (provides pdftotext)
3. OpenGL libraries (libGL.so.1 for cv2/unstructured)
"""

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyCheck:
    """Result of a single dependency check"""
    name: str
    command: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None


class OCRValidator:
    """Validates OCR dependencies for unstructured.io"""

    REQUIRED_TOOLS = [
        ("tesseract", "tesseract --version"),
        ("pdftotext", "pdftotext -v"),
    ]

    REQUIRED_LIBRARIES = [
        "libGL.so.1",
        "libglib-2.0.so.0",
    ]

    REQUIRED_TESSDATA = [
        "eng.traineddata",  # English language data
        "osd.traineddata",  # Orientation and script detection
    ]

    def __init__(self):
        self.checks: List[DependencyCheck] = []

    def validate_all(self) -> bool:
        """
        Validate all OCR dependencies.

        Returns:
            True if all dependencies are available, False otherwise
        """
        logger.info("Starting OCR dependency validation")

        # Check command-line tools
        for tool_name, test_command in self.REQUIRED_TOOLS:
            check = self._check_tool(tool_name, test_command)
            self.checks.append(check)
            if check.available:
                logger.info(f"✓ {tool_name} available: {check.version}")
            else:
                logger.error(f"✗ {tool_name} NOT available: {check.error}")

        # Check system libraries
        for lib_name in self.REQUIRED_LIBRARIES:
            check = self._check_library(lib_name)
            self.checks.append(check)
            if check.available:
                logger.info(f"✓ {lib_name} available")
            else:
                logger.warning(f"⚠ {lib_name} NOT available: {check.error}")

        # Check tessdata files
        for tessdata_file in self.REQUIRED_TESSDATA:
            check = self._check_tessdata(tessdata_file)
            self.checks.append(check)
            if check.available:
                logger.info(f"✓ {tessdata_file} available")
            else:
                logger.error(f"✗ {tessdata_file} NOT available: {check.error}")

        # Check Python imports
        unstructured_check = self._check_unstructured()
        self.checks.append(unstructured_check)
        if unstructured_check.available:
            logger.info(f"✓ unstructured library available: {unstructured_check.version}")
        else:
            logger.error(f"✗ unstructured library NOT available: {unstructured_check.error}")

        all_available = all(check.available for check in self.checks)

        if all_available:
            logger.info("✓ All OCR dependencies validated successfully")
        else:
            missing = [c.name for c in self.checks if not c.available]
            logger.error(f"✗ Missing OCR dependencies: {', '.join(missing)}")
            self._log_installation_instructions(missing)

        return all_available

    def _check_tool(self, tool_name: str, test_command: str) -> DependencyCheck:
        """Check if a command-line tool is available"""
        try:
            # Check if command exists
            if not shutil.which(tool_name):
                return DependencyCheck(
                    name=tool_name,
                    command=test_command,
                    available=False,
                    error=f"Command '{tool_name}' not found in PATH"
                )

            # Try to get version
            result = subprocess.run(
                test_command.split(),
                capture_output=True,
                text=True,
                timeout=5
            )

            # Extract version from output
            version_output = result.stdout + result.stderr
            version_line = version_output.split('\n')[0] if version_output else "unknown"

            return DependencyCheck(
                name=tool_name,
                command=test_command,
                available=True,
                version=version_line.strip()
            )

        except Exception as e:
            return DependencyCheck(
                name=tool_name,
                command=test_command,
                available=False,
                error=str(e)
            )

    def _check_library(self, lib_name: str) -> DependencyCheck:
        """Check if a system library is available"""
        try:
            # Use ldconfig to search for library (Linux)
            result = subprocess.run(
                ["ldconfig", "-p"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if lib_name in result.stdout:
                return DependencyCheck(
                    name=lib_name,
                    command="ldconfig -p",
                    available=True,
                    version="found"
                )
            else:
                return DependencyCheck(
                    name=lib_name,
                    command="ldconfig -p",
                    available=False,
                    error=f"Library not found in ldconfig cache"
                )

        except FileNotFoundError:
            # ldconfig not available (might not be Linux)
            return DependencyCheck(
                name=lib_name,
                command="ldconfig -p",
                available=True,  # Assume available if we can't check
                version="unchecked (ldconfig unavailable)"
            )
        except Exception as e:
            return DependencyCheck(
                name=lib_name,
                command="ldconfig -p",
                available=False,
                error=str(e)
            )

    def _check_tessdata(self, tessdata_file: str) -> DependencyCheck:
        """Check if tessdata language file exists"""
        import os

        # Check common tessdata locations
        tessdata_paths = [
            os.environ.get('TESSDATA_PREFIX'),
            '/usr/share/tesseract-ocr/5/tessdata',
            '/usr/share/tesseract-ocr/4.00/tessdata',
            '/usr/share/tessdata',
            '/usr/local/share/tessdata',
        ]

        for base_path in tessdata_paths:
            if not base_path:
                continue
            tessdata_path = os.path.join(base_path, tessdata_file)
            if os.path.isfile(tessdata_path):
                return DependencyCheck(
                    name=tessdata_file,
                    command=f"check {tessdata_path}",
                    available=True,
                    version=base_path
                )

        return DependencyCheck(
            name=tessdata_file,
            command="check tessdata paths",
            available=False,
            error=f"File not found in standard tessdata locations"
        )

    def _check_unstructured(self) -> DependencyCheck:
        """Check if unstructured library can be imported"""
        try:
            from unstructured.partition.pdf import partition_pdf

            # Try to get version
            try:
                import unstructured
                version = getattr(unstructured, '__version__', 'unknown')
            except:
                version = 'unknown'

            return DependencyCheck(
                name="unstructured",
                command="import unstructured.partition.pdf",
                available=True,
                version=version
            )

        except ImportError as e:
            return DependencyCheck(
                name="unstructured",
                command="import unstructured.partition.pdf",
                available=False,
                error=str(e)
            )

    def _log_installation_instructions(self, missing: List[str]):
        """Log installation instructions for missing dependencies"""
        logger.error("=" * 60)
        logger.error("OCR DEPENDENCY INSTALLATION INSTRUCTIONS")
        logger.error("=" * 60)

        if "tesseract" in missing:
            logger.error("Tesseract OCR:")
            logger.error("  Debian/Ubuntu: apt-get install tesseract-ocr tesseract-ocr-eng")
            logger.error("  Alpine: apk add tesseract-ocr")

        if "pdftotext" in missing:
            logger.error("Poppler Utils (pdftotext):")
            logger.error("  Debian/Ubuntu: apt-get install poppler-utils")
            logger.error("  Alpine: apk add poppler-utils")

        if any("libGL" in m for m in missing):
            logger.error("OpenGL Libraries:")
            logger.error("  Debian/Ubuntu: apt-get install libgl1 libglib2.0-0")
            logger.error("  Alpine: apk add mesa-gl glib")

        if "unstructured" in missing:
            logger.error("Unstructured Library:")
            logger.error("  pip install unstructured[pdf]")

        if any("traineddata" in m for m in missing):
            logger.error("Tesseract Language Data:")
            logger.error("  Debian/Ubuntu: apt-get install tesseract-ocr-eng")
            logger.error("  Alpine: apk add tesseract-ocr-data-eng")
            logger.error("  Set TESSDATA_PREFIX environment variable if needed")

        logger.error("=" * 60)

    def get_summary(self) -> str:
        """Get a summary of all dependency checks"""
        summary = ["OCR Dependency Validation Summary:"]
        for check in self.checks:
            status = "✓" if check.available else "✗"
            version_info = f" ({check.version})" if check.version else ""
            summary.append(f"  {status} {check.name}{version_info}")
        return "\n".join(summary)


def validate_ocr_dependencies() -> bool:
    """
    Validate all OCR dependencies required for unstructured.io.

    Returns:
        True if all dependencies are available, False otherwise
    """
    validator = OCRValidator()
    return validator.validate_all()
