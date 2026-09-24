# AI Engineering Portfolio & Technical Blog

Live portfolio: <https://keithgregory.vercel.app>

Personal site for Keith Gregory: building, evaluating, and documenting AI
systems across RAG and retrieval, agents and tool use, guardrails, and
observability, with a growing focus on financial AI. It has three jobs:

1. **Portfolio**. A fast technical overview: what has been built, how it was
   evaluated, and where the evidence lives.
2. **Blog**. Markdown articles with the detailed reasoning, failures, and
   lessons that do not fit on a project card.
3. **Semantic search**. A working retrieval feature over the site's own
   content, built with local embeddings.

## Architecture

```text
FastAPI               routing, lifespan, JSON APIs           server.py
Jinja2 templates      server-rendered pages                  templates/
Vanilla HTML/CSS/JS   one stylesheet, one script, no build   assets/
Markdown + YAML       blog articles with front matter        content/blog/
Python data           canonical profile/projects/skills      content.py
sentence-transformers semantic search over content + blog    search.py
Starlette middleware  security headers, rate + size limits   security.py
Environment settings  one variable: APP_ENV                  config.py
pytest                route, blog, search, security tests    tests/
Vercel function       CPU PyTorch + baked model, the host    vercel.json
Container image       the same app, kept as a fallback       Dockerfile
```

Request flow:

- `GET /` renders `templates/index.html` from `content.py` and the three most
  recent posts.
- `GET /blog` and `GET /blog/{slug}` render posts loaded by `blog.py`.
  Unknown slugs return a real 404.
- `POST /api/search` embeds the query with `all-MiniLM-L6-v2` and ranks
  pre-computed chunk embeddings by cosine similarity. The index is built once
  at startup from `content.py` **and every blog post**, so new articles are
  searchable without touching Python.
- `POST /api/chat` is a small scripted keyword responder ("Portfolio Guide").
  It is not an LLM and is labelled that way in the UI.

There is no database, CMS, auth, or frontend build step.

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --reload-include '*.md' --reload-include '*.html' --port 3000
```

Open <http://localhost:3000>. The `--reload-include` flags make uvicorn
restart when a blog post or template changes, not only Python files. The first start downloads the embedding model
(~87 MB) into the Hugging Face cache; later starts take a few seconds.

`APP_ENV` defaults to `development`, so `/docs`, `/redoc` and `/openapi.json`
are available locally and no HSTS header is sent. See `.env.example`.

On later sessions only the last two lines are needed. Activate the virtual
environment, then run uvicorn. If VS Code offers to use `./venv` as the
workspace interpreter, accept it so the editor resolves the same packages.

## Testing

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite starts the app once (loading the model) and covers:

- routes: homepage, blog index, article, 404s, static assets, navigation
- blog: Markdown parsing, required front matter, invalid dates/slugs,
  duplicate slugs, related-project validation, ordering, reading time
- search: response schema, ranking, de-duplication, blog/project content is
  indexed, malformed requests return 422
- content: no placeholder URLs in rendered pages, the profile exposes an exact
  set of fields, project definitions are consistent, guide labels are honest
- boundaries: the app serves only its declared routes, pages link only to
  approved destinations, and the search index is built only from approved
  content sources
- security: the response headers, that the templates contain nothing the CSP
  forbids, that the interactive docs are development-only, and that the rate
  and body-size limits hold

`python -m blog` validates every article from the command line. CI
(`.github/workflows/ci.yml`) installs dependencies, validates posts, checks
syntax, and runs the tests on every push and pull request.

## Content

### Adding a blog article

Create `content/blog/<slug>.md`:

```markdown
---
title: "Evaluating Retrieval in the Knowledge Base Assistant"
slug: "evaluating-retrieval"
date: "2026-10-15"
description: "One or two sentences shown in listings and search."
tags:
  - RAG
  - Evaluation
related_project: agentic-knowledge-base-assistant   # optional: a slug from content.py
github_url: https://github.com/RealKeithGregory/...  # optional
---

