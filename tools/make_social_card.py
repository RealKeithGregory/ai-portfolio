"""Render a social card: the 1200×630 PNG a link preview shows.

A local publishing tool. It is never deployed (.vercelignore keeps tools/
out) and CI does not run it; the PNGs it writes are committed like any other
content.

    pip install -r requirements-tools.txt
    playwright install chromium        # once; skipped if already installed

    python tools/make_social_card.py why-im-learning-ai-engineering
    python tools/make_social_card.py --site

A post card takes its text from the post's front matter: the title, the first
tag as the category label, and `social_subtitle` if the post has one. The
site card, used by every page without its own image, takes its text from
content.PROFILE.
"""

import argparse
import math
import random
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(ROOT))

import blog  # noqa: E402
import content  # noqa: E402

SOCIAL_DIR = ROOT / "assets" / "images" / "social"
WIDTH, HEIGHT = 1200, 630

# Fixed so every card shares one constellation. Changing it changes the look
# of every card rendered afterwards.
MOTIF_SEED = 7


def post_card(slug):
    post = blog.get_post(blog.load_posts(), slug)
    if post is None:
        sys.exit(f"No post with slug {slug!r} in {blog.BLOG_DIR}")
    card = {
        "label": f"Blog · {post.tags[0]}",
        "title": post.title,
        "subtitle": post.extra.get("social_subtitle"),
    }
    return card, SOCIAL_DIR / "blog" / f"{slug}.png"


def site_card():
    # Deliberately minimal: the headline says what the site is about, so a
    # label or subtitle would only repeat it.
    card = {"label": None, "title": content.PROFILE["headline"], "subtitle": None}
    return card, SOCIAL_DIR / "site.png"


def neural_motif(node_count=44, link_distance=150):
    """Nodes and links in the style of the site's animated background, kept
    to the right-hand side of the card where the title never reaches."""
    rng = random.Random(MOTIF_SEED)
    nodes = [
        {
            "x": round(rng.uniform(700, WIDTH + 20), 1),
            "y": round(rng.uniform(-20, HEIGHT + 20), 1),
            "r": round(rng.uniform(1.5, 3.5), 1),
        }
        for _ in range(node_count)
    ]
    links = []
    for index, start in enumerate(nodes):
        for end in nodes[index + 1:]:
            distance = math.dist((start["x"], start["y"]), (end["x"], end["y"]))
            if distance < link_distance:
                links.append({
                    "x1": start["x"], "y1": start["y"],
                    "x2": end["x"], "y2": end["y"],
                    # Nearer nodes get stronger links, as on the site.
                    "opacity": round(0.4 * (1 - distance / link_distance), 3),
                })
    return nodes, links


def render_html(card):
    env = Environment(loader=FileSystemLoader(TOOLS_DIR), autoescape=True)
    nodes, links = neural_motif()
    return env.get_template("social_card.html").render(
        name=content.PROFILE["name"], nodes=nodes, links=links, **card
    )


# Both checks run in the page before the screenshot. A card rendered in a
# fallback font, or with text cut off, would otherwise be written silently.
FONTS_LOADED = """() => {
    const loaded = [...document.fonts]
        .filter(face => face.status === 'loaded')
        .map(face => face.family.replace(/["']/g, ''));
    return ['Syne', 'Space Mono'].every(family => loaded.includes(family));
}"""
TEXT_OVERFLOWS = """() => {
    const card = document.querySelector('.card');
    return card.scrollHeight > card.clientHeight;
}"""


def screenshot(html, output_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(html, wait_until="networkidle")
        page.evaluate("async () => { await document.fonts.ready; }")
        if not page.evaluate(FONTS_LOADED):
            sys.exit("Syne and Space Mono did not load from Google Fonts; is the network up?")
        if page.evaluate(TEXT_OVERFLOWS):
            sys.exit("The text does not fit on the card; shorten the title or subtitle.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=output_path)
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("slug", nargs="?", help="render the card for this blog post")
    target.add_argument("--site", action="store_true", help="render the site-wide fallback card")
    args = parser.parse_args()

    card, output_path = site_card() if args.site else post_card(args.slug)
    screenshot(render_html(card), output_path)
    size_kb = output_path.stat().st_size / 1024
    print(f"Wrote {output_path.relative_to(ROOT)} ({WIDTH}×{HEIGHT}, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
