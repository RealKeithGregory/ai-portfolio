"""Shared fixtures. The app is started once per session, and its lifespan
loads the blog posts every test reads."""

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