Article body in Markdown. Fenced code blocks and tables are supported.
```

Rules enforced by `blog.py` (and by the tests):

- `title`, `slug`, `date` (YYYY-MM-DD), `description`, and `tags` are required
- `slug` is lowercase words joined by hyphens and must be unique
- `related_project`, if set, must match a project slug in `content.py`

**Article Markdown is trusted content.** Posts come from this repository and
are never accepted from a visitor or any other external source. The rendered
HTML is inserted into the page unescaped (`post.body_html | safe`), and
python-markdown passes raw HTML through, so a `<script>` tag written into an
article would run. That is the same trust already placed in `content.py` and
the templates: committing to this repository is the trust boundary. Everything
that *does* come from a visitor -- search queries and Portfolio Guide messages
-- is escaped, and the CSP blocks inline script regardless. If articles ever
come from somewhere else, that is the point to add a sanitizer.

Posts and embeddings are loaded once at startup. With the run command above
the server restarts itself when a `.md` or `.html` file changes; without the
`--reload-include` flags, restart it by hand after editing content.
The article appears on `/blog`, on the homepage (if it is one of the three
newest), in semantic search, and (when `related_project` is set) as an
"Article" link on that project's card.

### Editing portfolio content

Everything the site says about its focus areas, skills, and projects is in
`content.py`. Project entries follow a case-study shape (problem,
architecture, implementation, evaluation, failure modes, results,
improvements) plus `evidence` links. Leave a section out rather than guessing;
planned projects list the evaluation questions they must answer instead of
results. Projects are grouped by `category` into core and supporting work.
`TODO` comments mark links that are not known yet.

This site is a portfolio, not a resume: `content.py` deliberately holds no
employment history, meaning no employer names, job titles, dates, or duties. Anything
added there is rendered publicly *and* embedded into the semantic search index,
so it is retrievable by any visitor. Personal resume material is kept
outside the repository entirely and is never served.

## Production

One environment variable decides the difference, and it is never set locally:

| | development (default) | `APP_ENV=production` |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | served | not served |
| `Strict-Transport-Security` | not sent | sent, one year |
| everything else | identical | identical |

Set on the Vercel project, and in the `Dockerfile` for the container build;
`.env.example` lists it. The app reads real environment variables, so `.env`
is only for your own shell and is never required.

### What the app defends itself with

- **Security headers** on every response, pages and API alike (`security.py`).
  The CSP is `default-src 'self'` with no `'unsafe-inline'` and no
  `'unsafe-eval'`: the only external origins allowed are the Google Fonts
  stylesheet and the font files it loads. Nothing in the templates uses an
  inline `<script>`, an `on*=` handler, or a `style=` attribute, and tests
  assert that stays true -- a CSP is only worth having if the site obeys it.
  Also `nosniff`, `frame-ancestors 'none'` with `X-Frame-Options: DENY`,
  `strict-origin-when-cross-origin`, and a `Permissions-Policy` that denies
  every browser feature the site does not use.
- **Rate limits** on the two POST endpoints, per client IP, in memory:
  20/minute on `/api/search` (it runs embedding inference) and 40/minute on
  `/api/chat` (keyword matching, cheaper). Over the limit is a `429` with
  `Retry-After`, which the page reports as a rate limit rather than a
  failure. Pages are never throttled. The counters live in the process, so
  each running instance enforces its own allowance. On a serverless platform
  that means the limit is per instance rather than global -- a deliberate
  trade-off, since a shared counter would mean a Redis this site does not
  otherwise need. It still bounds what one client can drive on the instance
  serving it, which is what protects the inference.
- **Request bounds.** Both endpoints take one string of at most 500
  characters. A body over 16 KB is refused with `413` before it is read.
  Empty, blank, wrong-typed, over-long and malformed-JSON bodies all return
  `422`. The platform caps a request body at 4.5 MB before the app sees it.
- **A pinned model.** `search.py` names the model in full and pins it to one
  commit of its Hugging Face repository, with `trust_remote_code` off so no
  code from that repository is ever executed. The weights are downloaded into
  the image at build time, so a running container needs no network access
  (`HF_HUB_OFFLINE=1`) and a cold start does not wait on a download.

## Deployment

Vercel, which runs the FastAPI application itself. There is no proxy and no
second runtime: a request is served by the app, on Vercel, and nowhere else.

| | |
|---|---|
| Build | `git push origin main` (Vercel builds from this repository) |
| Entry point | `server.py`, whose `app` Vercel's Python runtime loads directly |
| Runtime | Python 3.12 (`.python-version`), Fluid compute, region `iad1` |
| CPU / memory | 1 vCPU, 2 GB |
| Max duration | 300 s, which the slowest cold search uses about 5% of |
| Instances | scale to zero when idle |
| Environment | `APP_ENV=production`, `HF_HUB_OFFLINE=1` (set on the project) |
| Persistent disk | none; the bundle carries the model |

Two things in `vercel.json` do the work the `Dockerfile` does for a container:

- `installCommand` pins the **CPU build of PyTorch** from PyTorch's own index.
  The default PyPI wheel brings roughly 2 GB of CUDA libraries that no
  function can use, and would not fit in any case.
- `buildCommand` runs `vercel_build.py`, which **bakes the pinned model into
  the bundle**. A function's filesystem is read-only apart from `/tmp`, and
  `/tmp` does not survive between instances, so the weights have to be
  written at build time. The script also flattens the Hugging Face cache's
  symlinks -- they do not survive bundling -- and refuses to finish unless the
  result loads again with `HF_HUB_OFFLINE=1` in a fresh interpreter.

Dependencies and weights come to about 1.4 GB unpacked, past the 500 MB
standard limit for a Python function, so Vercel places it on the large-function
path automatically. CI installs the same CPU wheel and runs the same build
script, so tests run against what production runs.

Static assets live in `assets/`, not `public/`: Vercel treats a root-level
`public/` as a CDN directory, and CDN-served files bypass the application --
which would mean serving the stylesheet and the script without the security
headers below.

### The container, and why it is still here

`Dockerfile` builds the same application for Google Cloud Run, which hosted
the site before this and is kept as a rollback target. CI still builds and
starts that image on every push, so the fallback cannot rot unnoticed.

### Which client address is trusted

The rate limiter keys on an address, so which address matters. uvicorn's
`--proxy-headers` is deliberately **not** used: with `--forwarded-allow-ips='*'`
it takes the **left-most** `X-Forwarded-For` entry, and that is the one a
visitor writes. `security.client_identity()` reads the header itself and
takes the **right-most** entry instead -- the one Google's front end appended
after seeing the connection. A request forged with `X-Forwarded-For: 9.9.9.9`
arrives as `9.9.9.9, <real address>`, so the forgery lands on the left and is
ignored.

IPv6 visitors are counted per **/64 network** rather than per address. A
home connection is handed a whole /64 and its host bits rotate on their own
(privacy extensions), so counting full addresses would hand one subscriber an
unlimited supply of allowances. IPv4 is counted per address.

`TRUSTED_PROXY_HOPS = 1` says one proxy in front of the app may be believed.
That is true on Vercel, which sets `X-Forwarded-For` to the client's address
and discards whatever the client sent -- so the header arrives with one entry
and that entry is not the visitor's to choose. It was equally true on Cloud
Run, where nothing reaches the container except through Google's front end.
Exposing this app's port directly would make the header forgeable again, so
the assumption is pinned by a test rather than left in a comment. With no
header at all, the socket peer is used.

Checked against the running site rather than assumed: fill the window to the
limit, then replay it with `X-Forwarded-For`, `X-Real-IP`, `Forwarded`,
`X-Client-IP` and the `X-Vercel-*` forwarding headers all forged. Every
variant still returns `429`.

## Philosophy

The site deliberately avoids frameworks, build tooling, and services it does
not need. A FastAPI app, a few templates, one stylesheet, one script, and
Markdown files are enough to render pages, publish articles, and run semantic
search. They are also easy for another engineer to read in one sitting.
