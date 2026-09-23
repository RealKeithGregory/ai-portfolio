"""Canonical portfolio content.

Everything the public site says lives here (or in content/blog/*.md).
Templates, the search index, and the portfolio guide all read from these
structures so the same fact is never written twice.

This is an AI engineering portfolio, not a resume. Employment history --
employer names, job titles, dates, duties -- is deliberately not present in
this module, because everything here is rendered publicly and indexed by the
semantic search. Keep personal resume material outside the repository.

Leave a TODO rather than inventing a value that is not known yet.
"""

PROFILE = {
    "name": "Keith Gregory",
    # The one-line positioning for the whole site: page titles, hero, metadata.
    "headline": "Building Reliable AI Systems",
    "specialization": "AI evaluation & reliability",
    "tagline": "AI Engineering · Evaluation & Reliability · RAG · Agents",
    # Short hero statement. Emphasis markers (*...*) are rendered as highlights.
    "summary": (
        "I build, evaluate, and document *AI systems*: RAG and retrieval, agents "
        "and tool use, guardrails, and observability, with a growing focus on "
        "*financial AI*. Every project here is measured, not just demonstrated."
    ),
    "about": [
        (
            "I'm focused on building AI systems that can be evaluated, tested, and "
            "improved rather than simply demonstrated. The questions I care about "
            "are the measurable ones: Did retrieval return the right chunk? Did the "
            "model pick the right tool with valid arguments? Is the answer grounded "
            "in the source? What happens when an API fails, or when the information "
            "simply is not there?"
        ),
        (
            "My current work explores RAG, retrieval evaluation, AI agents, tool "
            "calling, multi-agent systems, guardrails, observability, and financial "
            "AI. I document the architecture, engineering decisions, evaluation "
            "methods, failure modes, and lessons behind each project as I build it."
        ),
        (
            "My approach is shaped by more than a decade of experience building, "
            "testing, automating, and validating software systems."
        ),
    ],
    "workflow": ["Learn", "Build", "Evaluate", "Document evidence", "Improve"],
    # The public focus areas. These are technical areas of work, not job titles.
    "ai_focus": [
        "AI Evaluation & Reliability",
        "RAG & Retrieval",
        "Agents & Tool Calling",
        "Guardrails & Observability",
        "Multi-Agent Systems",
        "Financial AI",
    ],
    "links": {
        "github": "https://github.com/RealKeithGregory",
        "linkedin": "https://linkedin.com/in/devkeithgregory",
        "email": "keithgregory1625@gmail.com",
    },
}

# Skills are grouped, not rated. The question each group answers is: what
# supports the AI engineering work shown on this portfolio? Items are listed
# only when the projects, the blog, or this repository actually demonstrate
# them -- this is not a comprehensive tooling inventory.
SKILL_GROUPS = [
    {
        "name": "AI Engineering",
        "blurb": "What the projects on this site are built from.",
        "skills": [
            "LLM APIs",
            "Embeddings",
            "Semantic search",
            "RAG (building)",
            "Agents & tool calling (building)",
            "Structured outputs (building)",
            "Multi-agent systems (planned)",
        ],
    },
    {
        "name": "Evaluation & Reliability",
        "blurb": "How I decide whether an AI system actually works.",
        "skills": [
            "AI evaluation",
            "Retrieval evaluation",
            "Regression testing",
            "Schema validation",
            "Failure analysis",
            "Guardrails (learning)",
            "Observability (learning)",
        ],
    },
    {
        "name": "Engineering",
        "blurb": "The tools these systems are built and shipped with.",
        "skills": [
            "Python",
            "FastAPI",
            "APIs",
            "JavaScript",
            "SQL",
            "Git",
            "Docker",
            "CI/CD",
            "Playwright",
        ],
    },
]

# Projects are grouped so the long-term AI systems lead, with smaller working
# pieces of AI engineering underneath. (key, heading, blurb) in display order.
PROJECT_CATEGORIES = [
    (
        "core",
        "Core AI Engineering Projects",
        "The systems I am building to work through retrieval, agents, "
        "coordination, and the reliability problems each one creates.",
    ),
    (
        "supporting",
        "Supporting AI Engineering Projects",
        "Smaller pieces of AI engineering that are already running, and that the "
        "larger projects reuse.",
    ),
]

