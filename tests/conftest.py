"""Shared fixtures. The app is started once per session because the lifespan
loads the sentence-transformers model and embeds every chunk."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def posts(client):
    return server.app.state.posts


@pytest.fixture(scope="session")
def search_index(client):
    """The built index.

    The index is built on the first search rather than at startup, so this
    performs one real search to trigger it and then hands back the result.
    Tests that inspect the corpus use this instead of reaching into app
    state, which now holds the lazy wrapper rather than the index itself."""
    assert client.post("/api/search", json={"query": "warm up"}).status_code == 200
    holder = server.app.state.search_index
    assert holder.ready
    return holder._index


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Clear the API rate-limit counters before each test.

    The client is session-scoped, so without this the requests made by one
    test would count against the next one's allowance and the suite would
    start returning 429s. The limiter's own tests do their counting inside a
    single test, so they are unaffected."""
    server.api_limiter.reset()
    yield
