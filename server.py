"""FastAPI entry point for the portfolio and blog.

Run locally:  uvicorn server:app --reload --reload-include '*.md' --reload-include '*.html' --port 3000
(the --reload-include flags restart the server when posts or templates change)
"""

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio.to_thread

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

import blog
import config
import content
import search
import security

BASE_DIR = Path(__file__).parent
RECENT_POSTS_ON_HOME = 3

# uvicorn configures its own loggers but not this one, and the root logger
# defaults to WARNING -- which silently swallowed the index-build messages
# below. They are the only record of when the model loaded and how long it
# took, so the level is set explicitly rather than left to chance.
log = logging.getLogger("portfolio")
log.setLevel(logging.INFO)
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    log.addHandler(_handler)


class LazySearchIndex:
    """Builds the search index on first use, once per process.

    Startup used to embed the whole corpus before the app would serve
    anything, which put the embedding model on the critical path of every
    page. Nothing but /api/search needs it, so it is built on the first
    search instead: an instance that only ever serves pages never imports
    PyTorch, never loads the model, and never pays for either.

    Concurrency: the first caller takes the lock and builds. Anyone arriving
    meanwhile waits on the same lock and then finds the finished index
    rather than starting a second build, so the model is loaded at most once
    per process. The build runs in a worker thread because it is blocking
    CPU work that would otherwise stall the event loop -- and therefore
    every page request -- for as long as it took.

    Failure: an exception propagates to the caller and the index stays
    unbuilt, so a later search retries from scratch. It is deliberately not
    remembered as a permanent failure; a transient problem should not
    disable search until the instance is replaced.
    """

    def __init__(self, build):
        self._build = build
        self._index = None
        self._lock = asyncio.Lock()

    @property
    def ready(self):
        """True once the index exists. Never triggers a build."""
        return self._index is not None

    async def get(self):
        if self._index is not None:
            return self._index
        async with self._lock:
            # Another request may have finished the build while this one
            # was waiting for the lock.
            if self._index is None:
                log.info("Building search index (first search on this instance)")
                started = time.perf_counter()
                self._index = await anyio.to_thread.run_sync(self._build)
                log.info(
                    "Embedded %d searchable chunks in %.2fs.",
                    len(self._index.chunks),
                    time.perf_counter() - started,
                )
            return self._index


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Posts are cheap and every page needs them, so they load here. The
    # search index is not: see LazySearchIndex.
    app.state.posts = blog.load_posts()
    print(f"Loaded {len(app.state.posts)} blog post(s).")
    app.state.search_index = LazySearchIndex(
        lambda: search.build_index(app.state.posts)
    )
    yield


def docs_settings():
    """FastAPI's interactive docs are a development convenience. Production
    serves only the routes this site declares, so /docs, /redoc and the
    OpenAPI schema are not built at all there."""
    if config.IS_PRODUCTION:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(lifespan=lifespan, **docs_settings())

# Held by name so that its counters can be inspected and reset.
api_limiter = security.RateLimiter()

# Added last means outermost: the security headers are applied to every
# response, including the 429 and 413 the guard below returns itself.
app.add_middleware(security.ApiGuardMiddleware, limiter=api_limiter)
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


def articles_by_project(posts):
    """Map project slug -> posts whose front matter names it as related_project."""
    related = {}
    for post in posts:
        if post.related_project:
            related.setdefault(post.related_project["slug"], []).append(post)
    return related


def asset_version():
    """Newest mtime of the static assets, appended to their URLs so browsers
    never keep a stale stylesheet or script after an edit."""
    files = [BASE_DIR / "assets" / "css" / "styles.css", BASE_DIR / "assets" / "js" / "site.js"]
    return str(int(max(f.stat().st_mtime for f in files)))


