"""Semantic search over the portfolio.

Chunks are derived from content.py and the blog posts, embedded once with
sentence-transformers at startup, and ranked by cosine similarity. Vectors
are normalized so the dot product is the cosine similarity. Scores are raw
similarities in [-1, 1] and are not calibrated probabilities.

The corpus is the public portfolio only: About, AI focus areas, skills,
project case studies, contact links, and blog posts. Employment history is
not part of content.py and must never be added to the index -- anything
embedded here is retrievable by any visitor.
"""

import numpy as np

import content

# The embedding model, named in full and pinned to one commit of the Hugging
# Face repository. The pin matters here because the retrieval tests assert
# which chunk ranks first for a given question: if the upstream repository
# published new weights, those assertions would start failing for a reason
# that has nothing to do with this code. Moving the pin is a deliberate
# change, reviewed by re-running the retrieval tests.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
# The model is plain BERT weights loaded by sentence-transformers. It carries
# no custom modelling code, and none is ever executed: see load_model().
MODEL_TRUST_REMOTE_CODE = False

DEFAULT_TOP_K = 5
SNIPPET_CHARS = 260
# Blog paragraphs are grouped until a chunk reaches roughly this many words.
BLOG_CHUNK_WORDS = 110


def _chunk(section, text, url):
    return {"section": section, "text": " ".join(text.split()), "url": url}


def snippet(text, limit=SNIPPET_CHARS):
    """Shorten a chunk for display, cutting at a word boundary."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:—-") + "…"


def content_chunks():
    """Chunks for the bio, AI focus areas, skills, projects, and contact details."""
    profile = content.PROFILE
    # The focus areas live inside the About chunk rather than in a chunk of
    # their own. As a standalone list they were pure keywords, so a question
    # like "what has Keith built with agents?" ranked the About section above
    # the agent project itself -- the visitor wants the project, not the bio.
    chunks = [
        _chunk(
            "About",
            f"{profile['name']}, {profile['headline']}, specializing in "
            f"{profile['specialization']}. " + " ".join(profile["about"])
            + " Focus areas: " + ", ".join(profile["ai_focus"]) + ".",
            "/#about",
        ),
    ]

    # One chunk for the Projects section as a whole, so "what is he working
    # on?" lands on the project list instead of the bio.
    overview = ["The AI engineering projects on this portfolio."]
    for key, heading, blurb in content.PROJECT_CATEGORIES:
        named = ", ".join(
            f"{project['name']} ({content.STATUS_LABELS[project['status']]})"
            for project in content.projects_in_category(key)
        )
        overview.append(f"{heading}: {blurb} {named}.")
    chunks.append(_chunk("Projects overview", " ".join(overview), "/#projects"))

    for group in content.SKILL_GROUPS:
        chunks.append(
            _chunk(
                f"Skills: {group['name']}",
                f"{group['blurb']} {', '.join(group['skills'])}.",
                "/#skills",
            )
        )

    for project in content.PROJECTS:
        status = content.STATUS_LABELS[project["status"]]
        parts = [f"{project['name']} ({status}). {project['summary']}"]
        for key, label in content.CASE_STUDY_SECTIONS:
            if key in project["sections"]:
                parts.append(f"{label}: {project['sections'][key]}")
        if project.get("questions"):
            parts.append("Evaluation questions: " + " ".join(project["questions"]))
        parts.append("Tags: " + ", ".join(project["tags"]) + ".")
        chunks.append(
            _chunk(f"Project: {project['name']}", " ".join(parts), f"/#project-{project['slug']}")
        )

    links = profile["links"]
    chunks.append(
        _chunk(
            "Contact",
            f"Reach {profile['name']} on LinkedIn ({links['linkedin']}), by email "
            f"({links['email']}), or on GitHub ({links['github']}).",
            "/#contact",
        )
    )
    return chunks


def blog_chunks(posts):
    """One chunk for a post's title + description, then its body in paragraph groups."""
    chunks = []
    for post in posts:
        section = f"Blog: {post.title}"
        chunks.append(_chunk(section, f"{post.title}. {post.description}", post.url))

        buffer, count = [], 0
        for paragraph in post.plain_text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            buffer.append(paragraph)
            count += len(paragraph.split())
            if count >= BLOG_CHUNK_WORDS:
                chunks.append(_chunk(section, " ".join(buffer), post.url))
                buffer, count = [], 0
        if buffer:
            chunks.append(_chunk(section, " ".join(buffer), post.url))
    return chunks


def load_model():
    """Load the pinned embedding model.

    In deployment the weights are already in the image, baked in at build
    time under HF_HOME, and HF_HUB_OFFLINE=1 stops anything reaching for the
    Hugging Face Hub at runtime. Running locally, the first call downloads
    them (~87 MB) into the local cache instead.

    `trust_remote_code` stays False so that nothing from the model repository
    is ever executed as Python -- only weights and config are read.

    sentence_transformers is imported here rather than at the top of the
    module because importing it pulls in PyTorch, which is by far the most
    expensive import in the process and the largest thing in the image. A
    request for a portfolio page does not need any of it, so nothing loads
    it until a search actually asks for it.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=MODEL_TRUST_REMOTE_CODE,
    )


class SearchIndex:
    """Embeds chunks once; `query` ranks them by cosine similarity."""

    def __init__(self, chunks, model=None):
        self.chunks = chunks
        self.model = model or load_model()
        self.embeddings = self.model.encode(
            [c["text"] for c in chunks], normalize_embeddings=True
        )

    def query(self, text, top_k=DEFAULT_TOP_K):
        """Top chunks by cosine similarity, keeping only the best chunk per page.

        A long article is split into several chunks; without this a single
        post could fill every result slot with near-duplicate hits.
        """
        query_vec = self.model.encode([text], normalize_embeddings=True)
        scores = (self.embeddings @ query_vec.T).flatten()
        results, seen_urls = [], set()
        for i in np.argsort(scores)[::-1]:
            chunk = self.chunks[i]
            if chunk["url"] in seen_urls:
                continue
            seen_urls.add(chunk["url"])
            results.append(
                {**chunk, "snippet": snippet(chunk["text"]), "score": round(float(scores[i]), 4)}
            )
            if len(results) == top_k:
                break
        return results


def build_index(posts):
    return SearchIndex(content_chunks() + blog_chunks(posts))
