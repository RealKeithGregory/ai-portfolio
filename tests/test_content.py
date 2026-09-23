"""Content integrity: the canonical content module and the pages it renders.

Boundary tests here are allowlists. The profile exposes an exact set of
fields and the site presents an exact positioning, so anything added outside
that shape is caught without this file describing what it must not be."""

import re

import pytest

import content

# Placeholder and template leftovers that must never reach a rendered page.
# Each one was a real problem in an earlier version of the site.
PLACEHOLDER_MARKERS = [
    "yourusername",
    "your-trivia-game",
    "Trivia",  # no implementation exists in this repository
    "Project Three",
    "trained on",
    "contrib-cell",
    "% match",
    "TODO",
]

# The exact set of fields the public profile exposes. A new field cannot be
# added without this test being updated, which is the point.
APPROVED_PROFILE_FIELDS = {
    "name",
    "headline",
    "specialization",
    "tagline",
    "summary",
    "about",
    "workflow",
    "ai_focus",
    "links",
}

APPROVED_LINK_FIELDS = {"github", "linkedin", "email"}

# Public pages carry no dated history ranges (YYYY-YYYY or YYYY-Present).
DATE_RANGE = re.compile(r"\b(19|20)\d{2}\s*[–—-]\s*((19|20)\d{2}|Present)\b", re.I)

ALLOWED_URL = re.compile(r"^(https?://|/|#)")


@pytest.fixture(scope="module")
def pages(client, posts):
    return {path: client.get(path).text for path in ["/", "/blog", posts[0].url]}


@pytest.mark.parametrize("needle", PLACEHOLDER_MARKERS)
def test_rendered_pages_contain_no_placeholders(pages, needle):
    for path, html in pages.items():
        assert needle.lower() not in html.lower(), f"{needle!r} found on {path}"


def test_public_pages_present_no_dated_history(pages):
    """The portfolio pages present no date ranges. The published article is
    exempt: it tells its own story in its own words."""
    for path in ["/", "/blog"]:
        assert DATE_RANGE.search(pages[path]) is None, f"date range on {path}"


def test_content_module_exposes_only_approved_fields():
    """Anything in content.py is rendered publicly and embedded into the search
    index, so the public shape is pinned to an exact set of fields."""
    assert set(content.PROFILE) == APPROVED_PROFILE_FIELDS
    assert set(content.PROFILE["links"]) == APPROVED_LINK_FIELDS
    # No separate history structure alongside the approved ones.
    public_names = {n for n in vars(content) if n.isupper()}
    assert public_names == {
        "PROFILE",
        "SKILL_GROUPS",
        "PROJECT_CATEGORIES",
        "PROJECTS",
        "CASE_STUDY_SECTIONS",
        "STATUS_LABELS",
    }
    values = repr(
        [content.PROFILE, content.SKILL_GROUPS, content.PROJECTS, content.PROJECT_CATEGORIES]
    )
    assert DATE_RANGE.search(values) is None


def test_profile_positions_the_site_around_ai_engineering():
    assert content.PROFILE["headline"] == "Building Reliable AI Systems"
    focus = " ".join(content.PROFILE["ai_focus"]).lower()
    for area in ["evaluation", "rag", "agents", "guardrails", "multi-agent", "financial"]:
        assert area in focus, f"{area} missing from the public focus areas"


def test_homepage_leads_with_the_canonical_positioning(pages):
    """The rendered hero presents the canonical headline, so the site's public
    identity always matches the content module."""
    import html as html_module

    home = html_module.unescape(pages["/"])  # the tagline contains "&"
    assert content.PROFILE["headline"] in home
    assert content.PROFILE["tagline"] in home


