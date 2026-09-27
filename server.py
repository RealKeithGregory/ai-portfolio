"""FastAPI entry point for the portfolio and blog.

Run locally:  uvicorn server:app --reload --reload-include '*.md' --reload-include '*.html' --port 3000
(the --reload-include flags restart the server when posts or templates change)
"""

import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.exceptions import HTTPException as StarletteHTTPException

import blog
import config
import content
import security

BASE_DIR = Path(__file__).parent
RECENT_POSTS_ON_HOME = 2
SITE_SOCIAL_IMAGE = "/static/images/social/site.png"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.posts = blog.load_posts()
    print(f"Loaded {len(app.state.posts)} blog post(s).")
    yield


def docs_settings():
    """FastAPI's interactive docs are a development convenience. Production
    serves only the routes this site declares, so /docs, /redoc and the
    OpenAPI schema are not built at all there."""
    if config.IS_PRODUCTION:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(lifespan=lifespan, **docs_settings())

app.add_middleware(security.SecurityHeadersMiddleware, hsts=config.IS_PRODUCTION)

app.mount("/static", StaticFiles(directory=BASE_DIR / "assets"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def emphasize(text):
    """Render *marked* spans in content strings as <strong>, escaping everything else."""
    parts = re.split(r"\*([^*]+)\*", str(text))
    out = []
    for i, part in enumerate(parts):
        out.append(f"<strong>{escape(part)}</strong>" if i % 2 else str(escape(part)))
    return Markup("".join(out))


templates.env.filters["emphasize"] = emphasize


def asset_version():
    """Newest mtime of the static assets, appended to their URLs so browsers
    never keep a stale stylesheet or script after an edit."""
    files = [BASE_DIR / "assets" / "css" / "styles.css", BASE_DIR / "assets" / "js" / "site.js"]
    return str(int(max(f.stat().st_mtime for f in files)))


def social_card(post=None):
    """The image a link preview shows. A post uses its own card when it has
    one; every other page, and a post whose card is missing, gets the site
    card, so a preview never points at an image that does not exist."""
    if post is not None and post.social_image:
        path, alt = post.social_image, f"{post.title} — {content.PROFILE['name']}"
    else:
        path, alt = SITE_SOCIAL_IMAGE, f"{content.PROFILE['name']} — {content.PROFILE['headline']}"
    return {"url": content.SITE_URL + path, "alt": alt}


def page_context(request: Request, **extra):
    """Context shared by every template, plus page-specific values."""
    return {
        "request": request,
        "profile": content.PROFILE,
        "asset_version": asset_version(),
        # The canonical address of this page. The path alone, so a shared
        # link's ?utm_source=... never becomes part of it.
        "page_url": content.SITE_URL + request.url.path,
        "social_card": social_card(),
        **extra,
    }


# ─── PAGES ────────────────────────────────────────────────────────────────────
@app.get("/")
async def homepage(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        page_context(
            request,
            skill_groups=content.SKILL_GROUPS,
            recent_posts=request.app.state.posts[:RECENT_POSTS_ON_HOME],
        ),
    )


@app.get("/blog")
async def blog_index(request: Request):
    return templates.TemplateResponse(
        request, "blog.html", page_context(request, posts=request.app.state.posts)
    )


@app.get("/blog/{slug}")
async def blog_post(request: Request, slug: str):
    post = blog.get_post(request.app.state.posts, slug)
    if post is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse(
        request, "blog-post.html", page_context(request, post=post, social_card=social_card(post))
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return templates.TemplateResponse(
        request,
        "404.html" if exc.status_code == 404 else "error.html",
        # An error page is not a real address, so it declares no canonical URL.
        page_context(request, status_code=exc.status_code, detail=exc.detail, page_url=None),
        status_code=exc.status_code,
    )
