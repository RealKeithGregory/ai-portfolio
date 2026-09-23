"""The search index is built on first use, not at startup.

These tests are about the wrapper, not about retrieval: that the model is
built once and only once, that a failure to build it degrades search alone
and leaves the site standing, and that serving pages never touches it.
"""

import asyncio
import threading

import pytest

import server


def make_index(build):
    return server.LazySearchIndex(build)


class FakeIndex:
    def __init__(self, tag="ok"):
        self.chunks = [{"section": tag, "text": tag, "url": "/"}]


# ─── BUILT ONCE ───────────────────────────────────────────────────────────────
def test_index_is_not_built_until_something_asks():
    calls = []
    holder = make_index(lambda: calls.append(1) or FakeIndex())
    assert holder.ready is False
    assert calls == []


def test_first_get_builds_and_later_gets_reuse():
    calls = []

    def build():
        calls.append(1)
        return FakeIndex()

    holder = make_index(build)
    first = asyncio.run(holder.get())

    async def again():
        return await holder.get(), await holder.get()

    second, third = asyncio.run(again())
    assert first is second is third
    assert calls == [1], "the model must be loaded once per process"
    assert holder.ready is True


def test_simultaneous_first_requests_build_only_once():
    """Two searches arriving together on a cold instance must not each load
    their own copy of the model -- that is 450 MB twice."""
    started = threading.Event()
    calls = []

    def slow_build():
        calls.append(1)
        started.set()
        # Long enough that every waiter is definitely queued behind the lock.
        threading.Event().wait(0.3)
        return FakeIndex()

    holder = make_index(slow_build)

    async def race():
        return await asyncio.gather(*(holder.get() for _ in range(8)))

    results = asyncio.run(race())
    assert calls == [1], f"built {len(calls)} times under concurrent first use"
    assert len({id(r) for r in results}) == 1, "callers got different indexes"


# ─── FAILURE IS CONTAINED ─────────────────────────────────────────────────────
def test_failure_propagates_and_leaves_the_holder_unbuilt():
    holder = make_index(lambda: (_ for _ in ()).throw(RuntimeError("no model")))
    with pytest.raises(RuntimeError):
        asyncio.run(holder.get())
    assert holder.ready is False


def test_a_later_request_can_retry_after_a_failure():
    """A transient failure must not disable search until the instance dies."""
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return FakeIndex("recovered")

    holder = make_index(flaky)
    with pytest.raises(RuntimeError):
        asyncio.run(holder.get())
    recovered = asyncio.run(holder.get())
    assert recovered.chunks[0]["section"] == "recovered"
    assert len(attempts) == 2


def test_search_returns_503_when_the_index_cannot_be_built(client, monkeypatch):
    """Search degrades; it does not lie by returning an empty result list."""
    broken = make_index(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(server.app.state, "search_index", broken)

    response = client.post("/api/search", json={"query": "evaluation"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
    # The traceback must not reach the visitor.
    assert "RuntimeError" not in response.text and "Traceback" not in response.text


def test_the_rest_of_the_site_survives_a_broken_index(client, monkeypatch):
    broken = make_index(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(server.app.state, "search_index", broken)

    for path in ["/", "/blog"]:
        assert client.get(path).status_code == 200, path
    # The Portfolio Guide is keyword matching and needs no model at all.
    assert client.post("/api/chat", json={"message": "projects"}).status_code == 200


# ─── PAGES DO NOT PAY FOR THE MODEL ───────────────────────────────────────────
def test_serving_pages_never_builds_the_index(client, monkeypatch):
    """The point of the whole change: a visitor reading the site must not
    cause the embedding model to load."""
    built = []
    holder = make_index(lambda: built.append(1) or FakeIndex())
    monkeypatch.setattr(server.app.state, "search_index", holder)

    for path in ["/", "/blog", "/definitely-not-a-page", "/static/css/styles.css"]:
        client.get(path)
    client.post("/api/chat", json={"message": "what projects have you built?"})

    assert built == [], "serving pages triggered a model load"
    assert holder.ready is False


def test_search_py_does_not_import_torch_at_module_level():
    """Importing the module must stay cheap; PyTorch arrives only with the
    model. This is what keeps a page-only cold start off the AI stack."""
    import ast
    import pathlib

    source = pathlib.Path(server.BASE_DIR / "search.py").read_text()
    tree = ast.parse(source)
    top_level_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module.split(".")[0])

    assert "sentence_transformers" not in top_level_imports
    assert "torch" not in top_level_imports
