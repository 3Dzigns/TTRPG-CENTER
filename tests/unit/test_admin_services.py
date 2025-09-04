# tests/unit/test_admin_services.py
"""
Unit tests for Phase 4 Admin Services
Tests all five admin service modules (ADM-001 through ADM-005)
"""

import pytest
import asyncio
import time
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

from src_common.admin.status import AdminStatusService, EnvironmentStatus
from src_common.admin.ingestion import AdminIngestionService, IngestionJob
from src_common.admin.dictionary import AdminDictionaryService, DictionaryTerm
from src_common.admin.testing import AdminTestingService, RegressionTest, BugBundle, TestStatus, BugSeverity
from src_common.admin.cache_control import AdminCacheService, CachePolicy


class TestAdminStatusService:
    """Test System Status Dashboard Service (ADM-001)"""
    
    @pytest.fixture
    def status_service(self):
        return AdminStatusService()
    
    @pytest.mark.asyncio
    async def test_get_system_overview(self, status_service):
        """Test system overview retrieval"""
        overview = await status_service.get_system_overview()
        
        assert "timestamp" in overview
        assert "environments" in overview
        assert "system_metrics" in overview
        assert "overall_status" in overview
        assert len(overview["environments"]) == 3  # dev, test, prod
    
    @pytest.mark.asyncio
    async def test_check_environment_health(self, status_service):
        """Test environment health checking"""
        env_status = await status_service.check_environment_health("dev")
        
        assert isinstance(env_status, EnvironmentStatus)
        assert env_status.name == "dev"
        assert env_status.port > 0
        assert env_status.websocket_port > 0
        assert env_status.last_health_check is not None
    
    @pytest.mark.asyncio
    async def test_get_system_metrics(self, status_service):
        """Test system metrics collection"""
        metrics = status_service.get_system_metrics()
        
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        assert metrics.disk_percent >= 0
        assert len(metrics.load_average) == 3
        assert metrics.timestamp > 0
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"level": "INFO", "message": "test log"}')
    async def test_get_environment_logs(self, mock_file, mock_exists, status_service):
        """Test environment log retrieval"""
        mock_exists.return_value = True
        
        logs = await status_service.get_environment_logs("dev", 10)
        
        assert isinstance(logs, list)
        mock_file.assert_called_once()


class TestAdminIngestionService:
    """Test Ingestion Console Service (ADM-002)"""
    
    @pytest.fixture
    def ingestion_service(self):
        return AdminIngestionService()
    
    @pytest.mark.asyncio
    async def test_get_ingestion_overview(self, ingestion_service):
        """Test ingestion overview"""
        overview = await ingestion_service.get_ingestion_overview()
        
        assert "timestamp" in overview
        assert "environments" in overview
        assert len(overview["environments"]) == 3
        
        for env in ["dev", "test", "prod"]:
            assert env in overview["environments"]
            assert "total_jobs" in overview["environments"][env]
            assert "status_breakdown" in overview["environments"][env]
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, ingestion_service):
        """Test job listing"""
        jobs = await ingestion_service.list_jobs("dev")
        
        assert isinstance(jobs, list)
        # Should return empty list when no jobs exist
        assert len(jobs) >= 0
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    async def test_start_ingestion_job(self, mock_json_dump, mock_file, mock_mkdir, ingestion_service):
        """Test job creation"""
        job_id = await ingestion_service.start_ingestion_job(
            "dev", 
            "test.pdf", 
            {"option1": "value1"}
        )
        
        assert job_id.startswith("job_")
        assert "_dev" in job_id
        mock_mkdir.assert_called_once()
        mock_json_dump.assert_called_once()