def test_projects_are_grouped_with_the_core_ai_systems_first():
    keys = [key for key, _, _ in content.PROJECT_CATEGORIES]
    assert keys[0] == "core"
    core = [p["name"] for p in content.projects_in_category("core")]
    assert "Agentic Knowledge Base Assistant" in core
    assert "Finance AI Capstone" in core
    supporting = [p["name"] for p in content.projects_in_category("supporting")]
    assert "Semantic Portfolio Search" in supporting
    # Every project belongs to exactly one declared group.
    assert len(core) + len(supporting) == len(content.PROJECTS)


def test_project_definitions_are_complete_and_consistent():
    slugs = [p["slug"] for p in content.PROJECTS]
    assert len(slugs) == len(set(slugs))
    section_keys = {key for key, _ in content.CASE_STUDY_SECTIONS}
    for project in content.PROJECTS:
        assert project["status"] in content.STATUS_LABELS
        assert project["name"] and project["summary"] and project["tags"]
        assert set(project["sections"]) <= section_keys
        for url in project["evidence"].values():
            assert ALLOWED_URL.match(url), f"bad evidence url {url!r} in {project['slug']}"
        if project["status"] == "planned":
            assert "results" not in project["sections"], "planned projects cannot have results"
            assert project.get("questions"), "planned projects list their evaluation questions"


def test_skills_have_no_ratings():
    for group in content.SKILL_GROUPS:
        for skill in group["skills"]:
            assert "%" not in skill and not re.search(r"\d/\d", skill)


def test_portfolio_guide_is_labelled_honestly(pages):
    home = pages["/"]
    assert "Portfolio Guide" in home
    assert "not an LLM" in home
    assert "AI Assistant" not in home


def test_guide_replies_come_from_canonical_content(client, posts):
    reply = client.post("/api/chat", json={"message": "What projects have you built?"}).json()["reply"]
    for project in content.PROJECTS:
        assert project["name"] in reply
    reply = client.post("/api/chat", json={"message": "What is on the blog?"}).json()["reply"]
    assert posts[0].title in reply
    fallback = client.post("/api/chat", json={"message": "zzzz qqqq"}).json()["reply"]
    assert "semantic search" in fallback


# Generic inputs that reach the guide's background reply.
BACKGROUND_INPUTS = ["background", "history", "work", "role", "experience"]


@pytest.mark.parametrize("message", BACKGROUND_INPUTS)
def test_guide_background_reply_stays_at_a_high_level(client, message):
    """The background reply summarises and points at the public evidence. It
    carries no dates and links only to approved destinations."""
    reply = client.post("/api/chat", json={"message": message}).json()["reply"]
    assert DATE_RANGE.search(reply) is None
    assert not re.search(r"\b(19|20)\d{2}\b", reply), "no dates in this reply"
    assert "more than a decade" in reply.lower()
    assert "/blog" in reply or "Projects" in reply
    for path in re.findall(r"(?<![\w:/])/[a-z0-9][\w/-]*", reply):
        assert path == "/blog", f"unapproved path in reply: {path}"


def test_guide_still_answers_availability_questions(client):
    """The availability reply is matched before the background reply, which
    also matches the word "work"."""
    reply = client.post(
        "/api/chat", json={"message": "Are you available for work?"}
    ).json()["reply"]
    assert "open to conversations" in reply


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": 123},
        {"message": "x" * 501},
        {"msg": "wrong field"},
    ],
)
def test_malformed_guide_requests_fail_safely(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


def test_invalid_guide_json_body_is_rejected(client):
    r = client.post(
        "/api/chat", content="not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422


def test_templates_render_positioning_from_the_content_module():
    """Positioning integrity: the templates read the headline from content.py
    rather than hard-coding an identity of their own."""
    import pathlib

    base = pathlib.Path("templates/base.html").read_text(encoding="utf-8")
    index = pathlib.Path("templates/index.html").read_text(encoding="utf-8")
    assert "profile.headline" in base
    assert "profile.headline" in index
    assert "profile.tagline" in index
    # The literal headline is never pasted into a template.
    assert content.PROFILE["headline"] not in base
    assert content.PROFILE["headline"] not in index
