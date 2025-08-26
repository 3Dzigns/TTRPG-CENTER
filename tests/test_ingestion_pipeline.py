"""Unit tests for ingestion pipeline concurrency and error handling"""

import unittest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.ingestion.pipeline import IngestionPipeline, ingestion_lock, ErrorSeverity, IngestionError


class TestIngestionPipeline(unittest.TestCase):
    """Test cases for ingestion pipeline improvements"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pipeline = IngestionPipeline()
        self.test_file_list = [
            {
                "path": "/test/file1.pdf",
                "metadata": {"title": "Test File 1", "system": "D&D 5E"}
            },
            {
                "path": "/test/file2.pdf", 
                "metadata": {"title": "Test File 2", "system": "Pathfinder 2E"}
            }
        ]
    
    @patch('app.ingestion.pipeline.Path.mkdir')
    @patch('builtins.open')
    def test_ingestion_lock_success(self, mock_open, mock_mkdir):
        """Test successful ingestion lock acquisition"""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.fileno.return_value = 1
        
        with patch('msvcrt.locking') as mock_locking:  # Windows
            with ingestion_lock("test"):
                mock_locking.assert_called()
                self.assertTrue(True)  # Test passes if no exception
    
    def test_ingestion_lock_already_held(self):
        """Test ingestion lock when another process holds it"""
        with patch('builtins.open') as mock_open:
            mock_open.side_effect = IOError("Lock held")
            
            with self.assertRaises(RuntimeError) as context:
                with ingestion_lock("test"):
                    pass
            
            self.assertIn("Another ingestion process is running", str(context.exception))
    
    def test_error_severity_classification(self):
        """Test error severity enumeration"""
        critical_error = IngestionError("Database failure", ErrorSeverity.CRITICAL)
        self.assertEqual(critical_error.severity, ErrorSeverity.CRITICAL)
        self.assertTrue(critical_error.rollback_needed)
        
        recoverable_error = IngestionError("File parse warning", ErrorSeverity.RECOVERABLE, False)
        self.assertEqual(recoverable_error.severity, ErrorSeverity.RECOVERABLE)
        self.assertFalse(recoverable_error.rollback_needed)
    
    @patch('app.ingestion.pipeline.ingestion_lock')
    @patch.object(IngestionPipeline, 'ingest_file')
    def test_bulk_ingest_with_lock(self, mock_ingest, mock_lock):
        """Test bulk ingestion uses locking mechanism"""
        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()
        
        mock_ingest.return_value = {"status": "completed", "source_id": "test_123"}
        
        results = self.pipeline.bulk_ingest(self.test_file_list, env="test")
        
        mock_lock.assert_called_with("test")
        self.assertEqual(len(results), 2)
    
    @patch('app.ingestion.pipeline.ingestion_lock')
    @patch.object(IngestionPipeline, 'ingest_file')
    @patch.object(IngestionPipeline, '_rollback_ingestions')
    def test_bulk_ingest_critical_error_rollback(self, mock_rollback, mock_ingest, mock_lock):
        """Test critical error triggers rollback in bulk ingestion"""
        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()
        
        # First file succeeds, second fails critically
        mock_ingest.side_effect = [
            {"status": "completed", "source_id": "test_123"},
            {"status": "failed", "error": "Critical database error"}
        ]
        
        results = self.pipeline.bulk_ingest(self.test_file_list, env="test")
        
        # Should have rolled back the successful ingestion
        mock_rollback.assert_called_once_with(["test_123"])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]["status"], "failed")
    
    @patch('app.ingestion.pipeline.ingestion_lock')
    @patch.object(IngestionPipeline, 'ingest_file')
    def test_bulk_ingest_recoverable_error_continues(self, mock_ingest, mock_lock):
        """Test recoverable error allows processing to continue"""
        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()
        
        # First file fails recoverably, second succeeds
        mock_ingest.side_effect = [
            {"status": "failed", "error": "File format not supported"},
            {"status": "completed", "source_id": "test_456"}
        ]
        
        results = self.pipeline.bulk_ingest(self.test_file_list, env="test")
        
        # Both files should be processed
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[1]["status"], "completed")
    
    @patch.object(IngestionPipeline, 'remove_source')
    def test_rollback_ingestions(self, mock_remove):
        """Test rollback functionality"""
        mock_remove.side_effect = [
            {"status": "removed", "chunks_deleted": 5},
            {"status": "removed", "chunks_deleted": 3}
        ]
        
        result = self.pipeline._rollback_ingestions(["source1", "source2"])
        
        self.assertEqual(result["rollback_attempted"], 2)
        self.assertEqual(result["rollback_successful"], 2)
        mock_remove.assert_any_call("source1")
        mock_remove.assert_any_call("source2")


class TestIngestionErrorHandling(unittest.TestCase):
    """Test cases for improved error handling"""
    
    def test_critical_error_properties(self):
        """Test critical error has correct properties"""
        error = IngestionError("Database connection failed", ErrorSeverity.CRITICAL)
        
        self.assertEqual(error.severity, ErrorSeverity.CRITICAL)
        self.assertTrue(error.rollback_needed)
        self.assertEqual(str(error), "Database connection failed")
    
    def test_recoverable_error_properties(self):
        """Test recoverable error has correct properties"""
        error = IngestionError("Invalid PDF structure", ErrorSeverity.RECOVERABLE, False)
        
        self.assertEqual(error.severity, ErrorSeverity.RECOVERABLE)
        self.assertFalse(error.rollback_needed)


if __name__ == '__main__':
    unittest.main()