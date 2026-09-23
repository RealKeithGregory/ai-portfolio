"""HTTP routes, rendered pages, and the public surface they expose.

The boundary tests here work from allowlists: the app must expose only the
routes this site declares, and public pages must link only to approved
destinations. An allowlist catches anything unapproved without naming it."""

from html.parser import HTMLParser


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))


def links_in(html):
    parser = LinkCollector()
    parser.feed(html)
    return parser.hrefs


# Every route this application is meant to serve. FastAPI's own /docs,
# /redoc and /openapi.json are excluded from the comparison below.
APPROVED_ROUTES = {"/", "/blog", "/blog/{slug}", "/api/search", "/api/chat"}

FASTAPI_BUILTIN_ROUTES = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

# The pages are allowed to link to: the two site pages, published articles,
# in-page anchors, static assets, and external URLs.
APPROVED_EXACT_LINKS = {"/", "/blog"}


def is_approved_link(href, post_urls):
    """True when an href points somewhere this site is meant to expose."""
    if href is None or href.startswith(("http://", "https://", "mailto:")):
        return True
    if href in APPROVED_EXACT_LINKS or href in post_urls:
        return True
    return href.startswith(("#", "/#", "/static/"))


def test_homepage_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Keith" in r.text and "Building Reliable AI Systems" in r.text
    hrefs = links_in(r.text)
    assert "/blog" in hrefs
    assert "https://github.com/RealKeithGregory" in hrefs


def test_homepage_shows_recent_posts_but_not_full_articles(client, posts):
    r = client.get("/")
    for post in posts[:3]:
        assert post.title in r.text
        assert post.url in links_in(r.text)
    # The article body itself must only appear on the article page.
    assert "<div class=\"article-body\">" not in r.text


def test_homepage_project_anchors_exist(client):
    import content

    r = client.get("/")
    for project in content.PROJECTS:
        assert f'id="project-{project["slug"]}"' in r.text


def test_blog_index_lists_every_post(client, posts):
    r = client.get("/blog")
    assert r.status_code == 200
    hrefs = links_in(r.text)
    for post in posts:
        assert post.title in r.text
        assert post.url in hrefs
    assert "/" in hrefs  # back to portfolio


def test_blog_post_renders_article(client, posts):
    post = posts[0]
    r = client.get(post.url)
    assert r.status_code == 200
    assert post.title in r.text
    assert post.description in r.text
    assert post.body_html[:200] in r.text
    assert post.date.isoformat() in r.text
    hrefs = links_in(r.text)
    assert "/blog" in hrefs and "/" in hrefs


def test_unknown_blog_slug_is_404_html(client):
    r = client.get("/blog/this-post-does-not-exist")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "Page not found" in r.text


def test_unknown_page_is_404_not_homepage(client):
    r = client.get("/definitely-not-a-page")
    assert r.status_code == 404
    assert "Keith<br>" not in r.text


def test_unknown_api_path_is_json_404(client):
    r = client.post("/api/nothing")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_app_exposes_only_approved_routes():
    """Route integrity: the app serves exactly the routes it declares, so a
    route cannot be added or re-added without this test noticing."""
    import server

    registered = {
        r.path for r in server.app.routes if hasattr(r, "methods")
    } - FASTAPI_BUILTIN_ROUTES
    assert registered == APPROVED_ROUTES


def test_public_pages_link_only_to_approved_destinations(client, posts):
    """Any internal link that is not an approved destination fails here."""
    post_urls = {p.url for p in posts}
    for path in ["/", "/blog", posts[0].url]:
        for href in links_in(client.get(path).text):
            assert is_approved_link(href, post_urls), f"unapproved link {href!r} on {path}"


def test_undeclared_paths_are_not_served(client):
    """Anything outside the declared routes returns the site 404 rather than
    content."""
    for path in ["/about-me", "/cv", "/downloads/profile.pdf", "/notes"]:
        assert client.get(path).status_code == 404, path


def test_static_mount_serves_only_public_assets(client):
    """The static mount must not reach files outside public/."""
    for path in [
        "/static/../content.py",
        "/static/../../content.py",
        "/static/%2e%2e/content.py",
    ]:
        assert client.get(path).status_code != 200, path


def test_static_assets_are_served(client):
    css = client.get("/static/css/styles.css")
    js = client.get("/static/js/site.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]


def test_every_page_has_primary_navigation(client, posts):
    for path in ["/", "/blog", posts[0].url]:
        hrefs = links_in(client.get(path).text)
        for target in ["/#projects", "/blog", "/#about", "/#contact"]:
            assert target in hrefs, f"{target} missing from nav on {path}"
        assert "https://github.com/RealKeithGregory" in hrefs, f"GitHub missing on {path}"


def test_navigation_contains_exactly_the_approved_items(client):
    """Nav integrity: the primary navigation is an exact set, so an extra or
    renamed item is caught without listing what it must not be."""
    import re

    html = client.get("/").text
    nav = html.split('<ul class="nav-links"', 1)[1].split("</ul>", 1)[0]
    labels = [re.sub(r"<[^>]+>", "", item).strip() for item in re.findall(r"<li>.*?</li>", nav, re.S)]
    assert labels == ["Projects", "Blog", "About", "GitHub", "Contact"]
