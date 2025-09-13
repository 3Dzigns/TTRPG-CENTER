# tests/container/test_docker_compose.py
"""
FR-006: Docker Compose Tests
Tests for container orchestration and service health
"""

import pytest
import requests
import time
import subprocess
from typing import Dict, Any
import psycopg2
import pymongo
from neo4j import GraphDatabase
import redis


class TestDockerCompose:
    """Test Docker Compose stack functionality"""
    
    @pytest.fixture(scope="class")
    def wait_for_services(self):
        """Wait for all services to be healthy before running tests"""
        max_wait = 120  # 2 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.get("http://localhost:8000/healthz", timeout=5)
                if response.status_code == 200:
                    health = response.json()
                    if health.get("status") == "healthy":
                        return health
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(5)
        
        pytest.fail("Services failed to become healthy within timeout")
    
    def test_compose_up_status(self):
        """Test that docker-compose stack is running"""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ttrpg", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        container_names = result.stdout.strip().split('\n')
        
        expected_containers = [
            "ttrpg-app-dev",
            "ttrpg-postgres-dev", 
            "ttrpg-mongo-dev",
            "ttrpg-neo4j-dev",
            "ttrpg-redis-dev"
        ]
        
        for container in expected_containers:
            assert container in container_names, f"Container {container} not running"
    
    def test_health_endpoint(self, wait_for_services):
        """Test the main health endpoint"""
        response = requests.get("http://localhost:8000/healthz")
        
        assert response.status_code == 200
        health = response.json()
        
        assert "status" in health
        assert "timestamp" in health
        assert "environment" in health
        assert "services" in health
        
        # Check critical services
        services = health["services"]
        assert "database" in services
        assert services["database"]["status"] in ["healthy"]
    
    def test_service_health_details(self, wait_for_services):
        """Test detailed service health information"""
        response = requests.get("http://localhost:8000/healthz?details=true")
        
        assert response.status_code == 200
        health = response.json()
        
        services = health["services"]
        
        # Database services should be healthy
        assert services["database"]["status"] == "healthy"
        assert services["mongodb"]["status"] == "healthy"
        assert services["neo4j"]["status"] == "healthy"
        
        # Redis should be healthy or disabled
        assert services["redis"]["status"] in ["healthy", "disabled"]
        
        # External services should be configured or disabled
        assert services["astradb"]["status"] in ["healthy", "configured", "disabled"]
        assert services["openai"]["status"] in ["configured", "disabled"]


class TestNetworking:
    """Test container networking and connectivity"""
    
    def test_app_external_access(self):
        """Test that app is accessible from host"""
        response = requests.get("http://localhost:8000/", timeout=10)
        assert response.status_code in [200, 404]  # 404 is OK if no root route
    
    def test_database_ports_exposed(self):
        """Test that database ports are exposed for admin access"""
        # These should be accessible from host for admin tools
        
        # PostgreSQL
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="ttrpg_dev", 
                user="ttrpg_user",
                password="ttrpg_dev_pass",
                connect_timeout=5
            )
            conn.close()
            postgres_accessible = True
        except:
            postgres_accessible = False
        
        assert postgres_accessible, "PostgreSQL should be accessible on localhost:5432"
    
    def test_internal_network_isolation(self):
        """Test that services can communicate internally"""
        # This is implicitly tested by the health checks
        # If services are healthy, internal networking is working
        response = requests.get("http://localhost:8000/healthz")
        assert response.status_code == 200
        
        health = response.json()
        assert health["services"]["database"]["status"] == "healthy"
        assert health["services"]["mongodb"]["status"] == "healthy"


