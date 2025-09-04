# tests/unit/test_fr1_e6_size_splitting.py
"""
Unit tests for FR1-E6: Configurable size-based auto-splitting in PDF pre-processor
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src_common.pdf_chapter_splitter import PDFChapterSplitter, SplitManifest, ChapterSplit
from src_common.fr1_config import FR1Config


class TestFR1E6SizeSplitting:
    """Test suite for FR1-E6 size-based auto-splitting functionality"""
    
    def test_fr1_config_initialization(self):
        """Test FR1Config initialization with different environments"""
        # Test dev environment (default)
        config = FR1Config("dev")
        assert config.env == "dev"
        assert config.get("preprocessor", "size_threshold_mb") == 30.0  # Dev threshold
        
        # Test prod environment
        config = FR1Config("prod")
        assert config.env == "prod"
        assert config.get("preprocessor", "size_threshold_mb") == 50.0  # Prod threshold
    
    def test_should_split_by_size(self):
        """Test size-based splitting decision logic"""
        config = FR1Config("dev")  # 30MB threshold
        
        # File below threshold
        assert not config.should_split_by_size(25.0)
        
        # File above threshold
        assert config.should_split_by_size(35.0)
        
        # File exactly at threshold
        assert config.should_split_by_size(30.0)
    
    @patch('pathlib.Path.stat')
    def test_should_auto_split(self, mock_stat):
        """Test PDFChapterSplitter.should_auto_split method"""
        # Mock file size (40MB)
        mock_stat.return_value.st_size = 40 * 1024 * 1024
        
        splitter = PDFChapterSplitter(env="dev")  # 30MB threshold
        pdf_path = Path("test.pdf")
        
        should_split, manifest = splitter.should_auto_split(pdf_path)
        
        # Should split (40MB > 30MB threshold)
        assert should_split is True
        assert manifest.split_triggered is True
        assert manifest.original_size_mb == 40.0
        assert manifest.threshold_mb == 30.0
        assert manifest.split_strategy == "pending"
    
    @patch('pathlib.Path.stat')
    def test_should_not_auto_split(self, mock_stat):
        """Test PDFChapterSplitter.should_auto_split when below threshold"""
        # Mock file size (20MB)
        mock_stat.return_value.st_size = 20 * 1024 * 1024
        
        splitter = PDFChapterSplitter(env="dev")  # 30MB threshold
        pdf_path = Path("test.pdf")
        
        should_split, manifest = splitter.should_auto_split(pdf_path)
        
        # Should not split (20MB < 30MB threshold)
        assert should_split is False
        assert manifest.split_triggered is False
        assert manifest.original_size_mb == 20.0
        assert manifest.split_strategy == "no_split"
    
    def test_split_manifest_dataclass(self):
        """Test SplitManifest dataclass functionality"""
        manifest = SplitManifest(
            original_file="test.pdf",
            original_size_bytes=1024,
            original_size_mb=1.0,
            threshold_mb=30.0,
            split_strategy="semantic_chapters",
            split_triggered=True,
            num_parts=3,
            part_checksums=["abc123", "def456", "ghi789"],
            processing_time_ms=5000
        )
        
        assert manifest.original_file == "test.pdf"
        assert manifest.num_parts == 3
        assert len(manifest.part_checksums) == 3
        assert manifest.processing_time_ms == 5000
    
    @patch('src_common.pdf_chapter_splitter.open')
    @patch('src_common.pdf_chapter_splitter.pypdf.PdfReader')
    @patch('pathlib.Path.stat')
    def test_detect_chapters_includes_manifest(self, mock_stat, mock_pdf_reader, mock_open):
        """Test that detect_chapters includes manifest in ChapterSplit result"""
        # Mock file size (40MB - should trigger splitting)
        mock_stat.return_value.st_size = 40 * 1024 * 1024
        
        # Mock PDF with 10 pages
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(10)]
        for i, page in enumerate(mock_reader.pages):
            page.extract_text.return_value = f"Page {i+1} content"
        
        mock_pdf_reader.return_value = mock_reader
        
        splitter = PDFChapterSplitter(env="dev")
        pdf_path = Path("test.pdf")
        
        result = splitter.detect_chapters(pdf_path)
        
        # Verify ChapterSplit includes manifest
        assert isinstance(result, ChapterSplit)
        assert result.manifest is not None
        assert result.manifest.original_size_mb == 40.0
        assert result.manifest.split_triggered is True
        assert result.manifest.processing_time_ms > 0
    
    @patch('src_common.pdf_chapter_splitter.open')
    @patch('pathlib.Path.stat')
    def test_fallback_split_includes_manifest(self, mock_stat, mock_open):
        """Test that _fallback_split includes manifest in ChapterSplit result"""
        # Mock file size (15MB - should not trigger splitting)
        mock_stat.return_value.st_size = 15 * 1024 * 1024
        
        # Mock file opening to raise exception, forcing fallback
        mock_open.side_effect = Exception("PDF read error")
        
        splitter = PDFChapterSplitter(env="dev")
        pdf_path = Path("test.pdf")
        
        result = splitter.detect_chapters(pdf_path)
        
        # Verify fallback ChapterSplit includes manifest
        assert isinstance(result, ChapterSplit)
        assert result.manifest is not None
        assert result.manifest.original_size_mb == 15.0
        assert result.manifest.split_triggered is False
        assert result.manifest.split_strategy == "error"
        assert result.fallback_used is True
    
    def test_config_validation(self):
        """Test FR1Config validation logic"""
        config = FR1Config("dev")
        
        # Valid configuration should pass
        assert config.validate_config() is True
        
        # Test with invalid threshold (will be caught in validation)
        config._config["preprocessor"]["size_threshold_mb"] = -5.0
        assert config.validate_config() is False
    
    def test_environment_variable_overrides(self):
        """Test environment variable overrides for FR1 configuration"""
        import os
        
        # Set environment variable
        os.environ["FR1_SIZE_THRESHOLD_MB"] = "45.0"
        
        try:
            config = FR1Config("test")
            # Should use env var override instead of test default (25.0)
            assert config.get("preprocessor", "size_threshold_mb") == 45.0
        finally:
            # Clean up
            if "FR1_SIZE_THRESHOLD_MB" in os.environ:
                del os.environ["FR1_SIZE_THRESHOLD_MB"]


if __name__ == "__main__":
    pytest.main([__file__])