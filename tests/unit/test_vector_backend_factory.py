import pytest

from src_common.vector_store import factory
from src_common.vector_store.memory import MemoryVectorStore


@pytest.fixture(autouse=True)
def clear_factory_cache():
    factory._CACHE.clear()
    factory._BACKEND_CACHE.clear()
    yield
    factory._CACHE.clear()
    factory._BACKEND_CACHE.clear()


def test_default_backend_is_memory_in_tests(monkeypatch):
    monkeypatch.delenv("VECTOR_STORE_BACKEND", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "vector-backend")

    store = factory.make_vector_store("dev", fresh=True)
    assert isinstance(store, MemoryVectorStore)
    assert store.backend_name == "memory"


def test_cassandra_backend_requires_env_and_raises_clear_error(monkeypatch):
    from src_common.vector_store import cassandra as cassandra_module

    monkeypatch.setenv("VECTOR_STORE_BACKEND", "cassandra")
    monkeypatch.setattr(cassandra_module, "_CASSANDRA_IMPORT_ERROR", RuntimeError("native libs missing"), raising=False)
    monkeypatch.setattr(cassandra_module, "Cluster", None, raising=False)
    monkeypatch.setattr(cassandra_module, "AsyncioConnection", None, raising=False)
    monkeypatch.setattr(cassandra_module, "SimpleStatement", None, raising=False)

    with pytest.raises(RuntimeError, match="Cassandra backend unavailable"):
        factory.make_vector_store("dev", fresh=True)