# Project case studies.
#
# `status` is one of: "live" (running on this site), "built", "planned".
# `category` matches a key in PROJECT_CATEGORIES.
# `sections` holds the case-study parts that exist today; omit a key rather
# than filling it with guesses. `questions` are the evaluation questions a
# planned project must answer. `evidence` links are only included when real.
PROJECTS = [
    {
        "slug": "agentic-knowledge-base-assistant",
        "name": "Agentic Knowledge Base Assistant",
        "status": "planned",
        "category": "core",
        "icon": "📚",
        "summary": (
            "A retrieval-augmented generation system that answers questions from "
            "custom documents, built to test whether retrieval finds the right "
            "chunk and whether answers stay grounded in the source."
        ),
        "tags": ["RAG", "Retrieval evaluation", "Groundedness", "Applied NLP"],
        "sections": {
            "problem": (
                "Answer questions over a private document set with cited, grounded "
                "responses. Measure that it works rather than assuming it does."
            ),
        },
        "questions": [
            "Did retrieval return the correct document?",
            "Did retrieval return the correct chunk?",
            "Did the generated answer remain grounded in the source?",
            "What happens when the relevant information is missing?",
            "What failure cases were discovered?",
        ],
        "evidence": {},
    },
    {
        "slug": "smart-personal-ai-agent",
        "name": "Smart Personal AI Agent",
        "status": "planned",
        "category": "core",
        "icon": "🛠️",
        "summary": (
            "A multi-tool assistant connected to external APIs (weather, travel, "
            "productivity) to study agent loops, tool calling, error handling, and "
            "permission boundaries."
        ),
        "tags": ["Agents", "Tool calling", "External APIs", "Permissions"],
        "sections": {
            "problem": (
                "Give a model the ability to take actions, then find out how "
                "reliably it chooses tools, validates arguments, and stays inside "
                "its permission boundary."
            ),
        },
        "questions": [
            "Did the model choose the correct tool?",
            "Were the tool arguments valid?",
            "How were invalid requests handled?",
            "What happens when an API fails?",
            "Can the agent take actions outside its permission boundary?",
            "How deterministic is tool selection across runs?",
        ],
        "evidence": {},
    },
    {
        "slug": "multi-agent-research-automation",
        "name": "Multi-Agent Research & Task Automation",
        "status": "planned",
        "category": "core",
        "icon": "🧩",
        "summary": (
            "Planner, Research, and Executor agents coordinating on complex tasks. "
            "The real question: does the extra architecture improve results enough "
            "to justify its complexity?"
        ),
        "tags": ["Multi-agent", "Task decomposition", "Coordination", "Evaluation"],
        "sections": {
            "problem": (
                "Decompose and complete multi-step tasks with specialised agents, "
                "and compare the outcome against a simpler single-agent baseline "
                "instead of assuming more agents is better."
            ),
        },
        "questions": [
            "Output quality versus a single-agent baseline?",
            "Failure rate and coordination failures?",
            "Latency, token usage, and cost?",
            "How much complexity does the coordination layer add?",
        ],
        "evidence": {},
    },
    {
        "slug": "finance-ai-capstone",
        "name": "Finance AI Capstone",
        "status": "planned",
        "category": "core",
        "icon": "📈",
        "summary": (
            "A longer-term system that brings the other projects together around "
            "financial data: structured outputs, retrieval, agents, tool use, "
            "guardrails, observability, and reliability testing in CI."
        ),
        "tags": ["Financial AI", "Guardrails", "Observability", "Reliability"],
        "sections": {
            "problem": (
                "Financial systems cannot just be impressive; they have to be "
                "accurate, traceable, and controlled. This capstone is where the "
                "evaluation and guardrail work from the earlier projects has to hold "
                "up under stricter requirements."
            ),
        },
        "questions": [
            "Which guardrails are required before an agent may touch financial data?",
            "How is every model decision traced and audited?",
            "What reliability checks run in CI before a change ships?",
        ],
        "evidence": {},
    },
    {
        "slug": "semantic-portfolio-search",
        "name": "Semantic Portfolio Search",
        "status": "live",
        "category": "supporting",
        "icon": "🔍",
        "summary": (
            "The search box on this site. Queries are embedded locally with "
            "sentence-transformers and ranked by cosine similarity against the "
            "portfolio content and blog posts. No external API."
        ),
        "tags": ["Python", "FastAPI", "sentence-transformers", "NumPy", "Embeddings"],
        "sections": {
            "problem": (
                "Let a visitor ask a natural-language question and get the most "
                "relevant part of the portfolio back, without keyword matching or a "
                "hosted vector service."
            ),
            "architecture": (
                "At startup the server derives text chunks from the canonical "
                "content module and every Markdown blog post, embeds them once with "
                "all-MiniLM-L6-v2, and keeps the normalized vectors in a NumPy "
                "array. A query is embedded the same way and scored with a dot "
                "product (equal to cosine similarity for normalized vectors)."
            ),
            "implementation": (
                "The index is built from the same data the pages render, so a new "
                "blog post becomes searchable without touching Python. The model "
                "loads once in the FastAPI lifespan, not per request."
            ),
            "evaluation": (
                "Automated tests check the response schema, that malformed requests "
                "fail with 422, that a query about a blog topic surfaces that post, "
                "and that scores are within the cosine range."
            ),
            "failure_modes": (
                "An earlier version displayed raw cosine similarity as a percentage "
                "\"match\", which reads like a calibrated confidence it is not. It now "
                "shows the similarity value and lets ranking do the work. Short "
                "queries with no overlap still return low-similarity results rather "
                "than saying \"nothing relevant\"."
            ),
            "improvements": (
                "Add a small retrieval evaluation set (query → expected section) so "
                "ranking regressions are caught in CI, and experiment with a "
                "similarity floor for \"no good match\"."
            ),
        },
        "evidence": {
            "try_it": "#search",
            # TODO: add the public repository URL for this portfolio once it is published.
        },
    },
]

# Labels for the case-study sections, in display order.
CASE_STUDY_SECTIONS = [
    ("problem", "Problem"),
    ("architecture", "Architecture"),
    ("implementation", "Implementation"),
    ("evaluation", "Evaluation"),
    ("failure_modes", "Failure modes"),
    ("results", "Results"),
    ("improvements", "Improvements"),
]

STATUS_LABELS = {
    "live": "Live",
    "built": "Built",
    "planned": "Planned",
}


def get_project(slug):
    """Return the project with this slug, or None."""
    for project in PROJECTS:
        if project["slug"] == slug:
            return project
    return None


def projects_in_category(category_key):
    """Return the projects in one PROJECT_CATEGORIES group, in listed order."""
    return [project for project in PROJECTS if project["category"] == category_key]
