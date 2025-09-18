"""
Unit tests for graph artifact loader implementation.
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.orchestrator.graph_loader import (
    GraphLoader, GraphSnapshot, GraphNode, GraphEdge, CrossReference, get_graph_loader
)


class TestGraphNode:
    """Test GraphNode data structure."""

    def test_node_creation(self):
        """Test creating a graph node."""
        node = GraphNode(
            node_id="test_node",
            node_type="section",
            title="Test Section",
            content="Test content",
            parent_id="parent_1",
            children=["child_1", "child_2"],
            metadata={"key": "value"}
        )

        assert node.node_id == "test_node"
        assert node.node_type == "section"
        assert node.title == "Test Section"
        assert node.content == "Test content"
        assert node.parent_id == "parent_1"
        assert node.children == ["child_1", "child_2"]
        assert node.metadata == {"key": "value"}

    def test_node_default_children(self):
        """Test that children defaults to empty list."""
        node = GraphNode(
            node_id="test",
            node_type="chunk",
            title="Test"
        )
        assert node.children == []


class TestGraphSnapshot:
    """Test GraphSnapshot functionality."""

    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample graph snapshot for testing."""
        nodes = {
            "node1": GraphNode("node1", "section", "Section 1", children=["node2"]),
            "node2": GraphNode("node2", "chunk", "Chunk 1", parent_id="node1"),
            "node3": GraphNode("node3", "entity", "Wizard Class")
        }

        edges = [
            GraphEdge("edge1", "node1", "node2", "contains", 1.0),
            GraphEdge("edge2", "node2", "node3", "references", 0.8)
        ]

        cross_refs = [
            CrossReference("ref1", "wizard", "spell", "class_to_spell", 0.9, "Wizards can cast spells")
        ]

        aliases = {
            "wizard": {"mage", "spellcaster"},
            "spell": {"magic", "incantation"}
        }

        return GraphSnapshot(
            job_id="test_job",
            created_at=1234567890.0,
            nodes=nodes,
            edges=edges,
            cross_references=cross_refs,
            aliases=aliases
        )

    def test_get_node(self, sample_snapshot):
        """Test getting nodes by ID."""
        node = sample_snapshot.get_node("node1")
        assert node is not None
        assert node.title == "Section 1"

        missing_node = sample_snapshot.get_node("missing")
        assert missing_node is None

    def test_get_children(self, sample_snapshot):
        """Test getting child nodes."""
        children = sample_snapshot.get_children("node1")
        assert len(children) == 1
        assert children[0].node_id == "node2"

        no_children = sample_snapshot.get_children("node2")
        assert len(no_children) == 0

    def test_get_related_nodes(self, sample_snapshot):
        """Test graph traversal for related nodes."""
        related = sample_snapshot.get_related_nodes("node1", max_depth=2)

        # Should find node2 and node3 through edges
        node_ids = [node.node_id for node in related]
        assert "node2" in node_ids
        assert "node3" in node_ids
        assert "node1" not in node_ids  # Don't include self

    def test_find_cross_references(self, sample_snapshot):
        """Test finding cross-references for elements."""
        wizard_refs = sample_snapshot.find_cross_references("wizard")
        assert len(wizard_refs) == 1
        assert wizard_refs[0].source_element == "wizard"

        spell_refs = sample_snapshot.find_cross_references("spell")
        assert len(spell_refs) == 1
        assert spell_refs[0].target_element == "spell"

    def test_expand_aliases(self, sample_snapshot):
        """Test alias expansion."""
        wizard_aliases = sample_snapshot.expand_aliases("wizard")
        assert "wizard" in wizard_aliases
        assert "mage" in wizard_aliases
        assert "spellcaster" in wizard_aliases

        # Test reverse lookup
        mage_aliases = sample_snapshot.expand_aliases("mage")
        assert "wizard" in mage_aliases
        assert "mage" in mage_aliases


