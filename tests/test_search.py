"""Semantic search endpoint: schema, ranking, retrieval quality, and the
integrity of the index source.

Index-source tests are allowlists. Every chunk must come from a declared
content category and point at a declared public URL, so anything that is not
part of the published site cannot reach the index unnoticed."""

import re

import pytest

import content
import search

# Public pages carry no dated history ranges (YYYY-YYYY or YYYY-Present).
DATE_RANGE = re.compile(r"\b(19|20)\d{2}\s*[–—-]\s*((19|20)\d{2}|Present)\b", re.I)

RESULT_KEYS = {"section", "text", "snippet", "url", "score"}

# The content categories the index is built from.
APPROVED_SECTIONS = {"About", "Contact", "Projects overview"}
APPROVED_SECTION_PREFIXES = ("Project: ", "Skills: ", "Blog: ")


def approved_urls(posts):
    """Every URL the index is allowed to point at, derived from the canonical
    content rather than hard-coded."""
    urls = {"/#about", "/#projects", "/#skills", "/#contact"}
    urls |= {f"/#project-{p['slug']}" for p in content.PROJECTS}
    urls |= {p.url for p in posts}
    return urls


def test_search_returns_expected_schema(client):
    r = client.post("/api/search", json={"query": "test automation"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "test automation"
    assert isinstance(body["results"], list) and body["results"]
    for result in body["results"]:
        assert set(result) == RESULT_KEYS
        assert isinstance(result["score"], float)
        assert -1.0 <= result["score"] <= 1.0
        assert result["url"].startswith("/")
        assert len(result["snippet"]) <= search.SNIPPET_CHARS + 1


def test_results_are_ranked_and_deduplicated_by_page(client):
    results = client.post("/api/search", json={"query": "finance"}).json()["results"]
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    urls = [r["url"] for r in results]
    assert len(urls) == len(set(urls))
    assert len(results) <= search.DEFAULT_TOP_K


def test_blog_content_is_searchable(client, posts):
    post = posts[0]
    r = client.post("/api/search", json={"query": post.title})
    urls = [res["url"] for res in r.json()["results"][:2]]
    assert post.url in urls


def test_project_content_is_searchable(client):
    r = client.post("/api/search", json={"query": "multi-agent planner research executor"})
    assert r.json()["results"][0]["url"] == "/#project-multi-agent-research-automation"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": 123},
        {"query": "x" * 501},
        {"q": "wrong field"},
    ],
)
def test_malformed_search_requests_fail_safely(client, payload):
    r = client.post("/api/search", json=payload)
    assert r.status_code == 422
    assert "detail" in r.json()


def test_invalid_json_body_is_rejected(client):
    r = client.post("/api/search", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_search_requires_post(client):
    assert client.get("/api/search").status_code == 405


def test_index_covers_content_and_blog(search_index, posts):
    chunks = search_index.chunks
    sections = {c["section"] for c in chunks}
    assert "About" in sections and "Contact" in sections
    assert "Projects overview" in sections
    assert any(s.startswith("Project: ") for s in sections)
    assert any(s.startswith("Skills: ") for s in sections)
    for post in posts:
        assert f"Blog: {post.title}" in sections
    # Every core and supporting project is retrievable.
    for project in content.PROJECTS:
        assert f"Project: {project['name']}" in sections


def test_index_is_built_only_from_approved_content(search_index, posts):
    """Index source integrity: every chunk belongs to a declared category and
    points at a declared public URL. Anything else fails, whatever it is."""
    chunks = search_index.chunks
    allowed = approved_urls(posts)
    for chunk in chunks:
        section = chunk["section"]
        assert (
            section in APPROVED_SECTIONS
            or section.startswith(APPROVED_SECTION_PREFIXES)
        ), f"unapproved index section: {section}"
        assert chunk["url"] in allowed, f"unapproved index url: {chunk['url']}"


def test_indexed_text_carries_no_dated_history(search_index):
    """The published site presents no dated history, so none can be indexed."""
    for chunk in search_index.chunks:
        assert DATE_RANGE.search(chunk["text"]) is None, chunk["section"]


def test_focus_areas_remain_searchable(search_index):
    """They moved into the About chunk; they must still be findable."""
    about = next(c for c in search_index.chunks if c["section"] == "About")
    for area in content.PROFILE["ai_focus"]:
        assert area in about["text"], area


@pytest.mark.parametrize(
    "query",
    [
        "personal details",
        "background and history",
        "tell me everything about this person",
        "documents and files",
    ],
)
def test_off_topic_queries_stay_inside_approved_content(client, posts, query):
    """Whatever is asked, results can only come from the approved corpus."""
    results = client.post("/api/search", json={"query": query}).json()["results"]
    assert results, "search should still answer from the portfolio"
    allowed = approved_urls(posts)
    for result in results:
        assert result["url"] in allowed, f"unapproved result url: {result['url']}"
        assert DATE_RANGE.search(result["text"]) is None


@pytest.mark.parametrize(
    "query, expected_url",
    [
        ("What has Keith built with agents and tool calling?", "/#project-smart-personal-ai-agent"),
        ("planner research executor multi-agent coordination", "/#project-multi-agent-research-automation"),
        ("grounded answers from documents with citations", "/#project-agentic-knowledge-base-assistant"),
        ("guardrails and observability for financial data", "/#project-finance-ai-capstone"),
        ("how are embeddings and cosine similarity used here", "/#project-semantic-portfolio-search"),
    ],
)
def test_project_evidence_is_retrievable(client, query, expected_url):
    """Retrieval evaluation: each project must be the top hit for the question
    it is the answer to."""
    results = client.post("/api/search", json={"query": query}).json()["results"]
    assert results[0]["url"] == expected_url, f"{query!r} -> {results[0]['section']}"


def test_snippet_cuts_on_word_boundary():
    text = "alpha " * 100
    cut = search.snippet(text.strip(), limit=20)
    assert cut.endswith("…") and " alph…" not in cut
    assert search.snippet("short") == "short"


@pytest.mark.parametrize(
    "query",
    [
        "What has Keith built with agents?",
        "How does Keith evaluate retrieval?",
        "What AI projects is Keith working on?",
    ],
)
def test_visitor_questions_return_project_or_blog_evidence(client, query):
    """The questions this portfolio exists to answer must land on technical
    evidence -- a project or an article -- not on the bio or the contact card."""
    top = client.post("/api/search", json={"query": query}).json()["results"][0]
    assert top["url"].startswith("/#project") or top["url"].startswith("/blog"), (
        f"{query!r} -> {top['section']}"
    )
