"""Markdown blog loader.

Articles live in content/blog/*.md with a YAML front matter block:

    ---
    title: "Why I'm Learning AI Engineering"
    slug: "why-im-learning-ai-engineering"
    date: "2026-09-21"
    description: "One or two sentences shown in listings."
    tags: [AI Engineering, Career]
    related_project: agentic-knowledge-base-assistant   # optional, a slug from content.PROJECTS
    github_url: https://github.com/...                   # optional
    ---

Adding a post is adding a file; no Python changes are needed. Run
`python -m blog` to validate every post from the command line.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import markdown
import yaml

import content

BLOG_DIR = Path(__file__).parent / "content" / "blog"
REQUIRED_FIELDS = ("title", "slug", "date", "description", "tags")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORDS_PER_MINUTE = 200

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


class BlogError(ValueError):
    """Raised when a post is missing metadata or conflicts with another post."""


@dataclass
class Post:
    title: str
    slug: str
    date: date
    description: str
    tags: list
    body_markdown: str
    body_html: str
    reading_minutes: int
    related_project: dict | None = None
    github_url: str | None = None
    source_path: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def url(self):
        return f"/blog/{self.slug}"

    @property
    def date_display(self):
        return self.date.strftime("%B %-d, %Y")

    @property
    def plain_text(self):
        """Markdown body with the most common markup stripped, for search indexing."""
        text = re.sub(r"```.*?```", " ", self.body_markdown, flags=re.DOTALL)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"[*_`>]+", "", text)
        return text


def split_front_matter(raw):
    match = FRONT_MATTER.match(raw)
    if not match:
        raise BlogError("missing front matter block (--- ... ---)")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise BlogError("front matter must be a mapping")
    return meta, match.group(2)


def reading_minutes(text):
    words = len(text.split())
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def render_markdown(text):
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def parse_post(raw, source_path=None):
    """Turn one Markdown file's contents into a Post, validating its metadata."""
    where = f" in {source_path.name}" if source_path else ""
    meta, body = split_front_matter(raw)

    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        raise BlogError(f"missing required front matter {missing}{where}")

    slug = str(meta["slug"])
    if not SLUG_PATTERN.match(slug):
        raise BlogError(f"slug {slug!r} must be lowercase words joined by hyphens{where}")

    post_date = meta["date"]
    if isinstance(post_date, str):
        try:
            post_date = date.fromisoformat(post_date)
        except ValueError:
            raise BlogError(f"date {post_date!r} must be YYYY-MM-DD{where}")
    if not isinstance(post_date, date):
        raise BlogError(f"date must be YYYY-MM-DD{where}")

    tags = meta["tags"]
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise BlogError(f"tags must be a list of strings{where}")

    related_project = None
    if meta.get("related_project"):
        related_project = content.get_project(str(meta["related_project"]))
        if related_project is None:
            raise BlogError(
                f"related_project {meta['related_project']!r} is not a project slug{where}"
            )

    if not body.strip():
        raise BlogError(f"post body is empty{where}")

    known = set(REQUIRED_FIELDS) | {"related_project", "github_url"}
    return Post(
        title=str(meta["title"]),
        slug=slug,
        date=post_date,
        description=str(meta["description"]).strip(),
        tags=tags,
        body_markdown=body,
        body_html=render_markdown(body),
        reading_minutes=reading_minutes(body),
        related_project=related_project,
        github_url=str(meta["github_url"]) if meta.get("github_url") else None,
        source_path=source_path,
        extra={k: v for k, v in meta.items() if k not in known},
    )


def load_posts(blog_dir=BLOG_DIR):
    """Load every post under blog_dir, newest first. Raises BlogError on bad posts."""
    posts = []
    seen = {}
    for path in sorted(Path(blog_dir).glob("*.md")):
        post = parse_post(path.read_text(encoding="utf-8"), source_path=path)
        if post.slug in seen:
            raise BlogError(
                f"duplicate slug {post.slug!r} in {path.name} and {seen[post.slug].name}"
            )
        seen[post.slug] = path
        posts.append(post)
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


def get_post(posts, slug):
    for post in posts:
        if post.slug == slug:
            return post
    return None


if __name__ == "__main__":
    for post in load_posts():
        print(f"{post.date}  {post.slug:45s}  {post.reading_minutes} min  {post.title}")
    print(f"OK: {len(load_posts())} post(s) validated")
