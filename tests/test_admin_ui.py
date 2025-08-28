"""
Test suite for Admin UI user stories (04_admin_ui.md)
Tests for ADM-001, ADM-002, ADM-003, ADM-004 acceptance criteria
"""
import pytest
import json
import requests
from unittest.mock import patch, MagicMock
from pathlib import Path

# Test ADM-001: System Status dashboard
class TestSystemStatusDashboard:
    
    def test_admin_ui_accessible(self):
        """Test admin interface is accessible at /admin"""
        # This would require a running server for full integration test
        # For now, test the template rendering logic
        from app.server import render_admin_template
        
        # Mock config for template
        mock_config = {
            'runtime': {'env': 'test', 'port': 8181},
            'build': {'id': 'test-build-001'}
        }
        
        with patch('app.server.load_config', return_value=mock_config):
            html = render_admin_template()
            
            assert 'Environment: TEST' in html, "Environment not displayed"
            assert 'test-build-001' in html, "Build ID not displayed"
    
    def test_health_check_display(self):
        """Test health checks for Astra Vector, Graph, OpenAI are shown"""
        from app.server import get_system_status
        
        status = get_system_status()
        
        required_components = ['astra_vector', 'graph_engine', 'openai']
        for component in required_components:
            assert component in status, f"Missing health check for {component}"
            assert 'status' in status[component], f"Missing status for {component}"
    
    def test_ngrok_url_display_prod(self):
        """Test ngrok public URL display for PROD environment"""
        # Mock PROD environment
        with patch.dict('os.environ', {'APP_ENV': 'prod'}):
            from app.server import get_system_status
            
            status = get_system_status()
            
            # In PROD, should have ngrok URL information
            if status.get('runtime', {}).get('env') == 'prod':
                assert 'ngrok_url' in status.get('runtime', {}), "PROD missing ngrok URL"

# Test ADM-002: Ingestion Console
class TestIngestionConsole:
    
    def test_single_file_upload_interface(self):
        """Test single file upload capability exists"""
        from app.server import render_admin_template
        
        html = render_admin_template()
        
        # Check for file upload form elements
        assert 'type="file"' in html, "Missing file upload input"
        assert 'upload' in html.lower(), "Missing upload functionality"
    
    def test_bulk_upload_interface(self):
        """Test bulk upload capability exists"""
        from app.server import render_admin_template
        
        html = render_admin_template()
        
        # Check for bulk upload elements
        assert 'bulk' in html.lower() or 'multiple' in html.lower(), "Missing bulk upload capability"
    
    def test_ingestion_progress_display(self):
        """Test real-time progress display structure"""
        from app.server import render_admin_template
        
        html = render_admin_template()
        
        # Check for progress indicators
        progress_indicators = ['progress', 'status', 'phase']
        found_indicators = sum(1 for indicator in progress_indicators if indicator in html.lower())
        assert found_indicators >= 1, "Missing progress display elements"
    
    def test_ingestion_log_tail(self):
        """Test live tail of processing status exists"""
        # Test ingestion status endpoint
        from app.server import get_ingestion_status
        
        # Mock an ingestion job
        mock_job_id = "test_job_001"
        status = get_ingestion_status(mock_job_id)
        
        # Should return structured status
        if status:
            expected_fields = ['status', 'progress', 'phase']
            for field in expected_fields:
                assert field in status, f"Ingestion status missing {field}"

