"""Link previews: the canonical URL, the Open Graph and X card tags, and the
social-card images they point at.

LinkedIn, Facebook and X build a preview from these tags alone, without
running the page's script, so the tests read the rendered <head> the way a
crawler does."""

import dataclasses
import struct
from html.parser import HTMLParser

import content
import server

SITE_URL = content.SITE_URL
SITE_CARD_URL = SITE_URL + server.SITE_SOCIAL_IMAGE
CARD_SIZE = (1200, 630)
# Platforms accept up to 5 MB and a card is ~120 KB, so this budget catches a
# render that went wrong long before a platform would reject it.
CARD_BYTES_BUDGET = 500 * 1024

REQUIRED_TAGS = [
    "og:site_name", "og:type", "og:title", "og:description", "og:url",
    "og:image", "og:image:width", "og:image:height", "og:image:alt",
    "twitter:card", "twitter:title", "twitter:description",
    "twitter:image", "twitter:image:alt",
]


class HeadCollector(HTMLParser):
    """Collects <meta> tags by property or name, and the canonical link."""

    def __init__(self):
        super().__init__()
        self.meta = {}
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and "content" in attrs:
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key] = attrs["content"]
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")


def preview(client, path):
    collector = HeadCollector()
    collector.feed(client.get(path).text)
    return collector


def public_pages(posts):
    return ["/", "/blog"] + [post.url for post in posts]


def png_size(data):
    """Width and height from a PNG's header chunk, which always comes first."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def test_every_page_has_complete_preview_tags(client, posts):
    for path in public_pages(posts):
        tags = preview(client, path)
        missing = [name for name in REQUIRED_TAGS if not tags.meta.get(name)]
        assert not missing, f"{path} is missing {missing}"
        assert tags.meta["twitter:card"] == "summary_large_image", path


def test_canonical_and_preview_urls_are_absolute_production_urls(client, posts):
    for path in public_pages(posts):
        tags = preview(client, path)
        assert tags.canonical == SITE_URL + path, path
        assert tags.meta["og:url"] == SITE_URL + path, path
        assert tags.meta["og:image"].startswith(SITE_URL + "/static/"), path
        assert tags.meta["twitter:image"] == tags.meta["og:image"], path


def test_canonical_url_ignores_query_strings(client, posts):
    """Shared links often carry tracking parameters; they must not become a
    second address for the same article."""
    tags = preview(client, posts[0].url + "?utm_source=linkedin")
    assert tags.canonical == SITE_URL + posts[0].url
    assert tags.meta["og:url"] == SITE_URL + posts[0].url


def test_preview_images_are_served_at_their_declared_size(client, posts):
    """The tags promise the crawler an image of a given size. Each image must
    exist, be a PNG, and match that promise."""
    for path in public_pages(posts):
        tags = preview(client, path)
        image_url = tags.meta["og:image"]
        response = client.get(image_url.removeprefix(SITE_URL))
        assert response.status_code == 200, image_url
        assert response.headers["content-type"] == "image/png", image_url
        declared = (int(tags.meta["og:image:width"]), int(tags.meta["og:image:height"]))
        assert png_size(response.content) == declared == CARD_SIZE, image_url
        assert len(response.content) < CARD_BYTES_BUDGET, image_url


def test_every_post_has_its_own_social_card(client, posts):
    """The publishing gate. A post without its own card still works -- it
    falls back to the site card -- but it should not be published that way."""
    assert posts, "no posts loaded, so this check would pass without checking anything"
    for post in posts:
        expected = f"{SITE_URL}/static/images/social/blog/{post.slug}.png"
        assert preview(client, post.url).meta["og:image"] == expected, (
            f"{post.slug} has no social card; run: python tools/make_social_card.py {post.slug}"
        )


def test_posts_preview_as_articles_with_their_own_title_and_date(client, posts):
    for post in posts:
        tags = preview(client, post.url)
        assert tags.meta["og:type"] == "article", post.slug
        # The bare title: the site name is already in og:site_name.
        assert tags.meta["og:title"] == tags.meta["twitter:title"] == post.title, post.slug
        assert tags.meta["og:description"] == post.description, post.slug
        assert tags.meta["article:published_time"] == post.date.isoformat(), post.slug


def test_other_pages_preview_as_the_site_with_the_site_card(client):
    for path in ["/", "/blog"]:
        tags = preview(client, path)
        assert tags.meta["og:type"] == "website", path
        assert "article:published_time" not in tags.meta, path
        assert tags.meta["og:image"] == SITE_CARD_URL, path


def test_error_pages_declare_no_canonical_url(client):
    tags = preview(client, "/not-a-page")
    assert tags.canonical is None
    assert "og:url" not in tags.meta
    assert tags.meta["og:image"] == SITE_CARD_URL


def test_post_without_a_card_falls_back_to_the_site_card(posts):
    """A missing card degrades to the site card: never a broken image, and
    never an error on the page."""
    uncarded = dataclasses.replace(posts[0], social_image=None)
    card = server.social_card(uncarded)
    assert card["url"] == SITE_CARD_URL
    assert card["alt"] == server.social_card()["alt"]
