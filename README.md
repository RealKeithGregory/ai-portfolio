# AI Engineering Portfolio & Technical Blog

Live portfolio: <https://keithgregory.vercel.app>

Personal site for Keith Gregory: building, evaluating, and documenting AI
systems across RAG and retrieval, agents and tool use, guardrails, and
observability, with a growing focus on financial AI. It has two jobs:

1. **Portfolio**. A fast technical overview: what is being built, how it will
   be evaluated, and where the evidence lives.
2. **Blog**. Markdown articles with the detailed reasoning, failures, and
   lessons that do not fit on a project card.

## Architecture

```text
FastAPI               routing, lifespan                      server.py
Jinja2 templates      server-rendered pages                  templates/
Vanilla HTML/CSS/JS   one stylesheet, one script, no build   assets/
Markdown + YAML       blog articles with front matter        content/blog/
Python data           canonical profile/projects/skills      content.py
Starlette middleware  security headers                       security.py
Environment settings  one variable: APP_ENV                  config.py
pytest                route, blog, content, security tests   tests/
Vercel function       the host; FastAPI preset, no build     requirements.txt
```

Request flow:

- `GET /` renders `templates/index.html` from `content.py` and the three most
  recent posts.
- `GET /blog` and `GET /blog/{slug}` render posts loaded by `blog.py`.
  Unknown slugs return a real 404.

There is no database, CMS, auth, or frontend build step.

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --reload-include '*.md' --reload-include '*.html' --port 3000
```

Open <http://localhost:3000>. The `--reload-include` flags make uvicorn
restart when a blog post or template changes, not only Python files.

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

The suite starts the app once and covers:

- routes: homepage, blog index, article, 404s, static assets, navigation
- blog: Markdown parsing, required front matter, invalid dates/slugs,
  duplicate slugs, related-project validation, ordering, reading time
- content: no placeholder URLs in rendered pages, the profile exposes an exact
  set of fields, project definitions are consistent
- boundaries: the app serves only its declared routes, and pages link only
  to approved destinations
- security: the response headers, that the templates contain nothing the CSP
  forbids, and that the interactive docs are development-only

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
description: "One or two sentences shown in listings."
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
the templates: committing to this repository is the trust boundary. Nothing
on the site comes from a visitor, and the CSP blocks inline script regardless.
If articles ever come from somewhere else, that is the point to add a
sanitizer.

Posts are loaded once at startup. With the run command above
the server restarts itself when a `.md` or `.html` file changes; without the
`--reload-include` flags, restart it by hand after editing content.
The article appears on `/blog`, on the homepage (if it is one of the three
newest), and (when `related_project` is set) as an
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
added there is rendered publicly. Personal resume material is kept outside the
repository entirely and is never served.

## Production

One environment variable decides the difference, and it is never set locally:

| | development (default) | `APP_ENV=production` |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | served | not served |
| `Strict-Transport-Security` | not sent | sent, one year |
| everything else | identical | identical |

Set on the Vercel project; `.env.example` lists it. The app reads real environment variables, so `.env`
is only for your own shell and is never required.

### What the app defends itself with

- **Security headers** on every response, pages, assets and errors alike
  (`security.py`). The CSP is `default-src 'self'` with no `'unsafe-inline'` and no
  `'unsafe-eval'`: the only external origins allowed are the Google Fonts
  stylesheet and the font files it loads. Nothing in the templates uses an
  inline `<script>`, an `on*=` handler, or a `style=` attribute, and tests
  assert that stays true -- a CSP is only worth having if the site obeys it.
  Also `nosniff`, `frame-ancestors 'none'` with `X-Frame-Options: DENY`,
  `strict-origin-when-cross-origin`, and a `Permissions-Policy` that denies
  every browser feature the site does not use.
- **No visitor input.** Every route is a `GET` that renders repository
  content. There is no form, no API and no endpoint that accepts data, so
  the CSP allows the script no network requests at all (`connect-src 'none'`).

## Deployment

```text
Visitor → Vercel → FastAPI portfolio
```

Vercel runs the FastAPI application itself. There is no proxy and no second
runtime: a request is served by the app, on Vercel, and nowhere else.

| | |
|---|---|
| Build | `git push origin main` (Vercel builds from this repository) |
| Entry point | `server.py`, whose `app` Vercel's Python runtime loads directly |
| Runtime | Python 3.12 (`.python-version`), Fluid compute, region `iad1` |
| CPU / memory | 1 vCPU, 2 GB |
| Instances | scale to zero when idle |
| Environment | `APP_ENV=production` (set on the project) |
| Persistent disk | none, and none needed |

There is no `vercel.json` and no build step. The project uses Vercel's
FastAPI preset, which installs `requirements.txt` and loads `server.py`.
CI does the same in a clean environment, checks that the installed
dependencies stay inside Vercel's standard 500 MB function size, and starts
the app in its production configuration, so a deploy-time failure shows up
as a red build first.

Static assets live in `assets/`, not `public/`: Vercel treats a root-level
`public/` as a CDN directory, and CDN-served files bypass the application --
which would mean serving the stylesheet and the script without the security
headers described above.

## Philosophy

The site deliberately avoids frameworks, build tooling, and services it does
not need. A FastAPI app, a few templates, one stylesheet, one script, and
Markdown files are enough to render pages and publish articles. They are also
easy for another engineer to read in one sitting.
