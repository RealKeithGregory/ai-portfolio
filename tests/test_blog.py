"""Markdown loading and front-matter validation."""

from datetime import date

import pytest

import blog
import content

GOOD = """---
title: "A Post"
slug: "a-post"
date: "2026-01-02"
description: "Short description."
tags:
  - Testing
related_project: semantic-portfolio-search
github_url: https://github.com/RealKeithGregory
---

# Heading

Body paragraph with **bold** text and `code`.

```python
print("hi")
```
"""


def write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_real_posts_load_and_are_valid(posts):
    assert posts, "expected at least one published post"
    for post in posts:
        assert post.url == f"/blog/{post.slug}"
        assert post.title and post.description and post.tags
        assert isinstance(post.date, date)
        assert post.reading_minutes >= 1
        assert "<p>" in post.body_html


def test_posts_are_sorted_newest_first(posts):
    dates = [p.date for p in posts]
    assert dates == sorted(dates, reverse=True)


def test_parse_post_reads_metadata_and_renders_markdown():
    post = blog.parse_post(GOOD)
    assert post.title == "A Post"
    assert post.slug == "a-post"
    assert post.date == date(2026, 1, 2)
    assert post.tags == ["Testing"]
    assert post.related_project["slug"] == "semantic-portfolio-search"
    assert post.github_url == "https://github.com/RealKeithGregory"
    assert "<h1>Heading</h1>" in post.body_html
    assert "<strong>bold</strong>" in post.body_html
    assert '<pre><code class="language-python">' in post.body_html
    # Fenced code is dropped from the search text; prose and headings stay.
    assert "print" not in post.plain_text and "```" not in post.plain_text
    assert "Heading" in post.plain_text and "bold text" in post.plain_text


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda t: t.replace('title: "A Post"\n', ""), "missing required"),
        (lambda t: t.replace('description: "Short description."\n', ""), "missing required"),
        (lambda t: t.replace('slug: "a-post"', 'slug: "A Post!"'), "slug"),
        (lambda t: t.replace('date: "2026-01-02"', 'date: "Jan 2 2026"'), "date"),
        (lambda t: t.replace("related_project: semantic-portfolio-search", "related_project: nope"), "related_project"),
        (lambda t: t.split("---\n\n")[0] + "---\n\n   \n", "empty"),
        (lambda t: t.replace("---\n", "", 1), "front matter"),
    ],
)
def test_invalid_front_matter_is_rejected(mutation, message):
    with pytest.raises(blog.BlogError, match=message):
        blog.parse_post(mutation(GOOD))


def test_optional_fields_may_be_blank():
    text = GOOD.replace("related_project: semantic-portfolio-search", "related_project:")
    text = text.replace("github_url: https://github.com/RealKeithGregory", "github_url:")
    post = blog.parse_post(text)
    assert post.related_project is None and post.github_url is None


def test_duplicate_slugs_are_detected(tmp_path):
    write(tmp_path, "one.md", GOOD)
    write(tmp_path, "two.md", GOOD.replace('title: "A Post"', 'title: "Another"'))
    with pytest.raises(blog.BlogError, match="duplicate slug"):
        blog.load_posts(tmp_path)


def test_load_posts_orders_by_date_and_reports_file(tmp_path):
    write(tmp_path, "old.md", GOOD.replace("a-post", "old").replace("2026-01-02", "2025-05-01"))
    write(tmp_path, "new.md", GOOD.replace("a-post", "new"))
    loaded = blog.load_posts(tmp_path)
    assert [p.slug for p in loaded] == ["new", "old"]
    assert loaded[0].source_path.name == "new.md"


def test_reading_time_rounds_up():
    assert blog.reading_minutes("word " * 10) == 1
    assert blog.reading_minutes("word " * 201) == 2


def test_related_project_slugs_exist_for_all_real_posts(posts):
    for post in posts:
        if post.related_project:
            assert content.get_project(post.related_project["slug"]) is not None


def test_first_article_keeps_its_own_career_context(posts):
    """The portfolio brands AI-first, but the article is allowed to explain the
    QA background that led there. This guards against a future content pass
    scrubbing the article to match the site's branding."""
    article = blog.get_post(posts, "why-im-learning-ai-engineering")
    assert article is not None, "the first article must stay published"
    assert "Career" in article.tags
    body = article.body_markdown.lower()
    assert "job security" in body
    assert "qa" in body
    assert "more than a decade" in body
