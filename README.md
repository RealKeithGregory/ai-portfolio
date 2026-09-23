# AI Engineering Portfolio & Technical Blog

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
Vanilla HTML/CSS/JS   one stylesheet, one script, no build   public/
Markdown + YAML       blog articles with front matter        content/blog/
Python data           canonical profile/projects/skills      content.py
sentence-transformers semantic search over content + blog    search.py
pytest                route, blog, search, and content tests tests/
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
(~90 MB) into the Hugging Face cache; later starts take a few seconds.

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

## Philosophy

The site deliberately avoids frameworks, build tooling, and services it does
not need. A FastAPI app, a few templates, one stylesheet, one script, and
Markdown files are enough to render pages, publish articles, and run semantic
search. They are also easy for another engineer to read in one sitting.
