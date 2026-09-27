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
    """Anything in content.py is rendered publicly, so the public shape is
    pinned to an exact set of fields."""
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
    # Every project belongs to exactly one declared group, and no declared
    # group is empty -- an empty one would render a heading with nothing under it.
    grouped = [content.projects_in_category(key) for key in keys]
    assert all(grouped), "a project category has no projects"
    assert sum(len(group) for group in grouped) == len(content.PROJECTS)


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
