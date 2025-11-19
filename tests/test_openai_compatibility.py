"""Test OpenAI library compatibility with httpx 0.28+.

NOTE: Requires OpenAI library to be installed.
Run: pip install openai>=1.50.0 httpx>=0.28.0
"""
import pytest

def test_openai_version():
    """Verify OpenAI version is 1.50+."""
    try:
        import openai
        version = openai.__version__
        major, minor = map(int, version.split('.')[:2])
        assert major >= 1 and minor >= 50, f"OpenAI version {version} too old"
        print(f"✅ OpenAI version {version} is compatible")
    except ImportError:
        pytest.skip("OpenAI library not installed")

def test_httpx_version():
    """Verify httpx version is 0.28+."""
    try:
        import httpx
        version = httpx.__version__
        major, minor = map(int, version.split('.')[:2])
        assert (major == 0 and minor >= 28) or major >= 1, f"httpx version {version} incompatible"
        print(f"✅ httpx version {version} is compatible")
    except ImportError:
        pytest.skip("httpx library not installed")

def test_client_initialization():
    """Test OpenAI client initializes without proxies error."""
    try:
        from openai import OpenAI
        import os

        api_key = os.getenv("OPENAI_API_KEY", "test-key")

        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        assert client is not None
        print("✅ OpenAI client initialized successfully")
    except TypeError as e:
        if "proxies" in str(e):
            pytest.fail(f"OpenAI/httpx incompatibility still present: {e}")
        raise
    except ImportError:
        pytest.skip("OpenAI library not installed")

def test_embedding_api_structure():
    """Verify embedding API uses modern structure."""
    try:
        from openai import OpenAI
        import os

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        client = OpenAI(api_key=api_key)

        # Verify client has embeddings attribute
        assert hasattr(client, 'embeddings'), "Client missing embeddings API"
        assert hasattr(client.embeddings, 'create'), "Embeddings missing create method"

        print("✅ Modern OpenAI API structure verified")
    except ImportError:
        pytest.skip("OpenAI library not installed")

if __name__ == "__main__":
    print("Run tests with: python -m pytest tests/test_openai_compatibility.py -v")
    print("Or run directly: python tests/test_openai_compatibility.py")

    # Run basic checks
    test_openai_version()
    test_httpx_version()
    test_client_initialization()
    print("\n✅ All compatibility checks passed!")