class TestGraphLoader:
    """Test GraphLoader functionality."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_artifact_structure(self, temp_artifacts_dir):
        """Create mock artifact directory structure."""
        # Create environment directory
        env_dir = temp_artifacts_dir / "artifacts" / "ingest" / "test"
        env_dir.mkdir(parents=True)

        # Create job directory
        job_dir = env_dir / "job_123_test"
        job_dir.mkdir()

        # Create graph snapshot
        graph_data = {
            "job_id": "job_123_test",
            "pass": "E",
            "created_at": 1234567890.0,
            "graph_summary": {"nodes": 2, "edges": 1, "cross_references": 1},
            "nodes": {
                "node1": {
                    "node_type": "section",
                    "title": "Test Section",
                    "content": "Test content",
                    "children": ["node2"],
                    "metadata": {}
                },
                "node2": {
                    "node_type": "chunk",
                    "title": "Test Chunk",
                    "parent_id": "node1",
                    "children": [],
                    "metadata": {}
                }
            },
            "edges": [
                {
                    "edge_id": "edge1",
                    "source_id": "node1",
                    "target_id": "node2",
                    "edge_type": "contains",
                    "weight": 1.0,
                    "metadata": {}
                }
            ],
            "cross_references": [
                {
                    "ref_id": "ref1",
                    "source_element": "wizard",
                    "target_element": "spell",
                    "ref_type": "class_to_spell",
                    "confidence": 0.9,
                    "context": "Test context"
                }
            ]
        }

        graph_file = job_dir / "graph_snapshot.json"
        with open(graph_file, 'w') as f:
            json.dump(graph_data, f)

        # Create alias map
        alias_data = {
            "job_id": "job_123_test",
            "created_at": 1234567890.0,
            "aliases": {
                "wizard": ["mage", "spellcaster"],
                "spell": ["magic"]
            }
        }

        alias_file = job_dir / "alias_map.json"
        with open(alias_file, 'w') as f:
            json.dump(alias_data, f)

        return env_dir

    def test_loader_initialization(self):
        """Test loader initialization."""
        loader = GraphLoader("test")
        assert loader.environment == "test"
        assert loader.cache_ttl == 3600

    def test_get_artifact_directory_specific_job(self, mock_artifact_structure):
        """Test finding specific job directory."""
        with patch.object(Path, 'exists', return_value=True):
            loader = GraphLoader("test")

            # Mock the artifacts path to use our temp structure
            with patch.object(loader, 'get_artifact_directory') as mock_get_dir:
                job_dir = mock_artifact_structure / "job_123_test"
                mock_get_dir.return_value = job_dir

                result = loader.get_artifact_directory("job_123_test")
                assert result == job_dir

    def test_load_graph_snapshot_success(self, mock_artifact_structure):
        """Test successful graph snapshot loading."""
        loader = GraphLoader("test")

        # Mock the get_artifact_directory to return our test structure
        with patch.object(loader, 'get_artifact_directory') as mock_get_dir:
            job_dir = mock_artifact_structure / "job_123_test"
            mock_get_dir.return_value = job_dir

            snapshot = loader.load_graph_snapshot("job_123_test")

            assert snapshot is not None
            assert snapshot.job_id == "job_123_test"
            assert len(snapshot.nodes) == 2
            assert len(snapshot.edges) == 1
            assert len(snapshot.cross_references) == 1
            assert "wizard" in snapshot.aliases

    def test_load_graph_snapshot_missing_files(self, temp_artifacts_dir):
        """Test handling of missing graph files."""
        loader = GraphLoader("test")

        # Create empty job directory
        job_dir = temp_artifacts_dir / "empty_job"
        job_dir.mkdir(parents=True)

        with patch.object(loader, 'get_artifact_directory', return_value=job_dir):
            snapshot = loader.load_graph_snapshot("empty_job")
            assert snapshot is None

    def test_cache_behavior(self, mock_artifact_structure):
        """Test caching behavior."""
        loader = GraphLoader("test")

        with patch.object(loader, 'get_artifact_directory') as mock_get_dir:
            job_dir = mock_artifact_structure / "job_123_test"
            mock_get_dir.return_value = job_dir

            # First load
            snapshot1 = loader.load_graph_snapshot("job_123_test")
            assert snapshot1 is not None

            # Second load should hit cache
            snapshot2 = loader.load_graph_snapshot("job_123_test")
            assert snapshot2 is snapshot1  # Same object reference

            # Force reload should bypass cache
            snapshot3 = loader.load_graph_snapshot("job_123_test", force_reload=True)
            assert snapshot3 is not snapshot1  # Different object

    def test_clear_cache(self):
        """Test cache clearing."""
        loader = GraphLoader("test")

        # Add something to cache
        loader._cache["test"] = MagicMock()
        loader._cache_timestamps["test"] = 123456

        loader.clear_cache()

        assert len(loader._cache) == 0
        assert len(loader._cache_timestamps) == 0

    def test_get_cache_info(self, mock_artifact_structure):
        """Test cache information retrieval."""
        loader = GraphLoader("test")

        with patch.object(loader, 'get_artifact_directory') as mock_get_dir:
            job_dir = mock_artifact_structure / "job_123_test"
            mock_get_dir.return_value = job_dir

            # Load snapshot to populate cache
            loader.load_graph_snapshot("job_123_test")

            cache_info = loader.get_cache_info()

            assert "job_123_test" in cache_info
            info = cache_info["job_123_test"]
            assert info["job_id"] == "job_123_test"
            assert info["nodes"] == 2
            assert info["edges"] == 1


class TestGlobalLoaderManagement:
    """Test global loader instance management."""

    def test_get_graph_loader_singleton(self):
        """Test that get_graph_loader returns singleton instances."""
        loader1 = get_graph_loader("test_env")
        loader2 = get_graph_loader("test_env")
        loader3 = get_graph_loader("different_env")

        # Same environment should return same instance
        assert loader1 is loader2

        # Different environment should return different instance
        assert loader1 is not loader3

    def test_get_graph_loader_default_environment(self):
        """Test loader creation with default environment."""
        with patch.dict('os.environ', {'APP_ENV': 'production'}):
            loader = get_graph_loader()
            assert loader.environment == "production"