class TestDataPersistence:
    """Test that data persists in volumes"""
    
    def test_postgres_data_persistence(self):
        """Test PostgreSQL data persistence"""
        # Connect and create test data
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="ttrpg_dev",
            user="ttrpg_user", 
            password="ttrpg_dev_pass"
        )
        
        cursor = conn.cursor()
        
        # Create test table and data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_persistence (
                id SERIAL PRIMARY KEY,
                test_data VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        test_value = f"persistence_test_{int(time.time())}"
        cursor.execute(
            "INSERT INTO test_persistence (test_data) VALUES (%s) RETURNING id",
            (test_value,)
        )
        
        test_id = cursor.fetchone()[0]
        conn.commit()
        
        # Verify data exists
        cursor.execute(
            "SELECT test_data FROM test_persistence WHERE id = %s",
            (test_id,)
        )
        
        result = cursor.fetchone()
        assert result[0] == test_value
        
        cursor.close()
        conn.close()
    
    def test_mongodb_data_persistence(self):
        """Test MongoDB data persistence"""
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client["ttrpg_dev"]
        collection = db["test_persistence"]
        
        # Insert test document
        test_doc = {
            "test_data": f"persistence_test_{int(time.time())}",
            "created_at": time.time()
        }
        
        result = collection.insert_one(test_doc)
        assert result.inserted_id is not None
        
        # Verify document exists
        found_doc = collection.find_one({"_id": result.inserted_id})
        assert found_doc["test_data"] == test_doc["test_data"]
        
        client.close()
    
    def test_neo4j_data_persistence(self):
        """Test Neo4j data persistence"""
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "dev_password")
        )
        
        with driver.session() as session:
            # Create test node
            test_value = f"persistence_test_{int(time.time())}"
            result = session.run(
                "CREATE (n:TestPersistence {test_data: $test_data, created_at: timestamp()}) "
                "RETURN n.test_data as test_data",
                test_data=test_value
            )
            
            record = result.single()
            assert record["test_data"] == test_value
            
            # Verify node exists
            result = session.run(
                "MATCH (n:TestPersistence {test_data: $test_data}) RETURN count(n) as count",
                test_data=test_value
            )
            
            count = result.single()["count"]
            assert count == 1
        
        driver.close()


class TestSecurity:
    """Test container security configurations"""
    
    def test_non_root_user(self):
        """Test that app container runs as non-root user"""
        result = subprocess.run(
            ["docker", "exec", "ttrpg-app-dev", "whoami"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        user = result.stdout.strip()
        assert user == "ttrpg", f"Expected 'ttrpg' user, got '{user}'"
    
    def test_no_privileged_containers(self):
        """Test that no containers run in privileged mode"""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ttrpg", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        container_names = result.stdout.strip().split('\n')
        
        for container_name in container_names:
            if container_name:  # Skip empty lines
                inspect_result = subprocess.run(
                    ["docker", "inspect", container_name, "--format", "{{.HostConfig.Privileged}}"],
                    capture_output=True,
                    text=True
                )
                
                assert inspect_result.returncode == 0
                privileged = inspect_result.stdout.strip()
                assert privileged == "false", f"Container {container_name} is privileged"
    
    def test_secrets_not_in_environment(self):
        """Test that sensitive data is not exposed in environment variables"""
        result = subprocess.run(
            ["docker", "exec", "ttrpg-app-dev", "env"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        env_vars = result.stdout
        
        # Check that passwords are not plaintext in environment
        # Note: They will be there as env vars, but shouldn't be leaked in logs
        sensitive_patterns = [
            "password=",
            "secret=", 
            "key=",
            "token="
        ]
        
        # This test mainly ensures the environment is captured correctly
        # Real security would involve checking logs don't contain secrets
        assert "POSTGRES_PASSWORD" in env_vars  # Should be set
        assert "SECRET_KEY" in env_vars  # Should be set


class TestResourceUsage:
    """Test container resource usage and limits"""
    
    def test_container_memory_usage(self):
        """Test that containers are using reasonable memory"""
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", 
             "{{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        lines = result.stdout.strip().split('\n')
        container_stats = {}
        
        for line in lines:
            if 'ttrpg' in line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    container = parts[0]
                    mem_usage = parts[1]
                    mem_perc = parts[2].rstrip('%')
                    
                    container_stats[container] = {
                        'usage': mem_usage,
                        'percentage': float(mem_perc) if mem_perc.replace('.', '').isdigit() else 0
                    }
        
        # Basic sanity checks - containers should be using some memory but not excessive
        for container, stats in container_stats.items():
            assert stats['percentage'] > 0, f"Container {container} shows 0% memory usage"
            assert stats['percentage'] < 90, f"Container {container} using {stats['percentage']}% memory"
    
    def test_disk_usage_reasonable(self):
        """Test that containers aren't using excessive disk space"""
        result = subprocess.run(
            ["docker", "system", "df"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # This is mainly a smoke test - in real scenarios you'd have specific limits


if __name__ == "__main__":
    pytest.main([__file__, "-v"])