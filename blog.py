"""Markdown blog loader.

Articles live in content/blog/*.md with a YAML front matter block:

    ---
    title: "Why I'm Learning AI Engineering"
    slug: "why-im-learning-ai-engineering"
    date: "2026-09-21"
    description: "One or two sentences shown in listings."
    tags: [AI Engineering, Career]
    github_url: https://github.com/...   # optional
    social_subtitle: "One short line."   # optional, social card only
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


BLOG_DIR = Path(__file__).parent / "content" / "blog"
# Each post's social card, rendered by tools/make_social_card.py and served
# from /static like the rest of assets/.
SOCIAL_CARD_DIR = Path(__file__).parent / "assets" / "images" / "social" / "blog"
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
    github_url: str | None = None
    social_image: str | None = None
    source_path: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def url(self):
        return f"/blog/{self.slug}"

    @property
    def date_display(self):
        return self.date.strftime("%B %-d, %Y")


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

    if not body.strip():
        raise BlogError(f"post body is empty{where}")

    known = set(REQUIRED_FIELDS) | {"github_url"}
    return Post(
        title=str(meta["title"]),
        slug=slug,
        date=post_date,
        description=str(meta["description"]).strip(),
        tags=tags,
        body_markdown=body,
        body_html=render_markdown(body),
        reading_minutes=reading_minutes(body),
        github_url=str(meta["github_url"]) if meta.get("github_url") else None,
        source_path=source_path,
        extra={k: v for k, v in meta.items() if k not in known},
    )


def social_image_url(slug, card_dir=SOCIAL_CARD_DIR):
    """URL of the post's own social card, or None when it has not been
    rendered. None is not an error: the page falls back to the site card."""
    if (Path(card_dir) / f"{slug}.png").is_file():
        return f"/static/images/social/blog/{slug}.png"
    return None


def load_posts(blog_dir=BLOG_DIR):
    """Load every post under blog_dir, newest first. Raises BlogError on bad posts."""
    posts = []
    seen = {}
    for path in sorted(Path(blog_dir).glob("*.md")):
        post = parse_post(path.read_text(encoding="utf-8"), source_path=path)
        post.social_image = social_image_url(post.slug)
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
