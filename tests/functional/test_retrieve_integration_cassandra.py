import os

import pytest

pytestmark = pytest.mark.cassandra


@pytest.mark.integration
def test_cassandra_backend_skip_by_default():
    if not os.getenv("RUN_CASSANDRA_TESTS"):
        pytest.skip("RUN_CASSANDRA_TESTS not set")
    pytest.fail("Cassandra integration requires live cluster")