def page_context(request: Request, **extra):
    """Context shared by every template, plus page-specific values."""
    return {
        "request": request,
        "profile": content.PROFILE,
        "asset_version": asset_version(),
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
            project_categories=content.PROJECT_CATEGORIES,
            projects_in_category=content.projects_in_category,
            case_study_sections=content.CASE_STUDY_SECTIONS,
            status_labels=content.STATUS_LABELS,
            recent_posts=request.app.state.posts[:RECENT_POSTS_ON_HOME],
            articles_by_project=articles_by_project(request.app.state.posts),
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
        request, "blog-post.html", page_context(request, post=post)
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse(
        request,
        "404.html" if exc.status_code == 404 else "error.html",
        page_context(request, status_code=exc.status_code, detail=exc.detail),
        status_code=exc.status_code,
    )


# ─── SEARCH ───────────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


@app.post("/api/search")
async def api_search(req: SearchRequest, request: Request):
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be blank")
    try:
        index = await request.app.state.search_index.get()
    except Exception:
        # The traceback goes to the logs, never to the visitor, and the rest
        # of the site is unaffected -- only search is degraded. Returning an
        # empty result list instead would be worse: it would look like an
        # answer.
        log.exception("Search index failed to build")
        raise HTTPException(
            status_code=503,
            detail="Search is temporarily unavailable. The rest of the site works.",
        )
    results = index.query(req.query)
    return {"query": req.query, "results": results}


# ─── PORTFOLIO GUIDE ──────────────────────────────────────────────────────────
# A small scripted responder: it matches keywords against a few prepared
# answers built from content.py. It is not an LLM and does not claim to be.
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


def guide_reply(message: str, posts) -> str:
    msg = message.lower()
    profile = content.PROFILE

    def has(*words):
        return any(w in msg for w in words)

    if has("blog", "article", "writing", "post", "read"):
        if posts:
            latest = posts[0]
            return (
                f"The latest article is \"{latest.title}\" ({latest.date_display}). "
                f"All articles are at /blog."
            )
        return "No articles are published yet. Check /blog later."

    if has("project", "built", "build", "case study", "rag", "agent"):
        built = [p["name"] for p in content.PROJECTS if p["status"] in ("live", "built")]
        planned = [p["name"] for p in content.PROJECTS if p["status"] == "planned"]
        return (
            f"Built: {', '.join(built)}. Planned next: {', '.join(planned)}. "
            "Each card in the Projects section expands into a case study."
        )

    if has("hire", "available", "open to", "opportunit", "looking for", "freelance"):
        return (
            f"{profile['name']} is open to conversations about AI engineering work: "
            "evaluation, reliability, RAG, and agents. The Contact section has "
            "LinkedIn and email."
        )

    if has(
        "experience", "background", "qa", "years", "career", "resume", "cv",
        "employer", "employ", "company", "work", "history", "job", "role",
    ):
        return (
            f"{profile['name']}'s approach to AI engineering is shaped by more than "
            "a decade of experience building, testing, automating, and validating "
            "software systems. This site is about the AI work itself. See the "
            "Projects section for what is being built and evaluated, /blog for the "
            f"engineering reasoning behind it, and GitHub ({profile['links']['github']}) "
            "for the implementation."
        )

    if has("skill", "know", "tech", "stack", "language", "tool"):
        groups = "; ".join(
            f"{g['name']}: {', '.join(g['skills'][:5])}" for g in content.SKILL_GROUPS
        )
        return f"Skills by area. {groups}. Full lists are in the Skills section."


    if has("contact", "reach", "email", "linkedin", "github"):
        links = profile["links"]
        return (
            f"LinkedIn: {links['linkedin']} · GitHub: {links['github']} · "
            f"Email: {links['email']}"
        )

    if has("search", "semantic", "embedding"):
        return (
            "The Search section embeds your question with sentence-transformers and "
            "ranks portfolio content and blog posts by cosine similarity. Everything runs "
            "locally, with no external API."
        )

    if has("who", "about", "tell me", "introduce", "keith"):
        return (
            f"{profile['name']}, {profile['headline']}. The focus is "
            f"{profile['specialization']}: RAG and retrieval, agents and tool use, "
            "guardrails, observability, and financial AI. See the About section for "
            "the short version."
        )

    return (
        "I only match a few keywords (projects, skills, blog, search, contact). "
        "For anything else, try the semantic search on this page."
    )


@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request):
    return {"reply": guide_reply(req.message, request.app.state.posts)}