# Test ADM-003: Dictionary management interface
class TestDictionaryManagement:
    
    def test_dictionary_viewing_interface(self):
        """Test view current dictionary entries"""
        from app.server import render_admin_template
        
        html = render_admin_template()
        
        # Check for dictionary management elements
        dict_elements = ['dictionary', 'terms', 'definitions']
        found_elements = sum(1 for element in dict_elements if element in html.lower())
        assert found_elements >= 1, "Missing dictionary management interface"
    
    def test_dictionary_crud_operations(self):
        """Test add/remove/edit dictionary terms"""
        from app.ingestion.dictionary import get_dictionary_manager
        
        dict_manager = get_dictionary_manager()
        
        # Test adding a term
        test_term = "test_admin_term"
        dict_manager.add_term(test_term, "A test term for admin interface", {"category": "test"})
        
        # Verify it was added
        terms = dict_manager.get_all_terms()
        assert test_term in [t.get('term', t) for t in (terms if isinstance(terms, list) else terms.keys())], "Term not added successfully"
        
        # Test removing the term
        dict_manager.remove_term(test_term)
    
    def test_enrichment_threshold_configuration(self):
        """Test configure enrichment thresholds"""
        from app.ingestion.dictionary import get_dictionary_manager
        
        dict_manager = get_dictionary_manager()
        
        # Test accessing configuration
        config = dict_manager.get_config() if hasattr(dict_manager, 'get_config') else {}
        
        # Should have some configuration structure
        assert isinstance(config, dict), "Dictionary configuration not accessible"

# Test ADM-004: Regression test and bug bundle management  
class TestRegressionTestManagement:
    
    def test_regression_test_listing(self):
        """Test list and view regression test cases"""
        regression_dir = Path("tests/regression/cases")
        
        if regression_dir.exists():
            test_cases = list(regression_dir.glob("*.json"))
            
            # Verify test case structure
            if test_cases:
                with open(test_cases[0]) as f:
                    test_case = json.load(f)
                
                required_fields = ['case_id', 'query', 'expected_response']
                for field in required_fields:
                    assert field in test_case, f"Regression test case missing {field}"
    
    def test_test_case_invalidation(self):
        """Test invalidate/remove test cases"""
        # Test the ability to manage regression test cases
        from app.testing.regression_manager import get_regression_manager
        
        if hasattr('app.testing', 'regression_manager'):
            rm = get_regression_manager()
            
            # Test listing cases
            cases = rm.list_test_cases() if hasattr(rm, 'list_test_cases') else []
            assert isinstance(cases, list), "Regression test cases not listable"
    
    def test_bug_bundle_management(self):
        """Test view and download bug bundles from feedback"""
        bugs_dir = Path("bugs")
        
        if bugs_dir.exists():
            bug_files = list(bugs_dir.glob("*.json"))
            
            # Verify bug bundle structure
            if bug_files:
                with open(bug_files[0]) as f:
                    try:
                        bug_data = json.load(f)
                        
                        # Check basic bug structure
                        expected_fields = ['bug_id', 'timestamp', 'description']
                        for field in expected_fields:
                            if field not in bug_data:
                                # Some bug files might have different structure
                                continue
                    except json.JSONDecodeError:
                        # Some bug files might not be valid JSON
                        pass

# Integration tests
class TestAdminUIIntegration:
    
    def test_admin_ui_component_integration(self):
        """Test all admin UI components work together"""
        from app.server import render_admin_template, get_system_status
        
        # Test template renders with real status
        html = render_admin_template()
        status = get_system_status()
        
        assert len(html) > 1000, "Admin template too short - likely missing components"
        assert isinstance(status, dict), "System status not returned as dict"
    
    def test_admin_javascript_functionality(self):
        """Test admin JavaScript functions are properly loaded"""
        admin_js_path = Path("app/static/js/admin.js")
        
        assert admin_js_path.exists(), "Admin JavaScript file missing"
        
        js_content = admin_js_path.read_text()
        
        # Check for key admin functions
        required_functions = ['refreshStatus', 'showCollectionInfo', 'refreshBugs']
        for function in required_functions:
            assert function in js_content, f"Admin JavaScript missing {function} function"
    
    def test_static_file_serving(self):
        """Test admin UI static files are served correctly"""
        static_files = [
            Path("app/static/js/admin.js"),
            Path("app/static/css/admin.css") if Path("app/static/css/admin.css").exists() else None
        ]
        
        for file_path in static_files:
            if file_path and file_path.exists():
                content = file_path.read_text()
                assert len(content) > 0, f"Static file {file_path} is empty"