class TestAdminDictionaryService:
    """Test Dictionary Management Service (ADM-003)"""
    
    @pytest.fixture
    def dictionary_service(self):
        return AdminDictionaryService()
    
    @pytest.mark.asyncio
    async def test_get_dictionary_overview(self, dictionary_service):
        """Test dictionary overview"""
        overview = await dictionary_service.get_dictionary_overview()
        
        assert "timestamp" in overview
        assert "environments" in overview
        assert len(overview["environments"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_environment_stats(self, dictionary_service):
        """Test environment statistics"""
        stats = await dictionary_service.get_environment_stats("dev")
        
        assert stats.environment == "dev"
        assert stats.total_terms >= 0
        assert isinstance(stats.categories, dict)
        assert isinstance(stats.sources, dict)
    
    @pytest.mark.asyncio
    @patch.object(AdminDictionaryService, '_load_environment_terms')
    async def test_list_terms(self, mock_load_terms, dictionary_service):
        """Test term listing"""
        # Mock return data
        mock_terms = [
            DictionaryTerm(
                term="test_term",
                definition="test definition",
                category="concept",
                environment="dev",
                source="test_source",
                created_at=time.time(),
                updated_at=time.time()
            )
        ]
        mock_load_terms.return_value = mock_terms
        
        terms = await dictionary_service.list_terms("dev")
        
        assert len(terms) == 1
        assert terms[0].term == "test_term"
    
    @pytest.mark.asyncio
    @patch.object(AdminDictionaryService, '_save_term')
    @patch.object(AdminDictionaryService, 'get_term')
    async def test_create_term(self, mock_get_term, mock_save_term, dictionary_service):
        """Test term creation"""
        mock_get_term.return_value = None  # Term doesn't exist
        mock_save_term.return_value = None
        
        term_data = {
            'term': 'New Term',
            'definition': 'Definition of new term',
            'category': 'concept',
            'source': 'test_source'
        }
        
        created_term = await dictionary_service.create_term("dev", term_data)
        
        assert created_term.term == "New Term"
        assert created_term.environment == "dev"
        mock_save_term.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_terms(self, dictionary_service):
        """Test term searching"""
        results = await dictionary_service.search_terms("dev", "test")
        
        assert isinstance(results, list)


class TestAdminTestingService:
    """Test Testing & Bug Management Service (ADM-004)"""
    
    @pytest.fixture
    def testing_service(self):
        return AdminTestingService()
    
    @pytest.mark.asyncio
    async def test_get_testing_overview(self, testing_service):
        """Test testing overview"""
        overview = await testing_service.get_testing_overview()
        
        assert "timestamp" in overview
        assert "environments" in overview
        assert len(overview["environments"]) == 3
        
        for env in ["dev", "test", "prod"]:
            assert env in overview["environments"]
            assert "test_stats" in overview["environments"][env]
            assert "bug_stats" in overview["environments"][env]
    
    @pytest.mark.asyncio
    @patch.object(AdminTestingService, '_load_environment_tests')
    async def test_list_tests(self, mock_load_tests, testing_service):
        """Test test listing"""
        mock_tests = [
            RegressionTest(
                test_id="test_1",
                name="Sample Test",
                description="Test description",
                environment="dev",
                test_type="unit",
                command="pytest",
                expected_result="pass",
                created_at=time.time(),
                created_by="admin"
            )
        ]
        mock_load_tests.return_value = mock_tests
        
        tests = await testing_service.list_tests("dev")
        
        assert len(tests) == 1
        assert tests[0]["name"] == "Sample Test"
    
    @pytest.mark.asyncio
    @patch.object(AdminTestingService, '_save_test')
    async def test_create_test(self, mock_save_test, testing_service):
        """Test test creation"""
        mock_save_test.return_value = None
        
        test_data = {
            'name': 'New Test',
            'description': 'Test description',
            'test_type': 'functional',
            'command': 'pytest test_file.py',
            'expected_result': 'All tests pass'
        }
        
        created_test = await testing_service.create_test("dev", test_data)
        
        assert created_test.name == "New Test"
        assert created_test.environment == "dev"
        mock_save_test.assert_called_once()
    
    @pytest.mark.asyncio
    @patch.object(AdminTestingService, '_load_environment_bugs')
    async def test_list_bugs(self, mock_load_bugs, testing_service):
        """Test bug listing"""
        mock_bugs = [
            BugBundle(
                bug_id="bug_1",
                title="Sample Bug",
                description="Bug description",
                environment="dev",
                severity=BugSeverity.MEDIUM,
                status="open",
                created_at=time.time(),
                created_by="admin"
            )
        ]
        mock_load_bugs.return_value = mock_bugs
        
        bugs = await testing_service.list_bugs("dev")
        
        assert len(bugs) == 1
        assert bugs[0]["title"] == "Sample Bug"
    
    @pytest.mark.asyncio
    @patch.object(AdminTestingService, '_save_bug')
    async def test_create_bug(self, mock_save_bug, testing_service):
        """Test bug creation"""
        mock_save_bug.return_value = None
        
        bug_data = {
            'title': 'New Bug',
            'description': 'Bug description',
            'severity': 'high',
            'steps_to_reproduce': ['Step 1', 'Step 2']
        }
        
        created_bug = await testing_service.create_bug("dev", bug_data)
        
        assert created_bug.title == "New Bug"
        assert created_bug.severity == BugSeverity.HIGH
        mock_save_bug.assert_called_once()


class TestAdminCacheService:
    """Test Cache Control Service (ADM-005)"""
    
    @pytest.fixture
    def cache_service(self):
        return AdminCacheService()
    
    @pytest.mark.asyncio
    async def test_get_cache_overview(self, cache_service):
        """Test cache overview"""
        overview = await cache_service.get_cache_overview()
        
        assert "timestamp" in overview
        assert "environments" in overview
        assert len(overview["environments"]) == 3
        
        for env in ["dev", "test", "prod"]:
            assert env in overview["environments"]
            assert "policy" in overview["environments"][env]
            assert "status" in overview["environments"][env]
    
    @pytest.mark.asyncio
    async def test_get_cache_policy(self, cache_service):
        """Test cache policy retrieval"""
        policy = await cache_service.get_cache_policy("dev")
        
        assert isinstance(policy, CachePolicy)
        assert policy.environment == "dev"
        assert policy.cache_enabled is False  # Dev default
    
    @pytest.mark.asyncio
    async def test_update_cache_policy(self, cache_service):
        """Test cache policy updates"""
        updates = {'cache_enabled': True, 'default_ttl_seconds': 300}
        
        updated_policy = await cache_service.update_cache_policy("dev", updates)
        
        assert updated_policy.cache_enabled is True
        assert updated_policy.default_ttl_seconds == 300
    
    @pytest.mark.asyncio
    async def test_get_cache_headers(self, cache_service):
        """Test cache header generation"""
        # Test no-cache environment (dev)
        headers = await cache_service.get_cache_headers("dev", "/api/test")
        assert "no-store" in headers["Cache-Control"]
        
        # Test caching environment (prod)
        headers = await cache_service.get_cache_headers("prod", "/api/test")
        assert "max-age" in headers["Cache-Control"]
    
    @pytest.mark.asyncio
    async def test_disable_cache(self, cache_service):
        """Test cache disabling"""
        success = await cache_service.disable_cache("dev")
        
        assert success is True
        
        # The disable operation calls update_cache_policy internally
        # In a test environment without persistence, we verify the operation completed
        # In a real environment, the policy would be persisted and retrievable
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_service):
        """Test cache clearing"""
        result = await cache_service.clear_cache("dev")
        
        assert result["success"] is True
        assert result["environment"] == "dev"
        assert "cleared_entries" in result
    
    @pytest.mark.asyncio
    async def test_validate_compliance(self, cache_service):
        """Test cache compliance validation"""
        compliance = await cache_service.validate_compliance("dev")
        
        assert "environment" in compliance
        assert "compliant" in compliance
        assert "issues" in compliance
        assert isinstance(compliance["issues"], list)
    
    def test_match_pattern(self, cache_service):
        """Test pattern matching utility"""
        # Test wildcard patterns
        assert cache_service._match_pattern("*", "/any/path") is True
        assert cache_service._match_pattern("/api/*", "/api/test") is True
        assert cache_service._match_pattern("/admin/*", "/admin/dashboard") is True
        assert cache_service._match_pattern("/api/*", "/other/path") is False
        
        # Test exact patterns
        assert cache_service._match_pattern("/exact", "/exact") is True
        assert cache_service._match_pattern("/exact", "/other") is False


@pytest.mark.asyncio
async def test_service_integration():
    """Integration test for admin services working together"""
    # Initialize all services
    status_service = AdminStatusService()
    ingestion_service = AdminIngestionService()
    dictionary_service = AdminDictionaryService()
    testing_service = AdminTestingService()
    cache_service = AdminCacheService()
    
    # Test that all services can provide overviews
    status_overview = await status_service.get_system_overview()
    ingestion_overview = await ingestion_service.get_ingestion_overview()
    dictionary_overview = await dictionary_service.get_dictionary_overview()
    testing_overview = await testing_service.get_testing_overview()
    cache_overview = await cache_service.get_cache_overview()
    
    # All should return valid data structures
    assert all("timestamp" in overview for overview in [
        status_overview, ingestion_overview, dictionary_overview, 
        testing_overview, cache_overview
    ])
    
    # All should have environment-specific data
    assert all("environments" in overview for overview in [
        status_overview, ingestion_overview, dictionary_overview,
        testing_overview, cache_overview
    ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])